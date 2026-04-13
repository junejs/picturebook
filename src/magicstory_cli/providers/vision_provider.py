from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class VisionProvider(ABC):
    @abstractmethod
    def analyze_image(
        self,
        image_path: Path,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Analyze an image and return a text description."""
