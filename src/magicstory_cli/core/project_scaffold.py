from __future__ import annotations

import logging
from pathlib import Path

from magicstory_cli.models.config import AppSettings, BookConfig
from magicstory_cli.utils.files import ensure_directory, write_json, write_yaml

logger = logging.getLogger(__name__)


def create_book_project(root: Path, book: BookConfig, settings: AppSettings) -> Path:
    project_dir = ensure_directory(root / book.id)
    logger.info("Creating project: %s", project_dir)

    ensure_directory(project_dir / settings.runtime.artifacts_dirname)
    ensure_directory(project_dir / settings.runtime.images_dirname)
    ensure_directory(project_dir / settings.runtime.output_dirname)
    ensure_directory(project_dir / settings.runtime.render_dirname)

    write_yaml(project_dir / "book.yaml", {"book": book.model_dump(mode="json", exclude_none=True)})
    write_json(
        project_dir / settings.runtime.artifacts_dirname / "manifest.json",
        {
            "book_id": book.id,
            "title": book.title,
            "status": "initialized",
            "next_steps": ["story plan", "story illustrate", "story render"],
        },
    )
    logger.info("Project created: %s", project_dir)
    return project_dir
