from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from magicstory_cli.config.loader import load_settings
from magicstory_cli.core.book_renderer import render_book
from magicstory_cli.core.build_pipeline import build_book
from magicstory_cli.core.character_manager import create_character, list_characters
from magicstory_cli.core.illustrator import illustrate_book
from magicstory_cli.core.paths import resolve_characters_dir
from magicstory_cli.core.project_scaffold import create_book_project
from magicstory_cli.core.story_planner import plan_story
from magicstory_cli.models.character import CharacterConfig
from magicstory_cli.models.config import AppSettings, BookConfig
from magicstory_cli.providers.factory import build_image_provider, build_vision_provider
from magicstory_cli.utils.files import slugify

app = typer.Typer(help="MagicStory CLI for storybook generation.")
character_app = typer.Typer(help="Manage reusable character references.")
app.add_typer(character_app, name="character")
console = Console()
PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"

logging.basicConfig(
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)


def resolve_settings(settings_path: Path) -> AppSettings:
    if not settings_path.exists():
        raise typer.BadParameter(
            f"settings file not found: {settings_path}. Copy config/settings.example.yaml first."
        )
    app_settings = load_settings(settings_path)
    logging.getLogger().setLevel(app_settings.app.log_level.upper())
    return app_settings


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


# ── Character commands ──────────────────────────────────────────────────────


@character_app.command("new")
def character_new(
    name: str = typer.Argument(..., help="Character name."),
    description: str | None = typer.Option(None, "--description", "-d", help="Character appearance description."),
    style: str | None = typer.Option(None, "--style", "-s", help="Art style override."),
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings", help="Path to settings YAML."),
) -> None:
    """Create a new character with a reference image."""
    app_settings = resolve_settings(settings)
    prompt_description = description or typer.prompt("Character description")

    char_id = slugify(name)
    char_config = CharacterConfig(
        id=char_id,
        name=name,
        description=prompt_description,
        style=style,
    )

    characters_dir = resolve_characters_dir(app_settings)
    with console.status("Generating character reference image and analyzing..."):
        result = create_character(characters_dir, char_config, app_settings, PROMPTS_DIR)

    console.print(f"[bold green]Character created:[/] {result.name} ({result.id})")
    console.print(f"  Reference: {characters_dir / result.id / 'reference.png'}")
    console.print(f"  Analyzed description: {result.analyzed_description[:200]}")


@character_app.command("list")
def character_list(
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings", help="Path to settings YAML."),
) -> None:
    """List all available characters."""
    app_settings = resolve_settings(settings)
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
        table.add_row(
            char.id,
            char.name,
            char.style or "(default)",
            (char.analyzed_description or char.description)[:60] + "...",
        )

    console.print(table)


# ── Project commands ────────────────────────────────────────────────────────


@app.command()
def doctor(
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings", help="Path to settings YAML."),
) -> None:
    """Validate environment and provider configuration."""
    app_settings = resolve_settings(settings)

    table = Table(title="MagicStory Doctor")
    table.add_column("Check")
    table.add_column("Result")

    table.add_row("Settings file", f"OK: {settings}")
    table.add_row("Workspace", str(app_settings.runtime.workspace_dir))
    table.add_row("Characters dir", str(resolve_characters_dir(app_settings)))
    table.add_row("Text provider", f"{app_settings.providers.text.provider} / {app_settings.providers.text.model}")
    active_image = app_settings.providers.image.get_active_config()
    table.add_row(
        "Image provider", f"{app_settings.providers.image.active} / {active_image.model}"
    )
    table.add_row(
        "Vision provider",
        (
            f"{app_settings.providers.vision.provider} / {app_settings.providers.vision.model}"
            if app_settings.providers.vision
            else "not configured"
        ),
    )
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

    try:
        build_vision_provider(app_settings)
        table.add_row("Vision provider wiring", "OK")
    except Exception as exc:
        table.add_row("Vision provider wiring", f"ERROR: {exc}")

    console.print(table)


@app.command("new")
def new_project(
    title: str | None = typer.Argument(None, help="Book title."),
    idea: str | None = typer.Option(None, "--idea", help="Core story idea."),
    style: str | None = typer.Option(None, "--style", help="Illustration style."),
    page_count: int | None = typer.Option(None, "--pages", min=4, max=16, help="Book page count."),
    language: str | None = typer.Option(None, "--language", help="Primary book language."),
    target_age: str | None = typer.Option(None, "--age", help="Target age range."),
    book_id: str | None = typer.Option(None, "--id", help="Optional custom project id."),
    characters: list[str] | None = typer.Option(None, "--characters", "-c", help="Character IDs to use."),
    notes: str | None = typer.Option(None, "--notes", help="Optional author notes."),
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings", help="Path to settings YAML."),
) -> None:
    """Create a new book project scaffold."""
    app_settings = resolve_settings(settings)
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
            title,
            idea,
            style,
            page_count,
            language,
            target_age,
            book_id,
            characters,
            notes,
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


