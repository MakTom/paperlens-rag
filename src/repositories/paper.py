from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.models.paper import Paper
from src.schemas.paper import PaperInput


def insert_statement(paper: PaperInput):
    return (
        insert(Paper)
        .values(**paper.model_dump(mode="json"))
        .on_conflict_do_nothing(index_elements=[Paper.arxiv_id])
        .returning(Paper.arxiv_id)
    )


class PaperRepository:
    def __init__(self, session: Session):
        self.session = session

    def insert_if_missing(self, paper: PaperInput) -> bool:
        return self.session.execute(insert_statement(paper)).scalar_one_or_none() is not None

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(Paper)) or 0

    def list_papers(self, limit: int = 20) -> list[Paper]:
        return list(self.session.scalars(select(Paper).order_by(Paper.arxiv_id).limit(limit)))
