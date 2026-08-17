#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SnapSort 主题配置 — 安静质感风格

设计理念：
- 主按钮用纯黑反色（参考 Polestar/沃尔沃 P 按钮逻辑）
- 琥珀色点缀仅用于 AI 状态/活跃标签（参考录音机界面 5% 面积原则）
- 中性灰为主，色彩克制，靠字号/字重/留白做层级
"""

COLORS = {
    "bg": "#F5F5F7",          # 窗口背景 — 浅银灰
    "sidebar": "#FFFFFF",      # 侧边栏背景
    "card": "#FFFFFF",         # 卡片背景
    "primary": "#1D1D1F",      # 主按钮 — 纯黑（P 按钮逻辑）
    "primary_hover": "#3A3A3A",
    "primary_active": "#000000",
    "accent": "#D97706",       # 琥珀色 — AI 状态/活跃标签专用
    "accent_hover": "#B45309",
    "accent_light": "#FEF3E2", # 琥珀色浅底
    "text": "#1D1D1F",         # 主文字
    "text_secondary": "#86868B",  # 次要文字 — 冷灰
    "border": "#D1D1D6",       # 边框
    "border_light": "#E8E8ED", # 浅色边框
    "success": "#34C759",      # 成功绿
    "warning": "#D97706",      # 警告 — 与 accent 同色
    "danger": "#E0455B",       # 错误红
    "info": "#5AC8FA",         # 信息蓝
    "hover": "#F2F2F7",        # hover 背景
    "selected": "#EDEDF0",     # 选中背景 — 中性灰，不带蓝色调
}

import platform

_PLATFORM = platform.system()

if _PLATFORM == "Darwin":
    _SANS = "SF Pro Display"
    _SANS_TEXT = "SF Pro Text"
    _CJK = "PingFang SC"
    _MONO = "SF Mono"
elif _PLATFORM == "Windows":
    _SANS = "Segoe UI"
    _SANS_TEXT = "Segoe UI"
    _CJK = "Microsoft YaHei"
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


# 通用样式配置（用于 customtkinter）
def apply_root_theme(root):
    root.configure(fg_color=COLORS["bg"])
    try:
        import os
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "snapsort_icon.png")
        if os.path.exists(icon_path):
            from PIL import ImageTk
            icon = ImageTk.PhotoImage(file=icon_path)
            root.iconphoto(True, icon)
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
    style["text_color"] = COLORS["text"]
    style["hover_color"] = COLORS["selected"]
    style["font"] = font_safe(14, "bold")
    return style


def primary_button_style():
    """主按钮 — 纯黑底白字，P 按钮反色逻辑"""
    return {
        "corner_radius": 12,
        "fg_color": COLORS["primary"],
        "hover_color": COLORS["primary_hover"],
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
    """分段按钮 — 活跃态用黑色，非活跃态用白底"""
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
