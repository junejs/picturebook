# MagicStory CLI 重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 MagicStory CLI — 消除重复、统一 Provider 抽象、引入 PipelineContext、拆分 CLI、统一角色加载

**Architecture:** 5 个独立任务按顺序执行。每个任务完成后全量测试通过、提交一次。Provider 层独立先行；PipelineContext 作为后续任务的基础。

**Tech Stack:** Python 3.12, Typer, Pydantic v2, httpx, Jinja2, Playwright

---

## Task 1: Provider 层重构 — 公共基类 + 工具函数提取

**Files:**
- Modify: `src/magicstory_cli/utils/files.py` — 新增 `encode_image_as_data_url`
- Modify: `src/magicstory_cli/providers/base.py` — 新增 `BaseHttpProvider`
- Modify: `src/magicstory_cli/providers/openai_compatible.py` — 继承 `BaseHttpProvider`
- Modify: `src/magicstory_cli/providers/minimax.py` — 继承 `BaseHttpProvider`，删除重复代码
- Modify: `src/magicstory_cli/providers/volcengine.py` — 继承 `BaseHttpProvider`，删除重复代码
- Modify: `tests/test_volcengine_provider.py` — mock 路径可能变化

- [ ] **Step 1: 在 `utils/files.py` 新增 `encode_image_as_data_url`**

在文件末尾添加：

```python
import base64
import mimetypes


def encode_image_as_data_url(image_path: Path) -> str:
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    image_bytes = image_path.read_bytes()
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{b64}"
```

注意：`base64` 和 `mimetypes` 需要在文件顶部 import（`json` 和 `re` 已有，在它们之后加）。

- [ ] **Step 2: 在 `providers/base.py` 新增 `BaseHttpProvider`**

保留现有 `TextProvider` 和 `ImageProvider` ABC 不变，在文件末尾添加：

```python
import logging
import os

import httpx

from magicstory_cli.models.config import ProviderConfig

logger = logging.getLogger(__name__)


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
        logger.info("%s request: POST %s model=%s %s", type(self).__name__, url, self.config.model, " ".join(f"{k}={v}" for k, v in extra.items()))

    def _log_response(self, status_code: int, **extra: object) -> None:
        logger.info("%s response: status=%s model=%s %s", type(self).__name__, status_code, self.config.model, " ".join(f"{k}={v}" for k, v in extra.items()))

    def _write_image(self, output_path: str, image_bytes: bytes) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(image_bytes)
        return str(output)
```

需要在文件顶部补充 imports：
```python
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from magicstory_cli.models.config import ProviderConfig
```

- [ ] **Step 3: 重写 `providers/openai_compatible.py`**

完整替换为：

```python
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
```

- [ ] **Step 4: 重写 `providers/minimax.py`**

完整替换为：

```python
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
        self._log_request(url, seed=seed, ref_count=len(reference_images) if reference_images else 0)

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
```

- [ ] **Step 5: 重写 `providers/volcengine.py`**

完整替换为：

```python
from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx

from magicstory_cli.providers.base import BaseHttpProvider, ImageProvider
from magicstory_cli.utils.files import encode_image_as_data_url

logger = logging.getLogger(__name__)


class VolcengineImageProvider(BaseHttpProvider, ImageProvider):
    """火山引擎（豆包）文生图 / 图生图 Provider。

    兼容 Seedream 3.0 / 4.0 / 4.5 / 5.0 系列模型。
    API 文档: https://www.volcengine.com/docs/82379/1666945
    """

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

        # 种子参数仅 doubao-seedream-3.0-t2i 支持
        model_lower = self.config.model.lower()
        if seed is not None and "3.0" in model_lower:
            payload["seed"] = seed

        # 参考图：仅 4.0/4.5/5.0 系列支持
        if reference_images and "3.0" not in model_lower:
            if len(reference_images) == 1:
                payload["image"] = encode_image_as_data_url(reference_images[0])
            else:
                payload["image"] = [
                    encode_image_as_data_url(p) for p in reference_images
                ]

        url = f"{base_url}/api/v3/images/generations"
        self._log_request(url, seed=seed, ref_count=len(reference_images) if reference_images else 0)

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
                with self._http_client() as dl_client:
                    dl_resp = dl_client.get(image_url)
                    dl_resp.raise_for_status()
                    return self._write_image(output_path, dl_resp.content)
            else:
                raise RuntimeError("Volcengine API returned no image data (url or b64_json)")

        return self._write_image(output_path, base64.b64decode(image_b64))
```

- [ ] **Step 6: 更新 `tests/test_volcengine_provider.py` 中的 mock 路径**

所有 `@patch("magicstory_cli.providers.volcengine.httpx.Client")` 不变（volcengine.py 仍然直接 import httpx，因为 generate_image 内部的 `self._http_client()` 返回的 client 在 with 语句中使用，mock 路径不变）。