@app.command()
def plan(
    project: Path = typer.Option(..., "--project", help="Path to the book project directory."),
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings", help="Path to settings YAML."),
) -> None:
    """Generate structured story pages and illustration prompts."""
    app_settings = resolve_settings(settings)
    book_spec = plan_story(project, app_settings, PROMPTS_DIR)
    paths = resolve_characters_dir(app_settings)
    console.print(f"Planned {len(book_spec.pages)} pages for: {book_spec.title}")


@app.command()
def illustrate(
    project: Path = typer.Option(..., "--project", help="Path to the book project directory."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Regenerate existing page images."),
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings", help="Path to settings YAML."),
) -> None:
    """Generate page illustrations from the planned prompts."""
    app_settings = resolve_settings(settings)
    result = illustrate_book(project, app_settings, PROMPTS_DIR, overwrite=overwrite)
    console.print(
        f"Illustration complete for: {result.book_spec.title} "
        f"(generated={result.generated_pages}, skipped={result.skipped_pages})"
    )


@app.command()
def render(
    project: Path = typer.Option(..., "--project", help="Path to the book project directory."),
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings", help="Path to settings YAML."),
) -> None:
    """Render a formal picture-book PDF from generated pages and images."""
    app_settings = resolve_settings(settings)
    result = render_book(project, app_settings, TEMPLATES_DIR)
    console.print(f"Rendered HTML: {result.html_path}")
    console.print(f"Rendered PDF: {result.pdf_path}")


@app.command("e2e-test")
def e2e_test(
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings", help="Path to settings YAML."),
) -> None:
    """运行端到端测试：用真实 AI API 生成一本 4 页迷你绘本。"""
    app_settings = resolve_settings(settings)

    test_id = "e2e-test-little-cat"
    test_title = "小猫的冒险"
    workspace = Path(app_settings.runtime.workspace_dir) / "_e2e_test"
    project_dir = workspace / test_id

    if project_dir.exists():
        import shutil
        shutil.rmtree(project_dir)

    # Step 1: Create a test character
    console.print("[bold]E2E 测试：创建角色[/] (character)")
    characters_dir = resolve_characters_dir(app_settings)
    test_char_id = "e2e-test-orange-cat"
    test_char_dir = characters_dir / test_char_id
    if test_char_dir.exists():
        import shutil
        shutil.rmtree(test_char_dir)

    char_config = CharacterConfig(
        id=test_char_id,
        name="小橘",
        description="一只圆滚滚的橘色小猫，大眼睛，耳朵上有一小撮白毛，尾巴末端是白色的",
        style="卡通风格",
    )
    with console.status("Generating character reference image and analyzing..."):
        char_result = create_character(characters_dir, char_config, app_settings, PROMPTS_DIR)
    console.print(f"  Character created: {char_result.name} ({char_result.id})")

    # Step 2: Create book project with character reference
    book = BookConfig(
        id=test_id,
        title=test_title,
        idea="一只橘猫偷偷溜出家门，在花园里遇到了蝴蝶和青蛙，最后安全回家",
        language="zh-CN",
        target_age="7-8",
        style="卡通风格",
        page_count=4,
        characters=[test_char_id],
    )

    console.print(f"[bold]E2E 测试：创建项目[/] {test_title}")
    project_dir = create_book_project(workspace, book, app_settings)

    # Step 3: Run full build pipeline
    console.print("[bold]E2E 测试：运行 build 流程[/] (plan → illustrate → render)")
    result = build_book(
        project_dir,
        app_settings,
        prompts_dir=PROMPTS_DIR,
        templates_dir=TEMPLATES_DIR,
        overwrite_images=False,
    )

    console.print(
        f"[bold green]E2E 测试通过[/] "
        f"(pages={len(result.planned_book.pages)}, "
        f"images={result.illustration_result.generated_pages}, "
        f"character={test_char_id})"
    )
    console.print(f"  HTML: {result.render_result.html_path}")
    console.print(f"  PDF:  {result.render_result.pdf_path}")
    console.print(f"  清理: rm -rf {project_dir} {test_char_dir}")


@app.command()
def build(
    project: Path = typer.Option(..., "--project", help="Path to the book project directory."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Regenerate existing page images."),
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings", help="Path to settings YAML."),
) -> None:
    """Run the full storybook pipeline: plan, illustrate, then render."""
    app_settings = resolve_settings(settings)
    result = build_book(
        project,
        app_settings,
        prompts_dir=PROMPTS_DIR,
        templates_dir=TEMPLATES_DIR,
        overwrite_images=overwrite,
    )
    console.print(
        f"Build complete for: {result.planned_book.title} "
        f"(pages={len(result.planned_book.pages)}, "
        f"generated_images={result.illustration_result.generated_pages}, "
        f"skipped_images={result.illustration_result.skipped_pages})"
    )
    console.print(f"HTML: {result.render_result.html_path}")
    console.print(f"PDF: {result.render_result.pdf_path}")


if __name__ == "__main__":
    app()
