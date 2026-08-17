#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 工具箱：位图转矢量、以文搜图、图片描述、图片问答、智能助手、重复检测"""
import os
import hashlib
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path

import requests

from ui.theme import (
    COLORS, font_safe, primary_button_style,
    secondary_button_style, card_frame_style
)
from core.sorter_engine import fetch_all_models, DEFAULT_URL
from core.image_utils import is_image_file, encode_image, bitmap_to_vector_svg
from core.model_info import get_model_hint, is_vision_model, get_model_role_tag


class ToolboxPage(ctk.CTkFrame):
    """AI 工具箱页面 — 集成多种 AI 工具"""

    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.configure(fg_color=COLORS["bg"])
        self._tool_thread = None
        self._build_ui()
        self._refresh_models()

    def _build_ui(self):
        # 标题
        ctk.CTkLabel(self, text="AI 工具箱", font=font_safe(28, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=32, pady=(28, 4))
        ctk.CTkLabel(self, text="位图转矢量 · 以文搜图 · 图片描述 · 图片问答 · 智能助手 · 重复检测 · 格式转换 · EXIF查看 · 日期修正",
                     font=font_safe(14, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=32, pady=(0, 24))

        # 工具分段选择器（常用 + 更多）
        seg_container = ctk.CTkFrame(self, fg_color="transparent")
        seg_container.pack(fill="x", padx=32, pady=(0, 8))

        self.tool_var = ctk.StringVar(value="search_by_text")
        self.tool_buttons = {}

        # 常用工具（第一行，始终显示）
        common_tools = [
            ("🔍 以文搜图", "search_by_text"),
            ("📝 图片描述", "describe_image"),
            ("🔄 格式转换", "format_convert"),
            ("📅 日期修正", "date_fix"),
            ("🔁 重复检测", "dedup"),
        ]
        for label, val in common_tools:
            btn = ctk.CTkButton(seg_container, text=label,
                                command=lambda v=val: self._switch_tool(v),
                                width=120, height=34,
                                font=font_safe(12, "normal"),
                                fg_color=COLORS["card"],
                                text_color=COLORS["text"],
                                hover_color=COLORS["hover"],
                                corner_radius=8)
            btn.pack(side="left", padx=(0, 8))
            self.tool_buttons[val] = btn

        # 更多工具（第二行，默认收起）
        self.more_tools_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.more_tools_visible = False

        more_tools = [
            ("🎨 位图转矢量", "vectorize"),
            ("💬 图片问答", "visual_qa"),
            ("🤖 智能助手", "smart_assistant"),
            ("🏷 自定义重命名", "custom_rename"),
            ("📋 EXIF 查看", "exif_view"),
        ]
        for label, val in more_tools:
            btn = ctk.CTkButton(self.more_tools_frame, text=label,
                                command=lambda v=val: self._switch_tool(v),
                                width=120, height=34,
                                font=font_safe(12, "normal"),
                                fg_color=COLORS["card"],
                                text_color=COLORS["text"],
                                hover_color=COLORS["hover"],
                                corner_radius=8)
            btn.pack(side="left", padx=(0, 8))
            self.tool_buttons[val] = btn

        # 更多工具切换按钮
        self.more_toggle_btn = ctk.CTkButton(
            seg_container, text="更多工具 ▼",
            command=self._toggle_more_tools,
            width=120, height=34,
            font=font_safe(12, "normal"),
            fg_color="transparent", text_color=COLORS["text_secondary"],
            hover_color=COLORS["hover"], corner_radius=8)
        self.more_toggle_btn.pack(side="left", padx=(0, 8))

        # 模型配置
        self.model_card = ctk.CTkFrame(self, **card_frame_style())
        self.model_card.pack(fill="x", padx=32, pady=(0, 16))

        ctk.CTkLabel(self.model_card, text="模型", font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=24, pady=(16, 4))

        model_row = ctk.CTkFrame(self.model_card, fg_color="transparent")
        model_row.pack(fill="x", padx=24, pady=(0, 4))
        self.toolbox_model_var = ctk.StringVar(value="llava:13b")
        self.toolbox_model_combo = ctk.CTkOptionMenu(model_row, variable=self.toolbox_model_var,
                                                     values=["加载中..."], width=240, height=34,
                                                     font=font_safe(13, "normal"),
                                                     dropdown_font=font_safe(13, "normal"),
                                                     command=self._on_model_change)
        self.toolbox_model_combo.pack(side="left")
        ctk.CTkButton(model_row, text="🔄", command=self._refresh_models, width=36, height=34,
                      fg_color=COLORS["card"], hover_color=COLORS["hover"],
                      text_color=COLORS["text"]).pack(side="left", padx=(8, 0))

        self.model_hint_var = ctk.StringVar(value="正在加载模型信息...")
        self.model_hint_label = ctk.CTkLabel(self.model_card, textvariable=self.model_hint_var,
                                             font=font_safe(11, "normal"),
                                             text_color=COLORS["text_secondary"])
        self.model_hint_label.pack(anchor="w", padx=24, pady=(0, 16))

        # 工具参数区
        self.tool_body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.tool_body.pack(fill="both", expand=True, padx=32, pady=(0, 8))

        self._switch_tool("search_by_text")

    def _toggle_more_tools(self):
        """展开/收起更多工具。"""
        if self.more_tools_visible:
            self.more_tools_frame.pack_forget()
            self.more_toggle_btn.configure(text="更多工具 ▼")
            self.more_tools_visible = False
        else:
            self.more_tools_frame.pack(fill="x", padx=32, pady=(0, 8),
                                       before=self.model_card if hasattr(self, 'model_card') else None)
            self.more_toggle_btn.configure(text="收起 ▲")
            self.more_tools_visible = True

    def _switch_tool(self, tool_key):
        self.tool_var.set(tool_key)
        for k, btn in self.tool_buttons.items():
            if k == tool_key:
                btn.configure(fg_color=COLORS["primary"], text_color="white",
                              hover_color=COLORS["primary_hover"])
            else:
                btn.configure(fg_color=COLORS["card"], text_color=COLORS["text"],
                              hover_color=COLORS["hover"])

        for w in self.tool_body.winfo_children():
            w.destroy()

        if tool_key == "vectorize":
            self._build_vectorize()
        elif tool_key == "search_by_text":
            self._build_search_by_text()
        elif tool_key == "describe_image":
            self._build_describe_image()
        elif tool_key == "visual_qa":
            self._build_visual_qa()
        elif tool_key == "smart_assistant":
            self._build_smart_assistant()
        elif tool_key == "dedup":
            self._build_dedup()
        elif tool_key == "custom_rename":
            self._build_custom_rename()
        elif tool_key == "format_convert":
            self._build_format_convert()
        elif tool_key == "exif_view":
            self._build_exif_view()
        elif tool_key == "date_fix":
            self._build_date_fix()

        self._on_model_change(self.toolbox_model_var.get())

        # 智能助手自动切换到文本模型，其他工具切换到视觉模型
        if tool_key == "smart_assistant":
            current = self.toolbox_model_var.get()
            if is_vision_model(current):
                values = list(self.toolbox_model_combo.cget("values"))
                text_models = [m for m in values if m and not is_vision_model(m)]
                if text_models:
                    self.toolbox_model_var.set(text_models[0])
                    self._on_model_change(text_models[0])
        elif tool_key in ("search_by_text", "describe_image", "visual_qa"):
            current = self.toolbox_model_var.get()
            if not is_vision_model(current):
                values = list(self.toolbox_model_combo.cget("values"))
                vision_models = [m for m in values if m and is_vision_model(m)]
                if vision_models:
                    self.toolbox_model_var.set(vision_models[0])
                    self._on_model_change(vision_models[0])

    def _on_model_change(self, model_name):
        hint = get_model_hint(model_name)
        tag = get_model_role_tag(model_name)
        tag_color = COLORS["success"] if tag == "视觉模型" else COLORS["warning"]
        self.model_hint_var.set(f"{tag} · {hint}")
        self.model_hint_label.configure(text_color=tag_color)

    # ── 位图转矢量 ──
    def _build_vectorize(self):
        card = ctk.CTkFrame(self.tool_body, **card_frame_style())
        card.pack(fill="both", expand=True)

        ctk.CTkLabel(card, text="位图转矢量图", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(20, 8))
        ctk.CTkLabel(card, text="将 JPG/PNG 转换为 SVG 矢量文件，长什么样就转成什么样。优先使用 VTracer（Rust 引擎），未安装时回退到内置算法。",
                     font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=24, pady=(0, 16))

        sel_row = ctk.CTkFrame(card, fg_color="transparent")
        sel_row.pack(fill="x", padx=24, pady=(0, 12))
        self.vec_img_var = ctk.StringVar(value="")
        ctk.CTkEntry(sel_row, textvariable=self.vec_img_var, font=font_safe(13, "normal"),
                     height=36, fg_color="white", border_color=COLORS["border"],
                     placeholder_text="选择一张图片...").pack(side="left", fill="x", expand=True, padx=(0, 12))
        ctk.CTkButton(sel_row, text="选择图片", command=self._choose_vec_image,
                      width=100, **secondary_button_style()).pack(side="left")

        opt_row = ctk.CTkFrame(card, fg_color="transparent")
        opt_row.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkLabel(opt_row, text="转换质量", font=font_safe(13, "bold"),
                     text_color=COLORS["text"]).pack(side="left", padx=(0, 8))
        self.vec_quality_var = ctk.StringVar(value="high")
        ctk.CTkSegmentedButton(opt_row, values=["高", "中", "低"],
                               variable=self.vec_quality_var,
                               font=font_safe(13, "normal"),
                               selected_color=COLORS["primary"],
                               selected_hover_color=COLORS["primary_hover"],
                               unselected_color=COLORS["card"]).pack(side="left")
        ctk.CTkLabel(opt_row, text="（高=色彩还原最佳，低=文件最小）",
                     font=font_safe(11, "normal"),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(12, 0))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkButton(btn_row, text="🎨 开始转换", command=self._run_vectorize,
                      **primary_button_style()).pack(side="left", padx=(0, 12))
        self.vec_status_var = ctk.StringVar(value="")
        ctk.CTkLabel(btn_row, textvariable=self.vec_status_var,
                     font=font_safe(12, "normal"), text_color=COLORS["text_secondary"]).pack(side="left")

        preview_frame = ctk.CTkFrame(card, fg_color=COLORS["bg"], corner_radius=8)
        preview_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self.vec_preview = scrolledtext.ScrolledText(preview_frame, wrap="word",
                                                     font=("SF Mono", 10), bg="#f8f9fa",
                                                     fg="#1D1D1F", relief="flat")
        self.vec_preview.pack(fill="both", expand=True, padx=8, pady=8)
        self.vec_preview.insert("1.0", "SVG 预览将显示在这里...")
        self.vec_preview.config(state="disabled")

    def _choose_vec_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("图片", "*.jpg *.jpeg *.png *.webp *.heic *.heif"), ("所有文件", "*.*")])
        if path:
            self.vec_img_var.set(path)

    def _run_vectorize(self):
        path = self.vec_img_var.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showwarning("路径错误", "请先选择一张图片")
            return

        quality = self.vec_quality_var.get()
        quality_map = {
            "high": {"max_colors": 16, "max_size": 800},
            "medium": {"max_colors": 8, "max_size": 500},
            "low": {"max_colors": 4, "max_size": 300},
        }
        params = quality_map.get(quality, quality_map["high"])

        self.vec_status_var.set("正在转换...")

        def _convert():
            try:
                svg = bitmap_to_vector_svg(path, mode="photo",
                                           max_colors=params["max_colors"],
                                           max_size=params["max_size"])
                if svg:
                    self.app.root.after(0, lambda: self._show_vectorize_result(svg))
                else:
                    self.app.root.after(0, lambda: self.vec_status_var.set("转换失败"))
            except Exception as e:
                self.app.root.after(0, lambda: self.vec_status_var.set(f"错误：{e}"))

        threading.Thread(target=_convert, daemon=True).start()

    def _show_vectorize_result(self, svg):
        self.vec_preview.config(state="normal")
        self.vec_preview.delete("1.0", "end")
        self.vec_preview.insert("1.0", svg)
        self.vec_preview.config(state="disabled")
        self.vec_status_var.set("转换完成，点击保存")

        if messagebox.askyesno("保存 SVG", "转换完成，是否保存 SVG 文件？"):
            out = filedialog.asksaveasfilename(
                defaultextension=".svg",
                filetypes=[("SVG", "*.svg")],
                initialfile=Path(self.vec_img_var.get()).stem + ".svg")
            if out:
                with open(out, "w", encoding="utf-8") as f:
                    f.write(svg)
                messagebox.showinfo("保存成功", f"已保存到：\n{out}")

    # ── 以文搜图 ──
    def _build_search_by_text(self):
        from core import clip_search

        card = ctk.CTkFrame(self.tool_body, **card_frame_style())
        card.pack(fill="both", expand=True)

        ctk.CTkLabel(card, text="以文搜图", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(20, 8))

        # 检查 CLIP 是否可用
        clip_ok = clip_search.is_available()
        if clip_ok:
            ctk.CTkLabel(card, text="CLIP 语义搜索 · 512 维向量 · FAISS 索引 · 毫秒级搜索",
                         font=font_safe(13, "normal"),
                         text_color=COLORS["text_secondary"]).pack(anchor="w", padx=24, pady=(0, 16))
        else:
            ctk.CTkLabel(card, text="⚠️ CLIP 未安装，使用慢速模式。安装后体验 10 倍提升：pip install sentence-transformers faiss-cpu",
                         font=font_safe(12, "normal"),
                         text_color=COLORS["warning"]).pack(anchor="w", padx=24, pady=(0, 16))

        # 搜索文件夹
        dir_row = ctk.CTkFrame(card, fg_color="transparent")
        dir_row.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkLabel(dir_row, text="搜索文件夹", font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"], width=90).pack(side="left")
        self.search_dir_var = ctk.StringVar(value=self.app.output_var.get() or os.path.expanduser("~/Desktop"))
        ctk.CTkEntry(dir_row, textvariable=self.search_dir_var, font=font_safe(13, "normal"),
                     height=36, fg_color=COLORS["bg"], border_color=COLORS["border"]).pack(
                         side="left", fill="x", expand=True, padx=(12, 8))
        ctk.CTkButton(dir_row, text="选择…", command=self._choose_search_dir,
                      width=70, **secondary_button_style()).pack(side="left", padx=(0, 4))

        # CLIP 模式：建立索引按钮 + 索引状态
        if clip_ok:
            index_row = ctk.CTkFrame(card, fg_color="transparent")
            index_row.pack(fill="x", padx=24, pady=(0, 12))
            self.clip_index_btn = ctk.CTkButton(index_row, text="📋 建立索引",
                                                command=self._build_clip_index,
                                                width=120, **secondary_button_style())
            self.clip_index_btn.pack(side="left")
            info = clip_search.get_index_info()
            count = info.get("total_images", 0)
            self.clip_index_status = ctk.StringVar(value=f"索引: {count} 张" if count else "未建立索引")
            ctk.CTkLabel(index_row, textvariable=self.clip_index_status,
                         font=font_safe(12, "normal"),
                         text_color=COLORS["text_secondary"]).pack(side="left", padx=(12, 0))

        # 搜索输入
        query_row = ctk.CTkFrame(card, fg_color="transparent")
        query_row.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkLabel(query_row, text="搜索内容", font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"], width=90).pack(side="left")
        self.search_query_var = ctk.StringVar(value="")
        ctk.CTkEntry(query_row, textvariable=self.search_query_var, font=font_safe(13, "normal"),
                     height=36, fg_color="white", border_color=COLORS["border"],
                     placeholder_text="例如：红色汽车在停车场 / 工厂车间设备 / 负责人和客户合影").pack(
                         side="left", fill="x", expand=True, padx=(12, 0))

        # 选项与按钮
        opt_row = ctk.CTkFrame(card, fg_color="transparent")
        opt_row.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkLabel(opt_row, text="返回数量", font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(side="left")
        self.top_k_var = ctk.StringVar(value="10")
        ctk.CTkEntry(opt_row, textvariable=self.top_k_var, width=60, height=30,
                     font=font_safe(13, "normal")).pack(side="left", padx=(8, 0))
        self.search_btn = ctk.CTkButton(opt_row, text="🔍 搜索", command=self._run_search_by_text,
                      **primary_button_style())
        self.search_btn.pack(side="left", padx=(24, 0))
        self.search_status_var = ctk.StringVar(value="")
        ctk.CTkLabel(opt_row, textvariable=self.search_status_var,
                     font=font_safe(12, "normal"),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(12, 0))

        # 结果区
        result_frame = ctk.CTkFrame(card, fg_color="transparent")
        result_frame.pack(fill="both", expand=True, padx=24, pady=(8, 20))
        self.search_result_text = scrolledtext.ScrolledText(result_frame, wrap="word",
                                                            font=("SF Mono", 12) if os.name != "nt" else ("Consolas", 12),
                                                            bg="#f8f9fa", fg="#1D1D1F",
                                                            relief="flat")
        self.search_result_text.pack(fill="both", expand=True)

    def _choose_search_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.search_dir_var.set(path)

    def _build_clip_index(self):
        """为 CLIP 搜索建立 FAISS 索引。"""
        from core import clip_search
        if not clip_search.is_available():
            messagebox.showwarning("CLIP 未安装",
                "请先安装依赖：\npip install sentence-transformers faiss-cpu")
            return

        search_dir = self.search_dir_var.get().strip()
        if not os.path.isdir(search_dir):
            messagebox.showwarning("路径错误", "搜索文件夹不存在")
            return

        self.clip_index_btn.configure(state="disabled", text="⏳ 索引中...")
        self.clip_index_status.set("正在建立索引...")

        self._clip_cancel = False

        def _run():
            ok, msg = clip_search.index_folder(
                search_dir,
                progress_cb=lambda done, total: self.after(0, lambda:
                    self.clip_index_status.set(f"索引中 {done}/{total}")),
                cancel_cb=lambda: self._clip_cancel
            )
            def _done():
                self.clip_index_btn.configure(state="normal", text="📋 建立索引")
                if ok:
                    self.clip_index_status.set(msg)
                    self._log(f"✅ {msg}")
                else:
                    self.clip_index_status.set(f"❌ {msg}")
            self.after(0, _done)

        threading.Thread(target=_run, daemon=True).start()

    def _run_search_by_text(self):
        query = self.search_query_var.get().strip()
        search_dir = self.search_dir_var.get().strip()

        if not query:
            messagebox.showwarning("输入为空", "请输入搜索关键词")
            return
        if not os.path.isdir(search_dir):
            messagebox.showwarning("路径错误", "搜索文件夹不存在")
            return

        from core import clip_search
        clip_ok = clip_search.is_available()

        self.search_result_text.config(state="normal")
        self.search_result_text.delete("1.0", "end")
        self.search_result_text.config(state="disabled")

        if clip_ok:
            # CLIP 模式：毫秒级语义搜索
            self.search_status_var.set("CLIP 搜索中...")

            def _clip_search():
                # 确保索引存在
                info = clip_search.get_index_info()
                if info.get("total_images", 0) == 0:
                    self.after(0, lambda: self._append_search(
                        "⚠️ 尚未建立索引，正在自动索引...\n"))
                    # 自动建立索引
                    ok, msg = clip_search.index_folder(search_dir)
                    if not ok:
                        self.after(0, lambda: self._append_search(f"❌ {msg}\n"))
                        self.after(0, lambda: self.search_status_var.set(""))
                        return

                results = clip_search.search(query, top_n=int(self.top_k_var.get() or "10"))
                self.after(0, lambda: self._show_search_results(results, len(results)))

            threading.Thread(target=_clip_search, daemon=True).start()

        else:
            # 回退模式：VLM 逐张搜索（慢）
            model = self.toolbox_model_var.get()
            if not is_vision_model(model):
                messagebox.showwarning("模型不可用",
                    f"当前 {model} 不是视觉模型。\n请切换到 llava/moondream 等，或安装 CLIP：\npip install sentence-transformers faiss-cpu")
                return

            self.search_status_var.set("VLM 慢速搜索中...")

            def _vlm_search():
                images = []
                for root, _, files in os.walk(search_dir):
                    for f in files:
                        path = os.path.join(root, f)
                        if is_image_file(path):
                            images.append(path)

                if not images:
                    self.after(0, lambda: self._append_search("未找到图片文件\n"))
                    self.after(0, lambda: self.search_status_var.set(""))
                    return

                top_k = min(int(self.top_k_var.get() or "10"), len(images))
                self.after(0, lambda: self.search_status_var.set(f"VLM 分析 0/{len(images)}"))

                results = []
                for i, img_path in enumerate(images):
                    self.after(0, lambda idx=i+1, total=len(images):
                        self.search_status_var.set(f"VLM 分析 {idx}/{total}"))
                    try:
                        prompt = (f"问题：这张图片是否符合描述「{query}」？"
                                  f"只回答「是」或「否」，不要解释。")
                        b64 = encode_image(img_path, max_size_kb=384)
                        r = requests.post(f"{DEFAULT_URL}/api/generate", json={
                            "model": model, "prompt": prompt, "images": [b64],
                            "stream": False, "options": {"temperature": 0.1, "num_predict": 10}
                        }, timeout=120)
                        if r.status_code == 200:
                            resp = r.json().get("response", "").strip().lower()
                            if resp.startswith("是") or "yes" in resp or "符合" in resp:
                                results.append((img_path, 1.0))
                    except Exception:
                        pass

                self.after(0, lambda: self._show_search_results(results[:top_k], len(images)))

            threading.Thread(target=_vlm_search, daemon=True).start()

    def _show_search_results(self, results, total):
        self.search_result_text.config(state="normal")
        self.search_result_text.delete("1.0", "end")
        self.search_status_var.set(f"完成，返回 {len(results)} 张")
        if not results:
            self.search_result_text.insert("end", "未找到匹配的图片\n")
        else:
            self.search_result_text.insert("end", f"找到 {len(results)} 张匹配图片：\n\n")
            for i, (path, score) in enumerate(results, 1):
                pct = f"{score*100:.1f}%" if score <= 1.0 else f"{score:.3f}"
                line = f"{i}. [{pct}] {os.path.basename(path)}\n   {path}\n\n"
                self.search_result_text.insert("end", line)
        self.search_result_text.config(state="disabled")

    def _append_search(self, text):
        self.search_result_text.config(state="normal")
        self.search_result_text.insert("end", text)
        self.search_result_text.config(state="disabled")

    # ── 图片描述 ──
    def _build_describe_image(self):
        card = ctk.CTkFrame(self.tool_body, **card_frame_style())
        card.pack(fill="both", expand=True)

        ctk.CTkLabel(card, text="AI 图片描述", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(20, 8))
        ctk.CTkLabel(card, text="为单张图片生成可用于小红书、朋友圈、网站的文案描述。",
                     font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=24, pady=(0, 16))

        sel_row = ctk.CTkFrame(card, fg_color="transparent")
        sel_row.pack(fill="x", padx=24, pady=(0, 12))
        self.desc_img_var = ctk.StringVar(value="")
        ctk.CTkEntry(sel_row, textvariable=self.desc_img_var, font=font_safe(13, "normal"),
                     height=36, fg_color="white", border_color=COLORS["border"],
                     placeholder_text="选择一张图片...").pack(side="left", fill="x", expand=True, padx=(0, 12))
        ctk.CTkButton(sel_row, text="选择图片", command=self._choose_describe_image,
                      width=100, **secondary_button_style()).pack(side="left", padx=(0, 8))
        ctk.CTkButton(sel_row, text="生成描述", command=self._run_describe_image,
                      width=100, **primary_button_style()).pack(side="left")

        opt_row = ctk.CTkFrame(card, fg_color="transparent")
        opt_row.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkLabel(opt_row, text="风格", font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(side="left")
        self.desc_style_var = ctk.StringVar(value="通用")
        ctk.CTkOptionMenu(opt_row, variable=self.desc_style_var,
                          values=["通用", "小红书", "朋友圈", "产品详情", "SEO 标签"],
                          width=140, height=30, font=font_safe(13, "normal")).pack(side="left", padx=(8, 0))

        result_frame = ctk.CTkFrame(card, fg_color="transparent")
        result_frame.pack(fill="both", expand=True, padx=24, pady=(8, 20))
        self.desc_result_text = scrolledtext.ScrolledText(result_frame, wrap="word",
                                                          font=("SF Mono", 12), bg="#f8f9fa",
                                                          fg="#1D1D1F", relief="flat")
        self.desc_result_text.pack(fill="both", expand=True)

    def _choose_describe_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("图片", "*.jpg *.jpeg *.png *.heic *.heif *.webp"), ("所有文件", "*.*")])
        if path:
            self.desc_img_var.set(path)

    def _run_describe_image(self):
        path = self.desc_img_var.get().strip()
        model = self.toolbox_model_var.get()
        if not path or not os.path.isfile(path):
            messagebox.showwarning("路径错误", "请先选择一张图片")
            return
        if not is_vision_model(model):
            messagebox.showwarning("模型不可用",
                "图片描述需要视觉模型。请在上方切换到 llava/bakllava/moondream 等。")
            return

        style = self.desc_style_var.get()
        prompts = {
            "通用": "请详细描述这张图片的内容、场景、人物、色彩和构图。100-200字。",
            "小红书": "请为这张图片写一段小红书风格的文案，带 emoji，活泼亲切，100-150字。",
            "朋友圈": "请为这张图片写一段适合发朋友圈的文案，简洁有感觉，50-100字。",
            "产品详情": "请为这张图片写一段电商产品详情描述，突出卖点，100-200字。",
            "SEO 标签": "请为这张图片生成 10 个 SEO/标签关键词，用逗号分隔。"
        }

        self.desc_result_text.config(state="normal")
        self.desc_result_text.delete("1.0", "end")
        self.desc_result_text.insert("end", "⏳ 正在生成描述...\n")
        self.desc_result_text.config(state="disabled")

        def _describe():
            try:
                prompt = prompts.get(style, prompts["通用"])
                b64 = encode_image(path, max_size_kb=512)
                r = requests.post(f"{DEFAULT_URL}/api/generate", json={
                    "model": model, "prompt": prompt, "images": [b64],
                    "stream": False, "options": {"temperature": 0.4, "num_predict": 300}
                }, timeout=300)
                if r.status_code == 200:
                    desc = r.json().get("response", "").strip()
                    self.app.root.after(0, lambda: self._show_describe_result(desc))
                else:
                    self.app.root.after(0, lambda: self._show_describe_result(f"错误：HTTP {r.status_code}"))
            except Exception as e:
                self.app.root.after(0, lambda: self._show_describe_result(f"错误：{e}"))

        threading.Thread(target=_describe, daemon=True).start()

    def _show_describe_result(self, text):
        self.desc_result_text.config(state="normal")
        self.desc_result_text.delete("1.0", "end")
        self.desc_result_text.insert("end", text)
        self.desc_result_text.config(state="disabled")

    # ── 图片问答 ──
    def _build_visual_qa(self):
        card = ctk.CTkFrame(self.tool_body, **card_frame_style())
        card.pack(fill="both", expand=True)

        ctk.CTkLabel(card, text="图片问答", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(20, 8))
        ctk.CTkLabel(card, text="上传一张图片，针对图片内容提问。例如：'图中有几个人？''这个场景是在办公室吗？'",
                     font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=24, pady=(0, 16))

        sel_row = ctk.CTkFrame(card, fg_color="transparent")
        sel_row.pack(fill="x", padx=24, pady=(0, 12))
        self.qa_img_var = ctk.StringVar(value="")
        ctk.CTkEntry(sel_row, textvariable=self.qa_img_var, font=font_safe(13, "normal"),
                     height=36, fg_color="white", border_color=COLORS["border"],
                     placeholder_text="选择一张图片...").pack(side="left", fill="x", expand=True, padx=(0, 12))
        ctk.CTkButton(sel_row, text="选择图片", command=self._choose_qa_image,
                      width=100, **secondary_button_style()).pack(side="left")

        input_row = ctk.CTkFrame(card, fg_color="transparent")
        input_row.pack(fill="x", padx=24, pady=(0, 12))
        self.qa_input_var = ctk.StringVar(value="")
        ctk.CTkEntry(input_row, textvariable=self.qa_input_var, font=font_safe(13, "normal"),
                     height=36, fg_color="white", border_color=COLORS["border"],
                     placeholder_text="输入你的问题...").pack(side="left", fill="x", expand=True, padx=(0, 12))
        ctk.CTkButton(input_row, text="发送", command=self._run_qa,
                      width=80, **primary_button_style()).pack(side="left")

        chat_area = ctk.CTkFrame(card, fg_color=COLORS["bg"], corner_radius=8)
        chat_area.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self.qa_history = scrolledtext.ScrolledText(chat_area, wrap="word",
                                                    font=("SF Mono", 12), bg="#f8f9fa",
                                                    fg="#1D1D1F", relief="flat")
        self.qa_history.pack(fill="both", expand=True, padx=8, pady=8)
        self.qa_history.insert("1.0", "🤖 请选择图片并输入问题\n")
        self.qa_history.config(state="disabled")

    def _choose_qa_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("图片", "*.jpg *.jpeg *.png *.heic *.heif *.webp"), ("所有文件", "*.*")])
        if path:
            self.qa_img_var.set(path)

    def _run_qa(self):
        path = self.qa_img_var.get().strip()
        question = self.qa_input_var.get().strip()
        model = self.toolbox_model_var.get()

        if not path or not os.path.isfile(path):
            messagebox.showwarning("路径错误", "请先选择一张图片")
            return
        if not question:
            return
        if not is_vision_model(model):
            messagebox.showwarning("模型不可用",
                "图片问答需要视觉模型。请在上方切换到 llava/bakllava/moondream 等。")
            return

        self.qa_input_var.set("")
        self._append_qa(f"🧑 你：{question}\n", "user")
        self._append_qa("🤖 AI：思考中...\n", "ai")

        def _ask():
            try:
                prompt = f"请根据图片内容回答问题：{question}"
                b64 = encode_image(path, max_size_kb=512)
                r = requests.post(f"{DEFAULT_URL}/api/generate", json={
                    "model": model, "prompt": prompt, "images": [b64],
                    "stream": False, "options": {"temperature": 0.3, "num_predict": 300}
                }, timeout=300)
                if r.status_code == 200:
                    reply = r.json().get("response", "").strip()
                    self.app.root.after(0, lambda: self._show_qa_reply(reply))
                else:
                    self.app.root.after(0, lambda: self._show_qa_reply(f"[错误] HTTP {r.status_code}"))
            except Exception as e:
                self.app.root.after(0, lambda: self._show_qa_reply(f"[错误] {e}"))

        threading.Thread(target=_ask, daemon=True).start()

    def _append_qa(self, text, role):
        self.qa_history.config(state="normal")
        self.qa_history.insert("end", text)
        self.qa_history.see("end")
        self.qa_history.config(state="disabled")

    def _show_qa_reply(self, reply):
        self.qa_history.config(state="normal")
        content = self.qa_history.get("1.0", "end-1c")
        content = content.rsplit("🤖 AI：思考中...\n", 1)[0]
        self.qa_history.delete("1.0", "end")
        self.qa_history.insert("end", content)
        if content:
            self.qa_history.insert("end", "\n")
        self.qa_history.insert("end", f"🤖 AI：{reply}\n")
        self.qa_history.see("end")
        self.qa_history.config(state="disabled")

    # ── 智能助手（文本模型，如 qwen2.5）──
    def _build_smart_assistant(self):
        card = ctk.CTkFrame(self.tool_body, **card_frame_style())
        card.pack(fill="both", expand=True)

        ctk.CTkLabel(card, text="智能助手", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(20, 8))
        ctk.CTkLabel(card, text="使用文本模型（如 qwen2.5）进行文案生成、翻译、总结。这是纯文本模型在 SnapSort 中的主要用途。需要 Ollama 运行中。",
                     font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=24, pady=(0, 16))

        # 快捷功能
        quick_row = ctk.CTkFrame(card, fg_color="transparent")
        quick_row.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkLabel(quick_row, text="快捷功能", font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(side="left")
        presets = [
            ("\U0001f4dd 营销文案", "请为以下内容生成一段适合社交媒体发布的营销文案，带 emoji，200字以内：\n\n"),
            ("\U0001f310 中英翻译", "请将以下内容翻译成英文，保持专业商务口吻：\n\n"),
            ("\U0001f4cb 内容总结", "请用3个要点总结以下内容的核心信息：\n\n"),
            ("\U0001f3f7 关键词提取", "请从以下内容中提取10个关键词标签，用逗号分隔：\n\n"),
            ("\u270d\ufe0f 文案润色", "请润色以下文案，使其更加专业、简洁、有吸引力：\n\n"),
        ]
        for label, prefix in presets:
            ctk.CTkButton(quick_row, text=label, command=lambda p=prefix: self._use_assistant_preset(p),
                          height=28, font=font_safe(11, "normal"),
                          fg_color=COLORS["card"], hover_color=COLORS["hover"],
                          text_color=COLORS["text"], corner_radius=6,
                          border_color=COLORS["border_light"], border_width=1).pack(side="left", padx=(8, 0))

        # 输入区
        input_frame = ctk.CTkFrame(card, fg_color="transparent")
        input_frame.pack(fill="x", padx=24, pady=(0, 8))
        self.assistant_input = scrolledtext.ScrolledText(input_frame, wrap="word",
                                                          font=("SF Mono", 12), bg="#f8f9fa",
                                                          fg="#999999", relief="flat", height=80)
        self.assistant_input.pack(fill="x")
        self._assistant_placeholder = True
        self.assistant_input.insert("1.0", "在此输入内容，或点击上方快捷功能...")
        self.assistant_input.bind("<FocusIn>", self._assistant_on_focus_in)
        self.assistant_input.bind("<FocusOut>", self._assistant_on_focus_out)

        # 发送按钮
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkButton(btn_row, text="\U0001f680 发送", command=self._run_assistant,
                      **primary_button_style()).pack(side="left", padx=(0, 12))
        self.assistant_status_var = ctk.StringVar(value="")
        ctk.CTkLabel(btn_row, textvariable=self.assistant_status_var,
                     font=font_safe(12, "normal"),
                     text_color=COLORS["text_secondary"]).pack(side="left")

        # 结果区
        result_frame = ctk.CTkFrame(card, fg_color=COLORS["bg"], corner_radius=8)
        result_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self.assistant_result = scrolledtext.ScrolledText(result_frame, wrap="word",
                                                           font=("SF Mono", 12), bg="#f8f9fa",
                                                           fg="#1D1D1F", relief="flat")
        self.assistant_result.pack(fill="both", expand=True, padx=8, pady=8)
        self.assistant_result.insert("1.0", "AI 回复将显示在这里...")
        self.assistant_result.config(state="disabled")

    def _assistant_on_focus_in(self, event=None):
        """输入框获得焦点时清除占位文本"""
        if self._assistant_placeholder:
            self.assistant_input.delete("1.0", "end")
            self.assistant_input.configure(fg="#1D1D1F")
            self._assistant_placeholder = False

    def _assistant_on_focus_out(self, event=None):
        """输入框失去焦点时恢复占位文本"""
        content = self.assistant_input.get("1.0", "end-1c").strip()
        if not content:
            self.assistant_input.delete("1.0", "end")
            self.assistant_input.insert("1.0", "在此输入内容，或点击上方快捷功能...")
            self.assistant_input.configure(fg="#999999")
            self._assistant_placeholder = True

    def _use_assistant_preset(self, prefix):
        """快捷功能：填入预设前缀，光标定位到末尾"""
        self._assistant_placeholder = False
        self.assistant_input.delete("1.0", "end")
        self.assistant_input.configure(fg="#1D1D1F")
        self.assistant_input.insert("1.0", prefix)
        self.assistant_input.see("end")
        self.assistant_input.focus_set()
        self.assistant_input.mark_set("insert", "end")

    def _run_assistant(self):
        # 获取输入文本，跳过占位符
        if self._assistant_placeholder:
            messagebox.showwarning("输入为空", "请先输入内容，或点击上方快捷功能")
            return
        text = self.assistant_input.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("输入为空", "请先输入内容")
            return

        model = self.toolbox_model_var.get()

        # 先检查 Ollama 是否在线
        self.assistant_status_var.set("正在连接 Ollama...")
        self.assistant_result.config(state="normal")
        self.assistant_result.delete("1.0", "end")
        self.assistant_result.insert("end", "\u23f3 正在连接 Ollama...\n")
        self.assistant_result.config(state="disabled")

        def _generate():
            try:
                # 先检查连接
                try:
                    check = requests.get(f"{DEFAULT_URL}/api/tags", timeout=5)
                    if check.status_code != 200:
                        self.app.root.after(0, lambda: self._show_assistant_result(
                            "\u274c Ollama 未正常运行\n\n请先启动 Ollama：\n- Mac: 打开 Ollama 应用\n- Windows: 运行 ollama serve"))
                        return
                except requests.exceptions.ConnectionError:
                    self.app.root.after(0, lambda: self._show_assistant_result(
                        "\u274c 无法连接 Ollama (localhost:11434)\n\n请先启动 Ollama：\n- Mac: 打开 Ollama 应用\n- Windows: 运行 ollama serve"))
                    return

                # 检查模型是否可用
                available_models = [m["name"] for m in check.json().get("models", [])]
                if available_models and model not in available_models:
                    # 尝试模糊匹配
                    base = model.split(":")[0]
                    matched = [m for m in available_models if m.startswith(base)]
                    if matched:
                        model_to_use = matched[0]
                    else:
                        model_to_use = available_models[0]
                        self.app.root.after(0, lambda: self._show_assistant_result(
                            f"\u26a0\ufe0f 模型 {model} 未安装，自动切换到 {model_to_use}\n\n"))
                else:
                    model_to_use = model

                self.app.root.after(0, lambda: self.assistant_status_var.set(
                    f"正在用 {model_to_use} 生成..."))
                self.app.root.after(0, lambda: self._show_assistant_result(
                    f"\u23f3 正在用 {model_to_use} 生成...\n"))

                r = requests.post(f"{DEFAULT_URL}/api/generate", json={
                    "model": model_to_use, "prompt": text,
                    "stream": False, "options": {"temperature": 0.7, "num_predict": 500}
                }, timeout=300)
                if r.status_code == 200:
                    reply = r.json().get("response", "").strip()
                    if not reply:
                        reply = "(模型返回了空回复，请尝试换一种问法)"
                    self.app.root.after(0, lambda: self._show_assistant_result(reply))
                else:
                    err = r.json().get("error", "") if r.headers.get("content-type", "").startswith("application/json") else ""
                    self.app.root.after(0, lambda: self._show_assistant_result(
                        f"\u274c 错误：HTTP {r.status_code}\n{err}"))
            except requests.exceptions.ConnectionError:
                self.app.root.after(0, lambda: self._show_assistant_result(
                    "\u274c 无法连接 Ollama\n\n请确保 Ollama 正在运行：\n- Mac: 打开 Ollama 应用\n- Windows: 运行 ollama serve"))
            except requests.exceptions.Timeout:
                self.app.root.after(0, lambda: self._show_assistant_result(
                    "\u274c 请求超时（300秒）\n\n模型可能正在加载中，请稍后重试。"))
            except Exception as e:
                self.app.root.after(0, lambda: self._show_assistant_result(f"\u274c 错误：{e}"))

        threading.Thread(target=_generate, daemon=True).start()

    def _show_assistant_result(self, text):
        self.assistant_result.config(state="normal")
        self.assistant_result.delete("1.0", "end")
        self.assistant_result.insert("end", text)
        self.assistant_result.config(state="disabled")
        self.assistant_status_var.set("完成")

    # ── 重复图片检测 ──
    def _build_dedup(self):
        card = ctk.CTkFrame(self.tool_body, **card_frame_style())
        card.pack(fill="both", expand=True)

        ctk.CTkLabel(card, text="重复图片检测", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(20, 8))
        ctk.CTkLabel(card, text="基于文件内容哈希（MD5）检测完全相同的图片，不依赖 AI 模型。",
                     font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=24, pady=(0, 16))

        dir_row = ctk.CTkFrame(card, fg_color="transparent")
        dir_row.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkLabel(dir_row, text="检测目录", font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"], width=80).pack(side="left")
        self.dedup_dir_var = ctk.StringVar(value=self.app.output_var.get() or os.path.expanduser("~/Desktop"))
        ctk.CTkEntry(dir_row, textvariable=self.dedup_dir_var, font=font_safe(13, "normal"),
                     height=36, fg_color=COLORS["bg"], border_color=COLORS["border"]).pack(
                         side="left", fill="x", expand=True, padx=(12, 12))
        ctk.CTkButton(dir_row, text="选择…", command=self._choose_dedup_dir,
                      width=80, **secondary_button_style()).pack(side="left")

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkButton(btn_row, text="🔍 开始检测", command=self._run_dedup,
                      **primary_button_style()).pack(side="left", padx=(0, 12))
        self.dedup_status_var = ctk.StringVar(value="")
        ctk.CTkLabel(btn_row, textvariable=self.dedup_status_var,
                     font=font_safe(12, "normal"),
                     text_color=COLORS["text_secondary"]).pack(side="left")

        # 结果区：滚动框架 + 每行带操作按钮
        result_scroll = ctk.CTkScrollableFrame(card, fg_color=COLORS["bg"], height=300)
        result_scroll.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self.dedup_result = scrolledtext.ScrolledText(result_scroll, wrap="word",
                                                       font=("SF Mono", 12), bg="#f8f9fa",
                                                       fg="#1D1D1F", relief="flat", height=60)
        self.dedup_result.pack(fill="x", padx=0, pady=(0, 8))
        self.dedup_result.insert("1.0", "重复图片列表将显示在这里...")
        self.dedup_result.config(state="disabled")

        # 操作按钮容器
        self.dedup_actions_frame = ctk.CTkFrame(result_scroll, fg_color="transparent")
        self.dedup_actions_frame.pack(fill="both", expand=True)
        self._dedup_duplicate_list = []  # 缓存重复列表，供操作按钮使用

    def _choose_dedup_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.dedup_dir_var.set(path)

    def _run_dedup(self):
        search_dir = self.dedup_dir_var.get().strip()
        if not os.path.isdir(search_dir):
            messagebox.showwarning("路径错误", "目录不存在")
            return

        self.dedup_status_var.set("正在扫描...")
        self.dedup_result.config(state="normal")
        self.dedup_result.delete("1.0", "end")
        self.dedup_result.insert("end", "🔍 正在扫描图片并计算哈希...\n")
        self.dedup_result.config(state="disabled")

        def _scan():
            hashes = {}
            duplicates = []
            total = 0

            for root, _, files in os.walk(search_dir):
                for f in files:
                    path = os.path.join(root, f)
                    if not is_image_file(path):
                        continue
                    total += 1
                    if total % 50 == 0:
                        self.app.root.after(0, lambda t=total:
                            self.dedup_status_var.set(f"已扫描 {t} 张..."))
                    try:
                        with open(path, "rb") as fp:
                            md5 = hashlib.md5(fp.read()).hexdigest()
                        if md5 in hashes:
                            duplicates.append((hashes[md5], path))
                        else:
                            hashes[md5] = path
                    except Exception:
                        pass

            self.app.root.after(0, lambda: self._show_dedup_results(duplicates, total, len(hashes)))

        threading.Thread(target=_scan, daemon=True).start()

    def _show_dedup_results(self, duplicates, total, unique_count):
        # 清理旧的操作按钮
        for w in self.dedup_actions_frame.winfo_children():
            w.destroy()
        self._dedup_duplicate_list = duplicates

        # 更新摘要文本
        self.dedup_result.config(state="normal")
        self.dedup_result.delete("1.0", "end")

        if not duplicates:
            self.dedup_result.insert("end", f"✅ 未发现重复图片\n\n共扫描 {total} 张，{unique_count} 张唯一\n")
            self.dedup_status_var.set(f"完成：{total} 张中无重复")
        else:
            self.dedup_result.insert("end",
                f"⚠️ 发现 {len(duplicates)} 组重复图片\n"
                f"共扫描 {total} 张，{unique_count} 张唯一，{len(duplicates)} 张重复\n"
                f"↓ 下方可逐组操作：打开文件夹 或 删除重复文件\n")
            self.dedup_status_var.set(f"完成：发现 {len(duplicates)} 组重复")

            # 为每组重复添加操作按钮行
            for i, (orig, dup) in enumerate(duplicates, 1):
                row = ctk.CTkFrame(self.dedup_actions_frame, fg_color=COLORS["card"],
                                   corner_radius=8, border_color=COLORS["border_light"],
                                   border_width=1)
                row.pack(fill="x", pady=(0, 6))

                # 信息标签
                info_frame = ctk.CTkFrame(row, fg_color="transparent")
                info_frame.pack(fill="x", padx=12, pady=(8, 4))

                orig_name = os.path.basename(orig)[:30]
                dup_name = os.path.basename(dup)[:30]
                ctk.CTkLabel(info_frame, text=f"#{i} 原始: {orig_name}",
                             font=font_safe(12, "normal"),
                             text_color=COLORS["text"]).pack(anchor="w")
                ctk.CTkLabel(info_frame, text=f"    重复: {dup_name}",
                             font=font_safe(12, "normal"),
                             text_color=COLORS["text_secondary"]).pack(anchor="w")

                # 按钮行
                btn_row = ctk.CTkFrame(row, fg_color="transparent")
                btn_row.pack(fill="x", padx=12, pady=(0, 8))

                ctk.CTkButton(btn_row, text="📂 打开原始", width=90, height=28,
                              font=font_safe(11, "normal"),
                              fg_color=COLORS["card"], hover_color=COLORS["hover"],
                              text_color=COLORS["text"],
                              command=lambda p=orig: self._open_file_location(p)).pack(side="left", padx=(0, 6))

                ctk.CTkButton(btn_row, text="📂 打开重复", width=90, height=28,
                              font=font_safe(11, "normal"),
                              fg_color=COLORS["card"], hover_color=COLORS["hover"],
                              text_color=COLORS["text"],
                              command=lambda p=dup: self._open_file_location(p)).pack(side="left", padx=(0, 16))

                ctk.CTkButton(btn_row, text="🗑 删除此重复文件", width=130, height=28,
                              font=font_safe(11, "normal"),
                              fg_color=COLORS["danger"], hover_color="#E6352B",
                              text_color="white",
                              command=lambda p=dup, r=row: self._dedup_delete(p, r)).pack(side="left")

        self.dedup_result.config(state="disabled")

    def _open_file_location(self, path):
        """在文件管理器中打开文件所在位置"""
        import subprocess, platform
        if not os.path.exists(path):
            messagebox.showwarning("文件不存在", f"文件已不存在：\n{path}")
            return
        try:
            folder = os.path.dirname(path)
            if platform.system() == "Darwin":
                subprocess.run(["open", "-R", path])
            elif platform.system() == "Windows":
                subprocess.run(["explorer", "/select,", path])
            else:
                subprocess.run(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开：{e}")

    def _dedup_delete(self, path, row_widget):
        """删除重复文件并移除对应操作行"""
        if not os.path.exists(path):
            row_widget.destroy()
            return
        if messagebox.askyesno("确认删除", f"确定要删除此重复文件吗？\n\n{path}\n\n⚠️ 此操作不可撤销！"):
            try:
                os.remove(path)
                row_widget.destroy()
                messagebox.showinfo("已删除", f"已删除：\n{os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("删除失败", str(e))

    # ── 自定义重命名 ──
    def _build_custom_rename(self):
        card = ctk.CTkFrame(self.tool_body, **card_frame_style())
        card.pack(fill="both", expand=True)

        ctk.CTkLabel(card, text="自定义批量重命名", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(20, 8))
        ctk.CTkLabel(card, text="选择文件夹，设置命名规则，预览后一键重命名。支持子文件夹递归处理。",
                     font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=24, pady=(0, 16))

        # 文件夹选择
        dir_row = ctk.CTkFrame(card, fg_color="transparent")
        dir_row.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkLabel(dir_row, text="目标文件夹", font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"], width=80).pack(side="left")
        self.rename_dir_var = ctk.StringVar(value=self.app.output_var.get() or os.path.expanduser("~/Desktop"))
        ctk.CTkEntry(dir_row, textvariable=self.rename_dir_var, font=font_safe(13, "normal"),
                     height=36, fg_color=COLORS["bg"], border_color=COLORS["border"]).pack(
                         side="left", fill="x", expand=True, padx=(12, 12))
        ctk.CTkButton(dir_row, text="选择…", command=self._choose_rename_dir,
                      width=80, **secondary_button_style()).pack(side="left")

        # 命名规则
        pattern_row = ctk.CTkFrame(card, fg_color="transparent")
        pattern_row.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkLabel(pattern_row, text="命名规则", font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"], width=80).pack(side="left")
        self.rename_pattern_var = ctk.StringVar(
            value=self.app.config_manager.get("event_mode", {}).get("rename_pattern", "{date}_{event}_{seq:02d}{grade}_{desc}"))
        pattern_entry = ctk.CTkEntry(pattern_row, textvariable=self.rename_pattern_var,
                                     font=font_safe(13, "normal"), height=36,
                                     fg_color="white", border_color=COLORS["border"])
        pattern_entry.pack(side="left", fill="x", expand=True, padx=(12, 0))

        # 变量说明（可点击插入）
        var_row = ctk.CTkFrame(card, fg_color="transparent")
        var_row.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkLabel(var_row, text="可用变量（点击插入）：", font=font_safe(11, "normal"),
                     text_color=COLORS["text_secondary"]).pack(side="left")
        var_chips = [
            ("{name}", "原文件名"),
            ("{seq}", "序号"),
            ("{seq:02d}", "序号01"),
            ("{seq:03d}", "序号001"),
            ("{date}", "日期"),
            ("{parent}", "上级文件夹"),
            ("{ext}", "扩展名"),
        ]
        for var_text, var_tip in var_chips:
            ctk.CTkButton(var_row, text=f"{var_text} {var_tip}",
                          command=lambda v=var_text: self._insert_rename_var(v),
                          height=24, font=font_safe(10, "normal"),
                          fg_color=COLORS["selected"], hover_color=COLORS["hover"],
                          text_color=COLORS["primary"], corner_radius=5,
                          border_color=COLORS["border_light"], border_width=1).pack(
                              side="left", padx=(4, 0))

        # 选项行
        opt_row = ctk.CTkFrame(card, fg_color="transparent")
        opt_row.pack(fill="x", padx=24, pady=(0, 12))
        self.rename_recursive_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt_row, text="包含子文件夹", variable=self.rename_recursive_var,
                        font=font_safe(12, "normal"), text_color=COLORS["text"],
                        fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]).pack(side="left")
        ctk.CTkLabel(opt_row, text="  起始序号", font=font_safe(12, "normal"),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(16, 0))
        self.rename_start_seq_var = ctk.StringVar(value="1")
        ctk.CTkEntry(opt_row, textvariable=self.rename_start_seq_var, width=50, height=28,
                     font=font_safe(12, "normal"), fg_color="white",
                     border_color=COLORS["border"]).pack(side="left", padx=(6, 0))
        ctk.CTkLabel(opt_row, text="  筛选", font=font_safe(12, "normal"),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(16, 0))
        self.rename_filter_var = ctk.StringVar(value="仅图片")
        ctk.CTkOptionMenu(opt_row, variable=self.rename_filter_var,
                          values=["仅图片", "所有文件"], width=100, height=28,
                          font=font_safe(12, "normal")).pack(side="left", padx=(6, 0))

        # 操作按钮
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkButton(btn_row, text="👁 预览", command=self._preview_rename,
                      **secondary_button_style()).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="✅ 确认重命名", command=self._apply_rename,
                      **primary_button_style()).pack(side="left", padx=(0, 8))
        self.rename_status_var = ctk.StringVar(value="")
        ctk.CTkLabel(btn_row, textvariable=self.rename_status_var,
                     font=font_safe(12, "normal"),
                     text_color=COLORS["text_secondary"]).pack(side="left")

        # 预览/结果区
        result_frame = ctk.CTkFrame(card, fg_color=COLORS["bg"], corner_radius=8)
        result_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self.rename_preview = scrolledtext.ScrolledText(result_frame, wrap="word",
                                                        font=("SF Mono", 12), bg="#f8f9fa",
                                                        fg="#1D1D1F", relief="flat")
        self.rename_preview.pack(fill="both", expand=True, padx=8, pady=8)
        self.rename_preview.insert("1.0", "点击「👁 预览」查看重命名方案\n"
                                       "可用变量：{name} {seq} {seq:02d} {date} {parent} {ext}\n"
                                       "示例规则：{parent}_{seq:03d}{ext}  →  工厂图_001.jpg")
        self.rename_preview.config(state="disabled")

        # 缓存预览结果
        self._rename_preview_data = []

    def _choose_rename_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.rename_dir_var.set(path)

    def _insert_rename_var(self, var_text):
        """在命名规则输入框光标处插入变量"""
        entry = self.rename_pattern_var
        current = entry.get()
        # 简单追加到末尾（CTkEntry 没有 icursor 的直接接口，追加最稳妥）
        entry.set(current + var_text)

    def _scan_rename_files(self):
        """扫描目标文件夹，返回文件路径列表"""
        target_dir = self.rename_dir_var.get().strip()
        if not os.path.isdir(target_dir):
            return []

        recursive = self.rename_recursive_var.get()
        filter_mode = self.rename_filter_var.get()
        files = []

        if recursive:
            for root, _, fnames in os.walk(target_dir):
                for f in fnames:
                    path = os.path.join(root, f)
                    if filter_mode == "仅图片" and not is_image_file(path):
                        continue
                    files.append(path)
        else:
            for f in os.listdir(target_dir):
                path = os.path.join(target_dir, f)
                if os.path.isfile(path):
                    if filter_mode == "仅图片" and not is_image_file(path):
                        continue
                    files.append(path)

        files.sort()
        return files

    def _build_new_name(self, file_path, seq, pattern):
        """根据模板生成新文件名"""
        fname = os.path.basename(file_path)
        base, ext = os.path.splitext(fname)
        parent = os.path.basename(os.path.dirname(file_path))

        # 获取日期
        try:
            from core.event_classifier import get_date
            date_str = get_date(file_path)
        except Exception:
            import time
            date_str = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(file_path)))

        name = pattern
        name = name.replace("{name}", base)
        name = name.replace("{ext}", ext)
        name = name.replace("{date}", date_str)
        name = name.replace("{parent}", parent)
        # 支持 {seq} {seq:02d} {seq:03d} 等
        name = __import__("re").sub(
            r'\{seq(?::(\d+)d)?\}',
            lambda m: str(seq).zfill(int(m.group(1)) if m.group(1) else 0),
            name
        )

        # 如果不包含 {ext}，自动补上
        if not name.endswith(ext) and ext:
            name += ext

        # 清理非法字符
        name = __import__("re").sub(r'[\\/:*?"<>|]', '', name)
        return name

    def _preview_rename(self):
        files = self._scan_rename_files()
        if not files:
            self._show_rename_preview("未找到符合条件的文件")
            self.rename_status_var.set("未找到文件")
            return

        pattern = self.rename_pattern_var.get().strip()
        if not pattern:
            self._show_rename_preview("请输入命名规则")
            return

        try:
            start_seq = int(self.rename_start_seq_var.get() or "1")
        except ValueError:
            start_seq = 1

        # 生成预览
        lines = [f"📋 重命名预览（共 {len(files)} 个文件）\n", "=" * 60, ""]
        self._rename_preview_data = []

        has_conflict = False
        new_names_set = set()

        for i, path in enumerate(files):
            old_name = os.path.basename(path)
            seq = start_seq + i
            new_name = self._build_new_name(path, seq, pattern)
            new_path = os.path.join(os.path.dirname(path), new_name)

            # 检查冲突
            conflict = ""
            if new_name == old_name:
                conflict = "  (无变化)"
            elif os.path.exists(new_path) and path != new_path:
                conflict = "  ⚠️ 目标已存在"
                has_conflict = True
            elif new_name in new_names_set:
                conflict = "  ⚠️ 重名冲突"
                has_conflict = True

            new_names_set.add(new_name)
            lines.append(f"  {old_name}")
            lines.append(f"  → {new_name}{conflict}")
            lines.append("")

            self._rename_preview_data.append((path, new_path, new_name, old_name))

        if has_conflict:
            lines.insert(2, "⚠️ 存在冲突，冲突文件将被自动加序号后缀")
            lines.insert(3, "")

        lines.append("=" * 60)
        lines.append(f"共 {len(files)} 个文件，"
                     f"其中 {sum(1 for _, _, nn, on in self._rename_preview_data if nn != on)} 个将被重命名")

        self._show_rename_preview("\n".join(lines))
        self.rename_status_var.set(f"预览完成：{len(files)} 个文件")

    def _show_rename_preview(self, text):
        self.rename_preview.config(state="normal")
        self.rename_preview.delete("1.0", "end")
        self.rename_preview.insert("end", text)
        self.rename_preview.config(state="disabled")

    def _apply_rename(self):
        if not self._rename_preview_data:
            # 没有预览数据，先预览
            self._preview_rename()
            return

        # 确认
        total = len(self._rename_preview_data)
        to_rename = [(old, new) for old, new, nn, on in self._rename_preview_data if nn != on]

        if not to_rename:
            messagebox.showinfo("无需操作", "所有文件名已经符合规则，无需重命名")
            return

        if not messagebox.askyesno("确认重命名",
                                   f"即将重命名 {len(to_rename)} 个文件\n\n"
                                   f"⚠️ 此操作不可撤销！\n\n确定继续？"):
            return

        # 执行重命名
        ok = 0
        fail = 0
        skipped = 0

        for old_path, new_path, new_name, old_name in self._rename_preview_data:
            if new_name == old_name:
                skipped += 1
                continue
            try:
                # 处理目标已存在
                if os.path.exists(new_path) and old_path != new_path:
                    base, ext = os.path.splitext(new_path)
                    c = 1
                    while os.path.exists(f"{base}_{c}{ext}"):
                        c += 1
                    new_path = f"{base}_{c}{ext}"

                os.rename(old_path, new_path)
                ok += 1
            except Exception as e:
                fail += 1

        # 更新预览显示结果
        self._show_rename_preview(
            f"{'=' * 60}\n"
            f"✅ 重命名完成\n"
            f"{'=' * 60}\n\n"
            f"成功：{ok} 个\n"
            f"跳过：{skipped} 个（无需改名）\n"
            f"失败：{fail} 个\n"
        )
        self.rename_status_var.set(f"完成：成功 {ok}，失败 {fail}")
        self._rename_preview_data = []

        if fail > 0:
            messagebox.showwarning("部分失败", f"{fail} 个文件重命名失败，请检查权限或文件是否被占用")
        else:
            messagebox.showinfo("完成", f"成功重命名 {ok} 个文件")

    # ── 模型列表异步加载 ──
    def _refresh_models(self):
        self.toolbox_model_combo.configure(values=["加载中..."])

        def _load():
            try:
                models = fetch_all_models()
                if not models:
                    models = ["llava:13b", "llava:7b", "bakllava:latest", "moondream:latest", "qwen2.5:7b"]
                self._safe_after(lambda: self._on_models_loaded(models))
            except Exception:
                self._safe_after(lambda: self._on_models_loaded(["llava:13b"]))

        threading.Thread(target=_load, daemon=True).start()

    def _safe_after(self, callback):
        """安全地在主线程执行回调（窗口已关闭则不执行）"""
        try:
            if self.winfo_exists():
                self.after(0, callback)
        except Exception:
            pass

    def _on_models_loaded(self, models):
        self.toolbox_model_combo.configure(values=models)
        if self.toolbox_model_var.get() not in models and models:
            current_tool = self.tool_var.get()
            if current_tool == "smart_assistant":
                # 智能助手优先选文本模型
                preferred = [m for m in models if not is_vision_model(m)]
                self.toolbox_model_var.set(preferred[0] if preferred else models[0])
            else:
                # 其他工具优先视觉模型
                preferred = [m for m in models if is_vision_model(m)]
                self.toolbox_model_var.set(preferred[0] if preferred else models[0])
        self._on_model_change(self.toolbox_model_var.get())

    # ── 格式转换 ──
    def _build_format_convert(self):
        card = ctk.CTkFrame(self.tool_body, **card_frame_style())
        card.pack(fill="both", expand=True)

        ctk.CTkLabel(card, text="批量格式转换", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(20, 8))
        ctk.CTkLabel(card, text="批量转换图片格式，自动保留 EXIF 拍摄时间。支持 HEIC→JPG、JPG→PNG、PNG→WebP 等。",
                     font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=24, pady=(0, 16))

        # 文件夹选择
        folder_row = ctk.CTkFrame(card, fg_color="transparent")
        folder_row.pack(fill="x", padx=24, pady=(0, 12))
        self.fc_folder_var = ctk.StringVar()
        ctk.CTkEntry(folder_row, textvariable=self.fc_folder_var,
                     font=font_safe(13), height=38,
                     fg_color=COLORS["bg"], border_color=COLORS["border"],
                     placeholder_text="选择图片文件夹...").pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(folder_row, text="📂 选择", width=80,
                      command=self._fc_pick_folder,
                      **secondary_button_style()).pack(side="left")

        # 格式 + 质量
        opt_row = ctk.CTkFrame(card, fg_color="transparent")
        opt_row.pack(fill="x", padx=24, pady=(0, 12))

        ctk.CTkLabel(opt_row, text="目标格式", font=font_safe(13, "bold"),
                     text_color=COLORS["text"]).pack(side="left", padx=(0, 8))
        self.fc_format_var = ctk.StringVar(value="JPEG")
        ctk.CTkOptionMenu(opt_row, variable=self.fc_format_var,
                          values=["JPEG", "PNG", "WebP"],
                          width=120, height=34,
                          font=font_safe(13)).pack(side="left", padx=(0, 16))

        ctk.CTkLabel(opt_row, text="质量", font=font_safe(13, "bold"),
                     text_color=COLORS["text"]).pack(side="left", padx=(0, 8))
        self.fc_quality_var = ctk.IntVar(value=95)
        ctk.CTkSlider(opt_row, from_=50, to=100, variable=self.fc_quality_var,
                      width=120, height=20,
                      fg_color=COLORS["border"],
                      progress_color=COLORS["primary"]).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(opt_row, textvariable=self.fc_quality_var,
                     font=font_safe(12), text_color=COLORS["text_secondary"],
                     width=30).pack(side="left")

        # EXIF 保留
        self.fc_keep_exif = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(card, text="保留 EXIF（拍摄时间、GPS 等元数据，事件分类依赖此数据）",
                        variable=self.fc_keep_exif,
                        font=font_safe(13), text_color=COLORS["text"],
                        fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]
                        ).pack(anchor="w", padx=24, pady=(0, 12))

        # 按钮
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 12))
        self.fc_run_btn = ctk.CTkButton(btn_row, text="🔄 开始转换", **primary_button_style())
        self.fc_run_btn.pack(side="left")
        self.fc_run_btn.configure(command=self._fc_run)

        # 日志
        self.fc_log = scrolledtext.ScrolledText(card, height=180, wrap="word",
                                                font=("SF Mono", 11) if os.path != "Windows" else ("Consolas", 11),
                                                bg="#1e1b18", fg="#e2ddd5",
                                                relief="flat", borderwidth=0)
        self.fc_log.pack(fill="both", expand=True, padx=24, pady=(0, 20))

    def _fc_pick_folder(self):
        d = filedialog.askdirectory(title="选择图片文件夹")
        if d:
            self.fc_folder_var.set(d)

    def _fc_run(self):
        folder = self.fc_folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("提示", "请先选择有效的图片文件夹")
            return

        fmt = self.fc_format_var.get()
        quality = self.fc_quality_var.get()
        keep_exif = self.fc_keep_exif.get()

        self.fc_run_btn.configure(state="disabled", text="⏳ 转换中...")
        self.fc_log.delete("1.0", "end")
        self._fc_log(f"📂 文件夹: {folder}")
        self._fc_log(f"格式: {fmt}  质量: {quality}  保留EXIF: {keep_exif}")
        self._fc_log("─" * 40)

        def _run():
            from core.image_utils import _safe_open_image
            try:
                from PIL import Image
            except ImportError:
                self._fc_log("❌ 需要 Pillow 库")
                return

            files = []
            for root, _, fnames in os.walk(folder):
                for fn in fnames:
                    p = os.path.join(root, fn)
                    if is_image_file(p):
                        files.append(p)

            self._fc_log(f"📸 找到 {len(files)} 张图片")

            ok = ng = 0
            ext_map = {"JPEG": ".jpg", "PNG": ".png", "WebP": ".webp"}
            new_ext = ext_map.get(fmt, ".jpg")

            for i, path in enumerate(files):
                try:
                    img, _ = _safe_open_image(path)
                    if img is None:
                        raise ValueError("无法打开图片")

                    out_dir = os.path.dirname(path)
                    base = os.path.splitext(os.path.basename(path))[0]
                    out_path = os.path.join(out_dir, base + new_ext)

                    # 避免覆盖原文件
                    if out_path == path:
                        out_path = os.path.join(out_dir, base + "_converted" + new_ext)

                    save_kwargs = {}
                    if fmt == "JPEG":
                        save_kwargs["quality"] = quality
                    elif fmt == "WebP":
                        save_kwargs["quality"] = quality

                    if keep_exif:
                        exif = img.info.get("exif", b"")
                        if exif:
                            save_kwargs["exif"] = exif

                    # 转为 RGB（JPEG 不支持 RGBA）
                    if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")

                    img.save(out_path, fmt, **save_kwargs)
                    ok += 1

                    if (i + 1) % 10 == 0:
                        self._fc_log(f"   {i+1}/{len(files)} 已转换")
                except Exception as e:
                    ng += 1
                    self._fc_log(f"   ❌ {os.path.basename(path)}: {e}")

            self._fc_log("─" * 40)
            self._fc_log(f"✅ 成功: {ok}  ❌ 失败: {ng}")

            def _done():
                self.fc_run_btn.configure(state="normal", text="🔄 开始转换")
            self.after(0, _done)

        threading.Thread(target=_run, daemon=True).start()

    def _fc_log(self, msg):
        self.fc_log.insert("end", msg + "\n")
        self.fc_log.see("end")

    # ── EXIF 查看 ──
    def _build_exif_view(self):
        card = ctk.CTkFrame(self.tool_body, **card_frame_style())
        card.pack(fill="both", expand=True)

        ctk.CTkLabel(card, text="EXIF 元数据查看", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(20, 8))
        ctk.CTkLabel(card, text="查看图片的拍摄时间、设备、GPS 等元数据。无 EXIF 的图片可能是截图或转发图。",
                     font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=24, pady=(0, 16))

        file_row = ctk.CTkFrame(card, fg_color="transparent")
        file_row.pack(fill="x", padx=24, pady=(0, 12))
        self.exif_file_var = ctk.StringVar()
        ctk.CTkEntry(file_row, textvariable=self.exif_file_var,
                     font=font_safe(13), height=38,
                     fg_color=COLORS["bg"], border_color=COLORS["border"],
                     placeholder_text="选择图片...").pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(file_row, text="📂 选择", width=80,
                      command=self._exif_pick_file,
                      **secondary_button_style()).pack(side="left")

        self.exif_result = scrolledtext.ScrolledText(card, height=300, wrap="word",
                                                     font=("SF Mono", 12) if os.name != "nt" else ("Consolas", 12),
                                                     bg="#1e1b18", fg="#e2ddd5",
                                                     relief="flat", borderwidth=0)
        self.exif_result.pack(fill="both", expand=True, padx=24, pady=(0, 20))

    def _exif_pick_file(self):
        f = filedialog.askopenfilename(title="选择图片",
                                      filetypes=[("图片", "*.jpg *.jpeg *.png *.heic *.heif *.webp *.bmp"), ("所有文件", "*.*")])
        if f:
            self.exif_file_var.set(f)
            self._exif_show(f)

    def _exif_show(self, path):
        self.exif_result.delete("1.0", "end")
        self._exif_log(f"📄 文件: {os.path.basename(path)}")
        self._exif_log(f"📁 路径: {path}")
        self._exif_log(f"💾 大小: {os.path.getsize(path) / 1024:.1f} KB")
        import time as _time
        st = os.stat(path)
        self._exif_log(f"📂 文件创建时间: {_time.strftime('%Y-%m-%d %H:%M:%S', _time.localtime(st.st_ctime))}")
        self._exif_log(f"📂 文件修改时间: {_time.strftime('%Y-%m-%d %H:%M:%S', _time.localtime(st.st_mtime))}")
        self._exif_log("─" * 40)

        try:
            from core.image_utils import _safe_open_image
            from PIL.ExifTags import TAGS
            import hashlib as _hashlib

            img, fmt = _safe_open_image(path)
            if img is None:
                self._exif_log("❌ 无法打开图片")
                return

            self._exif_log(f"🖼 格式: {fmt}")
            self._exif_log(f"📐 尺寸: {img.width} x {img.height} 像素")
            self._exif_log(f"🎨 色彩模式: {img.mode}")
            megapixels = img.width * img.height / 1_000_000
            self._exif_log(f"📐 分辨率: {megapixels:.1f} MP")

            # 文件 MD5
            try:
                with open(path, "rb") as f:
                    md5 = _hashlib.md5(f.read()).hexdigest()[:16]
                self._exif_log(f"🔑 文件MD5: {md5}...")
            except Exception:
                pass

            self._exif_log("─" * 40)

            exif = img.getexif()
            if not exif:
                self._exif_log("⚠️ 无 EXIF 数据 — 可能是截图、转发图或已被压缩")
                self._exif_log("   此图片的创建时间可能不准确（会用文件修改时间替代）")
                self._exif_log("   可使用「批量 EXIF 日期修正」工具手动写入日期")
                return

            # 常用 EXIF 标签的中文名映射
            exif_names_cn = {
                306: "拍摄日期(DateTime)",
                36867: "原始拍摄时间(DateTimeOriginal)",
                36868: "数字化时间(DateTimeDigitized)",
                271: "设备厂商(Make)",
                272: "设备型号(Model)",
                33434: "曝光时间(ExposureTime)",
                33437: "光圈值(FNumber)",
                37510: "用户评论(UserComment)",
                41988: "焦距(FocalLength)",
                37386: "镜头焦距(FocalLength35mm)",
                41990: "对比度(Contrast)",
                37385: "闪光灯(Flash)",
                41986: "曝光模式(ExposureMode)",
                41987: "白平衡(WhiteBalance)",
                37384: "测光模式(LightSource)",
            }

            self._exif_log("📋 EXIF 元数据:")
            important_tags = [36867, 306, 271, 272, 33434, 33437, 41988, 37385, 37386]
            other_tags = [t for t in exif.keys() if t not in important_tags]

            for tag_id in important_tags:
                if tag_id in exif and exif.get(tag_id):
                    tag_name = exif_names_cn.get(tag_id, TAGS.get(tag_id, f"Tag_{tag_id}"))
                    val_str = str(exif.get(tag_id))
                    if len(val_str) > 80:
                        val_str = val_str[:77] + "..."
                    self._exif_log(f"   {tag_name}: {val_str}")

            if other_tags:
                self._exif_log("─" * 40)
                self._exif_log("📋 其他元数据:")
                for tag_id in other_tags:
                    tag_name = exif_names_cn.get(tag_id, TAGS.get(tag_id, f"Tag_{tag_id}"))
                    val_str = str(exif.get(tag_id))
                    if len(val_str) > 80:
                        val_str = val_str[:77] + "..."
                    self._exif_log(f"   {tag_name}: {val_str}")

        except Exception as e:
            self._exif_log(f"❌ 读取失败: {e}")

    def _exif_log(self, msg):
        self.exif_result.insert("end", msg + "\n")
        self.exif_result.see("end")

    # ── 日期修正 ──
    def _build_date_fix(self):
        card = ctk.CTkFrame(self.tool_body, **card_frame_style())
        card.pack(fill="both", expand=True)

        ctk.CTkLabel(card, text="批量 EXIF 日期修正", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(20, 8))
        ctk.CTkLabel(card, text="为截图、转发图等无 EXIF 的图片批量写入拍摄日期。修正后事件分类可以正确按时间分组。",
                     font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=24, pady=(0, 16))

        # 文件夹选择
        folder_row = ctk.CTkFrame(card, fg_color="transparent")
        folder_row.pack(fill="x", padx=24, pady=(0, 12))
        self.df_folder_var = ctk.StringVar()
        ctk.CTkEntry(folder_row, textvariable=self.df_folder_var,
                     font=font_safe(13), height=38,
                     fg_color=COLORS["bg"], border_color=COLORS["border"],
                     placeholder_text="选择图片文件夹...").pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(folder_row, text="📂 选择", width=80,
                      command=self._df_pick_folder,
                      **secondary_button_style()).pack(side="left")

        # 日期输入
        date_row = ctk.CTkFrame(card, fg_color="transparent")
        date_row.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkLabel(date_row, text="拍摄日期", font=font_safe(13, "bold"),
                     text_color=COLORS["text"]).pack(side="left", padx=(0, 8))
        self.df_year_var = ctk.StringVar(value="2025")
        self.df_month_var = ctk.StringVar(value="01")
        self.df_day_var = ctk.StringVar(value="01")
        ctk.CTkEntry(date_row, textvariable=self.df_year_var, width=60, height=34,
                     font=font_safe(13), fg_color=COLORS["bg"],
                     border_color=COLORS["border"]).pack(side="left", padx=(0, 4))
        ctk.CTkLabel(date_row, text="年", font=font_safe(12),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(date_row, textvariable=self.df_month_var, width=40, height=34,
                     font=font_safe(13), fg_color=COLORS["bg"],
                     border_color=COLORS["border"]).pack(side="left", padx=(0, 4))
        ctk.CTkLabel(date_row, text="月", font=font_safe(12),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(date_row, textvariable=self.df_day_var, width=40, height=34,
                     font=font_safe(13), fg_color=COLORS["bg"],
                     border_color=COLORS["border"]).pack(side="left", padx=(0, 4))
        ctk.CTkLabel(date_row, text="日", font=font_safe(12),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 16))

        # 模式选择
        self.df_mode_var = ctk.StringVar(value="no_exif")
        ctk.CTkLabel(card, text="修正范围", font=font_safe(13, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(0, 4))
        mode_row = ctk.CTkFrame(card, fg_color="transparent")
        mode_row.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkRadioButton(mode_row, text="仅修正无 EXIF 的图片（推荐，安全）",
                           variable=self.df_mode_var, value="no_exif",
                           font=font_safe(13), text_color=COLORS["text"],
                           fg_color=COLORS["primary"]).pack(anchor="w")
        ctk.CTkRadioButton(mode_row, text="修正所有图片（覆盖已有日期）",
                           variable=self.df_mode_var, value="all",
                           font=font_safe(13), text_color=COLORS["text"],
                           fg_color=COLORS["danger"]).pack(anchor="w")

        # 按钮
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 12))
        self.df_run_btn = ctk.CTkButton(btn_row, text="📅 批量修正日期", **primary_button_style())
        self.df_run_btn.pack(side="left")
        self.df_run_btn.configure(command=self._df_run)

        # 日志
        self.df_log = scrolledtext.ScrolledText(card, height=160, wrap="word",
                                                font=("SF Mono", 11) if os.name != "nt" else ("Consolas", 11),
                                                bg="#1e1b18", fg="#e2ddd5",
                                                relief="flat", borderwidth=0)
        self.df_log.pack(fill="both", expand=True, padx=24, pady=(0, 20))

    def _df_pick_folder(self):
        d = filedialog.askdirectory(title="选择图片文件夹")
        if d:
            self.df_folder_var.set(d)

    def _df_run(self):
        folder = self.df_folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("提示", "请先选择有效的图片文件夹")
            return

        year = self.df_year_var.get().strip()
        month = self.df_month_var.get().strip().zfill(2)
        day = self.df_day_var.get().strip().zfill(2)

        try:
            int(year)
            int(month)
            int(day)
        except ValueError:
            messagebox.showwarning("日期错误", "请输入有效的数字日期")
            return

        date_str = f"{year}:{month}:{day} 12:00:00"
        mode = self.df_mode_var.get()

        self.df_run_btn.configure(state="disabled", text="⏳ 修正中...")
        self.df_log.delete("1.0", "end")
        self._df_log(f"📂 文件夹: {folder}")
        self._df_log(f"📅 设定日期: {year}年{month}月{day}日")
        self._df_log(f"🔧 模式: {'仅无EXIF' if mode == 'no_exif' else '全部覆盖'}")
        self._df_log("─" * 40)

        def _run():
            from core.image_utils import _safe_open_image
            from core.event_classifier import is_screenshot
            try:
                from PIL import Image
            except ImportError:
                self._df_log("❌ 需要 Pillow 库")
                return

            files = []
            for root, _, fnames in os.walk(folder):
                for fn in fnames:
                    p = os.path.join(root, fn)
                    if is_image_file(p):
                        files.append(p)

            self._df_log(f"📸 找到 {len(files)} 张图片")

            # 筛选需要修正的
            to_fix = []
            skipped = 0
            for p in files:
                if mode == "all":
                    to_fix.append(p)
                else:
                    # 检查是否有 EXIF 日期
                    has_date = False
                    try:
                        img, _ = _safe_open_image(p)
                        if img:
                            exif = img.getexif()
                            if exif:
                                for tag in (36867, 36868, 306):
                                    if exif.get(tag):
                                        has_date = True
                                        break
                    except Exception:
                        pass
                    if not has_date:
                        to_fix.append(p)
                    else:
                        skipped += 1

            self._df_log(f"🔧 需要修正: {len(to_fix)} 张（跳过 {skipped} 张已有日期）")

            ok = ng = 0
            for i, path in enumerate(to_fix):
                try:
                    img, fmt = _safe_open_image(path)
                    if img is None:
                        raise ValueError("无法打开图片")

                    # 构建 EXIF
                    exif = img.getexif()
                    exif[36867] = date_str   # DateTimeOriginal
                    exif[36868] = date_str   # DateTimeDigitized
                    exif[306] = date_str     # DateTime

                    # 保存（覆盖原文件）
                    ext = os.path.splitext(path)[1].lower()
                    save_fmt = {
                        ".jpg": "JPEG", ".jpeg": "JPEG",
                        ".png": "PNG", ".webp": "WebP",
                        ".heic": "HEIF", ".heif": "HEIF",
                    }.get(ext, "JPEG")

                    save_kwargs = {"exif": exif.tobytes() if hasattr(exif, 'tobytes') else b""}
                    if save_fmt == "JPEG" and img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")

                    img.save(path, save_fmt, **save_kwargs)
                    ok += 1

                    if (i + 1) % 10 == 0:
                        self._df_log(f"   {i+1}/{len(to_fix)} 已修正")
                except Exception as e:
                    ng += 1
                    self._df_log(f"   ❌ {os.path.basename(path)}: {e}")

            self._df_log("─" * 40)
            self._df_log(f"✅ 成功: {ok}  ❌ 失败: {ng}")
            self._df_log(f"💡 修正后的图片在事件分类时会按 {year}-{month}-{day} 分组")

            def _done():
                self.df_run_btn.configure(state="normal", text="📅 批量修正日期")
            self.after(0, _done)

        threading.Thread(target=_run, daemon=True).start()

    def _df_log(self, msg):
        self.df_log.insert("end", msg + "\n")
        self.df_log.see("end")
