"""Copy PostgreSQL records into a rebuildable search index, in bounded batches."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.paper import Paper
from src.schemas.paper import PaperInput


def index_papers(engine, search, batch_size: int = 100) -> dict[str, int]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    search.ensure_index()
    processed = 0
    with Session(engine) as session:
        rows = session.scalars(
            select(Paper).order_by(Paper.arxiv_id).execution_options(yield_per=batch_size)
        )
        batch = []
        for row in rows:
            batch.append(PaperInput(
                arxiv_id=row.arxiv_id, title=row.title, abstract=row.abstract,
                source_url=row.source_url, categories=row.categories, text_kind=row.text_kind,
            ))
            if len(batch) == batch_size:
                processed += search.index_batch(batch)
                batch = []
        if batch:
            processed += search.index_batch(batch)
    search.refresh()
    return {"indexed": processed, "index_total": search.count()}
