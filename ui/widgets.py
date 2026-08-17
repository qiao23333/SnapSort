#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复用 UI 组件"""
import customtkinter as ctk
from ui.theme import COLORS, font_safe


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

        ctk.CTkLabel(top, text=icon, font=("Apple Color Emoji", 24)).pack(side="left")

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
            self.subtitle_label.pack(anchor="w", padx=20, pady=(0, 16))
