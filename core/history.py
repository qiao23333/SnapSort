#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史记录管理"""
import json
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

from core.paths import migrate_legacy_file, user_data_dir


class HistoryManager:
    def __init__(self, history_path=None):
        if history_path is None:
            self.history_path = user_data_dir() / "history.json"
            migrate_legacy_file("history.json", self.history_path)
        else:
            self.history_path = Path(history_path)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.records = self.load()

    def load(self):
        if self.history_path.exists():
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, list) else []
            except (json.JSONDecodeError, OSError):
                try:
                    backup = str(self.history_path) + f".corrupt.{int(time.time())}"
                    shutil.copy2(self.history_path, backup)
                except OSError:
                    pass
        return []

    def save(self):
        tmp_path = str(self.history_path) + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.history_path)

    def add(self, input_dir, output_dir, model, total, results, elapsed):
        summary = {}
        for cat, files in results.items():
            summary[cat] = len(files)

        record = {
            # Windows 系统时钟可能在连续调用时返回相同“微秒”，UUID 不依赖
            # 时钟精度，快速连续完成两次任务也不会发生记录 ID 冲突。
            "id": uuid.uuid4().hex,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "input_dir": input_dir,
            "output_dir": output_dir,
            "model": model,
            "total": total,
            "results": summary,
            "elapsed": round(elapsed, 1)
        }
        self.records.insert(0, record)
        self.save()
        return record

    def get_all(self):
        return self.records

    def clear(self):
        self.records = []
        self.save()

    def delete(self, record_id):
        self.records = [r for r in self.records if r.get("id") != record_id]
        self.save()
