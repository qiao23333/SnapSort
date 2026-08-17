#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图片工具测试：编码 / 临时文件清理 / 格式判断"""
import os

from PIL import Image

from core.image_utils import (encode_image, _cleanup_temp, is_image_file,
                              format_size)


def _mkimg(path, color=(10, 120, 220)):
    Image.new("RGB", (80, 60), color).save(path)
    return path


def test_encode_image_roundtrip(tmp_path):
    p = _mkimg(str(tmp_path / "x.png"))
    b64 = encode_image(p)
    assert isinstance(b64, str) and len(b64) > 100
    assert os.path.exists(p), "编码后原文件必须还在"


def test_encode_downscales_large(tmp_path):
    p = str(tmp_path / "big.png")
    Image.new("RGB", (4000, 3000), "red").save(p)
    import base64, io
    raw = base64.b64decode(encode_image(p))
    img = Image.open(io.BytesIO(raw))
    assert max(img.size) <= 1600, "长边应被压到 1600 以内"


def test_cleanup_temp_keeps_original(tmp_path):
    orig = _mkimg(str(tmp_path / "orig.png"))
    fake_tmp = str(tmp_path / "tmp_converted.jpg")
    _mkimg(fake_tmp)
    _cleanup_temp(fake_tmp, orig)  # 清理临时文件，不动原图
    assert os.path.exists(orig), "原文件绝不能被删"
    assert not os.path.exists(fake_tmp), "临时文件应被删除"


def test_cleanup_same_path_noop(tmp_path):
    """打开的文件就是原文件（非 HEIC）时不应自删"""
    p = _mkimg(str(tmp_path / "same.png"))
    _cleanup_temp(p, p)
    assert os.path.exists(p)


def test_is_image_file():
    assert is_image_file("a/b/photo.JPG")
    assert is_image_file("x/img.heic")
    assert not is_image_file("y/doc.pdf")
    assert not is_image_file("z/video.mp4")


def test_format_size():
    assert format_size(0) == "0 B"
    assert format_size(2048) == "2.0 KB"
    assert format_size(5 * 1024 * 1024) == "5.0 MB"
