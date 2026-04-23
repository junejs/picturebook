from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler

from magicstory_cli.config.loader import load_settings
from magicstory_cli.models.config import AppSettings

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
console = Console()

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


# 注册命令模块
from magicstory_cli.cli.commands import (  # noqa: E402
    build,
    character,
    config_cmd,
    illustrate,
    plan,
    project,
    render,
)

project.register(app)
plan.register(app)
illustrate.register(app)
render.register(app)
build.register(app)
character.register(app)
config_cmd.register(app)

if __name__ == "__main__":
    app()
