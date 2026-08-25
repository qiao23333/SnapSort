#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台资源与用户数据目录。

程序资源随安装包只读分发；配置、缓存、日志和参考照片写入用户目录，
避免 Windows 安装到 Program Files 后无写入权限，也避免把开发者数据打进安装包。
"""
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "SnapSort"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resource_root() -> Path:
    """源码模式返回项目根目录，PyInstaller 模式返回解包资源目录。"""
    return Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def user_data_dir() -> Path:
    """返回适合持久化配置与用户内容的平台目录。"""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_cache_dir() -> Path:
    """返回平台缓存目录；缓存删除后可以自动重建。"""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        path = base / APP_NAME / "Cache"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Caches" / APP_NAME
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def desktop_dir() -> Path:
    """返回系统桌面目录，兼容 Windows 中被 OneDrive/策略重定向的桌面。"""
    if sys.platform == "win32":
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "Desktop")
            return Path(os.path.expandvars(value)).expanduser()
        except (OSError, ImportError):
            pass
    return Path.home() / "Desktop"


def migrate_legacy_file(filename: str, destination: Path) -> None:
    """首次运行时迁移旧版项目 data/ 中的个人文件。"""
    if destination.exists() or getattr(sys, "frozen", False):
        return
    legacy = PROJECT_ROOT / "data" / filename
    if legacy.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, destination)
