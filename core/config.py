#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置管理"""
import os
import json
from pathlib import Path

DEFAULT_CONFIG = {
    "categories": {
        "工厂图": "工厂厂房、仓库、生产线、机械设备、工业场景、车间、制造现场",
        "人物肖像图": "负责人个人肖像、负责人特写、负责人形象照、个人品牌照片、负责人单人照",
        "本地风景图": "澳大利亚自然风景、海滩、城市天际线、地标建筑、本地户外、悉尼歌剧院、海岸",
        "办公室图": "办公室内景、办公桌、会议室、办公环境、公司前台、办公空间",
        "合作洽谈图": "两人或以上会面、握手、签约、商务洽谈、交流讨论、会议场景"
    },
    "model": "llava:13b",
    "confidence_threshold": 0.6,
    "supported_exts": [".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bmp", ".tiff", ".gif"],
    "incremental": True,
    "report_format": "csv",
    "theme": "light",
    "last_input": "",
    "last_output": "",
    "rules": [],
    "output": {
        "keep_original_name": True,
        "handle_duplicates": "rename",
        "generate_report": True,
        "low_confidence_review": True,
        "file_mode": "copy"
    },
    "event_mode": {
        "rename_pattern": "{date}_{event}_{seq:02d}{grade}_{desc}",
        "event_name_samples": 3,
        "grade_enabled": True,
        "min_grade_for_event": "B",
        "default_model": "llava:13b",
    },
    "story_grades": {
        "A": "人物互动、情感瞬间、关键动作、独特场景",
        "B": "环境交代、背景细节、过渡场景",
        "C": "重复场景、模糊、空镜、文档资料"
    },
    "tag_presets": {
        "默认ABC": {
            "tags": [
                {"name": "A", "desc": "人物互动、情感瞬间、关键动作、独特场景"},
                {"name": "B", "desc": "环境交代、背景细节、过渡场景"},
                {"name": "C", "desc": "重复场景、模糊、空镜、文档资料"}
            ],
            "multi_tag": False,
            "max_tags": 1
        },
        "内容分类": {
            "tags": [
                {"name": "工业", "desc": "工厂、设备、生产线、车间、工业场景"},
                {"name": "人物", "desc": "人物特写、肖像、人物为主体"},
                {"name": "商务", "desc": "会议、签约、洽谈、商务交流"},
                {"name": "风景", "desc": "自然景观、城市风光、户外"},
                {"name": "人文", "desc": "人物生活、文化活动、人文气息"}
            ],
            "multi_tag": True,
            "max_tags": 3
        }
    },
    "active_tag_preset": "默认ABC",
    "business_context": "本地通用业务移民公司，负责人是企业用户，素材用于短视频展示真实雇主实力和本地工作场景。",
    "optimized_prompt": "",
    "min_photos_per_event": 2,
    "known_persons": [],
    "person_recognition": True,
    "known_places": [],
    "place_recognition": True
}


class ConfigManager:
    def __init__(self, config_path=None):
        if config_path is None:
            # 配置文件统一放在 data/ 目录下
            root = Path(__file__).parent.parent
            self.config_path = root / "data" / "snapsort_config.json"
        else:
            self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config = self.load()

    def load(self):
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            # 合并默认值，防止升级后缺字段
            for k, v in DEFAULT_CONFIG.items():
                if k not in config:
                    config[k] = v
                elif isinstance(v, dict) and k in config:
                    for sub_k, sub_v in v.items():
                        if sub_k not in config[k]:
                            config[k][sub_k] = sub_v
            return config
        self.save(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()

    def save(self, config=None):
        if config is None:
            config = self.config
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        self.config = config

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()
