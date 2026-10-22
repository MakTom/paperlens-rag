"""Live PostgreSQL checks. Inserts the fixture but never deletes existing papers."""
from sqlalchemy.orm import Session

from scripts.seed_papers import load_seed, seed_papers
from src.db.session import build_engine
from src.models.paper import Paper


def verify(engine):
    papers = load_seed()
    first = seed_papers(engine, papers)
    with Session(engine) as session:
        before = {p.arxiv_id: session.get(Paper, p.arxiv_id).created_at for p in papers}
    second = seed_papers(engine, papers)
    if second["inserted"] != 0 or second["skipped"] != len(papers):
        raise AssertionError("Repeated seed inserted duplicate records.")
    if first["total"] != second["total"]:
        raise AssertionError("Paper count changed on the second run.")
    with Session(engine) as session:
        after = {p.arxiv_id: session.get(Paper, p.arxiv_id).created_at for p in papers}
        if before != after:
            raise AssertionError("Repeated seed modified creation timestamps.")

    # Verify rollback using an existing row; leave persisted data unchanged.
    with Session(engine) as session:
        paper = session.get(Paper, papers[0].arxiv_id)
        original = paper.title
        paper.title = "Temporary rollback check"
        session.flush()
        session.rollback()
        session.expire_all()
        if session.get(Paper, papers[0].arxiv_id).title != original:
            raise AssertionError("Transaction rollback failed.")
    print(f"PASS: {len(papers)} fixture IDs present; second seed inserted=0; rollback verified.")


if __name__ == "__main__":
    engine = build_engine()
    try:
        verify(engine)
    finally:
        engine.dispose()
