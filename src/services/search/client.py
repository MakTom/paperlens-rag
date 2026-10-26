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
        version = (
            data.get(self.settings.index, {}).get("mappings", {})
            .get("_meta", {}).get("schema_version")
        )
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
        failed = [
            paper.arxiv_id for paper, item in zip(papers, items)
            if not isinstance(item, dict)
            or item.get("index", {}).get("status") not in (200, 201)
            or item.get("index", {}).get("error")
        ]
        if failed or data.get("errors") is not False:
            raise SearchServiceError(
                "Some records may have been indexed. Retry after resolving errors. "
                f"Failed IDs: {', '.join(failed) or 'unknown'}"
            )
        return len(papers)

    def refresh(self):
        data = self._request("POST", f"{self.settings.index}/_refresh")
        if data.get("_shards", {}).get("failed", 0):
            raise SearchServiceError("Index refresh reported shard failures.")

    def count(self) -> int:
        data = self._request("GET", f"{self.settings.index}/_count")
        if data.get("_shards", {}).get("failed", 0):
            raise SearchServiceError("Count reported shard failures.")
        count = data.get("count")
        if type(count) is not int or count < 0:
            raise SearchServiceError("Invalid document count.")
        return count

    def search(self, request: SearchRequest) -> SearchResponse:
        data = self._request(
            "POST", f"{self.settings.index}/_search", json=build_query(request),
            params={"allow_partial_search_results": "false"},
        )
        if data.get("timed_out") or data.get("_shards", {}).get("failed", 0):
            raise SearchServiceError("OpenSearch could not return a complete search result.")
        try:
            hits = [
                SearchHit(**hit["_source"], score=hit["_score"])
                for hit in data["hits"]["hits"]
            ]
            return SearchResponse(
                query=request.query, total=data["hits"]["total"]["value"],
                took_ms=data["took"], hits=hits,
            )
        except (KeyError, TypeError, ValidationError) as exc:
            raise SearchServiceError("Search results do not match the expected paper schema.") from exc
