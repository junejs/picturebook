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
            logger.warning("Character %s not found, skipping", char_id)
            continue

        descriptions.append(f"{char.name}: {char.description}")

        if char.seed is not None and seed is None:
            seed = char.seed

        if include_reference_images and ctx.settings.features.enable_reference_image:
            ref_path = ctx.characters_dir / char_id / "reference.png"
            if ref_path.exists():
                reference_images.append(ref_path)
            else:
                logger.warning("Reference image not found for %s: %s", char_id, ref_path)

    return CharacterContext(
        description_text="; ".join(descriptions),
        reference_images=reference_images,
        seed=seed,
    )
