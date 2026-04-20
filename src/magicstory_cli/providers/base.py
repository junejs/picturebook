from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from magicstory_cli.models.config import ProviderConfig

logger = logging.getLogger(__name__)


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


class BaseHttpProvider:
    """Provider 公共基类：统一 API key 获取、HTTP 客户端创建、日志、图片写入。"""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    def _get_api_key(self, default_env: str) -> str:
        api_key_name = self.config.api_key_env or default_env
        api_key = os.getenv(api_key_name)
        if not api_key:
            raise RuntimeError(f"missing required environment variable: {api_key_name}")
        return api_key

    def _http_client(self) -> httpx.Client:
        transport = httpx.HTTPTransport(retries=self.config.max_retries)
        return httpx.Client(timeout=self.config.timeout_seconds, transport=transport)

    def _log_request(self, url: str, **extra: object) -> None:
        logger.info(
            "%s request: POST %s model=%s %s",
            type(self).__name__,
            url,
            self.config.model,
            " ".join(f"{k}={v}" for k, v in extra.items()),
        )

    def _log_response(self, status_code: int, **extra: object) -> None:
        logger.info(
            "%s response: status=%s model=%s %s",
            type(self).__name__,
            status_code,
            self.config.model,
            " ".join(f"{k}={v}" for k, v in extra.items()),
        )

    def _write_image(self, output_path: str, image_bytes: bytes) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(image_bytes)
        return str(output)
