#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成不包含文件名、本地路径和图片内容的使用报告。"""

from collections import Counter
from datetime import datetime
from pathlib import Path


def build_usage_report(records):
    """将本地历史记录汇总成便于归档或分享的 Markdown 报告。"""
    records = [record for record in records if isinstance(record, dict)]
    total_tasks = len(records)
    total_images = sum(int(record.get("total", 0) or 0) for record in records)
    total_seconds = sum(float(record.get("elapsed", 0) or 0) for record in records)
    categories = Counter()
    models = Counter()

    for record in records:
        categories.update({
            str(name): int(count or 0)
            for name, count in (record.get("results") or {}).items()
            if int(count or 0) > 0
        })
        model = str(record.get("model") or "").strip()
        if model:
            models[model] += 1

    dates = sorted(
        str(record.get("time") or "")[:10]
        for record in records if record.get("time")
    )
    date_range = f"{dates[0]} 至 {dates[-1]}" if dates else "暂无记录"
    average = round(total_images / total_tasks, 1) if total_tasks else 0

    lines = [
        "# SnapSort 使用报告",
        "",
        f"> 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}。"
        "仅包含汇总数据，不包含图片名、本地路径或图片内容。",
        "",
        "## 处理概况",
        "",
        f"- 使用区间：{date_range}",
        f"- 完成任务：{total_tasks} 次",
        f"- 处理素材：{total_images} 张",
        f"- 平均每次：{average} 张",
        f"- 累计处理耗时：{round(total_seconds / 60, 1)} 分钟",
        "",
        "## 分类结果",
        "",
    ]
    lines.extend(
        [f"- {name}：{count} 张" for name, count in categories.most_common()]
        or ["- 暂无数据"]
    )
    lines.extend(["", "## 使用模型", ""])
    lines.extend(
        [f"- {name}：{count} 次任务" for name, count in models.most_common()]
        or ["- 暂无数据"]
    )
    lines.append("")
    return "\n".join(lines)


def export_usage_report(records, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_usage_report(records), encoding="utf-8")
    return path
