from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from magicstory_cli.cli.app import app


def test_new_project_prompts_for_missing_fields(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_book_project(root: Path, book, settings):
        captured["root"] = root
        captured["book"] = book
        captured["settings"] = settings
        return tmp_path / "projects" / book.id

    monkeypatch.setattr("magicstory_cli.cli.app.create_book_project", fake_create_book_project)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["new", "--settings", "config/settings.example.yaml"],
        input=(
            "Moon Garden\n"
            "A rabbit seeks a glowing flower.\n"
            "warm watercolor picture book\n"
            "8\n"
            "zh-CN\n"
            "4-6\n"
            "moon-garden\n"
            "notes here\n"
        ),
    )

    assert result.exit_code == 0, result.output
    assert captured["root"] == Path("projects")
    book = captured["book"]
    assert book.title == "Moon Garden"
    assert book.idea == "A rabbit seeks a glowing flower."
    assert book.style == "warm watercolor picture book"
    assert book.page_count == 8
    assert book.language == "zh-CN"
    assert book.target_age == "4-6"
    assert book.id == "moon-garden"
    assert book.notes == "notes here"


def test_new_project_uses_defaults_without_prompt_when_fully_specified(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_book_project(root: Path, book, settings):
        captured["root"] = root
        captured["book"] = book
        captured["settings"] = settings
        return tmp_path / "projects" / book.id

    monkeypatch.setattr("magicstory_cli.cli.app.create_book_project", fake_create_book_project)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "new",
            "Moon Garden",
            "--idea",
            "A rabbit seeks a glowing flower.",
            "--style",
            "warm watercolor picture book",
            "--pages",
            "8",
            "--language",
            "zh-CN",
            "--age",
            "4-6",
            "--settings",
            "config/settings.example.yaml",
        ],
    )

    assert result.exit_code == 0, result.output
    book = captured["book"]
    assert book.id == "moon-garden"
    assert book.notes is None
