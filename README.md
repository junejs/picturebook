# MagicStory CLI

`MagicStory CLI` 是一个基于 Python 的命令行绘本生成程序，用来把故事创意转换为完整绘本项目，包括：

- 分页故事文本
- 每页插图描述
- AI 生成插图
- 最终绘本 HTML / PDF

当前项目目标是先稳定支持单机 CLI 工作流，不提供 UI。

## 当前能力

目前已经实现：

- `story new`：创建绘本项目
- `story plan`：生成分页故事文本和插图描述
- `story illustrate`：根据每页 prompt 调用图片模型出图
- `story render`：把图片和文本排版为正式绘本 HTML / PDF
- `story build`：串联完整流程
- `story character new`：创建角色参考图（文生图 + Vision 分析）
- `story character list`：列出所有可用角色
- 创建项目时可指定角色（`--characters`），实现角色一致性
- 单元测试：覆盖配置校验、分页校验、续跑逻辑、渲染、build orchestration

## 角色系统

角色（Character）是全局共享的可复用资源，存储在 `characters/` 目录下。创建角色时会自动：

1. 根据描述文生图，生成角色参考图
2. 使用 Vision 模型分析参考图，提取精准的角色视觉描述
3. 生成绘本时，角色描述注入 prompt + 参考图通过 API 传入，双重保障一致性

### 创建角色

```bash
uv run story character new "小明" \
  -d "一个6岁的小男孩，穿蓝色背带裤，棕色短发，大眼睛"
```

### 查看角色列表

```bash
uv run story character list
```

### 在项目中使用角色

```bash
uv run story new "小明的冒险" \
  --idea "小明在森林中发现了一个神奇的秘密" \
  --characters xiaoming \
  --pages 8
```

也可以在交互模式下指定角色 ID（逗号分隔）。

## 技术选型

- Python 3.12+
- `uv`：依赖管理与命令执行
- `Typer`：CLI
- `Pydantic v2`：配置和数据结构校验
- `Jinja2`：prompt / HTML 模板
- `WeasyPrint`：HTML 转 PDF
- Provider 抽象：
  - 文本模型：`OpenAI-compatible`
  - 图片模型：`MiniMax`
  - 视觉模型：`OpenAI-compatible`（用于角色参考图分析）

## 目录结构

```text
story/
├── config/
│   └── settings.example.yaml
├── prompts/
│   ├── story_plan.jinja2
│   ├── page_content.jinja2
│   ├── illustration_prompt.jinja2
│   ├── character_description_extraction.jinja2
│   └── minimax/
│       ├── character_generation.jinja2
│       └── illustration_generation.jinja2
├── src/magicstory_cli/
│   ├── cli/
│   ├── config/
│   ├── core/
│   ├── models/
│   ├── providers/
│   ├── rendering/
│   └── utils/
├── templates/
│   └── book.html.jinja2
├── tests/
├── pyproject.toml
└── README.md
```

### 角色目录

角色数据独立于项目，全局共享：

```text
characters/<character-id>/
├── character.yaml
└── reference.png
```

### 绘本项目目录

绘本项目默认放在 `projects/` 下：

```text
projects/<book-id>/
├── book.yaml
├── artifacts/
│   ├── manifest.json
│   ├── plan.raw.json
│   ├── plan.meta.json
│   ├── pages.json
│   ├── illustration.meta.json
│   └── render.meta.json
├── images/
│   ├── page-01.png
│   └── ...
├── render/
│   └── book.html
└── output/
    └── book.pdf
```

## 环境准备

### 1. 安装依赖

```bash
uv sync
```

### 2. 初始化配置

```bash
cp config/settings.example.yaml config/settings.yaml
```

### 3. 配置环境变量

至少需要：

```bash
export TEXT_AI_API_KEY=...
export IMAGE_AI_API_KEY=...
```

如果要使用角色功能（Vision 分析），还需要：

```bash
export VISION_AI_API_KEY=...
```

如果你的文本模型或视觉模型是兼容 OpenAI Chat Completions 的网关，也可以在 `config/settings.yaml` 里改 `base_url` 和 `model`。

### 4. 环境检查

```bash
uv run story doctor
```

## 配置文件

主配置文件是 `config/settings.yaml`。

示例：

```yaml
providers:
  text:
    provider: openai-compatible
    model: gpt-4.1-mini
    api_key_env: TEXT_AI_API_KEY
    base_url: null
    timeout_seconds: 300
    max_retries: 2
  image:
    provider: minimax
    model: image-01
    api_key_env: IMAGE_AI_API_KEY
    base_url: https://api.minimaxi.com
    timeout_seconds: 300
    max_retries: 2
  vision:
    provider: openai-compatible
    model: gpt-4.1-mini
    api_key_env: VISION_AI_API_KEY
    base_url: null
    timeout_seconds: 300
    max_retries: 2

render:
  page_size: 210mmx210mm
  include_cover: true
  text_layout: bottom-band
  body_font: Noto Sans SC
  heading_font: Noto Serif SC
  dpi: 144

runtime:
  workspace_dir: projects
  characters_dirname: characters
  artifacts_dirname: artifacts
  images_dirname: images
  output_dirname: output
  render_dirname: render
  max_parallel_image_jobs: 1

features:
  enable_reference_image: false

app:
  log_level: info
```

