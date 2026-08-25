@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0.."

echo ========================================
echo   SnapSort Windows 打包脚本 (v3.6.0)
echo ========================================
echo.

REM 检查 Python
set PYTHON=python
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到 python，请先安装 Python 3.10+ 并添加到 PATH
    pause
    exit /b 1
)

for /f "tokens=*" %%a in ('%PYTHON% --version 2^>^&1') do echo ℹ️  Python: %%a

REM 创建/激活虚拟环境
if not exist "venv" (
    echo.
    echo 📦 创建虚拟环境...
    %PYTHON% -m venv venv
)

call .\venv\Scripts\activate.bat

REM 安装依赖
echo.
echo 📦 安装依赖...
python -m pip install -q --upgrade pip
if errorlevel 1 (
    echo ❌ pip 更新失败
    pause
    exit /b 1
)

python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo ❌ 程序依赖安装失败
    pause
    exit /b 1
)

python -m pip install -q pyinstaller
if errorlevel 1 (
    echo ❌ PyInstaller 安装失败
    pause
    exit /b 1
)

python -c "import customtkinter, requests, PIL, pillow_heif, openpyxl, tkinterdnd2"
if errorlevel 1 (
    echo ❌ 依赖校验失败，停止打包
    pause
    exit /b 1
)

echo ✅ 依赖安装完成

REM 清理旧构建
echo.
echo 🧹 清理旧构建...
if exist build rmdir /s /q build
if exist dist\SnapSort rmdir /s /q dist\SnapSort

REM 使用 spec 文件打包
echo.
echo 🔨 开始打包（使用 PyInstaller spec）...
pyinstaller --noconfirm packaging\snapsort.spec

if errorlevel 1 (
    echo.
    echo ❌ 打包失败！
    echo 请检查上方错误信息
    pause
    exit /b 1
)

if not exist "dist\SnapSort\SnapSort.exe" (
    echo ❌ 打包命令结束，但未找到 SnapSort.exe
    pause
    exit /b 1
)

echo.
echo ========================================
echo   ✅ 打包完成！
echo ========================================
echo.
echo 📁 输出目录: dist\SnapSort\
echo 📁 可执行文件: dist\SnapSort\SnapSort.exe
echo.
echo 💡 分发方式:
echo    1. 将 dist\SnapSort 整个文件夹打包为 ZIP
echo    2. 用户解压后双击 SnapSort.exe 即可运行
echo    3. 用户需另外安装 Ollama 并下载模型
echo.
echo 💡 注意: 界面不需要 Ollama 即可打开
echo    仅自动分类/AI工具需要 Ollama 运行
echo.
pause
