from pathlib import Path

from PIL import Image

from core.icon_manager import install_custom_icon, selected_icon_path


class _Config:
    def __init__(self, value):
        self.value = value

    def get(self, key, default=None):
        return self.value if key == "app_icon" else default


def test_selected_icon_uses_bundled_presets():
    direct = selected_icon_path(_Config({"preset": "direct"}))
    minimal = selected_icon_path(_Config({"preset": "minimal"}))

    assert direct.name == "snapsort_icon.png"
    assert minimal.name == "snapsort_icon_minimal.png"
    assert direct.is_file()
    assert minimal.is_file()


def test_missing_custom_icon_falls_back_to_default(tmp_path):
    selected = selected_icon_path(
        _Config({"preset": "custom", "custom_path": str(tmp_path / "missing.png")})
    )

    assert selected.name == "snapsort_icon.png"


def test_install_custom_icon_creates_stable_png_and_ico(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGBA", (128, 128), (12, 100, 220, 200)).save(source)

    png_path, ico_path = install_custom_icon(source, tmp_path / "installed")

    assert png_path.is_file()
    assert ico_path.is_file()
    with Image.open(png_path) as installed:
        assert installed.mode == "RGBA"
        assert installed.size == (128, 128)


def test_install_custom_icon_rejects_tiny_image(tmp_path):
    source = tmp_path / "tiny.png"
    Image.new("RGBA", (16, 16), "blue").save(source)

    try:
        install_custom_icon(source, tmp_path / "installed")
    except ValueError as exc:
        assert "32×32" in str(exc)
    else:
        raise AssertionError("tiny icon should be rejected")
