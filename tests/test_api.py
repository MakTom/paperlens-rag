import pytest
from pydantic import ValidationError

from src.schemas.api.ask import AskRequest, AskResponse


def test_health_is_api_liveness_only(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_name": "paperlens-test",
        "version": "0.6.0",
        "scope": "api_only",
    }


@pytest.mark.parametrize("body", [
    {},
    {"query": ""},
    {"query": "   "},
    {"query": "x" * 4001},
    {"query": "RAG", "top_k": 0},
    {"query": "RAG", "top_k": 21},
    {"query": "RAG", "top_k": True},
    {"query": "RAG", "top_k": "5"},
    {"query": "RAG", "use_hybrid": "yes"},
    {"query": "RAG", "categories": [" "]},
    {"query": "RAG", "model": " "},
    {"query": "RAG", "unexpected": "field"},
])
def test_invalid_questions_return_422(client, body):
    assert client.post("/api/v1/ask", json=body).status_code == 422


def test_schema_trims_text_and_sets_defaults():
    request = AskRequest(query="  What is RAG?  ")
    assert request.query == "What is RAG?"
    assert request.top_k == 5
    assert request.use_hybrid is False
    assert request.categories == []


def test_response_contract_rejects_invalid_search_mode():
    with pytest.raises(ValidationError):
        AskResponse(query="RAG?", answer="Answer", chunks_used=1, search_mode="unknown")


def test_openapi_contains_question_contracts(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schemas = response.json()["components"]["schemas"]
    assert "AskRequest" in schemas
    assert "AskResponse" in schemas


def test_unknown_route_is_404(client):
    assert client.get("/api/v1/missing").status_code == 404
