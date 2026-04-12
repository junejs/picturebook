from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PageSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1)
    story_text: str
    illustration_prompt: str
    image_path: str | None = None


class BookSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    language: str
    target_age: str
    style: str
    page_count: int = Field(ge=4, le=16)
    pages: list[PageSpec] = Field(default_factory=list)
