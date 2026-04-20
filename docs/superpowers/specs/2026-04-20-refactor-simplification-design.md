# MagicStory CLI 重构设计

日期: 2026-04-20
目标: 降低维护成本、提升可扩展性、全面瘦身 — 综合权衡

## 1. Provider 层重构

### 问题
- `base.py` 仅有纯 ABC，零公共实现
- 3 个 provider 重复: API key 获取、httpx 客户端创建、请求/响应日志
- `_encode_image_as_data_url` 在 minimax.py 和 volcengine.py 中完全相同

### 方案

新增 `BaseHttpProvider` 基类到 `providers/base.py`，提供:
- `_get_api_key()` — 统一从环境变量获取，缺失则抛 RuntimeError
- `_http_client()` — 创建配置好的 httpx.Client (timeout + retry transport)
- `_log_request(url, model, **extra)` — 统一请求日志
- `_log_response(status_code, model, **extra)` — 统一响应日志
- `_write_image(output_path, image_bytes)` — 统一 base64 解码 + 写文件 + 创建目录

`_encode_image_as_data_url` 移入 `utils/files.py`。

ABC 接口 (`TextProvider.generate_structured_text` / `ImageProvider.generate_image`) 签名不变。

### 文件变更
- `providers/base.py` — 新增 `BaseHttpProvider`
- `providers/openai_compatible.py` — 继承 `BaseHttpProvider`，删除重复逻辑
- `providers/minimax.py` — 继承 `BaseHttpProvider`，删除重复逻辑和 `_encode_image_as_data_url`
- `providers/volcengine.py` — 继承 `BaseHttpProvider`，删除重复逻辑和 `_encode_image_as_data_url`
- `utils/files.py` — 新增 `encode_image_as_data_url`
- `providers/factory.py` — 不变

## 2. CLI 拆分 + e2e 移出

### 问题
- `app.py` 521 行，8 个命令 + 配置解析 + 用户交互混杂
- `e2e-test` 是测试命令，不该出现在生产 CLI
- `config` 命令的 help docstring 有 55 行

### 方案

```
cli/
  app.py                  # Typer app 实例 + resolve_settings() + import 注册 (~80 行)
  commands/
    __init__.py
    project.py            # new 命令 + _prompt_book_config()
    plan.py               # plan 命令
    illustrate.py         # illustrate 命令
    render.py             # render 命令
    build.py              # build 命令
    character.py          # character new / list
    config.py             # config / doctor 命令
```

`e2e-test` 命令从 CLI 移除，改为 `tests/test_e2e_cli.py`（调用 core 层 API）。

`config` 命令的 docstring 缩短为一句话 + 指向 README。

### 文件变更
- `cli/app.py` — 精简到 ~80 行
- `cli/commands/` — 新目录，7 个命令文件
- `tests/test_e2e_cli.py` — 新增，替代 CLI 中的 e2e-test 命令

## 3. 统一角色上下文服务

### 问题
- `story_planner.py` 第 42-52 行和 `illustrator.py` 第 34-70 行各自遍历角色 ID、加载角色、拼接信息
- 两处逻辑高度相似但独立实现

### 方案

新增 `core/character_context.py`:

```python
@dataclass
class CharacterContext:
    description_text: str          # "name: desc; name2: desc2"
    reference_images: list[Path]
    seed: int | None

def load_character_context(
    settings: AppSettings,
    character_ids: list[str],
    include_reference_images: bool = False,
) -> CharacterContext:
    ...
```

- `story_planner.py` 用 `load_character_context(settings, book.characters).description_text`
- `illustrator.py` 用 `load_character_context(settings, book.characters, include_reference_images=True)` 获取全部字段
- `character_manager.py` 中的 `load_character` / `list_characters` / `create_character` 不变

### 文件变更
- `core/character_context.py` — 新增
- `core/story_planner.py` — 删除内联角色加载，改用 `load_character_context`
- `core/illustrator.py` — 删除 `_build_character_description` / `_get_character_seed` / `_collect_reference_images`，改用 `load_character_context`

## 4. Pipeline 上下文 + 路径配置化

### 问题
- `PROMPTS_DIR` / `TEMPLATES_DIR` 通过 `__file__` 硬编码，每次调用 core 函数要透传
- `resolve_project_paths()` 在 story_planner、illustrator、book_renderer 各自调用
- core 函数的 `settings` + `prompts_dir` + `templates_dir` 参数组合重复

### 方案

1. `prompts_dir` 和 `templates_dir` 加入 `RuntimeConfig`:

```python
class RuntimeConfig(BaseModel):
    ...
    prompts_dir: Path | None = None
    templates_dir: Path | None = None
```

默认值通过 `model_validator` 从包路径解析（等价于现有 `__file__` 逻辑），用户可在 settings.yaml 中覆盖。

2. 新增 `PipelineContext`:

```python
@dataclass
class PipelineContext:
    settings: AppSettings
    paths: ProjectPaths
    prompts_dir: Path
    templates_dir: Path
    characters_dir: Path

    @classmethod
    def from_settings(cls, project_dir: Path, settings: AppSettings) -> PipelineContext:
        ...
```

core 函数签名统一为 `(ctx: PipelineContext, ...)`。

### 文件变更
- `models/config.py` — `RuntimeConfig` 新增 `prompts_dir` / `templates_dir` 字段 + `model_validator`
- `core/paths.py` — 新增 `PipelineContext` 数据类
- `core/story_planner.py` — 签名改为 `(ctx: PipelineContext)`
- `core/illustrator.py` — 签名改为 `(ctx: PipelineContext, overwrite: bool)`
- `core/book_renderer.py` — 签名改为 `(ctx: PipelineContext)`
- `core/build_pipeline.py` — 构造 `PipelineContext`，传给各阶段
- CLI 命令 — 构造 `PipelineContext` 传给 core

## 5. 杂项清理

| 项目 | 改动 |
|------|------|
| `app.py:380-381` 死代码 | 删除 `plan` 命令中未使用的 `resolve_characters_dir()` 调用 |
| `character_manager.py` 内联 `import yaml` | 改为顶层 import |
| `config/settings.example.yaml` | 新增 `prompts_dir` / `templates_dir` 字段说明 |

## 不在范围内

- 测试补全（可作为后续独立任务）
- 模板/渲染逻辑变更
- 新增功能

## 实施顺序

1. Provider 层重构（独立，风险低）
2. Pipeline 上下文 + 路径配置化（影响所有 core 函数签名）
3. 统一角色上下文服务（依赖第 2 步的 PipelineContext）
4. CLI 拆分（依赖第 2、3 步完成后的 core API）
5. 杂项清理（随时可做）
