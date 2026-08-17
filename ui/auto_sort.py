#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动分类页面 — 双模式：按内容分类 / 按事件整理(日期→事件→分级→重命名)
"""
import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog

from ui.theme import COLORS, font_safe, primary_button_style, secondary_button_style, card_frame_style
from core.image_utils import is_image_file
from core.sorter_engine import SorterEngine, fetch_ollama_models, get_processed_files, optimize_prompt
from core.model_info import get_model_hint, get_model_role_tag
from core.event_classifier import (
    EventPipeline, Checkpoint, scan_photos, group_by_date, BatchRenamer, EventAnalyzer
)


class AutoSortPage(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.configure(fg_color=COLORS["bg"])
        self.engine = None
        self.sort_thread = None
        self._mode = "category"
        self._build_ui()
        self._refresh_model_list()

    # ═══════════════════════════════════════
    #  UI — 头部共享：模式切换 + 模型选择
    # ═══════════════════════════════════════

    def _build_ui(self):
        ctk.CTkLabel(self, text="智能分类", font=font_safe(28, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=32, pady=(28, 6))

        top = ctk.CTkFrame(self, **card_frame_style())
        top.pack(fill="x", padx=32, pady=(0, 14))

        r1 = ctk.CTkFrame(top, fg_color="transparent")
        r1.pack(fill="x", padx=24, pady=(16, 8))
        self.mode_seg = ctk.CTkSegmentedButton(r1, values=["按内容分类", "按事件整理"],
                                                command=self._switch_mode,
                                                font=font_safe(13, "normal"),
                                                selected_color=COLORS["primary"],
                                                selected_hover_color=COLORS["primary_hover"],
                                                unselected_color=COLORS["card"])
        self.mode_seg.pack(side="left")
        self.mode_seg.set("按内容分类")
        self.mode_desc = ctk.CTkLabel(r1, text="AI 识别内容，自动分到对应文件夹",
                                      font=font_safe(12),
                                      text_color=COLORS["text_secondary"])
        self.mode_desc.pack(side="left", padx=(16, 0))

        r2 = ctk.CTkFrame(top, fg_color="transparent")
        r2.pack(fill="x", padx=24, pady=(4, 14))
        ctk.CTkLabel(r2, text="AI模型", font=font_safe(13),
                     text_color=COLORS["text_secondary"]).pack(side="left")
        self.model_var = ctk.StringVar(value=self.app.config_manager.get("model", "llava:13b"))
        self.model_combo = ctk.CTkOptionMenu(r2, variable=self.model_var,
                                             values=["加载中..."], width=200, height=34,
                                             font=font_safe(13),
                                             dropdown_font=font_safe(13))
        self.model_combo.pack(side="left", padx=(10, 10))
        ctk.CTkButton(r2, text="🔄", command=self._refresh_model_list, width=36, height=34,
                      fg_color=COLORS["card"], hover_color=COLORS["hover"],
                      text_color=COLORS["text"]).pack(side="left", padx=(0, 20))
        self.model_hint = ctk.CTkLabel(r2, text="", font=font_safe(11),
                                       text_color=COLORS["text_secondary"])
        self.model_hint.pack(side="left")

        # ── 内容区（可滚动，事件模式选项多时上下滑动）──
        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True)
        self._build_category()

    def _switch_mode(self, choice):
        self._mode = "category" if choice == "按内容分类" else "event"
        for w in self.content.winfo_children():
            w.destroy()
        if self._mode == "category":
            self.mode_desc.configure(text="AI 识别内容，自动分到对应文件夹")
            self._build_category()
        else:
            self.mode_desc.configure(text="按日期分组 → AI命名事件 → ABC分级 → 批量重命名")
            self._build_event()

    # ═══════════════════════════════════════
    #  分类模式
    # ═══════════════════════════════════════

    def _build_category(self):
        p = self.content

        card = ctk.CTkFrame(p, **card_frame_style())
        card.pack(fill="x", padx=32, pady=(0, 12))
        ctk.CTkLabel(card, text="文件夹", font=font_safe(17, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(16, 8))

        for label, var in [("素材", self.app.input_var), ("输出", self.app.output_var)]:
            r = ctk.CTkFrame(card, fg_color="transparent")
            r.pack(fill="x", padx=24, pady=(0, 8))
            ctk.CTkLabel(r, text=label, font=font_safe(13),
                         text_color=COLORS["text_secondary"], width=40).pack(side="left")
            ctk.CTkEntry(r, textvariable=var, font=font_safe(13), height=34,
                         fg_color=COLORS["bg"],
                         border_color=COLORS["border"]).pack(side="left", fill="x", expand=True, padx=(10, 10))
            ctk.CTkButton(r, text="选", command=lambda v=var: self._pick_folder(v), width=40, height=34,
                          font=font_safe(12), fg_color=COLORS["card"], hover_color=COLORS["hover"],
                          text_color=COLORS["text"], corner_radius=8).pack(side="left")

        cfg = ctk.CTkFrame(card, fg_color="transparent")
        cfg.pack(fill="x", padx=24, pady=(4, 14))
        self.inc_var = ctk.BooleanVar(value=self.app.config_manager.get("incremental", True))
        ctk.CTkCheckBox(cfg, text="增量（跳过已处理）", variable=self.inc_var,
                        font=font_safe(13), text_color=COLORS["text"],
                        fg_color=COLORS["primary"],
                        hover_color=COLORS["primary_hover"]).pack(side="left")
        ctk.CTkLabel(cfg, text="分类", font=font_safe(13),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(24, 6))
        for cat in self.app.config_manager.get("categories", {}):
            ctk.CTkLabel(cfg, text=cat, font=font_safe(11),
                         fg_color=COLORS["selected"], text_color=COLORS["primary"],
                         corner_radius=5, padx=8, pady=3).pack(side="left", padx=(0, 4))

        # 人物识别状态指示
        known_persons = self.app.config_manager.get("known_persons", []) or []
        person_on = self.app.config_manager.get("person_recognition", True) and bool(known_persons)
        if person_on:
            names = "、".join(p.get("name", "") for p in known_persons[:4])
            more = f" 等{len(known_persons)}人" if len(known_persons) > 4 else ""
            ctk.CTkLabel(cfg, text=f"👤 人物识别：{names}{more}",
                         font=font_safe(11), fg_color=COLORS["selected"],
                         text_color=COLORS["primary"], corner_radius=5, padx=8, pady=3).pack(
                             side="left", padx=(12, 0))
        elif not known_persons:
            ctk.CTkLabel(cfg, text="👤 人物识别：未设置（设置→已知人物）",
                         font=font_safe(11), fg_color=COLORS["hover"],
                         text_color=COLORS["text_secondary"], corner_radius=5, padx=8, pady=3).pack(
                             side="left", padx=(12, 0))

        # 地点识别状态指示
        known_places = self.app.config_manager.get("known_places", []) or []
        place_on = self.app.config_manager.get("place_recognition", True) and bool(known_places)
        if place_on:
            names = "、".join(p.get("name", "") for p in known_places[:4])
            more = f" 等{len(known_places)}处" if len(known_places) > 4 else ""
            ctk.CTkLabel(cfg, text=f"📍 地点识别：{names}{more}",
                         font=font_safe(11), fg_color=COLORS["selected"],
                         text_color=COLORS["primary"], corner_radius=5, padx=8, pady=3).pack(
                             side="left", padx=(8, 0))
        elif not known_places:
            ctk.CTkLabel(cfg, text="📍 地点识别：未设置（设置→已知地点）",
                         font=font_safe(11), fg_color=COLORS["hover"],
                         text_color=COLORS["text_secondary"], corner_radius=5, padx=8, pady=3).pack(
                             side="left", padx=(8, 0))

        prog = ctk.CTkFrame(p, **card_frame_style())
        prog.pack(fill="x", padx=32, pady=(0, 12))
        ctk.CTkLabel(prog, text="进度", font=font_safe(17, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(16, 6))
        self.status_var = ctk.StringVar(value="就绪")
        ctk.CTkLabel(prog, textvariable=self.status_var, font=font_safe(13),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=24, pady=(0, 4))
        self.progress_bar = ctk.CTkProgressBar(prog, progress_color=COLORS["primary"],
                                               fg_color=COLORS["border_light"], height=8)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=24, pady=(0, 10))

        bf = ctk.CTkFrame(prog, fg_color="transparent")
        bf.pack(fill="x", padx=24, pady=(0, 16))
        self.btn_start = ctk.CTkButton(bf, text="🚀 开始分类",
                                       command=self._cat_start, **primary_button_style())
        self.btn_start.pack(side="left", padx=(0, 10))
        self.btn_stop = ctk.CTkButton(bf, text="⏹ 停止", command=self._stop,
                                      fg_color=COLORS["danger"], hover_color="#E6352B",
                                      text_color="white", font=font_safe(13, "bold"),
                                      height=36, state="disabled")
        self.btn_stop.pack(side="left", padx=(0, 10))
        ctk.CTkButton(bf, text="📂 打开输出", command=self.app.open_output_folder,
                      **secondary_button_style()).pack(side="left")

        log = ctk.CTkFrame(p, **card_frame_style())
        log.pack(fill="both", expand=True, padx=32, pady=(0, 28))
        ctk.CTkLabel(log, text="日志", font=font_safe(17, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(16, 8))
        self.log_text = scrolledtext.ScrolledText(log, wrap="word",
                                                   font=("SF Mono", 12), bg="#0f172a", fg="#e2e8f0",
                                                   relief="flat", padx=10, pady=10)
        self.log_text.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        self.log_text.config(state="disabled")

    # ═══════════════════════════════════════
    #  事件模式
    # ═══════════════════════════════════════

    def _build_event(self):
        p = self.content

        # ── 步骤指示器 ──
        step_bar = ctk.CTkFrame(p, fg_color="transparent")
        step_bar.pack(fill="x", padx=32, pady=(0, 10))
        steps = [
            ("①", "选文件夹", "选择素材和输出路径"),
            ("②", "配选项", "命名规则、标签、业务背景"),
            ("③", "看结果", "扫描、分析、重命名"),
        ]
        for i, (num, title, desc) in enumerate(steps):
            col = ctk.CTkFrame(step_bar, fg_color="transparent")
            col.pack(side="left", expand=True, fill="x", padx=(0, 8 if i < 2 else 0))
            is_active = (i == 0)
            ctk.CTkLabel(col, text=num, font=font_safe(20, "bold"),
                         text_color=COLORS["primary"] if is_active else COLORS["text_secondary"]).pack(anchor="w")
            ctk.CTkLabel(col, text=title, font=font_safe(13, "bold"),
                         text_color=COLORS["text"] if is_active else COLORS["text_secondary"]).pack(anchor="w")
            ctk.CTkLabel(col, text=desc, font=font_safe(10),
                         text_color=COLORS["text_secondary"]).pack(anchor="w")
            if i < 2:
                ctk.CTkLabel(step_bar, text="→", font=font_safe(16),
                             text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 8))

        # ═══ 1. 文件夹 + 选项（紧凑）═══
        card = ctk.CTkFrame(p, **card_frame_style())
        card.pack(fill="x", padx=32, pady=(0, 10))
        ctk.CTkLabel(card, text="① 选文件夹 & 选项", font=font_safe(15, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(12, 6))

        for label, var in [("素材", self.app.input_var), ("输出", self.app.output_var)]:
            r = ctk.CTkFrame(card, fg_color="transparent")
            r.pack(fill="x", padx=20, pady=(0, 4))
            ctk.CTkLabel(r, text=label, font=font_safe(13),
                         text_color=COLORS["text_secondary"], width=40).pack(side="left")
            ctk.CTkEntry(r, textvariable=var, font=font_safe(13), height=32,
                         fg_color=COLORS["bg"],
                         border_color=COLORS["border"]).pack(side="left", fill="x", expand=True, padx=(8, 8))
            ctk.CTkButton(r, text="选", command=lambda v=var: self._pick_folder(v), width=40, height=32,
                          font=font_safe(12), fg_color=COLORS["card"], hover_color=COLORS["hover"],
                          text_color=COLORS["text"], corner_radius=8).pack(side="left")

        opt_row = ctk.CTkFrame(card, fg_color="transparent")
        opt_row.pack(fill="x", padx=20, pady=(6, 0))
        self.evt_inc = ctk.BooleanVar(value=self.app.config_manager.get("incremental", True))
        ctk.CTkCheckBox(opt_row, text="增量", variable=self.evt_inc,
                        font=font_safe(12), text_color=COLORS["text"],
                        fg_color=COLORS["primary"],
                        hover_color=COLORS["primary_hover"]).pack(side="left")
        self.evt_grade_ck = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt_row, text="ABC 分级", variable=self.evt_grade_ck,
                        font=font_safe(12), text_color=COLORS["text"],
                        fg_color=COLORS["primary"],
                        hover_color=COLORS["primary_hover"]).pack(side="left", padx=(16, 0))
        self.evt_rename_ck = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt_row, text="重命名", variable=self.evt_rename_ck,
                        font=font_safe(12), text_color=COLORS["text"],
                        fg_color=COLORS["primary"],
                        hover_color=COLORS["primary_hover"]).pack(side="left", padx=(16, 0))
        # ── 命名规则：可拖拽变量 + 自定义输入 + 实时预览 ──
        pattern_label_row = ctk.CTkFrame(card, fg_color="transparent")
        pattern_label_row.pack(fill="x", padx=20, pady=(8, 0))
        ctk.CTkLabel(pattern_label_row, text="命名规则", font=font_safe(12, "bold"),
                     text_color=COLORS["text"], width=70).pack(side="left")
        ctk.CTkLabel(pattern_label_row, text="💡 点击标签插入 / 拖拽到输入框 / 直接键盘输入",
                     font=font_safe(10),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(8, 0))

        # 输入框 + 清空按钮
        pattern_row = ctk.CTkFrame(card, fg_color="transparent")
        pattern_row.pack(fill="x", padx=20, pady=(2, 0))
        self.evt_pattern_var = ctk.StringVar(
            value=self.app.config_manager.get("event_mode", {}).get(
                "rename_pattern", "{date}_{event}_{seq:02d}{grade}_{desc}"))
        self.evt_pattern_var.trace_add("write", self._update_pattern_preview)
        self.evt_pattern_entry = ctk.CTkEntry(pattern_row, textvariable=self.evt_pattern_var,
                     font=("SF Mono", 13), height=34,
                     fg_color=COLORS["bg"], border_color=COLORS["border"],
                     border_width=1.5)
        self.evt_pattern_entry.pack(side="left", fill="x", expand=True, padx=(70, 4))
        # 清空按钮
        self._clear_btn = ctk.CTkButton(pattern_row, text="✕ 清空", command=self._clear_pattern,
                      width=56, height=34,
                      font=font_safe(11), fg_color=COLORS["card"], hover_color=COLORS["hover"],
                      text_color=COLORS["text_secondary"], corner_radius=8)
        self._clear_btn.pack(side="left")

        # ── 变量标签（可点击插入 / 拖拽到输入框）──
        self._drag_var = None
        self._drag_active = False
        self._drag_start_x = 0
        self._drag_start_y = 0

        vars_row = ctk.CTkFrame(card, fg_color="transparent")
        vars_row.pack(fill="x", padx=20, pady=(6, 0))
        ctk.CTkLabel(vars_row, text="变量", font=font_safe(11, "bold"),
                     text_color=COLORS["text_secondary"], width=70).pack(side="left")
        chips_frame = ctk.CTkFrame(vars_row, fg_color="transparent")
        chips_frame.pack(side="left", fill="x", expand=True, padx=(0, 0))

        self._pattern_vars = [
            ("{date}",    "📅 日期"),
            ("{event}",   "🏷️ 事件"),
            ("{seq:02d}", "🔢 序号"),
            ("{grade}",   "⭐ 等级"),
            ("{desc}",    "📝 描述"),
            ("{ext}",     "📎 后缀"),
        ]
        self._var_chips = []
        for var_text, label in self._pattern_vars:
            chip = ctk.CTkButton(
                chips_frame,
                text=f"{label} {var_text}",
                width=0, height=28,
                font=font_safe(11),
                fg_color=COLORS.get("selected", "#EDEDF0"),
                hover_color=COLORS.get("primary_hover", "#3A3A3A"),
                text_color=COLORS.get("primary", "#1D1D1F"),
                corner_radius=6,
            )
            chip.pack(side="left", padx=(0, 5), pady=2)
            # 拖拽绑定（不设 command，统一用 release 处理）
            chip.bind("<ButtonPress-1>", lambda e, v=var_text: self._drag_start(e, v))
            chip.bind("<B1-Motion>", self._drag_motion)
            chip.bind("<ButtonRelease-1>", self._drag_release)
            self._var_chips.append(chip)

        # ── 分隔符快捷按钮 ──
        sep_row = ctk.CTkFrame(card, fg_color="transparent")
        sep_row.pack(fill="x", padx=20, pady=(2, 0))
        ctk.CTkLabel(sep_row, text="分隔符", font=font_safe(11),
                     text_color=COLORS["text_secondary"], width=70).pack(side="left")
        sep_frame = ctk.CTkFrame(sep_row, fg_color="transparent")
        sep_frame.pack(side="left", padx=(0, 0))
        for sep_text, sep_label in [("_", "下划线 _"), ("-", "短横 -"), (" ", "空格"),
                                     (".", "点号 ."), ("", "无分隔")]:
            ctk.CTkButton(sep_frame, text=sep_label,
                          command=lambda s=sep_text: self._insert_var(s),
                          width=0, height=24,
                          font=font_safe(10),
                          fg_color=COLORS["card"],
                          hover_color=COLORS["hover"],
                          text_color=COLORS["text_secondary"],
                          corner_radius=5).pack(side="left", padx=(0, 4), pady=2)

        # ── 实时预览 ──
        self.evt_pattern_preview = ctk.CTkLabel(
            card, text="", font=font_safe(12, "bold"),
            text_color=COLORS["primary"], anchor="w")
        self.evt_pattern_preview.pack(fill="x", padx=20, pady=(4, 6))
        self._update_pattern_preview()
        ctk.CTkLabel(card, text="", height=4).pack()  # spacer

        # ═══ 2. 业务背景（可折叠）═══
        self._ctx_collapsed = ctk.BooleanVar(value=False)
        ctx_header = ctk.CTkFrame(card, fg_color="transparent")
        ctx_header.pack(fill="x", padx=20, pady=(4, 0))
        ctk.CTkLabel(ctx_header, text="业务背景（折叠）", font=font_safe(12),
                     text_color=COLORS["text_secondary"]).pack(side="left")
        ctk.CTkButton(ctx_header, text="▸ 展开", command=self._toggle_ctx, width=70, height=24,
                      font=font_safe(11), fg_color="transparent",
                      text_color=COLORS["primary"],
                      hover_color=COLORS["hover"]).pack(side="left", padx=(8, 0))
        self._ctx_expand_btn = ctx_header.winfo_children()[-1]
        self.ctx_text = ctk.CTkTextbox(card, height=60, font=("SF Pro Text", 12),
                                        fg_color=COLORS["bg"],
                                        border_color=COLORS["border"], border_width=1)
        self.ctx_text.pack(fill="x", padx=20, pady=(4, 4))
        # 业务背景：沿用上次编辑内容；若为空则填入默认范例供用户修改
        saved_ctx = self.app.config_manager.get("business_context", "")
        default_ctx = saved_ctx if saved_ctx else (
            "本地通用业务移民公司，负责人是企业用户，"
            "素材用于短视频展示真实雇主实力和本地工作场景。"
        )
        self.ctx_text.insert("1.0", default_ctx)

        # AI 优化提示词按钮 + 状态
        self.opt_prompt_row = ctk.CTkFrame(card, fg_color="transparent")
        self.opt_prompt_row.pack(fill="x", padx=20, pady=(0, 8))
        self.opt_prompt_btn = ctk.CTkButton(
            self.opt_prompt_row, text="✨ AI 优化提示词",
            command=self._optimize_prompt,
            font=font_safe(12, "bold"), fg_color=COLORS.get("accent", "#D97706"),
            hover_color=COLORS.get("accent_hover", "#B45309"), text_color="white", height=30, width=140)
        self.opt_prompt_btn.pack(side="left")
        self.opt_prompt_status = ctk.CTkLabel(
            self.opt_prompt_row, text="", font=font_safe(11),
            text_color=COLORS["text_secondary"])
        self.opt_prompt_status.pack(side="left", padx=(8, 0))
        # 显示是否已有优化提示词
        if self.app.config_manager.get("optimized_prompt", ""):
            self.opt_prompt_status.configure(text="✅ 已有优化提示词", text_color=COLORS["success"])

        # 默认折叠
        self.ctx_text.pack_forget()
        self.opt_prompt_row.pack_forget()

        # ═══ 3. 操作按钮（醒目）═══
        btn_card = ctk.CTkFrame(p, **card_frame_style())
        btn_card.pack(fill="x", padx=32, pady=(0, 10))
        ctk.CTkLabel(btn_card, text="② 开始", font=font_safe(15, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(12, 6))

        inner = ctk.CTkFrame(btn_card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=(0, 6))

        self.evt_run = ctk.CTkButton(inner, text="🚀 一键扫描 + 分析 + 重命名",
                                     command=self._evt_run,
                                     fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                                     text_color="white", font=font_safe(14, "bold"),
                                     height=42, corner_radius=12)
        self.evt_run.pack(side="left", padx=(0, 8), fill="x", expand=True)

        self.evt_force = ctk.CTkButton(inner, text="↻ 强制重跑",
                                        command=self._evt_force,
                                        fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                                        text_color="white", font=font_safe(13, "bold"),
                                        height=42, corner_radius=12, state="disabled")
        self.evt_force.pack(side="left")

        self.evt_stop_btn = ctk.CTkButton(inner, text="⏹", command=self._stop,
                                          fg_color=COLORS["danger"], hover_color="#E6352B",
                                          text_color="white", font=font_safe(13, "bold"),
                                          height=42, width=50, corner_radius=12, state="disabled")
        self.evt_stop_btn.pack(side="left", padx=(8, 0))

        # 撤销按钮（完成后显示，30 秒内可撤销）
        self.evt_undo_btn = ctk.CTkButton(inner, text="↩ 撤销本次整理",
                                          command=self._evt_undo,
                                          fg_color=COLORS["card"], hover_color=COLORS["hover"],
                                          text_color=COLORS["danger"], font=font_safe(13, "bold"),
                                          height=42, width=150, corner_radius=12,
                                          border_color=COLORS["danger"], border_width=1)
        self._undo_after_id = None

        self.evt_status = ctk.StringVar(value="👆 点上面黑色按钮一键开始")
        ctk.CTkLabel(btn_card, textvariable=self.evt_status, font=font_safe(12),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=20, pady=(0, 4))
        self.evt_progress = ctk.CTkProgressBar(btn_card, progress_color=COLORS["primary"],
                                               fg_color=COLORS["border_light"], height=6)
        self.evt_progress.set(0)
        self.evt_progress.pack(fill="x", padx=20, pady=(0, 12))

        # ═══ 4. 规则自定义（可折叠，默认隐藏）═══
        rules_card = ctk.CTkFrame(p, **card_frame_style())
        rules_card.pack(fill="x", padx=32, pady=(0, 10))
        rh = ctk.CTkFrame(rules_card, fg_color="transparent")
        rh.pack(fill="x", padx=20, pady=(12, 4))
        ctk.CTkLabel(rh, text="③ 自定义 ABC 规则 & 重命名（折叠）",
                     font=font_safe(15, "bold"),
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(rh, text="▸ 展开", command=self._toggle_rules, width=70, height=24,
                      font=font_safe(11), fg_color="transparent",
                      text_color=COLORS["primary"],
                      hover_color=COLORS["hover"]).pack(side="left", padx=(8, 0))
        self._rules_expand_btn = rh.winfo_children()[-1]
        self._rules_body = ctk.CTkFrame(rules_card, fg_color="transparent")
        # 默认隐藏，状态保存
        self._rules_collapsed = True

        # ── 标签预设管理 ──
        preset_row = ctk.CTkFrame(self._rules_body, fg_color="transparent")
        preset_row.pack(fill="x", padx=20, pady=(0, 4))
        ctk.CTkLabel(preset_row, text="标签预设", font=font_safe(12, "bold"),
                     text_color=COLORS["text"], width=70).pack(side="left")
        self.preset_var = ctk.StringVar(
            value=self.app.config_manager.get("active_tag_preset", "默认ABC"))
        self.preset_combo = ctk.CTkOptionMenu(preset_row, variable=self.preset_var,
                                               values=list(self.app.config_manager.get("tag_presets", {}).keys()),
                                               width=140, height=28,
                                               font=font_safe(12),
                                               command=self._switch_preset)
        self.preset_combo.pack(side="left", padx=(4, 8))
        ctk.CTkButton(preset_row, text="💾 另存为", command=self._save_preset_as,
                      width=70, height=28, font=font_safe(11),
                      fg_color=COLORS["card"], hover_color=COLORS["hover"],
                      text_color=COLORS["text"]).pack(side="left", padx=(0, 4))
        ctk.CTkButton(preset_row, text="🗑 删除", command=self._delete_preset,
                      width=60, height=28, font=font_safe(11),
                      fg_color=COLORS["danger"], hover_color="#E6352B",
                      text_color="white").pack(side="left", padx=(0, 4))

        # 多标签开关
        self.multi_tag_var = ctk.BooleanVar(value=self._current_preset_multi())
        ctk.CTkCheckBox(preset_row, text="多标签", variable=self.multi_tag_var,
                        font=font_safe(11), text_color=COLORS["text"],
                        fg_color=COLORS["primary"],
                        hover_color=COLORS["primary_hover"]).pack(side="left", padx=(8, 0))

        # 标签列表容器
        self._tag_entries = []
        self.tags_container = ctk.CTkFrame(self._rules_body, fg_color="transparent")
        self.tags_container.pack(fill="x", padx=20, pady=(4, 4))
        self._render_tag_entries()

        # 添加标签按钮
        ctk.CTkButton(self._rules_body, text="➕ 添加标签",
                      command=self._add_tag_entry,
                      width=100, height=28, font=font_safe(11),
                      fg_color=COLORS["card"], hover_color=COLORS["hover"],
                      text_color=COLORS["text"]).pack(anchor="w", padx=20, pady=(0, 4))
        # 重命名规则提示
        rr = ctk.CTkFrame(self._rules_body, fg_color="transparent")
        rr.pack(fill="x", padx=20, pady=(8, 4))
        ctk.CTkLabel(rr, text="📝 命名", font=font_safe(12, "bold"),
                     text_color=COLORS["text"], width=70).pack(side="left")
        ctk.CTkLabel(rr, text="💡 在上方①区域点击变量标签或拖拽到输入框组合规则，也可直接键盘输入",
                     font=font_safe(12),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(4, 0))
        ctk.CTkLabel(self._rules_body, text="", height=4).pack()
        # spacer bottom（保存引用，便于展开时定位插入位置）
        self._rules_spacer = ctk.CTkLabel(rules_card, text="", height=8)
        self._rules_spacer.pack()

        # ═══ 5. 预览 + 日志 ═══
        bottom = ctk.CTkFrame(p, fg_color="transparent")
        bottom.pack(fill="both", expand=True, padx=32, pady=(0, 20))

        left = ctk.CTkFrame(bottom, **card_frame_style())
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ctk.CTkLabel(left, text="④ 预览 & 结果", font=font_safe(14, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=16, pady=(10, 4))
        self.evt_preview = scrolledtext.ScrolledText(left, wrap="word", height=14,
                                                      font=("SF Mono", 11), bg="#0f172a", fg="#e2e8f0",
                                                      relief="flat", padx=10, pady=8)
        self.evt_preview.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self.evt_preview.insert("1.0", "点「🚀 一键开始」扫描日期 + AI分析 + 重命名。\n"
                                "中途停止后再运行会自动跳过已处理日期。")
        self.evt_preview.config(state="disabled")

        right = ctk.CTkFrame(bottom, **card_frame_style())
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))
        ctk.CTkLabel(right, text="日志", font=font_safe(14, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=16, pady=(10, 4))
        self.log_text = scrolledtext.ScrolledText(right, wrap="word", height=14,
                                                   font=("SF Mono", 11), bg="#0f172a", fg="#e2e8f0",
                                                   relief="flat", padx=10, pady=8)
        self.log_text.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self.log_text.config(state="disabled")

    def _toggle_ctx(self):
        if self.ctx_text.winfo_ismapped():
            self.ctx_text.pack_forget()
            self.opt_prompt_row.pack_forget()
            self._ctx_expand_btn.configure(text="▸ 展开")
        else:
            self.ctx_text.pack(fill="x", padx=20, pady=(4, 4))
            self.opt_prompt_row.pack(fill="x", padx=20, pady=(0, 8))
            self._ctx_expand_btn.configure(text="▾ 折叠")

    def _optimize_prompt(self):
        """用 AI 优化业务背景为分类提示词。"""
        ctx = self.ctx_text.get("1.0", "end-1c").strip()
        if not ctx:
            messagebox.showwarning("提示", "请先输入业务背景")
            return

        model = self.model_var.get()
        self.opt_prompt_btn.configure(state="disabled", text="⏳ 优化中...")
        self.opt_prompt_status.configure(text="正在让 AI 优化提示词...", text_color=COLORS["text_secondary"])

        def _run():
            ok, result = optimize_prompt(ctx, model)
            def _done():
                self.opt_prompt_btn.configure(state="normal", text="✨ AI 优化提示词")
                if ok:
                    self.app.config_manager.set("optimized_prompt", result)
                    self.app.config_manager.set("business_context", ctx)
                    self.opt_prompt_status.configure(
                        text=f"✅ 优化完成（{len(result)}字）",
                        text_color=COLORS["success"])
                    self._log(f"✨ 提示词优化完成：{result[:60]}...")
                    messagebox.showinfo("优化完成",
                        f"AI 已将业务背景优化为分类提示词：\n\n{result[:200]}...\n\n"
                        f"后续分类将使用此优化提示词。\n"
                        f"可在业务背景区域重新输入并再次优化。")
                else:
                    self.opt_prompt_status.configure(
                        text=f"❌ 优化失败：{result[:30]}",
                        text_color=COLORS["danger"])
            self._safe_after(_done)

        threading.Thread(target=_run, daemon=True).start()

    def _toggle_rules(self):
        if self._rules_body.winfo_ismapped():
            self._rules_body.pack_forget()
            self._rules_expand_btn.configure(text="▸ 展开")
        else:
            # 展开时插入到底部 spacer 之前（紧贴标题）
            self._rules_body.pack(fill="x", pady=(0, 8), before=self._rules_spacer)
            self._rules_expand_btn.configure(text="▾ 折叠")

    # ── 标签预设管理 ──

    def _get_active_preset(self):
        """获取当前激活的标签预设 dict"""
        presets = self.app.config_manager.get("tag_presets", {})
        name = self.preset_var.get() if hasattr(self, "preset_var") else \
               self.app.config_manager.get("active_tag_preset", "默认ABC")
        return presets.get(name, {"tags": [], "multi_tag": False, "max_tags": 1})

    def _current_preset_multi(self):
        """当前预设是否允许多标签"""
        p = self._get_active_preset()
        return p.get("multi_tag", False)

    def _render_tag_entries(self):
        """渲染标签编辑行"""
        for w in self.tags_container.winfo_children():
            w.destroy()
        self._tag_entries.clear()

        preset = self._get_active_preset()
        tags = preset.get("tags", [])
        for t in tags:
            self._add_tag_row(t.get("name", ""), t.get("desc", ""))

    def _add_tag_row(self, name="", desc=""):
        """添加一行标签编辑器"""
        row = ctk.CTkFrame(self.tags_container, fg_color="transparent")
        row.pack(fill="x", pady=(0, 3))

        name_entry = ctk.CTkEntry(row, font=font_safe(12), height=28, width=60,
                                   fg_color=COLORS["bg"], border_color=COLORS["border"],
                                   placeholder_text="标签名")
        name_entry.insert(0, name)
        name_entry.pack(side="left", padx=(0, 4))

        desc_entry = ctk.CTkEntry(row, font=font_safe(12), height=28,
                                   fg_color=COLORS["bg"], border_color=COLORS["border"],
                                   placeholder_text="标签描述（什么照片适合这个标签）")
        desc_entry.insert(0, desc)
        desc_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))

        ctk.CTkButton(row, text="✕", width=24, height=24,
                      fg_color=COLORS["danger"], hover_color="#E6352B",
                      text_color="white", font=font_safe(10),
                      command=lambda r=row: self._remove_tag_row(r)).pack(side="right")
        self._tag_entries.append((name_entry, desc_entry, row))

    def _add_tag_entry(self):
        """添加新标签行"""
        self._add_tag_row()

    def _remove_tag_row(self, row):
        """删除标签行"""
        for i, (n, d, r) in enumerate(self._tag_entries):
            if r == row:
                row.destroy()
                self._tag_entries.pop(i)
                break

    def _switch_preset(self, choice):
        """切换标签预设"""
        self.app.config_manager.set("active_tag_preset", choice)
        self.multi_tag_var.set(self._current_preset_multi())
        self._render_tag_entries()

    def _save_preset_as(self):
        """将当前编辑的标签另存为新预设"""
        name = simpledialog.askstring("另存为预设", "输入预设名称：")
        if not name:
            return
        name = name.strip()
        tags = []
        for name_entry, desc_entry, _ in self._tag_entries:
            n = name_entry.get().strip()
            d = desc_entry.get().strip()
            if n:
                tags.append({"name": n, "desc": d})
        if not tags:
            messagebox.showwarning("提示", "没有有效标签")
            return
        preset = {
            "tags": tags,
            "multi_tag": self.multi_tag_var.get(),
            "max_tags": 3 if self.multi_tag_var.get() else 1
        }
        presets = self.app.config_manager.get("tag_presets", {})
        presets[name] = preset
        self.app.config_manager.set("tag_presets", presets)
        self.app.config_manager.set("active_tag_preset", name)
        self.preset_var.set(name)
        self.preset_combo.configure(values=list(presets.keys()))
        messagebox.showinfo("保存成功", f"预设「{name}」已保存（{len(tags)}个标签）")

    def _delete_preset(self):
        """删除当前预设"""
        name = self.preset_var.get()
        presets = self.app.config_manager.get("tag_presets", {})
        if len(presets) <= 1:
            messagebox.showwarning("无法删除", "至少保留一个预设")
            return
        if messagebox.askyesno("确认", f"删除预设「{name}」？"):
            del presets[name]
            self.app.config_manager.set("tag_presets", presets)
            new_name = list(presets.keys())[0]
            self.app.config_manager.set("active_tag_preset", new_name)
            self.preset_var.set(new_name)
            self.preset_combo.configure(values=list(presets.keys()))
            self._render_tag_entries()

    def _update_pattern_preview(self, *_):
        """命名规则实时预览"""
        pattern = self.evt_pattern_var.get().strip() or "{date}_{event}_{seq:02d}{grade}_{desc}"
        try:
            from core.event_classifier import BatchRenamer
            sample = BatchRenamer.new_name(
                "2026-08-06", "工厂考察", 1, "A", "车间全景", ".jpg", pattern=pattern)
            self.evt_pattern_preview.configure(text=f"预览: {sample}")
        except Exception:
            self.evt_pattern_preview.configure(text="预览: （规则有误）")

    # ── 变量标签：点击插入 / 拖拽到输入框 ──

    def _insert_var(self, var_text):
        """在光标位置插入变量文本（也用于分隔符快捷按钮）"""
        entry = self.evt_pattern_entry
        entry.focus_set()
        try:
            pos = entry.index("insert")
        except Exception:
            pos = len(self.evt_pattern_var.get())
        current = self.evt_pattern_var.get()
        new_val = current[:pos] + var_text + current[pos:]
        self.evt_pattern_var.set(new_val)
        # 移动光标到插入内容之后
        new_pos = pos + len(var_text)
        try:
            entry.icursor(new_pos)
        except Exception:
            pass

    def _clear_pattern(self):
        """清空命名规则输入框"""
        self.evt_pattern_var.set("")
        self.evt_pattern_entry.focus_set()

    def _drag_start(self, event, var_text):
        """开始拖拽一个变量标签"""
        self._drag_var = var_text
        self._drag_active = False
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def _drag_motion(self, event):
        """拖拽中 — 移动超过 5px 才算真正的拖拽"""
        dx = abs(event.x_root - self._drag_start_x)
        dy = abs(event.y_root - self._drag_start_y)
        if dx > 5 or dy > 5:
            self._drag_active = True
            try:
                self.evt_pattern_entry.configure(border_color=COLORS["primary"])
            except Exception:
                pass

    def _drag_release(self, event):
        """释放 — 区分点击和拖拽"""
        # 恢复输入框边框
        try:
            self.evt_pattern_entry.configure(border_color=COLORS["border"])
        except Exception:
            pass

        var = self._drag_var
        self._drag_var = None
        if not var:
            return

        if self._drag_active:
            # 拖拽 — 检查是否释放在输入框区域
            entry = self.evt_pattern_entry
            ex = entry.winfo_rootx()
            ey = entry.winfo_rooty()
            ew = entry.winfo_width()
            eh = entry.winfo_height()
            if ex <= event.x_root <= ex + ew and ey <= event.y_root <= ey + eh:
                self._insert_var(var)
            self._drag_active = False
        else:
            # 普通点击 — 直接插入到光标位置
            self._insert_var(var)

    # ═══════════════════════════════════════
    #  事件 模式 — 一键运行
    # ═══════════════════════════════════════

    def _evt_run(self, force=False):
        inp = self.app.input_var.get().strip()
        if not os.path.isdir(inp):
            messagebox.showerror("错误", "素材文件夹不存在"); return
        out = self.app.output_var.get().strip()
        model = self.model_var.get()
        grade_enabled = self.evt_grade_ck.get()
        rename = self.evt_rename_ck.get()
        ctx = self.ctx_text.get("1.0", "end-1c").strip()

        self._hide_undo_button()  # 上一轮的撤销入口失效

        os.makedirs(out, exist_ok=True)
        self.app.config_manager.set("model", model)
        self.app.config_manager.set("business_context", ctx)

        # 保存自定义命名规则
        rename_pattern = self.evt_pattern_var.get().strip()
        if rename_pattern:
            evt_cfg = self.app.config_manager.get("event_mode", {})
            evt_cfg["rename_pattern"] = rename_pattern
            self.app.config_manager.set("event_mode", evt_cfg)

        # 构建标签预设（从 UI 收集当前编辑的标签）
        tag_preset = None
        if grade_enabled and hasattr(self, "_tag_entries") and self._tag_entries:
            tags = []
            for name_entry, desc_entry, _ in self._tag_entries:
                n = name_entry.get().strip()
                d = desc_entry.get().strip()
                if n:
                    tags.append({"name": n, "desc": d})
            if tags:
                preset_name = self.preset_var.get() if hasattr(self, "preset_var") else "默认ABC"
                tag_preset = {
                    "tags": tags,
                    "multi_tag": self.multi_tag_var.get() if hasattr(self, "multi_tag_var") else False,
                    "max_tags": 3 if (self.multi_tag_var.get() if hasattr(self, "multi_tag_var") else False) else 1
                }
                # 保存到配置
                presets = self.app.config_manager.get("tag_presets", {})
                presets[preset_name] = tag_preset
                self.app.config_manager.set("tag_presets", presets)
                self.app.config_manager.set("active_tag_preset", preset_name)

        # 兼容旧版
        grade_rules = None

        # 最小照片数
        min_photos = self.app.config_manager.get("min_photos_per_event", 2)

        self._clear_log()
        self._log(f"🤖 开始分析 — {model}")
        if ctx:
            self._log(f"   业务背景: {ctx[:50]}...")
        opt_p = self.app.config_manager.get("optimized_prompt", "")
        if opt_p:
            self._log(f"   ✨ 使用 AI 优化提示词（{len(opt_p)}字）")
        if tag_preset:
            tags_str = ", ".join(t["name"] for t in tag_preset.get("tags", []))
            multi = "多标签" if tag_preset.get("multi_tag") else "单标签"
            self._log(f"   🏷️ 标签预设({multi}): {tags_str}")
        if min_photos > 1:
            self._log(f"   🔗 最小分组: {min_photos}张")
        if rename:
            self._log(f"   命名规则: {rename_pattern}")
        if not rename:
            self._log("   跳过重命名（仅分析）")

        self._evt_ui_state(False)
        self.evt_stop_btn.configure(state="normal")
        self.evt_status.set("⏳ 分析中...")
        self.evt_progress.set(0)

        def _run():
            try:
                self.engine = EventPipeline(inp, out, model, ctx,
                                            force=force, dry_run=not rename,
                                            grade_rules=grade_rules,
                                            rename_pattern=rename_pattern if rename else None,
                                            tag_preset=tag_preset,
                                            min_photos=min_photos,
                                            gap_hours=4.0,
                                            max_workers=3)
                self.engine.run(
                    log=lambda m: self._safe_after(lambda: self._log(m)),
                    prog=lambda c, t: self._safe_after(lambda: self._update_evt_progress(c, t)),
                    on_event=lambda n, d: self._safe_after(
                        lambda: self.evt_status.set(f"⏳ {n} ({d}张)"))
                )
                self._safe_after(self._evt_show_result)
            except Exception as e:
                self._safe_after(lambda: self._log(f"❌ {e}"))
                self._safe_after(lambda: self._evt_ui_state(True))

        self.sort_thread = threading.Thread(target=_run, daemon=True)
        self.sort_thread.start()

    def _evt_force(self):
        if messagebox.askyesno("确认", "清除断点，从头重新分析所有照片。\n\n确定？"):
            Checkpoint.clear(self.app.output_var.get().strip())
            self._evt_run(force=True)

    def _evt_show_result(self):
        self._evt_ui_state(True)
        s = self.engine.summary if self.engine else {}
        evts = self.engine.events if self.engine else []

        lines = ["=" * 40]
        if s.get('events', 0) == 0:
            lines.append("✅ 全部已处理，无需重新分析")
        else:
            lines.append(f"📊 完成 {s.get('events',0)} 事件")
            lines.append(f"⭐ A={s.get('A',0)}  📋 B={s.get('B',0)}  📎 C={s.get('C',0)}")
            lines.append(f"✅ 成功 {s.get('success',0)} 张  ❌ 失败 {s.get('fail',0)} 张")
        lines.append(f"⏭ 跳过 {s.get('skipped',0)} 个已处理日期")
        lines.append("=" * 40)

        for evt in evts:
            lines.append("")
            lines.append(f"📅 {evt['date']} — {evt['name']}")
            # 标签统计
            tag_counts = {}
            for path, r in evt.get("results", []):
                tags = r.get("tags", [])
                if tags:
                    for t in tags:
                        tag_counts[t] = tag_counts.get(t, 0) + 1
                else:
                    g = r.get("grade", "C")
                    tag_counts[g] = tag_counts.get(g, 0) + 1
            tag_str = "  ".join(f"{k}={v}" for k, v in sorted(tag_counts.items(), key=lambda x: -x[1]))
            lines.append(f"   {evt['total']}张  {tag_str}")
            for path, r in evt.get("results", [])[:3]:
                tags = r.get("tags", [])
                tag_display = ",".join(tags) if tags else r.get("grade", "?")
                lines.append(f"      [{tag_display}] {r['desc']}  ← {os.path.basename(path)}")

            # 核心故事点
            top_items = [(p, r) for p, r in evt.get("results", [])
                         if r.get("tags") or r.get("grade") == "A"]
            if top_items:
                lines.append("   🎯 核心故事:")
                for p, r in top_items[:3]:
                    s_text = r.get("story", "")
                    if s_text:
                        lines.append(f"      · {s_text}")

        self._evt_show(lines)
        tag_summary = s.get("tags", {})
        if tag_summary:
            tag_str = " ".join(f"{k}={v}" for k, v in sorted(tag_summary.items(), key=lambda x: -x[1])[:5])
            self.evt_status.set(f"✅ {s.get('events',0)}事件  {tag_str}")
        else:
            self.evt_status.set(f"✅ {s.get('events',0)}事件 A={s.get('A',0)} B={s.get('B',0)} C={s.get('C',0)}")
        self.evt_progress.set(1)

        # 有输出文件时提供限时撤销
        if self.engine and getattr(self.engine, "_dests", None):
            self._log("↩ 30 秒内可点「撤销本次整理」删除本次输出（原文件不受影响）")
            self._show_undo_button(30)

    def _show_undo_button(self, secs=30):
        if not hasattr(self, "evt_undo_btn"):
            return
        self.evt_undo_btn.pack(side="left", padx=(8, 0))
        self._tick_undo_countdown(secs)

    def _tick_undo_countdown(self, secs):
        if getattr(self, "_undo_after_id", None):
            self.after_cancel(self._undo_after_id)
            self._undo_after_id = None
        if secs <= 0:
            self._hide_undo_button()
            return
        self.evt_undo_btn.configure(text=f"↩ 撤销本次整理（{secs}s）")
        self._undo_after_id = self.after(1000, lambda: self._tick_undo_countdown(secs - 1))

    def _hide_undo_button(self):
        if getattr(self, "_undo_after_id", None):
            self.after_cancel(self._undo_after_id)
            self._undo_after_id = None
        if hasattr(self, "evt_undo_btn"):
            self.evt_undo_btn.pack_forget()

    def _evt_undo(self):
        if not self.engine:
            return
        if not messagebox.askyesno("撤销确认",
                "将删除本次整理生成的输出文件（原文件不受影响）。\n\n确定撤销？"):
            return
        self._hide_undo_button()
        removed = self.engine.undo()
        self._log(f"↩ 已撤销：删除 {removed} 个输出文件，原文件未动")
        self.evt_status.set(f"↩ 已撤销（{removed} 个文件）")

    # ═══════════════════════════════════════
    #  事件 辅助
    # ═══════════════════════════════════════

    def _evt_ui_state(self, enabled):
        for b in [self.evt_run, self.evt_force]:
            b.configure(state="normal" if enabled else "disabled")
        self.evt_stop_btn.configure(state="disabled" if enabled else "normal")

    def _evt_show(self, text):
        self.evt_preview.config(state="normal")
        self.evt_preview.delete("1.0", "end")
        self.evt_preview.insert("end", text)
        self.evt_preview.see("end")
        self.evt_preview.config(state="disabled")

    def _update_evt_progress(self, cur, total):
        if total > 0:
            self.evt_progress.set(cur / total)

    # ═══════════════════════════════════════
    #  共用
    # ═══════════════════════════════════════

    def _refresh_model_list(self):
        self.model_combo.configure(values=["加载中..."])
        def _load():
            try:
                ms = fetch_ollama_models()
                self._safe_after(lambda: self._on_models(ms))
            except Exception:
                self._safe_after(lambda: self._on_models(
                    ["llava:13b", "llava:7b", "bakllava", "moondream"]))
        threading.Thread(target=_load, daemon=True).start()

    def _safe_after(self, callback):
        """安全地在主线程执行回调（窗口已关闭则不执行）"""
        try:
            if self.winfo_exists():
                self.after(0, callback)
        except Exception:
            pass

    def _on_models(self, models):
        self.model_combo.configure(values=models)
        if self.model_var.get() not in models and models:
            self.model_var.set(models[0])
        self._update_hint()

    def _update_hint(self):
        m = self.model_var.get()
        tag = get_model_role_tag(m)
        clr = COLORS["success"] if tag == "视觉模型" else COLORS["warning"]
        self.model_hint.configure(text=f"{tag} · {get_model_hint(m)}", text_color=clr)

    def _pick_folder(self, var):
        d = filedialog.askdirectory(initialdir=var.get())
        if d:
            var.set(d)
            k = "last_input" if var is self.app.input_var else "last_output"
            self.app.config_manager.set(k, d)

    def _log(self, line):
        self.log_text.config(state="normal")
        self.log_text.insert("end", line + "\n")
        t = int(self.log_text.index("end-1c").split(".")[0])
        if t > 500:
            self.log_text.delete("1.0", f"{t - 500}.0")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    # ═══════════════════════════════════════
    #  分类模式专用
    # ═══════════════════════════════════════

    def _cat_start(self):
        inp = self.app.input_var.get().strip()
        out = self.app.output_var.get().strip()
        if not os.path.isdir(inp):
            messagebox.showerror("错误", f"素材文件夹不存在：\n{inp}"); return

        # ── 预扫描：统计图片数量（递归子目录） ──
        self.status_var.set("正在扫描图片...")
        self.update_idletasks()
        image_count = 0
        out_abs = os.path.abspath(out)
        for root, dirs, files in os.walk(inp):
            if os.path.abspath(root) == out_abs:
                dirs[:] = []
                continue
            for f in files:
                if is_image_file(os.path.join(root, f)):
                    image_count += 1

        if image_count == 0:
            messagebox.showwarning("无图片", f"在素材文件夹中没有找到图片：\n{inp}")
            self.status_var.set("就绪")
            return

        # ── 估算 ETA（按模型大小粗估） ──
        model_lower = self.model_var.get().lower()
        if "13b" in model_lower:
            sec_per_img = 10
        elif "7b" in model_lower:
            sec_per_img = 5
        else:
            sec_per_img = 7
        eta_sec = image_count * sec_per_img
        if eta_sec < 60:
            eta_str = f"约 {eta_sec} 秒"
        elif eta_sec < 3600:
            eta_str = f"约 {eta_sec // 60} 分 {eta_sec % 60} 秒"
        else:
            eta_str = f"约 {eta_sec // 3600} 时 {(eta_sec % 3600) // 60} 分"

        # ── 增量模式：计算实际待处理数量 ──
        inc = self.inc_var.get()
        if inc:
            processed = get_processed_files(out)
            new_count = max(0, image_count - len(processed))
            if new_count == 0:
                messagebox.showinfo("无需处理",
                                    "所有图片已处理完毕，没有新图片。\n如需重新分类，请取消勾选「增量」。")
                self.status_var.set("就绪")
                return
            msg = (f"📋 扫描结果\n\n"
                   f"📁 找到图片：{image_count} 张\n"
                   f"✅ 已处理：{len(processed)} 张\n"
                   f"🆕 待处理：{new_count} 张\n\n"
                   f"🤖 模型：{self.model_var.get()}\n"
                   f"⏱️ 预计耗时：{eta_str}\n\n"
                   f"是否开始分类？")
        else:
            msg = (f"📋 扫描结果\n\n"
                   f"📁 找到图片：{image_count} 张\n\n"
                   f"🤖 模型：{self.model_var.get()}\n"
                   f"⏱️ 预计耗时：{eta_str}\n\n"
                   f"是否开始分类？")

        if not messagebox.askyesno("确认分类", msg):
            self.status_var.set("已取消")
            return

        # ── 确认后开始分类 ──
        os.makedirs(out, exist_ok=True)
        self.app.config_manager.set("model", self.model_var.get())
        self.app.config_manager.set("incremental", self.inc_var.get())
        self._clear_log()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.progress_bar.set(0)
        self.status_var.set("准备中...")
        self.engine = SorterEngine(
            self.app.config_manager.config,
            log_callback=self._log,
            progress_callback=lambda c, t, f: self._safe_after(lambda: (
                self.progress_bar.set(c / t if t else 0),
                self.status_var.set(f"{c}/{t}：{f}")
            )),
            finished_callback=self._cat_finished
        )
        self.sort_thread = threading.Thread(target=self.engine.run, args=(inp, out), daemon=True)
        self.sort_thread.start()

    def _stop(self):
        if self.engine:
            self.engine.stop()
            self.status_var.set("正在停止...")

    def _cat_finished(self, success, results):
        self._safe_after(lambda: self._cat_reset(success))

    def _cat_reset(self, ok):
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.status_var.set("完成" if ok else "失败")
        if ok:
            self.progress_bar.set(1)
            self._refresh_model_list()
            self.app.pages["dashboard"].refresh_stats()
