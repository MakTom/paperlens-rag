"""Read-only connection, migration and paper-count check."""
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.db.session import build_engine
from src.repositories.paper import PaperRepository


def main() -> int:
    engine = None
    try:
        engine = build_engine()
        with Session(engine) as session:
            session.execute(text("SELECT 1"))
            revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            repository = PaperRepository(session)
            print(f"PASS: PostgreSQL reachable; migration={revision}; papers={repository.count()}")
            for paper in repository.list_papers():
                print(f"{paper.arxiv_id} | {paper.title} | {paper.text_kind}")
        return 0
    except (SQLAlchemyError, ValidationError):
        print("FAIL: check Docker, DB settings and alembic upgrade head.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
