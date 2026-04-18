from __future__ import annotations

import json


def parse_json_object(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    # 剥离模型返回的 <think...</think?> 思考标签
    cleaned = _strip_think_tags(cleaned)
    if cleaned.startswith("```"):
        cleaned = _strip_fence(cleaned)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def _strip_fence(text: str) -> str:
    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
        return "\n".join(lines[1:-1]).strip()
    return text


def _strip_think_tags(text: str) -> str:
    import re

    return re.sub(r"<think[^>]*>.*?</think\s*>", "", text, flags=re.DOTALL).strip()
