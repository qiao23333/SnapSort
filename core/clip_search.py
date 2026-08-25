#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基于 CLIP 嵌入的语义图片搜索。

使用 sentence-transformers 的 CLIP 模型生成图片和文本的 512 维向量，
用 FAISS 做近似最近邻搜索，实现真正的语义级以文搜图。

相比逐张调用视觉语言模型，更适合建立本地图片检索索引。
"""
import json
import os
import threading
import time
from importlib.util import find_spec

from core.paths import user_cache_dir

DATA_DIR = user_cache_dir() / "clip_index"
DATA_DIR.mkdir(parents=True, exist_ok=True)

INDEX_PATH = DATA_DIR / "faiss_index.bin"
PATHS_PATH = DATA_DIR / "image_paths.json"
META_PATH = DATA_DIR / "index_meta.json"
VECTORS_PATH = DATA_DIR / "image_vectors.npy"
MODEL_NAME = "clip-ViT-B-32"

_model = None
_faiss = None
_index = None
_paths = []
_lock = threading.RLock()


def _lazy_imports():
    """延迟导入，避免未安装时影响整个应用。"""
    global _model, _faiss
    if _model is not None:
        return True

    try:
        import faiss
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return False

    _model = SentenceTransformer(MODEL_NAME)
    _faiss = faiss
    return True


def is_available():
    """检查 CLIP 搜索是否可用（依赖已安装）。"""
    return find_spec("faiss") is not None and find_spec("sentence_transformers") is not None


def get_model_info():
    """返回模型信息。"""
    return {
        "model": MODEL_NAME,
        "dim": 512,
        "backend": "sentence-transformers + FAISS",
    }


def index_folder(folder, batch_size=32, progress_cb=None, cancel_cb=None):
    """为文件夹内所有图片生成 CLIP 嵌入并建立 FAISS 索引。

    Args:
        folder: 图片文件夹路径
        batch_size: 批量处理大小
        progress_cb: 回调函数 (done, total)
        cancel_cb: 返回 True 时取消

    Returns:
        (success, message)
    """
    folder = os.path.abspath(folder)
    if not _lazy_imports():
        return False, "需要安装依赖：pip install sentence-transformers faiss-cpu"

    import numpy as np
    from core.image_utils import is_image_file

    with _lock:
        image_paths = sorted(
            os.path.abspath(os.path.join(root, filename))
            for root, _, files in os.walk(folder)
            for filename in files
            if is_image_file(os.path.join(root, filename))
        )
        if not image_paths:
            return False, "文件夹中没有图片"

        signatures = {}
        for path in image_paths:
            try:
                stat = os.stat(path)
                signatures[path] = [stat.st_mtime_ns, stat.st_size]
            except OSError:
                pass
        image_paths = [path for path in image_paths if path in signatures]
        total = len(image_paths)

        old_meta = get_index_info()
        old_paths = []
        old_vectors = None
        try:
            if (old_meta.get("model") == MODEL_NAME
                    and os.path.abspath(old_meta.get("source_folder", "")) == folder
                    and PATHS_PATH.exists() and VECTORS_PATH.exists()):
                with open(PATHS_PATH, "r", encoding="utf-8") as handle:
                    old_paths = json.load(handle)
                old_vectors = np.load(VECTORS_PATH, allow_pickle=False)
                if len(old_paths) != len(old_vectors):
                    old_paths, old_vectors = [], None
        except (OSError, ValueError, json.JSONDecodeError):
            old_paths, old_vectors = [], None

        old_signatures = old_meta.get("signatures", {}) or {}
        reusable = {}
        if old_vectors is not None:
            for index, path in enumerate(old_paths):
                if signatures.get(path) == old_signatures.get(path):
                    reusable[path] = old_vectors[index]

        pending = [path for path in image_paths if path not in reusable]
        if not pending and len(reusable) == total and INDEX_PATH.exists():
            if progress_cb:
                progress_cb(total, total)
            return True, f"索引已是最新，共 {total} 张图片"

        encoded = {}
        processed = len(reusable)
        if progress_cb and processed:
            progress_cb(processed, total)

        for start in range(0, len(pending), max(1, batch_size)):
            if cancel_cb and cancel_cb():
                return False, "已取消"
            batch_paths = pending[start:start + max(1, batch_size)]
            batch_images, valid_paths = _load_clip_images(batch_paths)
            if batch_images:
                try:
                    batch_vectors = _model.encode(
                        batch_images, batch_size=len(batch_images),
                        show_progress_bar=False, convert_to_numpy=True,
                    ).astype("float32")
                    _faiss.normalize_L2(batch_vectors)
                    encoded.update(zip(valid_paths, batch_vectors))
                except Exception:
                    pass
            processed += len(batch_paths)
            if progress_cb:
                progress_cb(min(processed, total), total)

        indexed_paths = [
            path for path in image_paths if path in reusable or path in encoded
        ]
        if not indexed_paths:
            return False, "没有成功生成任何嵌入"

        vectors = np.vstack([
            reusable[path] if path in reusable else encoded[path]
            for path in indexed_paths
        ]).astype("float32")
        _faiss.normalize_L2(vectors)
        dim = vectors.shape[1]
        index = _faiss.IndexFlatIP(dim)
        index.add(vectors)

        _write_index_files(index, indexed_paths, vectors, {
            "source_folder": folder,
            "total_images": len(indexed_paths),
            "errors": total - len(indexed_paths),
            "dim": dim,
            "model": MODEL_NAME,
            "updated_at": int(time.time()),
            "signatures": {path: signatures[path] for path in indexed_paths},
        })

        global _index, _paths
        _index, _paths = index, indexed_paths
        changed = len(encoded)
        reused_count = len(indexed_paths) - changed
        return True, f"索引完成：新增或更新 {changed} 张，复用 {reused_count} 张"


def _load_clip_images(paths):
    from PIL import Image as PILImage
    images, valid_paths = [], []
    for path in paths:
        try:
            with PILImage.open(path) as opened:
                image = opened.convert("RGB")
                if max(image.size) > 512:
                    image.thumbnail((512, 512))
                images.append(image.copy())
            valid_paths.append(path)
        except Exception:
            continue
    return images, valid_paths


def _write_index_files(index, paths, vectors, meta):
    """先写临时文件再替换，避免程序中断留下半个索引。"""
    import numpy as np
    temp_index = INDEX_PATH.with_suffix(".tmp")
    temp_paths = PATHS_PATH.with_suffix(".tmp")
    temp_meta = META_PATH.with_suffix(".tmp")
    temp_vectors = VECTORS_PATH.with_suffix(".tmp.npy")
    _faiss.write_index(index, str(temp_index))
    np.save(temp_vectors, vectors, allow_pickle=False)
    for path, value in ((temp_paths, paths), (temp_meta, meta)):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2 if path == temp_meta else None)
    os.replace(temp_index, INDEX_PATH)
    os.replace(temp_vectors, VECTORS_PATH)
    os.replace(temp_paths, PATHS_PATH)
    os.replace(temp_meta, META_PATH)


def _ensure_loaded():
    """确保索引已加载到内存。"""
    global _index, _paths
    with _lock:
        if _index is not None and _paths:
            return True
        if not _lazy_imports():
            return False
        if not INDEX_PATH.exists() or not PATHS_PATH.exists():
            return False
        try:
            loaded_index = _faiss.read_index(str(INDEX_PATH))
            with open(PATHS_PATH, "r", encoding="utf-8") as f:
                loaded_paths = json.load(f)
        except (OSError, ValueError, json.JSONDecodeError):
            return False
        if not isinstance(loaded_paths, list) or loaded_index.ntotal != len(loaded_paths):
            return False
        _index, _paths = loaded_index, loaded_paths
        return bool(_index is not None and _paths)


def search(query_text, top_n=10):
    """用文本搜索图片，返回 (path, score) 列表。

    Args:
        query_text: 搜索文本（如"红色汽车在停车场"）
        top_n: 返回前 N 个结果

    Returns:
        [(path, score), ...] 按相似度降序
    """
    if not _ensure_loaded():
        return []


    with _lock:
        query_vec = _model.encode([query_text], convert_to_numpy=True).astype("float32")
        _faiss.normalize_L2(query_vec)
        return _search_vector(query_vec, top_n)


def search_by_reference(reference_paths, top_n=10, text_hint=""):
    """用一个具体对象的多张参考照片搜索相似图片。

    多张参考图先各自归一化，再取平均形成该对象的“视觉原型”；可选文字
    只占较小权重，用于补充颜色、用途等参考图未覆盖的信息。
    """
    if not _ensure_loaded():
        return []
    import numpy as np
    with _lock:
        images, _ = _load_clip_images(reference_paths)
        if not images:
            return []
        vectors = _model.encode(
            images, batch_size=len(images), show_progress_bar=False,
            convert_to_numpy=True,
        ).astype("float32")
        _faiss.normalize_L2(vectors)
        query_vec = np.mean(vectors, axis=0, keepdims=True).astype("float32")
        if text_hint.strip():
            text_vec = _model.encode(
                [text_hint.strip()], convert_to_numpy=True).astype("float32")
            _faiss.normalize_L2(text_vec)
            query_vec = query_vec * 0.85 + text_vec * 0.15
        _faiss.normalize_L2(query_vec)
        return _search_vector(query_vec, top_n)


def _search_vector(query_vec, top_n):
    scores, indices = _index.search(query_vec, min(max(1, top_n), len(_paths)))
    return [
        (_paths[idx], float(score))
        for idx, score in zip(indices[0], scores[0])
        if 0 <= idx < len(_paths)
    ]


def index_matches_folder(folder):
    info = get_index_info()
    source = info.get("source_folder", "")
    return bool(source and os.path.normcase(os.path.abspath(source))
                == os.path.normcase(os.path.abspath(folder)))


def get_index_info():
    """返回当前索引的信息。"""
    if META_PATH.exists():
        try:
            with open(META_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"total_images": 0}


def clear_index():
    """清除索引。"""
    global _index, _paths
    _index = None
    _paths = []
    for p in [INDEX_PATH, PATHS_PATH, META_PATH, VECTORS_PATH]:
        try:
            p.unlink()
        except Exception:
            pass
