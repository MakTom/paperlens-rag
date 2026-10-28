import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.config import PROJECT_ROOT
from src.schemas.api.ask import AskRequest
from src.schemas.paper import PaperInput


def fingerprint(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def canonical_corpus(papers):
    normalized = [PaperInput.model_validate(p).model_dump(mode="json") for p in papers]
    ids = [p["arxiv_id"] for p in normalized]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate corpus IDs")
    return sorted(normalized, key=lambda p: p["arxiv_id"])


class EvidenceLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    arxiv_id: str
    passage: str = Field(min_length=1)


class EvalCase(AskRequest):
    id: str = Field(min_length=1)
    split: Literal["dev", "holdout"]
    supported: bool = Field(strict=True)
    kind: str
    relevant_paper_ids: list[str]
    expected_answer_points: list[str]
    evidence: list[EvidenceLabel]
    unsupported_reason: str | None = None

    @model_validator(mode="after")
    def consistent_labels(self):
        if len(self.relevant_paper_ids) != len(set(self.relevant_paper_ids)):
            raise ValueError("Duplicate relevance labels")
        if self.supported:
            if not self.relevant_paper_ids or not self.expected_answer_points or not self.evidence:
                raise ValueError("Supported cases require relevance, expected points and evidence")
            if self.unsupported_reason:
                raise ValueError("Supported cases cannot have an unsupported reason")
        elif self.relevant_paper_ids or self.expected_answer_points or self.evidence or not self.unsupported_reason:
            raise ValueError("Unsupported cases require a reason and no positive labels")
        if self.use_hybrid or self.model is not None:
            raise ValueError("Evaluation uses configured BM25 and model only")
        return self


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_version: str
    corpus_version: str
    corpus_sha256: str
    cases: list[EvalCase]


def load_dataset(path: Path | None = None, corpus_path: Path | None = None) -> Dataset:
    path = path or PROJECT_ROOT / "eval/questions.v1.json"
    corpus_path = corpus_path or PROJECT_ROOT / "fixtures/papers.seed.json"
    dataset = Dataset.model_validate_json(path.read_text())
    papers = canonical_corpus(json.loads(corpus_path.read_text()))
    if fingerprint(papers) != dataset.corpus_sha256:
        raise ValueError("Fixture corpus changed; version the corpus and relabel evaluation")
    ids = [c.id for c in dataset.cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate evaluation IDs")
    if len(ids) != 12 or sum(c.supported for c in dataset.cases) != 8:
        raise ValueError("v1 must contain 12 cases: 8 supported and 4 unsupported")
    if sum(c.split == "holdout" for c in dataset.cases) != 4:
        raise ValueError("v1 reserves four holdout cases")
    records = {p["arxiv_id"]: p for p in papers}
    for case in dataset.cases:
        if set(e.arxiv_id for e in case.evidence) != set(case.relevant_paper_ids):
            raise ValueError(f"Evidence labels disagree with relevant IDs: {case.id}")
        for evidence in case.evidence:
            paper = records.get(evidence.arxiv_id)
            if paper is None or evidence.passage not in paper["abstract"]:
                raise ValueError(f"Evidence is not a verbatim fixture passage: {case.id}")
            if case.categories and not set(case.categories).intersection(paper["categories"]):
                raise ValueError(f"Positive label excluded by categories: {case.id}")
    return dataset
