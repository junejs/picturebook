from __future__ import annotations

from magicstory_cli.models.config import AppSettings
from magicstory_cli.providers.base import ImageProvider, TextProvider
from magicstory_cli.providers.minimax import MiniMaxImageProvider
from magicstory_cli.providers.openai_compatible import (
    OpenAICompatibleTextProvider,
    OpenAICompatibleVisionProvider,
)
from magicstory_cli.providers.vision_provider import VisionProvider


def build_image_provider(settings: AppSettings) -> ImageProvider:
    provider_name = settings.providers.image.provider.lower()
    if provider_name == "minimax":
        return MiniMaxImageProvider(settings.providers.image)
    raise ValueError(f"unsupported image provider: {settings.providers.image.provider}")


def build_text_provider(settings: AppSettings) -> TextProvider:
    provider_name = settings.providers.text.provider.lower()
    if provider_name in {"openai-compatible", "openai_compatible"}:
        return OpenAICompatibleTextProvider(settings.providers.text)
    raise ValueError(f"unsupported text provider: {settings.providers.text.provider}")


def build_vision_provider(settings: AppSettings) -> VisionProvider:
    if not settings.providers.vision:
        raise RuntimeError("vision provider is not configured in settings")
    provider_name = settings.providers.vision.provider.lower()
    if provider_name in {"openai-compatible", "openai_compatible"}:
        return OpenAICompatibleVisionProvider(settings.providers.vision)
    raise ValueError(f"unsupported vision provider: {settings.providers.vision.provider}")
