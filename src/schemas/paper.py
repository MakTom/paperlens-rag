from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PaperInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    arxiv_id: str = Field(pattern=r"^\d{4}\.\d{4,5}(v\d+)?$")
    title: NonBlank
    abstract: NonBlank
    source_url: HttpUrl
    categories: list[NonBlank] = Field(min_length=1)
    text_kind: Literal["authored_summary", "source_abstract"] = "authored_summary"

    @model_validator(mode="after")
    def check_source_identity(self):
        if str(self.source_url) != f"https://arxiv.org/abs/{self.arxiv_id}":
            raise ValueError("source_url must match this paper's arXiv ID")
        return self
