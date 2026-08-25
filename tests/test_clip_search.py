import json
import os

import pytest

np = pytest.importorskip("numpy")
from PIL import Image

from core import clip_search


class _FakeIndex:
    def __init__(self, dim):
        self.dim = dim
        self.vectors = np.empty((0, dim), dtype="float32")

    @property
    def ntotal(self):
        return len(self.vectors)

    def add(self, vectors):
        self.vectors = np.asarray(vectors, dtype="float32")

    def search(self, query, count):
        scores = np.asarray(query) @ self.vectors.T
        order = np.argsort(-scores, axis=1)[:, :count]
        return np.take_along_axis(scores, order, axis=1), order


class _FakeFaiss:
    IndexFlatIP = _FakeIndex

    @staticmethod
    def normalize_L2(vectors):
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors /= np.maximum(norms, 1e-12)

    @staticmethod
    def write_index(index, path):
        with open(path, "wb") as handle:
            np.save(handle, index.vectors, allow_pickle=False)

    @staticmethod
    def read_index(path):
        with open(path, "rb") as handle:
            vectors = np.load(handle, allow_pickle=False)
        index = _FakeIndex(vectors.shape[1])
        index.add(vectors)
        return index


class _FakeModel:
    def __init__(self):
        self.encoded_items = 0

    def encode(self, items, **_kwargs):
        self.encoded_items += len(items)
        vectors = []
        for item in items:
            if isinstance(item, str):
                vectors.append([1.0, 0.2, 0.1])
            else:
                pixel = np.asarray(item, dtype="float32").mean(axis=(0, 1))
                vectors.append(pixel[:3] + 1.0)
        return np.asarray(vectors, dtype="float32")


def test_incremental_index_reuses_unchanged_vectors(tmp_path, monkeypatch):
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    red = image_dir / "red.jpg"
    blue = image_dir / "blue.jpg"
    Image.new("RGB", (20, 20), "red").save(red)
    Image.new("RGB", (20, 20), "blue").save(blue)

    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(clip_search, "INDEX_PATH", cache / "index.bin")
    monkeypatch.setattr(clip_search, "PATHS_PATH", cache / "paths.json")
    monkeypatch.setattr(clip_search, "META_PATH", cache / "meta.json")
    monkeypatch.setattr(clip_search, "VECTORS_PATH", cache / "vectors.npy")
    fake_model = _FakeModel()
    monkeypatch.setattr(clip_search, "_model", fake_model)
    monkeypatch.setattr(clip_search, "_faiss", _FakeFaiss())
    monkeypatch.setattr(clip_search, "_index", None)
    monkeypatch.setattr(clip_search, "_paths", [])
    monkeypatch.setattr(clip_search, "_lazy_imports", lambda: True)

    ok, _ = clip_search.index_folder(str(image_dir), batch_size=2)
    assert ok and fake_model.encoded_items == 2

    ok, message = clip_search.index_folder(str(image_dir), batch_size=2)
    assert ok and "最新" in message and fake_model.encoded_items == 2

    old_ns = blue.stat().st_mtime_ns
    Image.new("RGB", (20, 20), "green").save(blue)
    os.utime(blue, ns=(old_ns + 2_000_000, old_ns + 2_000_000))
    ok, message = clip_search.index_folder(str(image_dir), batch_size=2)
    assert ok and "新增或更新 1 张" in message
    assert fake_model.encoded_items == 3

    meta = json.loads((cache / "meta.json").read_text(encoding="utf-8"))
    assert meta["total_images"] == 2


def test_reference_search_averages_multiple_examples(tmp_path, monkeypatch):
    # Reuse the same fake backend through a normal first indexing pass.
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    red = image_dir / "red.jpg"
    blue = image_dir / "blue.jpg"
    Image.new("RGB", (20, 20), "red").save(red)
    Image.new("RGB", (20, 20), "blue").save(blue)
    cache = tmp_path / "cache"
    cache.mkdir()
    for name, path in {
        "INDEX_PATH": cache / "index.bin", "PATHS_PATH": cache / "paths.json",
        "META_PATH": cache / "meta.json", "VECTORS_PATH": cache / "vectors.npy",
    }.items():
        monkeypatch.setattr(clip_search, name, path)
    monkeypatch.setattr(clip_search, "_model", _FakeModel())
    monkeypatch.setattr(clip_search, "_faiss", _FakeFaiss())
    monkeypatch.setattr(clip_search, "_index", None)
    monkeypatch.setattr(clip_search, "_paths", [])
    monkeypatch.setattr(clip_search, "_lazy_imports", lambda: True)

    assert clip_search.index_folder(str(image_dir))[0]
    results = clip_search.search_by_reference([str(red)], top_n=1)
    assert results[0][0] == str(red)
