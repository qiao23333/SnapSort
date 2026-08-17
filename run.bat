@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
REM SnapSort 3.0 Windows 启动脚本（源码模式）
REM 推荐使用 packaging\build_windows.bat 打包成 exe 后分发
REM 此脚本需要用户已安装 Python

cd /d "%~dp0"

REM 尝试找到 Python
set PYTHON=
for %%p in (python python3 py) do (
    %%p --version >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON=%%p
        goto found_python
    )
)

echo.
echo ❌ 未找到 Python，请先安装 Python 3.10+
echo 下载地址: https://www.python.org/downloads/
echo 安装时请勾选 "Add Python to PATH"
echo.
pause
exit /b 1

:found_python
for /f "tokens=*" %%a in ('%PYTHON% --version 2^>^&1') do echo ℹ️  Python: %%a

REM 检查 tkinter
%PYTHON% -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ❌ 当前 Python 未安装 tkinter
    echo 请重新安装 Python 并勾选 "tcl/tk and IDLE"
    pause
    exit /b 1
)
echo ✅ tkinter 已就绪

REM 安装依赖
echo ℹ️  检查依赖...
%PYTHON% -c "import customtkinter" >nul 2>&1
if errorlevel 1 (
    echo 📦 首次运行，安装依赖...
    %PYTHON% -m pip install customtkinter requests Pillow pillow-heif openpyxl
    if errorlevel 1 (
        echo ❌ 依赖安装失败，请手动运行:
        echo    pip install customtkinter requests Pillow pillow-heif openpyxl
        pause
        exit /b 1
    )
)

REM 拖拽支持（可选，失败不阻塞）
%PYTHON% -c "import tkinterdnd2" >nul 2>&1
if errorlevel 1 (
    echo ℹ️  安装拖拽支持（可选）...
    %PYTHON% -m pip install tkinterdnd2 >nul 2>&1
)
echo ✅ 依赖已就绪

REM 启动应用
echo.
echo 🚀 正在启动 SnapSort 素材分类器...
echo ====================================
%PYTHON% app.py
if errorlevel 1 (
    echo.
    echo ❌ 程序异常退出
    echo 如果是模型相关错误，请确保 Ollama 已安装并运行
    pause
)
