from core.usage_report import build_usage_report


def test_usage_report_aggregates_without_paths():
    records = [{
        "time": "2026-08-20 10:00:00",
        "input_dir": "C:/private/client-a",
        "output_dir": "C:/private/output",
        "model": "llava:7b",
        "total": 12,
        "elapsed": 30,
        "results": {"工作": 8, "其他": 4},
    }]
    text = build_usage_report(records)
    assert "SnapSort 使用报告" in text
    assert "处理素材：12 张" in text
    assert "工作：8 张" in text
    assert "llava:7b：1 次任务" in text
    assert "client-a" not in text
    assert "C:/private" not in text
    assert "作品集" not in text
