#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SnapSort 主题配置 — 清爽、克制的跨平台浅色主题。

设计理念：
- 黑色用于主操作，Apple 蓝用于导航、选择和进度反馈
- 琥珀色仅用于 AI 状态，避免所有功能都挤在同一种颜色里
- 中性灰负责背景和边界，让 Windows 与 macOS 都保持轻盈
"""

import platform
from pathlib import Path

COLORS = {
    "bg": "#F5F5F7",          # 窗口背景 — 浅银灰
    "sidebar": "#FFFFFF",      # 侧边栏背景
    "card": "#FFFFFF",         # 卡片背景
    "primary": "#0071E3",      # 通用交互色 — 延续旧版 Mac 的 Apple 蓝
    "primary_hover": "#0066CC",
    "primary_active": "#0057B8",
    "primary_light": "#E8F4FD",
    "action": "#1D1D1F",       # 主操作按钮 — 黑色，避免与导航状态混淆
    "action_hover": "#333336",
    "accent": "#D97706",       # 琥珀色 — AI 状态/活跃标签专用
    "accent_hover": "#B45309",
    "accent_light": "#FEF3E2", # 琥珀色浅底
    "text": "#1D1D1F",         # 主文字
    "text_secondary": "#86868B",  # 次要文字 — 冷灰
    "border": "#D1D1D6",       # 边框
    "border_light": "#E8E8ED", # 浅色边框
    "success": "#34C759",      # 成功绿
    "success_light": "#EAF8EE",
    "warning": "#D97706",      # 警告 — 与 accent 同色
    "danger": "#E0455B",       # 错误红
    "danger_light": "#FDECEF",
    "info": "#0071E3",         # 信息蓝
    "hover": "#F2F2F7",        # hover 背景
    "selected": "#E8F4FD",     # 选中背景 — 淡蓝，强化当前位置
    "selected_text": "#0066CC",
}

from core.paths import resource_path

_PLATFORM = platform.system()

if _PLATFORM == "Darwin":
    _SANS = "SF Pro Display"
    _SANS_TEXT = "SF Pro Text"
    _CJK = "PingFang SC"
    _MONO = "SF Mono"
elif _PLATFORM == "Windows":
    # Tk 不支持 CSS 式字体回退列表。界面以中文为主，因此直接使用
    # Windows 自带的 UI 字体，避免 Segoe UI → 微软雅黑临时回退造成
    # 同一行基线、字重和行高不一致。
    _SANS = "Microsoft YaHei UI"
    _SANS_TEXT = "Microsoft YaHei UI"
    _CJK = "Microsoft YaHei UI"
    _MONO = "Cascadia Code"
else:
    _SANS = "Noto Sans"
    _SANS_TEXT = "Noto Sans"
    _CJK = "Noto Sans CJK SC"
    _MONO = "monospace"

FONTS = {
    "family": _SANS,
    "family_text": _SANS_TEXT,
    "fallback": _CJK,
    "fallback2": _CJK,
    "mono": _MONO,
}


def font(size=13, weight="normal"):
    """获取字体元组"""
    return (_SANS, size, weight)


def font_text(size=13, weight="normal"):
    return (_SANS_TEXT, size, weight)


def font_fallback(size=13, weight="normal"):
    return (_CJK, size, weight)


def font_safe(size=13, weight="normal"):
    """跨平台安全字体"""
    return (_SANS, size, weight)


def font_mono(size=12, weight="normal"):
    """日志、代码和固定宽度数据使用的平台原生等宽字体。"""
    return (_MONO, size, weight)


# 通用样式配置（用于 customtkinter）
def apply_root_theme(root, selected_icon=None):
    root.configure(fg_color=COLORS["bg"])
    try:
        icon_path = Path(selected_icon) if selected_icon else resource_path(
            "data", "snapsort_icon.png")
        if icon_path.exists():
            from PIL import Image, ImageTk

            with Image.open(icon_path) as opened:
                source = opened.convert("RGBA")
            icons = [
                ImageTk.PhotoImage(source.resize((size, size), Image.Resampling.LANCZOS))
                for size in (16, 24, 32, 48, 64, 128, 256)
            ]
            root.iconphoto(True, *icons)
            # Tk 必须持有引用，否则图片会被垃圾回收，标题栏会退回默认图标。
            root._snapsort_icon_images = icons
    except Exception:
        pass


def sidebar_button_style():
    return {
        "width": 200,
        "height": 42,
        "corner_radius": 10,
        "fg_color": "transparent",
        "hover_color": COLORS["hover"],
        "text_color": COLORS["text"],
        "font": font_safe(14, "normal"),
        "anchor": "w",
        "compound": "left",
    }


def sidebar_button_active_style():
    style = sidebar_button_style()
    style["fg_color"] = COLORS["selected"]
    style["text_color"] = COLORS["selected_text"]
    style["hover_color"] = COLORS["selected"]
    style["font"] = font_safe(14, "bold")
    return style


def primary_button_style():
    """主按钮 — 黑底白字；蓝色只负责导航、进度和链接状态。"""
    return {
        "corner_radius": 12,
        "fg_color": COLORS["action"],
        "hover_color": COLORS["action_hover"],
        "text_color": "white",
        "font": font_safe(13, "bold"),
        "height": 38,
    }


def secondary_button_style():
    """次按钮 — 白底灰边框"""
    return {
        "corner_radius": 12,
        "fg_color": COLORS["card"],
        "hover_color": COLORS["hover"],
        "text_color": COLORS["text"],
        "border_color": COLORS["border"],
        "border_width": 1,
        "font": font_safe(13, "normal"),
        "height": 38,
    }


def accent_button_style():
    """琥珀色按钮 — 仅用于 AI 状态相关操作"""
    return {
        "corner_radius": 12,
        "fg_color": COLORS["accent"],
        "hover_color": COLORS["accent_hover"],
        "text_color": "white",
        "font": font_safe(13, "bold"),
        "height": 38,
    }


def card_frame_style():
    return {
        "fg_color": COLORS["card"],
        "corner_radius": 12,
        "border_color": COLORS["border_light"],
        "border_width": 1,
    }


def segmented_button_style(active=False):
    """分段按钮 — 活跃态用主色，非活跃态用白底。"""
    return {
        "width": 120,
        "height": 32,
        "corner_radius": 8,
        "fg_color": COLORS["primary"] if active else COLORS["card"],
        "hover_color": COLORS["primary_hover"] if active else COLORS["hover"],
        "text_color": "white" if active else COLORS["text"],
        "border_color": COLORS["border_light"],
        "border_width": 0 if active else 1,
        "font": font_safe(12, "bold" if active else "normal"),
    }
