#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设置页面：分类配置、规则引擎、模型管理、输出选项"""
import os
import json
import threading
import customtkinter as ctk
from tkinter import messagebox, filedialog

import requests

from ui.theme import COLORS, font_safe, primary_button_style, secondary_button_style, card_frame_style
from core.sorter_engine import fetch_all_models, DEFAULT_URL, ensure_model
from core.model_info import get_model_hint, get_model_role_tag
from core import reference_manager as ref_mgr


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.configure(fg_color=COLORS["bg"])
        self.category_widgets = []
        self._build_ui()
        self._refresh_installed_models()

    def _build_ui(self):
        ctk.CTkLabel(self, text="设置", font=font_safe(28, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=32, pady=(28, 8))
        ctk.CTkLabel(self, text="管理分类、规则引擎、模型和输出选项",
                     font=font_safe(14, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=32, pady=(0, 20))

        # 用滚动区域包裹所有设置内容
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # ── 1. 分类配置 ──
        self._build_category_section()
        # ── 2. 已知人物 ──
        self._build_person_section()
        # ── 3. 已知地点 ──
        self._build_place_section()
        # ── 4. 规则引擎 ──
        self._build_rule_section()
        # ── 5. 模型管理 ──
        self._build_model_section()
        # ── 6. 输出选项 ──
        self._build_output_section()

        # 保存按钮（浮动在底部）
        save_bar = ctk.CTkFrame(self, fg_color=COLORS["card"], height=52,
                                corner_radius=0)
        save_bar.pack(fill="x", side="bottom")
        save_bar.pack_propagate(False)
        ctk.CTkButton(save_bar, text="💾 保存全部设置", command=self._save_all,
                      width=180, **primary_button_style()).pack(side="right", padx=32, pady=10)

    # ── 分类配置 ──
    def _build_category_section(self):
        card = ctk.CTkFrame(self.scroll_frame, **card_frame_style())
        card.pack(fill="x", padx=32, pady=(8, 16))

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 12))
        ctk.CTkLabel(hdr, text="📂 分类配置", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(hdr, text="➕ 添加分类", command=self._add_category,
                      **secondary_button_style()).pack(side="right")

        self.cat_list = ctk.CTkFrame(card, fg_color="transparent")
        self.cat_list.pack(fill="x", padx=24, pady=(0, 20))
        self._render_categories()

    def _render_categories(self):
        for widget in self.cat_list.winfo_children():
            widget.destroy()
        self.category_widgets.clear()

        for cat, desc in self.app.config_manager.get("categories", {}).items():
            row = ctk.CTkFrame(self.cat_list, fg_color=COLORS["bg"], corner_radius=8, height=48)
            row.pack(fill="x", pady=(0, 8))
            row.pack_propagate(False)

            name_entry = ctk.CTkEntry(row, font=font_safe(13, "normal"), fg_color="white",
                                      border_color=COLORS["border"])
            name_entry.insert(0, cat)
            name_entry.pack(side="left", padx=(12, 8), fill="y", pady=6)

            desc_entry = ctk.CTkEntry(row, font=font_safe(13, "normal"), fg_color="white",
                                      border_color=COLORS["border"])
            desc_entry.insert(0, desc)
            desc_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=6)

            ctk.CTkButton(row, text="删除", width=60, height=28,
                          command=lambda c=cat: self._delete_category(c),
                          fg_color=COLORS["danger"], hover_color="#E6352B",
                          text_color="white", font=font_safe(12, "normal")).pack(
                              side="right", padx=(0, 12), pady=6)

            self.category_widgets.append((name_entry, desc_entry))

    def _add_category(self):
        categories = self.app.config_manager.get("categories", {})
        categories["新分类"] = ""
        self.app.config_manager.set("categories", categories)
        self._render_categories()

    def _delete_category(self, cat):
        categories = self.app.config_manager.get("categories", {})
        if cat in categories:
            del categories[cat]
            self.app.config_manager.set("categories", categories)
            self._render_categories()

    # ── 已知人物 ──
    def _build_person_section(self):
        card = ctk.CTkFrame(self.scroll_frame, **card_frame_style())
        card.pack(fill="x", padx=32, pady=(8, 16))

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 8))
        ctk.CTkLabel(hdr, text="👤 已知人物", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(hdr, text="➕ 添加人物", command=self._add_person_dialog,
                      **secondary_button_style()).pack(side="right")

        desc = ctk.CTkLabel(card,
                            text="分类时自动识别这些固定人物。可添加参考照片让 AI 视觉比对识别（推荐），"
                                 "或仅用文字描述。含人物的照片会额外归档到 人物库/{姓名}/。",
                            font=font_safe(12, "normal"), text_color=COLORS["text_secondary"])
        desc.pack(anchor="w", padx=24, pady=(0, 10))

        # 识别开关
        toggle_row = ctk.CTkFrame(card, fg_color="transparent")
        toggle_row.pack(fill="x", padx=24, pady=(0, 8))
        self.person_recog_var = ctk.BooleanVar(
            value=self.app.config_manager.get("person_recognition", True))
        ctk.CTkCheckBox(toggle_row, text="开启人物识别（按内容分类时生效）",
                        variable=self.person_recog_var,
                        font=font_safe(13), text_color=COLORS["text"],
                        fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]).pack(side="left")

        self.person_list = ctk.CTkFrame(card, fg_color="transparent")
        self.person_list.pack(fill="x", padx=24, pady=(0, 20))
        self._render_persons()

    def _render_persons(self):
        for w in self.person_list.winfo_children():
            w.destroy()

        persons = self.app.config_manager.get("known_persons", []) or []
        if not persons:
            ctk.CTkLabel(self.person_list, text="暂无已知人物，点击「添加人物」创建\n给几张照片告诉 AI 这是谁，分类时自动识别",
                         font=font_safe(12, "normal"),
                         text_color=COLORS["text_secondary"]).pack(pady=10)
            return

        for idx, p in enumerate(persons):
            row = ctk.CTkFrame(self.person_list, fg_color=COLORS["bg"], corner_radius=8, height=52)
            row.pack(fill="x", pady=(0, 8))
            row.pack_propagate(False)

            name = p.get("name", "")
            pdesc = p.get("description", "")
            ref_count = ref_mgr.count_reference_images("person", name)
            ctk.CTkLabel(row, text="👤", font=font_safe(16),
                         text_color=COLORS["primary"], width=30).pack(side="left", padx=(12, 4))
            ctk.CTkLabel(row, text=name, font=font_safe(13, "bold"),
                         text_color=COLORS["text"], width=90).pack(side="left", padx=(0, 8))
            # 参考照片徽章
            if ref_count > 0:
                ctk.CTkLabel(row, text=f"📷{ref_count}", font=font_safe(11, "bold"),
                             fg_color=COLORS["selected"], text_color=COLORS["primary"],
                             corner_radius=4, padx=6, pady=2).pack(side="left", padx=(0, 8))
            disp = pdesc if len(pdesc) <= 40 else pdesc[:37] + "..."
            ctk.CTkLabel(row, text=disp, font=font_safe(12, "normal"),
                         text_color=COLORS["text_secondary"]).pack(side="left", fill="x", expand=True)

            _edit_btn = secondary_button_style()
            _edit_btn.update({"width": 50, "height": 26})
            ctk.CTkButton(row, text="编辑",
                          command=lambda i=idx: self._edit_person_dialog(i),
                          **_edit_btn).pack(side="right", padx=(6, 8))
            ctk.CTkButton(row, text="删除", width=50, height=26,
                          command=lambda i=idx: self._delete_person(i),
                          fg_color=COLORS["danger"], hover_color="#E6352B",
                          text_color="white", font=font_safe(11, "normal")).pack(side="right", padx=(0, 4))

    def _add_person_dialog(self):
        self._person_dialog(idx=None, title="添加已知人物")

    def _edit_person_dialog(self, idx):
        self._person_dialog(idx=idx, title="编辑已知人物")

    def _person_dialog(self, idx, title):
        persons = self.app.config_manager.get("known_persons", []) or []
        existing = persons[idx] if idx is not None and idx < len(persons) else {}
        old_name = existing.get("name", "")

        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("540x560")
        dialog.transient(self)

        frm = ctk.CTkScrollableFrame(dialog, fg_color=COLORS["bg"])
        frm.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(frm, text="人物姓名", font=font_safe(13, "bold")).pack(anchor="w")
        name_entry = ctk.CTkEntry(frm, font=font_safe(13), fg_color="white",
                                  placeholder_text="如：张总 / 王负责人 / 李工")
        name_entry.insert(0, old_name)
        name_entry.pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(frm, text="外貌描述（辅助识别，有参考照片可简写）", font=font_safe(13, "bold")).pack(anchor="w")
        ctk.CTkLabel(frm, text="建议包含：性别、年龄段、发型、眼镜、服饰特征等",
                     font=font_safe(11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        desc_entry = ctk.CTkEntry(frm, font=font_safe(13), fg_color="white",
                                  placeholder_text="如：中年男性，戴黑框眼镜，短发，常穿深色衬衫")
        desc_entry.insert(0, existing.get("description", ""))
        desc_entry.pack(fill="x", pady=(4, 8))

        # 参考照片区域
        ref_state = self._build_ref_photo_area(frm, "person", old_name)

        ctk.CTkLabel(frm, text="备注关键词（可选，逗号分隔，辅助匹配）", font=font_safe(13, "bold")).pack(anchor="w", pady=(8, 0))
        kw_entry = ctk.CTkEntry(frm, font=font_safe(13), fg_color="white",
                                placeholder_text="如：负责人,创始人,张总")
        kw_entry.insert(0, existing.get("keywords", ""))
        kw_entry.pack(fill="x", pady=(4, 12))

        def _save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("姓名不能为空", "请输入人物姓名")
                return
            person = {
                "name": name,
                "description": desc_entry.get().strip(),
                "keywords": [k.strip() for k in kw_entry.get().split(",") if k.strip()]
            }
            persons = self.app.config_manager.get("known_persons", []) or []
            if idx is not None and idx < len(persons):
                persons[idx] = person
            else:
                persons.append(person)
            self.app.config_manager.set("known_persons", persons)

            # 处理参考照片
            self._save_ref_photos(ref_state, "person", old_name, name)

            self._render_persons()
            dialog.destroy()

        ctk.CTkButton(frm, text="保存", command=_save, **primary_button_style()).pack(pady=(8, 0))

    def _delete_person(self, idx):
        persons = self.app.config_manager.get("known_persons", []) or []
        if idx < len(persons):
            name = persons[idx].get("name", "")
            if messagebox.askyesno("确认删除", f"删除已知人物「{name}」？\n参考照片也会一并删除。"):
                ref_mgr.delete_reference_images("person", name)
                del persons[idx]
                self.app.config_manager.set("known_persons", persons)
                self._render_persons()

    # ── 已知地点 ──
    def _build_place_section(self):
        card = ctk.CTkFrame(self.scroll_frame, **card_frame_style())
        card.pack(fill="x", padx=32, pady=(8, 16))

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 8))
        ctk.CTkLabel(hdr, text="📍 已知地点", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(hdr, text="➕ 添加地点", command=self._add_place_dialog,
                      **secondary_button_style()).pack(side="right")

        desc = ctk.CTkLabel(card,
                            text="分类时自动识别这些固定地点。可添加参考照片让 AI 视觉比对识别。"
                                 "含地点的照片会额外归档到 地点库/{地点名}/。",
                            font=font_safe(12, "normal"), text_color=COLORS["text_secondary"])
        desc.pack(anchor="w", padx=24, pady=(0, 10))

        toggle_row = ctk.CTkFrame(card, fg_color="transparent")
        toggle_row.pack(fill="x", padx=24, pady=(0, 8))
        self.place_recog_var = ctk.BooleanVar(
            value=self.app.config_manager.get("place_recognition", True))
        ctk.CTkCheckBox(toggle_row, text="开启地点识别（按内容分类时生效）",
                        variable=self.place_recog_var,
                        font=font_safe(13), text_color=COLORS["text"],
                        fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]).pack(side="left")

        self.place_list = ctk.CTkFrame(card, fg_color="transparent")
        self.place_list.pack(fill="x", padx=24, pady=(0, 20))
        self._render_places()

    def _render_places(self):
        for w in self.place_list.winfo_children():
            w.destroy()

        places = self.app.config_manager.get("known_places", []) or []
        if not places:
            ctk.CTkLabel(self.place_list, text="暂无已知地点，点击「添加地点」创建\n给几张照片告诉 AI 这是哪里，分类时自动识别",
                         font=font_safe(12, "normal"),
                         text_color=COLORS["text_secondary"]).pack(pady=10)
            return

        for idx, p in enumerate(places):
            row = ctk.CTkFrame(self.place_list, fg_color=COLORS["bg"], corner_radius=8, height=52)
            row.pack(fill="x", pady=(0, 8))
            row.pack_propagate(False)

            name = p.get("name", "")
            pdesc = p.get("description", "")
            ref_count = ref_mgr.count_reference_images("place", name)
            ctk.CTkLabel(row, text="📍", font=font_safe(16),
                         text_color=COLORS["primary"], width=30).pack(side="left", padx=(12, 4))
            ctk.CTkLabel(row, text=name, font=font_safe(13, "bold"),
                         text_color=COLORS["text"], width=90).pack(side="left", padx=(0, 8))
            if ref_count > 0:
                ctk.CTkLabel(row, text=f"📷{ref_count}", font=font_safe(11, "bold"),
                             fg_color=COLORS["selected"], text_color=COLORS["primary"],
                             corner_radius=4, padx=6, pady=2).pack(side="left", padx=(0, 8))
            disp = pdesc if len(pdesc) <= 40 else pdesc[:37] + "..."
            ctk.CTkLabel(row, text=disp, font=font_safe(12, "normal"),
                         text_color=COLORS["text_secondary"]).pack(side="left", fill="x", expand=True)

            _edit_btn = secondary_button_style()
            _edit_btn.update({"width": 50, "height": 26})
            ctk.CTkButton(row, text="编辑",
                          command=lambda i=idx: self._edit_place_dialog(i),
                          **_edit_btn).pack(side="right", padx=(6, 8))
            ctk.CTkButton(row, text="删除", width=50, height=26,
                          command=lambda i=idx: self._delete_place(i),
                          fg_color=COLORS["danger"], hover_color="#E6352B",
                          text_color="white", font=font_safe(11, "normal")).pack(side="right", padx=(0, 4))

    def _add_place_dialog(self):
        self._place_dialog(idx=None, title="添加已知地点")

    def _edit_place_dialog(self, idx):
        self._place_dialog(idx=idx, title="编辑已知地点")

    def _place_dialog(self, idx, title):
        places = self.app.config_manager.get("known_places", []) or []
        existing = places[idx] if idx is not None and idx < len(places) else {}
        old_name = existing.get("name", "")

        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("540x520")
        dialog.transient(self)

        frm = ctk.CTkScrollableFrame(dialog, fg_color=COLORS["bg"])
        frm.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(frm, text="地点名称", font=font_safe(13, "bold")).pack(anchor="w")
        name_entry = ctk.CTkEntry(frm, font=font_safe(13), fg_color="white",
                                  placeholder_text="如：悉尼工厂 / 墨尔本办公室 / 仓库A")
        name_entry.insert(0, old_name)
        name_entry.pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(frm, text="地点描述（辅助识别，有参考照片可简写）", font=font_safe(13, "bold")).pack(anchor="w")
        ctk.CTkLabel(frm, text="建议包含：地点类型、特征标志、周边环境等",
                     font=font_safe(11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        desc_entry = ctk.CTkEntry(frm, font=font_safe(13), fg_color="white",
                                  placeholder_text="如：大型工厂车间，蓝色机器，有安全标识")
        desc_entry.insert(0, existing.get("description", ""))
        desc_entry.pack(fill="x", pady=(4, 8))

        ref_state = self._build_ref_photo_area(frm, "place", old_name)

        def _save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("名称不能为空", "请输入地点名称")
                return
            place = {
                "name": name,
                "description": desc_entry.get().strip(),
            }
            places = self.app.config_manager.get("known_places", []) or []
            if idx is not None and idx < len(places):
                places[idx] = place
            else:
                places.append(place)
            self.app.config_manager.set("known_places", places)

            self._save_ref_photos(ref_state, "place", old_name, name)

            self._render_places()
            dialog.destroy()

        ctk.CTkButton(frm, text="保存", command=_save, **primary_button_style()).pack(pady=(8, 0))

    def _delete_place(self, idx):
        places = self.app.config_manager.get("known_places", []) or []
        if idx < len(places):
            name = places[idx].get("name", "")
            if messagebox.askyesno("确认删除", f"删除已知地点「{name}」？\n参考照片也会一并删除。"):
                ref_mgr.delete_reference_images("place", name)
                del places[idx]
                self.app.config_manager.set("known_places", places)
                self._render_places()

    # ── 参考照片 UI（人物/地点共用）──
    def _build_ref_photo_area(self, parent, ref_type, entity_name):
        """构建参考照片选择 UI，返回状态字典。"""
        state = {
            "existing": ref_mgr.get_reference_images(ref_type, entity_name) if entity_name else [],
            "new": [],
            "removed": set(),
        }

        ctk.CTkLabel(parent, text="📷 参考照片（给几张照片，让 AI 视觉比对识别）",
                     font=font_safe(13, "bold")).pack(anchor="w", pady=(8, 2))
        ctk.CTkLabel(parent, text=f"选 1-{ref_mgr.MAX_REF_IMAGES} 张这个{'人' if ref_type == 'person' else '地点'}的照片，"
                                 "分类时 AI 会对比参考照片来精准识别",
                     font=font_safe(11), text_color=COLORS["text_secondary"]).pack(anchor="w")

        list_frame = ctk.CTkFrame(parent, fg_color=COLORS["bg"], corner_radius=8,
                                  border_color=COLORS["border"], border_width=1)
        list_frame.pack(fill="x", pady=(4, 8))

        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 4))
        _photo_btn = secondary_button_style()
        _photo_btn.update({"width": 120, "height": 30})
        ctk.CTkButton(btn_row, text="📷 选择照片",
                      command=lambda: self._select_ref_photos(state, ref_type),
                      **_photo_btn).pack(side="left")

        def refresh():
            for w in list_frame.winfo_children():
                w.destroy()
            current_refs = [(p, True) for p in state["existing"] if p not in state["removed"]]
            current_refs += [(p, False) for p in state["new"]]
            if not current_refs:
                ctk.CTkLabel(list_frame, text="暂无参考照片，点击「选择照片」添加",
                             font=font_safe(11), text_color=COLORS["text_secondary"]).pack(pady=10)
                return
            for path, is_existing in current_refs:
                row = ctk.CTkFrame(list_frame, fg_color="transparent")
                row.pack(fill="x", padx=8, pady=2)
                fname = os.path.basename(path)
                tag = "已保存" if is_existing else "新选"
                ctk.CTkLabel(row, text=f"📷 {tag}  {fname[:35]}",
                             font=font_safe(11), text_color=COLORS["text"]).pack(side="left", padx=(4, 8))
                ctk.CTkButton(row, text="✕", width=24, height=20,
                              fg_color=COLORS["danger"], hover_color="#E6352B",
                              text_color="white", font=font_safe(10),
                              command=lambda p=path, ie=is_existing: self._remove_ref(state, p, ie, refresh)
                              ).pack(side="right")

        state["refresh"] = refresh
        refresh()
        return state

    def _select_ref_photos(self, state, ref_type):
        paths = filedialog.askopenfilenames(
            title="选择参考照片",
            filetypes=[("图片", "*.jpg *.jpeg *.png *.webp *.heic *.bmp *.tiff"),
                       ("所有文件", "*.*")]
        )
        if not paths:
            return
        current = len([p for p in state["existing"] if p not in state["removed"]]) + len(state["new"])
        remaining = ref_mgr.MAX_REF_IMAGES - current
        if remaining <= 0:
            messagebox.showwarning("已达上限", f"最多 {ref_mgr.MAX_REF_IMAGES} 张参考照片")
            return
        state["new"].extend(paths[:remaining])
        if len(paths) > remaining:
            messagebox.showinfo("提示", f"已达上限，仅添加前 {remaining} 张")
        state["refresh"]()

    def _remove_ref(self, state, path, is_existing, refresh):
        if is_existing:
            state["removed"].add(path)
        else:
            if path in state["new"]:
                state["new"].remove(path)
        refresh()

    def _save_ref_photos(self, ref_state, ref_type, old_name, new_name):
        """保存参考照片：处理重命名、删除、新增。"""
        # 名称变更 → 重命名参考照片目录
        if old_name and old_name != new_name:
            ref_mgr.rename_reference_dir(ref_type, old_name, new_name)

        # 删除标记为移除的照片
        for path in ref_state["removed"]:
            ref_mgr.delete_single_reference(ref_type, new_name, path)

        # 保存新选的照片
        if ref_state["new"]:
            ref_mgr.save_reference_images(ref_type, new_name, ref_state["new"])

    # ── 规则引擎 ──
    def _build_rule_section(self):
        card = ctk.CTkFrame(self.scroll_frame, **card_frame_style())
        card.pack(fill="x", padx=32, pady=(8, 16))
        self.rule_card = card

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 12))
        ctk.CTkLabel(hdr, text="🔧 规则引擎", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(hdr, text="➕ 添加规则", command=self._add_rule_dialog,
                      **secondary_button_style()).pack(side="right")

        desc = ctk.CTkLabel(card, text="分类完成后自动执行规则。例如：IF 分类==截图 AND 包含'微信' THEN 移动到 WeChat_Screenshots",
                            font=font_safe(12, "normal"), text_color=COLORS["text_secondary"])
        desc.pack(anchor="w", padx=24, pady=(0, 12))

        self.rule_list = ctk.CTkFrame(card, fg_color="transparent")
        self.rule_list.pack(fill="x", padx=24, pady=(0, 20))
        self._render_rules()

    def _render_rules(self):
        for w in self.rule_list.winfo_children():
            w.destroy()

        rules = self.app.config_manager.get("rules", [])
        if not rules:
            ctk.CTkLabel(self.rule_list, text="暂无规则，点击「添加规则」创建",
                         font=font_safe(12, "normal"),
                         text_color=COLORS["text_secondary"]).pack(pady=10)
            return

        for idx, rule in enumerate(rules):
            row = ctk.CTkFrame(self.rule_list, fg_color=COLORS["bg"], corner_radius=8, height=52)
            row.pack(fill="x", pady=(0, 8))
            row.pack_propagate(False)

            enabled = rule.get("enabled", True)
            prefix = "🟢" if enabled else "⚪"
            ctk.CTkLabel(row, text=f"{prefix} {rule.get('name', '未命名')}",
                        font=font_safe(13, "bold"), text_color=COLORS["text"]).pack(
                            side="left", padx=(12, 12), pady=10)

            cond = rule.get("condition", {})
            act = rule.get("action", {})
            detail = f"IF {json.dumps(cond, ensure_ascii=False)}  →  {act.get('type', '?')}: {act.get('target_dir', act.get('pattern', ''))}"
            if len(detail) > 60:
                detail = detail[:57] + "..."
            ctk.CTkLabel(row, text=detail, font=font_safe(11, "normal"),
                        text_color=COLORS["text_secondary"]).pack(
                            side="left", padx=(0, 12))

            ctk.CTkButton(row, text="删除", width=50, height=26,
                          command=lambda i=idx: self._delete_rule(i),
                          fg_color=COLORS["danger"], hover_color="#E6352B",
                          text_color="white", font=font_safe(11, "normal")).pack(
                              side="right", padx=(0, 12))

            _edit_btn = secondary_button_style()
            _edit_btn.update({"width": 50, "height": 26})
            ctk.CTkButton(row, text="编辑",
                          command=lambda i=idx: self._edit_rule_dialog(i),
                          **_edit_btn).pack(side="right", padx=(0, 6))

    def _add_rule_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("添加规则")
        dialog.geometry("520x360")
        dialog.transient(self)

        frm = ctk.CTkFrame(dialog, fg_color=COLORS["bg"])
        frm.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frm, text="规则名称", font=font_safe(13, "bold")).pack(anchor="w")
        name_entry = ctk.CTkEntry(frm, font=font_safe(13), fg_color="white")
        name_entry.pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(frm, text="条件 (category / text_contains / filename_contains)", font=font_safe(13, "bold")).pack(anchor="w")
        ctk.CTkLabel(frm, text='示例: {"category": "截图", "text_contains": "微信"}',
                     font=font_safe(11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        cond_entry = ctk.CTkEntry(frm, font=font_safe(13), fg_color="white")
        cond_entry.pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(frm, text="动作 (type: move/rename/copy, target_dir: 目标目录)", font=font_safe(13, "bold")).pack(anchor="w")
        ctk.CTkLabel(frm, text='示例: {"type": "move", "target_dir": "WeChat_Screenshots"}',
                     font=font_safe(11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        act_entry = ctk.CTkEntry(frm, font=font_safe(13), fg_color="white")
        act_entry.pack(fill="x", pady=(4, 12))

        def _save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("名称不能为空", "请输入规则名称")
                return
            try:
                cond = json.loads(cond_entry.get().strip() or "{}")
                act = json.loads(act_entry.get().strip() or "{}")
            except json.JSONDecodeError as e:
                messagebox.showwarning("JSON 格式错误", f"条件或动作不是有效的 JSON：{e}")
                return

            rules = self.app.config_manager.get("rules", [])
            rules.append({"name": name, "enabled": True, "condition": cond, "action": act})
            self.app.config_manager.set("rules", rules)
            self._render_rules()
            dialog.destroy()

        ctk.CTkButton(frm, text="保存规则", command=_save, **primary_button_style()).pack(pady=(8, 0))

    def _edit_rule_dialog(self, idx):
        # 简化：弹出一个编辑窗口
        rules = self.app.config_manager.get("rules", [])
        if idx >= len(rules):
            return
        rule = rules[idx]

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"编辑规则 - {rule.get('name', '')}")
        dialog.geometry("520x360")
        dialog.transient(self)

        frm = ctk.CTkFrame(dialog, fg_color=COLORS["bg"])
        frm.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frm, text="规则名称", font=font_safe(13, "bold")).pack(anchor="w")
        name_entry = ctk.CTkEntry(frm, font=font_safe(13), fg_color="white")
        name_entry.insert(0, rule.get("name", ""))
        name_entry.pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(frm, text="条件", font=font_safe(13, "bold")).pack(anchor="w")
        cond_entry = ctk.CTkEntry(frm, font=font_safe(13), fg_color="white")
        cond_entry.insert(0, json.dumps(rule.get("condition", {}), ensure_ascii=False))
        cond_entry.pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(frm, text="动作", font=font_safe(13, "bold")).pack(anchor="w")
        act_entry = ctk.CTkEntry(frm, font=font_safe(13), fg_color="white")
        act_entry.insert(0, json.dumps(rule.get("action", {}), ensure_ascii=False))
        act_entry.pack(fill="x", pady=(4, 12))

        enabled_var = ctk.BooleanVar(value=rule.get("enabled", True))
        ctk.CTkCheckBox(frm, text="启用此规则", variable=enabled_var,
                        font=font_safe(13), text_color=COLORS["text"],
                        fg_color=COLORS["primary"]).pack(anchor="w")

        def _save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("名称不能为空", "请输入规则名称")
                return
            try:
                cond = json.loads(cond_entry.get().strip() or "{}")
                act = json.loads(act_entry.get().strip() or "{}")
            except json.JSONDecodeError as e:
                messagebox.showwarning("JSON 格式错误", str(e))
                return
            rules[idx] = {"name": name, "enabled": enabled_var.get(), "condition": cond, "action": act}
            self.app.config_manager.set("rules", rules)
            self._render_rules()
            dialog.destroy()

        ctk.CTkButton(frm, text="保存修改", command=_save, **primary_button_style()).pack(pady=(8, 0))

    def _delete_rule(self, idx):
        rules = self.app.config_manager.get("rules", [])
        if idx < len(rules):
            del rules[idx]
            self.app.config_manager.set("rules", rules)
            self._render_rules()

    # ── 模型管理 ──
    def _build_model_section(self):
        card = ctk.CTkFrame(self.scroll_frame, **card_frame_style())
        card.pack(fill="x", padx=32, pady=(8, 16))

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 12))
        ctk.CTkLabel(hdr, text="🤖 模型管理", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(hdr, text="🔄 刷新", command=self._refresh_installed_models,
                      **secondary_button_style()).pack(side="right")

        # 模型下载区
        dl_row = ctk.CTkFrame(card, fg_color="transparent")
        dl_row.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkLabel(dl_row, text="下载新模型", font=font_safe(13, "normal"),
                     text_color=COLORS["text_secondary"]).pack(side="left")
        self.model_dl_var = ctk.StringVar(value="")
        ctk.CTkEntry(dl_row, textvariable=self.model_dl_var, font=font_safe(13, "normal"),
                     fg_color="white", border_color=COLORS["border"], width=200, height=34,
                     placeholder_text="如 llava:13b").pack(side="left", padx=(12, 8))
        self.model_dl_btn = ctk.CTkButton(dl_row, text="下载", command=self._download_model,
                                          **primary_button_style())
        self.model_dl_btn.pack(side="left")

        # 下载进度
        self.model_dl_progress = ctk.CTkProgressBar(card, progress_color=COLORS["primary"],
                                                    fg_color=COLORS["border_light"], height=6)
        self.model_dl_progress.set(0)
        self.model_dl_progress.pack(fill="x", padx=24, pady=(0, 8))
        self.model_dl_status_var = ctk.StringVar(value="")
        ctk.CTkLabel(card, textvariable=self.model_dl_status_var, font=font_safe(12, "normal"),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=24)

        # 推荐模型列表
        rec_frame = ctk.CTkFrame(card, fg_color=COLORS["bg"], corner_radius=8,
                                 border_color=COLORS["border"], border_width=1)
        rec_frame.pack(fill="x", padx=24, pady=(12, 12))
        rec_hdr = ctk.CTkFrame(rec_frame, fg_color="transparent")
        rec_hdr.pack(fill="x", padx=12, pady=(10, 6))
        ctk.CTkLabel(rec_hdr, text="推荐模型", font=font_safe(13, "bold"),
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(rec_hdr, text="🔍 检测本地模型", width=120, height=26,
                      command=self._detect_local_models,
                      font=font_safe(11),
                      corner_radius=12,
                      fg_color=COLORS["card"],
                      hover_color=COLORS["hover"],
                      text_color=COLORS["text"],
                      border_color=COLORS["border"],
                      border_width=1).pack(side="right")

        recommended = [
            ("moondream", "视觉模型", "轻量首选 · 1.9GB · 适合大批量快速分类"),
            ("gemma3:4b", "视觉模型", "平衡之选 · 2.5GB · Google 多模态 · 中文不错"),
            ("llava:7b", "视觉模型", "质量之选 · 4.7GB · 分类最准但较重"),
            ("minicpm-v:8b", "视觉模型", "国产之光 · 5.5GB · 中文 OCR 最强"),
            ("qwen2.5:3b", "文本模型", "智能助手 · 1.9GB · 文案/翻译/总结"),
        ]

        for name, tag, desc in recommended:
            row = ctk.CTkFrame(rec_frame, fg_color="transparent", height=36)
            row.pack(fill="x", padx=8, pady=(0, 2))
            row.pack_propagate(False)

            tag_color = COLORS["success"] if tag == "视觉模型" else COLORS["warning"]
            ctk.CTkLabel(row, text=tag, font=font_safe(9, "bold"),
                         fg_color=tag_color, text_color="white",
                         corner_radius=3, padx=5, pady=1).pack(side="left", padx=(4, 6))
            ctk.CTkLabel(row, text=name, font=font_safe(12, "bold"),
                         text_color=COLORS["text"], width=100).pack(side="left")
            ctk.CTkLabel(row, text=desc, font=font_safe(11),
                         text_color=COLORS["text_secondary"]).pack(side="left", padx=(4, 0))
            ctk.CTkButton(row, text="下载", width=50, height=26,
                          command=lambda n=name: self._quick_download_model(n),
                          font=font_safe(11),
                          corner_radius=12,
                          fg_color=COLORS["card"],
                          hover_color=COLORS["hover"],
                          text_color=COLORS["text"],
                          border_color=COLORS["border"],
                          border_width=1).pack(side="right", padx=(0, 4))

        # 增强组件安装
        enh_frame = ctk.CTkFrame(card, fg_color=COLORS["bg"], corner_radius=8,
                                 border_color=COLORS["border"], border_width=1)
        enh_frame.pack(fill="x", padx=24, pady=(0, 12))
        ctk.CTkLabel(enh_frame, text="增强组件", font=font_safe(13, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=12, pady=(10, 4))
        ctk.CTkLabel(enh_frame, text="安装后自动启用，无需配置。未安装时回退到基础模式。",
                     font=font_safe(11), text_color=COLORS["text_secondary"]).pack(anchor="w", padx=12, pady=(0, 6))

        enhancements = [
            ("CLIP 语义搜索", "sentence-transformers faiss-cpu", "以文搜图快 100 倍，准 3-5 倍"),
            ("VTracer 矢量引擎", "vtracer", "位图转矢量色彩保真度大幅提升"),
        ]

        for name, pkg, desc in enhancements:
            row = ctk.CTkFrame(enh_frame, fg_color="transparent", height=36)
            row.pack(fill="x", padx=8, pady=(0, 2))
            row.pack_propagate(False)
            ctk.CTkLabel(row, text=name, font=font_safe(12, "bold"),
                         text_color=COLORS["text"], width=120).pack(side="left", padx=(4, 0))
            ctk.CTkLabel(row, text=desc, font=font_safe(11),
                         text_color=COLORS["text_secondary"]).pack(side="left", padx=(4, 0))
            installed = self._check_enhancement(pkg)
            if installed:
                ctk.CTkLabel(row, text="已安装", font=font_safe(10, "bold"),
                             text_color=COLORS["success"]).pack(side="right", padx=(0, 4))
            else:
                ctk.CTkButton(row, text="安装", width=50, height=26,
                              command=lambda p=pkg: self._install_enhancement(p),
                              font=font_safe(11),
                              corner_radius=12,
                              fg_color=COLORS["card"],
                              hover_color=COLORS["hover"],
                              text_color=COLORS["text"],
                              border_color=COLORS["border"],
                              border_width=1).pack(side="right", padx=(0, 4))

        # 已安装模型列表
        self.installed_models_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.installed_models_frame.pack(fill="x", padx=24, pady=(8, 20))
        ctk.CTkLabel(self.installed_models_frame, text="已安装模型",
                     font=font_safe(13, "bold"), text_color=COLORS["text"]).pack(anchor="w")

    def _refresh_installed_models(self):
        for w in self.installed_models_frame.winfo_children():
            if w != self.installed_models_frame.winfo_children()[0] if self.installed_models_frame.winfo_children() else None:
                pass
        # 清除旧列表（保留标题）
        children = list(self.installed_models_frame.winfo_children())
        if children:
            # 保留第一个（标题），删除其余
            for w in children[1:]:
                w.destroy()

        def _load():
            try:
                models = fetch_all_models()
                self.app.root.after(0, lambda: self._show_installed_models(models))
            except Exception:
                self.app.root.after(0, lambda: self._show_installed_models(["无法获取模型列表"]))
        threading.Thread(target=_load, daemon=True).start()

    def _show_installed_models(self, models):
        # 再删一次，确保干净
        for w in self.installed_models_frame.winfo_children()[1:]:
            w.destroy()

        for m in models:
            row = ctk.CTkFrame(self.installed_models_frame, fg_color=COLORS["bg"], corner_radius=6, height=40)
            row.pack(fill="x", pady=(0, 4))
            row.pack_propagate(False)

            tag = get_model_role_tag(m)
            tag_color = COLORS["success"] if tag == "视觉模型" else COLORS["warning"]
            ctk.CTkLabel(row, text=tag, font=font_safe(10, "bold"),
                         fg_color=tag_color, text_color="white",
                         corner_radius=4, padx=6, pady=2).pack(side="left", padx=(8, 8))
            ctk.CTkLabel(row, text=m, font=font_safe(13, "normal"),
                        text_color=COLORS["text"]).pack(side="left")
            ctk.CTkLabel(row, text=get_model_hint(m), font=font_safe(11, "normal"),
                        text_color=COLORS["text_secondary"]).pack(side="left", padx=(12, 0))
            ctk.CTkButton(row, text="删除", width=50, height=24,
                          command=lambda mn=m: self._delete_model(mn),
                          fg_color=COLORS["danger"], hover_color="#E6352B",
                          text_color="white", font=font_safe(11, "normal")).pack(
                              side="right", padx=(0, 8))

    def _download_model(self):
        model_name = self.model_dl_var.get().strip()
        if not model_name:
            messagebox.showwarning("输入为空", "请输入模型名称，如 llava:13b")
            return

        self.model_dl_btn.configure(state="disabled")
        self.model_dl_progress.set(0)
        self.model_dl_status_var.set(f"正在下载 {model_name}...")

        def _dl():
            try:
                with requests.post(f"{DEFAULT_URL}/api/pull",
                                   json={"name": model_name, "stream": True},
                                   stream=True, timeout=1200) as r:
                    if r.status_code != 200:
                        self.app.root.after(0, lambda: self._on_model_downloaded(False, f"HTTP {r.status_code}"))
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
                                    self.app.root.after(0, lambda p=pct: self.model_dl_progress.set(p))
                                    self.app.root.after(0, lambda s=status:
                                        self.model_dl_status_var.set(f"{s} ({completed}/{total})"))
                            elif status:
                                self.app.root.after(0, lambda s=status:
                                    self.model_dl_status_var.set(s))
                        except Exception:
                            pass

                self.app.root.after(0, lambda: self._on_model_downloaded(True, model_name))
            except Exception as e:
                self.app.root.after(0, lambda: self._on_model_downloaded(False, str(e)))

        threading.Thread(target=_dl, daemon=True).start()

    def _on_model_downloaded(self, success, info):
        self.model_dl_btn.configure(state="normal")
        if success:
            self.model_dl_progress.set(1)
            self.model_dl_status_var.set(f"✅ {info} 下载完成")
            self._refresh_installed_models()
            messagebox.showinfo("下载完成", f"模型 {info} 已安装")
        else:
            self.model_dl_status_var.set(f"❌ 下载失败：{info}")
            messagebox.showerror("下载失败", f"无法下载模型：{info}")

    def _quick_download_model(self, name):
        """一键下载推荐模型。"""
        self.model_dl_var.set(name)
        self._download_model()

    def _check_enhancement(self, pkg_str):
        """检查增强组件是否已安装。"""
        for pkg in pkg_str.split():
            try:
                __import__(pkg.replace("-", "_").split("=")[0])
            except ImportError:
                return False
        return True

    def _install_enhancement(self, pkg_str):
        """一键安装增强组件。"""
        if not messagebox.askyesno("安装增强组件",
            f"将执行：\npip install {pkg_str}\n\n可能需要几分钟，确定继续？"):
            return

        import subprocess
        import sys

        def _run():
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install"] + pkg_str.split(),
                    capture_output=True, text=True, timeout=300
                )
                def _done():
                    if result.returncode == 0:
                        messagebox.showinfo("安装成功",
                            f"已安装 {pkg_str}\n重启应用后生效。")
                    else:
                        messagebox.showerror("安装失败",
                            f"pip install 失败：\n{result.stderr[:500]}")
                self.app.root.after(0, _done)
            except Exception as e:
                self.app.root.after(0, lambda:
                    messagebox.showerror("安装失败", str(e)))

        threading.Thread(target=_run, daemon=True).start()

    def _detect_local_models(self):
        """检测本地已有的模型（Ollama + GGUF 文件 + LM Studio）。"""
        self.model_dl_status_var.set("正在检测本地模型...")

        def _detect():
            results = []

            # 1. 检查 Ollama 已安装的模型
            try:
                resp = requests.get(f"{DEFAULT_URL}/api/tags", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    if models:
                        results.append(("Ollama 已安装", models))
                    else:
                        results.append(("Ollama", ["未安装任何模型"]))
                else:
                    results.append(("Ollama", ["未运行或未安装"]))
            except Exception:
                results.append(("Ollama", ["未运行（请先启动 Ollama）"]))

            # 2. 检查常见 GGUF 文件位置
            import glob
            home = os.path.expanduser("~")
            gguf_paths = [
                os.path.join(home, ".ollama", "models"),
                os.path.join(home, ".cache", "lm-studio", "models"),
                os.path.join(home, "Library", "Application Support", "LM Studio", "models"),
            ]
            gguf_files = []
            for base in gguf_paths:
                if os.path.exists(base):
                    for f in glob.glob(os.path.join(base, "**", "*.gguf"), recursive=True):
                        size_mb = os.path.getsize(f) / (1024 * 1024)
                        gguf_files.append(f"{os.path.basename(f)} ({size_mb:.0f}MB)")

            if gguf_files:
                results.append(("GGUF 模型文件", gguf_files[:10]))
            else:
                results.append(("GGUF 模型文件", ["未找到"]))

            # 3. 检查增强组件
            try:
                import sentence_transformers
                results.append(("CLIP 语义搜索", ["已安装"]))
            except ImportError:
                results.append(("CLIP 语义搜索", ["未安装"]))

            try:
                import vtracer
                results.append(("VTracer 矢量引擎", ["已安装"]))
            except ImportError:
                results.append(("VTracer 矢量引擎", ["未安装"]))

            def _show():
                self.model_dl_status_var.set("检测完成")
                dialog = ctk.CTkToplevel(self)
                dialog.title("本地模型检测结果")
                dialog.geometry("500x400")
                dialog.transient(self)

                frm = ctk.CTkScrollableFrame(dialog, fg_color=COLORS["bg"])
                frm.pack(fill="both", expand=True, padx=16, pady=16)

                ctk.CTkLabel(frm, text="本地环境检测", font=font_safe(16, "bold"),
                             text_color=COLORS["text"]).pack(anchor="w", pady=(0, 12))

                for category, items in results:
                    ctk.CTkLabel(frm, text=category, font=font_safe(13, "bold"),
                                 text_color=COLORS["primary"]).pack(anchor="w", pady=(8, 2))
                    for item in items:
                        icon = "✅" if "已安装" in item or "已" in item else "•"
                        if "未" in item:
                            icon = "❌"
                        ctk.CTkLabel(frm, text=f"  {icon} {item}", font=font_safe(12),
                                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=8)

                ctk.CTkButton(frm, text="关闭", command=dialog.destroy,
                              **secondary_button_style()).pack(anchor="w", pady=(12, 0))

            self.app.root.after(0, _show)

        threading.Thread(target=_detect, daemon=True).start()

    def _delete_model(self, model_name):
        if not messagebox.askyesno("确认删除", f"确定删除模型 {model_name}？此操作不可恢复。"):
            return
        try:
            r = requests.delete(f"{DEFAULT_URL}/api/delete", json={"name": model_name}, timeout=10)
            if r.status_code == 200:
                self._refresh_installed_models()
                messagebox.showinfo("已删除", f"模型 {model_name} 已删除")
            else:
                messagebox.showerror("删除失败", f"无法删除模型：HTTP {r.status_code}")
        except Exception as e:
            messagebox.showerror("错误", str(e))

    # ── 输出选项 ──
    def _build_output_section(self):
        card = ctk.CTkFrame(self.scroll_frame, **card_frame_style())
        card.pack(fill="x", padx=32, pady=(8, 16))

        ctk.CTkLabel(card, text="⚙️ 输出选项", font=font_safe(18, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=24, pady=(20, 12))

        out_cfg = self.app.config_manager.get("output", {})
        self.gen_report_var = ctk.BooleanVar(value=out_cfg.get("generate_report", True))
        ctk.CTkCheckBox(card, text="分类完成后生成 CSV 报告", variable=self.gen_report_var,
                        font=font_safe(13), text_color=COLORS["text"],
                        fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]).pack(
                            anchor="w", padx=24, pady=(0, 10))

        self.low_conf_var = ctk.BooleanVar(value=out_cfg.get("low_confidence_review", True))
        ctk.CTkCheckBox(card, text="低置信度图片进入「待复核」文件夹", variable=self.low_conf_var,
                        font=font_safe(13), text_color=COLORS["text"],
                        fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]).pack(
                            anchor="w", padx=24, pady=(0, 10))

        # 文件处理方式
        mode_row = ctk.CTkFrame(card, fg_color="transparent")
        mode_row.pack(fill="x", padx=24, pady=(0, 10))
        ctk.CTkLabel(mode_row, text="文件处理方式", font=font_safe(13),
                     text_color=COLORS["text_secondary"]).pack(side="left")
        self.file_mode_var = ctk.StringVar(
            value="移动" if out_cfg.get("file_mode", "copy") == "move" else "复制")
        ctk.CTkSegmentedButton(mode_row, variable=self.file_mode_var,
                               values=["复制", "移动"],
                               font=font_safe(12),
                               selected_color=COLORS["primary"],
                               selected_hover_color=COLORS["primary_hover"],
                               unselected_color=COLORS["card"]).pack(side="left", padx=(12, 0))
        ctk.CTkLabel(mode_row, text="移动=分类后删除原始文件", font=font_safe(11),
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(8, 0))

        # 置信度阈值
        thresh_row = ctk.CTkFrame(card, fg_color="transparent")
        thresh_row.pack(fill="x", padx=24, pady=(0, 20))
        ctk.CTkLabel(thresh_row, text="置信度阈值", font=font_safe(13),
                     text_color=COLORS["text_secondary"]).pack(side="left")
        self.conf_thresh_var = ctk.StringVar(value=str(self.app.config_manager.get("confidence_threshold", 0.6)))
        ctk.CTkEntry(thresh_row, textvariable=self.conf_thresh_var, width=60, height=30,
                     font=font_safe(13)).pack(side="left", padx=(8, 0))

    # ── 保存 ──
    def _save_all(self):
        # 分类
        categories = {}
        for name_entry, desc_entry in self.category_widgets:
            name = name_entry.get().strip()
            desc = desc_entry.get().strip()
            if name:
                categories[name] = desc
        self.app.config_manager.set("categories", categories)

        # 输出
        output_cfg = self.app.config_manager.get("output", {})
        output_cfg["generate_report"] = self.gen_report_var.get()
        output_cfg["low_confidence_review"] = self.low_conf_var.get()
        output_cfg["file_mode"] = "move" if self.file_mode_var.get() == "移动" else "copy"
        self.app.config_manager.set("output", output_cfg)

        # 置信度
        try:
            self.app.config_manager.set("confidence_threshold", float(self.conf_thresh_var.get()))
        except ValueError:
            pass

        # 人物识别开关（known_persons 在添加/编辑时已保存）
        self.app.config_manager.set("person_recognition", self.person_recog_var.get())

        # 地点识别开关（known_places 在添加/编辑时已保存）
        self.app.config_manager.set("place_recognition", self.place_recog_var.get())

        # 规则已在添加/编辑时保存

        messagebox.showinfo("保存成功", "所有设置已保存")
