from copy import deepcopy
from types import SimpleNamespace
import subprocess

import httpx
import pytest

from scripts.seed_papers import load_seed
from scripts.verify_week1 import run_stages
from src.routers.ask import get_generator
from src.routers.search import get_search_client
from src.schemas.api.search import SearchRequest
from src.services.search.client import SearchClient, SearchServiceError
from src.services.search.index_definition import SCHEMA_VERSION
from src.services.search.settings import SearchSettings


def settings():
    return SearchSettings(_env_file=None)


def valid_result():
    return {"timed_out": False, "took": 1, "_shards": {"failed": 0},
            "hits": {"total": {"value": 1, "relation": "eq"},
                     "hits": [{"_score": 2, "_source": load_seed()[0].model_dump(mode="json")}]}}


def search_for(body):
    return SearchClient(settings(), transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=body)))


@pytest.mark.parametrize("field,value", [
    ("_shards", None), ("_shards", []), ("_shards", {"failed": "0"}),
    ("_shards", {"failed": True}), ("_shards", {}),
    ("hits", None), ("hits", []), ("timed_out", "false"), ("took", True),
])
def test_malformed_nested_payload_becomes_service_error(field, value):
    body = valid_result()
    body[field] = value
    with search_for(body) as search, pytest.raises(SearchServiceError):
        search.search(SearchRequest(query="retrieval"))


@pytest.mark.parametrize("change", ["approximate", "null_hits", "null_total", "missing_hit", "null_score", "null_source"])
def test_incomplete_or_malformed_hit_data_is_rejected(change):
    body = valid_result()
    if change == "approximate":
        body["hits"]["total"]["relation"] = "gte"
    elif change == "null_hits":
        body["hits"]["hits"] = None
    elif change == "null_total":
        body["hits"]["total"] = None
    elif change == "missing_hit":
        body["hits"]["hits"] = []
    elif change == "null_score":
        body["hits"]["hits"][0]["_score"] = None
    else:
        body["hits"]["hits"][0]["_source"] = None
    with search_for(body) as search, pytest.raises(SearchServiceError):
        search.search(SearchRequest(query="retrieval"))


@pytest.mark.parametrize("path", ["/api/v1/search", "/api/v1/ask"])
def test_real_adapter_bad_response_returns_503_not_500(client, path):
    class NeverGenerate:
        def generate(self, *args, **kwargs):
            raise AssertionError("Malformed retrieval must not reach generation")
    with search_for({"_shards": None}) as search:
        client.app.dependency_overrides[get_search_client] = lambda: search
        client.app.dependency_overrides[get_generator] = lambda: NeverGenerate()
        response = client.post(path, json={"query": "retrieval"})
    assert response.status_code == 503
    assert "invalid nested response" in response.json()["detail"]


@pytest.mark.parametrize("operation", [None, [], {"status": True}, {"status": "201"}])
def test_malformed_bulk_operation_reports_failed_id(operation):
    body = {"errors": False, "items": [{"index": operation}]}
    paper = load_seed()[0]
    with search_for(body) as search, pytest.raises(SearchServiceError, match=paper.arxiv_id):
        search.index_batch([paper])


@pytest.mark.parametrize("method", ["count", "refresh"])
def test_count_and_refresh_reject_null_shards(method):
    with search_for({"_shards": None, "count": 5}) as search, pytest.raises(SearchServiceError):
        getattr(search, method)()


def test_malformed_mapping_is_service_error_and_never_deleted():
    seen = []
    def handler(request):
        seen.append(request.method)
        if request.method == "HEAD":
            return httpx.Response(200)
        return httpx.Response(200, json={settings().index: {"mappings": None}})
    with SearchClient(settings(), transport=httpx.MockTransport(handler)) as search:
        with pytest.raises(SearchServiceError):
            search.ensure_index()
    assert seen == ["HEAD", "GET"]


def test_valid_mapping_and_empty_search_still_work():
    def handler(request):
        if request.method == "HEAD":
            return httpx.Response(200)
        if request.url.path.endswith("_mapping"):
            return httpx.Response(200, json={settings().index: {"mappings": {"_meta": {"schema_version": SCHEMA_VERSION}}}})
        return httpx.Response(200, json={"timed_out": False, "took": 0, "_shards": {"failed": 0},
            "hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}})
    with SearchClient(settings(), transport=httpx.MockTransport(handler)) as search:
        search.ensure_index()
        assert search.search(SearchRequest(query="unknown")).hits == []


def test_verification_stops_on_failure_and_marks_remaining_not_run():
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1)
    rows = run_stages([("db", ["scripts.check_db"], 10), ("model", ["scripts.smoke_llm"], 10)], execute)
    assert [r["status"] for r in rows] == ["failed", "not_run"]
    assert len(calls) == 1


def test_verification_preserves_order_and_invokes_python_modules():
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        assert kwargs["check"] is False
        return SimpleNamespace(returncode=0)
    stages = [("a", ["scripts.check_config"], 10), ("b", ["scripts.evaluate", "--retrieval-only"], 20)]
    rows = run_stages(stages, execute)
    assert all(r["status"] == "passed" for r in rows)
    assert calls[0][1:] == ["-m", "scripts.check_config"]
    assert calls[1][-1] == "--retrieval-only"


@pytest.mark.parametrize("exception,status", [
    (subprocess.TimeoutExpired("test", 1), "timed_out"), (OSError("test"), "could_not_start"),
])
def test_verification_operational_errors_are_not_success(exception, status):
    def execute(*args, **kwargs):
        raise exception
    rows = run_stages([("a", ["test"], 1)], execute)
    assert rows[0]["status"] == status


def test_snapshot_input_fixture_not_modified_by_validation():
    body = valid_result()
    before = deepcopy(body)
    with search_for(body) as search:
        result = search.search(SearchRequest(query="retrieval"))
    assert result.total == 1 and body == before
