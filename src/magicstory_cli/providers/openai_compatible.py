from __future__ import annotations

import os

import httpx

from magicstory_cli.models.config import ProviderConfig
from magicstory_cli.providers.base import TextProvider


class OpenAICompatibleTextProvider(TextProvider):
    def __init__(self, config: ProviderConfig):
        self.config = config

    def generate_structured_text(self, prompt: str, system_prompt: str | None = None) -> str:
        api_key_name = self.config.api_key_env or "OPENAI_API_KEY"
        api_key = os.getenv(api_key_name)
        if not api_key:
            raise RuntimeError(f"missing required environment variable: {api_key_name}")

        base_url = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        payload = {
            "model": self.config.model,
            "messages": self._build_messages(prompt, system_prompt),
            "response_format": {"type": "json_object"},
        }

        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

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
