#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ConfigManager 测试：原子写入 / 防抖 / 默认值合并 / 损坏恢复"""
import json
import os
import time

from core.config import ConfigManager, DEFAULT_CONFIG


def test_atomic_write_no_tmp_left(tmp_path):
    p = tmp_path / "config.json"
    cm = ConfigManager(str(p))
    cm.set("model", "llava:13b")
    cm.flush()
    assert json.load(open(p))["model"] == "llava:13b"
    assert not os.path.exists(str(p) + ".tmp"), "临时文件不应残留"


def test_debounce_merges_writes(tmp_path):
    p = tmp_path / "config.json"
    cm = ConfigManager(str(p))
    # 连续 10 次 set，防抖后只落盘最终值
    for i in range(10):
        cm.set(f"key{i}", i)
    cm.flush()
    data = json.load(open(p))
    assert data["key9"] == 9
    assert data["key0"] == 0


def test_flush_survives_reload(tmp_path):
    p = tmp_path / "config.json"
    cm = ConfigManager(str(p))
    cm.set("input_dir", "/tmp/photos")
    cm.flush()
    cm2 = ConfigManager(str(p))
    assert cm2.get("input_dir") == "/tmp/photos"


def test_defaults_merged_on_upgrade(tmp_path):
    p = tmp_path / "config.json"
    # 模拟旧版本配置文件（缺新字段）
    p.write_text(json.dumps({"model": "llava:7b"}), encoding="utf-8")
    cm = ConfigManager(str(p))
    for k in DEFAULT_CONFIG:
        assert k in cm.config, f"升级后应补默认字段: {k}"
    assert cm.get("model") == "llava:7b", "已有字段不应被覆盖"


def test_corrupt_file_does_not_crush_load(tmp_path):
    """配置损坏时 load 应该能回退（不抛异常即可）"""
    p = tmp_path / "config.json"
    p.write_text("{ this is not valid json !!!", encoding="utf-8")
    try:
        cm = ConfigManager(str(p))
        cm.get("model")  # 能读到默认值或 None 即可
    except json.JSONDecodeError:
        raise AssertionError("损坏的配置文件不应让程序崩溃（load 应处理异常）")
