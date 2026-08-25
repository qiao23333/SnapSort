#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""已知对象：用名称、描述和参考照片连接自动分类与图片搜索。"""


DEFAULT_RECOGNITION_TARGETS = [
    {
        "name": "我的常用物品",
        "type": "物品",
        "description": "请改成具体名称，并添加 1–5 张能清楚看到该物品的参考照片",
        "search_query": "",
        "enabled": False,
    },
]

LEGACY_GENERIC_TARGET_NAMES = {"产品与包装", "文件资料", "工作设备"}


def enabled_targets(config):
    if not config.get("recognition_targets_enabled", True):
        return []
    targets = config.get("recognition_targets", []) or []
    return [
        target for target in targets
        if target.get("enabled", True) and str(target.get("name", "")).strip()
    ]


def targets_prompt(targets):
    lines = []
    for target in targets:
        name = str(target.get("name", "")).strip()
        target_type = str(target.get("type", "自定义")).strip() or "自定义"
        description = str(target.get("description", "")).strip()
        line = f"- {name}（{target_type}）"
        if description:
            line += f"：{description}"
        lines.append(line)
    return "\n".join(lines)


def search_presets(config):
    return [
        {
            "name": str(target.get("name", "")).strip(),
            "query": str(target.get("search_query") or target.get("description")
                         or target.get("name", "")).strip(),
        }
        for target in enabled_targets(config)
    ]
