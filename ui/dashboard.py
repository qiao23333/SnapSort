#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仪表盘页面：问候头部 + AI 状态胶囊 + 主行动卡(含近7日趋势) + 统计卡 + 最近任务"""
import os
import threading
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.image_utils import format_size, image_count_and_size
from core.paths import desktop_dir
from core.usage_report import export_usage_report
from ui.theme import (
    COLORS,
    card_frame_style,
    font_safe,
    primary_button_style,
    secondary_button_style,
)
from ui.widgets import StatCard, safe_after


def _greeting():
    h = datetime.now().hour
    if 5 <= h < 11:
        return "早上好"
    if 11 <= h < 14:
        return "中午好"
    if 14 <= h < 18:
        return "下午好"
    return "晚上好"


class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.configure(fg_color=COLORS["bg"])
        self._build_ui()
        self.refresh_stats()
        self.check_ai_status()

    # ─────────────────────── 界面构建 ───────────────────────

    def _build_ui(self):
        # ── 问候头部：左侧问候语+日期，右侧 Ollama 状态胶囊 ──
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=32, pady=(26, 4))

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left")
        week = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.now().weekday()]
        date_str = datetime.now().strftime("%m月%d日") + f" · {week}"
        ctk.CTkLabel(left, text=f"{_greeting()}，准备好整理素材了吗？",
                     font=font_safe(26, "bold"), text_color=COLORS["text"]
                     ).pack(anchor="w")
        ctk.CTkLabel(left, text=date_str, font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(2, 0))

        # AI 状态胶囊（在线→管理模型，离线→弹出安装向导）
        self.ai_pill = ctk.CTkButton(
            header, text="AI 检测中…", width=150, height=32, corner_radius=16,
            fg_color=COLORS["accent_light"], hover_color=COLORS["accent_light"],
            text_color=COLORS["accent"], font=font_safe(12, "bold"),
            command=self._on_ai_pill_click)
        self.ai_pill.pack(side="right", pady=(8, 0))

        # ── 主行动卡：左侧开始整理 + 路径，右侧近7日趋势图 ──
        hero = ctk.CTkFrame(self, **card_frame_style())
        hero.pack(fill="x", padx=32, pady=(16, 20))

        hero_left = ctk.CTkFrame(hero, fg_color="transparent")
        hero_left.pack(side="left", fill="both", expand=True, padx=(24, 12), pady=20)

        self.last_run_label = ctk.CTkLabel(
            hero_left, text="还没有整理记录，从第一次开始吧", font=font_safe(13, "normal"),
            text_color=COLORS["text_secondary"])
        self.last_run_label.pack(anchor="w", pady=(0, 10))

        btns = ctk.CTkFrame(hero_left, fg_color="transparent")
        btns.pack(anchor="w")
        ctk.CTkButton(btns, text="开始整理素材",
                      command=lambda: self.app.show_page("auto_sort"),
                      **primary_button_style()).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btns, text="选择素材文件夹", command=self._choose_input,
                      **secondary_button_style()).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btns, text="打开输出文件夹",
                      command=self.app.open_output_folder,
                      **secondary_button_style()).pack(side="left")

        # 近7日处理量趋势（Canvas 迷你柱状图）
        trend_frame = ctk.CTkFrame(hero, fg_color="transparent")
        trend_frame.pack(side="right", padx=(4, 24), pady=20)
        ctk.CTkLabel(trend_frame, text="近 7 日处理量", font=font_safe(12, "bold"),
                     text_color=COLORS["text_secondary"]).pack(anchor="e")
        self.trend_canvas = ctk.CTkCanvas(trend_frame, width=230, height=96,
                                          bg=COLORS["card"], highlightthickness=0)
        self.trend_canvas.pack()

        # ── 统计卡片区 ──
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=32, pady=(0, 20))
        cards_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.stat_total = StatCard(cards_frame, title="累计处理", value="0", subtitle="张图片",
                                   icon="累计", width=200, height=120)
        self.stat_total.grid(row=0, column=0, padx=(0, 14), sticky="nsew")

        self.stat_tasks = StatCard(cards_frame, title="分类任务", value="0", subtitle="次",
                                   icon="任务", width=200, height=120)
        self.stat_tasks.grid(row=0, column=1, padx=(0, 14), sticky="nsew")

        self.stat_input = StatCard(cards_frame, title="素材文件夹", value="0", subtitle="张待处理",
                                   icon="待理", width=200, height=120)
        self.stat_input.grid(row=0, column=2, padx=(0, 14), sticky="nsew")

        self.stat_output = StatCard(cards_frame, title="输出文件夹", value="0", subtitle="张已分类",
                                    icon="已理", width=200, height=120)
        self.stat_output.grid(row=0, column=3, sticky="nsew")

        # ── 最近任务区 ──
        recent_card = ctk.CTkFrame(self, **card_frame_style())
        recent_card.pack(fill="both", expand=True, padx=32, pady=(0, 28))

        header2 = ctk.CTkFrame(recent_card, fg_color="transparent")
        header2.pack(fill="x", padx=24, pady=(18, 10))
        ctk.CTkLabel(header2, text="最近任务", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(header2, text="查看全部", command=lambda: self.app.show_page("history"),
                      fg_color="transparent", hover_color=COLORS["hover"],
                      text_color=COLORS["primary"], font=font_safe(12, "normal"),
                      width=70, height=28).pack(side="right")
        ctk.CTkButton(
            header2, text="导出使用报告", command=self._export_usage_report,
            fg_color="transparent", hover_color=COLORS["hover"],
            text_color=COLORS["primary"], font=font_safe(12, "normal"),
            width=100, height=28,
        ).pack(side="right", padx=(0, 8))

        self.recent_list = ctk.CTkFrame(recent_card, fg_color="transparent")
        self.recent_list.pack(fill="both", expand=True, padx=24, pady=(0, 18))

    # ─────────────────────── AI 状态 ───────────────────────

    def check_ai_status(self):
        """后台检测 Ollama 可用性，回填状态胶囊"""
        self._set_pill("AI 检测中…", COLORS["accent_light"], COLORS["accent"])

        def _check():
            from core.sorter_engine import check_ollama
            ok = check_ollama()
            def _apply():
                if ok:
                    self._set_pill(
                        "AI 在线 · 管理模型", COLORS["success_light"], COLORS["success"])
                else:
                    self._set_pill(
                        "AI 离线 · 安装", COLORS["danger_light"], COLORS["danger"])
            safe_after(self, _apply)

        threading.Thread(target=_check, daemon=True).start()

    def _on_ai_pill_click(self):
        """点击 AI 状态胶囊：在线则管理模型，离线则弹出安装向导"""
        from core.sorter_engine import check_ollama
        if check_ollama():
            self.check_ai_status()
        else:
            from ui.ollama_wizard import OllamaWizard
            OllamaWizard(self.app.root, self.app, on_success=self.check_ai_status)

    def _set_pill(self, text, bg, fg):
        try:
            self.ai_pill.configure(text=text, fg_color=bg, text_color=fg)
        except Exception:
            pass

    # ─────────────────────── 数据刷新 ───────────────────────

    def _choose_input(self):
        path = filedialog.askdirectory(
            initialdir=self.app.config_manager.get("last_input") or str(desktop_dir()))
        if path:
            self.app.input_var.set(path)
            self.app.config_manager.set("last_input", path)
            self.refresh_stats()

    def _export_usage_report(self):
        from core.history import HistoryManager

        path = filedialog.asksaveasfilename(
            title="导出 SnapSort 使用报告",
            initialdir=str(desktop_dir()),
            initialfile="SnapSort_使用报告.md",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            export_usage_report(HistoryManager().get_all(), path)
            messagebox.showinfo("导出完成", "使用报告已生成，不包含图片名和本地路径。")
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc))

    def refresh_stats(self):
        # 历史统计
        from core.history import HistoryManager
        records = HistoryManager().get_all()
        total_images = sum(r.get("total", 0) for r in records)
        total_tasks = len(records)

        self.stat_total.update_value(value=str(total_images))
        self.stat_tasks.update_value(value=str(total_tasks))

        # 上次整理提示
        if records:
            r = records[0]
            self.last_run_label.configure(
                text=f"上次整理：{r.get('time', '')} · 处理 {r.get('total', 0)} 张 · 耗时 {r.get('elapsed', 0)}s")
        else:
            self.last_run_label.configure(text="还没有整理记录，从第一次开始吧")

        self._draw_trend(records)

        # 输入/输出统计（目录可能很大，放后台线程统计，避免卡死界面）
        input_dir = self.app.input_var.get()
        output_dir = self.app.output_var.get()
        self.stat_input.update_value(value="…", subtitle="统计中")
        self.stat_output.update_value(value="…", subtitle="统计中")

        def _scan_dirs():
            in_count, in_size = (image_count_and_size(input_dir)
                                 if os.path.isdir(input_dir) else (None, None))
            out_count, out_size = (image_count_and_size(output_dir)
                                   if os.path.isdir(output_dir) else (None, None))

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

    # ─────────────────────── 趋势图 ───────────────────────

    def _draw_trend(self, records):
        """近7日每日处理量迷你柱状图（Canvas 绘制）"""
        try:
            self.trend_canvas.delete("all")
        except Exception:
            return

        days = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
        daily = {d: 0 for d in days}
        for r in records:
            t = (r.get("time") or "")[:10]
            if t in daily:
                daily[t] += r.get("total", 0)

        w, h = 230, 96
        pad_b, gap = 16, 8
        bar_w = (w - gap * 8) / 7
        top = sum(daily.values())
        self.trend_canvas.create_text(
            w - 2, 2, anchor="ne", text=f"共 {top} 张",
            font=font_safe(9), fill=COLORS["text_secondary"])

        if top == 0:
            self.trend_canvas.create_text(
                w / 2, h / 2, text="暂无数据", font=font_safe(10),
                fill=COLORS["text_secondary"])
            return

        max_v = max(daily.values()) or 1
        for i, d in enumerate(days):
            v = daily[d]
            bh = max(3, int(v / max_v * (h - pad_b - 14))) if v else 2
            x = gap + i * (bar_w + gap)
            y1 = h - pad_b
            y0 = y1 - bh
            color = COLORS["primary"] if v else COLORS["border"]
            self.trend_canvas.create_rectangle(x, y0, x + bar_w, y1, fill=color, width=0)
            self.trend_canvas.create_text(
                x + bar_w / 2, h - 8, text=d[-2:], font=font_safe(8),
                fill=COLORS["text_secondary"])