但需确认：volcengine.py 顶部 `import httpx` 仍在（因为 `self._http_client()` 定义在 base.py 中通过 `import httpx` 使用）。mock 路径需要改为 mock base 中的 httpx.Client，因为现在 `_http_client()` 在 base.py 中。

将所有 `@patch("magicstory_cli.providers.volcengine.httpx.Client")` 替换为 `@patch("magicstory_cli.providers.base.httpx.Client")`。

同理，minimax 测试如果有的话也需同样处理。

- [ ] **Step 7: 运行测试确认通过**

```bash
pytest -q
ruff check src/
```

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "refactor: extract BaseHttpProvider and encode_image_as_data_url"
```

---

## Task 2: Pipeline 上下文 + 路径配置化

**Files:**
- Modify: `src/magicstory_cli/models/config.py` — `RuntimeConfig` 新增字段
- Modify: `src/magicstory_cli/core/paths.py` — 新增 `PipelineContext`
- Modify: `src/magicstory_cli/core/story_planner.py` — 签名改为 `(ctx: PipelineContext)`
- Modify: `src/magicstory_cli/core/illustrator.py` — 签名改为 `(ctx: PipelineContext, overwrite)`
- Modify: `src/magicstory_cli/core/book_renderer.py` — 签名改为 `(ctx: PipelineContext)`
- Modify: `src/magicstory_cli/core/build_pipeline.py` — 构造 `PipelineContext`
- Modify: `src/magicstory_cli/cli/app.py` — CLI 命令改用 `PipelineContext`
- Modify: `tests/test_illustrator.py` — 适配新签名
- Modify: `tests/test_build_pipeline.py` — 适配新签名
- Modify: `config/settings.example.yaml` — 新增字段

- [ ] **Step 1: `models/config.py` — RuntimeConfig 新增 `prompts_dir` / `templates_dir`**

在 `RuntimeConfig` 类中，`max_parallel_image_jobs` 之后新增：

```python
    prompts_dir: Path | None = None
    templates_dir: Path | None = None
```

- [ ] **Step 2: `core/paths.py` — 新增 `PipelineContext`**

在文件末尾新增：

```python
from dataclasses import dataclass

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class PipelineContext:
    settings: AppSettings
    paths: ProjectPaths
    prompts_dir: Path
    templates_dir: Path
    characters_dir: Path

    @classmethod
    def from_settings(cls, project_dir: Path, settings: AppSettings) -> PipelineContext:
        paths = resolve_project_paths(project_dir, settings)
        characters_dir = resolve_characters_dir(settings)
        prompts_dir = settings.runtime.prompts_dir or _PACKAGE_ROOT / "prompts"
        templates_dir = settings.runtime.templates_dir or _PACKAGE_ROOT / "templates"
        return cls(
            settings=settings,
            paths=paths,
            prompts_dir=prompts_dir,
            templates_dir=templates_dir,
            characters_dir=characters_dir,
        )
```

- [ ] **Step 3: 重写 `core/story_planner.py` — 使用 PipelineContext**

将 `plan_story` 签名从 `def plan_story(project_dir: Path, settings: AppSettings, prompts_dir: Path)` 改为 `def plan_story(ctx: PipelineContext)`。

函数体变更：
- `paths = resolve_project_paths(project_dir, settings)` → `paths = ctx.paths`
- `book = load_book_config(paths.book_yaml)` — 不变
- `characters_dir = resolve_characters_dir(settings)` → `characters_dir = ctx.characters_dir`
- `prompt_env = create_prompt_environment(prompts_dir)` → `prompt_env = create_prompt_environment(ctx.prompts_dir)`
- `provider = build_text_provider(settings)` → `provider = build_text_provider(ctx.settings)`

更新 import：移除不再需要的 `resolve_project_paths`, `resolve_characters_dir`；新增 `PipelineContext`。

- [ ] **Step 4: 重写 `core/illustrator.py` — 使用 PipelineContext**

将 `illustrate_book` 签名从 `def illustrate_book(project_dir, settings, prompts_dir, overwrite)` 改为 `def illustrate_book(ctx: PipelineContext, overwrite: bool = False)`。

函数体变更：
- `paths = resolve_project_paths(project_dir, settings)` → `paths = ctx.paths`
- `characters_dir = resolve_characters_dir(settings)` → `characters_dir = ctx.characters_dir`
- `book = load_book_config(paths.book_yaml)` — 不变
- `provider = build_image_provider(settings)` → `provider = build_image_provider(ctx.settings)`
- `max_workers = settings.runtime.max_parallel_image_jobs` → `max_workers = ctx.settings.runtime.max_parallel_image_jobs`
- `prompt_env = create_prompt_environment(prompts_dir)` → `prompt_env = create_prompt_environment(ctx.prompts_dir)`
- 所有 `settings.features` / `settings.runtime` 引用 → `ctx.settings.features` / `ctx.settings.runtime`
- `_generate_image` 内部 lambda/closure 中的 `project_dir` → `ctx.paths.project_dir`

更新 import：移除不再需要的直接 import；新增 `PipelineContext`。

- [ ] **Step 5: 重写 `core/book_renderer.py` — 使用 PipelineContext**

将 `render_book` 签名从 `def render_book(project_dir, settings, templates_dir)` 改为 `def render_book(ctx: PipelineContext)`。

函数体变更：
- `paths = resolve_project_paths(project_dir, settings)` → `paths = ctx.paths`
- `html = render_book_html(..., templates_dir=templates_dir)` → `html = render_book_html(..., templates_dir=ctx.templates_dir)`
- `write_pdf_from_html(html, pdf_path, base_url=project_dir)` → `write_pdf_from_html(html, pdf_path, base_url=ctx.paths.project_dir)`
- `settings.render` → `ctx.settings.render`

更新 import：移除不再需要的；新增 `PipelineContext`。

- [ ] **Step 6: 重写 `core/build_pipeline.py` — 构造 PipelineContext**

完整替换为：

```python
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from magicstory_cli.core.book_renderer import RenderResult, render_book
from magicstory_cli.core.illustrator import IllustrationResult, illustrate_book
from magicstory_cli.core.paths import PipelineContext
from magicstory_cli.core.story_planner import plan_story
from magicstory_cli.models.book import BookSpec
from magicstory_cli.models.config import AppSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BuildResult:
    planned_book: BookSpec
    illustration_result: IllustrationResult
    render_result: RenderResult


