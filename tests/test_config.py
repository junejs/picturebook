from __future__ import annotations

import pytest
from pydantic import ValidationError

from magicstory_cli.models.config import BookConfig


def test_book_id_is_normalized() -> None:
    book = BookConfig(
        id="  My Book  ",
        title="Moon Garden",
        idea="A rabbit looks for a glowing flower.",
        style="warm watercolor picture book",
        page_count=12,
    )

    assert book.id == "my-book"


@pytest.mark.parametrize("page_count", [3, 17])
def test_book_page_count_must_stay_in_supported_range(page_count: int) -> None:
    with pytest.raises(ValidationError):
        BookConfig(
            id="moon-garden",
            title="Moon Garden",
            idea="A rabbit looks for a glowing flower.",
            style="warm watercolor picture book",
            page_count=page_count,
        )
