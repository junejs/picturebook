from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from magicstory_cli.cli.app import resolve_settings
from magicstory_cli.core.paths import PipelineContext
from magicstory_cli.core.story_planner import plan_story

console = Console()


def register(app: typer.Typer) -> None:
    @app.command()
    def plan(
        project: Path = typer.Option(..., "--project", help="项目目录路径（必填）"),
        settings: Path = typer.Option(None, "--settings", help="配置文件路径"),
    ) -> None:
        """生成故事内容与每页插图提示词。"""
        app_settings, _ = resolve_settings(settings)
        ctx = PipelineContext.from_settings(project, app_settings)
        book_spec = plan_story(ctx)
        console.print(f"Planned {len(book_spec.pages)} pages for: {book_spec.title}")