注意：

- 绘本页数限制为 `4-16`
- 默认绘本尺寸为 `210mm x 210mm`
- 默认艺术风格为 `picture book`，适用于角色生成和插图生成
- 当前图片 provider 只实现了 `MiniMax`
- 当前文本 provider 只实现了 `OpenAI-compatible`
- 当前视觉 provider 只实现了 `OpenAI-compatible`
- `runtime.max_parallel_image_jobs` 控制 `story illustrate` / `story build` 的并行出图个数

## 快速开始

### 1. 创建角色（可选）

```bash
uv run story character new "小明" \
  -d "一个6岁的小男孩，穿蓝色背带裤，棕色短发，大眼睛"
```

### 2. 创建一本新书

```bash
uv run story new "月亮花园" \
  --idea "一只小兔子在月光下寻找会发光的花" \
  --style "warm watercolor picture book" \
  --pages 8
```

如果之前创建了角色，可以通过 `--characters` 指定：

```bash
uv run story new "月亮花园" \
  --idea "一只小兔子在月光下寻找会发光的花" \
  --characters xiaoming \
  --pages 8
```

如果你不想一次性把参数写完，可以直接运行 `uv run story new`，命令会按步骤逐个询问标题、故事设定、风格和页数等信息。

### 3. 生成分页文本和插图描述

```bash
uv run story plan --project projects/yue-liang-hua-yuan
```

### 4. 生成插图

```bash
uv run story illustrate --project projects/yue-liang-hua-yuan
```

如果要强制重出图片：

```bash
uv run story illustrate --project projects/yue-liang-hua-yuan --overwrite
```

### 5. 生成正式绘本 PDF

```bash
uv run story render --project projects/yue-liang-hua-yuan
```

### 6. 一条命令完整执行

```bash
uv run story build --project projects/yue-liang-hua-yuan
```

## 推荐协作方式

建议团队成员按下面的原则协作：

- `prompts/` 只改提示词，不混入业务逻辑
- `providers/` 只负责模型调用，不负责流程调度
- `core/` 负责真正的 pipeline 编排
- `templates/` 只负责排版与视觉结构
- `tests/` 必须跟着功能改动一起更新

如果要改一个流程节点，优先同时检查：

- 对应的 schema 是否需要更新
- 对应 artifact 是否会变更
- 对应测试是否需要新增或修正
- README 中相关命令或配置是否需要同步

## 产物说明

### `book.yaml`

每本书的输入配置，通常由 `story new` 生成，也允许人工修改。

### `character.yaml`

每个角色的配置，包含名称、描述、Vision 分析后的精准描述和风格。

### `artifacts/pages.json`

整个流水线最核心的中间产物，里面包含：

- 绘本元信息
- 每页故事文本
- 每页插图 prompt
- 每页图片路径

如果人工要调整某一页，优先修改这里。

### `render/book.html`

PDF 渲染前的排版结果。
当 PDF 样式有问题时，优先检查这个文件，而不是先怀疑模型输出。

## 测试

运行全部测试：

```bash
pytest -q
```

当前测试覆盖：

- 配置约束
- story planning payload 校验
- 图片续跑与回写
- HTML 渲染
- render 产物生成
- build 全流程 orchestration

原则：

- 每新增一个稳定功能，至少补一组不依赖外部 API 的测试
- provider 的真实联调优先做成集成测试，不污染单元测试稳定性

## 已知限制

- 当前还没有复杂的版式模板切换
- 当前 `build` 会重新执行 `plan`，不会自动判断"文本是否无需重生"
- 当前没有数据库，也没有多人并发写同一本书的保护
- `WeasyPrint` 在不同机器上可能依赖额外系统库

## 后续建议

建议优先继续做这几项：

1. `build` 的断点续跑策略和更细的跳过逻辑
2. provider 级别重试、超时和错误分类
3. 更正式的绘本版式模板
4. 集成测试和示例项目数据

## 开发命令

```bash
uv sync
uv run story --help
uv run story doctor
pytest -q
```

## 代码入口

- CLI 入口：`src/magicstory_cli/cli/app.py`
- 角色管理：`src/magicstory_cli/core/character_manager.py`
- 故事规划：`src/magicstory_cli/core/story_planner.py`
- 插图生成：`src/magicstory_cli/core/illustrator.py`
- PDF 渲染：`src/magicstory_cli/core/book_renderer.py`
- 全流程编排：`src/magicstory_cli/core/build_pipeline.py`
