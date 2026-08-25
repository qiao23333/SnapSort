#!/usr/bin/env python3
"""Build platform icon assets from the approved high-resolution master."""

from collections import deque
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
MASTER_PATH = DATA_DIR / "snapsort_icon_master.png"


def _remove_connected_dark_matte(source: Image.Image) -> Image.Image:
    """移除生成图四周连通的黑色衬底，不误伤图标内部阴影。

    部分图片生成器会返回 RGB 黑底而不是真正的透明 PNG。只从画布边缘
    洪泛暗色像素，比按全图亮度抠图更安全：图标内部的深蓝区域不会被删。
    """
    rgba = source.convert("RGBA")
    if source.mode == "RGBA" and source.getchannel("A").getextrema()[0] < 255:
        return rgba

    pixels = rgba.load()
    width, height = rgba.size
    queue = deque()
    visited = set()

    def enqueue(x, y):
        if (x, y) in visited:
            return
        r, g, b, _ = pixels[x, y]
        if max(r, g, b) <= 110:
            visited.add((x, y))
            queue.append((x, y))

    for x in range(width):
        enqueue(x, 0)
        enqueue(x, height - 1)
    for y in range(height):
        enqueue(0, y)
        enqueue(width - 1, y)

    while queue:
        x, y = queue.popleft()
        pixels[x, y] = (*pixels[x, y][:3], 0)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                enqueue(nx, ny)
    return rgba


def _render(master: Image.Image, size: int) -> Image.Image:
    """Downsample cleanly and add a tiny amount of small-size crispness."""
    icon = master.resize((size, size), Image.Resampling.LANCZOS)
    if size <= 64:
        icon = ImageEnhance.Contrast(icon).enhance(1.04)
        icon = icon.filter(ImageFilter.UnsharpMask(radius=0.6, percent=45, threshold=3))
    return icon


def build_icons() -> list[Path]:
    if not MASTER_PATH.exists():
        raise FileNotFoundError(f"缺少图标母版：{MASTER_PATH}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(MASTER_PATH) as source:
        master = _remove_connected_dark_matte(source)

    outputs = [
        DATA_DIR / "snapsort_icon.png",
        DATA_DIR / "snapsort_icon_small.png",
        DATA_DIR / "snapsort_icon.ico",
        DATA_DIR / "snapsort_icon.icns",
    ]

    _render(master, 256).save(outputs[0], "PNG", optimize=True)
    _render(master, 64).save(outputs[1], "PNG", optimize=True)

    ico_master = _render(master, 256)
    ico_master.save(
        outputs[2],
        "ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    _render(master, 1024).save(outputs[3], "ICNS")
    return outputs


if __name__ == "__main__":
    for output in build_icons():
        print(output.relative_to(ROOT))
