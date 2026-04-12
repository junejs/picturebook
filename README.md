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
- 单元测试：覆盖配置校验、分页校验、续跑逻辑、渲染、build orchestration

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

## 目录结构

```text
story/
├── config/
│   └── settings.example.yaml
├── prompts/
│   ├── story_plan.jinja2
│   ├── page_content.jinja2
│   └── illustration_prompt.jinja2
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

运行后生成的绘本项目默认放在 `projects/` 下：

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

可选：

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
- 当前图片 provider 只实现了 `MiniMax`
- 当前文本 provider 只实现了 `OpenAI-compatible`
- `vision` 配置已经预留，但当前主流程还没有实际消费它
- `enable_reference_image` 和 `app_url` 也已预留，后面做角色参考图时会用到

## 快速开始

### 1. 创建一本新书

```bash
uv run story new "月亮花园" \
  --idea "一只小兔子在月光下寻找会发光的花" \
  --style "warm watercolor picture book" \
  --pages 8
```

### 2. 生成分页文本和插图描述

```bash
uv run story plan --project projects/yue-liang-hua-yuan
```

### 3. 生成插图

```bash
uv run story illustrate --project projects/yue-liang-hua-yuan
```

如果要强制重出图片：

```bash
uv run story illustrate --project projects/yue-liang-hua-yuan --overwrite
```

### 4. 生成正式绘本 PDF

```bash
uv run story render --project projects/yue-liang-hua-yuan
```

### 5. 一条命令完整执行

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

- 当前还没有角色参考图能力
- 当前还没有复杂的版式模板切换
- 当前 `build` 会重新执行 `plan`，不会自动判断“文本是否无需重生”
- 当前没有数据库，也没有多人并发写同一本书的保护
- `WeasyPrint` 在不同机器上可能依赖额外系统库

## 后续建议

建议优先继续做这几项：

1. `build` 的断点续跑策略和更细的跳过逻辑
2. provider 级别重试、超时和错误分类
3. 更正式的绘本版式模板
4. 角色参考图和角色一致性能力
5. 集成测试和示例项目数据

## 开发命令

```bash
uv sync
uv run story --help
uv run story doctor
pytest -q
```

## 代码入口

- CLI 入口：`src/magicstory_cli/cli/app.py`
- 故事规划：`src/magicstory_cli/core/story_planner.py`
- 插图生成：`src/magicstory_cli/core/illustrator.py`
- PDF 渲染：`src/magicstory_cli/core/book_renderer.py`
- 全流程编排：`src/magicstory_cli/core/build_pipeline.py`
