import socket

import pytest
from fastapi.testclient import TestClient

from src.config import Settings
from src.main import create_app


@pytest.fixture(autouse=True)
def prevent_external_connections(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Offline tests must not connect to external services.")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture
def client():
    # Explicit values and _env_file=None isolate tests from a developer's .env.
    settings = Settings(
        _env_file=None,
        app_name="paperlens-test",
        ollama_base_url="http://localhost:11434",
        ollama_model="test-model",
        request_timeout_seconds=10,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client
