#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""照片分类引擎：Ollama + LLaVA 本地视觉模型"""
import os
import json
import time
import shutil
from datetime import datetime
from pathlib import Path

import requests

from core.image_utils import encode_image, is_image_file
from core.report import generate_csv_report
from core.history import HistoryManager
from core.rule_engine import RuleEngine
from core import reference_manager as ref_mgr


DEFAULT_URL = "http://localhost:11434"
# 已知视觉模型前缀（用于照片分类时筛选）
VISION_KEYWORDS = [
    "llava", "llava-", "bakllava", "moondream", "cogvlm",
    "yi-vl", "deepseek-vl", "qwen-vl", "qwen2.5-vl", "qwen2-vl",
    "internvl", "minicpm-v", "minicpm-llava", "paligemma",
    "granite3.2-vision", "llama3.2-vision", "phi3-vision",
    "obsidian", "x/llama3.2-vision", "gemma3"
]

# 纯文本模型前缀（非视觉，但在 AI 工具箱中可用）
TEXT_MODEL_KEYWORDS = [
    "qwen", "qwen2", "qwen2.5", "llama", "llama2", "llama3",
    "mistral", "gemma", "gemma2", "phi", "phi3", "deepseek",
    "codellama", "starcoder", "wizard", "yi", "falcon", "command"
]


def optimize_prompt(business_context, model, url=DEFAULT_URL):
    """用 AI 将业务背景优化为结构化分类提示词。

    用户输入粗略的业务背景 → AI 生成详细的分类提示词 → 保存后用于实际分类。
    返回 (success, optimized_prompt)。
    """
    if not business_context.strip():
        return False, "业务背景为空"

    meta_prompt = (
        "你是一个图片分类系统的提示词优化器。\n"
        "用户会给你一段业务背景描述，你需要将其优化为一条详细的、结构化的图片分析提示词。\n\n"
        f"用户的业务背景：{business_context}\n\n"
        "请生成一条优化后的提示词，要求：\n"
        "1. 明确告诉 AI 应该关注图片中的哪些要素（场景、人物、活动、氛围等）\n"
        "2. 结合业务背景给出具体的分类指引（什么算工厂图、什么算负责人IP图等）\n"
        "3. 要求 AI 按结构化格式回复（SCENE/DESC/PEOPLE/ACTION/MOOD）\n"
        "4. 控制在 200 字以内\n\n"
        "只输出优化后的提示词，不要解释。"
    )

    try:
        r = requests.post(f"{url}/api/generate", json={
            "model": model,
            "prompt": meta_prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 300}
        }, timeout=60)
        if r.status_code == 200:
            result = r.json().get("response", "").strip()
            return True, result
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)


