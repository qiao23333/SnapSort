#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""使用视觉模型按具体对象参考图搜索，并缓存每张照片的匹配结果。"""
import hashlib
import json
import os
import re
import threading

import requests

from core.image_utils import encode_image, is_image_file
from core.paths import user_cache_dir
from core.sorter_engine import DEFAULT_URL


CACHE_PATH = user_cache_dir() / "object_search_cache.json"
_cache_lock = threading.RLock()


def _signature(path):
    stat = os.stat(path)
    return [stat.st_mtime_ns, stat.st_size]


def _target_fingerprint(name, description, model, references):
    payload = {
        "name": name,
        "description": description,
        "model": model,
        "references": [(os.path.abspath(path), _signature(path)) for path in references],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_cache():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _save_cache(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = CACHE_PATH.with_suffix(".tmp")
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(cache, handle, ensure_ascii=False)
    os.replace(temp, CACHE_PATH)


def _parse_matches(response, candidate_count):
    match = re.search(r"MATCHES?\s*[:：]\s*([^\n]+)", response, re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip()
    if value in {"无", "none", "NONE", "没有"}:
        return set()
    return {
        int(number) for number in re.findall(r"\d+", value)
        if 1 <= int(number) <= candidate_count
    }


def search_object(
        folder, name, description, references, model,
        url=DEFAULT_URL, top_n=10, batch_size=3,
        progress_cb=None, cancel_cb=None):
    """把参考图和候选图分批交给 VLM；只推理未缓存或已变化的照片。"""
    references = [path for path in references if os.path.isfile(path)][:2]
    if not references:
        return [], {"total": 0, "processed": 0, "reused": 0, "errors": 0}

    candidates = sorted(
        os.path.abspath(os.path.join(root, filename))
        for root, _, files in os.walk(folder)
        for filename in files
        if is_image_file(os.path.join(root, filename))
    )
    fingerprint = _target_fingerprint(name, description, model, references)
    with _cache_lock:
        cache = _load_cache()
        target_cache = cache.setdefault(fingerprint, {})

    cached_matches, pending = [], []
    for path in candidates:
        try:
            signature = _signature(path)
        except OSError:
            continue
        entry = target_cache.get(path)
        if entry and entry.get("signature") == signature:
            if entry.get("matched"):
                cached_matches.append(path)
        else:
            pending.append((path, signature))

    try:
        reference_images = [encode_image(path, max_size_kb=256) for path in references]
    except Exception:
        return [], {"total": len(candidates), "processed": 0,
                    "reused": len(candidates) - len(pending), "errors": len(pending)}

    processed = 0
    errors = 0
    new_matches = []
    for start in range(0, len(pending), max(1, batch_size)):
        if cancel_cb and cancel_cb():
            break
        batch = pending[start:start + max(1, batch_size)]
        candidate_images, valid = [], []
        for path, signature in batch:
            try:
                candidate_images.append(encode_image(path, max_size_kb=256))
                valid.append((path, signature))
            except Exception:
                errors += 1
        if not valid:
            processed += len(batch)
            continue

        prompt = (
            f"前 {len(reference_images)} 张是具体对象「{name}」的参考照片。"
            f"对象补充说明：{description or '无'}。\n"
            f"后面 {len(valid)} 张依次是候选照片 1 到 {len(valid)}。"
            "请判断每张候选照片里是否出现了与参考照片中同一个具体对象；"
            "不能因为属于同类物品就算命中。只回复 MATCHES: 后接候选编号，"
            "例如 MATCHES: 1,3；全部不匹配则回复 MATCHES: 无。"
        )
        try:
            response = requests.post(
                f"{url}/api/generate",
                json={
                    "model": model, "prompt": prompt,
                    "images": reference_images + candidate_images,
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 30},
                }, timeout=180,
            )
            response.raise_for_status()
            matches = _parse_matches(response.json().get("response", ""), len(valid))
        except Exception:
            matches = None

        if matches is None:
            errors += len(valid)
        else:
            with _cache_lock:
                for number, (path, signature) in enumerate(valid, 1):
                    matched = number in matches
                    target_cache[path] = {"signature": signature, "matched": matched}
                    if matched:
                        new_matches.append(path)
                _save_cache(cache)

        processed += len(batch)
        if progress_cb:
            progress_cb(min(processed, len(pending)), len(pending))

    matches = cached_matches + new_matches
    return [(path, 1.0) for path in matches[:max(1, top_n)]], {
        "total": len(candidates),
        "processed": processed,
        "reused": len(candidates) - len(pending),
        "errors": errors,
    }
