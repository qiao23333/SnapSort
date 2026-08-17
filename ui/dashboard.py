#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仪表盘页面"""
import os
import threading
import customtkinter as ctk
from tkinter import filedialog

from ui.theme import COLORS, font_safe, primary_button_style, secondary_button_style, card_frame_style
from ui.widgets import StatCard, safe_after
from core.image_utils import image_count_and_size, format_size


class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.configure(fg_color=COLORS["bg"])
        self._build_ui()
        self.refresh_stats()

    def _build_ui(self):
        # 标题
        ctk.CTkLabel(self, text="仪表盘", font=font_safe(28, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=32, pady=(28, 8))
        ctk.CTkLabel(self, text="欢迎使用 SnapSort，一键整理你的素材照片",
                     font=font_safe(14, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=32, pady=(0, 24))

        # 统计卡片区
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=32, pady=(0, 24))
        cards_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.stat_total = StatCard(cards_frame, title="累计处理", value="0", subtitle="张图片",
                                   icon="📊", width=200, height=130)
        self.stat_total.grid(row=0, column=0, padx=(0, 16), sticky="nsew")

        self.stat_tasks = StatCard(cards_frame, title="分类任务", value="0", subtitle="次",
                                   icon="🚀", width=200, height=130)
        self.stat_tasks.grid(row=0, column=1, padx=(0, 16), sticky="nsew")

        self.stat_input = StatCard(cards_frame, title="素材文件夹", value="0", subtitle="张待处理",
                                   icon="🗂", width=200, height=130)
        self.stat_input.grid(row=0, column=2, padx=(0, 16), sticky="nsew")

        self.stat_output = StatCard(cards_frame, title="输出文件夹", value="0", subtitle="张已分类",
                                   icon="✅", width=200, height=130)
        self.stat_output.grid(row=0, column=3, sticky="nsew")

        # 快速操作区
        action_card = ctk.CTkFrame(self, **card_frame_style())
        action_card.pack(fill="x", padx=32, pady=(0, 24))

        ctk.CTkLabel(action_card, text="快速操作", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(20, 12))

        btn_frame = ctk.CTkFrame(action_card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(0, 20))

        ctk.CTkButton(btn_frame, text="🚀 开始自动分类", command=lambda: self.app.show_page("auto_sort"),
                      **primary_button_style()).pack(side="left", padx=(0, 12))
        ctk.CTkButton(btn_frame, text="🗂 选择素材文件夹", command=self._choose_input,
                      **secondary_button_style()).pack(side="left", padx=(0, 12))
        ctk.CTkButton(btn_frame, text="📂 打开输出文件夹", command=self.app.open_output_folder,
                      **secondary_button_style()).pack(side="left")

        # 最近任务区
        recent_card = ctk.CTkFrame(self, **card_frame_style())
        recent_card.pack(fill="both", expand=True, padx=32, pady=(0, 32))

        header = ctk.CTkFrame(recent_card, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 12))
        ctk.CTkLabel(header, text="最近任务", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(header, text="查看全部", command=lambda: self.app.show_page("history"),
                      fg_color="transparent", hover_color=COLORS["hover"],
                      text_color=COLORS["primary"], font=font_safe(12, "normal"),
                      width=70, height=28).pack(side="right")

        self.recent_list = ctk.CTkFrame(recent_card, fg_color="transparent")
        self.recent_list.pack(fill="both", expand=True, padx=24, pady=(0, 20))

    def _choose_input(self):
        path = filedialog.askdirectory(initialdir=self.app.config_manager.get("last_input", os.path.expanduser("~/Desktop")))
        if path:
            self.app.input_var.set(path)
            self.app.config_manager.set("last_input", path)
            self.refresh_stats()

    def refresh_stats(self):
        # 历史统计
        from core.history import HistoryManager
        history = HistoryManager()
        records = history.get_all()
        total_images = sum(r.get("total", 0) for r in records)
        total_tasks = len(records)

        self.stat_total.update_value(value=str(total_images))
        self.stat_tasks.update_value(value=str(total_tasks))

        # 输入/输出统计（目录可能很大，放后台线程统计，避免卡死界面）
        input_dir = self.app.input_var.get()
        output_dir = self.app.output_var.get()
        self.stat_input.update_value(value="…", subtitle="统计中")
        self.stat_output.update_value(value="…", subtitle="统计中")

        def _scan_dirs():
            if os.path.isdir(input_dir):
                in_count, in_size = image_count_and_size(input_dir)
            else:
                in_count, in_size = None, None
            if os.path.isdir(output_dir):
                out_count, out_size = image_count_and_size(output_dir)
            else:
                out_count, out_size = None, None

            def _apply():
                self.stat_input.update_value(
                    value=str(in_count) if in_count is not None else "0",
                    subtitle=format_size(in_size) if in_size is not None else "路径不存在")
                self.stat_output.update_value(
                    value=str(out_count) if out_count is not None else "0",
                    subtitle=format_size(out_size) if out_size is not None else "尚未生成")

            safe_after(self, _apply)

        threading.Thread(target=_scan_dirs, daemon=True).start()

        # 刷新最近任务
        for widget in self.recent_list.winfo_children():
            widget.destroy()

        recent = records[:5]
        if not recent:
            ctk.CTkLabel(self.recent_list, text="暂无分类记录",
                         font=font_safe(13, "normal"),
                         text_color=COLORS["text_secondary"]).pack(pady=20)
            return

        for r in recent:
            row = ctk.CTkFrame(self.recent_list, fg_color=COLORS["hover"], corner_radius=8, height=56)
            row.pack(fill="x", pady=(0, 8))
            row.pack_propagate(False)

            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="y", padx=16)
            ctk.CTkLabel(left, text=r.get("time", ""), font=font_safe(13, "bold"),
                         text_color=COLORS["text"]).pack(anchor="w")
            ctk.CTkLabel(left, text=f"{r.get('total', 0)} 张 · {r.get('model', '')}",
                         font=font_safe(11, "normal"),
                         text_color=COLORS["text_secondary"]).pack(anchor="w")

            right = ctk.CTkFrame(row, fg_color="transparent")
            right.pack(side="right", fill="y", padx=16)
            summary = ", ".join([f"{k}: {v}" for k, v in r.get("results", {}).items() if v > 0])
            ctk.CTkLabel(right, text=summary[:50] + ("..." if len(summary) > 50 else ""),
                         font=font_safe(12, "normal"),
                         text_color=COLORS["text_secondary"]).pack(side="right")
