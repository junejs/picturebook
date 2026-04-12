from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from magicstory_cli.models.config import AppSettings


@dataclass(frozen=True)
class ProjectPaths:
    project_dir: Path
    book_yaml: Path
    artifacts_dir: Path
    images_dir: Path
    output_dir: Path
    render_dir: Path


def resolve_project_paths(project_dir: Path, settings: AppSettings) -> ProjectPaths:
    return ProjectPaths(
        project_dir=project_dir,
        book_yaml=project_dir / "book.yaml",
        artifacts_dir=project_dir / settings.runtime.artifacts_dirname,
        images_dir=project_dir / settings.runtime.images_dirname,
        output_dir=project_dir / settings.runtime.output_dirname,
        render_dir=project_dir / settings.runtime.render_dirname,
    )
