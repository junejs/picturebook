from __future__ import annotations

import logging
import random
from pathlib import Path

from pydantic import ValidationError

from magicstory_cli.models.character import CharacterConfig
from magicstory_cli.models.config import AppSettings
from magicstory_cli.providers.factory import build_image_provider
from magicstory_cli.utils.files import ensure_directory, read_json, slugify, write_yaml
from magicstory_cli.utils.prompts import create_prompt_environment, render_prompt

logger = logging.getLogger(__name__)


def _resolve_character_dir(root: Path, character_id: str) -> Path:
    return root / character_id


def create_character(
    root: Path,
    config: CharacterConfig,
    settings: AppSettings,
    prompts_dir: Path,
) -> CharacterConfig:
    char_dir = ensure_directory(_resolve_character_dir(root, config.id))
    logger.info("Creating character: %s in %s", config.name, char_dir)

    # Generate a random seed for reproducible image generation
    seed = random.randint(0, 2**31 - 1)
    config.seed = seed
    logger.info("Character seed: %s", seed)

    # Step 1: Generate reference image via text-to-image
    style = config.style or "picture book"
    prompt_env = create_prompt_environment(prompts_dir)
    gen_prompt = render_prompt(
        prompt_env,
        "character_generation.jinja2",
        style=style,
        instruction=config.description,
    )

    image_provider = build_image_provider(settings)
    reference_path = str(char_dir / "reference.png")
    image_provider.generate_image(gen_prompt, reference_path, seed=seed)
    logger.info("Reference image generated: %s", reference_path)

    # Step 2: Save character.yaml
    write_yaml(
        char_dir / "character.yaml",
        {"character": config.model_dump(mode="json", exclude_none=True)},
    )
    logger.info("Character created: %s (%s)", config.name, config.id)
    return config


def list_characters(root: Path) -> list[CharacterConfig]:
    if not root.exists():
        return []
    characters: list[CharacterConfig] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        yaml_path = child / "character.yaml"
        if not yaml_path.exists():
            continue
        try:
            char = load_character(root, child.name)
            characters.append(char)
        except Exception:
            logger.warning("Failed to load character from %s", child)
    return characters


def load_character(root: Path, character_id: str) -> CharacterConfig:
    char_dir = _resolve_character_dir(root, character_id)
    yaml_path = char_dir / "character.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"character not found: {character_id}")

    data = read_json(yaml_path) if yaml_path.suffix == ".json" else _load_yaml_simple(yaml_path)
    char_data = data.get("character", data)

    try:
        return CharacterConfig.model_validate(char_data)
    except ValidationError as exc:
        raise RuntimeError(f"invalid character config for {character_id}: {exc}") from exc


def _load_yaml_simple(path: Path) -> dict:
    import yaml

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping at the top level")
    return data
