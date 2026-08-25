# SnapSort — 本地 AI 素材整理工作台

[![CI](https://github.com/qiao23333/SnapSort/actions/workflows/ci.yml/badge.svg)](https://github.com/qiao23333/SnapSort/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

SnapSort 是一个本地运行的图片素材整理工具。它读取文件夹中的照片，按内容或拍摄事件分组，并提供重命名、查重、格式转换和图片搜索等常用操作。需要识图时通过本机 Ollama 运行，默认不上传照片。

## ✨ 核心功能

### 自动分类
- 多标签预设系统：自由定义标签体系（默认 ABC / 内容分类），多标签混用
- 结构化输出：SCENE / DESC / PEOPLE / ACTION / MOOD 五字段
- 可以补充业务背景，让分类规则更贴合自己的工作
- 失败自动降级重试，低置信度进复核

### 按事件整理
- 拖拽文件夹进窗口即开始（可选）
- 时间聚类：按拍摄间隔自动切分事件
- AI 事件命名：LLM 为每组照片起名（如「三亚团建」）
- ABC 质量分级：A 级精选、C 级待删，贴合摄影师工作流
- 断点续跑：Checkpoint 机制，几千张跑到一半关机，重开接着跑
- 30 秒撤销：整理完不满意，一键删除本次输出（复制式整理，原文件始终安全）

### 图片工具箱
| 工具 | 说明 |
|------|------|
| 图片搜索 | 默认用本地视觉模型分批识别并缓存；可选 CLIP/FAISS 增量索引加速 |
| 位图转矢量 | Marching Squares 等值线 + 贝塞尔平滑，输出 SVG |
| 重复检测 | MD5 精确查重 + dHash 相似查重（截图变体也能检出） |
| 批量处理 | 尺寸 / 旋转 / 文字水印（位置、透明度可调） |
| 批量格式转换 | HEIC↔JPG↔PNG↔WebP，**EXIF 完整保留** |
| EXIF 信息与日期修正 | 查看并修改日期、标题、描述、作者、关键词、版权、评分；支持批量补拍摄时间 |
| 图片问答 / 描述 / 智能助手 | Ollama 视觉/文本模型多用途调用 |
| EXIF 查看 / 自定义重命名 | — |

### 桌面体验
- 针对 Windows 和 macOS 分别处理中文字体、图标和文件路径
- 设置页可在两套内置图标间切换，也可导入自己的 PNG / WebP / JPG / ICO 图标
- 素材库缩略图：线程池并发 + 磁盘缓存，万张级不卡顿
- 统一日志双写：界面日志 + 用户数据目录中的滚动日志
- 可以导出汇总使用报告，不包含图片名、本地路径和图片内容

### 已知对象
- 与已知人物、已知地点一致：给具体对象命名、填写描述并上传 1–5 张参考照片
- 自动分类时会把待分类照片与对象参考图进行实例级视觉比对
- 工具箱可直接点击已知对象；默认分批识别并缓存，安装可选 CLIP/FAISS 后使用多张参考图的平均视觉特征快速搜索
- 图片索引只处理新增或修改过的照片；搜索时不再突然重新扫描整个文件夹

## 🚀 快速开始

```bash
# 1. 克隆
git clone https://github.com/qiao23333/SnapSort.git
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
│   ├── clip_search.py    可选 CLIP/FAISS 增量向量索引
│   ├── object_search.py  参考图分批识别与结果缓存
│   ├── rule_engine.py    后处理自动化规则
│   └── image_utils.py    HEIC/缩略图/矢量化
└── data/                 只读图标资源（用户数据不会进入安装包）
```

**技术要点**：Ollama REST 多模型编排 · ThreadPoolExecutor 并发推理 · Checkpoint 断点续跑 · dHash 感知哈希 · Marching Squares 矢量化 · 滚动日志双写

## 📖 使用指南

1. **自动分类**：选输入/输出文件夹 → 选模型 → 开始。增量处理，已分类的自动跳过
2. **按事件整理**：选文件夹 → 配置选项（间隔/分级/命名规则）→ 预览分组 → 确认执行
3. **工具箱**：11 个独立工具，选文件夹即用
4. **设置**：标签预设、人物/地点/对象参考库、自动化规则、应用图标

更多细节见 [DEVBOOK.md](DEVBOOK.md)（开发手册）。

## 🗺 Roadmap

- [x] v3.1 批量处理（尺寸/旋转/水印）、相似查重、日志双写、拖拽导入、30 秒撤销
- [x] v3.3 Windows 用户数据隔离、跨平台 CI、Windows 打包冒烟测试
- [x] v3.6 已知对象参考图库、EXIF 编辑、增量图片搜索与 Windows 首帧优化
- [ ] 深浅色主题切换
- [ ] Windows 安装包（Inno Setup）
- [ ] 更多语言模型评测基准

## 🤝 贡献

欢迎 Issue / PR。开发者面板：侧栏副标题点击 5 次可查看项目结构与修改指引。

## 📄 许可

[MIT License](LICENSE) © 2026 乔心

版本历史见 [CHANGELOG.md](CHANGELOG.md)。
