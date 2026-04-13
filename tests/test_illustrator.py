from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from magicstory_cli.config.loader import load_settings
from magicstory_cli.core.illustrator import illustrate_book


def test_illustrate_book_skips_existing_images_and_updates_paths(tmp_path: Path) -> None:
    project_dir = tmp_path / "moon-garden"
    artifacts_dir = project_dir / "artifacts"
    images_dir = project_dir / "images"
    artifacts_dir.mkdir(parents=True)
    images_dir.mkdir()

    (project_dir / "book.yaml").write_text(
        """
book:
  id: moon-garden
  title: Moon Garden
  idea: A rabbit looks for a glowing flower.
  language: zh-CN
  target_age: 4-6
  style: warm watercolor picture book
  page_count: 4
""".strip(),
        encoding="utf-8",
    )

    pages = []
    for page_number in range(1, 5):
        (images_dir / f"page-{page_number:02d}.png").write_bytes(b"fake-image")
        pages.append(
            {
                "page_number": page_number,
                "story_text": f"text {page_number}",
                "illustration_prompt": f"prompt {page_number}",
                "image_path": None,
            }
        )

    (artifacts_dir / "pages.json").write_text(
        json.dumps(
            {
                "title": "Moon Garden",
                "language": "zh-CN",
                "target_age": "4-6",
                "style": "warm watercolor picture book",
                "page_count": 4,
                "pages": pages,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    settings = load_settings(Path("config/settings.example.yaml"))
    result = illustrate_book(project_dir, settings, Path("prompts"), overwrite=False)

    assert result.generated_pages == 0
    assert result.skipped_pages == 4

    updated = json.loads((artifacts_dir / "pages.json").read_text(encoding="utf-8"))
    assert updated["pages"][0]["image_path"] == "images/page-01.png"
    assert updated["pages"][3]["image_path"] == "images/page-04.png"

    meta = json.loads((artifacts_dir / "illustration.meta.json").read_text(encoding="utf-8"))
    assert meta["generated_pages"] == 0
    assert meta["skipped_pages"] == 4


def test_illustrate_book_uses_parallel_workers_when_configured(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "moon-garden"
    artifacts_dir = project_dir / "artifacts"
    images_dir = project_dir / "images"
    artifacts_dir.mkdir(parents=True)
    images_dir.mkdir()

    (project_dir / "book.yaml").write_text(
        """
book:
  id: moon-garden
  title: Moon Garden
  idea: A rabbit looks for a glowing flower.
  language: zh-CN
  target_age: 4-6
  style: warm watercolor picture book
  page_count: 4
""".strip(),
        encoding="utf-8",
    )

    pages = []
    for page_number in range(1, 5):
        pages.append(
            {
                "page_number": page_number,
                "story_text": f"text {page_number}",
                "illustration_prompt": f"prompt {page_number}",
                "image_path": None,
            }
        )

    (artifacts_dir / "pages.json").write_text(
        json.dumps(
            {
                "title": "Moon Garden",
                "language": "zh-CN",
                "target_age": "4-6",
                "style": "warm watercolor picture book",
                "page_count": 4,
                "pages": pages,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    settings = load_settings(Path("config/settings.example.yaml"))
    settings.runtime.max_parallel_image_jobs = 2

    active_count = 0
    max_active_count = 0
    lock = threading.Lock()
    overlap_event = threading.Event()

    class FakeImageProvider:
        def generate_image(self, prompt: str, output_path: str, reference_images=None) -> str:
            nonlocal active_count, max_active_count
            with lock:
                active_count += 1
                max_active_count = max(max_active_count, active_count)
                if active_count >= 2:
                    overlap_event.set()
            if not overlap_event.wait(timeout=1):
                raise AssertionError("image generation did not overlap")
            time.sleep(0.05)
            path = Path(output_path)
            path.write_bytes(b"fake-image")
            with lock:
                active_count -= 1
            return str(path)

    monkeypatch.setattr(
        "magicstory_cli.core.illustrator.build_image_provider",
        lambda settings: FakeImageProvider(),
    )

    result = illustrate_book(project_dir, settings, Path("prompts"), overwrite=False)

    assert result.generated_pages == 4
    assert result.skipped_pages == 0
    assert max_active_count >= 2
    assert (images_dir / "page-01.png").exists()
    assert (images_dir / "page-04.png").exists()
