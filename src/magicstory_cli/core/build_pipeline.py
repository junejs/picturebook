from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from magicstory_cli.core.book_renderer import RenderResult, render_book
from magicstory_cli.core.illustrator import IllustrationResult, illustrate_book
from magicstory_cli.core.story_planner import plan_story
from magicstory_cli.models.book import BookSpec
from magicstory_cli.models.config import AppSettings


@dataclass(frozen=True)
class BuildResult:
    planned_book: BookSpec
    illustration_result: IllustrationResult
    render_result: RenderResult


def build_book(
    project_dir: Path,
    settings: AppSettings,
    prompts_dir: Path,
    templates_dir: Path,
    overwrite_images: bool = False,
) -> BuildResult:
    planned_book = plan_story(project_dir, settings, prompts_dir)
    illustration_result = illustrate_book(
        project_dir,
        settings,
        overwrite=overwrite_images,
    )
    render_result = render_book(project_dir, settings, templates_dir)
    return BuildResult(
        planned_book=planned_book,
        illustration_result=illustration_result,
        render_result=render_result,
    )
