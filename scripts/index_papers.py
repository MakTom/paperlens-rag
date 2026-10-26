"""Index existing PostgreSQL papers. This command does not seed or delete data."""
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from src.db.session import build_engine
from src.services.search.client import SearchClient, SearchServiceError
from src.services.search.indexer import index_papers


def main():
    engine = None
    try:
        engine = build_engine()
        with SearchClient() as search:
            result = index_papers(engine, search)
        print("Index complete: " + ", ".join(f"{k}={v}" for k, v in result.items()))
        if result["indexed"] == 0:
            print("NOTE: no PostgreSQL records found. Run scripts.seed_papers first.")
        return 0
    except SearchServiceError as exc:
        print(f"FAIL: {exc}")
        return 1
    except (SQLAlchemyError, ValidationError):
        print("FAIL: check database connectivity, migrations, source records and settings.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
