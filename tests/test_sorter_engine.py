#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""排序引擎测试：关键词表缓存 / 参考图编码缓存"""
import os

from PIL import Image

from core.sorter_engine import build_keywords_map, encode_image_cached


def _mkimg(path, color=(200, 30, 30)):
    Image.new("RGB", (64, 64), color).save(path)
    return path


def test_keywords_cache_hit():
    cats = {"工厂图": "工厂、厂房、车间", "办公室图": "办公室"}
    m1 = build_keywords_map(cats)
    assert build_keywords_map(cats) is m1, "同一配置应命中缓存（返回同一对象）"


def test_keywords_cache_invalidate():
    cats = {"工厂图": "工厂"}
    m1 = build_keywords_map(cats)
    cats2 = dict(cats, 新分类="测试")
    m2 = build_keywords_map(cats2)
    assert m2 is not m1, "配置变化后缓存应失效"
    assert "新分类" in m2


def test_keywords_map_content():
    m = build_keywords_map({"工厂图": "车间。产线、设备"})
    kws = m["工厂图"]
    # 配置描述按 。 和 、 切分后并入关键词
    assert any("车间" in k for k in kws)
    assert any("产线" in k for k in kws)


def test_ref_encode_cache(tmp_path):
    p = _mkimg(str(tmp_path / "ref.png"))
    a = encode_image_cached(p)
    assert a and a == encode_image_cached(p), "同一文件应命中编码缓存"


def test_ref_encode_cache_invalidate_on_mtime(tmp_path):
    p = _mkimg(str(tmp_path / "ref2.png"))
    a = encode_image_cached(p)
    # 修改内容 + mtime → 缓存应失效重编
    _mkimg(p, color=(30, 30, 200))
    st = os.stat(p)
    os.utime(p, (st.st_atime + 10, st.st_mtime + 10))
    b = encode_image_cached(p)
    assert b and b != a, "文件变化后应重新编码"
