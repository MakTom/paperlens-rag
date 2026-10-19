"""Define the future RAG contract before wiring retrieval and generation."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[NonBlankText, Field(max_length=4000)]
    top_k: int = Field(default=5, ge=1, le=20, strict=True)
    use_hybrid: bool = Field(default=False, strict=True)
    categories: list[NonBlankText] = Field(default_factory=list, max_length=10)
    # None means use the model selected in Settings.
    model: NonBlankText | None = None


class AskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: NonBlankText
    answer: NonBlankText
    sources: list[str] = Field(default_factory=list)
    chunks_used: int = Field(ge=0)
    search_mode: Literal["bm25", "vector", "hybrid"]
