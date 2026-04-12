from __future__ import annotations

import pytest

from magicstory_cli.core.story_planner import _validate_payload


def test_validate_payload_accepts_expected_page_sequence() -> None:
    payload = {
        "pages": [
            {
                "page_number": 1,
                "story_text": "第一页的文字。",
                "illustration_prompt": "A rabbit stands in a moonlit garden.",
            },
            {
                "page_number": 2,
                "story_text": "第二页的文字。",
                "illustration_prompt": "The rabbit follows a glowing trail through flowers.",
            },
            {
                "page_number": 3,
                "story_text": "第三页的文字。",
                "illustration_prompt": "The rabbit reaches a bright flower under the moon.",
            },
            {
                "page_number": 4,
                "story_text": "第四页的文字。",
                "illustration_prompt": "The garden glows softly as the rabbit smiles.",
            },
        ]
    }

    model = _validate_payload(payload, expected_page_count=4)

    assert len(model.pages) == 4
    assert model.pages[0].page_number == 1
    assert model.pages[-1].page_number == 4


def test_validate_payload_rejects_non_sequential_page_numbers() -> None:
    payload = {
        "pages": [
            {"page_number": 1, "story_text": "A", "illustration_prompt": "B"},
            {"page_number": 3, "story_text": "C", "illustration_prompt": "D"},
            {"page_number": 4, "story_text": "E", "illustration_prompt": "F"},
            {"page_number": 5, "story_text": "G", "illustration_prompt": "H"},
        ]
    }

    with pytest.raises(RuntimeError, match="page numbers must be sequential"):
        _validate_payload(payload, expected_page_count=4)


def test_validate_payload_rejects_page_count_mismatch() -> None:
    payload = {
        "pages": [
            {"page_number": 1, "story_text": "A", "illustration_prompt": "B"},
            {"page_number": 2, "story_text": "C", "illustration_prompt": "D"},
            {"page_number": 3, "story_text": "E", "illustration_prompt": "F"},
        ]
    }

    with pytest.raises(RuntimeError, match="expected 4 pages"):
        _validate_payload(payload, expected_page_count=4)