def check_ollama(url=DEFAULT_URL):
    try:
        r = requests.get(f"{url}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def fetch_ollama_models(url=DEFAULT_URL):
    """获取 Ollama 中已安装的视觉模型列表（用于照片分类）"""
    try:
        r = requests.get(f"{url}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            vision_models = [m for m in models if any(k in m.lower() for k in VISION_KEYWORDS)]
            if vision_models:
                return vision_models
    except Exception:
        pass
    return ["llava:7b", "llava:13b", "bakllava", "moondream"]


def fetch_all_models(url=DEFAULT_URL):
    """获取 Ollama 中已安装的所有模型列表（用于 AI 工具箱等需要文字模型的场景）"""
    try:
        r = requests.get(f"{url}/api/tags", timeout=5)
        if r.status_code == 200:
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


def ensure_model(model_name, url=DEFAULT_URL, log_callback=None):
    """确保模型已下载，返回 (success, info)"""
    def log(msg):
        if log_callback:
            log_callback(msg, "INFO")

    try:
        r = requests.get(f"{url}/api/tags", timeout=10)
        models = [m["name"] for m in r.json().get("models", [])]
        if model_name in models:
            return True, model_name
        # 模糊匹配，例如 llava:13b 可匹配 llava:13b-latest
        base = model_name.split(":")[0]
        for m in models:
            if m.startswith(base):
                return True, m

        log(f"正在下载模型 {model_name}，请耐心等待...")
        r = requests.post(f"{url}/api/pull", json={"name": model_name}, stream=True, timeout=600)
        for line in r.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if data.get("status") == "success":
                        return True, model_name
                except Exception:
                    pass
        return True, model_name
    except Exception as e:
        return False, str(e)


def build_keywords_map(categories):
    """根据分类配置生成关键词映射（硬编码 + 配置描述）"""
    # 基础关键词，可覆盖
    base_keywords = {
        "工厂图": ["工厂", "厂房", "仓库", "生产线", "机械", "设备", "工业", "车间", "制造",
                   "factory", "warehouse", "industrial", "manufacturing", "plant"],
        "人物肖像图": ["负责人", "肖像", "特写", "个人照", "形象照", "单人", "创始人",
                         "portrait", "ceo", "founder", "headshot"],
        "本地风景图": ["本地", "澳大利亚", "悉尼", "墨尔本", "海滩", "海岸", "歌剧院",
                     "australia", "sydney", "melbourne", "beach", "landscape", "opera house"],
        "办公室图": ["办公室", "办公", "会议室", "前台", "办公桌", "工位",
                   "office", "meeting room", "desk", "workspace"],
        "合作洽谈图": ["洽谈", "签约", "握手", "会议", "交流", "会面", "合作", "团队",
                     "meeting", "handshake", "sign", "business", "discussion"]
    }

    # 把配置描述中的关键词也加入
    keywords_map = {}
    for cat, desc in categories.items():
        kws = list(base_keywords.get(cat, []))
        if desc:
            kws.extend([d.strip() for d in desc.split("。") if d.strip()])
            kws.extend([d.strip() for d in desc.split("、") if d.strip()])
        keywords_map[cat] = list(dict.fromkeys(kws))  # 去重
    return keywords_map


def match_category(desc, keywords_map):
    """根据描述匹配最相关类别"""
    desc_lower = desc.lower()
    best_match = "其他"
    max_score = 0

    for cat, kws in keywords_map.items():
        score = sum(1 for kw in kws if kw in desc or kw in desc_lower)
        if score > max_score:
            max_score = score
            best_match = cat

    return best_match, max_score


def classify_image(image_path, config, url=DEFAULT_URL, log_callback=None):
    """调用本地视觉模型获取描述并分类，返回 (category, score, reason, persons, places)。

    若配置了 known_persons/known_places 且对应识别开启：
    - 有参考照片时，将目标图 + 参考照片一起发送，让模型视觉比对识别
    - 无参考照片时，退化为文字描述提示
    persons / places 为检测到的名称列表（可能为空）。
    """
    categories = config.get("categories", {})
    keywords_map = build_keywords_map(categories)
    known_persons = config.get("known_persons", []) or []
    known_places = config.get("known_places", []) or []
    person_recognition = config.get("person_recognition", True)
    place_recognition = config.get("place_recognition", True)

    # ── 收集参考照片 ──
    # 格式: [(name, [img_path, ...]), ...]
    person_refs = []   # 有参考照片的人物
    person_text = []   # 仅有文字描述的人物（无参考照片）
    for p in known_persons:
        name = p.get("name", "").strip()
        if not name:
            continue
        refs = ref_mgr.get_reference_images_for_call("person", name)
        if refs:
            person_refs.append((name, refs))
        else:
            person_text.append(p)

    place_refs = []
    place_text = []
    for pl in known_places:
        name = pl.get("name", "").strip()
        if not name:
            continue
        refs = ref_mgr.get_reference_images_for_call("place", name)
        if refs:
            place_refs.append((name, refs))
        else:
            place_text.append(pl)

    use_person = person_recognition and (person_refs or person_text)
    use_place = place_recognition and (place_refs or place_text)

    # ── 构建图片列表和 prompt ──
    try:
        target_b64 = encode_image(image_path)
    except Exception as e:
        return "错误", 0.0, f"图片编码失败：{e}", [], []

    images = [target_b64]           # 第 1 张 = 待分类照片
    img_labels = ["第1张：待分类照片"]

    # 添加人物参考照片
    for name, refs in person_refs:
        for rp in refs:
            try:
                rb64 = encode_image(rp)
                images.append(rb64)
                idx = len(images)
                img_labels.append(f"第{idx}张：人物「{name}」的参考照片")
            except Exception:
                pass

    # 添加地点参考照片
    for name, refs in place_refs:
        for rp in refs:
            try:
                rb64 = encode_image(rp)
                images.append(rb64)
                idx = len(images)
                img_labels.append(f"第{idx}张：地点「{name}」的参考照片")
            except Exception:
                pass

    # ── 构建 prompt ──
    has_refs = len(images) > 1

    # 优先使用优化后的提示词
    optimized = config.get("optimized_prompt", "")
    if optimized and optimized.strip():
        prompt = optimized.strip() + "\n\n"
        prompt += "严格按以下格式回复（每项一行，不要额外文字）：\n"
        prompt += "SCENE: 场景类型(工厂/办公室/户外/会议/社交/其他)\n"
        prompt += "DESC: 详细描述(15-30字)\n"
        prompt += "PEOPLE: 人数及身份(如：3人/1男性负责人/无)\n"
        prompt += "ACTION: 主要活动(如：签约/参观/用餐/合影)\n"
        prompt += "MOOD: 氛围(正式/轻松/严肃)\n"
    else:
        prompt = "请分析这张图片，严格按以下格式回复（每项一行，不要额外文字）：\n"
        prompt += "SCENE: 场景类型(工厂/办公室/户外/会议/社交/其他)\n"
        prompt += "DESC: 详细描述(15-30字)\n"
        prompt += "PEOPLE: 人数及身份(如：3人/1男性负责人/无)\n"
        prompt += "ACTION: 主要活动(如：签约/参观/用餐/合影)\n"
        prompt += "MOOD: 氛围(正式/轻松/严肃)\n"

    if has_refs:
        prompt += "\n以下是图片列表：\n" + "\n".join(img_labels) + "\n"
        prompt += "\n请对比第1张待分类照片与后续参考照片，识别其中出现的已知人物和已知地点。\n"

    if use_person:
        prompt += "PERSONS: 出现的已知人物名字，逗号分隔，没有写\"无\"\n"
        if person_refs:
            ref_names = "、".join(n for n, _ in person_refs)
            prompt += f"  有参考照片的人物：{ref_names}\n"
        if person_text:
            lines = []
            for p in person_text:
                name = p.get("name", "").strip()
                desc = p.get("description", "").strip()
                if name:
                    lines.append(f"  - {name}：{desc}" if desc else f"  - {name}")
            if lines:
                prompt += "  仅有文字描述的人物：\n" + "\n".join(lines) + "\n"

    if use_place:
        prompt += "PLACES: 出现的已知地点名字，逗号分隔，没有写\"无\"\n"
        if place_refs:
            ref_names = "、".join(n for n, _ in place_refs)
            prompt += f"  有参考照片的地点：{ref_names}\n"
        if place_text:
            lines = []
            for pl in place_text:
                name = pl.get("name", "").strip()
                desc = pl.get("description", "").strip()
                if name:
                    lines.append(f"  - {name}：{desc}" if desc else f"  - {name}")
            if lines:
                prompt += "  仅有文字描述的地点：\n" + "\n".join(lines) + "\n"

    if not use_person and not use_place:
        prompt += "1. 图片中有什么场景/物体/人物；2. 有多少人在做什么；3. 地点类型。请用中文回答，不超过50字。"

    payload = {
        "model": config.get("model", "llava:7b"),
        "prompt": prompt,
        "images": images,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 150}
    }

    try:
        r = requests.post(f"{url}/api/generate", json=payload, timeout=300)
        if r.status_code == 200:
            resp = r.json().get("response", "").strip()
            desc, persons, places = _parse_classify_response(
                resp, known_persons, known_places,
                person_recognition and use_person,
                place_recognition and use_place)
            category, score = match_category(desc, keywords_map)
            # 改进置信度：三维加权（关键词 0.4 + 分类匹配 0.3 + 描述长度 0.3）
            kw_conf = min(0.4, score * 0.08)
            cat_conf = 0.3 if category != "其他" else 0.0
            desc_conf = min(0.3, len(desc) / 100 * 0.3)
            confidence = round(kw_conf + cat_conf + desc_conf, 2)
            return category, confidence, desc, persons, places
        else:
            from core.logger import get_logger
            get_logger().warning("分类 HTTP 错误 %s: %s", r.status_code, os.path.basename(image_path))
            return "错误", 0.0, f"HTTP {r.status_code}", [], []
    except Exception as e:
        from core.logger import get_logger
        get_logger().warning("分类失败(降级为待复核) %s: %s", os.path.basename(image_path), e)
        return "错误", 0.0, str(e), [], []


def _parse_classify_response(resp, known_persons, known_places, person_on, place_on):
    """从模型回复中解析结构化字段。兼容旧式纯描述回复。

    Returns:
        (desc, persons, places)
    """
    desc = resp
    persons = []
    places = []

    # 收集所有结构化字段
    fields = {}
    if "DESC:" in resp or "PERSONS:" in resp or "PLACES:" in resp or "SCENE:" in resp:
        for line in resp.split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue
            key = line.split(":", 1)[0].strip().upper()
            val = line.split(":", 1)[1].strip()
            fields[key] = val

        # 构建增强描述：SCENE + DESC + PEOPLE + ACTION
        parts = []
        if fields.get("SCENE") and fields["SCENE"] != "其他":
            parts.append(fields["SCENE"])
        if fields.get("DESC"):
            desc = fields["DESC"]
            parts.append(desc)
        else:
            parts.append(desc)
        if fields.get("PEOPLE") and fields["PEOPLE"] != "无":
            parts.append(fields["PEOPLE"])
        if fields.get("ACTION") and fields["ACTION"] != "无":
            parts.append(fields["ACTION"])

        # 增强描述用于关键词匹配
        desc = " ".join(parts[:4])

        # 解析人物
        if person_on and fields.get("PERSONS"):
            raw = fields["PERSONS"]
            if raw and raw != "无":
                names = [n.strip() for n in raw.replace("，", ",").split(",") if n.strip()]
                valid = {p.get("name", "").strip() for p in known_persons}
                persons = [n for n in names if n in valid] or names[:3]

        # 解析地点
        if place_on and fields.get("PLACES"):
            raw = fields["PLACES"]
            if raw and raw != "无":
                names = [n.strip() for n in raw.replace("，", ",").split(",") if n.strip()]
                valid = {p.get("name", "").strip() for p in known_places}
                places = [n for n in names if n in valid] or names[:3]

    return desc, persons, places


def classify_image_with_retry(image_path, config, url=DEFAULT_URL, max_retries=1):
    """带重试的分类，第一次失败后简化 prompt 重试。"""
    result = classify_image(image_path, config, url)
    if result[0] != "错误":
        return result
    # 简化配置重试（去掉人物/地点识别，减轻负载）
    simplified = {**config, "person_recognition": False, "place_recognition": False}
    result = classify_image(image_path, simplified, url)
    return result


def copy_to_person_folder(image_path, person_name, output_base, handle_duplicates="rename"):
    """将含已知人物的照片额外复制到 人物库/{name}/ 子目录。"""
    person_dir = os.path.join(output_base, "人物库")
    os.makedirs(person_dir, exist_ok=True)
    return copy_to_category(image_path, person_name, person_dir, handle_duplicates=handle_duplicates)


def copy_to_place_folder(image_path, place_name, output_base, handle_duplicates="rename"):
    """将含已知地点的照片额外复制到 地点库/{name}/ 子目录。"""
    place_dir = os.path.join(output_base, "地点库")
    os.makedirs(place_dir, exist_ok=True)
    return copy_to_category(image_path, place_name, place_dir, handle_duplicates=handle_duplicates)


def copy_to_category(image_path, category, output_base, handle_duplicates="rename", move=False):
    """复制或移动图片到分类目录，处理重名。move=True 时移动原始文件。"""
    dest_dir = os.path.join(output_base, category)
    os.makedirs(dest_dir, exist_ok=True)

    fname = os.path.basename(image_path)
    dest_path = os.path.join(dest_dir, fname)

    if os.path.exists(dest_path):
        if handle_duplicates == "skip":
            return None
        if handle_duplicates == "overwrite":
            if move:
                shutil.move(image_path, dest_path)
            else:
                shutil.copy2(image_path, dest_path)
            return dest_path
        # rename
        base, ext = os.path.splitext(dest_path)
        i = 1
        while os.path.exists(f"{base}_{i:03d}{ext}"):
            i += 1
        dest_path = f"{base}_{i:03d}{ext}"

    if move:
        shutil.move(image_path, dest_path)
    else:
        shutil.copy2(image_path, dest_path)
    return dest_path


def get_processed_files(output_dir):
    """获取已处理文件名集合（用于增量）"""
    processed = set()
    if not os.path.exists(output_dir):
        return processed
    for root, dirs, files in os.walk(output_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext and ext not in (".csv", ".xlsx", ".json", ".txt"):
                processed.add(f)
    return processed


class SorterEngine:
    """照片分类引擎，支持后台线程运行并通过回调更新 UI"""

    def __init__(self, config, log_callback=None, progress_callback=None,
                 finished_callback=None, stats_callback=None):
        self.config = config
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback
        self.stats_callback = stats_callback
        self._stop = False
        self.history = HistoryManager()

    def log(self, msg, level="INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = {"INFO": "ℹ️", "OK": "✅", "WARN": "⚠️", "ERROR": "❌", "PROGRESS": "⏳"}.get(level, "  ")
        line = f"[{ts}] {prefix} {msg}"
        if self.log_callback:
            self.log_callback(line)

    def stop(self):
        self._stop = True

    def run(self, input_dir, output_dir):
        """执行分类任务"""
        input_dir = os.path.abspath(input_dir)
        output_dir = os.path.abspath(output_dir)

        # 1. 检查 Ollama
        if not check_ollama():
            self.log("无法连接 Ollama，请确保 Ollama 正在运行", "ERROR")
            self.log("Mac: 打开 Ollama 应用；Windows: 运行 ollama serve", "INFO")
            if self.finished_callback:
                self.finished_callback(False, {})
            return

        model = self.config.get("model", "llava:7b")
        ok, info = ensure_model(model, log_callback=self.log_callback)
        if not ok:
            self.log(f"模型加载失败：{info}", "ERROR")
            if self.finished_callback:
                self.finished_callback(False, {})
            return
        self.log(f"模型已就绪：{info}", "OK")

        # 2. 扫描图片（递归扫描子目录）
        image_files = []
        for root, dirs, files in os.walk(input_dir):
            # 跳过输出目录本身（避免处理已分类的结果）
            if root == output_dir:
                dirs[:] = []
                continue
            for f in files:
                path = os.path.join(root, f)
                if is_image_file(path):
                    image_files.append(path)

        if not image_files:
            self.log(f"在 {input_dir} 中没有找到支持的图片文件", "ERROR")
            if self.finished_callback:
                self.finished_callback(False, {})
            return

        # 3. 增量处理
        if self.config.get("incremental", True):
            processed = get_processed_files(output_dir)
            new_files = [f for f in image_files if os.path.basename(f) not in processed]
            skipped = len(image_files) - len(new_files)
            if skipped > 0:
                self.log(f"增量模式：跳过 {skipped} 张已处理图片", "INFO")
            image_files = new_files

        if not image_files:
            self.log("所有图片已处理完毕，没有新图片", "OK")
            if self.finished_callback:
                self.finished_callback(True, {})
            return

        os.makedirs(output_dir, exist_ok=True)
        self.log(f"找到 {len(image_files)} 张新图片，开始分类...", "INFO")
        self.log(f"结果将保存到：{output_dir}", "INFO")

        results = {}
        errors = []
        low_confidence = []
        person_stats = {}          # 人物 → 出现次数
        place_stats = {}           # 地点 → 出现次数
        start = time.time()
        confidence_threshold = self.config.get("confidence_threshold", 0.6)
        low_conf_review = self.config.get("output", {}).get("low_confidence_review", True)
        handle_dup = self.config.get("output", {}).get("handle_duplicates", "rename")
        file_mode = self.config.get("output", {}).get("file_mode", "copy")
        move_original = file_mode == "move"
        known_persons = self.config.get("known_persons", []) or []
        known_places = self.config.get("known_places", []) or []
        person_recognition = self.config.get("person_recognition", True) and bool(known_persons)
        place_recognition = self.config.get("place_recognition", True) and bool(known_places)

        if person_recognition:
            self.log(f"👤 人物识别已开启：{len(known_persons)} 位已知人物", "INFO")
        if place_recognition:
            self.log(f"📍 地点识别已开启：{len(known_places)} 个已知地点", "INFO")
        if move_original:
            self.log("📦 文件处理模式：移动（分类后删除原始文件）", "WARN")

        for i, img_path in enumerate(image_files, 1):
            if self._stop:
                self.log("用户取消了分类", "WARN")
                break

            fname = os.path.basename(img_path)
            if self.progress_callback:
                self.progress_callback(i, len(image_files), fname)

            category, confidence, reason, persons, places = classify_image_with_retry(img_path, self.config)
            tags = []
            if persons:
                tags.append(f"👤{','.join(persons)}")
            if places:
                tags.append(f"📍{','.join(places)}")
            tag = f" {' '.join(tags)}" if tags else ""
            self.log(f"[{i}/{len(image_files)}] {fname} → {category} ({confidence:.0%}){tag}", "PROGRESS")

            if category == "错误":
                errors.append((img_path, reason))
                continue

            # 低置信度处理
            if low_conf_review and confidence < confidence_threshold:
                low_confidence.append((img_path, category, confidence, reason))
                category = "待复核"

            if category not in results:
                results[category] = []
            results[category].append((img_path, reason))

            try:
                dest_path = copy_to_category(img_path, category, output_dir, handle_dup, move=move_original)
                if dest_path is None:
                    self.log(f"   跳过重复文件", "INFO")
                    continue
                # 归档源：移动模式下从目标位置复制，复制模式下从原始位置复制
                src_for_archive = dest_path if move_original else img_path
                # 人物识别：额外归档到 人物库/{name}/
                if person_recognition and persons:
                    for pn in persons:
                        try:
                            copy_to_person_folder(src_for_archive, pn, output_dir, handle_dup)
                            person_stats[pn] = person_stats.get(pn, 0) + 1
                        except Exception as e:
                            self.log(f"人物归档失败 {pn}：{e}", "WARN")
                # 地点识别：额外归档到 地点库/{name}/
                if place_recognition and places:
                    for pl in places:
                        try:
                            copy_to_place_folder(src_for_archive, pl, output_dir, handle_dup)
                            place_stats[pl] = place_stats.get(pl, 0) + 1
                        except Exception as e:
                            self.log(f"地点归档失败 {pl}：{e}", "WARN")
            except Exception as e:
                self.log(f"复制失败：{e}", "ERROR")

        elapsed = time.time() - start

        # 4. 统计与报告
        total = sum(len(items) for items in results.values()) + len(errors)
        self.log("-" * 40, "INFO")
        for cat in list(self.config.get("categories", {}).keys()) + ["其他", "待复核"]:
            count = len(results.get(cat, []))
            if count > 0:
                self.log(f"   {cat}：{count} 张", "INFO")
        if errors:
            self.log(f"   处理失败：{len(errors)} 张", "WARN")
        # 人物识别统计
        if person_stats:
            self.log("   👤 人物识别：", "INFO")
            for pn, cnt in sorted(person_stats.items(), key=lambda x: -x[1]):
                self.log(f"      {pn}：{cnt} 张（已归档至 人物库/{pn}/）", "INFO")
        # 地点识别统计
        if place_stats:
            self.log("   📍 地点识别：", "INFO")
            for pl, cnt in sorted(place_stats.items(), key=lambda x: -x[1]):
                self.log(f"      {pl}：{cnt} 张（已归档至 地点库/{pl}/）", "INFO")
        self.log(f"总计：{total} 张，耗时 {elapsed:.1f} 秒", "OK")

        if self.config.get("output", {}).get("generate_report", True) and results:
            try:
                report_path = generate_csv_report(results, output_dir)
                self.log(f"报告已保存：{report_path}", "OK")
            except Exception as e:
                self.log(f"生成报告失败：{e}", "WARN")

        # 5. 记录历史
        self.history.add(input_dir, output_dir, model, total, results, elapsed)

        # 6. 执行规则引擎（分类后处理）
        rules = self.config.get("rules", [])
        if rules:
            try:
                rule_engine = RuleEngine(rules=rules, log_callback=self.log_callback)
                rule_engine.apply_all(results, output_dir)
            except Exception as e:
                self.log(f"规则引擎执行失败: {e}", "WARN")

        self.log("🎉 分类完成！", "OK")

        if self.finished_callback:
            self.finished_callback(True, results)

    def get_stats(self):
        """获取历史统计"""
        records = self.history.get_all()
        total_tasks = len(records)
        total_images = sum(r.get("total", 0) for r in records)
        return {
            "total_tasks": total_tasks,
            "total_images": total_images,
            "recent_tasks": records[:5]
        }
