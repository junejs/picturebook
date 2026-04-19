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
from magicstory_cli.providers.factory import build_image_provider, build_text_provider
from magicstory_cli.utils.files import slugify

app = typer.Typer(
    help=(
        "MagicStory CLI — 将故事想法转化为插画 PDF 绘本。\n"
        "\n"
        "完整流程:\n"
        "  1. story character new <name> --description '...'   # 创建角色（可选）\n"
        "  2. story new '书名' --idea '故事想法' --pages N     # 创建项目\n"
        "  3. story plan --project <dir>                       # 生成故事与插图提示词\n"
        "  4. story illustrate --project <dir>                 # 生成插图\n"
        "  5. story render --project <dir>                     # 渲染 HTML + PDF\n"
        "\n"
        "或者一步到位:\n"
        "  story build --project <dir>                         # plan + illustrate + render\n"
        "\n"
        "配置文件:\n"
        "  按优先级: --settings 指定 > ./config/settings.yaml > ~/.magicstory/settings.yaml\n"
        "  运行 story config --help 查看完整配置字段说明\n"
        "\n"
        "项目结构:\n"
        "  <project>/book.yaml            # 书籍配置\n"
        "  <project>/artifacts/pages.json # 故事内容与插图提示词\n"
        "  <project>/images/page-NN.png   # 插图\n"
        "  <project>/render/book.html     # HTML 预览\n"
        "  <project>/output/book.pdf      # 最终 PDF"
    ),
    no_args_is_help=True,
)
character_app = typer.Typer(help="管理可复用角色（character new 创建角色，character list 列出已有角色）。")
app.add_typer(character_app, name="character")
console = Console()
PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"

_DEFAULT_SETTINGS_CANDIDATES = [
    Path("config/settings.yaml"),
    Path.home() / ".magicstory" / "settings.yaml",
]

logging.basicConfig(
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)


def resolve_settings(settings_path: Path | None = None) -> tuple[AppSettings, Path]:
    if settings_path is not None:
        if not settings_path.exists():
            raise typer.BadParameter(f"settings file not found: {settings_path}")
    else:
        for candidate in _DEFAULT_SETTINGS_CANDIDATES:
            if candidate.exists():
                settings_path = candidate
                break
        if settings_path is None:
            raise typer.BadParameter(
                "未找到配置文件，请通过 --settings 指定，或将配置放在以下位置之一:\n"
                "  ./config/settings.yaml\n"
                "  ~/.magicstory/settings.yaml"
            )
    app_settings = load_settings(settings_path)
    logging.getLogger().setLevel(app_settings.app.log_level.upper())
    return app_settings, settings_path


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
    name: str = typer.Argument(..., help="角色名称"),
    description: str = typer.Option(..., "--description", "-d", help="角色外观描述（必填）"),
    style: str | None = typer.Option(None, "--style", "-s", help="画风覆盖，不传则使用 settings 中的默认画风"),
    settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
) -> None:
    """创建角色并生成参考图。

    输出: characters/<id>/character.yaml + characters/<id>/reference.png
    """
    app_settings, resolved_settings = resolve_settings(settings)

    char_id = slugify(name)
    char_config = CharacterConfig(
        id=char_id,
        name=name,
        description=description,
        style=style,
    )

    characters_dir = resolve_characters_dir(app_settings)
    with console.status("Generating character reference image..."):
        result = create_character(characters_dir, char_config, app_settings, PROMPTS_DIR)

    console.print(f"[bold green]Character created:[/] {result.name} ({result.id})")
    console.print(f"  Reference: {characters_dir / result.id / 'reference.png'}")
    console.print(f"  Description: {result.description[:200]}")


@character_app.command("list")
def character_list(
    settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
) -> None:
    """列出所有已创建的角色。"""
    app_settings, resolved_settings = resolve_settings(settings)
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
            char.description[:60] + "...",
        )

    console.print(table)


# ── Project commands ────────────────────────────────────────────────────────


