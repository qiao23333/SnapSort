#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一日志：界面日志照旧显示，同时写入用户日志目录（滚动保留）。"""
import logging
import os
from logging.handlers import RotatingFileHandler

from core.paths import user_data_dir

_LOG_DIR = str(user_data_dir() / "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "snapsort.log")
_configured = False


def get_logger(name="snapsort"):
    global _configured
    logger = logging.getLogger(name)
    if not _configured:
        os.makedirs(_LOG_DIR, exist_ok=True)
        handler = RotatingFileHandler(_LOG_FILE, maxBytes=200 * 1024, backupCount=3,
                                      encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.propagate = False
        _configured = True
    return logger


def log_path():
    return _LOG_FILE
