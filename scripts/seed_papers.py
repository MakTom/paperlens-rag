"""Validate the entire fixed corpus, then insert missing IDs in one transaction."""
import argparse
from pathlib import Path

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config import PROJECT_ROOT
from src.db.session import build_engine
from src.repositories.paper import PaperRepository
from src.schemas.paper import PaperInput

DEFAULT_SEED = PROJECT_ROOT / "fixtures" / "papers.seed.json"


def load_seed(path: Path = DEFAULT_SEED) -> list[PaperInput]:
    papers = TypeAdapter(list[PaperInput]).validate_json(path.read_text(encoding="utf-8"))
    if not papers:
        raise ValueError("Seed must contain at least one paper.")
    ids = [paper.arxiv_id for paper in papers]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate arXiv IDs in the seed file.")
    return papers


def seed_papers(engine, papers: list[PaperInput]) -> dict[str, int]:
    # The context commits only if all inserts succeed; otherwise it rolls back.
    with Session(engine) as session, session.begin():
        repository = PaperRepository(session)
        inserted = sum(repository.insert_if_missing(paper) for paper in papers)
        total = repository.count()
    return {"inserted": inserted, "skipped": len(papers) - inserted, "total": total}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_SEED)
    args = parser.parse_args()
    engine = None
    try:
        papers = load_seed(args.file)
        engine = build_engine()
        result = seed_papers(engine, papers)
        print("Seed complete: " + ", ".join(f"{k}={v}" for k, v in result.items()))
        return 0
    except (OSError, ValueError, ValidationError):
        print("FAIL: invalid seed file or settings. Check the file, IDs and source URLs.")
        return 1
    except SQLAlchemyError:
        print("FAIL: database operation failed. Check Docker/settings and run alembic upgrade head.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
