# SnapSort — 本地 AI 素材整理工作台

> **Local-first AI photo organizer.** SnapSort turns messy photo dumps into a structured, searchable asset library — event grouping, ABC quality grading, batch renaming — all running offline on your own machine via Ollama. No cloud, no token cost, zero privacy leakage.

完全本地运行的 AI 素材整理桌面软件：基于 Ollama 视觉模型，把「一堆杂乱照片」自动变成「按事件成组、按质量分级、按规则命名」的可用素材库。零云端、零 token 费用、隐私不出本机。

## 📸 截图

> 截图待补充（建议：仪表盘 / 事件整理 3 步流程 / 工具箱 / 素材库 / 重复检测结果）

## ✨ 核心功能

### AI 自动分类
- 多标签预设系统：自由定义标签体系（默认 ABC / 内容分类），多标签混用
- 结构化输出：SCENE / DESC / PEOPLE / ACTION / MOOD 五字段
- meta-prompt 优化：业务背景 → AI 优化提示词 → 更准的分类
- 失败自动降级重试，低置信度进复核

### 按事件整理（独有）
- 拖拽文件夹进窗口即开始（可选）
- 时间聚类：按拍摄间隔自动切分事件
- AI 事件命名：LLM 为每组照片起名（如「三亚团建」）
- ABC 质量分级：A 级精选、C 级待删，贴合摄影师工作流
- 断点续跑：Checkpoint 机制，几千张跑到一半关机，重开接着跑
- 30 秒撤销：整理完不满意，一键删除本次输出（复制式整理，原文件始终安全）

### 图片工具箱（11 个工具，多数无需 AI）
| 工具 | 说明 |
|------|------|
| 以文搜图 | CLIP 语义搜索，文字找图 |
| 位图转矢量 | Marching Squares 等值线 + 贝塞尔平滑，输出 SVG |
| 重复检测 | MD5 精确查重 + dHash 相似查重（截图变体也能检出） |
| 批量处理 | 尺寸 / 旋转 / 文字水印（位置、透明度可调） |
| 批量格式转换 | HEIC↔JPG↔PNG↔WebP，**EXIF 完整保留** |
| 日期修正 | 批量补 EXIF 拍摄时间，拯救截图日期 |
| 图片问答 / 描述 / 智能助手 | Ollama 视觉/文本模型多用途调用 |
| EXIF 查看 / 自定义重命名 | — |

### 界面
- Apple 风格 UI：安静质感配色、跨平台字体自适应（macOS/Windows/Linux）
- 素材库缩略图：线程池并发 + 磁盘缓存，万张级不卡顿
- 统一日志双写：界面日志 + `data/logs/` 文件日志

## 🚀 快速开始

```bash
# 1. 克隆
git clone https://github.com/你的用户名/SnapSort.git
cd SnapSort

# 2. 启动（自动安装依赖）
bash run.sh          # macOS
run.bat              # Windows
```

AI 功能需要 [Ollama](https://ollama.com)：

```bash
ollama pull llava:7b     # 视觉模型（轻量 4.7GB）
ollama pull qwen2.5:7b   # 文本模型（智能助手）
```

详细安装步骤（含常见问题）见 [INSTALL.md](INSTALL.md)。

## 🛠 技术架构

```
app.py                    主入口 + 侧栏路由
├── ui/                   界面层（customtkinter）
│   ├── theme.py          配色/字体/样式系统
│   ├── dashboard.py      仪表盘
│   ├── auto_sort.py      分类（内容模式 + 事件模式）
│   ├── gallery.py        素材库（线程池 + 缩略图缓存）
│   ├── toolbox.py        11 个工具
│   ├── settings.py       配置/标签/规则引擎
│   └── history_view.py   历史记录
├── core/                 业务层
│   ├── sorter_engine.py  AI 分类（重试/降级/结构化解析）
│   ├── event_classifier.py 事件聚类（间隔切分/合并/命名/分级）
│   ├── clip_search.py    CLIP 语义搜图
│   ├── rule_engine.py    后处理自动化规则
│   └── image_utils.py    HEIC/缩略图/矢量化
└── data/                 配置、缓存、日志（git 忽略）
```

**技术要点**：Ollama REST 多模型编排 · ThreadPoolExecutor 并发推理 · Checkpoint 断点续跑 · dHash 感知哈希 · Marching Squares 矢量化 · 滚动日志双写

## 📖 使用指南

1. **自动分类**：选输入/输出文件夹 → 选模型 → 开始。增量处理，已分类的自动跳过
2. **按事件整理**：选文件夹 → 配置选项（间隔/分级/命名规则）→ 预览分组 → 确认执行
3. **工具箱**：11 个独立工具，选文件夹即用
4. **设置**：标签预设、人物/地点参考库、自动化规则

更多细节见 [DEVBOOK.md](DEVBOOK.md)（开发手册）。

## 🗺 Roadmap

- [x] v3.1 批量处理（尺寸/旋转/水印）、相似查重、日志双写、拖拽导入、30 秒撤销
- [ ] 深浅色主题切换
- [ ] Windows 安装包（Inno Setup）
- [ ] 更多语言模型评测基准

## 🤝 贡献

欢迎 Issue / PR。开发者面板：侧栏副标题点击 5 次可查看项目结构与修改指引。

## 📄 许可

[MIT License](LICENSE) © 2026 乔心

版本历史见 [CHANGELOG.md](CHANGELOG.md)。
