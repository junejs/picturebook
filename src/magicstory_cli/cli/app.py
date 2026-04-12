from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from magicstory_cli.config.loader import load_settings
from magicstory_cli.core.illustrator import illustrate_book
from magicstory_cli.core.build_pipeline import build_book
from magicstory_cli.core.book_renderer import render_book
from magicstory_cli.core.paths import resolve_project_paths
from magicstory_cli.core.project_scaffold import create_book_project
from magicstory_cli.core.story_planner import plan_story
from magicstory_cli.models.config import AppSettings, BookConfig
from magicstory_cli.providers.factory import build_image_provider, build_text_provider
from magicstory_cli.utils.files import slugify

app = typer.Typer(help="MagicStory CLI for storybook generation.")
console = Console()
PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"


def resolve_settings(settings_path: Path) -> AppSettings:
    if not settings_path.exists():
        raise typer.BadParameter(
            f"settings file not found: {settings_path}. Copy config/settings.example.yaml first."
        )
    return load_settings(settings_path)


@app.command()
def doctor(
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings", help="Path to settings YAML.")
) -> None:
    """Validate environment and provider configuration."""
    app_settings = resolve_settings(settings)

    table = Table(title="MagicStory Doctor")
    table.add_column("Check")
    table.add_column("Result")

    table.add_row("Settings file", f"OK: {settings}")
    table.add_row("Workspace", str(app_settings.runtime.workspace_dir))
    table.add_row("Text provider", f"{app_settings.providers.text.provider} / {app_settings.providers.text.model}")
    table.add_row(
        "Image provider", f"{app_settings.providers.image.provider} / {app_settings.providers.image.model}"
    )
    table.add_row("Page range", "4-16 pages")
    table.add_row("PDF renderer", "WeasyPrint")

    try:
        build_text_provider(app_settings)
        table.add_row("Text provider wiring", "OK")
    except Exception as exc:  # pragma: no cover - CLI surface
        table.add_row("Text provider wiring", f"ERROR: {exc}")

    try:
        build_image_provider(app_settings)
        table.add_row("Image provider wiring", "OK")
    except Exception as exc:  # pragma: no cover - CLI surface
        table.add_row("Image provider wiring", f"ERROR: {exc}")

    console.print(table)


@app.command("new")
def new_project(
    title: str = typer.Argument(..., help="Book title."),
    idea: str = typer.Option(..., "--idea", prompt=True, help="Core story idea."),
    style: str = typer.Option(..., "--style", prompt=True, help="Illustration style."),
    page_count: int = typer.Option(12, "--pages", min=4, max=16, help="Book page count."),
    language: str = typer.Option("zh-CN", "--language", help="Primary book language."),
    target_age: str = typer.Option("4-6", "--age", help="Target age range."),
    book_id: str | None = typer.Option(None, "--id", help="Optional custom project id."),
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings", help="Path to settings YAML."),
) -> None:
    """Create a new book project scaffold."""
    app_settings = resolve_settings(settings)
    normalized_id = book_id or slugify(title)
    book = BookConfig(
        id=normalized_id,
        title=title,
        idea=idea,
        language=language,
        target_age=target_age,
        style=style,
        page_count=page_count,
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
    paths = resolve_project_paths(project, app_settings)
    console.print(f"Planned {len(book_spec.pages)} pages for: {book_spec.title}")
    console.print(f"Artifacts written to: {paths.artifacts_dir}")


@app.command()
def illustrate(
    project: Path = typer.Option(..., "--project", help="Path to the book project directory."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Regenerate existing page images."),
    settings: Path = typer.Option(Path("config/settings.yaml"), "--settings", help="Path to settings YAML."),
) -> None:
    """Generate page illustrations from the planned prompts."""
    app_settings = resolve_settings(settings)
    result = illustrate_book(project, app_settings, overwrite=overwrite)
    paths = resolve_project_paths(project, app_settings)
    console.print(
        f"Illustration complete for: {result.book_spec.title} "
        f"(generated={result.generated_pages}, skipped={result.skipped_pages})"
    )
    console.print(f"Images written under: {paths.images_dir}")


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


def _not_implemented(command_name: str, project: Path) -> int:
    console.print(f"`story {command_name}` is not implemented yet for project: {project}")
    return 1


if __name__ == "__main__":
    app()
