#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史记录管理测试"""
from core.history import HistoryManager


def test_add_and_get_all(tmp_path):
    h = HistoryManager(str(tmp_path / "history.json"))
    h.add("/in", "/out", "llava:13b", 100, {"工厂图": ["a.jpg"] * 30}, 12.5)
    recs = h.get_all()
    assert len(recs) == 1
    r = recs[0]
    assert r["total"] == 100
    assert r["results"]["工厂图"] == 30
    assert r["elapsed"] == 12.5


def test_newest_first(tmp_path):
    h = HistoryManager(str(tmp_path / "history.json"))
    h.add("/in", "/out", "m1", 1, {}, 1)
    h.add("/in", "/out", "m2", 2, {}, 1)
    recs = h.get_all()
    assert recs[0]["total"] == 2, "新记录应插在最前"


def test_delete_and_clear(tmp_path):
    h = HistoryManager(str(tmp_path / "history.json"))
    r = h.add("/in", "/out", "m", 1, {}, 1)
    h.delete(r["id"])
    assert h.get_all() == []
    h.add("/in", "/out", "m", 1, {}, 1)
    h.clear()
    assert h.get_all() == []


def test_persistence(tmp_path):
    p = str(tmp_path / "history.json")
    HistoryManager(p).add("/in", "/out", "llava", 9, {}, 3)
    h2 = HistoryManager(p)
    assert len(h2.get_all()) == 1, "重新加载应读到已保存记录"
