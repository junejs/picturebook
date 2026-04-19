from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    api_key_env: str | None = None
    base_url: str | None = None
    timeout_seconds: int = Field(default=300, ge=5, le=1800)
    max_retries: int = Field(default=2, ge=0, le=10)
    json_mode: bool = True


class ImageProvidersConfig(BaseModel):
    """支持多个 image provider 配置，通过 active 字段选择当前使用的 provider。

    格式::

        image:
          active: volcengine
          volcengine:
            model: doubao-seedream-3.0-t2i
            api_key_env: VOLCENGINE_API_KEY
          minimax:
            model: image-01
            api_key_env: IMAGE_AI_API_KEY
    """

    active: str
    providers: dict[str, ProviderConfig]

    @model_validator(mode="before")
    @classmethod
    def _normalize_format(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        # 新 YAML 格式：有 active，provider 配置在顶层键中，提取到 providers
        if "active" in data and "providers" not in data:
            active = data["active"]
            providers = {k: v for k, v in data.items() if k != "active"}
            return {"active": active, "providers": providers}
        return data

    def get_active_config(self) -> ProviderConfig:
        config = self.providers.get(self.active)
        if config is None:
            raise ValueError(
                f"active image provider '{self.active}' not found in configured providers: "
                f"{list(self.providers.keys())}"
            )
        return config


class ProvidersConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: ProviderConfig
    image: ImageProvidersConfig


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
    characters_dirname: str = "characters"
    artifacts_dirname: str = "artifacts"
    images_dirname: str = "images"
    output_dirname: str = "output"
    render_dirname: str = "render"
    max_parallel_image_jobs: int = Field(default=1, ge=1, le=8)


class FeaturesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enable_reference_image: bool = False


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    default_style: str = "picture book"


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providers: ProvidersConfig
    render: RenderConfig = RenderConfig()
    runtime: RuntimeConfig = RuntimeConfig()
    features: FeaturesConfig = FeaturesConfig()
    app: AppConfig = AppConfig()


class BookConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    idea: str
    language: str = "zh-CN"
    target_age: str = "4-6"
    style: str = "picture book"
    page_count: int = Field(ge=4, le=16)
    characters: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("id")
    @classmethod
    def validate_book_id(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "-")
        if not normalized:
            raise ValueError("book id cannot be empty")
        return normalized
