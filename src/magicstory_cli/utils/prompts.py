from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined


def create_prompt_environment(prompts_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(prompts_dir)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )


def render_prompt(environment: Environment, template_name: str, **context: Any) -> str:
    template = environment.get_template(template_name)
    return template.render(**context).strip()
