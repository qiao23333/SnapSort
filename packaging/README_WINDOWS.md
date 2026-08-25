# Windows 打包与分发指南 (v3.4)

> 将 SnapSort 打包为 Windows 下可双击运行的 `.exe` 程序，方便分发给同事或客户。

---

## 一、为什么用 exe 而不是 bat？

v2.3 之前用 `run.bat` 启动，存在以下问题：
- 需要用户已安装 Python + tkinter
- 需要手动 `pip install` 依赖
- 路径/编码问题导致双击后看不到界面

SnapSort 使用 PyInstaller 打包为 **exe**，解决这些问题：
- 用户不需要安装 Python
- 依赖全部打包进 exe
- 双击直接弹出界面
- 界面不需要 Ollama 也能打开（仅 AI 功能需要）
- 配置、日志和缓存写入 `%LOCALAPPDATA%\SnapSort`，不会混入安装目录
- 构建只包含只读图标资源，不会把开发者的照片或配置打进安装包

---

## 二、打包步骤

### 1. 准备 Windows 电脑

- Windows 10/11 64位
- 已安装 Python 3.10-3.12（仅打包时需要，用户不需要）
- 8GB 以上内存

### 2. 获取源码

将 `SnapSort素材分类器` 整个文件夹复制到 Windows 电脑。

### 3. 一键打包

```bat
cd SnapSort素材分类器
packaging\build_windows.bat
```

脚本会自动：
1. 创建虚拟环境
2. 安装所有依赖 + PyInstaller
3. 清理旧构建
4. 使用 `snapsort.spec` 打包
5. 输出到 `dist\SnapSort\`

### 4. 手动打包（如果脚本失败）

```powershell
cd SnapSort素材分类器
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm packaging\snapsort.spec
```

---

## 三、分发给用户

### 方案 A：文件夹 ZIP（推荐）

```powershell
Compress-Archive -Path dist\SnapSort -DestinationPath SnapSort_Windows.zip
```

用户解压后，双击 `SnapSort.exe` 即可运行。

### 方案 B：安装程序

使用 [Inno Setup](https://jrsoftware.org/isinfo.php) 制作安装向导。

---

## 四、用户环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 64位 |
| Python | **不需要**，已打包进 exe |
| Ollama | 仅使用 AI 功能时需要安装 |
| 内存 | 8GB+，llava:13b 建议 16GB |
| 磁盘空间 | 当前程序约 70MB + 模型空间（取决于所选模型） |

### 用户安装 Ollama（仅 AI 功能需要）

1. 下载 [Ollama for Windows](https://ollama.com/download/windows)
2. 打开 CMD/PowerShell，下载模型：
   ```powershell
   ollama pull llava:13b
   ```
3. 确保 Ollama 在后台运行

### 不需要 Ollama 的功能

- ✅ 位图转矢量（photo/silhouette/edge 三种模式）
- ✅ 重复图片检测
- ✅ 素材库浏览
- ✅ 历史记录
- ✅ 设置管理

---

## 五、常见问题

**Q: 用户双击 exe 后闪退？**
A: 
1. 确认 Windows 10/11 64位
2. 检查杀毒软件是否拦截
3. 从 CMD 运行 `SnapSort.exe` 查看错误信息

**Q: 打包后文件很大？**
A: 正常。PyInstaller 打包了 Python 运行时和依赖，当前构建约 70MB，后续会随依赖变化。使用 `--onedir`（spec 默认）比 `--onefile` 启动快。

**Q: 界面打不开，提示 tkinter 错误？**
A: v3.4 的 exe 打包已包含 tkinter。如果使用源码模式（run.bat），需要确保 Python 安装时勾选了 tcl/tk。

**Q: 模型列表为空？**
A: 说明 Ollama 未运行或未安装模型。先安装 Ollama 并 `ollama pull llava:13b`。
