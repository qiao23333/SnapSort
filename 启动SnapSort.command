#!/bin/bash
# SnapSort 3.0 Mac 启动器（双击运行）
# 自动定位项目目录、设置 Tcl/Tk 环境、启动应用

SCRIPT_SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SCRIPT_SOURCE" ]; do
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
    SCRIPT_SOURCE="$(readlink "$SCRIPT_SOURCE")"
    [[ $SCRIPT_SOURCE != /* ]] && SCRIPT_SOURCE="$SCRIPT_DIR/$SCRIPT_SOURCE"
done
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# 优先使用 WorkBuddy 管理 Python，其次系统 python3
PYTHON=""
for p in "python3" "python"; do
    if command -v "$p" &>/dev/null; then
        if "$p" -c "import tkinter" 2>/dev/null; then
            PYTHON="$p"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    osascript -e 'display dialog "找不到带 tkinter 的 Python，请安装 Python 3.10+" buttons {"确定"} default button "确定" with icon stop'
    exit 1
fi

PYTHON_VERSION=$($PYTHON --version 2>&1)
echo "Python: $PYTHON_VERSION"

# venv 或系统 Python 可能找不到 Tcl/Tk 库文件，这里显式导出路径
TCL_TK_DIR="$($PYTHON -c 'import sys, os; print(os.path.join(sys.base_prefix, \"lib\"))' 2>/dev/null)"
if [ -d "$TCL_TK_DIR/tcl9.0" ] && [ -d "$TCL_TK_DIR/tk9.0" ]; then
    export TCL_LIBRARY="$TCL_TK_DIR/tcl9.0"
    export TK_LIBRARY="$TCL_TK_DIR/tk9.0"
elif [ -d "$TCL_TK_DIR/tcl8.6" ] && [ -d "$TCL_TK_DIR/tk8.6" ]; then
    export TCL_LIBRARY="$TCL_TK_DIR/tcl8.6"
    export TK_LIBRARY="$TCL_TK_DIR/tk8.6"
fi

# 确保依赖已安装
echo "检查依赖..."
$PYTHON -c "import customtkinter, requests, PIL, pillow_heif" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "正在安装依赖..."
    $PYTHON -m pip install "customtkinter>=5.2.2,<6.0.0" requests Pillow pillow-heif openpyxl
fi

# 启动应用
echo "启动 SnapSort 3.0..."
$PYTHON app.py
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "程序异常退出（错误码：$EXIT_CODE），请查看上方错误信息。"
    read -n 1 -s -r -p "按任意键关闭..."
fi
