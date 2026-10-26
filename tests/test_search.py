import json

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from scripts.seed_papers import load_seed
from src.db.session import Base
from src.models.paper import Paper
from src.routers.search import get_search_client
from src.schemas.api.search import SearchRequest, SearchResponse
from src.services.search.client import SearchClient, SearchServiceError
from src.services.search.index_definition import SCHEMA_VERSION
from src.services.search.indexer import index_papers
from src.services.search.query import build_query
from src.services.search.settings import SearchSettings


def settings():
    return SearchSettings(
        _env_file=None, base_url="http://localhost:59200",
        index="paperlens-papers-v1", timeout_seconds=10,
    )


def result_body():
    return {
        "took": 2, "timed_out": False, "_shards": {"failed": 0},
        "hits": {
            "total": {"value": 1, "relation": "eq"},
            "hits": [{"_score": 3.5, "_source": load_seed()[0].model_dump(mode="json")}],
        },
    }


def test_query_boost_and_exact_filter():
    body = build_query(SearchRequest(query="retrieval", top_k=3, categories=["cs.CL"]))
    assert body["size"] == 3
    assert body["query"]["bool"]["must"][0]["multi_match"]["fields"] == ["title^2", "abstract"]
    assert body["query"]["bool"]["filter"] == [{"terms": {"categories": ["cs.CL"]}}]


def test_valid_search_parses_sources():
    def handle(request):
        assert request.method == "POST"
        assert request.url.params["allow_partial_search_results"] == "false"
        return httpx.Response(200, json=result_body())
    with SearchClient(settings(), transport=httpx.MockTransport(handle)) as search:
        result = search.search(SearchRequest(query="retrieval"))
    assert result.total == 1
    assert result.hits[0].arxiv_id == load_seed()[0].arxiv_id
    assert result.hits[0].text_kind == "authored_summary"


@pytest.mark.parametrize("status", [404, 500, 429])
def test_backend_http_errors_are_not_empty_results(status):
    with SearchClient(settings(), transport=httpx.MockTransport(
        lambda request: httpx.Response(status, json={})
    )) as search:
        with pytest.raises(SearchServiceError):
            search.search(SearchRequest(query="retrieval"))


@pytest.mark.parametrize("exception", [
    httpx.ConnectError("offline"), httpx.ReadTimeout("slow"),
])
def test_network_failure_is_actionable(exception):
    def handle(request):
        raise exception
    with SearchClient(settings(), transport=httpx.MockTransport(handle)) as search:
        with pytest.raises(SearchServiceError):
            search.search(SearchRequest(query="retrieval"))


@pytest.mark.parametrize("body", [
    {"timed_out": True},
    {"_shards": {"failed": 1}},
    {"hits": {}, "took": 1},
    [],
])
def test_incomplete_or_invalid_results_are_rejected(body):
    with SearchClient(settings(), transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=body)
    )) as search:
        with pytest.raises(SearchServiceError):
            search.search(SearchRequest(query="retrieval"))


def test_bulk_uses_stable_ids_and_final_newline():
    paper = load_seed()[0]
    def handle(request):
        assert request.content.endswith(b"\n")
        lines = request.content.decode().splitlines()
        assert json.loads(lines[0])["index"]["_id"] == paper.arxiv_id
        assert json.loads(lines[1])["abstract"] == paper.abstract
        return httpx.Response(200, json={"errors": False, "items": [{"index": {"status": 201}}]})
    with SearchClient(settings(), transport=httpx.MockTransport(handle)) as search:
        assert search.index_batch([paper]) == 1


def test_partial_bulk_failure_fails_command():
    with SearchClient(settings(), transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={
            "errors": True, "items": [{"index": {"status": 400, "error": {"type": "mapping"}}}],
        })
    )) as search:
        with pytest.raises(SearchServiceError, match=load_seed()[0].arxiv_id):
            search.index_batch([load_seed()[0]])


def test_create_index_only_when_missing():
    methods = []
    def handle(request):
        methods.append(request.method)
        if request.method == "HEAD":
            return httpx.Response(404)
        if request.method == "PUT":
            return httpx.Response(200, json={"acknowledged": True})
        return httpx.Response(200, json={
            settings().index: {"mappings": {"_meta": {"schema_version": SCHEMA_VERSION}}},
        })
    with SearchClient(settings(), transport=httpx.MockTransport(handle)) as search:
        search.ensure_index()
    assert methods == ["HEAD", "PUT", "GET"]


def test_foreign_index_is_not_overwritten():
    methods = []
    def handle(request):
        methods.append(request.method)
        return httpx.Response(200, json={})
    with SearchClient(settings(), transport=httpx.MockTransport(handle)) as search:
        with pytest.raises(SearchServiceError, match="different schema"):
            search.ensure_index()
    assert methods == ["HEAD", "GET"]


@pytest.mark.parametrize("body", [
    {}, {"query": " "}, {"query": "retrieval", "top_k": 0},
    {"query": "retrieval", "top_k": 21},
    {"query": "retrieval", "categories": [" "]},
    {"query": "retrieval", "use_hybrid": True},
])
def test_search_api_invalid_input(client, body):
    class NeverSearch:
        def search(self, request):
            raise AssertionError("Invalid requests must not reach search.")
    client.app.dependency_overrides[get_search_client] = lambda: NeverSearch()
    assert client.post("/api/v1/search", json=body).status_code == 422


def test_search_api_returns_200_and_empty_matches(client):
    class EmptySearch:
        def search(self, request):
            return SearchResponse(query=request.query, total=0, took_ms=1, hits=[])
    client.app.dependency_overrides[get_search_client] = lambda: EmptySearch()
    response = client.post("/api/v1/search", json={"query": "unknown"})
    assert response.status_code == 200
    assert response.json()["hits"] == []
    assert response.json()["search_mode"] == "bm25"


def test_search_api_outage_returns_503(client):
    class FailedSearch:
        def search(self, request):
            raise SearchServiceError("Cannot reach OpenSearch.")
    client.app.dependency_overrides[get_search_client] = lambda: FailedSearch()
    response = client.post("/api/v1/search", json={"query": "retrieval"})
    assert response.status_code == 503
    assert "Cannot reach" in response.json()["detail"]


def test_indexer_batches_all_source_rows_without_changing_db():
    # SQLite tests iteration and serialization only, not PostgreSQL integration.
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    papers = load_seed()
    with Session(engine) as session, session.begin():
        session.add_all(Paper(**p.model_dump(mode="json")) for p in papers)
    class RecordingSearch:
        def __init__(self):
            self.batches = []
        def ensure_index(self):
            pass
        def index_batch(self, batch):
            self.batches.append(batch)
            return len(batch)
        def refresh(self):
            pass
        def count(self):
            return sum(len(b) for b in self.batches)
    try:
        search = RecordingSearch()
        result = index_papers(engine, search, batch_size=2)
        assert [len(b) for b in search.batches] == [2, 2, 1]
        assert {p.arxiv_id for b in search.batches for p in b} == {p.arxiv_id for p in papers}
        assert result == {"indexed": 5, "index_total": 5}
        with Session(engine) as session:
            assert session.query(Paper).count() == 5
    finally:
        engine.dispose()

