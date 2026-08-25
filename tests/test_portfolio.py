from core.portfolio import build_portfolio_snapshot


def test_portfolio_snapshot_aggregates_without_paths():
    records = [{
        "time": "2026-08-20 10:00:00",
        "input_dir": "C:/private/client-a",
        "output_dir": "C:/private/output",
        "model": "llava:7b",
        "total": 12,
        "elapsed": 30,
        "results": {"工作": 8, "其他": 4},
    }]
    text = build_portfolio_snapshot(records)
    assert "处理素材：12 张" in text
    assert "工作：8 张" in text
    assert "llava:7b：1 次任务" in text
    assert "client-a" not in text
    assert "C:/private" not in text
