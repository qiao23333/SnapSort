#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成不包含文件名和本地路径的作品集证据快照。"""

from collections import Counter
from datetime import datetime
from pathlib import Path


def build_portfolio_snapshot(records):
    """把本地历史记录汇总为可放进作品集的 Markdown。"""
    records = [r for r in records if isinstance(r, dict)]
    total_tasks = len(records)
    total_images = sum(int(r.get("total", 0) or 0) for r in records)
    total_seconds = sum(float(r.get("elapsed", 0) or 0) for r in records)
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

    dates = sorted((str(r.get("time") or "")[:10] for r in records if r.get("time")))
    date_range = f"{dates[0]} 至 {dates[-1]}" if dates else "暂无记录"
    average = round(total_images / total_tasks, 1) if total_tasks else 0

    lines = [
        "# SnapSort 项目证据快照",
        "",
        f"> 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}。仅包含汇总数据，"
        "不包含图片名、本地路径或图片内容。",
        "",
        "## 真实使用数据",
        "",
        f"- 使用区间：{date_range}",
        f"- 完成任务：{total_tasks} 次",
        f"- 处理素材：{total_images} 张",
        f"- 平均每次：{average} 张",
        f"- 程序累计处理耗时：{round(total_seconds / 60, 1)} 分钟",
        "",
        "## 分类结果分布",
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
    lines.extend([
        "",
        "## 作品集补充证据（手动填写）",
        "",
        "- 与纯手工流程相比的时间对照：",
        "- 抽样分类准确率与样本量：",
        "- 实际工作中减少的重复步骤：",
        "- 一次失败或误判，以及如何改进：",
        "- 使用者反馈或后续迭代：",
        "",
    ])
    return "\n".join(lines)


def export_portfolio_snapshot(records, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_portfolio_snapshot(records), encoding="utf-8")
    return path
