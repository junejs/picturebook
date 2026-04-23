from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from magicstory_cli.core.paths import PipelineContext
from magicstory_cli.models.book import BookSpec
from magicstory_cli.rendering.html_renderer import render_book_html
from magicstory_cli.rendering.pdf import write_pdf_from_html
from magicstory_cli.utils.files import read_json, write_json

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RenderResult:
    html_path: Path
    pdf_path: Path
    book_spec: BookSpec


def render_book(
    ctx: PipelineContext,
) -> RenderResult:
    paths = ctx.paths
    pages_path = paths.artifacts_dir / "pages.json"
    if not pages_path.exists():
        raise RuntimeError("missing artifacts/pages.json. Run `story plan` first.")

    try:
        book_spec = BookSpec.model_validate(read_json(pages_path))
    except ValidationError as exc:
        raise RuntimeError(f"invalid pages artifact: {exc}") from exc

    missing_images = [page.page_number for page in book_spec.pages if not page.image_path]
    if missing_images:
        missing_display = ", ".join(str(value) for value in missing_images)
        raise RuntimeError(
            f"missing image_path for pages: {missing_display}. Run `story illustrate` first."
        )

    html = render_book_html(
        book=book_spec,
        render_config=ctx.settings.render,
        project_dir=ctx.paths.project_dir,
        templates_dir=ctx.templates_dir,
    )
    html_path = paths.render_dir / "book.html"
    pdf_path = paths.output_dir / "book.pdf"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    logger.info("HTML rendered: %s (%d chars)", html_path, len(html))

    write_pdf_from_html(html, pdf_path, base_url=ctx.paths.project_dir)
    logger.info("PDF rendered: %s", pdf_path)

    write_json(
        paths.artifacts_dir / "render.meta.json",
        {
            "title": book_spec.title,
            "page_count": book_spec.page_count,
            "html_path": str(html_path.relative_to(ctx.paths.project_dir)).replace("\\", "/"),
            "pdf_path": str(pdf_path.relative_to(ctx.paths.project_dir)).replace("\\", "/"),
        },
    )
    return RenderResult(html_path=html_path, pdf_path=pdf_path, book_spec=book_spec)
