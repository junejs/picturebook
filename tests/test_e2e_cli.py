from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from magicstory_cli.config.loader import load_settings
from magicstory_cli.core.build_pipeline import build_book
from magicstory_cli.core.character_manager import create_character
from magicstory_cli.core.paths import PipelineContext
from magicstory_cli.core.project_scaffold import create_book_project
from magicstory_cli.models.character import CharacterConfig
from magicstory_cli.models.config import BookConfig

pytestmark = pytest.mark.e2e


@pytest.mark.skipif(
    not __import__("os").environ.get("TEXT_AI_API_KEY"),
    reason="需要设置 TEXT_AI_API_KEY 等环境变量",
)
def test_e2e_build_pipeline(tmp_path: Path) -> None:
    """端到端测试：用真实 AI API 生成一本 4 页迷你绘本。"""
    settings = load_settings(Path("config/settings.example.yaml"))

    # 创建角色
    characters_dir = tmp_path / "characters"
    test_char_id = "e2e-test-orange-cat"
    char_config = CharacterConfig(
        id=test_char_id,
        name="max",
        description="一辆小汽车，名字叫 max，是一辆小校车，颜色是鲜艳的橘红色",
        style="卡通风格",
    )
    ctx_for_char = PipelineContext.from_settings(tmp_path, settings)
    create_character(
        characters_dir, char_config, settings, ctx_for_char.prompts_dir
    )

    # 创建项目
    workspace = tmp_path / "projects"
    book = BookConfig(
        id="e2e-test-little-cat",
        title="小汽车 max 的冒险故事",
        idea="去爬山，途中遇到暴风雨，最后安全回家",
        language="zh-CN",
        target_age="7-8",
        style="卡通风格",
        page_count=4,
        characters=[test_char_id],
    )
    project_dir = create_book_project(workspace, book, settings)

    # 运行 build
    result = build_book(project_dir, settings, overwrite_images=False)

    assert len(result.planned_book.pages) == 4
    assert result.illustration_result.generated_pages >= 0

    # 清理
    shutil.rmtree(project_dir, ignore_errors=True)
    shutil.rmtree(characters_dir / test_char_id, ignore_errors=True)
