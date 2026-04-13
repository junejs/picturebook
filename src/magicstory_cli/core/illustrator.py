from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from magicstory_cli.config.loader import load_book_config
from magicstory_cli.core.character_manager import load_character
from magicstory_cli.core.paths import (
    ProjectPaths,
    resolve_characters_dir,
    resolve_character_reference,
    resolve_project_paths,
)
from magicstory_cli.models.book import BookSpec
from magicstory_cli.models.config import AppSettings
from magicstory_cli.providers.factory import build_image_provider
from magicstory_cli.utils.files import read_json, write_json
from magicstory_cli.utils.prompts import create_prompt_environment, render_prompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IllustrationResult:
    generated_pages: int
    skipped_pages: int
    book_spec: BookSpec


def _build_character_description(characters_dir: Path, character_ids: list[str]) -> str:
    """Load and concatenate character analyzed_descriptions for prompt injection."""
    descriptions = []
    for char_id in character_ids:
        try:
            char = load_character(characters_dir, char_id)
            desc = char.analyzed_description or char.description
            descriptions.append(f"{char.name}: {desc}")
        except FileNotFoundError:
            logger.warning("Character %s not found, skipping for description", char_id)
    return "; ".join(descriptions)


def _collect_reference_images(
    characters_dir: Path, character_ids: list[str]
) -> list[Path]:
    """Collect reference image paths for all characters."""
    refs: list[Path] = []
    for char_id in character_ids:
        ref_path = resolve_character_reference(characters_dir, char_id)
        if ref_path.exists():
            refs.append(ref_path)
        else:
            logger.warning("Reference image not found for %s: %s", char_id, ref_path)
    return refs


def illustrate_book(
    project_dir: Path,
    settings: AppSettings,
    prompts_dir: Path,
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

    # Load book config for character info
    book = load_book_config(paths.book_yaml)
    characters_dir = resolve_characters_dir(settings)
    character_ids = book.characters

    # Build character context for prompts
    character_description = ""
    reference_images: list[Path] = []
    if character_ids:
        character_description = _build_character_description(characters_dir, character_ids)
        reference_images = _collect_reference_images(characters_dir, character_ids)

    # Load illustration prompt template
    prompt_env = create_prompt_environment(prompts_dir)

    provider = build_image_provider(settings)
    max_workers = settings.runtime.max_parallel_image_jobs
    logger.info(
        "Illustrating book: %s (%d pages, overwrite=%s, max_parallel=%d, characters=%d)",
        book_spec.title,
        len(book_spec.pages),
        overwrite,
        max_workers,
        len(character_ids),
    )

    generated_pages = 0
    skipped_pages = 0
    pending_jobs: list[tuple[int, Path, str, list[Path]]] = []

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

        # Build the final illustration prompt with character context
        illustration_prompt = page.illustration_prompt
        if character_description:
            try:
                illustration_prompt = render_prompt(
                    prompt_env,
                    "minimax/illustration_generation.jinja2",
                    style=book_spec.style,
                    illustrationDescription=page.illustration_prompt,
                    characterDescription=character_description,
                )
            except Exception:
                logger.debug("Failed to render illustration template, using raw prompt")
                illustration_prompt = page.illustration_prompt

        pending_jobs.append((
            page.page_number,
            image_output_path,
            illustration_prompt,
            reference_images,
        ))

    def _generate_image(job: tuple[int, Path, str, list[Path]]) -> tuple[int, str]:
        page_number, image_output_path, prompt, refs = job
        final_path = provider.generate_image(
            prompt, str(image_output_path), reference_images=refs or None
        )
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
            "characters_used": character_ids,
        },
    )
    logger.info("Illustration complete: %d generated, %d skipped", generated_pages, skipped_pages)
    return IllustrationResult(
        generated_pages=generated_pages,
        skipped_pages=skipped_pages,
        book_spec=book_spec,
    )