@app.command()
def doctor(
    settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
) -> None:
    """检查环境与 provider 配置是否正确。"""
    app_settings, resolved_settings = resolve_settings(settings)

    table = Table(title="MagicStory Doctor")
    table.add_column("Check")
    table.add_column("Result")

    table.add_row("Settings file", f"OK: {resolved_settings}")
    table.add_row("Workspace", str(app_settings.runtime.workspace_dir))
    table.add_row("Characters dir", str(resolve_characters_dir(app_settings)))
    table.add_row("Text provider", f"{app_settings.providers.text.provider} / {app_settings.providers.text.model}")
    active_image = app_settings.providers.image.get_active_config()
    table.add_row(
        "Image provider", f"{app_settings.providers.image.active} / {active_image.model}"
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

    console.print(table)


@app.command("config")
def show_config(
    settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
) -> None:
    """显示当前生效的配置文件内容和来源。

    配置文件位置（按优先级）:
      1. --settings 指定的路径
      2. ./config/settings.yaml（当前目录）
      3. ~/.magicstory/settings.yaml（用户主目录）

    配置文件格式 (YAML):

    providers:
      text:                              # 文本 AI 配置（用于生成故事和插图提示词）
        provider: openai-compatible      # provider 类型，当前仅支持 openai-compatible
        model: gpt-4.1-mini             # 模型名称
        api_key_env: TEXT_AI_API_KEY    # API Key 对应的环境变量名
        base_url: null                  # API 地址，null 则使用 provider 默认值
        timeout_seconds: 300            # 请求超时（秒）
        max_retries: 2                  # 最大重试次数
        json_mode: true                 # 是否启用 JSON 输出模式
      image:                            # 图片 AI 配置（用于生成插图）
        active: minimax                 # 当前使用的 image provider 名称
        minimax:                        # minimax provider 配置
          provider: minimax
          model: image-01
          api_key_env: IMAGE_AI_API_KEY
          base_url: https://api.minimaxi.com
        volcengine:                     # 火山引擎 provider 配置（可选）
          provider: volcengine
          model: doubao-seedream-3.0-t2i
          api_key_env: VOLCENGINE_API_KEY
          base_url: https://ark.cn-beijing.volces.com

    render:                             # 渲染配置
      page_size: 210mmx210mm           # 页面尺寸
      include_cover: false              # 是否包含封面
      text_layout: bottom-band          # 文字布局: bottom-band | overlay | full-page-text
      body_font: Noto Sans SC           # 正文字体
      heading_font: Noto Serif SC       # 标题字体
      dpi: 144                          # 渲染分辨率

    runtime:                            # 运行时配置
      workspace_dir: projects           # 项目工作目录（相对路径或绝对路径）
      characters_dirname: characters    # 角色目录名
      artifacts_dirname: artifacts      # 中间产物目录名
      images_dirname: images            # 插图目录名
      output_dirname: output            # 输出目录名（PDF 所在）
      render_dirname: render            # 渲染目录名（HTML 所在）
      max_parallel_image_jobs: 2        # 图片生成最大并行数（1-8）

    features:                           # 功能开关
      enable_reference_image: false     # 是否在插图生成时传入角色参考图

    app:                                # 应用配置
      log_level: info                   # 日志级别: debug | info | warning | error
      default_style: 水彩画             # 默认插画风格
    """
    import yaml as _yaml

    app_settings, resolved_settings = resolve_settings(settings)
    with open(resolved_settings, "r", encoding="utf-8") as f:
        raw = _yaml.safe_load(f) or {}

    console.print(f"[bold]配置文件:[/] {resolved_settings}")
    console.print()
    console.print(_yaml.dump(raw, allow_unicode=True, default_flow_style=False))


@app.command("new")
def new_project(
    title: str | None = typer.Argument(None, help="书名"),
    idea: str | None = typer.Option(None, "--idea", help="故事核心想法（必填，缺失则进入交互模式）"),
    style: str | None = typer.Option(None, "--style", help="插画风格，如 '水彩画'、'Cartoon'"),
    page_count: int | None = typer.Option(None, "--pages", min=4, max=16, help="页数，范围 4-16"),
    language: str | None = typer.Option(None, "--language", help="语言，默认 zh-CN"),
    target_age: str | None = typer.Option(None, "--age", help="目标年龄段，默认 4-6"),
    book_id: str | None = typer.Option(None, "--id", help="自定义项目 ID，默认由书名自动生成"),
    characters: list[str] | None = typer.Option(None, "--characters", "-c", help="关联角色 ID，可多次传"),
    notes: str | None = typer.Option(None, "--notes", help="补充说明"),
    settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
) -> None:
    """创建绘本项目。

    必须同时提供 title 和 --idea 才能非交互运行，否则会进入交互提示。
    输出: projects/<id>/book.yaml
    """
    app_settings, resolved_settings = resolve_settings(settings)
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
    project: Path = typer.Option(..., "--project", help="项目目录路径（必填）"),
    settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
) -> None:
    """生成故事内容与每页插图提示词。

    前置条件: 必须先运行 story new 创建项目。
    输出: <project>/artifacts/pages.json
    """
    app_settings, resolved_settings = resolve_settings(settings)
    book_spec = plan_story(project, app_settings, PROMPTS_DIR)
    paths = resolve_characters_dir(app_settings)
    console.print(f"Planned {len(book_spec.pages)} pages for: {book_spec.title}")


