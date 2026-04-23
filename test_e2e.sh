#!/usr/bin/env bash
# E2E 端到端测试：创建角色 + 生成一本 4 页迷你绘本
set -euo pipefail

BOOK_ID="e2e-test-adventure"
CHAR_ID="max"
PROJECT_DIR="projects/$BOOK_ID"

echo "=== E2E 测试开始 ==="

# 清理旧数据
rm -rf "$PROJECT_DIR" "characters/$CHAR_ID"

# 1. 创建角色（名称 max → slugify 后 ID 也是 max）
echo "--- 创建角色 ---"
uv run story character new "max" \
  --description "一辆小汽车，名字叫 max，是一辆小校车，颜色是鲜艳的橘红色，车顶有一个小小的行李架，前脸有 max 字样，车窗是圆形的，像眼睛一样，车头有一个微笑的格栅，整体造型可爱又充满冒险精神" \
  --style "卡通风格"

# 2. 创建项目（输出到 projects/e2e-test-adventure）
echo "--- 创建项目 ---"
uv run story new "$BOOK_ID" \
  --idea "去爬山，途中遇到暴风雨，最后安全回家" \
  --style "卡通风格" \
  --pages 4 \
  --age "7-8" \
  --language zh-CN \
  --characters "$CHAR_ID"

# 3. 生成故事
echo "--- 生成故事内容 ---"
uv run story plan --project "$PROJECT_DIR"

# 4. 生成插图
echo "--- 生成插图 ---"
uv run story illustrate --project "$PROJECT_DIR"

# 5. 渲染 HTML + PDF
echo "--- 渲染 ---"
uv run story render --project "$PROJECT_DIR"

echo ""
echo "=== E2E 测试完成 ==="
echo "HTML: $PROJECT_DIR/render/book.html"
echo "PDF:  $PROJECT_DIR/output/book.pdf"
echo "清理: rm -rf $PROJECT_DIR characters/$CHAR_ID"
