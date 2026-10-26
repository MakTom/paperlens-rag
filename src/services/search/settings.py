from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config import PROJECT_ROOT


class SearchSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_prefix="RAG_SEARCH_", extra="ignore", frozen=True,
    )
    base_url: HttpUrl = HttpUrl("http://127.0.0.1:59200")
    index: str = Field(default="paperlens-papers-v1", pattern=r"^[a-z][a-z0-9_-]{0,99}$")
    timeout_seconds: float = Field(default=20, gt=0, le=120)

    @field_validator("base_url")
    @classmethod
    def require_server_root(cls, value):
        if (value.username or value.password or value.query or value.fragment
                or value.path not in (None, "", "/")):
            raise ValueError("Use an HTTP(S) server root without credentials or an API path.")
        return value
