#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史记录页面"""
import os
import platform
import subprocess
from tkinter import messagebox

import customtkinter as ctk

from core.history import HistoryManager
from ui.theme import COLORS, card_frame_style, font_safe, secondary_button_style


class HistoryPage(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.configure(fg_color=COLORS["bg"])
        self.history = HistoryManager()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        ctk.CTkLabel(self, text="历史记录", font=font_safe(28, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=32, pady=(28, 8))
        ctk.CTkLabel(self, text="查看每一次分类任务的详情",
                     font=font_safe(14, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=32, pady=(0, 20))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(anchor="w", padx=32, pady=(0, 16))
        ctk.CTkButton(btn_frame, text="刷新", command=self.refresh,
                      **secondary_button_style()).pack(side="left", padx=(0, 12))
        ctk.CTkButton(btn_frame, text="清空历史", command=self._clear_all,
                      fg_color=COLORS["danger"], hover_color="#E6352B",
                      text_color="white", font=font_safe(13, "bold"),
                      height=36).pack(side="left")

        # 列表区
        self.list_card = ctk.CTkFrame(self, **card_frame_style())
        self.list_card.pack(fill="both", expand=True, padx=32, pady=(0, 32))

        self.list_container = ctk.CTkFrame(self.list_card, fg_color="transparent")
        self.list_container.pack(fill="both", expand=True, padx=24, pady=20)

    def refresh(self):
        for widget in self.list_container.winfo_children():
            widget.destroy()

        records = self.history.get_all()
        if not records:
            ctk.CTkLabel(self.list_container, text="暂无历史记录",
                         font=font_safe(13, "normal"),
                         text_color=COLORS["text_secondary"]).pack(pady=40)
            return

        for r in records:
            row = ctk.CTkFrame(self.list_container, fg_color=COLORS["hover"], corner_radius=8, height=72)
            row.pack(fill="x", pady=(0, 10))
            row.pack_propagate(False)

            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="y", padx=16, pady=10)
            ctk.CTkLabel(left, text=r.get("time", ""), font=font_safe(14, "bold"),
                         text_color=COLORS["text"]).pack(anchor="w")
            ctk.CTkLabel(left, text=f"模型：{r.get('model', '')} ｜ 共 {r.get('total', 0)} 张 ｜ 耗时 {r.get('elapsed', 0)}s",
                         font=font_safe(12, "normal"),
                         text_color=COLORS["text_secondary"]).pack(anchor="w")

            summary = ", ".join([f"{k}: {v}" for k, v in r.get("results", {}).items() if v > 0])
            if summary:
                ctk.CTkLabel(left, text=f"分布：{summary}", font=font_safe(11, "normal"),
                             text_color=COLORS["text_secondary"]).pack(anchor="w")

            right = ctk.CTkFrame(row, fg_color="transparent")
            right.pack(side="right", fill="y", padx=16, pady=10)
            ctk.CTkButton(right, text="打开输出",
                          command=lambda p=r.get("output_dir"): self._open_path(p),
                          **secondary_button_style()).pack(side="right", padx=(8, 0))
            ctk.CTkButton(right, text="删除", width=70, height=30,
                          command=lambda rid=r.get("id"): self._delete(rid),
                          fg_color=COLORS["danger"], hover_color="#E6352B",
                          text_color="white", font=font_safe(12, "normal")).pack(side="right")

    def _open_path(self, path):
        if not path or not os.path.isdir(path):
            messagebox.showwarning("路径不存在", f"输出文件夹不存在：\n{path}")
            return
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _delete(self, rid):
        if messagebox.askyesno("确认删除", "确定删除这条历史记录？"):
            self.history.delete(rid)
            self.refresh()

    def _clear_all(self):
        if messagebox.askyesno("确认清空", "确定清空所有历史记录？此操作不可恢复。"):
            self.history.clear()
            self.refresh()