@app.command()
def illustrate(
    project: Path = typer.Option(..., "--project", help="项目目录路径（必填）"),
    overwrite: bool = typer.Option(False, "--overwrite", help="强制重新生成已有插图"),
    settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
) -> None:
    """为每页生成插图。

    前置条件: 必须先运行 story plan。
    已有插图的页面默认跳过，除非使用 --overwrite。
    输出: <project>/images/page-01.png ~ page-NN.png
    """
    app_settings, resolved_settings = resolve_settings(settings)
    result = illustrate_book(project, app_settings, PROMPTS_DIR, overwrite=overwrite)
    console.print(
        f"Illustration complete for: {result.book_spec.title} "
        f"(generated={result.generated_pages}, skipped={result.skipped_pages})"
    )


@app.command()
def render(
    project: Path = typer.Option(..., "--project", help="项目目录路径（必填）"),
    settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
) -> None:
    """渲染 HTML 预览与 PDF 文件。

    前置条件: 必须先运行 story illustrate。
    输出: <project>/render/book.html + <project>/output/book.pdf
    """
    app_settings, resolved_settings = resolve_settings(settings)
    result = render_book(project, app_settings, TEMPLATES_DIR)
    console.print(f"Rendered HTML: {result.html_path}")
    console.print(f"Rendered PDF: {result.pdf_path}")


@app.command("e2e-test")
def e2e_test(
    settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
) -> None:
    """运行端到端测试：用真实 AI API 生成一本 4 页迷你绘本。"""
    app_settings, resolved_settings = resolve_settings(settings)

    test_id = "e2e-test-little-cat"
    test_title = "小汽车 max 的冒险故事"
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
        name="max",
        description="一辆小汽车，名字叫 max，是一辆小校车，颜色是鲜艳的橘红色，车顶有一个小小的行李架，前脸有 max 字样，车窗是圆形的，像眼睛一样，车头有一个微笑的格栅，整体造型可爱又充满冒险精神",
        style="卡通风格",
    )
    with console.status("Generating character reference image..."):
        char_result = create_character(characters_dir, char_config, app_settings, PROMPTS_DIR)
    console.print(f"  Character created: {char_result.name} ({char_result.id})")

    # Step 2: Create book project with character reference
    book = BookConfig(
        id=test_id,
        title=test_title,
        idea="去爬山，途中遇到暴风雨，最后安全回家",
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
    project: Path = typer.Option(..., "--project", help="项目目录路径（必填）"),
    overwrite: bool = typer.Option(False, "--overwrite", help="强制重新生成已有插图"),
    settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
) -> None:
    """一键运行完整流程: plan → illustrate → render。

    等同于依次运行 plan、illustrate、render 三个命令。
    输出: artifacts/pages.json + images/*.png + render/book.html + output/book.pdf
    """
    app_settings, resolved_settings = resolve_settings(settings)
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
