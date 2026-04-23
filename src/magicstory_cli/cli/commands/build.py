from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from magicstory_cli.cli.app import resolve_settings
from magicstory_cli.core.build_pipeline import build_book

console = Console()


def register(app: typer.Typer) -> None:
    @app.command()
    def build(
        project: Path = typer.Option(..., "--project", help="项目目录路径（必填）"),
        overwrite: bool = typer.Option(False, "--overwrite", help="强制重新生成已有插图"),
        settings: Path = typer.Option(None, "--settings", help="配置文件路径"),
    ) -> None:
        """一键运行完整流程: plan -> illustrate -> render。"""
        app_settings, _ = resolve_settings(settings)
        result = build_book(project, app_settings, overwrite_images=overwrite)
        console.print(
            f"Build complete for: {result.planned_book.title} "
            f"(pages={len(result.planned_book.pages)}, "
            f"generated_images={result.illustration_result.generated_pages}, "
            f"skipped_images={result.illustration_result.skipped_pages})"
        )
        console.print(f"HTML: {result.render_result.html_path}")
        console.print(f"PDF: {result.render_result.pdf_path}")
