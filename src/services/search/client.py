"""Small REST adapter using the project's existing HTTPX dependency."""
import json

import httpx
from pydantic import ValidationError

from src.schemas.api.search import SearchHit, SearchRequest, SearchResponse
from src.schemas.paper import PaperInput
from src.services.search.index_definition import INDEX_BODY, SCHEMA_VERSION
from src.services.search.query import build_query
from src.services.search.settings import SearchSettings


class SearchServiceError(RuntimeError):
    """Actionable error without raw remote response bodies."""


def require_object(value) -> dict:
    if not isinstance(value, dict):
        raise SearchServiceError("OpenSearch returned an invalid nested response object.")
    return value


def nonnegative_integer(value) -> int:
    if type(value) is not int or value < 0:
        raise SearchServiceError("OpenSearch returned an invalid integer field.")
    return value


def check_shards(data):
    shards = require_object(data.get("_shards"))
    if nonnegative_integer(shards.get("failed")) != 0:
        raise SearchServiceError("OpenSearch reported shard failures.")


class SearchClient:
    def __init__(self, settings: SearchSettings | None = None, *, transport=None):
        self.settings = settings or SearchSettings()
        self.http = httpx.Client(
            base_url=str(self.settings.base_url).rstrip("/") + "/",
            timeout=httpx.Timeout(self.settings.timeout_seconds, connect=5),
            trust_env=False,
            transport=transport,
        )

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _request(self, method, path, **kwargs):
        try:
            response = self.http.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise SearchServiceError("OpenSearch request timed out.") from exc
        except httpx.RequestError as exc:
            raise SearchServiceError("Cannot reach OpenSearch. Check Docker and search settings.") from exc
        if response.status_code == 404:
            raise SearchServiceError("Search index or endpoint missing. Run scripts.index_papers.")
        if response.is_error:
            raise SearchServiceError(f"OpenSearch returned HTTP {response.status_code}.")
        try:
            data = response.json()
        except ValueError as exc:
            raise SearchServiceError("OpenSearch returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise SearchServiceError("OpenSearch returned an unexpected response.")
        return data

    def ensure_index(self):
        try:
            response = self.http.head(self.settings.index)
        except httpx.RequestError as exc:
            raise SearchServiceError("Cannot reach OpenSearch.") from exc
        if response.status_code == 404:
            data = self._request("PUT", self.settings.index, json=INDEX_BODY)
            if data.get("acknowledged") is not True:
                raise SearchServiceError("Index creation was not acknowledged.")
        elif response.status_code != 200:
            raise SearchServiceError(f"Index check returned HTTP {response.status_code}.")
        data = self._request("GET", f"{self.settings.index}/_mapping")
        index = require_object(data.get(self.settings.index, {}))
        mappings = require_object(index.get("mappings", {}))
        metadata = require_object(mappings.get("_meta", {}))
        version = metadata.get("schema_version")
        if version != SCHEMA_VERSION:
            raise SearchServiceError("Existing index has a different schema; choose a new index name.")

    def index_batch(self, papers: list[PaperInput]) -> int:
        if not papers:
            return 0
        lines = []
        for paper in papers:
            lines.append(json.dumps({"index": {"_index": self.settings.index, "_id": paper.arxiv_id}}))
            lines.append(json.dumps(paper.model_dump(mode="json")))
        data = self._request(
            "POST", "_bulk", content=("\n".join(lines) + "\n").encode("utf-8"),
            headers={"Content-Type": "application/x-ndjson"},
        )
        items = data.get("items", [])
        if not isinstance(items, list) or len(items) != len(papers):
            raise SearchServiceError("Bulk response does not account for every submitted paper.")
        failed = []
        for paper, item in zip(papers, items):
            operation = item.get("index") if isinstance(item, dict) else None
            if (not isinstance(operation, dict)
                    or type(operation.get("status")) is not int
                    or operation["status"] not in (200, 201)
                    or operation.get("error")):
                failed.append(paper.arxiv_id)
        if failed or data.get("errors") is not False:
            raise SearchServiceError(
                "Some records may have been indexed. Retry after resolving errors. "
                f"Failed IDs: {', '.join(failed) or 'unknown'}"
            )
        return len(papers)

    def refresh(self):
        data = self._request("POST", f"{self.settings.index}/_refresh")
        check_shards(data)

    def count(self) -> int:
        data = self._request("GET", f"{self.settings.index}/_count")
        check_shards(data)
        count = data.get("count")
        if type(count) is not int or count < 0:
            raise SearchServiceError("Invalid document count.")
        return count

    def search(self, request: SearchRequest) -> SearchResponse:
        data = self._request(
            "POST", f"{self.settings.index}/_search", json=build_query(request),
            params={"allow_partial_search_results": "false"},
        )
        check_shards(data)
        if data.get("timed_out") is not False:
            raise SearchServiceError("OpenSearch did not report a completed search.")
        hit_block = require_object(data.get("hits"))
        total = require_object(hit_block.get("total"))
        total_value = nonnegative_integer(total.get("value"))
        took = nonnegative_integer(data.get("took"))
        raw_hits = hit_block.get("hits")
        if total.get("relation") != "eq" or not isinstance(raw_hits, list):
            raise SearchServiceError("OpenSearch returned incomplete search totals or hits.")
        if len(raw_hits) > request.top_k or len(raw_hits) != min(total_value, request.top_k):
            raise SearchServiceError("OpenSearch returned inconsistent hit counts.")
        try:
            hits = []
            for hit in raw_hits:
                hit = require_object(hit)
                source = require_object(hit.get("_source"))
                score = hit.get("_score")
                if type(score) not in (float, int):
                    raise SearchServiceError("OpenSearch returned an invalid relevance score.")
                hits.append(SearchHit(**source, score=score))
            return SearchResponse(query=request.query, total=total_value, took_ms=took, hits=hits)
        except (TypeError, ValidationError) as exc:
            raise SearchServiceError("Search results do not match the expected paper schema.") from exc
