from __future__ import annotations

import logging

from magicstory_cli.providers.base import BaseHttpProvider, TextProvider

logger = logging.getLogger(__name__)


class OpenAICompatibleTextProvider(BaseHttpProvider, TextProvider):
    def generate_structured_text(self, prompt: str, system_prompt: str | None = None) -> str:
        api_key = self._get_api_key("OPENAI_API_KEY")
        base_url = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        payload: dict = {
            "model": self.config.model,
            "messages": self._build_messages(prompt, system_prompt),
        }
        if self.config.json_mode:
            payload["response_format"] = {"type": "json_object"}

        url = f"{base_url}/chat/completions"
        self._log_request(url, messages=len(payload["messages"]))

        with self._http_client() as client:
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
            self._log_response(
                response.status_code,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
            )
        else:
            self._log_response(response.status_code)

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
