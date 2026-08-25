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


def test_corrupt_history_is_backed_up(tmp_path):
    p = tmp_path / "history.json"
    p.write_text("{broken", encoding="utf-8")
    history = HistoryManager(str(p))
    assert history.get_all() == []
    assert list(tmp_path.glob("history.json.corrupt.*"))


def test_record_ids_do_not_collide(tmp_path):
    history = HistoryManager(str(tmp_path / "history.json"))
    first = history.add("/in", "/out", "m", 1, {}, 0)
    second = history.add("/in", "/out", "m", 1, {}, 0)
    assert first["id"] != second["id"]