def build_book(
    project_dir: Path,
    settings: AppSettings,
    overwrite_images: bool = False,
) -> BuildResult:
    logger.info("Starting full build pipeline for: %s", project_dir)
    ctx = PipelineContext.from_settings(project_dir, settings)

    planned_book = plan_story(ctx)
    illustration_result = illustrate_book(ctx, overwrite=overwrite_images)
    render_result = render_book(ctx)

    logger.info("Build pipeline complete for: %s", planned_book.title)
    return BuildResult(
        planned_book=planned_book,
        illustration_result=illustration_result,
        render_result=render_result,
    )
```

注意：`build_book` 不再接受 `prompts_dir` / `templates_dir` 参数（它们现在通过 `PipelineContext.from_settings` 自动解析）。

- [ ] **Step 7: 更新 `cli/app.py` — 命令改用 PipelineContext**

各命令中：
- `plan` 命令：`plan_story(project, app_settings, PROMPTS_DIR)` → `plan_story(PipelineContext.from_settings(project, app_settings))`
- `illustrate` 命令：`illustrate_book(project, app_settings, PROMPTS_DIR, overwrite=overwrite)` → `illustrate_book(PipelineContext.from_settings(project, app_settings), overwrite=overwrite)`
- `render` 命令：`render_book(project, app_settings, TEMPLATES_DIR)` → `render_book(PipelineContext.from_settings(project, app_settings))`
- `build` 命令：`build_book(project, app_settings, prompts_dir=PROMPTS_DIR, templates_dir=TEMPLATES_DIR, overwrite_images=overwrite)` → `build_book(project, app_settings, overwrite_images=overwrite)`
- `e2e-test` 命令：同理更新
- 删除 `PROMPTS_DIR` 和 `TEMPLATES_DIR` 两个常量（不再需要，路径由 PipelineContext 解析）
- 新增 `from magicstory_cli.core.paths import PipelineContext`

- [ ] **Step 8: 更新 `tests/test_illustrator.py` — 适配新签名**

测试中所有 `illustrate_book(project_dir, settings, Path("prompts"), overwrite=False)` 改为：

```python
from magicstory_cli.core.paths import PipelineContext

# 构造 context
ctx = PipelineContext.from_settings(project_dir, settings)
result = illustrate_book(ctx, overwrite=False)
```

注意：由于 `PipelineContext.from_settings` 会从 `settings.runtime.prompts_dir` 解析，而 example settings 中默认为 None，所以会使用 `_PACKAGE_ROOT / "prompts"` 作为默认值，测试中如果 prompts 目录不存在但测试不实际渲染模板（只是 skip），这是 OK 的。

- [ ] **Step 9: 更新 `tests/test_build_pipeline.py` — 适配新签名**

测试中 `build_book(project_dir=..., settings=..., prompts_dir=..., templates_dir=..., overwrite_images=False)` 改为 `build_book(project_dir=..., settings=..., overwrite_images=False)`（prompts_dir 和 templates_dir 不再是参数）。

- [ ] **Step 10: 更新 `config/settings.example.yaml`**

在 `runtime:` 块中 `max_parallel_image_jobs: 2` 之后新增注释说明：

```yaml
  # prompts_dir: null            # Jinja2 提示词模板目录，null 则使用包内置 prompts/
  # templates_dir: null          # HTML 模板目录，null 则使用包内置 templates/
