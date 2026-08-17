#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史记录管理"""
import os
import json
from datetime import datetime
from pathlib import Path


class HistoryManager:
    def __init__(self, history_path=None):
        if history_path is None:
            root = Path(__file__).parent.parent
            self.history_path = root / "data" / "history.json"
        else:
            self.history_path = Path(history_path)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.records = self.load()

    def load(self):
        if self.history_path.exists():
            with open(self.history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def save(self):
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)

    def add(self, input_dir, output_dir, model, total, results, elapsed):
        summary = {}
        for cat, files in results.items():
            summary[cat] = len(files)

        record = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
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
