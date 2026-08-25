from pathlib import Path

from PIL import Image

from core.photo_metadata import read_photo_metadata, update_photo_metadata


def test_round_trip_editable_metadata_and_backup(tmp_path):
    photo = tmp_path / "photo.jpg"
    Image.new("RGB", (80, 60), "white").save(photo, "JPEG", quality=90)

    backup = update_photo_metadata(
        photo,
        {
            "date": "2026:08:24 10:30:00",
            "title": "样片",
            "description": "办公室里的产品包装",
            "author": "乔心",
            "copyright": "2026 乔心",
            "keywords": "工作;产品;包装",
            "rating": "4",
        },
    )
    values = read_photo_metadata(photo)

    assert backup == tmp_path / ".snapsort-backup" / "photo.jpg"
    assert backup.is_file()
    assert values["date"] == "2026:08:24 10:30:00"
    assert values["title"] == "样片"
    assert values["description"] == "办公室里的产品包装"
    assert values["author"] == "乔心"
    assert values["keywords"] == "工作;产品;包装"
    assert values["rating"] == "4"


def test_metadata_edit_rejects_unsafe_format(tmp_path):
    photo = tmp_path / "photo.bmp"
    Image.new("RGB", (40, 40), "white").save(photo)

    try:
        update_photo_metadata(photo, {})
    except ValueError as exc:
        assert "JPG" in str(exc)
    else:
        raise AssertionError("BMP metadata write should be rejected")
