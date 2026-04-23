from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from magicstory_cli.cli.app import resolve_settings
from magicstory_cli.core.paths import resolve_characters_dir
from magicstory_cli.providers.factory import build_image_provider, build_text_provider

console = Console()


def register(app: typer.Typer) -> None:

    @app.command()
    def doctor(
        settings: Path = typer.Option(None, "--settings", help="配置文件路径"),
    ) -> None:
        """检查环境与 provider 配置是否正确。"""
        app_settings, resolved_settings = resolve_settings(settings)

        table = Table(title="MagicStory Doctor")
        table.add_column("Check")
        table.add_column("Result")

        table.add_row("Settings file", f"OK: {resolved_settings}")
        table.add_row("Workspace", str(app_settings.runtime.workspace_dir))
        table.add_row("Characters dir", str(resolve_characters_dir(app_settings)))
        text_p = app_settings.providers.text
        table.add_row("Text provider", f"{text_p.provider} / {text_p.model}")
        active_image = app_settings.providers.image.get_active_config()
        img_p = app_settings.providers.image
        table.add_row("Image provider", f"{img_p.active} / {active_image.model}")
        table.add_row("Page range", "4-16 pages")
        table.add_row("PDF renderer", "Playwright (Chromium)")
        table.add_row("Reference images", str(app_settings.features.enable_reference_image).lower())
        table.add_row("Max parallel image jobs", str(app_settings.runtime.max_parallel_image_jobs))
        table.add_row("Log level", app_settings.app.log_level)

        try:
            build_text_provider(app_settings)
            table.add_row("Text provider wiring", "OK")
        except Exception as exc:
            table.add_row("Text provider wiring", f"ERROR: {exc}")

        try:
            build_image_provider(app_settings)
            table.add_row("Image provider wiring", "OK")
        except Exception as exc:
            table.add_row("Image provider wiring", f"ERROR: {exc}")

        console.print(table)

    @app.command("config")
    def show_config(
        settings: Path = typer.Option(None, "--settings", help="配置文件路径"),
    ) -> None:
        """显示当前生效的配置文件内容和来源。"""
        import yaml as _yaml

        app_settings, resolved_settings = resolve_settings(settings)
        with open(resolved_settings, encoding="utf-8") as f:
            raw = _yaml.safe_load(f) or {}

        console.print(f"[bold]配置文件:[/] {resolved_settings}")
        console.print()
        console.print(_yaml.dump(raw, allow_unicode=True, default_flow_style=False))
