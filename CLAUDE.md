# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language

This project's primary language is Chinese — code comments, prompts, CLI output, and README are all in Chinese. Maintain Chinese for user-facing text and prompts.

## Commands

```bash
uv sync                      # Install dependencies
playwright install chromium  # Download Chromium for PDF rendering
uv run story --help          # CLI help
uv run story doctor          # Validate environment/providers
pytest -q                    # Run all tests
pytest -q tests/test_config.py::test_name  # Run single test
ruff check src/              # Lint
ruff format src/             # Format
```

## Architecture

MagicStory CLI is a pipeline tool that transforms story ideas into illustrated PDF books. The pipeline has four stages: **new → plan → illustrate → render** (or `build` for all at once).

### Pipeline flow

```
story new → creates projects/<id>/book.yaml
story plan → calls text AI → writes artifacts/pages.json (story text + illustration prompts per page)
story illustrate → calls image AI per page → writes images/page-NN.png
story render → Jinja2 HTML → Playwright (Chromium) PDF
```

Intermediate artifacts in `artifacts/` enable resume — `illustrate` skips pages that already have images unless `--overwrite`.

### Key modules

| Layer | Directory | Responsibility |
|-------|-----------|---------------|
| CLI | `src/magicstory_cli/cli/` | Typer commands, input collection |
| Core | `src/magicstory_cli/core/` | Pipeline orchestration (story_planner, illustrator, book_renderer, build_pipeline, character_manager, project_scaffold) |
| Models | `src/magicstory_cli/models/` | Pydantic v2 schemas (config, book, character) |
| Providers | `src/magicstory_cli/providers/` | Abstract base + concrete implementations (openai_compatible for text/vision, minimax for images) |
| Rendering | `src/magicstory_cli/rendering/` | Jinja2 HTML + Playwright PDF |
| Prompts | `prompts/` | Jinja2 templates for AI prompts — no business logic |
| Templates | `templates/` | HTML template for book layout |

### Character system

Global reusable characters in `characters/<id>/` (character.yaml + reference.png). Creating a character generates a reference image via text-to-image, then a Vision model extracts a precise visual description. Both the description (injected into prompts) and reference image (passed via API) ensure consistency across pages.

### Configuration

`config/settings.yaml` defines providers (text/image/vision), render settings, and runtime options. API keys come from environment variables (`TEXT_AI_API_KEY`, `IMAGE_AI_API_KEY`, `VISION_AI_API_KEY`). Page count is strictly 4–16. Feature flags in `features:` section control optional behavior (e.g. `enable_reference_image: false` skips passing reference images to the image model, using only text descriptions).

## Module separation rules

- `prompts/` — only prompt text, no logic
- `providers/` — only model calls, no pipeline orchestration
- `core/` — pipeline orchestration only
- `templates/` — layout and visual structure only
- `tests/` — must be updated alongside feature changes

When modifying a pipeline stage, check: schema → artifact format → tests → README.

## Testing

Tests must not depend on external APIs. Provider integration tests are separate from unit tests. Every new stable feature needs at least one test.

## Linting

Ruff with rules E, F, I, UP, B. Line length 100. Target Python 3.12.
