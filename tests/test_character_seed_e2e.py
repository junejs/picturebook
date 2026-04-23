"""End-to-end tests verifying seed is generated, saved, and reused across character creation and illustration."""

from __future__ import annotations

import json
from pathlib import Path

from magicstory_cli.config.loader import load_settings
from magicstory_cli.core.character_manager import create_character, load_character
from magicstory_cli.core.illustrator import illustrate_book
from magicstory_cli.core.paths import PipelineContext
from magicstory_cli.models.character import CharacterConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_book_yaml(project_dir: Path, characters: list[str] | None = None) -> None:
    chars_block = ""
    if characters:
        chars_block = "\n  characters:\n" + "".join(
            f"    - {c}\n" for c in characters
        )
    (project_dir / "book.yaml").write_text(
        f"""
book:
  id: test-book
  title: Test Book
  idea: A test story.
  language: zh-CN
  target_age: 4-6
  style: picture book
  page_count: 4
{chars_block}
""".strip(),
        encoding="utf-8",
    )


def _write_pages_json(artifacts_dir: Path) -> None:
    pages = [
        {
            "page_number": i,
            "story_text": f"text {i}",
            "illustration_prompt": f"prompt {i}",
            "image_path": None,
        }
        for i in range(1, 5)
    ]
    (artifacts_dir / "pages.json").write_text(
        json.dumps(
            {
                "title": "Test Book",
                "language": "zh-CN",
                "target_age": "4-6",
                "style": "picture book",
                "page_count": 4,
                "pages": pages,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_character_generates_and_saves_seed(
    tmp_path: Path, monkeypatch
) -> None:
    """Seed should be auto-generated during character creation and persisted in character.yaml."""
    characters_dir = tmp_path / "characters"
    settings = load_settings(Path("config/settings.example.yaml"))
    settings.runtime.workspace_dir = tmp_path / "projects"

    received_seeds: list[int | None] = []

    class FakeImageProvider:
        def generate_image(
            self,
            prompt: str,
            output_path: str,
            reference_images=None,
            seed: int | None = None,
        ) -> str:
            received_seeds.append(seed)
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fake-reference")
            return str(path)

    monkeypatch.setattr(
        "magicstory_cli.core.character_manager.build_image_provider",
        lambda s: FakeImageProvider(),
    )

    config = CharacterConfig(id="xiao-ming", name="Xiao Ming", description="A 6-year-old boy")
    result = create_character(
        root=characters_dir,
        config=config,
        settings=settings,
        prompts_dir=Path("prompts"),
    )

    # 1. Seed should be set on the returned config
    assert result.seed is not None
    assert isinstance(result.seed, int)
    assert 0 <= result.seed < 2**31

    # 2. Seed should have been passed to the image provider
    assert len(received_seeds) == 1
    assert received_seeds[0] == result.seed

    # 3. Seed should be persisted in character.yaml
    loaded = load_character(characters_dir, result.id)
    assert loaded.seed == result.seed

    # 4. character.yaml file should contain the seed field
    yaml_text = (characters_dir / result.id / "character.yaml").read_text("utf-8")
    assert f"seed: {result.seed}" in yaml_text


def test_create_character_uses_specific_seed(tmp_path: Path, monkeypatch) -> None:
    """When seed is pre-set on the config, it should be passed through (not overwritten)."""
    characters_dir = tmp_path / "characters"
    settings = load_settings(Path("config/settings.example.yaml"))
    settings.runtime.workspace_dir = tmp_path / "projects"

    received_seeds: list[int | None] = []

    class FakeImageProvider:
        def generate_image(
            self,
            prompt: str,
            output_path: str,
            reference_images=None,
            seed: int | None = None,
        ) -> str:
            received_seeds.append(seed)
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fake-reference")
            return str(path)

    monkeypatch.setattr(
        "magicstory_cli.core.character_manager.build_image_provider",
        lambda s: FakeImageProvider(),
    )

    fixed_seed = 12345678
    config = CharacterConfig(
        id="test-char", name="Test Char", description="A test", seed=fixed_seed
    )
    result = create_character(
        root=characters_dir,
        config=config,
        settings=settings,
        prompts_dir=Path("prompts"),
    )

    # create_character generates a new random seed, overwriting the pre-set one
    assert result.seed is not None
    assert result.seed != fixed_seed  # it was overwritten by random seed

    # The random seed was passed to the image provider
    assert received_seeds[0] == result.seed


def test_illustrate_book_passes_character_seed_to_image_provider(
    tmp_path: Path, monkeypatch
) -> None:
    """When illustrating a book with characters, the character seed should be passed to generate_image."""
    project_dir = tmp_path / "moon-garden"
    characters_dir = tmp_path / "projects" / "characters"
    artifacts_dir = project_dir / "artifacts"
    images_dir = project_dir / "images"
    for d in [artifacts_dir, images_dir, characters_dir]:
        d.mkdir(parents=True)

    # Set up character with known seed
    char_id = "hero"
    (characters_dir / char_id).mkdir()
    (characters_dir / char_id / "character.yaml").write_text(
        f"""
character:
  id: hero
  name: Hero
  description: A brave hero
  seed: 99887766
""".strip(),
        encoding="utf-8",
    )
    (characters_dir / char_id / "reference.png").write_bytes(b"fake-ref")

    _write_book_yaml(project_dir, characters=["hero"])
    _write_pages_json(artifacts_dir)

    settings = load_settings(Path("config/settings.example.yaml"))
    settings.runtime.workspace_dir = tmp_path / "projects"
    settings.runtime.max_parallel_image_jobs = 1

    received_seeds: list[int | None] = []

    class FakeImageProvider:
        def generate_image(
            self,
            prompt: str,
            output_path: str,
            reference_images=None,
            seed: int | None = None,
        ) -> str:
            received_seeds.append(seed)
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fake-image")
            return str(path)

    monkeypatch.setattr(
        "magicstory_cli.core.illustrator.build_image_provider",
        lambda s: FakeImageProvider(),
    )

    ctx = PipelineContext.from_settings(project_dir, settings)
    result = illustrate_book(ctx, overwrite=False)

    assert result.generated_pages == 4
    # All pages should receive the character's seed
    assert len(received_seeds) == 4
    assert all(s == 99887766 for s in received_seeds)


def test_illustrate_book_no_seed_when_no_character(tmp_path: Path, monkeypatch) -> None:
    """When no characters are configured, seed should be None for illustration calls."""
    project_dir = tmp_path / "moon-garden"
    artifacts_dir = project_dir / "artifacts"
    images_dir = project_dir / "images"
    for d in [artifacts_dir, images_dir]:
        d.mkdir(parents=True)

    _write_book_yaml(project_dir, characters=None)
    _write_pages_json(artifacts_dir)

    settings = load_settings(Path("config/settings.example.yaml"))
    settings.runtime.workspace_dir = tmp_path / "projects"
    settings.runtime.max_parallel_image_jobs = 1

    received_seeds: list[int | None] = []

    class FakeImageProvider:
        def generate_image(
            self,
            prompt: str,
            output_path: str,
            reference_images=None,
            seed: int | None = None,
        ) -> str:
            received_seeds.append(seed)
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fake-image")
            return str(path)

    monkeypatch.setattr(
        "magicstory_cli.core.illustrator.build_image_provider",
        lambda s: FakeImageProvider(),
    )

    ctx = PipelineContext.from_settings(project_dir, settings)
    result = illustrate_book(ctx, overwrite=False)

    assert result.generated_pages == 4
    assert all(s is None for s in received_seeds)


def test_illustrate_book_uses_first_character_seed_with_multiple_characters(
    tmp_path: Path, monkeypatch
) -> None:
    """With multiple characters, the first character's seed should be used."""
    project_dir = tmp_path / "moon-garden"
    characters_dir = tmp_path / "projects" / "characters"
    artifacts_dir = project_dir / "artifacts"
    images_dir = project_dir / "images"
    for d in [artifacts_dir, images_dir, characters_dir]:
        d.mkdir(parents=True)

    for char_id, seed_val in [("hero", 11111), ("sidekick", 22222)]:
        char_dir = characters_dir / char_id
        char_dir.mkdir()
        (char_dir / "character.yaml").write_text(
            f"""
character:
  id: {char_id}
  name: {char_id.title()}
  description: A character
  seed: {seed_val}
""".strip(),
            encoding="utf-8",
        )
        (char_dir / "reference.png").write_bytes(b"fake-ref")

    _write_book_yaml(project_dir, characters=["hero", "sidekick"])
    _write_pages_json(artifacts_dir)

    settings = load_settings(Path("config/settings.example.yaml"))
    settings.runtime.workspace_dir = tmp_path / "projects"
    settings.runtime.max_parallel_image_jobs = 1

    received_seeds: list[int | None] = []

    class FakeImageProvider:
        def generate_image(
            self,
            prompt: str,
            output_path: str,
            reference_images=None,
            seed: int | None = None,
        ) -> str:
            received_seeds.append(seed)
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fake-image")
            return str(path)

    monkeypatch.setattr(
        "magicstory_cli.core.illustrator.build_image_provider",
        lambda s: FakeImageProvider(),
    )

    ctx = PipelineContext.from_settings(project_dir, settings)
    result = illustrate_book(ctx, overwrite=False)

    assert result.generated_pages == 4
    # Should use the first character's seed
    assert all(s == 11111 for s in received_seeds)
