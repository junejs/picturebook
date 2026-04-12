from __future__ import annotations

import pytest
from pydantic import ValidationError

from magicstory_cli.models.config import AppSettings, BookConfig


def test_book_id_is_normalized() -> None:
    book = BookConfig(
        id="  My Book  ",
        title="Moon Garden",
        idea="A rabbit looks for a glowing flower.",
        style="warm watercolor picture book",
        page_count=12,
    )

    assert book.id == "my-book"


@pytest.mark.parametrize("page_count", [3, 17])
def test_book_page_count_must_stay_in_supported_range(page_count: int) -> None:
    with pytest.raises(ValidationError):
        BookConfig(
            id="moon-garden",
            title="Moon Garden",
            idea="A rabbit looks for a glowing flower.",
            style="warm watercolor picture book",
            page_count=page_count,
        )


def test_app_settings_accept_model_related_configuration_blocks() -> None:
    settings = AppSettings.model_validate(
        {
            "providers": {
                "text": {
                    "provider": "openai-compatible",
                    "model": "gpt-4.1-mini",
                    "api_key_env": "TEXT_AI_API_KEY",
                    "base_url": None,
                    "timeout_seconds": 300,
                    "max_retries": 2,
                },
                "image": {
                    "provider": "minimax",
                    "model": "image-01",
                    "api_key_env": "IMAGE_AI_API_KEY",
                    "base_url": "https://api.minimaxi.com",
                    "timeout_seconds": 300,
                    "max_retries": 2,
                },
                "vision": {
                    "provider": "openai-compatible",
                    "model": "gpt-4.1-mini",
                    "api_key_env": "VISION_AI_API_KEY",
                    "base_url": None,
                    "timeout_seconds": 300,
                    "max_retries": 2,
                },
            },
            "features": {"enable_reference_image": False},
            "app": {"log_level": "info"},
        }
    )

    assert settings.providers.text.max_retries == 2
    assert settings.providers.image.api_key_env == "IMAGE_AI_API_KEY"
    assert settings.providers.vision is not None
    assert settings.app.log_level == "info"
