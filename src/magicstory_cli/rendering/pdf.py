from __future__ import annotations

import tempfile
from pathlib import Path


def write_pdf_from_html(html: str, output_path: Path, base_url: Path) -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - depends on runtime install
        raise RuntimeError("Playwright is not installed. Run `uv sync && playwright install chromium` first.") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write HTML to a temp file so Playwright can resolve relative URLs (images, css) via file://
    with tempfile.NamedTemporaryFile(
        suffix=".html", dir=base_url, delete=False, mode="w", encoding="utf-8"
    ) as tmp:
        tmp.write(html)
        tmp_path = Path(tmp.name)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(tmp_path.as_uri())
            page.pdf(path=str(output_path), format="A4", print_background=True)
            browser.close()
    finally:
        tmp_path.unlink(missing_ok=True)

    return output_path
