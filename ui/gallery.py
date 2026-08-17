#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""素材库页面：按分类浏览缩略图 — 后台生成、磁盘缓存、分批渲染、点击预览"""
import os
import hashlib
import threading
import queue
from pathlib import Path
import customtkinter as ctk
from PIL import Image, ImageTk
from concurrent.futures import ThreadPoolExecutor

from ui.theme import COLORS, font_safe, secondary_button_style, card_frame_style
from core.image_utils import make_thumbnail, is_image_file


def _thumb_cache_dir():
    """获取缩略图磁盘缓存目录"""
    cache = Path(__file__).parent.parent / "data" / "thumbnails"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def _get_cached_thumbnail(image_path, size=(130, 130)):
    """从磁盘缓存获取缩略图，不存在则生成并缓存"""
    try:
        # 用文件路径+修改时间生成缓存键
        stat = os.stat(image_path)
        cache_key = hashlib.md5(
            f"{image_path}_{stat.st_mtime}_{stat.st_size}_{size[0]}".encode()
        ).hexdigest()
        cache_file = _thumb_cache_dir() / f"{cache_key}.png"

        if cache_file.exists():
            return Image.open(cache_file)

        # 生成新缩略图
        thumb = make_thumbnail(image_path, size=size)
        if thumb:
            thumb.save(cache_file, "PNG")
        return thumb
    except Exception:
        return make_thumbnail(image_path, size=size)


