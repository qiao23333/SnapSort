#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读取和安全修改照片中常用的 EXIF/IPTC 风格信息。"""

import os
import shutil
import tempfile
from pathlib import Path

from PIL import Image


TAG_DATETIME = 306
TAG_DATETIME_ORIGINAL = 36867
TAG_DATETIME_DIGITIZED = 36868
TAG_DESCRIPTION = 270
TAG_ARTIST = 315
TAG_COPYRIGHT = 33432
TAG_XP_TITLE = 40091
TAG_XP_COMMENT = 40092
TAG_XP_AUTHOR = 40093
TAG_XP_KEYWORDS = 40094
TAG_RATING = 18246
TAG_USER_COMMENT = 37510
_COPYRIGHT_MARKER = b"SNAPSORT_COPYRIGHT\x00"

EDITABLE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def _decode_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        # Windows XP* 标签使用带结尾空字符的 UTF-16LE。
        for encoding in ("utf-16le", "utf-8", "latin-1"):
            try:
                return value.decode(encoding).rstrip("\x00")
            except (UnicodeDecodeError, ValueError):
                continue
    return str(value).rstrip("\x00")


def _xp_encode(value):
    return (str(value).rstrip("\x00") + "\x00").encode("utf-16le")


def _decode_copyright(exif):
    standard = _decode_text(exif.get(TAG_COPYRIGHT))
    if standard and "?" not in standard:
        return standard
    comment = exif.get(TAG_USER_COMMENT)
    if isinstance(comment, bytes) and comment.startswith(_COPYRIGHT_MARKER):
        try:
            return comment[len(_COPYRIGHT_MARKER):].decode("utf-16le").rstrip("\x00")
        except UnicodeDecodeError:
            pass
    return standard


def read_photo_metadata(path):
    """返回界面可编辑的常用元数据；没有 EXIF 时返回空字段。"""
    path = Path(path)
    with Image.open(path) as image:
        exif = image.getexif()
        date_value = (
            exif.get(TAG_DATETIME_ORIGINAL)
            or exif.get(TAG_DATETIME_DIGITIZED)
            or exif.get(TAG_DATETIME)
            or ""
        )
        return {
            "date": _decode_text(date_value),
            "title": _decode_text(exif.get(TAG_XP_TITLE)),
            "description": _decode_text(
                exif.get(TAG_XP_COMMENT) or exif.get(TAG_DESCRIPTION)
            ),
            "author": _decode_text(exif.get(TAG_XP_AUTHOR) or exif.get(TAG_ARTIST)),
            "copyright": _decode_copyright(exif),
            "keywords": _decode_text(exif.get(TAG_XP_KEYWORDS)),
            "rating": _decode_text(exif.get(TAG_RATING)),
        }


def _set_or_delete(mapping, tag, value, encoder=None):
    value = str(value or "").strip()
    if value:
        mapping[tag] = encoder(value) if encoder else value
    elif tag in mapping:
        del mapping[tag]


def _set_ascii_compatible(mapping, tag, value):
    value = str(value or "").strip()
    if value and value.isascii():
        mapping[tag] = value
    elif tag in mapping:
        del mapping[tag]


def _apply_values(exif, values):
    date_value = str(values.get("date", "")).strip()
    for tag in (TAG_DATETIME, TAG_DATETIME_ORIGINAL, TAG_DATETIME_DIGITIZED):
        _set_or_delete(exif, tag, date_value)
    _set_or_delete(exif, TAG_XP_TITLE, values.get("title"), _xp_encode)
    _set_or_delete(exif, TAG_XP_COMMENT, values.get("description"), _xp_encode)
    _set_ascii_compatible(exif, TAG_DESCRIPTION, values.get("description"))
    _set_or_delete(exif, TAG_XP_AUTHOR, values.get("author"), _xp_encode)
    _set_ascii_compatible(exif, TAG_ARTIST, values.get("author"))
    _set_ascii_compatible(exif, TAG_COPYRIGHT, values.get("copyright"))
    copyright_value = str(values.get("copyright", "")).strip()
    if copyright_value and not copyright_value.isascii():
        exif[TAG_USER_COMMENT] = _COPYRIGHT_MARKER + _xp_encode(copyright_value)
    elif isinstance(exif.get(TAG_USER_COMMENT), bytes) and exif.get(
            TAG_USER_COMMENT).startswith(_COPYRIGHT_MARKER):
        del exif[TAG_USER_COMMENT]
    _set_or_delete(exif, TAG_XP_KEYWORDS, values.get("keywords"), _xp_encode)
    rating = str(values.get("rating", "")).strip()
    if rating:
        parsed = int(rating)
        if not 0 <= parsed <= 5:
            raise ValueError("评分必须是 0–5 的整数")
        exif[TAG_RATING] = parsed
    elif TAG_RATING in exif:
        del exif[TAG_RATING]
    return exif


def _backup_once(path):
    backup_dir = path.parent / ".snapsort-backup"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / path.name
    if not backup_path.exists():
        shutil.copy2(path, backup_path)
    return backup_path


def update_photo_metadata(path, values, create_backup=True):
    """原子写入常用元数据，返回备份路径（未备份时为 None）。

    JPEG 使用 Pillow 的原始量化表保留模式；PNG/WebP/TIFF 使用各自容器保存。
    HEIC/BMP/GIF 暂不写入，避免格式转换或不可逆损失。
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    ext = path.suffix.lower()
    if ext not in EDITABLE_EXTENSIONS:
        raise ValueError("当前仅支持修改 JPG、PNG、WebP 和 TIFF 的元数据")

    backup_path = _backup_once(path) if create_backup else None
    fd, tmp_name = tempfile.mkstemp(prefix=".snapsort_metadata_", suffix=ext, dir=path.parent)
    os.close(fd)
    try:
        with Image.open(path) as source:
            source.load()
            exif = _apply_values(source.getexif(), values)
            save_kwargs = {"exif": exif.tobytes()}
            image_format = source.format or {
                ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG",
                ".webp": "WEBP", ".tif": "TIFF", ".tiff": "TIFF",
            }[ext]
            if image_format == "JPEG":
                save_kwargs.update({"quality": "keep", "subsampling": "keep"})
                if source.mode not in ("RGB", "L", "CMYK"):
                    source = source.convert("RGB")
            elif image_format == "WEBP":
                save_kwargs.update({"quality": 95})
            source.save(tmp_name, image_format, **save_kwargs)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return backup_path
