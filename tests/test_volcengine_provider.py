from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from magicstory_cli.models.config import ProviderConfig
from magicstory_cli.providers.volcengine import VolcengineImageProvider


def _make_config(**overrides) -> ProviderConfig:
    defaults = {
        "provider": "volcengine",
        "model": "doubao-seedream-3.0-t2i",
        "api_key_env": "VOLCENGINE_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com",
        "timeout_seconds": 60,
        "max_retries": 1,
    }
    defaults.update(overrides)
    return ProviderConfig(**defaults)


def _fake_png_bytes() -> bytes:
    # 最小有效 PNG
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQI12NgAAIABQAB"
        "Nl7BcQAAAABJRU5ErkJggg=="
    )


def _mock_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    resp = httpx.Response(status_code=status_code, json=json_data, request=MagicMock())
    return resp


class TestVolcengineImageProvider:
    @patch.dict("os.environ", {"VOLCENGINE_API_KEY": "test-key"})
    @patch("magicstory_cli.providers.base.httpx.Client")
    def test_generate_image_b64_json(self, mock_client_cls):
        img_b64 = base64.b64encode(_fake_png_bytes()).decode()
        mock_response = _mock_response({
            "model": "doubao-seedream-3.0-t2i",
            "created": 1234567890,
            "data": [{"b64_json": img_b64}],
        })
        mock_post = MagicMock(return_value=mock_response)
        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        config = _make_config()
        provider = VolcengineImageProvider(config)
        result = provider.generate_image("a cute cat", "/tmp/out.png")

        assert result == "/tmp/out.png"
        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert payload["model"] == "doubao-seedream-3.0-t2i"
        assert payload["prompt"] == "a cute cat"
        assert payload["response_format"] == "b64_json"
        assert payload["watermark"] is False
        assert payload["sequential_image_generation"] == "disabled"

    @patch.dict("os.environ", {"VOLCENGINE_API_KEY": "test-key"})
    @patch("magicstory_cli.providers.base.httpx.Client")
    def test_generate_image_url_fallback(self, mock_client_cls):
        """当 response_format 为 url 时，provider 回退下载。"""
        mock_img_response = httpx.Response(
            status_code=200,
            content=_fake_png_bytes(),
            request=MagicMock(),
        )
        mock_response = _mock_response({
            "model": "doubao-seedream-3.0-t2i",
            "data": [{"url": "https://example.com/image.png"}],
        })
        mock_post = MagicMock(return_value=mock_response)
        mock_get = MagicMock(return_value=mock_img_response)
        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.get = mock_get
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        config = _make_config()
        provider = VolcengineImageProvider(config)
        result = provider.generate_image("a dog", "/tmp/dog.png")

        assert result == "/tmp/dog.png"
        mock_get.assert_called_once_with("https://example.com/image.png")

    @patch.dict("os.environ", {})
    def test_missing_api_key_raises(self):
        config = _make_config(api_key_env="VOLCENGINE_API_KEY")
        provider = VolcengineImageProvider(config)
        with pytest.raises(RuntimeError, match="missing required environment variable"):
            provider.generate_image("test", "/tmp/out.png")

    @patch.dict("os.environ", {"MY_KEY": "test-key"})
    @patch("magicstory_cli.providers.base.httpx.Client")
    def test_custom_api_key_env(self, mock_client_cls):
        img_b64 = base64.b64encode(_fake_png_bytes()).decode()
        mock_response = _mock_response({
            "data": [{"b64_json": img_b64}],
        })
        mock_post = MagicMock(return_value=mock_response)
        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        config = _make_config(api_key_env="MY_KEY")
        provider = VolcengineImageProvider(config)
        provider.generate_image("test", "/tmp/out.png")

        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer test-key"

    @patch.dict("os.environ", {"VOLCENGINE_API_KEY": "test-key"})
    @patch("magicstory_cli.providers.base.httpx.Client")
    def test_seed_included_for_3_0_model(self, mock_client_cls):
        img_b64 = base64.b64encode(_fake_png_bytes()).decode()
        mock_response = _mock_response({
            "data": [{"b64_json": img_b64}],
        })
        mock_post = MagicMock(return_value=mock_response)
        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        config = _make_config(model="doubao-seedream-3.0-t2i")
        provider = VolcengineImageProvider(config)
        provider.generate_image("test", "/tmp/out.png", seed=42)

        payload = mock_post.call_args.kwargs["json"]
        assert payload["seed"] == 42

    @patch.dict("os.environ", {"VOLCENGINE_API_KEY": "test-key"})
    @patch("magicstory_cli.providers.base.httpx.Client")
    def test_seed_ignored_for_4_0_model(self, mock_client_cls):
        img_b64 = base64.b64encode(_fake_png_bytes()).decode()
        mock_response = _mock_response({
            "data": [{"b64_json": img_b64}],
        })
        mock_post = MagicMock(return_value=mock_response)
        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        config = _make_config(model="doubao-seedream-4.0")
        provider = VolcengineImageProvider(config)
        provider.generate_image("test", "/tmp/out.png", seed=42)

        payload = mock_post.call_args.kwargs["json"]
        assert "seed" not in payload

    @patch.dict("os.environ", {"VOLCENGINE_API_KEY": "test-key"})
    @patch("magicstory_cli.providers.base.httpx.Client")
    def test_reference_image_single(self, mock_client_cls, tmp_path):
        ref_img = tmp_path / "ref.png"
        ref_img.write_bytes(_fake_png_bytes())

        img_b64 = base64.b64encode(_fake_png_bytes()).decode()
        mock_response = _mock_response({
            "data": [{"b64_json": img_b64}],
        })
        mock_post = MagicMock(return_value=mock_response)
        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        config = _make_config(model="doubao-seedream-4.0")
        provider = VolcengineImageProvider(config)
        provider.generate_image("test", "/tmp/out.png", reference_images=[ref_img])

        payload = mock_post.call_args.kwargs["json"]
        assert "image" in payload
        # 单图应为字符串
        assert isinstance(payload["image"], str)
        assert payload["image"].startswith("data:image/png;base64,")

    @patch.dict("os.environ", {"VOLCENGINE_API_KEY": "test-key"})
    @patch("magicstory_cli.providers.base.httpx.Client")
    def test_reference_image_multiple(self, mock_client_cls, tmp_path):
        ref1 = tmp_path / "ref1.png"
        ref1.write_bytes(_fake_png_bytes())
        ref2 = tmp_path / "ref2.png"
        ref2.write_bytes(_fake_png_bytes())

        img_b64 = base64.b64encode(_fake_png_bytes()).decode()
        mock_response = _mock_response({
            "data": [{"b64_json": img_b64}],
        })
        mock_post = MagicMock(return_value=mock_response)
        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        config = _make_config(model="doubao-seedream-5.0-lite")
        provider = VolcengineImageProvider(config)
        provider.generate_image("test", "/tmp/out.png", reference_images=[ref1, ref2])

        payload = mock_post.call_args.kwargs["json"]
        assert isinstance(payload["image"], list)
        assert len(payload["image"]) == 2

    @patch.dict("os.environ", {"VOLCENGINE_API_KEY": "test-key"})
    @patch("magicstory_cli.providers.base.httpx.Client")
    def test_reference_image_ignored_for_3_0(self, mock_client_cls, tmp_path):
        ref_img = tmp_path / "ref.png"
        ref_img.write_bytes(_fake_png_bytes())

        img_b64 = base64.b64encode(_fake_png_bytes()).decode()
        mock_response = _mock_response({
            "data": [{"b64_json": img_b64}],
        })
        mock_post = MagicMock(return_value=mock_response)
        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        config = _make_config(model="doubao-seedream-3.0-t2i")
        provider = VolcengineImageProvider(config)
        provider.generate_image("test", "/tmp/out.png", reference_images=[ref_img])

        payload = mock_post.call_args.kwargs["json"]
        assert "image" not in payload

    @patch.dict("os.environ", {"VOLCENGINE_API_KEY": "test-key"})
    @patch("magicstory_cli.providers.base.httpx.Client")
    def test_api_error_raises(self, mock_client_cls):
        mock_response = _mock_response({
            "error": {"code": "InvalidRequest", "message": "bad prompt"},
        })
        mock_post = MagicMock(return_value=mock_response)
        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        config = _make_config()
        provider = VolcengineImageProvider(config)
        with pytest.raises(RuntimeError, match="Volcengine API error"):
            provider.generate_image("test", "/tmp/out.png")

    @patch.dict("os.environ", {"VOLCENGINE_API_KEY": "test-key"})
    @patch("magicstory_cli.providers.base.httpx.Client")
    def test_image_level_error_raises(self, mock_client_cls):
        mock_response = _mock_response({
            "data": [{"error": {"code": "ContentFilter", "message": "blocked"}}],
        })
        mock_post = MagicMock(return_value=mock_response)
        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        config = _make_config()
        provider = VolcengineImageProvider(config)
        with pytest.raises(RuntimeError, match="image generation failed"):
            provider.generate_image("test", "/tmp/out.png")

    @patch.dict("os.environ", {"VOLCENGINE_API_KEY": "test-key"})
    @patch("magicstory_cli.providers.base.httpx.Client")
    def test_empty_data_raises(self, mock_client_cls):
        mock_response = _mock_response({"data": []})
        mock_post = MagicMock(return_value=mock_response)
        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        config = _make_config()
        provider = VolcengineImageProvider(config)
        with pytest.raises(RuntimeError, match="returned no image data"):
            provider.generate_image("test", "/tmp/out.png")
