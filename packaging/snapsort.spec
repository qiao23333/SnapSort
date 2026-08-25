# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec 文件 — SnapSort 素材分类器
生成 Windows exe / macOS app，双击即可运行（无需安装 Python）。
"""

import os
import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# 收集 customtkinter 的数据文件（主题、字体等）
datas, binaries, hiddenimports = collect_all('customtkinter')

# tkinterdnd2 还需要其原生 tkdnd 二进制文件，只有 hidden import 不够。
try:
    dnd_datas, dnd_binaries, dnd_hidden = collect_all('tkinterdnd2')
    datas += dnd_datas
    binaries += dnd_binaries
    hiddenimports += dnd_hidden
except Exception:
    pass

# 添加项目内部数据目录
# spec 文件在 packaging/ 目录下，项目根目录是其父目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))

# 只打包只读资源。严禁把 data/ 整体加入安装包，其中可能有用户配置、
# 人物参考照片、日志和缩略图缓存。
for filename in ['snapsort_icon.png', 'snapsort_icon_small.png', 'snapsort_icon_minimal.png']:
    source = os.path.join(project_root, 'data', filename)
    if os.path.isfile(source):
        datas.append((source, 'data'))

if sys.platform == 'win32':
    icon_candidate = os.path.join(project_root, 'data', 'snapsort_icon.ico')
else:
    icon_candidate = os.path.join(project_root, 'data', 'snapsort_icon.icns')
icon_path = icon_candidate if os.path.isfile(icon_candidate) else None

a = Analysis(
    [os.path.join(project_root, 'app.py')],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
        'customtkinter',
        'customtkinter.windows',
        'customtkinter.windows.widgets',
        'customtkinter.windows.widgets.theme',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.ImageFilter',
        'PIL.ImageDraw',
        'pillow_heif',
        'requests',
        'openpyxl',
        'tkinterdnd2',
        'send2trash',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test', 'unittest', 'pydoc', 'doctest'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# onedir 模式：启动更快，适合桌面应用
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SnapSort',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 无控制台窗口
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SnapSort',
)

# macOS .app 打包（仅 macOS 上构建时生效）
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='SnapSort.app',
        icon=icon_path,
    bundle_identifier='com.snapsort.app',
    )
