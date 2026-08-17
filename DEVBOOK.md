# SnapSort 开发者手册 (DEVBOOK)

> 写给 AI 助手和后台开发人员的完整开发指南
> 版本 3.0 | 最后更新 2026-08-16

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术架构](#2-技术架构)
3. [目录结构](#3-目录结构)
4. [核心模块详解](#4-核心模块详解)
5. [数据流与生命周期](#5-数据流与生命周期)
6. [配置系统](#6-配置系统)
7. [UI 页面体系](#7-ui-页面体系)
8. [多线程与性能](#8-多线程与性能)
9. [模型管理](#9-模型管理)
10. [位图转矢量算法](#10-位图转矢量算法)
11. [规则引擎](#11-规则引擎)
12. [扩展开发指南](#12-扩展开发指南)
13. [打包分发](#13-打包分发)
14. [常见问题](#14-常见问题)

---

## 1. 项目概述

SnapSort 是一套**本地 AI 驱动的素材管理桌面软件**。核心能力是利用本机 Ollama 大模型对图片进行自动分类、搜索、描述，并提供规则引擎进行后处理，以及位图转矢量、重复检测等工具。

### 设计原则

- **完全本地运行**，不消耗任何云 API token
- **跨平台** UI（macOS / Windows / Linux），字体自动适配系统
- **"安静质感"配色**：纯黑主按钮 + 琥珀色点缀 + 中性灰底，靠字号/字重/留白做层级
- **模块化架构**，core/ui 分离，便于测试和扩展
- **多线程非阻塞**，AI 推理在后台线程执行，UI 始终响应
- **JSON 本地存储**，零数据库依赖，跨平台迁移零成本

### 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| UI | customtkinter 5.2+ | 跨平台桌面界面 |
| 图片 | Pillow + macOS sips | 缩略图、HEIC 转换、格式检测 |
| AI 推理 | Ollama REST API | LLaVA / Qwen / BakLLaVA 视觉/文本模型 |
| 矢量 | Pillow + 轮廓追踪 | 位图转 SVG（内置算法，可选 potrace） |
| 数据 | JSON 文件 | 配置、历史记录 |
| 打包 | PyInstaller | Windows .exe / macOS .app 分发 |

### v2.3 更新摘要

| 功能 | 变更 |
|------|------|
| 位图转矢量 | 完全重写：Moore 轮廓追踪 + Catmull-Rom 贝塞尔平滑，3 种模式（photo/silhouette/edge）|
| 智能助手 | 新增工具：使用文本模型（qwen2.5）进行文案生成/翻译/总结 |
| 重复检测 | 新增工具：基于 MD5 哈希检测完全相同的图片 |
| 缩略图缓存 | 磁盘缓存缩略图到 data/thumbnails/，大幅提升二次加载速度 |
| 模型说明 | 每个模型旁显示详细用途说明，视觉/文本模型自动切换 |
| Windows 打包 | 完善 PyInstaller spec + 一键打包脚本 |

### v3.0 更新摘要

| 功能 | 变更 |
|------|------|
| 配色系统 | 从 Apple 蓝改为"安静质感"风格：纯黑主按钮 + 琥珀色点缀 + 中性灰选中态 |
| 跨平台字体 | 自动检测系统：macOS=SF Pro / Windows=Segoe UI / Linux=Noto Sans |
| 多标签预设 | 支持多套标签预设（默认ABC/内容分类），可自由增删标签、多标签混用 |
| 事件合并 | min_photos_per_event 阈值，防止单张照片被拆成独立文件夹 |
| AI Prompt 优化 | 业务背景 → AI 优化 → 结构化分类提示词（meta-prompt 模式）|
| 结构化输出 | AI 描述从单字段 DESC 改为 SCENE/DESC/PEOPLE/ACTION/MOOD 五字段 |
| 重试机制 | 分类失败后自动简化 prompt 重试 |
| 步骤指示器 | 事件模式顶部新增 3 步引导条（选文件夹→配选项→看结果）|
| 开发者面板 | 点击"乔心制作"5 次触发，显示项目结构、修改指引、跨平台说明 |
| 路径清理 | 移除所有硬编码用户路径，run.sh/run.bat 完全跨平台 |

---

## 2. 技术架构

```text
┌──────────────────────────────────────────────────────┐
│                     app.py                           │
│             (主入口 + 侧栏导航路由)                     │
├──────────────────────────────────────────────────────┤
│  ui/                                                 │
│  ├── theme.py        样式系统 / Apple Design          │
│  ├── dashboard.py    仪表盘 (统计卡片+快速操作)          │
│  ├── auto_sort.py    自动分类页面                      │
│  ├── gallery.py      素材库 (分类浏览+磁盘缓存缩略图)    │
│  ├── toolbox.py      AI 工具箱 (6种工具)               │
│  ├── history_view.py 历史记录页面                      │
│  └── settings.py     设置 (分类/规则/模型/输出)          │
├──────────────────────────────────────────────────────┤
│  core/                                               │
│  ├── config.py        配置管理 (ConfigManager)         │
│  ├── sorter_engine.py 分类引擎 (Ollama API + 分类)     │
│  ├── rule_engine.py   规则引擎 (IF-THEN 后处理)         │
│  ├── image_utils.py   图片工具 + 位图转矢量算法          │
│  ├── model_info.py    模型角色映射与用途说明             │
│  ├── report.py        报告生成 (CSV/Excel)             │
│  └── history.py       历史记录 CRUD                    │
├──────────────────────────────────────────────────────┤
│  data/                                               │
│  ├── snapsort_config.json  配置文件                   │
│  ├── history.json          历史记录                   │
│  └── thumbnails/           缩略图磁盘缓存              │
├──────────────────────────────────────────────────────┤
│  packaging/                打包分发                   │
│  ├── snapsort.spec         PyInstaller spec           │
│  ├── build_windows.bat     Windows 一键打包            │
│  ├── build_macos.sh        macOS 一键打包              │
│  └── README_WINDOWS.md     Windows 部署指南            │
└──────────────────────────────────────────────────────┘
```

---

## 3. 目录结构

```text
SnapSort素材分类器/
├── app.py                    # 主入口，创建 CTk + SnapSortApp
├── run.sh                    # Mac/Linux 启动脚本
├── run.bat                   # Windows 启动脚本（源码模式）
├── requirements.txt          # Python 依赖
├── README.md                 # 用户手册
├── DEVBOOK.md                # 本文件 — 开发者手册
│
├── core/                     # ⚠️ 核心逻辑层（无 UI 依赖）
│   ├── __init__.py
│   ├── config.py             # ConfigManager: JSON 配置读写
│   ├── sorter_engine.py      # 照片分类引擎 (Ollama Vision API)
│   ├── rule_engine.py        # 规则引擎 (IF-THEN)
│   ├── image_utils.py        # encode_image, make_thumbnail, bitmap_to_vector_svg
│   ├── model_info.py         # 模型角色映射, 视觉/文本判断, 用途说明
│   ├── report.py             # CSV/Excel 报告生成
│   └── history.py            # HistoryManager: JSON CRUD
│
├── ui/                       # ⚠️ 界面层（依赖 core）
│   ├── __init__.py
│   ├── theme.py              # 颜色/字体/按钮样式常量
│   ├── widgets.py            # 通用组件 (StatCard 等)
│   ├── dashboard.py          # 仪表盘页面
│   ├── auto_sort.py          # 自动分类页面
│   ├── gallery.py            # 素材库页面 (缩略图缓存)
│   ├── toolbox.py            # AI 工具箱页面 (6种工具)
│   ├── history_view.py       # 历史记录页面
│   └── settings.py           # 设置页面 (分类/规则/模型)
│
├── data/                     # 运行时数据（JSON + 缓存）
│   ├── snapsort_config.json
│   ├── history.json
│   └── thumbnails/           # 缩略图磁盘缓存 (PNG)
│
├── packaging/                # 打包分发
│   ├── snapsort.spec         # PyInstaller spec 文件
│   ├── build_windows.bat     # Windows 一键打包
│   ├── build_macos.sh        # macOS 一键打包
│   └── README_WINDOWS.md     # Windows 部署指南
│
├── assets/                   # 图标资源
└── docs/                     # 历史文档
```

### 模块依赖规则

```
app.py  →  core/*  +  ui/*
ui/*    →  core/*  (单向，ui 可引用 core，反之不行)
core/*  →  无 UI 依赖 (core 不 import ui)
```

---

## 4. 核心模块详解

### 4.1 ConfigManager (`core/config.py`)

配置管理单例，自动合并默认值与用户配置。

```python
from core.config import ConfigManager

cm = ConfigManager()  # 自动加载 data/snapsort_config.json
cm.get("model")       # → "llava:13b"
cm.set("model", "bakllava:latest")  # 立即写入磁盘
```

**配置字段表：**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `categories` | dict | 5 个预置分类 | 分类名 → 描述提示词 |
| `model` | str | `"llava:13b"` | 默认视觉模型 |
| `confidence_threshold` | float | 0.6 | 低置信度阈值 |
| `supported_exts` | list | [".jpg", ...] | 支持的图片格式 |
| `incremental` | bool | true | 是否增量处理 |
| `last_input` | str | "" | 上次输入的文件夹路径 |
| `last_output` | str | "" | 上次输出的文件夹路径 |
| `rules` | list | [] | 规则引擎规则列表 |
| `output.generate_report` | bool | true | 是否生成 CSV 报告 |
| `output.low_confidence_review` | bool | true | 低置信度进入待复核 |
| `output.handle_duplicates` | str | "rename" | 重名处理策略 |

### 4.2 SorterEngine (`core/sorter_engine.py`)

分类主引擎，负责完整的工作流：

```text
检查 Ollama → 确保模型就绪 → 扫描图片 → 过滤已处理 → 
逐个分类 (AI 描述 + 关键词匹配) → 复制到分类目录 → 
生成报告 → 执行规则引擎 → 记录历史
```

**关键函数：**

| 函数 | 用途 |
|------|------|
| `fetch_ollama_models()` | 获取已安装的**视觉**模型列表 |
| `fetch_all_models()` | 获取**所有**已安装模型（含文本模型）|
| `ensure_model(name)` | 确保模型已下载，否则自动拉取 |
| `classify_image(path, config)` | 对单张图片调用 LLaVA 分类 |
| `match_category(desc, keywords)` | 关键词匹配最相关类别 |
| `build_keywords_map(categories)` | 从分类配置构建关键词表 |

### 4.3 图片工具 (`core/image_utils.py`)

| 函数 | 说明 |
|------|------|
| `encode_image(path, max_size_kb)` | 图片 → base64, HEIC 自动转 JPEG |
| `convert_heic_to_jpeg(path)` | macOS sips 转 HEIC, 兼容 pillow-heif |
| `make_thumbnail(path, size)` | 生成 Pillow 缩略图 |
| `image_count_and_size(dir)` | 统计目录图片数和总大小 |
| `is_image_file(path)` | 判断是否为支持的图片格式 |
| `bitmap_to_vector_svg(path, mode, ...)` | 位图转 SVG 矢量图（3种模式） |

### 4.4 模型信息 (`core/model_info.py`)

v2.3 新增/重构。提供模型角色判断和用途说明。

```python
from core.model_info import (
    get_model_hint,          # 一句话用途说明
    is_vision_model,         # 是否视觉模型
    is_text_model,           # 是否纯文本模型
    get_model_role_tag,      # "视觉模型" / "文本模型"
    get_model_usage_guide,   # 各功能适用性详细说明
)
```

**qwen2.5 在 SnapSort 中的定位：**

qwen2.5 是**纯文本模型**，不能看图。在 SnapSort 中：

| 功能 | qwen2.5 可用？ | 说明 |
|------|:---:|------|
| 自动分类 | ❌ | 需要视觉模型看图 |
| 以文搜图 | ❌ | 需要视觉模型看图 |
| 图片描述 | ❌ | 需要视觉模型看图 |
| 图片问答 | ❌ | 需要视觉模型看图 |
| **智能助手** | ✅ | **主要用途**：文案生成、翻译、总结、关键词提取 |
| 重复检测 | ✅ | 不需要 AI 模型 |
| 位图转矢量 | ✅ | 不需要 AI 模型 |

> **总结：qwen2.5 的价值在「智能助手」工具中体现**，利用其强大的中文文本能力为用户提供文案、翻译等服务。

### 4.5 历史记录 (`core/history.py`)

```python
from core.history import HistoryManager
h = HistoryManager()
h.add(input_dir, output_dir, model, total, results, elapsed)
h.get_all()   # 返回全部记录
h.delete(id)  # 删除单条
h.clear()     # 清空
```

---

## 5. 数据流与生命周期

### 5.1 应用启动

```text
app.py main() 
  → ctk.CTk() 创建窗口
  → SnapSortApp.__init__()
    → ConfigManager() 加载配置
    → 创建 StringVar (input_var, output_var)
    → _build_ui() 构建侧栏 + 初始化所有页面
    → show_page("dashboard")
    → root.mainloop()
```

### 5.2 自动分类流程

```text
用户点击「开始自动分类」
  → _start_sort()
    → 验证路径 → 清空日志 → 禁用按钮
    → 创建 SorterEngine(config, callbacks)
    → threading.Thread(target=engine.run) 后台启动
    → engine.run()
      → check_ollama() → ensure_model()
      → 扫描图片文件
      → 增量过滤 (get_processed_files)
      → for each image:
          → classify_image() → Ollama /api/generate
          → match_category() → 关键词匹配
          → 低置信度 → "待复核"
          → copy_to_category()
          → 进度回调 → UI 更新进度条
      → generate_csv_report()
      → RuleEngine.apply_all()
      → HistoryManager.add()
      → finished_callback → _reset_ui()
```

### 5.3 页面切换

```text
用户点击侧边栏按钮
  → Lambda → self.show_page(key)
    → 隐藏当前页面 (pack_forget)
    → 显示目标页面 (pack)
    → 更新导航高亮
    → 若页面有 refresh() → 调用
```

---

## 6. 配置系统

### 6.1 配置文件位置

```
SnapSort素材分类器/data/snapsort_config.json
```

### 6.2 新增配置项

向 `DEFAULT_CONFIG` 字典添加新键，ConfigManager.load() 会自动合并缺少的项。

---

## 7. UI 页面体系

### 7.1 主题系统 (`ui/theme.py`)

Apple Design Token 风格配色：

| Token | 值 | 用途 |
|-------|-----|------|
| `bg` | `#F5F5F7` | 窗口背景 |
| `sidebar` | `#FFFFFF` | 侧边栏 |
| `card` | `#FFFFFF` | 卡片 |
| `primary` | `#0071E3` | 主色 |
| `text` | `#1D1D1F` | 正文 |
| `text_secondary` | `#6E6E73` | 次要文字 |
| `border` | `#D2D2D7` | 边框 |
| `success` | `#34C759` | 成功 |
| `warning` | `#FF9500` | 警告 |
| `danger` | `#FF3B30` | 错误 |

### 7.2 AI 工具箱 (`ui/toolbox.py`) — v2.3 完整工具列表

| 工具 | 需要模型 | 说明 |
|------|---------|------|
| 🎨 位图转矢量 | 不需要 | 3种模式：photo/silhouette/edge |
| 🔍 以文搜图 | 视觉模型 | 输入文字描述，AI 在文件夹中找匹配图片 |
| 📝 图片描述 | 视觉模型 | 生成小红书/朋友圈/产品/SEO 文案 |
| 💬 图片问答 | 视觉模型 | 针对图片内容提问 |
| 🤖 智能助手 | 文本模型 | **qwen2.5 主要用途**：文案/翻译/总结/关键词 |
| 🔁 重复检测 | 不需要 | MD5 哈希检测完全相同的图片 |

工具切换时自动选择合适的模型类型：
- 切换到「智能助手」→ 自动选文本模型（如 qwen2.5）
- 切换到「以文搜图/图片描述/图片问答」→ 自动选视觉模型（如 llava）

### 7.3 素材库缩略图缓存 (`ui/gallery.py`) — v2.3 新增

```python
# 缓存路径
data/thumbnails/{md5_hash}.png

# 缓存键 = md5(文件路径 + 修改时间 + 文件大小 + 缩略图尺寸)
# 首次加载生成缩略图并缓存，后续直接从磁盘读取
```

### 7.4 页面通用接口

每个页面类必须：
- 继承 `ctk.CTkFrame`
- 构造函数接收 `(master, app, **kwargs)`
- 存储在 `app.pages[page_key]`
- 可选实现 `refresh()` 方法，切换页面时自动调用

---

## 8. 多线程与性能

### 8.1 线程模型

```text
主线程 (UI)          后台线程 (Worker)
    │                     │
    ├─ 渲染界面            ├─ Ollama API 调用 (HTTP 请求)
    ├─ 用户交互            ├─ 图片编码/解码
    ├─ 回调调度            ├─ 文件 I/O (复制/移动)
    │                     ├─ 缩略图生成/缓存
    │                     ├─ 矢量化计算
    │                     │
    │◄──── after(0) ──────│  # 通过 root.after 安全更新 UI
```

### 8.2 关键性能措施

1. **模型列表异步加载** — 后台线程运行，不阻塞 UI 首次渲染
2. **日志行数限制** — `_max_log_lines = 800` 防止 ScrolledText 内存泄漏
3. **缩略图磁盘缓存** — v2.3 新增，PNG 缓存到 data/thumbnails/
4. **缩略图懒加载** — Gallery 页面最多显示 300 张，分批渲染（每批 12 张）
5. **图片压缩** — `encode_image(max_size_kb=1024)` 自动缩小大图
6. **增量处理** — 已分类文件跳过，避免重复 AI 调用

### 8.3 避免 UI 卡顿的规则

```python
# ❌ 错误：在主线程做网络请求
models = fetch_ollama_models()  # 阻塞 UI

# ✅ 正确：后台线程 + after 回调
def _load_async():
    models = fetch_ollama_models()
    root.after(0, lambda: update_ui(models))
threading.Thread(target=_load_async, daemon=True).start()
```

---

## 9. 模型管理

### 9.1 Ollama API 端点

| 端点 | 用途 |
|------|------|
| `GET /api/tags` | 获取已安装模型列表 |
| `POST /api/generate` | 推理（文本或视觉）|
| `POST /api/pull` | 下载模型 |
| `DELETE /api/delete` | 删除模型 |
| `POST /api/show` | 获取模型详细信息 |

### 9.2 视觉模型 vs 文本模型

- **视觉模型**（用于照片分类/描述/问答/搜索）：通过 `is_vision_model()` 判断
  - `llava`, `bakllava`, `moondream`, `qwen-vl`, `qwen2.5-vl`, `gemma3` 等
  - 关键：名称中含 `-vl` 后缀或匹配 `VISION_KEYWORDS`
- **文本模型**（用于智能助手）：`is_text_model()` = `not is_vision_model()`
  - `qwen2.5`, `llama3`, `mistral`, `gemma`, `phi` 等
  - **不能看图，但可以处理文字**（文案、翻译、总结）

### 9.3 添加新的视觉模型支持

编辑 `core/sorter_engine.py` 的 `VISION_KEYWORDS` 列表，以及 `core/model_info.py` 的 `MODEL_HINTS` 字典。

---

## 10. 位图转矢量算法

### 10.1 概述

v2.3.1 使用 **Marching Squares 等值线提取算法**（带线性插值）替代了旧的 Moore 轮廓追踪。Marching Squares 是标准的等值线提取算法，通过在相邻像素之间进行线性插值获得亚像素精度的轮廓交点，生成的曲线远比像素级追踪平滑。

### 10.2 三种模式

#### photo 模式
```text
输入图片 → 缩放(max_size) → SMOOTH 模糊 → 颜色量化(N色 MEDIANCUT) →
对每种颜色创建二值掩码 → Marching Squares 轮廓提取(带线性插值) →
Douglas-Peucker 路径简化(tol_sq=3.0) → Catmull-Rom 转贝塞尔曲线 → SVG <path>
```
- 最小色块面积: 20 像素（过滤噪点）
- 最小轮廓长度: 6 点
- 最小简化后路径: 4 点

#### silhouette 模式
```text
输入图片 → 缩放(max_size) → 灰度化 → SMOOTH 模糊 → Otsu 自动阈值 → 二值化 →
Marching Squares 轮廓提取(带线性插值) → 路径简化(tol_sq=1.5) → 平滑曲线 → SVG <path>
（若系统已安装 potrace，优先使用 potrace 获得更好效果）
```

#### edge 模式
```text
输入图片 → 缩放(max_size) → 灰度化 → SMOOTH 模糊 → Sobel 边缘检测 → 阈值化(>50) →
Marching Squares 轮廓提取 → 路径简化(tol_sq=1.5) → SVG <path> (stroke, 不填充)
```
- 过滤单点和过短路径（距离<2px）

### 10.3 核心算法函数

| 函数 | 用途 |
|------|------|
| `_marching_squares_contours(mask, w, h)` | Marching Squares 等值线提取，带线性插值 |
| `_douglas_peucker(points, tol_sq)` | Douglas-Peucker 路径简化 |
| `_points_to_smooth_svg_path(points, closed)` | Catmull-Rom 转贝塞尔曲线 |
| `_points_to_svg_path(points, closed)` | 直线段 SVG path |
| `_kmeans_quantize(img, n_colors)` | 颜色量化（MEDIANCUT） |
| `_otsu_threshold(gray_img)` | Otsu 自动阈值 |
| `_morphological_close(mask, w, h)` | 形态学闭运算（膨胀+腐蚀） |
| `_vectorize_photo_mode(img, colors, size)` | photo 模式主函数 |
| `_vectorize_silhouette_mode(img, size)` | silhouette 模式主函数 |
| `_vectorize_edge_mode(img, size)` | edge 模式主函数 |
| `_safe_open_image(image_path)` | 安全打开图片（处理 HEIC/RGBA/P模式） |
| `convert_heic_to_jpeg(image_path)` | HEIC 转换（pillow_heif 优先，sips 备选） |

### 10.4 HEIC/HEIF 支持

- 模块加载时自动注册 `pillow_heif.register_heif_opener()`
- 注册后 `PIL.Image.open()` 可直接读取 HEIC/HEIF
- Windows 无 `sips`，必须安装 `pillow-heif`
- 转换失败时抛出 `ValueError` 带详细提示，不再静默返回

### 10.5 性能参数

- `max_size`: 默认 500px，范围 200-1000。越大越精细但越慢
- `max_colors`: 默认 8，范围 2-16。仅 photo 模式
- Marching Squares 时间复杂度 O(w*h)，500px 约 1-3 秒
- 在后台线程执行，不阻塞 UI

---

## 11. 规则引擎

### 11.1 规则格式

```json
{
    "name": "规则名称",
    "enabled": true,
    "condition": {
        "category": "截图",
        "text_contains": "微信",
        "filename_contains": "IMG_",
        "file_ext": ".png",
        "confidence_lt": 0.6,
        "confidence_gt": 0.8,
        "regex_match": "^photo_\\d+"
    },
    "action": {
        "type": "move",
        "target_dir": "微信截图"
    }
}
```

### 11.2 条件支持（全部为 AND 关系）

| 条件字段 | 类型 | 说明 |
|----------|------|------|
| `category` | str | 分类名精确匹配 |
| `text_contains` | str | AI 描述包含关键词 |
| `filename_contains` | str | 文件名包含字符串 |
| `file_ext` | str | 文件后缀 |
| `confidence_lt` | float | 置信度 < 该值 |
| `confidence_gt` | float | 置信度 > 该值 |
| `regex_match` | str | 文件名正则匹配 |
| `description_regex` | str | AI 描述正则匹配 |

### 11.3 动作支持

| 动作类型 | 参数 | 说明 |
|----------|------|------|
| `move` | `target_dir` | 移动文件到子目录（支持 `{category}` 变量）|
| `copy` | `target_dir` | 复制文件到子目录 |
| `rename` | `pattern` | 重命名（`{name}{ext}` 变量）|
| `add_tag` | `tag` | 添加标签 |

---

## 12. 扩展开发指南

### 12.1 添加新页面

1. 创建 `ui/my_new_page.py`，实现标准页面类
2. 在 `app.py` 中 import 并注册：
   ```python
   from ui.my_new_page import MyNewPage
   nav_items = [..., ("my_page", "🔮", "新功能"), ...]
   self.pages["my_page"] = MyNewPage(self.content_frame, self)
   ```

### 12.2 添加新 AI 工具

1. 在 `ui/toolbox.py` 的 `tools` 列表中添加新选项
2. 在 `_switch_tool()` 中添加 `elif` 分支
3. 实现 `_build_xxx()` 构建 UI 和 `_run_xxx()` 执行逻辑
4. 如需模型，在 `_on_model_change()` 中更新提示

### 12.3 扩展分类引擎

修改 `core/sorter_engine.py` 的 `classify_image()` 中的 prompt 或 `match_category()` 匹配算法。

### 12.4 扩展位图转矢量

在 `core/image_utils.py` 中添加新的 `_vectorize_xxx_mode()` 函数，然后在 `bitmap_to_vector_svg()` 中添加分支。

---

## 13. 打包分发

### 13.1 macOS 打包

```bash
# 使用打包脚本
cd SnapSort素材分类器
./packaging/build_macos.sh

# 或手动
pip install pyinstaller
pyinstaller packaging/snapsort.spec
# 输出在 dist/SnapSort.app
```

### 13.2 Windows 打包（exe）

```bat
# 在 Windows 上
cd SnapSort素材分类器
packaging\build_windows.bat

# 或手动
pip install -r requirements.txt pyinstaller
pyinstaller packaging\snapsort.spec
# 输出在 dist\SnapSort\SnapSort.exe
```

### 13.3 PyInstaller Spec 文件

`packaging/snapsort.spec` 包含：
- `--onedir` 模式（比 onefile 启动快）
- 所有依赖的 hidden-imports
- data/core/ui 目录打包
- customtkinter 资源文件

### 13.4 用户环境要求

| 项目 | macOS | Windows |
|------|-------|---------|
| 操作系统 | macOS 12+ | Windows 10/11 64位 |
| Python | 不需要（打包进app） | 不需要（打包进exe） |
| Ollama | 必须安装 | 必须安装 |
| 模型 | `ollama pull llava:13b` | `ollama pull llava:13b` |
| 内存 | 8GB+，llava:13b 建议 16GB | 8GB+，llava:13b 建议 16GB |

### 13.5 界面不依赖模型

SnapSort 的界面**不需要 Ollama 运行就能打开**。只有以下功能需要 Ollama：
- 自动分类（需要视觉模型）
- 以文搜图（需要视觉模型）
- 图片描述（需要视觉模型）
- 图片问答（需要视觉模型）
- 智能助手（需要文本模型）

以下功能不需要 Ollama：
- 位图转矢量
- 重复检测
- 素材库浏览
- 历史记录
- 设置管理

---

## 14. 事件分类模式（v2.4 新增）

### 14.1 概述

事件模式是 v2.4 新增的独立分类流程，专门为「用照片讲故事」的场景设计：

1. **按日期分组** — 同一天拍摄的照片自动归为同一事件
2. **AI 事件命名** — 抽取3张样片让视觉模型为事件起名（如"工厂考察""客户签约"）
3. **ABC 故事性分级** — 每张照片评估讲故事价值
4. **批量重命名** — 按 `{日期}_{事件}_{序号}{等级}_{描述}.jpg` 格式自动重命名

### 14.2 ABC 分级标准

| 等级 | 标签 | 标准 | 用途 |
|------|------|------|------|
| A | ⭐ 核心故事 | 人物互动、情感瞬间、关键动作、独特场景 | 故事高潮 |
| B | 📋 辅助场景 | 环境交代、背景细节、过渡场景 | 故事上下文 |
| C | 📎 记录备查 | 重复场景、模糊、空镜、文档资料 | 存档记录 |

### 14.3 核心模块

文件：`core/event_classifier.py`

关键函数：
- `get_photo_date(path)` — 从 EXIF 或文件时间获取拍摄日期
- `group_by_date(photos)` — 按日期分组
- `generate_event_name(date, samples, model)` — AI 命名事件
- `grade_photo(path, model)` — 单张 ABC 分级
- `build_new_filename(date, event, seq, grade, desc, ext)` — 生成新文件名
- `execute_batch_rename(results, event_name, output_dir, ...)` — 执行批量重命名
- `generate_storyline(events_info)` — 生成故事线摘要

### 14.4 UI 集成

在 `auto_sort.py` 中通过 `CTkSegmentedButton` 切换「分类模式」和「事件模式」。
事件模式的三步流程：
1. 「扫描日期分组」→ 按 EXIF/文件日期分组预览
2. 「AI 分析+分级+命名」→ 后台调用 Ollama 分析每一张
3. 「执行批量重命名」→ 复制并重命名到事件文件夹（AI分析时已自动执行）

---

## 15. 常见问题

### Q: 启动时报 "AttributeError: 'SnapSortApp' object has no attribute '_center_window'"

A: 检查 `app.py` 中是否定义了 `_center_window()` 方法。v2.1+ 已修复。

### Q: qwen2.5 模型有什么用？

A: qwen2.5 是**纯文本模型**，不能看图。它的主要用途是**「智能助手」工具**——文案生成、中英翻译、内容总结、关键词提取。切换到智能助手工具时会自动选择文本模型。分类、搜图等需要看图的功能仍然需要视觉模型（llava 等）。

### Q: 位图转矢量效果不好？

A: v2.3 已完全重写矢量算法。调整方法：
1. 增大「精度」参数（默认 500，最大 1000）
2. photo 模式调整颜色数（2-16）
3. 简单图形/Logo 用 silhouette 模式效果最好
4. 照片用 photo 模式，图标用 silhouette 或 edge 模式

### Q: 分类不准确

A: 
1. 升级模型到 `llava:13b` 或 `bakllava:latest`
2. 在设置中调整分类描述提示词
3. 编辑 `core/sorter_engine.py` 中的 `base_keywords` 添加领域关键词

### Q: Windows 双击 exe 后闪退？

A: v2.3 已确保界面不需要 Ollama 即可打开。如果闪退：
1. 确认 Windows 10/11 64位
2. 检查是否有杀毒软件拦截
3. 尝试从命令行运行查看错误信息

### Q: HEIC 图片无法分类

A: macOS 已通过系统 `sips` 命令支持。Windows 需安装 `pillow-heif`：
```bash
pip install pillow-heif
```

### Q: 缩略图缓存怎么清理？

A: 在素材库页面点击「🗑 清缓存」按钮，或手动删除 `data/thumbnails/` 目录。

---

## 附录 A: Python 环境

本项目开发使用 **WorkBuddy 管理的 Python 3.13.12**：

```bash
# 路径
/Users/apple/.workbuddy/binaries/python/versions/3.13.12/bin/python3

# 虚拟环境
/Users/apple/.workbuddy/binaries/python/envs/default/

# 安装新包
/Users/apple/.workbuddy/binaries/python/envs/default/bin/pip install <package>
```

打包后的 exe/app 不依赖此路径，可分发给任何用户。

## 附录 B: 相关资源

- [Ollama API 文档](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [customtkinter 文档](https://customtkinter.tomschimansky.com/)
- [Pillow 文档](https://pillow.readthedocs.io/)
- [Moore 边界追踪算法](https://en.wikipedia.org/wiki/Moore_neighborhood)
- [Douglas-Peucker 算法](https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm)
