from __future__ import annotations

import base64
import logging
from pathlib import Path

from magicstory_cli.providers.base import BaseHttpProvider, ImageProvider
from magicstory_cli.utils.files import encode_image_as_data_url

logger = logging.getLogger(__name__)


class MiniMaxImageProvider(BaseHttpProvider, ImageProvider):
    def generate_image(
        self,
        prompt: str,
        output_path: str,
        reference_images: list[Path] | None = None,
        seed: int | None = None,
    ) -> str:
        api_key = self._get_api_key("MINIMAX_API_KEY")
        base_url = self.config.base_url.rstrip("/")
        payload: dict = {
            "model": self.config.model,
            "prompt": prompt,
            "aspect_ratio": "1:1",
            "response_format": "base64",
            "n": 1,
            "prompt_optimizer": True,
        }

        if seed is not None:
            payload["seed"] = seed

        if reference_images:
            subject_refs = []
            for ref_path in reference_images:
                data_url = encode_image_as_data_url(ref_path)
                subject_refs.append({"type": "character", "image_file": data_url})
            payload["subject_reference"] = subject_refs
            payload["prompt_optimizer"] = False

        url = f"{base_url}/v1/image_generation"
        ref_count = len(reference_images) if reference_images else 0
        self._log_request(url, seed=seed, ref_count=ref_count)

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

        self._log_response(response.status_code, output=output_path)

        status_code = data.get("base_resp", {}).get("status_code")
        if status_code not in (None, 0):
            status_message = data.get("base_resp", {}).get("status_msg", "unknown error")
            raise RuntimeError(f"MiniMax returned status {status_code}: {status_message}")

        image_base64 = data.get("data", {}).get("image_base64", [None])[0]
        if not image_base64:
            raise RuntimeError("MiniMax did not return image data")

        return self._write_image(output_path, base64.b64decode(image_base64))
