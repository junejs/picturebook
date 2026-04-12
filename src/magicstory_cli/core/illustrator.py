from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    max_workers = settings.runtime.max_parallel_image_jobs
    logger.info(
        "Illustrating book: %s (%d pages, overwrite=%s, max_parallel_image_jobs=%d)",
        book_spec.title,
        len(book_spec.pages),
        overwrite,
        max_workers,
    )

    generated_pages = 0
    skipped_pages = 0
    pending_jobs: list[tuple[int, Path, str]] = []

    for page in book_spec.pages:
        image_relative_path = (
            Path(settings.runtime.images_dirname) / f"page-{page.page_number:02d}.png"
        )
        image_output_path = project_dir / image_relative_path

        if image_output_path.exists() and not overwrite:
            logger.debug(
                "Skipping page %d (already exists): %s",
                page.page_number,
                image_output_path,
            )
            page.image_path = image_relative_path.as_posix()
            skipped_pages += 1
            continue

        pending_jobs.append((page.page_number, image_output_path, page.illustration_prompt))

    def _generate_image(job: tuple[int, Path, str]) -> tuple[int, str]:
        page_number, image_output_path, illustration_prompt = job
        final_path = provider.generate_image(illustration_prompt, str(image_output_path))
        return page_number, str(Path(final_path).relative_to(project_dir)).replace("\\", "/")

    if pending_jobs:
        if max_workers == 1 or len(pending_jobs) == 1:
            results = [_generate_image(job) for job in pending_jobs]
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {executor.submit(_generate_image, job): job for job in pending_jobs}
                results = []
                for future in as_completed(future_map):
                    results.append(future.result())

        image_path_by_page = {page_number: image_path for page_number, image_path in results}
        for page in book_spec.pages:
            if page.page_number in image_path_by_page:
                page.image_path = image_path_by_page[page.page_number]
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
            "max_parallel_image_jobs": max_workers,
        },
    )
    logger.info("Illustration complete: %d generated, %d skipped", generated_pages, skipped_pages)
    return IllustrationResult(
        generated_pages=generated_pages,
        skipped_pages=skipped_pages,
        book_spec=book_spec,
    )
