from __future__ import annotations

from pathlib import Path


def write_pdf_from_html(html: str, output_path: Path, base_url: Path) -> Path:
    try:
        from weasyprint import HTML
    except ImportError as exc:  # pragma: no cover - depends on runtime install
        raise RuntimeError("WeasyPrint is not installed. Run `uv sync` first.") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(base_url)).write_pdf(str(output_path))
    return output_path
