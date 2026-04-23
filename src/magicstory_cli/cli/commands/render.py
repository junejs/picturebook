from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from magicstory_cli.cli.app import resolve_settings
from magicstory_cli.core.book_renderer import render_book
from magicstory_cli.core.paths import PipelineContext

console = Console()


def register(app: typer.Typer) -> None:
    @app.command()
    def render(
        project: Path = typer.Option(..., "--project", help="项目目录路径（必填）"),
        settings: Path = typer.Option(None, "--settings", help="配置文件路径"),
    ) -> None:
        """渲染 HTML 预览与 PDF 文件。"""
        app_settings, _ = resolve_settings(settings)
        ctx = PipelineContext.from_settings(project, app_settings)
        result = render_book(ctx)
        console.print(f"Rendered HTML: {result.html_path}")
        console.print(f"Rendered PDF: {result.pdf_path}")
