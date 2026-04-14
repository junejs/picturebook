from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class TextProvider(ABC):
    @abstractmethod
    def generate_structured_text(self, prompt: str, system_prompt: str | None = None) -> str:
        raise NotImplementedError


class ImageProvider(ABC):
    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        output_path: str,
        reference_images: list[Path] | None = None,
        seed: int | None = None,
    ) -> str:
        raise NotImplementedError
