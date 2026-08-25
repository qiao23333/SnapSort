import os

from PIL import Image

from core import object_search


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"response": "MATCHES: 1"}


def test_object_search_batches_and_reuses_cache(tmp_path, monkeypatch):
    folder = tmp_path / "library"
    folder.mkdir()
    candidates = []
    for index in range(4):
        path = folder / f"candidate_{index}.jpg"
        Image.new("RGB", (16, 16), (index * 40, 0, 0)).save(path)
        candidates.append(path)
    reference = tmp_path / "reference.jpg"
    Image.new("RGB", (16, 16), "red").save(reference)

    monkeypatch.setattr(object_search, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(object_search, "encode_image", lambda path, **_kwargs: str(path))
    calls = []

    def fake_post(*_args, **kwargs):
        calls.append(kwargs["json"]["images"])
        return _Response()

    monkeypatch.setattr(object_search.requests, "post", fake_post)

    results, stats = object_search.search_object(
        str(folder), "红色杯子", "固定的红色杯子", [str(reference)],
        "llava:7b", batch_size=3, top_n=10,
    )
    assert len(calls) == 2
    assert stats == {"total": 4, "processed": 4, "reused": 0, "errors": 0}
    assert [path for path, _ in results] == [str(candidates[0]), str(candidates[3])]

    calls.clear()
    results, stats = object_search.search_object(
        str(folder), "红色杯子", "固定的红色杯子", [str(reference)],
        "llava:7b", batch_size=3, top_n=10,
    )
    assert calls == []
    assert stats["processed"] == 0 and stats["reused"] == 4
    assert len(results) == 2

    old_ns = candidates[1].stat().st_mtime_ns
    Image.new("RGB", (16, 16), "green").save(candidates[1])
    os.utime(candidates[1], ns=(old_ns + 2_000_000, old_ns + 2_000_000))
    calls.clear()
    _, stats = object_search.search_object(
        str(folder), "红色杯子", "固定的红色杯子", [str(reference)],
        "llava:7b", batch_size=3, top_n=10,
    )
    assert len(calls) == 1
    assert stats["processed"] == 1 and stats["reused"] == 3