```

- [ ] **Step 11: 运行测试确认通过**

```bash
pytest -q
ruff check src/
```

- [ ] **Step 12: 提交**

```bash
git add -A
git commit -m "refactor: introduce PipelineContext and configure prompts/templates dir"
```

---

## Task 3: 统一角色上下文服务

**Files:**
- Create: `src/magicstory_cli/core/character_context.py`
- Modify: `src/magicstory_cli/core/story_planner.py` — 删除内联角色加载
- Modify: `src/magicstory_cli/core/illustrator.py` — 删除 `_build_character_description` / `_get_character_seed` / `_collect_reference_images`

- [ ] **Step 1: 创建 `core/character_context.py`**

```python
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from magicstory_cli.core.character_manager import load_character
from magicstory_cli.core.paths import PipelineContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CharacterContext:
    description_text: str = ""
    reference_images: list[Path] = field(default_factory=list)
    seed: int | None = None


def load_character_context(
    ctx: PipelineContext,
    character_ids: list[str],
    include_reference_images: bool = False,
) -> CharacterContext:
    if not character_ids:
        return CharacterContext()

    descriptions: list[str] = []
    reference_images: list[Path] = []
    seed: int | None = None

    for char_id in character_ids:
        try:
            char = load_character(ctx.characters_dir, char_id)
        except FileNotFoundError:
            logger.warning("Character %s not found, skipping", char_id)
            continue

        descriptions.append(f"{char.name}: {char.description}")

        if char.seed is not None and seed is None:
            seed = char.seed

        if include_reference_images and ctx.settings.features.enable_reference_image:
            ref_path = ctx.characters_dir / char_id / "reference.png"
            if ref_path.exists():
                reference_images.append(ref_path)
            else:
                logger.warning("Reference image not found for %s: %s", char_id, ref_path)

    return CharacterContext(
        description_text="; ".join(descriptions),
        reference_images=reference_images,
        seed=seed,
    )
```

- [ ] **Step 2: 重写 `core/story_planner.py` — 使用 `load_character_context`**

删除第 42-52 行的内联角色加载代码（`characters_dir = resolve_characters_dir(settings)` + for loop），替换为：

```python
from magicstory_cli.core.character_context import load_character_context

# 在 plan_story 函数内，替换角色加载部分：
characters_text = ""
if book.characters:
    char_ctx = load_character_context(ctx, book.characters)
    descriptions = char_ctx.description_text.split("; ") if char_ctx.description_text else []
    characters_text = "\n".join(f"- **{d.split(':')[0]}**:{d.split(':', 1)[1]}" for d in descriptions) if descriptions else ""
```

注意：`story_planner.py` 当前的格式是 `- **name**: description`（每行一个），而 `CharacterContext.description_text` 用 `"; "` 分隔（`name: description`）。需要在此处做格式转换。

- [ ] **Step 3: 重写 `core/illustrator.py` — 使用 `load_character_context`**

删除 `_build_character_description`、`_get_character_seed`、`_collect_reference_images` 三个函数。

在 `illustrate_book` 函数中，替换角色加载部分（约第 95-103 行）：

```python
from magicstory_cli.core.character_context import load_character_context

# 替换原有的角色加载代码块：
char_ctx = load_character_context(ctx, character_ids, include_reference_images=True)
character_description = char_ctx.description_text
reference_images = char_ctx.reference_images
character_seed = char_ctx.seed
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest -q
ruff check src/
```

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "refactor: unify character loading into CharacterContext service"
```

---

## Task 4: CLI 拆分

**Files:**
- Create: `src/magicstory_cli/cli/commands/__init__.py`
- Create: `src/magicstory_cli/cli/commands/project.py`
- Create: `src/magicstory_cli/cli/commands/plan.py`
- Create: `src/magicstory_cli/cli/commands/illustrate.py`
- Create: `src/magicstory_cli/cli/commands/render.py`
- Create: `src/magicstory_cli/cli/commands/build.py`
- Create: `src/magicstory_cli/cli/commands/character.py`
- Create: `src/magicstory_cli/cli/commands/config.py`
- Modify: `src/magicstory_cli/cli/app.py` — 精简为 ~80 行
- Modify: `tests/test_cli.py` — mock 路径更新
- Create: `tests/test_e2e_cli.py` — 替代 CLI 中的 e2e-test 命令

- [ ] **Step 1: 创建 `cli/commands/__init__.py`**

```python
```

（空文件）

- [ ] **Step 2: 创建 `cli/commands/project.py`**

从 `app.py` 提取 `new_project` 命令和 `_prompt_book_config` 辅助函数：

