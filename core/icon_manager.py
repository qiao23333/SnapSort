#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""应用图标预设、用户图标安装与路径解析。"""

from pathlib import Path

from PIL import Image

from core.paths import resource_path, user_data_dir


ICON_PRESETS = {
    "direct": "snapsort_icon.png",
    "minimal": "snapsort_icon_minimal.png",
}


def selected_icon_path(config_manager):
    """返回当前有效图标；自定义文件失效时安全回退到默认图标。"""
    config = config_manager.get("app_icon", {}) or {}
    preset = config.get("preset", "direct")
    if preset == "custom":
        custom_path = Path(str(config.get("custom_path", "")))
        if custom_path.is_file():
            return custom_path
    filename = ICON_PRESETS.get(preset, ICON_PRESETS["direct"])
    candidate = resource_path("data", filename)
    if candidate.is_file():
        return candidate
    return resource_path("data", ICON_PRESETS["direct"])


def install_custom_icon(source_path, destination_dir=None):
    """验证并复制用户图标到稳定的应用数据目录，同时生成 Windows ICO。"""
    source_path = Path(source_path)
    destination = Path(destination_dir) if destination_dir else user_data_dir() / "icons"
    destination.mkdir(parents=True, exist_ok=True)

    with Image.open(source_path) as opened:
        image = opened.convert("RGBA")
        image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        if image.width < 32 or image.height < 32:
            raise ValueError("图标尺寸至少需要 32×32 像素")
        png_path = destination / "custom_app_icon.png"
        ico_path = destination / "custom_app_icon.ico"
        image.save(png_path, "PNG", optimize=True)
        image.save(
            ico_path,
            "ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
    return png_path, ico_path
