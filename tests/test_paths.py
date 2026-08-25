#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台用户目录与资源目录测试。"""
import sys

from core import paths


def test_windows_data_and_cache_use_local_appdata(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert paths.user_data_dir() == tmp_path / "SnapSort"
    assert paths.user_cache_dir() == tmp_path / "SnapSort" / "Cache"


def test_linux_respects_xdg_dirs(tmp_path, monkeypatch):
    data = tmp_path / "xdg-data"
    cache = tmp_path / "xdg-cache"
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))

    assert paths.user_data_dir() == data / "SnapSort"
    assert paths.user_cache_dir() == cache / "SnapSort"


def test_resource_path_uses_pyinstaller_meipass(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert paths.resource_path("data", "icon.png") == tmp_path / "data" / "icon.png"
