from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from magicstory_cli.models.book import BookSpec
from magicstory_cli.models.config import RenderConfig


def create_render_environment(templates_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )


def render_book_html(
    book: BookSpec,
    render_config: RenderConfig,
    project_dir: Path,
    templates_dir: Path,
) -> str:
    environment = create_render_environment(templates_dir)
    template = environment.get_template("book.html.jinja2")
    return template.render(
        book=book,
        render=render_config,
        project_dir=project_dir,
        page_size_css=_page_size_css(render_config.page_size),
    )


def _page_size_css(page_size: str) -> str:
    normalized = page_size.strip().lower()
    if normalized == "a4":
        return "A4"
    if "x" not in normalized:
        return page_size
    width, height = normalized.split("x", maxsplit=1)
    return f"{width} {height}"
