from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from magicstory_cli.config.loader import load_book_config
from magicstory_cli.core.character_context import load_character_context
from magicstory_cli.core.paths import PipelineContext
from magicstory_cli.models.book import BookSpec, PageSpec
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


def plan_story(ctx: PipelineContext) -> BookSpec:
    paths = ctx.paths
    book = load_book_config(paths.book_yaml)
    logger.info("Planning story: %s (%d pages)", book.title, book.page_count)

    # Load character descriptions if any
    characters_text = ""
    if book.characters:
        char_ctx = load_character_context(ctx, book.characters)
        if char_ctx.description_text:
            parts = [d.strip() for d in char_ctx.description_text.split(";") if d.strip()]
            characters_text = "\n".join(
                f"- **{p.split(':', 1)[0].strip()}**: {p.split(':', 1)[1].strip()}" for p in parts
            )

    prompt_env = create_prompt_environment(ctx.prompts_dir)
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

    provider = build_text_provider(ctx.settings)
    max_retries = 3
    last_error: Exception | None = None
    payload: PlannedBookPayload | None = None

    for attempt in range(1, max_retries + 1):
        raw_response = provider.generate_structured_text(
            prompt=user_prompt,
            system_prompt=system_prompt,
        )
        logger.debug(
            "Attempt %d/%d: raw LLM response (%d chars)",
            attempt, max_retries, len(raw_response),
        )
        try:
            payload = _validate_payload(parse_json_object(raw_response), book.page_count)
            break
        except (ValueError, RuntimeError) as exc:
            last_error = exc
            logger.warning("Attempt %d/%d failed: %s", attempt, max_retries, exc)
            if attempt == max_retries:
                raise RuntimeError(
                    f"Failed to get valid JSON after {max_retries} attempts: {last_error}"
                ) from last_error

    assert payload is not None
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
