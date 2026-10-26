from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: Annotated[NonBlank, Field(max_length=4000)]
    top_k: int = Field(default=5, ge=1, le=20, strict=True)
    categories: list[NonBlank] = Field(default_factory=list, max_length=10)


class SearchHit(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    source_url: HttpUrl
    categories: list[str]
    text_kind: Literal["authored_summary", "source_abstract"]
    score: float = Field(ge=0, allow_inf_nan=False)


class SearchResponse(BaseModel):
    query: str
    search_mode: Literal["bm25"] = "bm25"
    total: int = Field(ge=0)
    took_ms: int = Field(ge=0)
    hits: list[SearchHit]
