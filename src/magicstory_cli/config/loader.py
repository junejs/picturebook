from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from magicstory_cli.models.config import AppSettings, BookConfig

logger = logging.getLogger(__name__)


def load_yaml(path: Path) -> dict[str, Any]:
    logger.debug("Loading YAML: %s", path)
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping at the top level")
    return data


def load_settings(path: Path) -> AppSettings:
    settings = AppSettings.model_validate(load_yaml(path))
    logger.info("Settings loaded from %s (log_level=%s)", path, settings.app.log_level)
    return settings


def load_book_config(path: Path) -> BookConfig:
    data = load_yaml(path)
    book_data = data.get("book", data)
    book = BookConfig.model_validate(book_data)
    logger.info("Book config loaded: %s (%d pages)", book.title, book.page_count)
    return book