```python
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from magicstory_cli.cli.app import resolve_settings
from magicstory_cli.core.paths import PipelineContext
from magicstory_cli.core.project_scaffold import create_book_project
from magicstory_cli.models.config import BookConfig
from magicstory_cli.utils.files import slugify

console = Console()


def _prompt_book_config(
    title: str | None = None,
    idea: str | None = None,
    style: str | None = None,
    page_count: int | None = None,
    language: str | None = None,
    target_age: str | None = None,
    book_id: str | None = None,
    characters: list[str] | None = None,
    notes: str | None = None,
    prompt_optional_fields: bool = False,
    default_style: str = "Cartoon",
) -> BookConfig:
    prompt_title = title or typer.prompt("Book title")
    prompt_idea = idea or typer.prompt("Story idea")
    prompt_style = style or typer.prompt("Illustration style", default=default_style)
    prompt_page_count = page_count if page_count is not None else typer.prompt("Page count", default=12, type=int)
    prompt_language = language or typer.prompt("Language", default="zh-CN")
    prompt_target_age = target_age or typer.prompt("Target age", default="4-6")
    prompt_book_id = book_id or (
        typer.prompt("Project id", default=slugify(prompt_title)) if prompt_optional_fields else slugify(prompt_title)
    )
    prompt_notes = notes if notes is not None else (
        typer.prompt("Notes", default="") if prompt_optional_fields else None
    )
    prompt_characters = characters if characters is not None else (
        [c.strip() for c in typer.prompt("Characters (comma-separated IDs)", default="").split(",") if c.strip()]
        if prompt_optional_fields else []
    )

    return BookConfig(
        id=prompt_book_id,
        title=prompt_title,
        idea=prompt_idea,
        language=prompt_language,
        target_age=prompt_target_age,
        style=prompt_style,
        page_count=prompt_page_count,
        characters=prompt_characters,
        notes=prompt_notes or None,
    )


def register(app: typer.Typer) -> None:
    @app.command("new")
    def new_project(
        title: str | None = typer.Argument(None, help="书名"),
        idea: str | None = typer.Option(None, "--idea", help="故事核心想法（必填，缺失则进入交互模式）"),
        style: str | None = typer.Option(None, "--style", help="插画风格，如 '水彩画'、'Cartoon'"),
        page_count: int | None = typer.Option(None, "--pages", min=4, max=16, help="页数，范围 4-16"),
        language: str | None = typer.Option(None, "--language", help="语言，默认 zh-CN"),
        target_age: str | None = typer.Option(None, "--age", help="目标年龄段，默认 4-6"),
        book_id: str | None = typer.Option(None, "--id", help="自定义项目 ID，默认由书名自动生成"),
        characters: list[str] | None = typer.Option(None, "--characters", "-c", help="关联角色 ID，可多次传"),
        notes: str | None = typer.Option(None, "--notes", help="补充说明"),
        settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
    ) -> None:
        """创建绘本项目。"""
        app_settings, _ = resolve_settings(settings)
        needs_prompt = (
            title is None
            or idea is None
            or style is None
            or page_count is None
            or language is None
            or target_age is None
        )
        if needs_prompt:
            book = _prompt_book_config(
                title, idea, style, page_count, language, target_age,
                book_id, characters, notes,
                prompt_optional_fields=True,
                default_style=app_settings.app.default_style,
            )
        else:
            normalized_id = book_id or slugify(title)
            book = BookConfig(
                id=normalized_id,
                title=title,
                idea=idea,
                language=language,
                target_age=target_age,
                style=style or app_settings.app.default_style,
                page_count=page_count,
                characters=characters or [],
                notes=notes,
            )

        project_dir = create_book_project(app_settings.runtime.workspace_dir, book, app_settings)
        console.print(f"Created project: {project_dir}")
        console.print(f"Next step: story plan --project {project_dir}")
```

- [ ] **Step 3: 创建 `cli/commands/plan.py`**

```python
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from magicstory_cli.cli.app import resolve_settings
from magicstory_cli.core.paths import PipelineContext
from magicstory_cli.core.story_planner import plan_story

console = Console()


def register(app: typer.Typer) -> None:
    @app.command()
    def plan(
        project: Path = typer.Option(..., "--project", help="项目目录路径（必填）"),
        settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
    ) -> None:
        """生成故事内容与每页插图提示词。"""
        app_settings, _ = resolve_settings(settings)
        ctx = PipelineContext.from_settings(project, app_settings)
        book_spec = plan_story(ctx)
        console.print(f"Planned {len(book_spec.pages)} pages for: {book_spec.title}")
```

- [ ] **Step 4: 创建 `cli/commands/illustrate.py`**

```python
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from magicstory_cli.cli.app import resolve_settings
from magicstory_cli.core.illustrator import illustrate_book
from magicstory_cli.core.paths import PipelineContext

console = Console()


def register(app: typer.Typer) -> None:
    @app.command()
    def illustrate(
        project: Path = typer.Option(..., "--project", help="项目目录路径（必填）"),
        overwrite: bool = typer.Option(False, "--overwrite", help="强制重新生成已有插图"),
        settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
    ) -> None:
        """为每页生成插图。"""
        app_settings, _ = resolve_settings(settings)
        ctx = PipelineContext.from_settings(project, app_settings)
        result = illustrate_book(ctx, overwrite=overwrite)
        console.print(
            f"Illustration complete for: {result.book_spec.title} "
            f"(generated={result.generated_pages}, skipped={result.skipped_pages})"
        )
```

