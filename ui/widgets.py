#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复用 UI 组件"""
import customtkinter as ctk

from ui.theme import COLORS, font_safe


def safe_after(widget, callback, delay=0):
    """线程安全 UI 调度：widget 已销毁时静默丢弃。

    CTkFrame 没有 after 方法，通过 winfo_toplevel() 拿到 Tk root 来调度。
    """
    try:
        if widget.winfo_exists():
            widget.winfo_toplevel().after(delay, callback)
    except Exception:
        pass


class StatCard(ctk.CTkFrame):
    """统计卡片"""
    def __init__(self, master, title, value, subtitle="", icon="", **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color=COLORS["card"], corner_radius=12,
                       border_color=COLORS["border_light"], border_width=1)

        self.title_text = title
        self.subtitle_text = subtitle

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(16, 4))

        if icon:
            ctk.CTkLabel(
                top, text=icon, width=42, height=24, corner_radius=7,
                fg_color=COLORS["primary_light"], text_color=COLORS["selected_text"],
                font=font_safe(11, "bold"),
            ).pack(side="left")

        self.value_label = ctk.CTkLabel(self, text=value, font=font_safe(32, "bold"),
                                        text_color=COLORS["text"])
        self.value_label.pack(anchor="w", padx=20)

        self.title_label = ctk.CTkLabel(self, text=title, font=font_safe(13, "normal"),
                                        text_color=COLORS["text_secondary"])
        self.title_label.pack(anchor="w", padx=20, pady=(0, 2))

        self.subtitle_label = ctk.CTkLabel(self, text=subtitle, font=font_safe(11, "normal"),
                                           text_color=COLORS["text_secondary"])
        self.subtitle_label.pack(anchor="w", padx=20, pady=(0, 16))
        self.subtitle_label.pack_forget() if not subtitle else None

    def update_value(self, value=None, subtitle=None):
        if value is not None:
            self.value_label.configure(text=value)
        if subtitle is not None:
            self.subtitle_label.configure(text=subtitle)


class Toast(ctk.CTkToplevel):
    """右上角轻提示：自动淡出销毁"""

    def __init__(self, master, message, duration=2600):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=COLORS["text"], corner_radius=10)

        ctk.CTkLabel(self, text=message, font=font_safe(13, "normal"),
                     text_color="white", fg_color="transparent").pack(padx=18, pady=10)

        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        x = master.winfo_rootx() + master.winfo_width() - w - 24
        y = master.winfo_rooty() + 16
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._alpha = 1.0
        self.after(duration, self._fade_out)

    def _fade_out(self):
        self._alpha -= 0.1
        if self._alpha <= 0:
            self.destroy()
            return
        try:
            self.attributes("-alpha", self._alpha)
        except Exception:
            self.destroy()
            return
        self.after(30, self._fade_out)
