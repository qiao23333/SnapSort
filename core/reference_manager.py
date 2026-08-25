#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""参考照片管理：存储和检索人物、地点和自定义对象的参考照片

目录结构:
  用户数据目录/ref_images/
    person/
      示例人物/
        ref_0001.jpg
        ref_0002.jpg
    place/
      示例地点/
        ref_0001.jpg
    target/
      示例物品/
        ref_0001.jpg
"""
import os
import shutil
from pathlib import Path

from core.paths import user_data_dir

# 每个人物/地点/对象最多保存的参考照片数
MAX_REF_IMAGES = 5
# 每次分类调用时，每个实体最多发送的参考照片数
MAX_REF_PER_CALL = 2
# 单次视觉模型请求的参考图总预算。过多图片会明显增加编码、传输和推理时间。
MAX_TOTAL_REF_PER_CALL = 8

_ROOT = user_data_dir() / "ref_images"


def _type_dir(ref_type: str) -> Path:
    """ref_type: 'person'、'place' 或 'target'"""
    if ref_type not in {"person", "place", "target"}:
        raise ValueError("ref_type 必须是 person、place 或 target")
    d = _ROOT / ref_type
    d.mkdir(parents=True, exist_ok=True)
    return d


def _entity_dir(ref_type: str, name: str) -> Path:
    """获取某个人物、地点或对象的参考照片目录"""
    safe_name = _sanitize_name(name)
    if not safe_name:
        raise ValueError("人物、地点或对象名称不能为空")
    return _type_dir(ref_type) / safe_name


def _sanitize_name(name: str) -> str:
    """清理名称，使其可作为目录名"""
    # 替换路径分隔符和特殊字符
    for ch in r'<>:"/\|?*':
        name = name.replace(ch, "_")
    return name.strip().strip(".")


def save_reference_images(ref_type: str, name: str, source_paths: list) -> list:
    """将源照片复制到参考照片目录。

    Args:
        ref_type: 'person'、'place' 或 'target'
        name: 人物名、地点名或对象名
        source_paths: 源图片路径列表

    Returns:
        保存后的完整路径列表
    """
    if not name or not name.strip() or not source_paths:
        return []

    dest_dir = _entity_dir(ref_type, name)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 已有数量
    existing = sorted(dest_dir.glob("*"))
    saved = []

    for src in source_paths:
        if len(existing) + len(saved) >= MAX_REF_IMAGES:
            break
        src = str(src)
        if not os.path.isfile(src):
            continue
        ext = os.path.splitext(src)[1].lower() or ".jpg"
        # 生成序号
        idx = len(existing) + len(saved)
        dest_name = f"ref_{idx:04d}{ext}"
        dest_path = dest_dir / dest_name
        shutil.copy2(src, str(dest_path))
        saved.append(str(dest_path))

    return saved


def get_reference_images(ref_type: str, name: str) -> list:
    """获取某个人物、地点或对象的所有参考照片路径"""
    d = _entity_dir(ref_type, name)
    if not d.exists():
        return []
    return sorted(str(p) for p in d.iterdir() if p.is_file())


def get_reference_images_for_call(ref_type: str, name: str) -> list:
    """获取用于 API 调用的参考照片（限制单个实体数量）"""
    all_imgs = get_reference_images(ref_type, name)
    return all_imgs[:MAX_REF_PER_CALL]


def delete_reference_images(ref_type: str, name: str):
    """删除某个人物、地点或对象的所有参考照片"""
    d = _entity_dir(ref_type, name)
    if d.exists():
        shutil.rmtree(str(d), ignore_errors=True)


def delete_single_reference(ref_type: str, name: str, filename: str):
    """删除单张参考照片"""
    d = _entity_dir(ref_type, name)
    target = d / os.path.basename(filename)
    if target.exists():
        target.unlink()


def rename_reference_dir(ref_type: str, old_name: str, new_name: str):
    """重命名人物、地点或对象时，同步重命名参考照片目录"""
    old_dir = _entity_dir(ref_type, old_name)
    new_dir = _entity_dir(ref_type, new_name)
    if old_dir.exists() and old_dir != new_dir:
        # 如果新目录已存在（重名），合并
        if new_dir.exists():
            for f in old_dir.iterdir():
                target = new_dir / f.name
                if not target.exists():
                    shutil.move(str(f), str(target))
            old_dir.rmdir()
        else:
            old_dir.rename(str(new_dir))


def count_reference_images(ref_type: str, name: str) -> int:
    """获取参考照片数量"""
    return len(get_reference_images(ref_type, name))
