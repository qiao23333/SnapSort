#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ollama 安装向导 — 首次使用或 AI 离线时弹出，引导用户下载安装 Ollama + 拉取模型。
"""
import os
import sys
import platform
import threading
import webbrowser
import json

import customtkinter as ctk
from tkinter import messagebox

from ui.theme import COLORS, font_safe, primary_button_style, secondary_button_style, card_frame_style
from ui.widgets import safe_after


# 推荐模型列表（名称、大小、说明）
RECOMMENDED_MODELS = [
    ("moondream", "~1.8GB", "轻量首选 · 速度快 · 适合快速分类"),
    ("llava:7b", "~4.7GB", "平衡之选 · 识别准 · 推荐日常使用"),
    ("llava:13b", "~13GB", "高精度 · 需 16GB+ 内存 · 适合精细场景"),
    ("minicpm-v:8b", "~5.5GB", "国产模型 · 中文友好 · 推荐国内用户"),
]

OLLAMA_DOWNLOAD_URLS = {
    "Darwin": "https://ollama.com/download/Ollama-darwin.zip",
    "Windows": "https://ollama.com/download/OllamaSetup.exe",
    "Linux": "https://ollama.com/download/Ollama-linux.tgz",
}


class OllamaWizard(ctk.CTkToplevel):
    """Ollama 安装向导弹窗"""

    def __init__(self, parent, app, on_success=None):
        super().__init__(parent)
        self.app = app
        self.on_success = on_success
        self.platform = platform.system()

        self.title("Ollama 安装向导")
        self.geometry("520x640")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.grab_set()

        # 居中显示
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 520) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 640) // 2
        self.geometry(f"+{x}+{y}")

        self._build_ui()
        self._check_status()

    def _build_ui(self):
        # 头部
        header = ctk.CTkFrame(self, fg_color=COLORS["primary"], corner_radius=0, height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="🤖 Ollama 安装向导",
                     font=font_safe(20, "bold"), text_color="white").pack(pady=(20, 0))
        ctk.CTkLabel(header, text="本地 AI 引擎 — 隐私安全 · 完全离线",
                     font=font_safe(12), text_color="#a0a0a0").pack()

        # 状态栏
        self.status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.status_frame.pack(fill="x", padx=24, pady=(16, 8))
        self.status_label = ctk.CTkLabel(self.status_frame, text="⏳ 正在检测…",
                                         font=font_safe(14, "bold"),
                                         text_color=COLORS["text"])
        self.status_label.pack(side="left")
        self.recheck_btn = ctk.CTkButton(self.status_frame, text="🔄 重新检测",
                                         command=self._check_status, width=100, height=28,
                                         font=font_safe(11),
                                         fg_color=COLORS["card"], hover_color=COLORS["hover"],
                                         text_color=COLORS["text"])
        self.recheck_btn.pack(side="right")

        # 可滚动内容区
        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # 底部关闭按钮
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(0, 16))
        ctk.CTkButton(footer, text="完成", command=self.destroy,
                      **primary_button_style()).pack(side="right")

    def _check_status(self):
        """检测 Ollama 状态，更新 UI"""
        self.status_label.configure(text="⏳ 正在检测…", text_color=COLORS["text_secondary"])
        self.recheck_btn.configure(state="disabled")

        def _check():
            from core.sorter_engine import check_ollama, fetch_ollama_models
            online = check_ollama()
            models = []
            if online:
                models = fetch_ollama_models()

            def _apply():
                self.recheck_btn.configure(state="normal")
                for w in self.content.winfo_children():
                    w.destroy()

                if online:
                    self.status_label.configure(text="✅ Ollama 已就绪", text_color=COLORS["success"])
                    self._show_model_step(models)
                else:
                    self.status_label.configure(text="❌ Ollama 未运行", text_color=COLORS["danger"])
                    self._show_install_steps()

            safe_after(self, _apply)

        threading.Thread(target=_check, daemon=True).start()

    def _show_install_steps(self):
        """显示安装步骤"""
        p = self.content

        # Step 1: 下载
        card1 = ctk.CTkFrame(p, **card_frame_style())
        card1.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card1, text="Step 1 · 下载 Ollama", font=font_safe(15, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=16, pady=(12, 4))

        plat_label = "macOS" if self.platform == "Darwin" else \
                     "Windows" if self.platform == "Windows" else "Linux"
        ctk.CTkLabel(card1, text=f"检测到系统：{plat_label}",
                     font=font_safe(12), text_color=COLORS["text_secondary"]).pack(anchor="w", padx=16)

        dl_url = OLLAMA_DOWNLOAD_URLS.get(self.platform, "https://ollama.com/download")
        dl_btn = ctk.CTkButton(card1, text="⬇ 下载 Ollama 安装包",
                               command=lambda: webbrowser.open(dl_url),
                               font=font_safe(13, "bold"), height=38,
                               fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                               text_color="white", corner_radius=10)
        dl_btn.pack(fill="x", padx=16, pady=(8, 12))

        # Step 2: 安装
        card2 = ctk.CTkFrame(p, **card_frame_style())
        card2.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card2, text="Step 2 · 安装", font=font_safe(15, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=16, pady=(12, 4))

        if self.platform == "Darwin":
            steps = "1. 双击下载的 .zip 解压\n2. 将 Ollama 拖到「应用程序」文件夹\n3. 双击启动 Ollama（菜单栏出现羊驼图标）"
        elif self.platform == "Windows":
            steps = "1. 双击下载的 OllamaSetup.exe\n2. 按提示完成安装（一路 Next）\n3. 安装完成后 Ollama 自动启动"
        else:
            steps = "1. 解压下载的 .tgz 文件\n2. 运行：sudo ./ollama serve\n3. 保持终端窗口打开"

        ctk.CTkLabel(card2, text=steps, font=font_safe(12),
                     text_color=COLORS["text_secondary"], justify="left").pack(anchor="w", padx=16, pady=(0, 12))

        # Step 3: 确认运行
        card3 = ctk.CTkFrame(p, **card_frame_style())
        card3.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card3, text="Step 3 · 确认运行", font=font_safe(15, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(card3, text="安装完成后，Ollama 会自动在后台运行。\n点击右上角「🔄 重新检测」确认状态变为 ✅。",
                     font=font_safe(12), text_color=COLORS["text_secondary"],
                     justify="left").pack(anchor="w", padx=16, pady=(0, 12))

        # 提示
        ctk.CTkLabel(p, text="💡 安装 Ollama 后再来这里下载 AI 模型",
                     font=font_safe(11), text_color=COLORS["text_secondary"]).pack()

    def _show_model_step(self, installed_models):
        """Ollama 已就绪，显示模型下载"""
        p = self.content

        has_vision = any("llava" in m or "moondream" in m or "bakllava" in m or "minicpm" in m
                        for m in installed_models)

        if has_vision:
            ctk.CTkLabel(p, text="✅ 已安装视觉模型，可以直接开始使用了！",
                         font=font_safe(14, "bold"), text_color=COLORS["success"],
                         wraplength=440).pack(pady=(8, 12))
        else:
            ctk.CTkLabel(p, text="⚠️ Ollama 已运行，但还没有视觉模型\n请下载下方推荐模型：",
                         font=font_safe(13, "bold"), text_color=COLORS["warning"],
                         wraplength=440, justify="left").pack(anchor="w", pady=(8, 12))

        # 模型下载卡片
        for name, size, desc in RECOMMENDED_MODELS:
            card = ctk.CTkFrame(p, **card_frame_style())
            card.pack(fill="x", pady=(0, 8))

            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(10, 4))

            ctk.CTkLabel(row, text=name, font=font_safe(14, "bold"),
                         text_color=COLORS["text"]).pack(side="left")
            ctk.CTkLabel(row, text=size, font=font_safe(11),
                         text_color=COLORS["text_secondary"]).pack(side="left", padx=(8, 0))

            already = name in installed_models or any(name in m for m in installed_models)
            if already:
                ctk.CTkLabel(row, text="✅ 已安装", font=font_safe(11, "bold"),
                             text_color=COLORS["success"]).pack(side="right")
            else:
                btn = ctk.CTkButton(row, text="下载", width=60, height=28,
                                    command=lambda n=name: self._pull_model(n),
                                    font=font_safe(11, "bold"),
                                    fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"],
                                    text_color="white", corner_radius=8)
                btn.pack(side="right")

            ctk.CTkLabel(card, text=desc, font=font_safe(11),
                         text_color=COLORS["text_secondary"]).pack(anchor="w", padx=16, pady=(0, 10))

        # 进度区
        self.pull_status = ctk.StringVar(value="")
        self.pull_label = ctk.CTkLabel(p, textvariable=self.pull_status,
                                       font=font_safe(11), text_color=COLORS["text_secondary"])
        self.pull_label.pack(anchor="w", pady=(4, 0))
        self.pull_progress = ctk.CTkProgressBar(p, progress_color=COLORS["primary"],
                                                fg_color=COLORS["border_light"], height=4)
        self.pull_progress.set(0)
        self.pull_progress.pack(fill="x", pady=(4, 0))

        if has_vision and self.on_success:
            ctk.CTkButton(p, text="🎉 开始使用 SnapSort", command=self._on_complete,
                          **primary_button_style()).pack(pady=(12, 0))

    def _pull_model(self, model_name):
        """通过 Ollama API 拉取模型"""
        self.pull_status.set(f"⏳ 正在下载 {model_name}…")
        self.pull_progress.set(0)

        def _pull():
            try:
                import requests
                from core.sorter_engine import DEFAULT_URL
                with requests.post(f"{DEFAULT_URL}/api/pull",
                                   json={"name": model_name, "stream": True},
                                   stream=True, timeout=3600) as r:
                    if r.status_code != 200:
                        safe_after(self, lambda: self.pull_status.set(f"❌ 下载失败：HTTP {r.status_code}"))
                        return

                    total = None
                    completed = 0
                    for line in r.iter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line.decode("utf-8"))
                            status = data.get("status", "")
                            if "total" in data and "completed" in data:
                                total = data.get("total") or total
                                completed = data.get("completed", completed)
                                if total:
                                    pct = completed / total
                                    safe_after(self, lambda p=pct: self.pull_progress.set(p))
                                    safe_after(self, lambda s=status, c=completed, t=total:
                                               self.pull_status.set(f"{s} ({c}/{t})"))
                            elif status:
                                safe_after(self, lambda s=status: self.pull_status.set(s))
                        except Exception:
                            pass

                safe_after(self, lambda: (
                    self.pull_progress.set(1),
                    self.pull_status.set(f"✅ {model_name} 下载完成！点击「重新检测」刷新")
                ))
                safe_after(self, self._check_status)
            except Exception as e:
                safe_after(self, lambda: self.pull_status.set(f"❌ 下载失败：{e}"))

        threading.Thread(target=_pull, daemon=True).start()

    def _on_complete(self):
        if self.on_success:
            self.on_success()
        self.destroy()