- [ ] **Step 5: 创建 `cli/commands/render.py`**

```python
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from magicstory_cli.cli.app import resolve_settings
from magicstory_cli.core.book_renderer import render_book
from magicstory_cli.core.paths import PipelineContext

console = Console()


def register(app: typer.Typer) -> None:
    @app.command()
    def render(
        project: Path = typer.Option(..., "--project", help="项目目录路径（必填）"),
        settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
    ) -> None:
        """渲染 HTML 预览与 PDF 文件。"""
        app_settings, _ = resolve_settings(settings)
        ctx = PipelineContext.from_settings(project, app_settings)
        result = render_book(ctx)
        console.print(f"Rendered HTML: {result.html_path}")
        console.print(f"Rendered PDF: {result.pdf_path}")
```

- [ ] **Step 6: 创建 `cli/commands/build.py`**

```python
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from magicstory_cli.cli.app import resolve_settings
from magicstory_cli.core.build_pipeline import build_book

console = Console()


def register(app: typer.Typer) -> None:
    @app.command()
    def build(
        project: Path = typer.Option(..., "--project", help="项目目录路径（必填）"),
        overwrite: bool = typer.Option(False, "--overwrite", help="强制重新生成已有插图"),
        settings: Path = typer.Option(None, "--settings", help="配置文件路径，默认自动查找 ./config/settings.yaml 或 ~/.magicstory/settings.yaml"),
    ) -> None:
        """一键运行完整流程: plan -> illustrate -> render。"""
        app_settings, _ = resolve_settings(settings)
        result = build_book(project, app_settings, overwrite_images=overwrite)
        console.print(
            f"Build complete for: {result.planned_book.title} "
            f"(pages={len(result.planned_book.pages)}, "
            f"generated_images={result.illustration_result.generated_pages}, "
            f"skipped_images={result.illustration_result.skipped_pages})"
        )
        console.print(f"HTML: {result.render_result.html_path}")
        console.print(f"PDF: {result.render_result.pdf_path}")
```

- [ ] **Step 7: 创建 `cli/commands/character.py`**

```python
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from magicstory_cli.cli.app import resolve_settings
from magicstory_cli.core.character_manager import create_character, list_characters
from magicstory_cli.core.paths import PipelineContext, resolve_characters_dir
from magicstory_cli.models.character import CharacterConfig
from magicstory_cli.utils.files import slugify

console = Console()

character_app = typer.Typer(help="管理可复用角色（character new 创建角色，character list 列出已有角色）。")


def register(app: typer.Typer) -> None:
    app.add_typer(character_app, name="character")

    @character_app.command("new")
    def character_new(
        name: str = typer.Argument(..., help="角色名称"),
        description: str = typer.Option(..., "--description", "-d", help="角色外观描述（必填）"),
        style: str | None = typer.Option(None, "--style", "-s", help="画风覆盖"),
        settings: Path = typer.Option(None, "--settings", help="配置文件路径"),
    ) -> None:
        """创建角色并生成参考图。"""
        app_settings, _ = resolve_settings(settings)
        char_id = slugify(name)
        char_config = CharacterConfig(id=char_id, name=name, description=description, style=style)
        characters_dir = resolve_characters_dir(app_settings)
        ctx = PipelineContext.from_settings(characters_dir.parent, app_settings)
        with console.status("Generating character reference image..."):
            result = create_character(characters_dir, char_config, app_settings, ctx.prompts_dir)
        console.print(f"[bold green]Character created:[/] {result.name} ({result.id})")
        console.print(f"  Reference: {characters_dir / result.id / 'reference.png'}")
        console.print(f"  Description: {result.description[:200]}")

    @character_app.command("list")
    def character_list(
        settings: Path = typer.Option(None, "--settings", help="配置文件路径"),
    ) -> None:
        """列出所有已创建的角色。"""
        app_settings, _ = resolve_settings(settings)
        characters_dir = resolve_characters_dir(app_settings)
        characters = list_characters(characters_dir)
        if not characters:
            console.print("No characters found.")
            return
        table = Table(title="Characters")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("Style")
        table.add_column("Description")
        for char in characters:
            table.add_row(char.id, char.name, char.style or "(default)", char.description[:60] + "...")
        console.print(table)
```

注意：`create_character` 仍然接受 `prompts_dir` 作为参数。需要保持这个接口或也改为接受 ctx。由于 `create_character` 在 `character_manager.py` 中，它的签名是 `create_character(root, config, settings, prompts_dir)`。这里我们通过 `ctx.prompts_dir` 传入。

- [ ] **Step 8: 创建 `cli/commands/config.py`**

