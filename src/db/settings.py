from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

from src.config import PROJECT_ROOT


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_prefix="RAG_DB_",
        extra="ignore",
        frozen=True,
    )
    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=55432, ge=1, le=65535)
    name: str = Field(default="paperlens", min_length=1)
    user: str = Field(default="paperlens", min_length=1)
    password: SecretStr = SecretStr("paperlens_local_only")

    def sqlalchemy_url(self) -> URL:
        # URL.create handles passwords containing characters such as @ or /.
        return URL.create(
            "postgresql+psycopg",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.name,
        )