class GalleryPage(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.configure(fg_color=COLORS["bg"])
        self.thumbnails = []
        self._cancel_flag = threading.Event()
        self._load_thread = None
        self._preview_window = None
        self._built = False
        self._thumb_executor = ThreadPoolExecutor(max_workers=4)
        self._thumb_futures = []
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="素材库", font=font_safe(28, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=32, pady=(28, 4))
        ctk.CTkLabel(self, text="浏览已分类的素材照片，支持按分类筛选",
                     font=font_safe(14, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=32, pady=(0, 20))

        # 筛选栏
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=32, pady=(0, 12))

        ctk.CTkLabel(filter_frame, text="分类筛选", font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(side="left")

        self.category_var = ctk.StringVar(value="全部")
        categories = ["全部"] + list(self.app.config_manager.get("categories", {}).keys()) + ["人物库", "地点库", "其他", "待复核"]
        self.category_menu = ctk.CTkOptionMenu(filter_frame, variable=self.category_var,
                                               values=categories, width=160, height=34,
                                               font=font_safe(13, "normal"),
                                               dropdown_font=font_safe(13, "normal"),
                                               command=self._on_category_change)
        self.category_menu.pack(side="left", padx=(8, 16))

        ctk.CTkButton(filter_frame, text="🔄 刷新", command=self.refresh,
                      **secondary_button_style()).pack(side="left")
        ctk.CTkButton(filter_frame, text="🗑 清缓存", command=self.clear_cache,
                      **secondary_button_style()).pack(side="left", padx=(8, 0))

        self.info_label = ctk.CTkLabel(filter_frame, text="",
                                       font=font_safe(12, "normal"),
                                       text_color=COLORS["text_secondary"])
        self.info_label.pack(side="right")

        # 图片网格区
        self.gallery_card = ctk.CTkFrame(self, **card_frame_style())
        self.gallery_card.pack(fill="both", expand=True, padx=32, pady=(0, 32))

        self.gallery_scroll = ctk.CTkScrollableFrame(self.gallery_card, fg_color="transparent")
        self.gallery_scroll.pack(fill="both", expand=True, padx=16, pady=16)

        self._built = True

    def _on_category_change(self, choice):
        self.refresh()

    def clear_cache(self):
        """清空缩略图磁盘缓存"""
        cache = _thumb_cache_dir()
        count = 0
        for f in cache.glob("*.png"):
            try:
                f.unlink()
                count += 1
            except Exception:
                pass
        from tkinter import messagebox
        messagebox.showinfo("缓存已清除", f"已清除 {count} 个缩略图缓存文件")
        self.refresh()

    def refresh(self):
        if not self._built:
            return

        # 取消旧任务
        self._cancel_flag.set()
        if self._load_thread and self._load_thread.is_alive():
            self._load_thread.join(timeout=0.5)
        for f in self._thumb_futures:
            f.cancel()
        self._thumb_futures.clear()
        self._cancel_flag.clear()

        for widget in self.gallery_scroll.winfo_children():
            widget.destroy()
        self.thumbnails.clear()

        output_dir = self.app.output_var.get()
        if not os.path.isdir(output_dir):
            ctk.CTkLabel(self.gallery_scroll, text="输出文件夹不存在，请先运行自动分类",
                         font=font_safe(13, "normal"),
                         text_color=COLORS["text_secondary"]).pack(pady=40)
            self.info_label.configure(text="0 张")
            return

        self.info_label.configure(text="正在扫描...")
        self._load_thread = threading.Thread(target=self._collect_images, args=(output_dir,), daemon=True)
        self._load_thread.start()

    def _collect_images(self, output_dir):
        selected_cat = self.category_var.get()
        images = []

        if selected_cat == "全部":
            for root, _, files in os.walk(output_dir):
                for f in files:
                    path = os.path.join(root, f)
                    if is_image_file(path):
                        images.append(path)
        else:
            cat_dir = os.path.join(output_dir, selected_cat)
            if os.path.isdir(cat_dir):
                # 人物库/地点库 有子目录（按人物/地点分），需要递归扫描
                if selected_cat in ("人物库", "地点库"):
                    for root, _, files in os.walk(cat_dir):
                        for f in files:
                            path = os.path.join(root, f)
                            if is_image_file(path):
                                images.append(path)
                else:
                    for f in os.listdir(cat_dir):
                        path = os.path.join(cat_dir, f)
                        if is_image_file(path):
                            images.append(path)

        self._safe_after(lambda: self._start_render(images))

    def _safe_after(self, callback):
        """安全地在主线程执行回调（窗口已关闭则不执行）"""
        try:
            if self.winfo_exists():
                self.after(0, callback)
        except Exception:
            pass

    def _start_render(self, images):
        if not images:
            ctk.CTkLabel(self.gallery_scroll, text=f"「{self.category_var.get()}」暂无图片",
                         font=font_safe(13, "normal"),
                         text_color=COLORS["text_secondary"]).pack(pady=40)
            self.info_label.configure(text="0 张")
            return

        self.info_label.configure(text=f"共 {len(images)} 张，加载中...")
        self._grid = ctk.CTkFrame(self.gallery_scroll, fg_color="transparent")
        self._grid.pack(fill="x")

        for c in range(4):
            self._grid.grid_columnconfigure(c, weight=1)

        self._pending_images = images[:300]
        self._rendered_count = 0
        self._render_batch()

    def _render_batch(self, batch_size=12):
        if self._cancel_flag.is_set():
            return

        batch = self._pending_images[:batch_size]
        self._pending_images = self._pending_images[batch_size:]

        for path in batch:
            if self._cancel_flag.is_set():
                return
            self._create_thumbnail_widget(self._grid, path, self._rendered_count)
            self._rendered_count += 1

        remaining = len(self._pending_images)
        self.info_label.configure(text=f"共 {self._rendered_count + remaining} 张")

        if remaining > 0:
            self.app.root.after(30, self._render_batch)
        else:
            self.info_label.configure(text=f"共 {self._rendered_count} 张")

    def _create_thumbnail_widget(self, parent, path, index):
        row, col = divmod(index, 4)

        frame = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=8,
                             border_color=COLORS["border_light"], border_width=1)
        frame.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        frame.grid_propagate(False)
        frame.configure(width=150, height=170)

        # 先生成占位图，再在后台加载真实缩略图
        label = ctk.CTkLabel(frame, text="加载中...", font=font_safe(10, "normal"),
                             text_color=COLORS["text_secondary"])
        label.pack(pady=(60, 4))

        name = Path(path).name
        display_name = name if len(name) <= 16 else name[:13] + "..."
        name_label = ctk.CTkLabel(frame, text=display_name, font=font_safe(10, "normal"),
                                  text_color=COLORS["text_secondary"])
        name_label.pack(pady=(0, 8))

        # 绑定点击预览
        for w in (frame, label, name_label):
            w.bind("<Button-1>", lambda e, p=path: self._open_preview(p))

        # 后台加载缩略图（带磁盘缓存，线程池限流）
        def _load_thumb(path=path, frame=frame, name_label=name_label):
            if self._cancel_flag.is_set():
                return
            thumb = _get_cached_thumbnail(path, size=(130, 130))
            if thumb:
                try:
                    photo = ImageTk.PhotoImage(thumb)
                except Exception:
                    return
                self._safe_after(lambda f=frame, p=photo, n=name_label, pa=path:
                                 self._set_thumb(f, p, n, pa))

        future = self._thumb_executor.submit(_load_thumb)
        self._thumb_futures.append(future)

    def _set_thumb(self, frame, photo, name_label, path):
        if self._cancel_flag.is_set():
            return
        for w in frame.winfo_children():
            w.destroy()
        img_label = ctk.CTkLabel(frame, image=photo, text="")
        img_label.pack(pady=(12, 4))
        img_label.bind("<Button-1>", lambda e, p=path: self._open_preview(p))
        name_label = ctk.CTkLabel(frame, text=Path(path).name if len(Path(path).name) <= 16 else Path(path).name[:13] + "...",
                                  font=font_safe(10, "normal"),
                                  text_color=COLORS["text_secondary"])
        name_label.pack(pady=(0, 8))
        name_label.bind("<Button-1>", lambda e, p=path: self._open_preview(p))

    def _open_preview(self, path):
        if self._preview_window and self._preview_window.winfo_exists():
            self._preview_window.destroy()
        self._preview_window = ctk.CTkToplevel(self)
        self._preview_window.title(f"预览 - {Path(path).name}")
        self._preview_window.geometry("900x700")
        self._preview_window.transient(self)

        try:
            from core.image_utils import _safe_open_image
            img, _ = _safe_open_image(path)
            img.thumbnail((860, 620), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.thumbnails.append(photo)
            ctk.CTkLabel(self._preview_window, image=photo, text="").pack(pady=20)
        except Exception as e:
            ctk.CTkLabel(self._preview_window, text=f"无法打开图片：\n{e}",
                         font=font_safe(13, "normal")).pack(pady=40)

        ctk.CTkLabel(self._preview_window, text=path, font=font_safe(11, "normal"),
                     text_color=COLORS["text_secondary"]).pack(pady=(0, 20))
