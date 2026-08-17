#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SnapSort 3.0 - 本地 AI 图片素材分类器
Apple 风格桌面应用。侧栏导航：仪表盘、自动分类（含内容分类/事件整理双模式）、素材预览、工具、历史、设置。
v3.0: 优化 — 双模式共享模型选择器、事件流程加确认步骤
"""
import os
import sys
import platform
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox

# 将项目根目录加入 sys.path
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.config import ConfigManager
from ui.theme import (COLORS, font_safe, apply_root_theme,
                      sidebar_button_style, sidebar_button_active_style,
                      secondary_button_style)
from ui.dashboard import DashboardPage
from ui.auto_sort import AutoSortPage
from ui.gallery import GalleryPage
from ui.toolbox import ToolboxPage
from ui.history_view import HistoryPage
from ui.settings import SettingsPage


ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("dark-blue")


def get_default_input_dir():
    """获取默认输入目录：优先使用上次路径，否则为桌面"""
    desktop = Path.home() / "Desktop"
    return str(desktop / "素材内容") if (desktop / "素材内容").exists() else str(desktop)


def get_default_output_dir():
    """获取默认输出目录"""
    desktop = Path.home() / "Desktop"
    return str(desktop / "素材内容_已分类")


class SnapSortApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SnapSort 3.0")
        self.root.geometry("1280x860")
        self.root.minsize(1080, 720)

        self.config_manager = ConfigManager()

        # 全局变量（路径）：从配置读取，无记录则使用默认桌面路径
        default_input = self.config_manager.get("last_input", get_default_input_dir())
        default_output = self.config_manager.get("last_output", get_default_output_dir())
        self.input_var = ctk.StringVar(value=default_input)
        self.output_var = ctk.StringVar(value=default_output)

        self.current_page = None
        self.pages = {}
        self.nav_buttons = {}

        self._center_window()
        self._build_ui()
        self.show_page("dashboard")

    def _center_window(self):
        self.root.update_idletasks()
        w, h = 1280, 860
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        # 确保窗口在最前并正常显示（macOS 上有时需要主动提升）
        self.root.deiconify()
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))

    def _build_ui(self):
        apply_root_theme(self.root)

        # 主容器
        self.container = ctk.CTkFrame(self.root, fg_color=COLORS["bg"], corner_radius=0)
        self.container.pack(fill="both", expand=True)

        # 侧边栏
        self.sidebar = ctk.CTkFrame(self.container, width=240, fg_color=COLORS["sidebar"],
                                     corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo 区
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=80)
        logo_frame.pack(fill="x", padx=20, pady=(24, 16))
        logo_frame.pack_propagate(False)
        ctk.CTkLabel(logo_frame, text="SnapSort", font=font_safe(24, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w")
        # 副标题 — 点击 5 次打开开发者面板（彩蛋）
        self._dev_click_count = 0
        self._dev_click_timer = None
        dev_label = ctk.CTkLabel(logo_frame, text="本地 AI 乔心制作", font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"], cursor="hand2")
        dev_label.pack(anchor="w")
        dev_label.bind("<Button-1>", lambda e: self._on_dev_label_click())

        # 导航按钮（macOS 风格侧边栏）
        nav_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_container.pack(fill="x", padx=12, pady=(8, 0))

        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "📊", "仪表盘"),
            ("auto_sort", "🚀", "自动分类"),
            ("gallery", "🖼", "素材预览"),
            ("toolbox", "🧰", "工具"),
            ("history", "📜", "历史记录"),
            ("settings", "⚙️", "设置"),
        ]

        for page_key, icon, label in nav_items:
            btn = ctk.CTkButton(nav_container, text=f" {icon}  {label}",
                                command=lambda k=page_key: self.show_page(k),
                                **sidebar_button_style())
            btn.pack(fill="x", pady=(0, 6))
            self.nav_buttons[page_key] = btn

        # 底部状态
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=20, pady=20)
        ctk.CTkLabel(footer, text="本地 AI · 隐私安全",
                     font=font_safe(11, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w")
        ctk.CTkLabel(footer, text="v3.0",
                     font=font_safe(11, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w")

        # 内容区
        self.content_frame = ctk.CTkFrame(self.container, fg_color=COLORS["bg"], corner_radius=0)
        self.content_frame.pack(side="left", fill="both", expand=True)

        # 初始化各页面
        self.pages["dashboard"] = DashboardPage(self.content_frame, self, fg_color=COLORS["bg"])
        self.pages["auto_sort"] = AutoSortPage(self.content_frame, self, fg_color=COLORS["bg"])
        self.pages["gallery"] = GalleryPage(self.content_frame, self, fg_color=COLORS["bg"])
        self.pages["toolbox"] = ToolboxPage(self.content_frame, self, fg_color=COLORS["bg"])
        self.pages["history"] = HistoryPage(self.content_frame, self, fg_color=COLORS["bg"])
        self.pages["settings"] = SettingsPage(self.content_frame, self, fg_color=COLORS["bg"])

        for page in self.pages.values():
            page.pack_forget()

    def show_page(self, page_key):
        if page_key not in self.pages:
            return

        if self.current_page:
            self.pages[self.current_page].pack_forget()
            self.nav_buttons[self.current_page].configure(**sidebar_button_style())

        self.pages[page_key].pack(fill="both", expand=True)
        self.current_page = page_key

        # 高亮当前导航
        self.nav_buttons[page_key].configure(**sidebar_button_active_style())

        # 刷新页面数据
        if hasattr(self.pages[page_key], "refresh"):
            self.pages[page_key].refresh()

    def open_output_folder(self):
        output_dir = self.output_var.get().strip()
        if os.path.isdir(output_dir):
            if platform.system() == "Windows":
                os.startfile(output_dir)
            elif platform.system() == "Darwin":
                os.system(f'open "{output_dir}"')
            else:
                os.system(f'xdg-open "{output_dir}"')
        else:
            messagebox.showwarning("文件夹不存在", f"输出文件夹尚未创建：\n{output_dir}")

    def save_path_config(self):
        """保存当前输入/输出路径到配置"""
        self.config_manager.set("last_input", self.input_var.get().strip())
        self.config_manager.set("last_output", self.output_var.get().strip())
        self.config_manager.save()

    def _on_dev_label_click(self):
        """副标题点击 5 次打开开发者面板"""
        self._dev_click_count += 1
        if self._dev_click_timer:
            self.after_cancel(self._dev_click_timer)
        self._dev_click_timer = self.after(2000, lambda: setattr(self, "_dev_click_count", 0))
        if self._dev_click_count >= 5:
            self._dev_click_count = 0
            self._show_dev_panel()

    def _show_dev_panel(self):
        """开发者面板：项目结构、修改指引、跨平台说明"""
        import platform as pf
        win = ctk.CTkToplevel(self.root)
        win.title("SnapSort 开发者面板")
        win.geometry("720x600")
        win.transient(self.root)

        frm = ctk.CTkScrollableFrame(win, fg_color=COLORS["bg"])
        frm.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(frm, text="🔧 开发者面板", font=font_safe(20, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", pady=(0, 8))

        sections = [
            ("项目结构", [
                "app.py              — 主入口，侧边栏 + 页面路由",
                "ui/theme.py         — 配色系统、字体、通用样式（改颜色改这里）",
                "ui/auto_sort.py     — 自动分类页（事件模式 + 内容模式）",
                "ui/toolbox.py       — 工具箱页（位图转矢量、以文搜图等）",
                "ui/settings.py      — 设置页（分类配置、人物/地点、规则引擎）",
                "ui/dashboard.py     — 仪表盘页",
                "ui/gallery.py       — 图库页",
                "core/sorter_engine.py  — AI 分类核心引擎（prompt、分类、重试）",
                "core/event_classifier.py — 事件聚类（日期分组、合并、命名）",
                "core/config.py      — 配置管理（JSON 读写）",
                "core/rule_engine.py  — 规则引擎（后处理自动化）",
                "core/image_utils.py  — 图片处理（缩略图、HEIC、矢量转换）",
                "core/model_info.py   — 模型类型识别（视觉/文本）",
                "core/reference_manager.py — 人物/地点参考照片管理",
            ]),
            ("配色修改", [
                "打开 ui/theme.py → 修改 COLORS 字典",
                "primary = 主按钮颜色（默认纯黑 #1D1D1F）",
                "accent = 琥珀色，仅用于 AI 状态/活跃标签",
                "selected = 选中态背景色",
                "改完即时生效，无需编译",
            ]),
            ("添加新工具", [
                "1. 在 ui/toolbox.py 的 _build_tools() 中添加新工具卡片",
                "2. 创建对应的 _run_xxx() 方法",
                "3. 如需 AI 能力，在 core/sorter_engine.py 中添加 API 调用",
                "4. 在 DEVBOOK.md 第 12 章查看完整扩展指南",
            ]),
            ("AI Prompt 修改", [
                "打开 core/sorter_engine.py → 找到 classify_image()",
                "PROMPT 变量控制 AI 分类时的提示词",
                "optimize_prompt() 函数处理业务背景→优化提示词",
                "structured 解析在 _parse_structured_desc() 中",
            ]),
            ("跨平台说明", [
                f"当前系统: {pf.system()} {pf.release()}",
                "字体: macOS=SF Pro / Windows=Segoe UI / Linux=Noto Sans（自动检测）",
                "路径: 全部使用 os.path / pathlib 相对路径",
                "HEIC: 需要安装 pillow-heif（requirements.txt 已包含）",
                "启动: Mac 用 run.sh / Windows 用 run.bat",
                "打包: packaging/ 下有 build_macos.sh 和 build_windows.bat",
            ]),
            ("构建发布", [
                "macOS: bash packaging/build_macos.sh",
                "Windows: packaging\\build_windows.bat",
                "输出: dist/SnapSort.app 或 dist/SnapSort.exe",
                "需要 PyInstaller: pip install pyinstaller",
            ]),
        ]

        for title, items in sections:
            ctk.CTkLabel(frm, text=title, font=font_safe(15, "bold"),
                         text_color=COLORS["primary"]).pack(anchor="w", pady=(12, 4))
            for item in items:
                ctk.CTkLabel(frm, text=item, font=font_safe(12),
                             text_color=COLORS["text_secondary"]).pack(anchor="w", padx=12)

        ctk.CTkLabel(frm, text=f"\n乔心制作 · v3.0 · {pf.system()}",
                     font=font_safe(11), text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(12, 0))
        ctk.CTkButton(frm, text="关闭", command=win.destroy,
                      **secondary_button_style()).pack(anchor="w", pady=(8, 0))


def main():
    try:
        root = ctk.CTk()
        app = SnapSortApp(root)
        root.mainloop()
    except Exception as e:
        import traceback
        error_msg = f"SnapSort 启动失败：\n\n{type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        try:
            messagebox.showerror("启动错误", error_msg)
        except Exception:
            print(error_msg, file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
