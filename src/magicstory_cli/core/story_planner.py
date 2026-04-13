from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from magicstory_cli.config.loader import load_book_config
from magicstory_cli.core.character_manager import load_character
from magicstory_cli.core.paths import resolve_characters_dir, resolve_project_paths
from magicstory_cli.models.book import BookSpec, PageSpec
from magicstory_cli.models.config import AppSettings
from magicstory_cli.providers.factory import build_text_provider
from magicstory_cli.utils.files import write_json
from magicstory_cli.utils.json_tools import parse_json_object
from magicstory_cli.utils.prompts import create_prompt_environment, render_prompt

logger = logging.getLogger(__name__)


class PlannedPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1)
    story_text: str = Field(min_length=1)
    illustration_prompt: str = Field(min_length=1)


class PlannedBookPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pages: list[PlannedPage]


def plan_story(project_dir: Path, settings: AppSettings, prompts_dir: Path) -> BookSpec:
    paths = resolve_project_paths(project_dir, settings)
    book = load_book_config(paths.book_yaml)
    logger.info("Planning story: %s (%d pages)", book.title, book.page_count)

    # Load character descriptions if any
    characters_text = ""
    if book.characters:
        characters_dir = resolve_characters_dir(settings)
        char_descriptions = []
        for char_id in book.characters:
            try:
                char = load_character(characters_dir, char_id)
                char_descriptions.append(f"- **{char.name}**: {char.analyzed_description or char.description}")
            except FileNotFoundError:
                logger.warning("Character %s not found in %s, skipping", char_id, characters_dir)
        if char_descriptions:
            characters_text = "\n".join(char_descriptions)

    prompt_env = create_prompt_environment(prompts_dir)
    user_prompt = render_prompt(
        prompt_env,
        "page_content.jinja2",
        title=book.title,
        idea=book.idea,
        language=book.language,
        target_age=book.target_age,
        style=book.style,
        page_count=book.page_count,
        characters=characters_text or None,
    )
    system_prompt = render_prompt(prompt_env, "story_plan.jinja2")

    raw_response = build_text_provider(settings).generate_structured_text(
        prompt=user_prompt,
        system_prompt=system_prompt,
    )
    logger.debug("Raw LLM response length: %d chars", len(raw_response))

    payload = _validate_payload(parse_json_object(raw_response), book.page_count)
    book_spec = BookSpec(
        title=book.title,
        language=book.language,
        target_age=book.target_age,
        style=book.style,
        page_count=book.page_count,
        pages=[
            PageSpec(
                page_number=page.page_number,
                story_text=page.story_text,
                illustration_prompt=page.illustration_prompt,
            )
            for page in payload.pages
        ],
    )

    write_json(paths.artifacts_dir / "plan.raw.json", {"response": raw_response})
    write_json(paths.artifacts_dir / "pages.json", book_spec.model_dump(mode="json"))
    write_json(
        paths.artifacts_dir / "plan.meta.json",
        {
            "book_id": book.id,
            "title": book.title,
            "page_count": book.page_count,
            "planned_pages": len(book_spec.pages),
        },
    )
    logger.info("Plan complete: %d pages planned for %s", len(book_spec.pages), book.title)
    return book_spec


def _validate_payload(payload: dict, expected_page_count: int) -> PlannedBookPayload:
    try:
        model = PlannedBookPayload.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError(f"invalid planning payload: {exc}") from exc

    page_numbers = [page.page_number for page in model.pages]
    if len(model.pages) != expected_page_count:
        raise RuntimeError(
            f"expected {expected_page_count} pages from planner, got {len(model.pages)}"
        )
    if page_numbers != list(range(1, expected_page_count + 1)):
        raise RuntimeError(f"page numbers must be sequential from 1 to {expected_page_count}")
    return model
