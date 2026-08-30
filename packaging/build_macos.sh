#!/bin/bash
# SnapSort macOS 打包脚本 (v3.7.0)
# 生成 SnapSort.app，双击即可运行

set -e

cd "$(dirname "$0")/.."

echo "========================================"
echo "  SnapSort macOS 打包脚本 (v3.7.0)"
echo "========================================"
echo

# 检查 Python
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" &>/dev/null; then
    echo "❌ 找不到 Python，请先安装 Python 3.10+"
    exit 1
fi

echo "ℹ️  Python: $($PYTHON --version 2>&1)"

# 安装依赖
echo
echo "📦 安装依赖..."
$PYTHON -m pip install -q --upgrade pip
$PYTHON -m pip install -q -r requirements.txt
$PYTHON -m pip install -q pyinstaller
$PYTHON -c "import customtkinter, requests, PIL, pillow_heif, openpyxl, tkinterdnd2"

# 清理旧构建
echo
echo "🧹 清理旧构建..."
rm -rf build dist/SnapSort.app dist/SnapSort

# 打包
echo
echo "🔨 开始打包..."
$PYTHON -m PyInstaller --noconfirm packaging/snapsort.spec

if [ ! -d "dist/SnapSort.app" ]; then
    echo "❌ 打包命令结束，但未找到 dist/SnapSort.app"
    exit 1
fi

echo
echo "========================================"
echo "  ✅ 打包完成！"
echo "========================================"
echo
echo "📁 输出目录: dist/SnapSort.app"
echo "📁 可执行文件: dist/SnapSort.app/Contents/MacOS/SnapSort"
echo
echo "💡 双击 SnapSort.app 即可运行"
echo "💡 分发: 将 dist/SnapSort.app 压缩为 zip 发给别人"
echo
