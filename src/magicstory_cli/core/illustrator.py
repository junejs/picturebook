from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from magicstory_cli.core.paths import resolve_project_paths
from magicstory_cli.models.book import BookSpec
from magicstory_cli.models.config import AppSettings
from magicstory_cli.providers.factory import build_image_provider
from magicstory_cli.utils.files import read_json, write_json

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IllustrationResult:
    generated_pages: int
    skipped_pages: int
    book_spec: BookSpec


def illustrate_book(
    project_dir: Path,
    settings: AppSettings,
    overwrite: bool = False,
) -> IllustrationResult:
    paths = resolve_project_paths(project_dir, settings)
    pages_path = paths.artifacts_dir / "pages.json"
    if not pages_path.exists():
        raise RuntimeError("missing artifacts/pages.json. Run `story plan` first.")

    try:
        book_spec = BookSpec.model_validate(read_json(pages_path))
    except ValidationError as exc:
        raise RuntimeError(f"invalid pages artifact: {exc}") from exc

    provider = build_image_provider(settings)
    logger.info("Illustrating book: %s (%d pages, overwrite=%s)", book_spec.title, len(book_spec.pages), overwrite)

    generated_pages = 0
    skipped_pages = 0

    for page in book_spec.pages:
        image_relative_path = Path(settings.runtime.images_dirname) / f"page-{page.page_number:02d}.png"
        image_output_path = project_dir / image_relative_path

        if image_output_path.exists() and not overwrite:
            logger.debug("Skipping page %d (already exists): %s", page.page_number, image_output_path)
            page.image_path = image_relative_path.as_posix()
            skipped_pages += 1
            continue

        final_path = provider.generate_image(page.illustration_prompt, str(image_output_path))
        page.image_path = str(Path(final_path).relative_to(project_dir)).replace("\\", "/")
        generated_pages += 1

    write_json(pages_path, book_spec.model_dump(mode="json"))
    write_json(
        paths.artifacts_dir / "illustration.meta.json",
        {
            "title": book_spec.title,
            "page_count": book_spec.page_count,
            "generated_pages": generated_pages,
            "skipped_pages": skipped_pages,
            "overwrite": overwrite,
        },
    )
    logger.info("Illustration complete: %d generated, %d skipped", generated_pages, skipped_pages)
    return IllustrationResult(
        generated_pages=generated_pages,
        skipped_pages=skipped_pages,
        book_spec=book_spec,
    )
