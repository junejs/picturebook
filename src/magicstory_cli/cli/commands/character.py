from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from magicstory_cli.cli.app import resolve_settings
from magicstory_cli.core.character_manager import create_character, list_characters
from magicstory_cli.core.paths import PipelineContext, resolve_characters_dir
from magicstory_cli.models.character import CharacterConfig
from magicstory_cli.utils.files import slugify

console = Console()

character_app = typer.Typer(help="管理可复用角色。")


def register(app: typer.Typer) -> None:
    app.add_typer(character_app, name="character")

    @character_app.command("new")
    def character_new(
        name: str = typer.Argument(..., help="角色名称"),
        description: str = typer.Option(..., "--description", "-d", help="角色外观描述（必填）"),
        style: str | None = typer.Option(None, "--style", "-s", help="画风覆盖"),
        settings: Path = typer.Option(None, "--settings", help="配置文件路径"),
    ) -> None:
        """创建角色并生成参考图。"""
        app_settings, _ = resolve_settings(settings)
        char_id = slugify(name)
        char_config = CharacterConfig(id=char_id, name=name, description=description, style=style)
        characters_dir = resolve_characters_dir(app_settings)
        ctx = PipelineContext.from_settings(characters_dir.parent, app_settings)
        with console.status("Generating character reference image..."):
            result = create_character(characters_dir, char_config, app_settings, ctx.prompts_dir)
        console.print(f"[bold green]Character created:[/] {result.name} ({result.id})")
        console.print(f"  Reference: {characters_dir / result.id / 'reference.png'}")
        console.print(f"  Description: {result.description[:200]}")

    @character_app.command("list")
    def character_list(
        settings: Path = typer.Option(None, "--settings", help="配置文件路径"),
    ) -> None:
        """列出所有已创建的角色。"""
        app_settings, _ = resolve_settings(settings)
        characters_dir = resolve_characters_dir(app_settings)
        characters = list_characters(characters_dir)
        if not characters:
            console.print("No characters found.")
            return
        table = Table(title="Characters")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("Style")
        table.add_column("Description")
        for char in characters:
            desc = char.description[:60] + "..." if len(char.description) > 60 else char.description
            table.add_row(char.id, char.name, char.style or "(default)", desc)
        console.print(table)
