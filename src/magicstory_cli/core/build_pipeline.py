from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from magicstory_cli.core.book_renderer import RenderResult, render_book
from magicstory_cli.core.illustrator import IllustrationResult, illustrate_book
from magicstory_cli.core.paths import PipelineContext
from magicstory_cli.core.story_planner import plan_story
from magicstory_cli.models.book import BookSpec
from magicstory_cli.models.config import AppSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BuildResult:
    planned_book: BookSpec
    illustration_result: IllustrationResult
    render_result: RenderResult


def build_book(
    project_dir: Path,
    settings: AppSettings,
    overwrite_images: bool = False,
) -> BuildResult:
    logger.info("Starting full build pipeline for: %s", project_dir)

    ctx = PipelineContext.from_settings(project_dir, settings)

    planned_book = plan_story(ctx)
    illustration_result = illustrate_book(ctx, overwrite=overwrite_images)
    render_result = render_book(ctx)

    logger.info("Build pipeline complete for: %s", planned_book.title)
    return BuildResult(
        planned_book=planned_book,
        illustration_result=illustration_result,
        render_result=render_result,
    )
