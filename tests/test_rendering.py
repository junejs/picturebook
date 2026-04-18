from __future__ import annotations

import json
from pathlib import Path

from magicstory_cli.config.loader import load_settings
from magicstory_cli.core.book_renderer import render_book
from magicstory_cli.rendering.html_renderer import render_book_html
from magicstory_cli.models.book import BookSpec, PageSpec


def test_render_book_html_includes_cover_and_pages() -> None:
    book = BookSpec(
        title="Moon Garden",
        language="zh-CN",
        target_age="4-6",
        style="warm watercolor picture book",
        page_count=4,
        pages=[
            PageSpec(
                page_number=1,
                story_text="小兔子走进月光花园。",
                illustration_prompt="A rabbit enters a moonlit garden.",
                image_path="images/page-01.png",
            ),
            PageSpec(
                page_number=2,
                story_text="它看见了一朵会发光的花。",
                illustration_prompt="The rabbit spots a glowing flower.",
                image_path="images/page-02.png",
            ),
            PageSpec(
                page_number=3,
                story_text="花朵轻轻摇摆，像在打招呼。",
                illustration_prompt="The glowing flower sways softly.",
                image_path="images/page-03.png",
            ),
            PageSpec(
                page_number=4,
                story_text="小兔子把光带回了家。",
                illustration_prompt="The rabbit carries the light home.",
                image_path="images/page-04.png",
            ),
        ],
    )
    settings = load_settings(Path("config/settings.example.yaml"))
    # 测试需要封面，确保 include_cover 为 True
    settings.render.include_cover = True

    html = render_book_html(
        book=book,
        render_config=settings.render,
        project_dir=Path("."),
        templates_dir=Path("templates"),
    )

    assert "Moon Garden" in html
    assert "MagicStory Picture Book" in html
    assert "images/page-01.png" in html
    assert "小兔子把光带回了家。" in html
    assert html.count('class="sheet page"') == 4


def test_render_book_writes_html_and_pdf_metadata(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "moon-garden"
    artifacts_dir = project_dir / "artifacts"
    images_dir = project_dir / "images"
    render_dir = project_dir / "render"
    output_dir = project_dir / "output"
    artifacts_dir.mkdir(parents=True)
    images_dir.mkdir()
    render_dir.mkdir()
    output_dir.mkdir()

    for page_number in range(1, 5):
        (images_dir / f"page-{page_number:02d}.png").write_bytes(b"fake-image")

    (artifacts_dir / "pages.json").write_text(
        json.dumps(
            {
                "title": "Moon Garden",
                "language": "zh-CN",
                "target_age": "4-6",
                "style": "warm watercolor picture book",
                "page_count": 4,
                "pages": [
                    {
                        "page_number": page_number,
                        "story_text": f"text {page_number}",
                        "illustration_prompt": f"prompt {page_number}",
                        "image_path": f"images/page-{page_number:02d}.png",
                    }
                    for page_number in range(1, 5)
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    settings = load_settings(Path("config/settings.example.yaml"))

    def fake_write_pdf(html: str, output_path: Path, base_url: Path) -> Path:
        assert "Moon Garden" in html
        assert base_url == project_dir
        output_path.write_bytes(b"%PDF-test")
        return output_path

    monkeypatch.setattr(
        "magicstory_cli.core.book_renderer.write_pdf_from_html",
        fake_write_pdf,
    )

    result = render_book(project_dir, settings, Path("templates"))

    assert result.html_path == render_dir / "book.html"
    assert result.pdf_path == output_dir / "book.pdf"
    assert result.html_path.exists()
    assert result.pdf_path.read_bytes() == b"%PDF-test"

    meta = json.loads((artifacts_dir / "render.meta.json").read_text(encoding="utf-8"))
    assert meta["html_path"] == "render/book.html"
    assert meta["pdf_path"] == "output/book.pdf"
