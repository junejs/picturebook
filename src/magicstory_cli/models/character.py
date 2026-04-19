from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CharacterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    style: str | None = None
    seed: int | None = None

    @field_validator("id")
    @classmethod
    def validate_character_id(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "-")
        if not normalized:
            raise ValueError("character id cannot be empty")
        return normalized
