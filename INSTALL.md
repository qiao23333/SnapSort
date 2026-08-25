# 安装指南

SnapSort 是一款完全本地运行的 AI 素材整理桌面工具。AI 功能依赖 [Ollama](https://ollama.com)，其余工具（格式转换、查重、批量处理等）无需任何 AI 环境即可使用。

## 前置条件

| 组件 | 要求 | 说明 |
|------|------|------|
| Python | 3.9+（推荐 3.11/3.12） | 自带 Tk 8.6+ |
| Ollama | 仅 AI 功能需要 | 视觉模型约需 8GB 内存 |

## macOS

### 1. 安装 Python

```bash
# 方式一：官网安装包（推荐，自带 Tk 8.6）
# https://www.python.org/downloads/

# 方式二：Homebrew
brew install python@3.12
```

> ⚠️ macOS 自带的 `/usr/bin/python3`（3.9，Tk 8.5）无法运行本程序，请安装新版 Python。

### 2. 安装 Ollama 并下载模型（可选，AI 功能需要）

```bash
# 安装 Ollama：https://ollama.com/download
# 下载视觉模型（选一个）
ollama pull llava:7b        # 轻量，约 4.7GB
ollama pull moondream       # 最轻量，约 1.7GB
ollama pull llava:13b       # 效果更好，约 8GB

# 文本模型（智能助手用）
ollama pull qwen2.5:7b
```

### 3. 启动

```bash
cd SnapSort素材分类器
bash run.sh
# 或双击「启动SnapSort.command」
```

首次启动会自动安装 Python 依赖（customtkinter、Pillow 等），并尝试安装拖拽支持（tkinterdnd2，可选）。

> 💡 拖拽：启动脚本会自动安装 tkinterdnd2；安装成功后可把文件夹直接拖进窗口设为素材路径。安装失败不影响其他功能。

## Windows

### 1. 安装 Python

从 [python.org](https://www.python.org/downloads/) 安装 3.11+，安装时勾选 **Add Python to PATH**。

### 2. 安装 Ollama（可选，AI 功能需要）

从 [ollama.com/download](https://ollama.com/download) 安装，然后：

```bat
ollama pull llava:7b
```

### 3. 启动

双击 `run.bat`。

或源码方式：

```bat
pip install -r requirements.txt
python app.py
```

## Linux

```bash
sudo apt install python3 python3-tk python3-pil.imagetk   # Debian/Ubuntu
pip install -r requirements.txt
python3 app.py
```

## 常见问题

**Q: 打开报 `ModuleNotFoundError: customtkinter`？**
首次启动 run.sh 会自动安装；若失败，手动执行 `pip install -r requirements.txt`。
注意 customtkinter 需 5.x 版本，6.0 不兼容。

**Q: 界面能打开，AI 功能提示连接失败？**
启动 Ollama 应用（macOS 打开 Ollama.app，Windows 运行 `ollama serve`），确认 `http://localhost:11434` 可访问。

**Q: HEIC 图片打不开？**
依赖已含 pillow-heif，若仍失败执行 `pip install pillow-heif`。

**Q: 配置、缓存和日志在哪里？**

- Windows：`%LOCALAPPDATA%\SnapSort`
- macOS：`~/Library/Application Support/SnapSort`（缓存位于 `~/Library/Caches/SnapSort`）
- Linux：遵循 `XDG_DATA_HOME` / `XDG_CACHE_HOME`

这些私人数据不会被打进安装包。

## 打包分发

```bash
# macOS
bash packaging/build_macos.sh   # 输出 dist/SnapSort.app

# Windows
packaging\build_windows.bat     # 输出 dist\SnapSort\SnapSort.exe
```

需要先 `pip install pyinstaller`。
