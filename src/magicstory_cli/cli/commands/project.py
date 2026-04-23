from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from magicstory_cli.cli.app import resolve_settings
from magicstory_cli.core.project_scaffold import create_book_project
from magicstory_cli.models.config import BookConfig
from magicstory_cli.utils.files import slugify

console = Console()


def _prompt_book_config(
    title: str | None = None,
    idea: str | None = None,
    style: str | None = None,
    page_count: int | None = None,
    language: str | None = None,
    target_age: str | None = None,
    book_id: str | None = None,
    characters: list[str] | None = None,
    notes: str | None = None,
    prompt_optional_fields: bool = False,
    default_style: str = "Cartoon",
) -> BookConfig:
    prompt_title = title or typer.prompt("Book title")
    prompt_idea = idea or typer.prompt("Story idea")
    prompt_style = style or typer.prompt("Illustration style", default=default_style)
    prompt_page_count = page_count if page_count is not None else typer.prompt("Page count", default=12, type=int)
    prompt_language = language or typer.prompt("Language", default="zh-CN")
    prompt_target_age = target_age or typer.prompt("Target age", default="4-6")
    prompt_book_id = book_id or (
        typer.prompt("Project id", default=slugify(prompt_title)) if prompt_optional_fields else slugify(prompt_title)
    )
    prompt_notes = notes if notes is not None else (
        typer.prompt("Notes", default="") if prompt_optional_fields else None
    )
    prompt_characters = characters if characters is not None else (
        [c.strip() for c in typer.prompt("Characters (comma-separated IDs)", default="").split(",") if c.strip()]
        if prompt_optional_fields else []
    )

    return BookConfig(
        id=prompt_book_id,
        title=prompt_title,
        idea=prompt_idea,
        language=prompt_language,
        target_age=prompt_target_age,
        style=prompt_style,
        page_count=prompt_page_count,
        characters=prompt_characters,
        notes=prompt_notes or None,
    )


def register(app: typer.Typer) -> None:
    @app.command("new")
    def new_project(
        title: str | None = typer.Argument(None, help="书名"),
        idea: str | None = typer.Option(None, "--idea", help="故事核心想法（必填）"),
        style: str | None = typer.Option(None, "--style", help="插画风格，如 '水彩画'、'Cartoon'"),
        page_count: int | None = typer.Option(None, "--pages", min=4, max=16, help="页数，范围 4-16"),
        language: str | None = typer.Option(None, "--language", help="语言，默认 zh-CN"),
        target_age: str | None = typer.Option(None, "--age", help="目标年龄段，默认 4-6"),
        book_id: str | None = typer.Option(None, "--id", help="自定义项目 ID，默认由书名自动生成"),
        characters: list[str] | None = typer.Option(
            None, "--characters", "-c", help="关联角色 ID",
        ),
        notes: str | None = typer.Option(None, "--notes", help="补充说明"),
        settings: Path = typer.Option(None, "--settings", help="配置文件路径"),
    ) -> None:
        """创建绘本项目。"""
        app_settings, _ = resolve_settings(settings)
        needs_prompt = (
            title is None
            or idea is None
            or style is None
            or page_count is None
            or language is None
            or target_age is None
        )
        if needs_prompt:
            book = _prompt_book_config(
                title, idea, style, page_count, language, target_age,
                book_id, characters, notes,
                prompt_optional_fields=True,
                default_style=app_settings.app.default_style,
            )
        else:
            normalized_id = book_id or slugify(title)
            book = BookConfig(
                id=normalized_id,
                title=title,
                idea=idea,
                language=language,
                target_age=target_age,
                style=style or app_settings.app.default_style,
                page_count=page_count,
                characters=characters or [],
                notes=notes,
            )

        project_dir = create_book_project(app_settings.runtime.workspace_dir, book, app_settings)
        console.print(f"Created project: {project_dir}")
        console.print(f"Next step: story plan --project {project_dir}")
