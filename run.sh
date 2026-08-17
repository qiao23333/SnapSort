#!/bin/bash
# SnapSort 3.0 Mac/Linux 启动脚本
# 自动查找可用的 Python，安装依赖，启动应用

# 清除可能的环境变量污染（IDE/虚拟环境可能设置了 PYTHONHOME/PYTHONPATH）
unset PYTHONHOME PYTHONPATH

SCRIPT_SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SCRIPT_SOURCE" ]; do
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
    SCRIPT_SOURCE="$(readlink "$SCRIPT_SOURCE")"
    [[ $SCRIPT_SOURCE != /* ]] && SCRIPT_SOURCE="$SCRIPT_DIR/$SCRIPT_SOURCE"
done
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# 查找可用的 Python（优先用 Tk 8.6+ 的版本）
PYTHON=""
for p in "python3" "python" "/usr/local/bin/python3" "/opt/homebrew/bin/python3" "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3" "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3" "/usr/bin/python3"; do
    if command -v "$p" &>/dev/null || [ -x "$p" ]; then
        if "$p" -c "import tkinter" 2>/dev/null; then
            # 检查 Tk 版本 >= 8.6（customtkinter 必需）
            TK_VER=$("$p" -c "import tkinter; print(tkinter.TkVersion)" 2>/dev/null)
            if [ -n "$TK_VER" ]; then
                # 比较版本号
                TK_MAJOR=$(echo "$TK_VER" | cut -d. -f1)
                if [ "$TK_MAJOR" -ge 8 ] && [ "$(echo "$TK_VER" | cut -d. -f2)" -ge 6 ]; then
                    PYTHON="$p"
                    break
                elif [ "$TK_MAJOR" -ge 9 ]; then
                    PYTHON="$p"
                    break
                fi
            fi
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ 找不到带 Tk 8.6+ 的 Python"
    echo ""
    echo "当前系统 Python 的 Tk 版本太旧，customtkinter 需要 Tk 8.6+。"
    echo ""
    echo "解决方案（选一个）："
    echo "  1. 从 python.org 下载安装 Python 3.10+（自带 Tk 8.6）"
    echo "     → https://www.python.org/downloads/mac-osx/"
    echo "  2. 用 Homebrew 安装：brew install python@3.11"
    echo ""
    read -n 1 -s -r -p "按任意键退出..."
    exit 1
fi

PYTHON_VERSION=$($PYTHON --version 2>&1)
echo "ℹ️  Python: $PYTHON_VERSION"
echo "✅ tkinter 已就绪"

if [ ! -f "app.py" ]; then
    echo "❌ 找不到 app.py"
    exit 1
fi

# 检查并安装依赖
echo "ℹ️  检查依赖..."
NEED_INSTALL=0
$PYTHON -c "import customtkinter" 2>/dev/null
if [ $? -ne 0 ]; then
    NEED_INSTALL=1
else
    # 检查 customtkinter 版本是否兼容（6.0+ 不兼容）
    CT_VER=$($PYTHON -c "import customtkinter; print(customtkinter.__version__)" 2>/dev/null)
    if echo "$CT_VER" | grep -qE "^6\."; then
        echo "⚠️  检测到 customtkinter $CT_VER（不兼容），正在降级到 5.x..."
        NEED_INSTALL=1
    fi
fi
if [ "$NEED_INSTALL" -ne 0 ]; then
    echo "📦 正在安装/更新依赖..."
    echo "   安装内容：customtkinter requests Pillow pillow-heif openpyxl"
    echo ""
    $PYTHON -m pip install "customtkinter>=5.2.2,<6.0.0" requests Pillow pillow-heif openpyxl
    INSTALL_EXIT=$?
    if [ $INSTALL_EXIT -ne 0 ]; then
        echo ""
        echo "❌ 依赖安装失败（错误码：$INSTALL_EXIT）"
        echo ""
        echo "可能原因："
        echo "  1. 网络连接问题 → 检查网络后重试"
        echo "  2. pip 权限不足 → 尝试：$PYTHON -m pip install --user customtkinter requests Pillow pillow-heif openpyxl"
        echo "  3. pip 版本过旧 → 尝试：$PYTHON -m pip install --upgrade pip"
        echo ""
        read -n 1 -s -r -p "按任意键退出..."
        exit $INSTALL_EXIT
    fi
    # 安装后再次验证
    $PYTHON -c "import customtkinter" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "❌ 依赖安装后仍无法导入 customtkinter"
        echo "   请手动执行：$PYTHON -m pip install customtkinter"
        read -n 1 -s -r -p "按任意键退出..."
        exit 1
    fi
fi

# 拖拽支持（可选依赖，失败不阻塞启动）
$PYTHON -c "import tkinterdnd2" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "ℹ️  安装拖拽支持（tkinterdnd2，可选）..."
    $PYTHON -m pip install tkinterdnd2 >/dev/null 2>&1
    $PYTHON -c "import tkinterdnd2" 2>/dev/null \
        && echo "✅ 拖拽就绪：可把文件夹直接拖进窗口" \
        || echo "ℹ️  拖拽未启用（不影响其他功能）"
fi
echo "✅ 依赖已就绪"

# 诊断输出
CTK_VER=$($PYTHON -c "import customtkinter; print(customtkinter.__version__)" 2>/dev/null)
echo "   Python路径: $(command -v $PYTHON)"
echo "   customtkinter: $CTK_VER"

echo ""
echo "🚀 正在启动 SnapSort 3.0..."
echo "===================================="
$PYTHON app.py

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ 程序异常退出（错误码：$EXIT_CODE）"
    read -n 1 -s -r -p "按任意键退出..."
    exit $EXIT_CODE
fi
