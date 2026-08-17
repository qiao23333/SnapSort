#!/usr/bin/env python3
"""Generate SnapSort app icon"""
from PIL import Image, ImageDraw, ImageFont
import math

def create_icon(size=256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background: rounded square with gradient
    margin = size // 8
    radius = size // 5

    # Draw rounded rectangle
    bbox = [margin, margin, size - margin, size - margin]
    draw.rounded_rectangle(bbox, radius=radius, fill=(29, 29, 31, 255))

    # Draw inner highlight
    highlight_bbox = [margin + 4, margin + 4, size - margin - 4, size - margin - 4]
    draw.rounded_rectangle(highlight_bbox, radius=radius - 4, fill=(45, 45, 48, 255))

    # Draw camera lens circle
    cx, cy = size // 2, size // 2
    lens_r = size // 4
    draw.ellipse(
        [cx - lens_r, cy - lens_r, cx + lens_r, cy + lens_r],
        fill=(255, 255, 255, 230),
        outline=(200, 200, 200, 100),
        width=2,
    )

    # Inner lens
    inner_r = lens_r // 2 + 4
    draw.ellipse(
        [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
        fill=(29, 29, 31, 255),
    )

    # Lens reflection
    refl_r = inner_r // 3
    draw.ellipse(
        [cx - refl_r - 6, cy - refl_r - 6, cx + refl_r - 10, cy + refl_r - 10],
        fill=(120, 120, 125, 200),
    )

    # Top: sorting arrows (up/down)
    arrow_y = margin + size // 12
    arrow_size = size // 14
    # Up arrow
    ax = cx - size // 5
    draw.polygon([
        (ax, arrow_y - arrow_size),
        (ax - arrow_size, arrow_y + arrow_size),
        (ax + arrow_size, arrow_y + arrow_size),
    ], fill=(100, 200, 150, 255))
    # Down arrow
    ax2 = cx + size // 5
    draw.polygon([
        (ax2, arrow_y + arrow_size),
        (ax2 - arrow_size, arrow_y - arrow_size),
        (ax2 + arrow_size, arrow_y - arrow_size),
    ], fill=(200, 100, 100, 255))

    return img

if __name__ == "__main__":
    icon = create_icon(256)
    icon.save("data/snapsort_icon.png", "PNG")
    icon_small = create_icon(64)
    icon_small.save("data/snapsort_icon_small.png", "PNG")
    print("Icon generated: data/snapsort_icon.png")
