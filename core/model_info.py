#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模型角色说明：用于在 UI 各选择框旁显示模型用途。"""

# 模型前缀到用途说明的映射
MODEL_HINTS = {
    # ── 视觉模型（能看图）──
    "llava": "视觉模型 · 图片分类、描述、问答，分类主力模型",
    "bakllava": "视觉模型 · Llama架构，分类与描述效果好",
    "moondream": "视觉模型 · 轻量快速，适合大批量快速分类",
    "cogvlm": "视觉模型 · 中文理解较好，适合国内场景",
    "minicpm-v": "视觉模型 · 轻量多模态，适合移动端",
    "qwen-vl": "视觉模型 · 通义千问视觉版，中文场景友好",
    "qwen2-vl": "视觉模型 · 通义千问2代视觉版",
    "qwen2.5-vl": "视觉模型 · 通义千问2.5代视觉版",
    "yi-vl": "视觉模型 · 零一万物视觉模型",
    "deepseek-vl": "视觉模型 · DeepSeek视觉模型",
    "internvl": "视觉模型 · 书生视觉模型",
    "llama3.2-vision": "视觉模型 · Llama3.2视觉版",
    "gemma3": "视觉模型 · Google Gemma3多模态",
    "phi3-vision": "视觉模型 · 微软Phi-3视觉版",
    "granite3.2-vision": "视觉模型 · IBM Granite视觉版",

    # ── 纯文本模型（不能看图，但能处理文字）──
    "qwen2.5": "文本模型 · 智能助手(文案/翻译/总结)，不能看图但文字能力强",
    "qwen2": "文本模型 · 智能助手(文案/翻译/总结)",
    "qwen": "文本模型 · 智能助手(文案/翻译/总结)",
    "phi": "文本模型 · 轻量对话，适合简单文案",
    "phi3": "文本模型 · 微软Phi-3，轻量对话",
    "mistral": "文本模型 · 通用对话与文案",
    "llama3": "文本模型 · Meta Llama3，通用对话",
    "llama": "文本模型 · 通用对话与文案",
    "gemma": "文本模型 · Google Gemma，轻量",
    "gemma2": "文本模型 · Google Gemma2",
    "deepseek": "文本模型 · DeepSeek，推理能力强",
    "codellama": "文本模型 · 代码生成专用",
    "yi": "文本模型 · 零一万物，中文友好",
}


def get_model_hint(model_name: str) -> str:
    """根据模型名称返回一句用途说明。"""
    if not model_name:
        return "未知模型"
    name_lower = model_name.lower()
    # 先检查视觉模型（更具体的匹配优先）
    for prefix, hint in MODEL_HINTS.items():
        if prefix in name_lower:
            return hint
    return "本地大模型"


def is_vision_model(model_name: str) -> bool:
    """判断模型是否为视觉模型（可用于看图/分类/描述）。"""
    if not model_name:
        return False
    vision_prefixes = [
        "llava", "bakllava", "moondream", "cogvlm", "minicpm-v",
        "qwen-vl", "qwen2-vl", "qwen2.5-vl", "yi-vl", "deepseek-vl",
        "internvl", "llama3.2-vision", "gemma3", "phi3-vision",
        "granite3.2-vision", "paligemma", "obsidian"
    ]
    name_lower = model_name.lower()
    # 注意：qwen2.5 (不带-vl) 不是视觉模型，但 qwen2.5-vl 是
    # 所以先检查 -vl 后缀
    if "-vl" in name_lower or "vl:" in name_lower or name_lower.endswith("vl"):
        return True
    return any(p in name_lower for p in vision_prefixes)


def is_text_model(model_name: str) -> bool:
    """判断模型是否为纯文本模型（不能看图，但能处理文字）。"""
    return bool(model_name) and not is_vision_model(model_name)


def get_model_role_tag(model_name: str) -> str:
    """返回简短角色标签：视觉 / 文本 / 未知"""
    if is_vision_model(model_name):
        return "视觉模型"
    if model_name:
        return "文本模型"
    return "未知"


def get_model_usage_guide(model_name: str) -> str:
    """返回模型在各功能中的适用说明（用于 UI 提示）"""
    if is_vision_model(model_name):
        return ("✅ 自动分类  ✅ 以文搜图  ✅ 图片描述  ✅ 图片问答  "
                "❌ 智能助手(可用但非最佳)  ✅ 重复检测(不需要模型)")
    elif model_name:
        return ("❌ 自动分类(需要视觉)  ❌ 以文搜图(需要视觉)  ❌ 图片描述(需要视觉)  "
                "❌ 图片问答(需要视觉)  ✅ 智能助手  ✅ 重复检测(不需要模型)")
    return ""
