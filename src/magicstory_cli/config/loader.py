from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from magicstory_cli.models.config import AppSettings, BookConfig


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping at the top level")
    return data


def load_settings(path: Path) -> AppSettings:
    return AppSettings.model_validate(load_yaml(path))


def load_book_config(path: Path) -> BookConfig:
    data = load_yaml(path)
    book_data = data.get("book", data)
    return BookConfig.model_validate(book_data)
