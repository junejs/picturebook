from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from magicstory_cli.core.character_manager import load_character
from magicstory_cli.core.paths import PipelineContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CharacterContext:
    description_text: str = ""
    reference_images: list[Path] = field(default_factory=list)
    seed: int | None = None


def load_character_context(
    ctx: PipelineContext,
    character_ids: list[str],
    include_reference_images: bool = False,
) -> CharacterContext:
    """统一加载角色上下文：描述文本、参考图、种子值。"""
    if not character_ids:
        return CharacterContext()

    descriptions: list[str] = []
    reference_images: list[Path] = []
    seed: int | None = None

    for char_id in character_ids:
        try:
            char = load_character(ctx.characters_dir, char_id)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"角色 '{char_id}' 未找到，请先运行 story character new 创建角色"
            ) from None

        descriptions.append(f"{char.name}: {char.description}")

        if char.seed is not None and seed is None:
            seed = char.seed

        if include_reference_images and ctx.settings.features.enable_reference_image:
            ref_path = ctx.characters_dir / char_id / "reference.png"
            if not ref_path.exists():
                raise FileNotFoundError(
                    f"角色 '{char_id}' 的参考图不存在: {ref_path}，"
                    f"请重新创建角色以生成参考图"
                )
            reference_images.append(ref_path)

    return CharacterContext(
        description_text="; ".join(descriptions),
        reference_images=reference_images,
        seed=seed,
    )
