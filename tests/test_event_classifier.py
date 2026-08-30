#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事件整理核心逻辑测试：时间聚类 / 命名模板 / 断点"""
import os
from datetime import datetime, timedelta

from core.event_classifier import (
    BatchRenamer,
    Checkpoint,
    get_datetime_info,
    group_by_time_interval,
)


def _make_photo(tmp_path, dt, name):
    """创建一张用 mtime 模拟拍摄时间的假照片"""
    p = tmp_path / name
    p.write_bytes(b"\xff\xd8\xff\xe0fakejpg")
    os.utime(p, (dt.timestamp(), dt.timestamp()))
    return str(p)


def test_same_event_grouped(tmp_path):
    base = datetime(2026, 8, 1, 10, 0, 0)
    photos = [_make_photo(tmp_path, base + timedelta(minutes=m * 5), f"a{m}.jpg")
              for m in range(5)]  # 间隔 5 分钟，同一事件
    groups = group_by_time_interval(photos, gap_hours=4)
    assert len(groups) == 1
    assert len(list(groups.values())[0]) == 5


def test_gap_splits_events(tmp_path):
    base = datetime(2026, 8, 1, 8, 0, 0)
    photos = [
        _make_photo(tmp_path, base, "morning1.jpg"),
        _make_photo(tmp_path, base + timedelta(minutes=30), "morning2.jpg"),
        _make_photo(tmp_path, base + timedelta(hours=6), "afternoon1.jpg"),  # 间隔 5.5h > 4h
    ]
    groups = group_by_time_interval(photos, gap_hours=4)
    assert len(groups) == 2
    assert "2026-08-01" in groups and "2026-08-01_2" in groups


def test_missing_exif_reports_file_mtime_as_low_confidence(tmp_path):
    photo = _make_photo(tmp_path, datetime(2026, 8, 30, 9, 0), "forwarded.jpg")

    captured_at, source = get_datetime_info(photo)

    assert captured_at == datetime(2026, 8, 30, 9, 0)
    assert source == "file_mtime"


def test_default_name_pattern():
    name = BatchRenamer.new_name("2026-08-01", "工厂参观", 3, "A", "车间全景", ".jpg")
    assert name.startswith("2026-08-01_工厂参观_03")
    assert "车间全景" in name
    assert name.endswith(".jpg")


def test_custom_name_pattern():
    name = BatchRenamer.new_name(
        "2026-08-01", "工厂/参观", 7, "B", "电焊 特写", ".jpg",
        pattern="{event}_{seq:03d}_{grade}",
        tags=["工业", "人物"])
    assert name == "工厂参观_007_B.jpg"


def test_pattern_illegal_chars_stripped():
    name = BatchRenamer.new_name(
        "2026-08-01", "事件", 1, "A", "描述", ".jpg",
        pattern='{event}: \\ bad ? name *')
    for ch in '\\/:*?"<>|':
        assert ch not in name


def test_checkpoint_roundtrip(tmp_path):
    d = str(tmp_path)
    Checkpoint.save(d, ["2026-08-01", "2026-08-02"])
    assert Checkpoint.is_done(d, "2026-08-01")
    assert not Checkpoint.is_done(d, "2026-08-03")
    Checkpoint.clear(d)
    assert not Checkpoint.is_done(d, "2026-08-01")
    assert not os.path.exists(Checkpoint.path(d)), "清除断点后文件应删除"
