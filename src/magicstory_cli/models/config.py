from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    api_key_env: str | None = None
    base_url: str | None = None
    timeout_seconds: int = Field(default=300, ge=5, le=1800)


class ProvidersConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: ProviderConfig
    image: ProviderConfig


class RenderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_size: str = "210mmx210mm"
    include_cover: bool = True
    text_layout: Literal["bottom-band", "overlay", "full-page-text"] = "bottom-band"
    body_font: str = "Noto Sans SC"
    heading_font: str = "Noto Serif SC"
    dpi: int = Field(default=144, ge=72, le=600)


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_dir: Path = Path("projects")
    artifacts_dirname: str = "artifacts"
    images_dirname: str = "images"
    output_dirname: str = "output"
    render_dirname: str = "render"
    max_parallel_image_jobs: int = Field(default=1, ge=1, le=8)


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providers: ProvidersConfig
    render: RenderConfig = RenderConfig()
    runtime: RuntimeConfig = RuntimeConfig()


class BookConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    idea: str
    language: str = "zh-CN"
    target_age: str = "4-6"
    style: str
    page_count: int = Field(ge=4, le=16)
    notes: str | None = None

    @field_validator("id")
    @classmethod
    def validate_book_id(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "-")
        if not normalized:
            raise ValueError("book id cannot be empty")
        return normalized
