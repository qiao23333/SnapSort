# SnapSort 素材分类器 v2.3

> 本地 AI 驱动的素材管理桌面软件，完全离线运行，零 token 消耗

## 快速开始

### macOS

```bash
# 双击 run.sh 或在终端执行
./run.sh
```

### Windows

**方式一：源码运行（需安装 Python）**
```bat
双击 run.bat
```

**方式二：exe 运行（推荐分发用，无需 Python）**
```bat
# 在 Windows 上打包
packaging\build_windows.bat
# 生成 dist\SnapSort\SnapSort.exe，双击即可运行
```

### 前置条件

- **Ollama**（仅 AI 功能需要）：[下载安装](https://ollama.com)
- **模型**：`ollama pull llava:13b`（分类）+ `ollama pull qwen2.5:7b`（智能助手）
- 界面不需要 Ollama 也能打开！

## 功能列表

| 功能 | 说明 | 需要模型 |
|------|------|:---:|
| 📊 仪表盘 | 统计概览和快速操作 | ❌ |
| 🚀 自动分类 | AI 自动将图片分到不同类别文件夹 | 视觉模型 |
| 🖼 素材库 | 按分类浏览缩略图（磁盘缓存加速） | ❌ |
| 🎨 位图转矢量 | JPG/PNG → SVG（3种模式：照片/剪影/边缘） | ❌ |
| 🔍 以文搜图 | 输入文字描述，AI 找匹配图片 | 视觉模型 |
| 📝 图片描述 | 生成小红书/朋友圈/产品/SEO 文案 | 视觉模型 |
| 💬 图片问答 | 针对图片内容提问 | 视觉模型 |
| 🤖 智能助手 | 文案生成/翻译/总结/关键词（qwen2.5 专用） | 文本模型 |
| 🔁 重复检测 | MD5 哈希检测完全相同的图片 | ❌ |
| 🔧 规则引擎 | 分类后自动执行 IF-THEN 规则 | ❌ |

## 模型说明

| 模型 | 类型 | 用途 |
|------|------|------|
| llava:13b | 视觉 | 分类主力、图片描述、问答、搜图 |
| llava:7b | 视觉 | 轻量分类（内存不足时用） |
| bakllava | 视觉 | 分类与描述 |
| moondream | 视觉 | 快速分类 |
| qwen2.5:7b | **文本** | **智能助手**（文案/翻译/总结） |

> qwen2.5 不能看图，主要用于「智能助手」工具中的文字处理任务。

## 位图转矢量说明

v2.3 完全重写了矢量算法，三种模式：

- **photo**：颜色量化 + 轮廓追踪，生成多色平滑矢量（适合照片风格化）
- **silhouette**：Otsu 自动阈值 + 边界追踪，生成黑白剪影（适合 Logo/图标）
- **edge**：Sobel 边缘检测 + 路径追踪，生成线稿描边

精度参数：200-1000px，越大越精细。

## 打包分发

### Windows exe
```bat
packaging\build_windows.bat
```
生成 `dist\SnapSort\` 文件夹，压缩为 zip 发给别人即可。

### macOS app
```bash
./packaging/build_macos.sh
```
生成 `dist/SnapSort.app`，需要 Xcode 命令行工具。

详见 `packaging/README_WINDOWS.md` 和 `DEVBOOK.md`。