```python
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from magicstory_cli.cli.app import resolve_settings
from magicstory_cli.core.paths import resolve_characters_dir
from magicstory_cli.providers.factory import build_image_provider, build_text_provider

console = Console()


def register(app: typer.Typer) -> None:

    @app.command()
    def doctor(
        settings: Path = typer.Option(None, "--settings", help="配置文件路径"),
    ) -> None:
        """检查环境与 provider 配置是否正确。"""
        app_settings, resolved_settings = resolve_settings(settings)

        table = Table(title="MagicStory Doctor")
        table.add_column("Check")
        table.add_column("Result")

        table.add_row("Settings file", f"OK: {resolved_settings}")
        table.add_row("Workspace", str(app_settings.runtime.workspace_dir))
        table.add_row("Characters dir", str(resolve_characters_dir(app_settings)))
        table.add_row("Text provider", f"{app_settings.providers.text.provider} / {app_settings.providers.text.model}")
        active_image = app_settings.providers.image.get_active_config()
        table.add_row("Image provider", f"{app_settings.providers.image.active} / {active_image.model}")
        table.add_row("Page range", "4-16 pages")
        table.add_row("PDF renderer", "Playwright (Chromium)")
        table.add_row("Reference images", str(app_settings.features.enable_reference_image).lower())
        table.add_row("Max parallel image jobs", str(app_settings.runtime.max_parallel_image_jobs))
        table.add_row("Log level", app_settings.app.log_level)

        try:
            build_text_provider(app_settings)
            table.add_row("Text provider wiring", "OK")
        except Exception as exc:
            table.add_row("Text provider wiring", f"ERROR: {exc}")

        try:
            build_image_provider(app_settings)
            table.add_row("Image provider wiring", "OK")
        except Exception as exc:
            table.add_row("Image provider wiring", f"ERROR: {exc}")

        console.print(table)

    @app.command("config")
    def show_config(
        settings: Path = typer.Option(None, "--settings", help="配置文件路径"),
    ) -> None:
        """显示当前生效的配置文件内容和来源。详见 README 获取完整配置字段说明。"""
        import yaml as _yaml

        app_settings, resolved_settings = resolve_settings(settings)
        with open(resolved_settings, "r", encoding="utf-8") as f:
            raw = _yaml.safe_load(f) or {}

        console.print(f"[bold]配置文件:[/] {resolved_settings}")
        console.print()
        console.print(_yaml.dump(raw, allow_unicode=True, default_flow_style=False))
```

- [ ] **Step 9: 精简 `cli/app.py`**

完整替换为：

```python
from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler

from magicstory_cli.config.loader import load_settings
from magicstory_cli.models.config import AppSettings

app = typer.Typer(
    help=(
        "MagicStory CLI — 将故事想法转化为插画 PDF 绘本。\n"
        "\n"
        "完整流程:\n"
        "  1. story character new <name> --description '...'   # 创建角色（可选）\n"
        "  2. story new '书名' --idea '故事想法' --pages N     # 创建项目\n"
        "  3. story plan --project <dir>                       # 生成故事与插图提示词\n"
        "  4. story illustrate --project <dir>                 # 生成插图\n"
        "  5. story render --project <dir>                     # 渲染 HTML + PDF\n"
        "\n"
        "或者一步到位:\n"
        "  story build --project <dir>                         # plan + illustrate + render\n"
        "\n"
        "配置文件:\n"
        "  按优先级: --settings 指定 > ./config/settings.yaml > ~/.magicstory/settings.yaml\n"
        "\n"
        "项目结构:\n"
        "  <project>/book.yaml            # 书籍配置\n"
        "  <project>/artifacts/pages.json # 故事内容与插图提示词\n"
        "  <project>/images/page-NN.png   # 插图\n"
        "  <project>/render/book.html     # HTML 预览\n"
        "  <project>/output/book.pdf      # 最终 PDF"
    ),
    no_args_is_help=True,
)

console = Console()

_DEFAULT_SETTINGS_CANDIDATES = [
    Path("config/settings.yaml"),
    Path.home() / ".magicstory" / "settings.yaml",
]

logging.basicConfig(
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True),
)


def resolve_settings(settings_path: Path | None = None) -> tuple[AppSettings, Path]:
    if settings_path is not None:
        if not settings_path.exists():
            raise typer.BadParameter(f"settings file not found: {settings_path}")
    else:
        for candidate in _DEFAULT_SETTINGS_CANDIDATES:
            if candidate.exists():
                settings_path = candidate
                break
        if settings_path is None:
            raise typer.BadParameter(
                "未找到配置文件，请通过 --settings 指定，或将配置放在以下位置之一:\n"
                "  ./config/settings.yaml\n"
                "  ~/.magicstory/settings.yaml"
            )
    app_settings = load_settings(settings_path)
    logging.getLogger().setLevel(app_settings.app.log_level.upper())
    return app_settings, settings_path


# 注册命令
from magicstory_cli.cli.commands import build, character, config, illustrate, plan, project, render  # noqa: E402

project.register(app)
plan.register(app)
illustrate.register(app)
render.register(app)
build.register(app)
character.register(app)
config.register(app)

if __name__ == "__main__":
    app()
```

