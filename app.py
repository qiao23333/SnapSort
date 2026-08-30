#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SnapSort — 本地 AI 图片素材分类器。"""
import os
import platform
import subprocess
import sys
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

# 将项目根目录加入 sys.path
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.config import ConfigManager
from core.icon_manager import selected_icon_path
from core.paths import desktop_dir, resource_path
from core.version import __version__
from ui.dashboard import DashboardPage
from ui.theme import (
    COLORS,
    apply_root_theme,
    font_safe,
    secondary_button_style,
    sidebar_button_active_style,
    sidebar_button_style,
)

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("dark-blue")


def _set_windows_app_id():
    """让 Windows 用 SnapSort 自己的任务栏分组与内嵌 EXE 图标。"""
    if platform.system() != "Windows":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Qiaoxin.SnapSort.Desktop"
        )
    except (AttributeError, OSError):
        pass


def get_default_input_dir():
    """获取默认输入目录：优先使用上次路径，否则为桌面"""
    desktop = desktop_dir()
    return str(desktop / "素材内容") if (desktop / "素材内容").exists() else str(desktop)


def get_default_output_dir():
    """获取默认输出目录"""
    desktop = desktop_dir()
    return str(desktop / "素材内容_已分类")


def _create_auto_sort_page(*args, **kwargs):
    from ui.auto_sort import AutoSortPage
    return AutoSortPage(*args, **kwargs)


def _create_gallery_page(*args, **kwargs):
    from ui.gallery import GalleryPage
    return GalleryPage(*args, **kwargs)


def _create_toolbox_page(*args, **kwargs):
    from ui.toolbox import ToolboxPage
    return ToolboxPage(*args, **kwargs)


def _create_history_page(*args, **kwargs):
    from ui.history_view import HistoryPage
    return HistoryPage(*args, **kwargs)


def _create_settings_page(*args, **kwargs):
    from ui.settings import SettingsPage
    return SettingsPage(*args, **kwargs)


class SnapSortApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"SnapSort {__version__}")
        self.config_manager = ConfigManager()
        self.active_icon_path = selected_icon_path(self.config_manager)

        # 全局变量（路径）：从配置读取，无记录则使用默认桌面路径
        default_input = self.config_manager.get("last_input") or get_default_input_dir()
        default_output = self.config_manager.get("last_output") or get_default_output_dir()
        self.input_var = ctk.StringVar(value=default_input)
        self.output_var = ctk.StringVar(value=default_output)

        self.current_page = None
        self.pages = {}
        self.page_factories = {}
        self.nav_buttons = {}
        self._task_running = False

        self._center_window()
        self._build_ui()
        self.show_page("dashboard")
        self.root.after_idle(self._show_ready)

    def _center_window(self):
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        w = min(1280, max(760, screen_w - 80))
        h = min(860, max(600, screen_h - 80))
        w = min(w, screen_w)
        h = min(h, screen_h)
        self.root.minsize(min(900, w), min(640, h))
        x = max(0, (screen_w - w) // 2)
        y = max(0, (screen_h - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _show_ready(self):
        """首帧完整渲染后再显示，避免 Windows 启动时先黑后白。"""
        self.root.update_idletasks()
        self.root.deiconify()
        self.root.lift()

    def _build_ui(self):
        apply_root_theme(self.root, self.active_icon_path)
        self._setup_dnd()

        # 主容器
        self.container = ctk.CTkFrame(self.root, fg_color=COLORS["bg"], corner_radius=0)
        self.container.pack(fill="both", expand=True)

        # 侧边栏
        self.sidebar = ctk.CTkFrame(self.container, width=240, fg_color=COLORS["sidebar"],
                                     corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # 品牌区：使用真实图标，不依赖各平台表现不一的彩色 Emoji。
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=80)
        logo_frame.pack(fill="x", padx=20, pady=(24, 16))
        logo_frame.pack_propagate(False)
        brand_row = ctk.CTkFrame(logo_frame, fg_color="transparent")
        brand_row.pack(fill="x", anchor="w")
        try:
            self.brand_icon = self._make_ctk_icon(self.active_icon_path, 34)
            self.brand_icon_label = ctk.CTkLabel(
                brand_row, text="", image=self.brand_icon, width=34, height=34)
            self.brand_icon_label.pack(
                side="left", padx=(0, 10))
        except Exception:
            self.brand_icon = None
            self.brand_icon_label = None
        ctk.CTkLabel(brand_row, text="SnapSort", font=font_safe(22, "bold"),
                     text_color=COLORS["text"]).pack(side="left")
        # 副标题 — 点击 5 次打开开发者面板（彩蛋）
        # 用 CTkButton 伪装成普通文字标签，保证点击事件可靠触发
        self._dev_click_count = 0
        self._dev_click_timer = None
        self.dev_btn = ctk.CTkButton(logo_frame, text="本地 AI 乔心制作",
                     font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"],
                     fg_color=COLORS["sidebar"], hover_color=COLORS["hover"],
                     border_width=0, height=24, anchor="w",
                     command=self._on_dev_label_click)
        self.dev_btn.pack(anchor="w", padx=(44 if self.brand_icon else 0, 0))

        # 导航按钮（macOS 风格侧边栏）
        nav_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_container.pack(fill="x", padx=12, pady=(8, 0))

        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "仪表盘"),
            ("auto_sort", "自动分类"),
            ("gallery", "素材预览"),
            ("toolbox", "工具箱"),
            ("history", "历史记录"),
            ("settings", "设置"),
        ]

        for page_key, label in nav_items:
            btn = ctk.CTkButton(nav_container, text=f"  {label}",
                                command=lambda k=page_key: self.show_page(k),
                                **sidebar_button_style())
            btn.pack(fill="x", pady=(0, 6))
            self.nav_buttons[page_key] = btn

        # 全局任务指示器（切页面也能看到后台任务在跑）
        self.task_indicator = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.task_indicator.pack(fill="x", padx=12, pady=(8, 0))
        self.task_indicator_label = ctk.CTkLabel(
            self.task_indicator, text="", font=font_safe(11, "bold"),
            text_color=COLORS["accent"], anchor="w")
        self.task_indicator_label.pack(fill="x")
        self.task_indicator_bar = ctk.CTkProgressBar(
            self.task_indicator, progress_color=COLORS["accent"],
            fg_color=COLORS["border_light"], height=4)
        self.task_indicator_bar.set(0)
        self.task_indicator_bar.pack(fill="x", pady=(4, 0))
        self.task_indicator.pack_forget()  # 默认隐藏

        # 底部状态
        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=20, pady=20)
        ctk.CTkLabel(footer, text="本地 AI · 隐私安全",
                     font=font_safe(11, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w")
        ctk.CTkLabel(footer, text=f"v{__version__}",
                     font=font_safe(11, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w")

        # 内容区
        self.content_frame = ctk.CTkFrame(self.container, fg_color=COLORS["bg"], corner_radius=0)
        self.content_frame.pack(side="left", fill="both", expand=True)

        # 页面按首次访问创建。工具箱组件较多，延迟构建能明显缩短冷启动，
        # 也避免用户只做一次分类时为不用的页面付出启动成本。
        self.page_factories = {
            "dashboard": DashboardPage,
            "auto_sort": _create_auto_sort_page,
            "gallery": _create_gallery_page,
            "toolbox": _create_toolbox_page,
            "history": _create_history_page,
            "settings": _create_settings_page,
        }

    @staticmethod
    def _make_ctk_icon(path, size):
        with Image.open(path) as opened:
            source = opened.convert("RGBA").copy()
        return ctk.CTkImage(light_image=source, dark_image=source, size=(size, size))

    def apply_icon_choice(self, preset, custom_path=""):
        """保存并立即应用应用内图标选择。"""
        icon_config = {"preset": preset, "custom_path": str(custom_path or "")}
        self.config_manager.set("app_icon", icon_config)
        self.active_icon_path = selected_icon_path(self.config_manager)
        apply_root_theme(self.root, self.active_icon_path)
        if self.brand_icon_label is not None:
            self.brand_icon = self._make_ctk_icon(self.active_icon_path, 34)
            self.brand_icon_label.configure(image=self.brand_icon)
        return self.active_icon_path

    def show_page(self, page_key):
        if page_key not in self.page_factories:
            return

        # 重复点击当前导航不应重新 pack 页面、更不应触发磁盘扫描。
        if page_key == self.current_page:
            return

        if page_key not in self.pages:
            page_class = self.page_factories[page_key]
            self.pages[page_key] = page_class(
                self.content_frame, self, fg_color=COLORS["bg"])

        if self.current_page:
            self.pages[self.current_page].pack_forget()
            self.nav_buttons[self.current_page].configure(**sidebar_button_style())

        self.pages[page_key].pack(fill="both", expand=True)
        self.current_page = page_key

        # 高亮当前导航
        self.nav_buttons[page_key].configure(**sidebar_button_active_style())

        # 先完成页面切换，让导航点击立即得到视觉反馈；数据刷新放到
        # 当前事件循环空闲时执行。页面可通过 on_show 自行判断数据是否
        # 已失效，避免在页面之间来回切换时重复扫描磁盘和重建组件。
        self.root.after_idle(lambda key=page_key: self._refresh_visible_page(key))

    def _refresh_visible_page(self, page_key):
        """仅刷新仍处于前台的页面，忽略快速切页留下的过期任务。"""
        if page_key != self.current_page or page_key not in self.pages:
            return
        page = self.pages[page_key]
        if hasattr(page, "on_show"):
            page.on_show()
        elif hasattr(page, "refresh"):
            page.refresh()

    def set_task_running(self, running, label=""):
        """全局任务状态指示器：后台任务运行/结束时切换侧栏指示器可见性。
        切换页面不影响后台线程，但用户需要看到任务仍在跑。
        """
        self._task_running = running
        if running:
            self.task_indicator_label.configure(text=f"{label}…")
            self.task_indicator_bar.set(0)
            self.task_indicator.pack(fill="x", padx=12, pady=(8, 0))
        else:
            self.task_indicator_label.configure(text="")
            self.task_indicator.pack_forget()

    def update_task_progress(self, ratio):
        """更新侧栏指示器的进度条（0~1）。"""
        if self._task_running:
            self.task_indicator_bar.set(ratio)

    def open_output_folder(self):
        output_dir = self.output_var.get().strip()
        if os.path.isdir(output_dir):
            if platform.system() == "Windows":
                os.startfile(output_dir)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", output_dir])
            else:
                subprocess.Popen(["xdg-open", output_dir])
        else:
            messagebox.showwarning("文件夹不存在", f"输出文件夹尚未创建：\n{output_dir}")

    def _setup_dnd(self):
        """拖拽文件夹到窗口 → 设为素材输入路径（需 tkinterdnd2，未安装则静默跳过）"""
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            from tkinterdnd2.TkinterDnD import DnDWrapper
            TkinterDnD._require(self.root)
            # 把 DnD 全部方法注入普通 Tk root（tkinterdnd2 默认只给自家 Tk 子类）
            for name, attr in vars(DnDWrapper).items():
                if callable(attr):
                    setattr(self.root, name, attr.__get__(self.root))
                elif name.startswith("_subst_format"):
                    setattr(self.root, name, attr)
        except Exception:
            return

        def _on_drop(event):
            raw = event.data.strip()
            if raw.startswith("{"):
                raw = raw[1:raw.index("}")] if "}" in raw else raw[1:]
            else:
                raw = raw.split(" ")[0]
            if raw.startswith("file://"):
                from urllib.parse import unquote, urlparse
                raw = unquote(urlparse(raw).path)
            if os.path.isdir(raw):
                self.input_var.set(raw)
                self.save_path_config()
                self._show_toast(f"📂 已设置素材文件夹：{os.path.basename(raw) or raw}")
            elif os.path.isfile(raw):
                self._show_toast("⚠️ 拖入的是文件，请拖文件夹")

        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", _on_drop)

    def _show_toast(self, message):
        try:
            from ui.widgets import Toast
            Toast(self.root, message)
        except Exception:
            pass

    def save_path_config(self):
        """保存当前输入/输出路径到配置"""
        self.config_manager.set("last_input", self.input_var.get().strip())
        self.config_manager.set("last_output", self.output_var.get().strip())
        self.config_manager.save()

    def _on_dev_label_click(self):
        """副标题点击 5 次打开开发者面板"""
        self._dev_click_count += 1
        if self._dev_click_timer:
            self.root.after_cancel(self._dev_click_timer)
        self._dev_click_timer = self.root.after(2000, lambda: setattr(self, "_dev_click_count", 0))
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

        ctk.CTkLabel(frm, text="开发者面板", font=font_safe(20, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", pady=(0, 8))

        sections = [
            ("项目结构", [
                "app.py              — 主入口，侧边栏 + 页面路由（点击本副标题5次打开此面板）",
                "ui/theme.py         — 配色系统、字体、通用样式（改颜色改这里）",
                "ui/widgets.py       — 复用组件（Toast 提示等）",
                "ui/dashboard.py     — 仪表盘页",
                "ui/auto_sort.py     — 自动分类页（事件模式 + 内容模式）",
                "ui/gallery.py       — 图库页（缩略图线程池加载）",
                "ui/toolbox.py       — 工具箱页（搜图/描述/问答/助手/查重/转换等）",
                "ui/history_view.py  — 历史记录页",
                "ui/settings.py      — 设置页（分类配置、人物/地点、规则引擎）",
                "core/sorter_engine.py  — AI 分类核心引擎（prompt、分类、重试）",
                "core/event_classifier.py — 事件聚类（日期分组、合并、命名）",
                "core/clip_search.py    — CLIP 语义搜图",
                "core/rule_engine.py    — 规则引擎（后处理自动化）",
                "core/config.py         — 配置管理（JSON 读写）",
                "core/image_utils.py    — 图片处理（缩略图、HEIC、矢量转换）",
                "core/model_info.py     — 模型类型识别（视觉/文本）",
                "core/reference_manager.py — 人物/地点参考照片管理",
                "core/report.py         — CSV/Excel 报告",
                "core/history.py        — 历史记录存储",
                "generate_icon.py    — 图标生成脚本（重跑即可换图标）",
            ]),
            ("图标修改（换图标看这里）", [
                "图标文件: data/snapsort_icon.png（256px）/ data/snapsort_icon_small.png（64px）",
                "直接替换这两个文件即可换图标；或改 generate_icon.py 后重新运行它",
                "窗口标题栏图标: ui/theme.py 的 apply_root_theme()（iconphoto，自动加载）",
                "⚠️ Dock/任务栏图标: python 直跑时永远是 Python 图标，属系统限制；",
                "   打包为 .app/.exe 后自动使用应用图标（见下方构建发布）",
            ]),
            ("配色修改", [
                "打开 ui/theme.py → 修改 COLORS 字典",
                "primary = 主按钮与导航颜色（默认 Apple 蓝 #0071E3）",
                "accent = 琥珀色，仅用于 AI 状态",
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

        ctk.CTkLabel(frm, text=f"\n乔心制作 · v{__version__} · {pf.system()}",
                     font=font_safe(11), text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(12, 0))
        ctk.CTkButton(frm, text="关闭", command=win.destroy,
                      **secondary_button_style()).pack(anchor="w", pady=(8, 0))


def _quit(root, app):
    """退出前强制落盘配置（防抖中的未保存项）"""
    try:
        app.config_manager.flush()
    except Exception:
        pass
    root.destroy()


def main():
    from core.logger import get_logger
    log = get_logger()
    log.info("SnapSort 启动")
    try:
        _set_windows_app_id()
        root = ctk.CTk()
        # CTk 根窗口默认会立即映射；在组件主题尚未应用时可能短暂显示黑色。
        # 先隐藏，待完整首帧构建后由 SnapSortApp._show_ready() 一次性显示。
        root.withdraw()
        app = SnapSortApp(root)
        root.protocol("WM_DELETE_WINDOW", lambda: _quit(root, app))
        root.mainloop()
        log.info("SnapSort 正常退出")
    except Exception as e:
        import traceback
        error_msg = f"SnapSort 启动失败：\n\n{type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        log.error("启动失败: %s", traceback.format_exc())
        try:
            messagebox.showerror("启动错误", error_msg)
        except Exception:
            print(error_msg, file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
