"""One validated configuration object shared by scripts and future API code."""
from pathlib import Path

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="RAG_",
        extra="ignore",
        frozen=True,
    )

    app_name: str = "research-paper-rag"
    ollama_base_url: HttpUrl = HttpUrl("http://localhost:11434")
    ollama_model: str = "llama3.2:1b"
    request_timeout_seconds: float = Field(default=180, gt=0, le=600)

    @field_validator("app_name", "ollama_model")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("ollama_base_url")
    @classmethod
    def require_server_url(cls, value: HttpUrl) -> HttpUrl:
        if value.username or value.password or value.query or value.fragment:
            raise ValueError("use a server URL without credentials, query or fragment")
        if value.path not in (None, "", "/"):
            raise ValueError("use the server root, without an API path")
        return value
