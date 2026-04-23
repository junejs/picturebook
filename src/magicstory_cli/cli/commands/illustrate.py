from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from magicstory_cli.cli.app import resolve_settings
from magicstory_cli.core.illustrator import illustrate_book
from magicstory_cli.core.paths import PipelineContext

console = Console()


def register(app: typer.Typer) -> None:
    @app.command()
    def illustrate(
        project: Path = typer.Option(..., "--project", help="项目目录路径（必填）"),
        overwrite: bool = typer.Option(False, "--overwrite", help="强制重新生成已有插图"),
        settings: Path = typer.Option(None, "--settings", help="配置文件路径"),
    ) -> None:
        """为每页生成插图。"""
        app_settings, _ = resolve_settings(settings)
        ctx = PipelineContext.from_settings(project, app_settings)
        result = illustrate_book(ctx, overwrite=overwrite)
        console.print(
            f"Illustration complete for: {result.book_spec.title} "
            f"(generated={result.generated_pages}, skipped={result.skipped_pages})"
        )
