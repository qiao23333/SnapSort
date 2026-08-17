# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec 文件 — SnapSort 素材分类器
生成 Windows exe / macOS app，双击即可运行（无需安装 Python）。
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# 收集 customtkinter 的数据文件（主题、字体等）
datas = []
datas += collect_data_files('customtkinter')

# 添加项目内部数据目录
# spec 文件在 packaging/ 目录下，项目根目录是其父目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))

# 确保 data/core/ui 目录被打包
for folder in ['data', 'core', 'ui', 'packaging']:
    folder_path = os.path.join(project_root, folder)
    if os.path.isdir(folder_path):
        datas.append((folder_path, folder))

a = Analysis(
    [os.path.join(project_root, 'app.py')],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=[
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
    icon=None,  # 可添加 icon='assets/icon.ico'
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
        icon=None,
        bundle_identifier='com.snapsort.app',
    )
