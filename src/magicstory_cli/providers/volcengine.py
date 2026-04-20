from __future__ import annotations

import base64
import logging
from pathlib import Path

from magicstory_cli.providers.base import BaseHttpProvider, ImageProvider
from magicstory_cli.utils.files import encode_image_as_data_url

logger = logging.getLogger(__name__)


class VolcengineImageProvider(BaseHttpProvider, ImageProvider):
    """火山引擎（豆包）文生图 / 图生图 Provider。"""

    def generate_image(
        self,
        prompt: str,
        output_path: str,
        reference_images: list[Path] | None = None,
        seed: int | None = None,
    ) -> str:
        api_key = self._get_api_key("VOLCENGINE_API_KEY")
        base_url = (self.config.base_url or "https://ark.cn-beijing.volces.com").rstrip("/")
        payload: dict = {
            "model": self.config.model,
            "prompt": prompt,
            "response_format": "b64_json",
            "watermark": False,
            "sequential_image_generation": "disabled",
        }

        model_lower = self.config.model.lower()
        if seed is not None and "3.0" in model_lower:
            payload["seed"] = seed

        if reference_images and "3.0" not in model_lower:
            if len(reference_images) == 1:
                payload["image"] = encode_image_as_data_url(reference_images[0])
            else:
                payload["image"] = [
                    encode_image_as_data_url(p) for p in reference_images
                ]

        url = f"{base_url}/api/v3/images/generations"
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

        if "error" in data:
            err = data["error"]
            raise RuntimeError(
                f"Volcengine API error: code={err.get('code')} message={err.get('message')}"
            )

        images = data.get("data", [])
        if not images:
            raise RuntimeError("Volcengine API returned no image data")

        first = images[0]
        if "error" in first:
            err = first["error"]
            raise RuntimeError(
                f"Volcengine image generation failed: code={err.get('code')} "
                f"message={err.get('message')}"
            )

        image_b64 = first.get("b64_json")
        if not image_b64:
            image_url = first.get("url")
            if image_url:
                logger.info("Downloading image from URL: %s", image_url)
                with self._http_client() as dl_client:
                    dl_resp = dl_client.get(image_url)
                    dl_resp.raise_for_status()
                    return self._write_image(output_path, dl_resp.content)
            else:
                raise RuntimeError("Volcengine API returned no image data (url or b64_json)")

        return self._write_image(output_path, base64.b64decode(image_b64))