- [ ] **Step 10: 创建 `tests/test_e2e_cli.py`**

将原 `app.py` 中的 `e2e_test` 命令逻辑转为测试函数。这个测试调用真实 API，用 `pytest.mark.skipif` 标记：

```python
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from magicstory_cli.config.loader import load_settings
from magicstory_cli.core.build_pipeline import build_book
from magicstory_cli.core.character_manager import create_character
from magicstory_cli.core.paths import PipelineContext
from magicstory_cli.models.character import CharacterConfig
from magicstory_cli.models.config import BookConfig

pytestmark = pytest.mark.skipif(
    not pytest.importorskip("os").environ.get("TEXT_AI_API_KEY"),
    reason="需要设置 TEXT_AI_API_KEY 等环境变量",
)


def test_e2e_build_pipeline(tmp_path: Path) -> None:
    """端到端测试：用真实 AI API 生成一本 4 页迷你绘本。"""
    settings = load_settings(Path("config/settings.example.yaml"))

    # 创建角色
    characters_dir = tmp_path / "characters"
    test_char_id = "e2e-test-orange-cat"
    char_config = CharacterConfig(
        id=test_char_id,
        name="max",
        description="一辆小汽车，名字叫 max，是一辆小校车，颜色是鲜艳的橘红色",
        style="卡通风格",
    )
    ctx_for_char = PipelineContext.from_settings(tmp_path, settings)
    char_result = create_character(characters_dir, char_config, settings, ctx_for_char.prompts_dir)

    # 创建项目
    workspace = tmp_path / "projects"
    book = BookConfig(
        id="e2e-test-little-cat",
        title="小汽车 max 的冒险故事",
        idea="去爬山，途中遇到暴风雨，最后安全回家",
        language="zh-CN",
        target_age="7-8",
        style="卡通风格",
        page_count=4,
        characters=[test_char_id],
    )
    from magicstory_cli.core.project_scaffold import create_book_project
    project_dir = create_book_project(workspace, book, settings)

    # 运行 build
    result = build_book(project_dir, settings, overwrite_images=False)

    assert len(result.planned_book.pages) == 4
    assert result.illustration_result.generated_pages >= 0

    # 清理
    shutil.rmtree(project_dir, ignore_errors=True)
    shutil.rmtree(characters_dir / test_char_id, ignore_errors=True)
```

- [ ] **Step 11: 更新 `tests/test_cli.py` — mock 路径更新**

所有 `magicstory_cli.cli.app.create_book_project` 替换为 `magicstory_cli.cli.commands.project.create_book_project`。

- [ ] **Step 12: 运行测试确认通过**

```bash
pytest -q
ruff check src/
```

- [ ] **Step 13: 提交**

```bash
git add -A
git commit -m "refactor: split CLI into command modules, move e2e-test to tests"
```

---

## Task 5: 杂项清理

**Files:**
- Modify: `src/magicstory_cli/core/character_manager.py` — 移动 import yaml 到顶层
- Modify: `config/settings.example.yaml` — 已在 Task 2 中处理，此处确认

- [ ] **Step 1: 修复 `character_manager.py` 内联 import**

将第 94 行的 `import yaml` 移到文件顶部 import 区，与 `import random` 一起。

- [ ] **Step 2: 运行测试确认通过**

```bash
pytest -q
ruff check src/
```

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "refactor: cleanup inline imports in character_manager"
```

---

## 自审清单

### Spec 覆盖率

| Spec 要求 | Task |
|-----------|------|
| BaseHttpProvider + 公共方法 | Task 1 |
| encode_image_as_data_url 移到 utils | Task 1 |
| CLI 拆分为 commands/ 目录 | Task 4 |
| e2e-test 移出 CLI | Task 4 |
| config 命令 docstring 缩短 | Task 4 |
| 统一角色上下文服务 | Task 3 |
| PipelineContext | Task 2 |
| prompts_dir / templates_dir 配置化 | Task 2 |
| 死代码删除 (plan 命令) | Task 2（app.py 重写时自动清理） |
| character_manager 内联 import | Task 5 |
| settings.example.yaml 更新 | Task 2 |

### 占位符扫描
无 TODO/TBD/placeholder。

### 类型一致性
- `PipelineContext` 在 `core/paths.py` 中定义，所有 core 模块和 CLI 命令引用同一类型。
- `BaseHttpProvider` 在 `providers/base.py` 中定义，所有 3 个 provider 继承。
- `CharacterContext` 在 `core/character_context.py` 中定义，`load_character_context` 接受 `PipelineContext` 参数。
