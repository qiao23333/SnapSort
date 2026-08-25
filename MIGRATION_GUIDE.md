# SnapSort v3.4.0 迁移指南

## 一、迁移到新电脑

### 方法 A：用 .app / .exe 打包版（最省事，无需装 Python）

**macOS：**
1. 将 `SnapSort_macOS_v3.4.0.zip` 拷到新 Mac（U盘/AirDrop/云盘）
2. 解压得到 `SnapSort.app`
3. 双击 `SnapSort.app` 即可运行
4. 首次打开可能提示"无法验证开发者"，右键→打开即可

**Windows：**
1. 需在 Windows 电脑上先运行 `packaging\build_windows.bat` 生成 exe
2. 将生成的 `dist\SnapSort\` 整个文件夹打包为 zip
3. 拷到目标电脑，解压后双击 `SnapSort.exe` 即可

> .app/.exe 内置完整 Python 运行时，不需要额外安装 Python。
> 但 AI 分类功能仍需安装 Ollama（应用内有向导引导下载）。

### 方法 B：用源码迁移包（需要装 Python）

1. 将 `SnapSort_v3.4.0_迁移包.zip` 拷贝到新电脑
2. 解压到任意目录
3. 双击 `启动SnapSort.command`（macOS）或运行 `run.bat`（Windows）

启动脚本会自动：
- 查找带 Tk 8.6+ 的 Python（没有会提示安装）
- 安装所有依赖（customtkinter, requests, Pillow 等）
- 安装拖拽支持（tkinterdnd2，可选）
- 启动应用

### 方法 C：从 GitHub 克隆

```bash
git clone https://github.com/qiao23333/SnapSort.git
cd SnapSort
bash run.sh
```

### 前提条件

新电脑需要：
- Python 3.10+（自带 Tk 8.6）：https://www.python.org/downloads/
- Ollama（本地 AI 模型）：https://ollama.com/
  - 安装后拉取模型：`ollama pull llava:7b` 或 `ollama pull moondream`
- 网络连接（首次安装依赖需要）

---

## 二、推送到 GitHub

### 1. 在 GitHub 网页创建仓库

1. 打开 https://github.com/new
2. Repository name: `SnapSort`
3. 根据是否希望公开源码选择 Private 或 Public
4. **不要**勾选 "Add a README"（项目已有）
5. 点 Create repository

### 2. 配置 Git 凭据（只需一次）

```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
```

### 3. 添加远程并推送

```bash
cd ~/Desktop/SnapSort素材分类器
git remote add origin https://github.com/qiao23333/SnapSort.git
git push -u origin main
```

首次推送时建议使用 Git Credential Manager 或 GitHub CLI 完成登录。

### 4. 安全登录

推荐安装 GitHub CLI 后执行 `gh auth login`。不要把访问令牌写入项目文件、迁移说明或聊天记录；如果令牌曾以明文保存，请立即在 GitHub 设置中撤销并重新创建。

---

## 三、新电脑首次运行检查清单

- [ ] Python 3.10+ 已安装
- [ ] Ollama 已安装并拉取模型
- [ ] 双击 `启动SnapSort.command` 能打开应用
- [ ] 侧栏导航正常（仪表盘/自动分类/素材预览/工具/历史/设置）
- [ ] 点击副标题 5 次能进入开发者面板
- [ ] 事件模式双进度条正常显示
- [ ] 切换页面时侧栏任务指示器可见
