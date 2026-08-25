from pathlib import Path

import pytest

from core.model_info import get_model_hint
from core import reference_manager
from core.reference_manager import _type_dir
from core.rule_engine import RuleAction


def test_rule_action_rejects_parent_directory(tmp_path):
    source = tmp_path / "source.jpg"
    source.write_bytes(b"image")
    output = tmp_path / "output"
    ok, message, path = RuleAction(
        {"type": "copy", "target_dir": "../outside"}
    ).execute(str(source), str(output))
    assert not ok
    assert path is None
    assert "不安全" in message
    assert not (tmp_path / "outside").exists()


def test_rule_copy_does_not_overwrite(tmp_path):
    source = tmp_path / "source.jpg"
    source.write_bytes(b"new")
    target = tmp_path / "output" / "精选"
    target.mkdir(parents=True)
    (target / "source.jpg").write_bytes(b"old")
    ok, _, copied = RuleAction(
        {"type": "copy", "target_dir": "精选"}
    ).execute(str(source), str(tmp_path / "output"))
    assert ok
    assert Path(copied).name == "source_001.jpg"
    assert (target / "source.jpg").read_bytes() == b"old"


def test_reference_type_is_restricted():
    with pytest.raises(ValueError):
        _type_dir("../outside")


def test_target_reference_type_is_supported(tmp_path, monkeypatch):
    monkeypatch.setattr(reference_manager, "_ROOT", tmp_path / "refs")
    assert _type_dir("target") == tmp_path / "refs" / "target"


def test_specific_model_hint_wins():
    assert "Gemma2" in get_model_hint("gemma2:9b")
