from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

from src.db.settings import DatabaseSettings


class Base(DeclarativeBase):
    pass


def build_engine(settings: DatabaseSettings | None = None):
    settings = settings or DatabaseSettings()
    return create_engine(
        settings.sqlalchemy_url(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=15000"},
    )
