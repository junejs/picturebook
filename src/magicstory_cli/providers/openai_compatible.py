from __future__ import annotations

import base64
import logging
import mimetypes
import os
from pathlib import Path

import httpx

from magicstory_cli.models.config import ProviderConfig
from magicstory_cli.providers.base import TextProvider
from magicstory_cli.providers.vision_provider import VisionProvider

logger = logging.getLogger(__name__)


class OpenAICompatibleTextProvider(TextProvider):
    def __init__(self, config: ProviderConfig):
        self.config = config

    def generate_structured_text(self, prompt: str, system_prompt: str | None = None) -> str:
        api_key_name = self.config.api_key_env or "OPENAI_API_KEY"
        api_key = os.getenv(api_key_name)
        if not api_key:
            raise RuntimeError(f"missing required environment variable: {api_key_name}")

        base_url = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        payload: dict = {
            "model": self.config.model,
            "messages": self._build_messages(prompt, system_prompt),
        }
        if self.config.json_mode:
            payload["response_format"] = {"type": "json_object"}

        url = f"{base_url}/chat/completions"
        logger.info(
            "LLM request: POST %s model=%s messages=%d",
            url,
            self.config.model,
            len(payload["messages"]),
        )

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

        usage = data.get("usage")
        if usage:
            logger.info(
                "LLM response: status=%s model=%s prompt_tokens=%s completion_tokens=%s",
                response.status_code,
                self.config.model,
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
            )
        else:
            logger.info("LLM response: status=%s model=%s", response.status_code, self.config.model)

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("text provider returned an unexpected response shape") from exc

    @staticmethod
    def _build_messages(prompt: str, system_prompt: str | None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages


def _encode_image_as_data_url(image_path: Path) -> str:
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    image_bytes = image_path.read_bytes()
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


class OpenAICompatibleVisionProvider(VisionProvider):
    def __init__(self, config: ProviderConfig):
        self.config = config

    def analyze_image(
        self,
        image_path: Path,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        api_key_name = self.config.api_key_env or "VISION_AI_API_KEY"
        api_key = os.getenv(api_key_name)
        if not api_key:
            raise RuntimeError(f"missing required environment variable: {api_key_name}")

        base_url = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        data_url = _encode_image_as_data_url(image_path)

        user_content: list[dict] = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": self.config.model,
            "messages": messages,
        }

        url = f"{base_url}/chat/completions"
        logger.info(
            "Vision request: POST %s model=%s image=%s",
            url,
            self.config.model,
            image_path.name,
        )

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

        logger.info(
            "Vision response: status=%s model=%s",
            response.status_code,
            self.config.model,
        )

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("vision provider returned an unexpected response shape") from exc
