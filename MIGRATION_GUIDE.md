# SnapSort v3.2.2 迁移指南

## 一、迁移到新电脑

### 方法 A：用迁移包（推荐）

1. 将 `SnapSort_v3.2.2_迁移包.zip` 拷贝到新电脑（U盘/AirDrop/云盘）
2. 解压到任意目录
3. 双击 `启动SnapSort.command`（macOS）或运行 `bash run.sh`

启动脚本会自动：
- 查找带 Tk 8.6+ 的 Python（没有会提示安装）
- 安装所有依赖（customtkinter, requests, Pillow 等）
- 安装拖拽支持（tkinterdnd2，可选）
- 启动应用

### 方法 B：从 GitHub 克隆

```bash
git clone https://github.com/你的用户名/SnapSort.git
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
3. 选 Private 或 Public（作品集建议 Public）
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
git remote add origin https://github.com/你的用户名/SnapSort.git
git push -u origin main
```

首次推送时会弹出登录窗口，输入 GitHub 账号密码或 Personal Access Token。

### 4. 获取 Token（如果密码不工作）

GitHub 已不支持密码推送，需要 Token：
1. 打开 https://github.com/settings/tokens
2. Generate new token (classic)
3. 勾选 `repo` 权限
4. 复制 token，推送时密码栏粘贴 token

---

## 三、新电脑首次运行检查清单

- [ ] Python 3.10+ 已安装
- [ ] Ollama 已安装并拉取模型
- [ ] 双击 `启动SnapSort.command` 能打开应用
- [ ] 侧栏导航正常（仪表盘/自动分类/素材预览/工具/历史/设置）
- [ ] 点击副标题 5 次能进入开发者面板
- [ ] 事件模式双进度条正常显示
- [ ] 切换页面时侧栏任务指示器可见
