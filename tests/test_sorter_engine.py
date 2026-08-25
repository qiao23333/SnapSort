#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""排序引擎测试：关键词表缓存 / 参考图编码缓存"""
import os
from pathlib import Path

from PIL import Image

from core.sorter_engine import (
    _build_output_digest_index,
    _content_digest,
    _load_incremental_manifest,
    _save_incremental_manifest,
    _source_key,
    _source_signature,
    build_keywords_map,
    classify_image,
    copy_to_category,
    encode_image_cached,
    ensure_model,
)


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


def test_custom_object_reference_is_sent_to_visual_model(tmp_path, monkeypatch):
    candidate = _mkimg(str(tmp_path / "candidate.png"))
    reference = _mkimg(str(tmp_path / "reference.png"), color=(210, 40, 40))
    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {"response": "SCENE: 办公室\nDESC: 桌上有杯子\nTARGETS: 红色杯子"}

    monkeypatch.setattr(
        "core.sorter_engine.ref_mgr.get_reference_images_for_call",
        lambda ref_type, name: [reference] if ref_type == "target" else [],
    )

    def fake_post(_url, json, timeout):
        captured.update(json)
        return Response()

    monkeypatch.setattr("core.sorter_engine.requests.post", fake_post)
    result = classify_image(candidate, {
        "categories": {"办公": "办公室、杯子"},
        "model": "llava:7b",
        "known_persons": [], "known_places": [],
        "recognition_targets_enabled": True,
        "recognition_targets": [{
            "name": "红色杯子", "type": "物品",
            "description": "固定的红色杯子", "enabled": True,
        }],
    })

    assert len(captured["images"]) == 2
    assert "自定义对象「红色杯子」的参考照片" in captured["prompt"]
    assert "识别目标:红色杯子" in result[2]


def test_category_cannot_escape_output_folder(tmp_path):
    image = _mkimg(str(tmp_path / "source.png"))
    output = tmp_path / "output"
    dest = Path(copy_to_category(image, "../外部", str(output)))
    assert output in dest.parents
    assert dest.parent.name == ".._外部"


def test_model_pull_error_is_not_reported_as_success(monkeypatch):
    class Response:
        def __init__(self, payload=None, lines=None):
            self._payload = payload or {}
            self._lines = lines or []

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

        def iter_lines(self):
            return iter(self._lines)

    monkeypatch.setattr(
        "core.sorter_engine.requests.get",
        lambda *args, **kwargs: Response({"models": []}),
    )
    monkeypatch.setattr(
        "core.sorter_engine.requests.post",
        lambda *args, **kwargs: Response(lines=[b'{"error":"disk full"}']),
    )

    ok, info = ensure_model("llava:7b")
    assert ok is False
    assert "disk full" in info


def test_incremental_manifest_tracks_exact_source(tmp_path):
    (tmp_path / "source").mkdir()
    source = _mkimg(str(tmp_path / "source" / "same.png"))
    output = tmp_path / "output"
    manifest = {_source_key(source): _source_signature(source)}
    _save_incremental_manifest(output, manifest)
    assert _load_incremental_manifest(output) == manifest


def test_legacy_incremental_index_does_not_confuse_same_name(tmp_path):
    (tmp_path / "output").mkdir()
    (tmp_path / "input").mkdir()
    old = _mkimg(str(tmp_path / "output" / "same.png"), color=(200, 30, 30))
    fresh = _mkimg(str(tmp_path / "input" / "same.png"), color=(30, 30, 200))
    index = _build_output_digest_index(tmp_path / "output")
    assert _content_digest(old) in index[os.path.getsize(old)]
    assert _content_digest(fresh) not in index.get(os.path.getsize(fresh), set())
