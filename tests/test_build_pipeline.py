from __future__ import annotations

import json
from pathlib import Path

from magicstory_cli.config.loader import load_settings
from magicstory_cli.core.build_pipeline import build_book


def test_build_book_runs_full_pipeline_with_stubbed_dependencies(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_dir = tmp_path / "moon-garden"
    artifacts_dir = project_dir / "artifacts"
    images_dir = project_dir / "images"
    output_dir = project_dir / "output"
    render_dir = project_dir / "render"
    artifacts_dir.mkdir(parents=True)
    images_dir.mkdir()
    output_dir.mkdir()
    render_dir.mkdir()

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

    settings = load_settings(Path("config/settings.example.yaml"))

    planning_payload = {
        "pages": [
            {
                "page_number": page_number,
                "story_text": f"story {page_number}",
                "illustration_prompt": f"prompt {page_number}",
            }
            for page_number in range(1, 5)
        ]
    }

    class FakeTextProvider:
        def generate_structured_text(self, prompt: str, system_prompt: str | None = None) -> str:
            assert "Moon Garden" in prompt
            assert system_prompt is not None
            return json.dumps(planning_payload, ensure_ascii=False)

    class FakeImageProvider:
        def generate_image(self, prompt: str, output_path: str, reference_images=None, seed=None) -> str:
            assert "warm watercolor picture book" in prompt
            path = Path(output_path)
            path.write_bytes(b"fake-image")
            return str(path)

    def fake_write_pdf(html: str, output_path: Path, base_url: Path) -> Path:
        assert "Moon Garden" in html
        assert base_url == project_dir
        output_path.write_bytes(b"%PDF-fake")
        return output_path

    monkeypatch.setattr(
        "magicstory_cli.core.story_planner.build_text_provider",
        lambda settings: FakeTextProvider(),
    )
    monkeypatch.setattr(
        "magicstory_cli.core.illustrator.build_image_provider",
        lambda settings: FakeImageProvider(),
    )
    monkeypatch.setattr(
        "magicstory_cli.core.book_renderer.write_pdf_from_html",
        fake_write_pdf,
    )

    result = build_book(
        project_dir=project_dir,
        settings=settings,
        prompts_dir=Path("prompts"),
        templates_dir=Path("templates"),
        overwrite_images=False,
    )

    assert len(result.planned_book.pages) == 4
    assert result.illustration_result.generated_pages == 4
    assert result.render_result.pdf_path == output_dir / "book.pdf"
    assert (artifacts_dir / "pages.json").exists()
    assert (artifacts_dir / "render.meta.json").exists()
    assert (render_dir / "book.html").exists()
    assert (output_dir / "book.pdf").read_bytes() == b"%PDF-fake"
