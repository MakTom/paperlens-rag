import json

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from scripts.seed_papers import load_seed
from src.models.paper import Paper
from src.repositories.paper import insert_statement
from src.schemas.paper import PaperInput


def test_fixed_corpus_has_five_unique_sourced_summaries():
    papers = load_seed()
    assert len(papers) == len({p.arxiv_id for p in papers}) == 5
    assert all(p.text_kind == "authored_summary" for p in papers)


def test_seed_rejects_duplicates_before_database_access(tmp_path):
    row = load_seed()[0].model_dump(mode="json")
    path = tmp_path / "duplicates.json"
    path.write_text(json.dumps([row, row]))
    with pytest.raises(ValueError, match="Duplicate"):
        load_seed(path)


@pytest.mark.parametrize("field,value", [
    ("title", " "),
    ("abstract", ""),
    ("arxiv_id", "not-an-id"),
    ("source_url", "https://arxiv.org/abs/9999.99999"),
    ("text_kind", "unknown"),
])
def test_invalid_paper_rejected(field, value):
    row = load_seed()[0].model_dump(mode="json")
    row[field] = value
    with pytest.raises(ValidationError):
        PaperInput(**row)


def test_insert_uses_database_conflict_protection():
    sql = str(insert_statement(load_seed()[0]).compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (arxiv_id) DO NOTHING" in sql
    assert "RETURNING papers.arxiv_id" in sql


def test_identity_is_a_database_primary_key():
    assert [column.name for column in Paper.__table__.primary_key] == ["arxiv_id"]
