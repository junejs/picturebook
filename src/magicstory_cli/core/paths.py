from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from magicstory_cli.models.config import AppSettings

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]


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


def resolve_characters_dir(settings: AppSettings) -> Path:
    return settings.runtime.workspace_dir / settings.runtime.characters_dirname


def resolve_character_reference(characters_dir: Path, character_id: str) -> Path:
    return characters_dir / character_id / "reference.png"


@dataclass(frozen=True)
class PipelineContext:
    settings: AppSettings
    paths: ProjectPaths
    prompts_dir: Path
    templates_dir: Path
    characters_dir: Path

    @classmethod
    def from_settings(cls, project_dir: Path, settings: AppSettings) -> PipelineContext:
        paths = resolve_project_paths(project_dir, settings)
        characters_dir = resolve_characters_dir(settings)
        prompts_dir = settings.runtime.prompts_dir or _PACKAGE_ROOT / "prompts"
        templates_dir = settings.runtime.templates_dir or _PACKAGE_ROOT / "templates"
        return cls(
            settings=settings,
            paths=paths,
            prompts_dir=prompts_dir,
            templates_dir=templates_dir,
            characters_dir=characters_dir,
        )
