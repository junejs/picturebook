from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

import httpx

from magicstory_cli.models.config import ProviderConfig
from magicstory_cli.providers.base import ImageProvider

logger = logging.getLogger(__name__)


def _encode_image_as_data_url(image_path: Path) -> str:
    import mimetypes

    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    image_bytes = image_path.read_bytes()
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


class VolcengineImageProvider(ImageProvider):
    """火山引擎（豆包）文生图 / 图生图 Provider。

    兼容 Seedream 3.0 / 4.0 / 4.5 / 5.0 系列模型。
    API 文档: https://www.volcengine.com/docs/82379/1666945
    """

    def __init__(self, config: ProviderConfig):
        self.config = config

    def generate_image(
        self,
        prompt: str,
        output_path: str,
        reference_images: list[Path] | None = None,
        seed: int | None = None,
    ) -> str:
        api_key_name = self.config.api_key_env or "VOLCENGINE_API_KEY"
        api_key = os.getenv(api_key_name)
        if not api_key:
            raise RuntimeError(f"missing required environment variable: {api_key_name}")

        base_url = (self.config.base_url or "https://ark.cn-beijing.volces.com").rstrip("/")
        payload: dict = {
            "model": self.config.model,
            "prompt": prompt,
            "response_format": "b64_json",
            "watermark": False,
            "sequential_image_generation": "disabled",
        }

        # 种子参数仅 doubao-seedream-3.0-t2i 支持
        model_lower = self.config.model.lower()
        if seed is not None and "3.0" in model_lower:
            payload["seed"] = seed

        # 参考图：仅 4.0/4.5/5.0 系列支持
        if reference_images and "3.0" not in model_lower:
            if len(reference_images) == 1:
                payload["image"] = _encode_image_as_data_url(reference_images[0])
            else:
                payload["image"] = [
                    _encode_image_as_data_url(p) for p in reference_images
                ]

        url = f"{base_url}/api/v3/images/generations"
        logger.info(
            "Image request: POST %s model=%s seed=%s ref_count=%s",
            url,
            self.config.model,
            seed,
            len(reference_images) if reference_images else 0,
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
            "Image response: status=%s model=%s output=%s",
            response.status_code,
            self.config.model,
            output_path,
        )

        # 顶层错误
        if "error" in data:
            err = data["error"]
            raise RuntimeError(
                f"Volcengine API error: code={err.get('code')} message={err.get('message')}"
            )

        images = data.get("data", [])
        if not images:
            raise RuntimeError("Volcengine API returned no image data")

        first = images[0]
        # 单图内嵌错误
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
                # 回退：通过 URL 下载图片
                logger.info("Downloading image from URL: %s", image_url)
                with httpx.Client(timeout=self.config.timeout_seconds) as dl_client:
                    dl_resp = dl_client.get(image_url)
                    dl_resp.raise_for_status()
                    image_bytes = dl_resp.content
            else:
                raise RuntimeError("Volcengine API returned no image data (url or b64_json)")
        else:
            image_bytes = base64.b64decode(image_b64)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(image_bytes)
        return str(output)
