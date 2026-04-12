from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

import httpx

from magicstory_cli.models.config import ProviderConfig
from magicstory_cli.providers.base import ImageProvider

logger = logging.getLogger(__name__)


class MiniMaxImageProvider(ImageProvider):
    def __init__(self, config: ProviderConfig):
        self.config = config

    def generate_image(self, prompt: str, output_path: str) -> str:
        api_key_name = self.config.api_key_env or "MINIMAX_API_KEY"
        api_key = os.getenv(api_key_name)
        if not api_key:
            raise RuntimeError(f"missing required environment variable: {api_key_name}")

        base_url = (self.config.base_url or "https://api.minimaxi.com").rstrip("/")
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "aspect_ratio": "1:1",
            "response_format": "base64",
            "n": 1,
            "prompt_optimizer": True,
        }

        url = f"{base_url}/v1/image_generation"
        logger.info("Image request: POST %s model=%s", url, self.config.model)

        transport = httpx.HTTPTransport(retries=self.config.max_retries)
        with httpx.Client(timeout=self.config.timeout_seconds, transport=transport) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        logger.info("Image response: status=%s model=%s output=%s", response.status_code, self.config.model, output_path)

        status_code = data.get("base_resp", {}).get("status_code")
        if status_code not in (None, 0):
            status_message = data.get("base_resp", {}).get("status_msg", "unknown error")
            raise RuntimeError(f"MiniMax returned status {status_code}: {status_message}")

        image_base64 = data.get("data", {}).get("image_base64", [None])[0]
        if not image_base64:
            raise RuntimeError("MiniMax did not return image data")

        image_bytes = base64.b64decode(image_base64)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(image_bytes)
        return str(output)
