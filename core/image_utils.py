#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图片工具：HEIC 转换、base64 编码、缩略图生成、位图转矢量"""
import os
import io
import base64
import subprocess
import tempfile
from pathlib import Path
from collections import defaultdict
import math

from PIL import Image, ImageFilter, ImageDraw

# ── HEIC/HEIF 支持 ──
# 在模块加载时注册 HEIF opener，使 PIL.Image.open 能直接读 HEIC
_HEIF_REGISTERED = False
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    _HEIF_REGISTERED = True
except ImportError:
    pass


SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif",
                  ".bmp", ".tiff", ".gif", ".tif")


def is_image_file(path):
    ext = os.path.splitext(path)[1].lower()
    return ext in SUPPORTED_EXTS


def convert_heic_to_jpeg(image_path):
    """将 HEIC/HEIF 转换为可被 PIL 读取的格式，返回可用的图片路径。
    
    如果 pillow_heif 已注册，PIL 可直接打开 HEIC，返回原路径。
    否则尝试用 macOS sips 转换。
    转换失败时抛出异常而非静默返回，方便调用方捕获。
    """
    ext = os.path.splitext(image_path)[1].lower()
    if ext not in (".heic", ".heif"):
        return image_path

    # 如果 pillow_heif 已注册，PIL 可以直接打开 HEIC，无需转换
    if _HEIF_REGISTERED:
        return image_path

    # 尝试 macOS sips
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".jpg", prefix="snapsort_")
    os.close(tmp_fd)
    try:
        subprocess.run(
            ["sips", "-s", "format", "jpeg", image_path, "--out", tmp_path],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30
        )
        if os.path.getsize(tmp_path) > 0:
            return tmp_path
        os.unlink(tmp_path)
    except subprocess.CalledProcessError as e:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise ValueError(
            f"HEIC 转换失败：sips 转换出错。\n"
            f"请安装 pillow-heif: pip install pillow-heif\n"
            f"错误详情: {e.stderr.decode('utf-8', errors='replace') if e.stderr else str(e)}"
        )
    except FileNotFoundError:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise ValueError(
            f"HEIC 转换失败：找不到 sips 命令（仅 macOS 可用）。\n"
            f"请安装 pillow-heif: pip install pillow-heif"
        )
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise ValueError(f"HEIC 转换失败：{e}")

    return image_path


def _safe_open_image(image_path):
    """安全打开图片，处理 HEIC/HEIF 格式，返回 (PIL Image, 实际打开的路径)。

    返回的路径为临时文件时（HEIC 经 sips 转换），调用方用完后须自行清理。
    """
    jpeg_path = convert_heic_to_jpeg(image_path)
    img = Image.open(jpeg_path)
    # 确保 RGBA 图片在白底上合成
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode == "P":
        img = img.convert("RGB")
    elif img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img, jpeg_path


def _cleanup_temp(opened_path, original_path):
    """清理 HEIC 转换产生的临时文件（opened_path 为原路径时无操作）"""
    if opened_path and opened_path != original_path:
        try:
            os.unlink(opened_path)
        except OSError:
            pass


def encode_image(image_path, max_size_kb=1024):
    """将图片转为 base64，HEIC/HEIF 会先转成 JPEG，并限制尺寸"""
    img, opened_path = _safe_open_image(image_path)
    try:
        # 限制长边
        max_side = 1600
        w, h = img.size
        if max(w, h) > max_side:
            ratio = max_side / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
        data = buf.getvalue()

        # 如果还太大，进一步压缩
        if len(data) > max_size_kb * 1024:
            quality = 70
            while len(data) > max_size_kb * 1024 and quality > 30:
                buf = io.BytesIO()
                img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
                data = buf.getvalue()
                quality -= 10

        return base64.b64encode(data).decode("utf-8")
    finally:
        _cleanup_temp(opened_path, image_path)


def make_thumbnail(image_path, size=(120, 120), quality=85):
    """生成缩略图，返回 PIL Image 对象"""
    opened = None
    try:
        img, opened = _safe_open_image(image_path)
        img.thumbnail(size, Image.LANCZOS)
        return img
    except Exception:
        return None
    finally:
        _cleanup_temp(opened, image_path)


def image_count_and_size(directory):
    """统计目录下图片数量和总大小"""
    total = 0
    total_size = 0
    if not os.path.isdir(directory):
        return 0, 0
    for f in os.listdir(directory):
        path = os.path.join(directory, f)
        if os.path.isfile(path) and is_image_file(path):
            total += 1
            total_size += os.path.getsize(path)
    return total, total_size


def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


# ====================================================================
# 位图转矢量 — Marching Squares 算法
# ====================================================================

def _rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _find_potrace():
    """查找系统是否安装了 potrace"""
    for cmd in ["potrace", "potrace.exe"]:
        try:
            result = subprocess.run([cmd, "-v"], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=2)
            if result.returncode == 0 or result.returncode == 1:
                return cmd
        except Exception:
            continue
    return None


def _marching_squares_contours(mask, w, h):
    """
    Marching Squares 等值线提取，带线性插值。
    
    mask: 二维 bool 列表 (h 行 w 列)，True = 前景
    返回: list of contours, 每条轮廓是 [(x, y), ...] 浮点坐标列表
    """
    contours = []
    
    # 遍历每个 2x2 cell
    # cell 的四个角: (x,y), (x+1,y), (x+1,y+1), (x,y+1)
    # 我们使用浮点坐标，像素中心在整数坐标处
    
    # 先收集所有线段
    segments = []
    
    for y in range(h - 1):
        for x in range(w - 1):
            # 四个角的值
            tl = mask[y][x]       # top-left
            tr = mask[y][x + 1]   # top-right
            br = mask[y + 1][x + 1]  # bottom-right
            bl = mask[y + 1][x]   # bottom-left
            
            code = (tl << 3) | (tr << 2) | (br << 1) | bl
            
            if code == 0 or code == 15:
                continue
            
            # 计算四条边上的交点（线性插值）
            # top edge: between (x,y) and (x+1,y)
            # right edge: between (x+1,y) and (x+1,y+1)
            # bottom edge: between (x,y+1) and (x+1,y+1)
            # left edge: between (x,y) and (x,y+1)
            
            def interp_top():
                # tl and tr differ
                t = 0.5
                return (x + t, float(y))
            
            def interp_right():
                t = 0.5
                return (float(x + 1), y + t)
            
            def interp_bottom():
                t = 0.5
                return (x + t, float(y + 1))
            
            def interp_left():
                t = 0.5
                return (float(x), y + t)
            
            # 根据 case 生成线段
            if code == 1 or code == 14:    # bl / ~bl
                segments.append((interp_left(), interp_bottom()))
            elif code == 2 or code == 13:  # br / ~br
                segments.append((interp_bottom(), interp_right()))
            elif code == 3 or code == 12:  # bl+br / ~bl+~br
                segments.append((interp_left(), interp_right()))
            elif code == 4 or code == 11:  # tr / ~tr
                segments.append((interp_top(), interp_right()))
            elif code == 5:                # bl+tr (saddle)
                segments.append((interp_left(), interp_top()))
                segments.append((interp_right(), interp_bottom()))
            elif code == 10:               # tl+br (saddle)
                segments.append((interp_left(), interp_bottom()))
                segments.append((interp_top(), interp_right()))
            elif code == 6 or code == 9:   # tr+br / ~tr+~br
                segments.append((interp_top(), interp_bottom()))
            elif code == 7 or code == 8:   # tl+tr+br / bl only
                segments.append((interp_left(), interp_top()))
    
    # 将线段连接成轮廓
    if not segments:
        return []
    
    # 构建端点到线段的映射
    # 使用四舍五入到一定精度作为键
    precision = 3
    
    def round_pt(p):
        return (round(p[0], precision), round(p[1], precision))
    
    # 每个端点对应哪些线段
    endpoint_map = defaultdict(list)
    for i, (p1, p2) in enumerate(segments):
        endpoint_map[round_pt(p1)].append((i, 0))
        endpoint_map[round_pt(p2)].append((i, 1))
    
    used = [False] * len(segments)
    
    for start_idx in range(len(segments)):
        if used[start_idx]:
            continue
        
        contour = []
        seg_idx = start_idx
        direction = 0  # 从 p1 开始
        
        while True:
            if used[seg_idx]:
                break
            used[seg_idx] = True
            
            if direction == 0:
                pt = segments[seg_idx][0]
                next_pt = segments[seg_idx][1]
            else:
                pt = segments[seg_idx][1]
                next_pt = segments[seg_idx][0]
            
            contour.append(pt)
            
            # 找下一条连接的线段
            key = round_pt(next_pt)
            found_next = False
            for sidx, sdir in endpoint_map[key]:
                if not used[sidx]:
                    seg_idx = sidx
                    direction = sdir
                    found_next = True
                    break
            
            if not found_next:
                contour.append(next_pt)
                break
        
        if len(contour) >= 3:
            contours.append(contour)
    
    return contours


def _douglas_peucker(points, tol_sq=2.25):
    """Douglas-Peucker 路径简化"""
    if len(points) < 3:
        return list(points)
    
    x1, y1 = points[0]
    x2, y2 = points[-1]
    max_dist = 0.0
    max_idx = 0
    for i in range(1, len(points) - 1):
        px, py = points[i]
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            d = (px - x1) ** 2 + (py - y1) ** 2
        else:
            t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            d = (px - proj_x) ** 2 + (py - proj_y) ** 2
        if d > max_dist:
            max_dist = d
            max_idx = i
    
    if max_dist > tol_sq:
        left = _douglas_peucker(points[:max_idx + 1], tol_sq)
        right = _douglas_peucker(points[max_idx:], tol_sq)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]


def _points_to_smooth_svg_path(points, closed=True):
    """将点列表转为平滑 SVG path（Catmull-Rom 转贝塞尔曲线）"""
    if not points or len(points) < 2:
        return ""
    if len(points) < 3:
        d = f"M{points[0][0]:.1f} {points[0][1]:.1f}"
        for p in points[1:]:
            d += f" L{p[0]:.1f} {p[1]:.1f}"
        if closed:
            d += " Z"
        return d

    n = len(points)
    parts = [f"M{points[0][0]:.1f} {points[0][1]:.1f}"]

    for i in range(n):
        p0 = points[(i - 1) % n] if closed else points[max(0, i - 1)]
        p1 = points[i]
        p2 = points[(i + 1) % n] if closed else points[min(n - 1, i + 1)]
        p3 = points[(i + 2) % n] if closed else points[min(n - 1, i + 2)]

        # Catmull-Rom 转 Bezier 控制点
        cp1x = p1[0] + (p2[0] - p0[0]) / 6
        cp1y = p1[1] + (p2[1] - p0[1]) / 6
        cp2x = p2[0] - (p3[0] - p1[0]) / 6
        cp2y = p2[1] - (p3[1] - p1[1]) / 6

        parts.append(
            f"C{cp1x:.1f} {cp1y:.1f} {cp2x:.1f} {cp2y:.1f} {p2[0]:.1f} {p2[1]:.1f}"
        )

    if closed:
        parts.append("Z")
    return " ".join(parts)


def _points_to_svg_path(points, closed=False):
    """将点列表转为 SVG path（直线段）"""
    if not points or len(points) < 2:
        return ""
    parts = [f"M{points[0][0]:.1f} {points[0][1]:.1f}"]
    for p in points[1:]:
        parts.append(f"L{p[0]:.1f} {p[1]:.1f}")
    if closed:
        parts.append("Z")
    return " ".join(parts)


def _kmeans_quantize(img, n_colors):
    """简单的 k-means 颜色量化（比 MEDIANCUT 效果更好）"""
    # 先用 PIL 的 quantize 做初步量化
    if n_colors <= 2:
        n_colors = 2
    
    # 使用 MEDIANCUT 做初步量化，然后用 k-means 优化
    quantized = img.convert("RGB").quantize(
        colors=n_colors, method=Image.Quantize.MEDIANCUT
    )
    
    # 获取调色板和量化后的像素
    palette = quantized.getpalette()[:n_colors * 3]
    pixels = list(quantized.getdata())
    
    # 转为 RGB
    rgb_img = quantized.convert("RGB")
    
    return rgb_img, n_colors


def _otsu_threshold(gray_img):
    """Otsu 自动阈值"""
    hist = gray_img.histogram()
    total = sum(hist)
    sum_all = sum(i * hist[i] for i in range(256))
    sum_b = 0
    w_b = 0
    max_var = 0
    threshold = 128
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var_between = w_b * w_f * (m_b - m_f) ** 2
        if var_between > max_var:
            max_var = var_between
            threshold = t
    return threshold


def _vectorize_photo_mode(img, max_colors, max_size):
    """照片风格化矢量：颜色量化 + Marching Squares 轮廓追踪 + 平滑路径"""
    # 缩放到合适尺寸
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    w, h = img.size
    
    # 轻微模糊平滑噪声
    img = img.filter(ImageFilter.SMOOTH)
    
    # 颜色量化
    rgb_img, n_colors = _kmeans_quantize(img, max_colors)
    
    # 获取每个像素的颜色索引
    quantized = rgb_img.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()[:n_colors * 3]
    indexed_pixels = list(quantized.getdata())
    
    # 为每个颜色创建二值掩码并用 marching squares 提取轮廓
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">',
    ]
    
    # 按颜色面积从大到小排序
    color_counts = defaultdict(int)
    for ci in indexed_pixels:
        color_counts[ci] += 1
    sorted_colors = sorted(color_counts.items(), key=lambda x: -x[1])
    
    # 先画最大色块作为背景
    if sorted_colors:
        bg_idx = sorted_colors[0][0]
        bg_rgb = tuple(palette[bg_idx * 3:bg_idx * 3 + 3])
        svg_parts.append(f'<rect width="{w}" height="{h}" fill="{_rgb_to_hex(bg_rgb)}"/>')
    
    # 为每个颜色提取轮廓
    for color_idx, count in sorted_colors[1:]:  # 跳过背景色
        if count < 20:  # 过滤太小的色块
            continue
        
        rgb = tuple(palette[color_idx * 3:color_idx * 3 + 3])
        hex_color = _rgb_to_hex(rgb)
        
        # 创建此颜色的二值掩码
        mask = [[False] * w for _ in range(h)]
        for idx in range(len(indexed_pixels)):
            if indexed_pixels[idx] == color_idx:
                mask[idx // w][idx % w] = True
        
        # Marching Squares 提取轮廓
        contours = _marching_squares_contours(mask, w, h)
        
        for contour in contours:
            if len(contour) < 6:  # 过滤太短的轮廓
                continue
            # 简化路径
            simplified = _douglas_peucker(contour, tol_sq=3.0)
            if len(simplified) < 4:
                continue
            # 平滑路径
            d = _points_to_smooth_svg_path(simplified, closed=True)
            if d:
                svg_parts.append(
                    f'<path d="{d}" fill="{hex_color}" stroke="none"/>'
                )
    
    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _morphological_close(mask, w, h):
    """形态学闭运算：先膨胀再腐蚀，填补小洞"""
    # 膨胀
    dilated = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w:
                            dilated[ny][nx] = True
    
    # 腐蚀
    eroded = [[False] * w for _ in range(h)]
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if dilated[y][x]:
                all_set = True
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        if not dilated[y + dy][x + dx]:
                            all_set = False
                            break
                    if not all_set:
                        break
                if all_set:
                    eroded[y][x] = True
    
    return eroded


def _vectorize_silhouette_mode(img, max_size):
    """黑白剪影矢量：Otsu 二值化 + Marching Squares 轮廓追踪"""
    # 缩放（高分辨率获得精细轮廓）
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    w, h = img.size
    
    # 转灰度并轻微模糊
    gray = img.convert("L").filter(ImageFilter.SMOOTH)
    
    # Otsu 阈值
    threshold = _otsu_threshold(gray)
    
    # 二值化
    pixels = list(gray.getdata())
    mask = [[False] * w for _ in range(h)]
    for idx, val in enumerate(pixels):
        if val < threshold:
            mask[idx // w][idx % w] = True
    
    # 形态学闭运算
    mask = _morphological_close(mask, w, h)
    
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="white"/>',
    ]
    
    # Marching Squares 提取轮廓
    contours = _marching_squares_contours(mask, w, h)
    
    for contour in contours:
        if len(contour) < 4:
            continue
        # 简化
        simplified = _douglas_peucker(contour, tol_sq=1.5)
        if len(simplified) < 3:
            continue
        d = _points_to_smooth_svg_path(simplified, closed=True)
        if d:
            svg_parts.append(
                f'<path d="{d}" fill="black" stroke="none" fill-rule="evenodd"/>'
            )
    
    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _vectorize_edge_mode(img, max_size):
    """边缘描边矢量：Sobel 边缘检测 + 路径输出"""
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    w, h = img.size
    
    # 先模糊再检测边缘，减少噪声
    gray = img.convert("L").filter(ImageFilter.SMOOTH)
    
    # Sobel 边缘检测
    edges = gray.filter(ImageFilter.FIND_EDGES)
    
    # 阈值化
    edge_pixels = list(edges.getdata())
    mask = [[False] * w for _ in range(h)]
    for idx, val in enumerate(edge_pixels):
        if val > 50:
            mask[idx // w][idx % w] = True
    
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">',
        f'<rect width="{w}" height="{h}" fill="white"/>',
    ]
    
    # Marching Squares 提取轮廓
    contours = _marching_squares_contours(mask, w, h)
    
    for contour in contours:
        if len(contour) < 4:
            continue
        simplified = _douglas_peucker(contour, tol_sq=1.5)
        # 过滤掉太短的路径（只有2个点且距离很近）
        if len(simplified) < 3:
            # 检查两个点是否足够远
            if len(simplified) == 2:
                dx = simplified[1][0] - simplified[0][0]
                dy = simplified[1][1] - simplified[0][1]
                if dx * dx + dy * dy < 4:
                    continue
            else:
                continue
        d = _points_to_svg_path(simplified, closed=False)
        if d:
            svg_parts.append(
                f'<path d="{d}" fill="none" stroke="black" '
                f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
            )
    
    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def bitmap_to_vector_svg(image_path, mode="photo", max_colors=8, max_size=500):
    """
    将位图转换为 SVG 矢量图。

    优先使用 VTracer（Rust 引擎，色彩保真度高），未安装时回退到内置算法。

    参数：
        image_path: 输入图片路径
        mode: "photo" 风格化照片(多色轮廓)，
              "silhouette" 黑白剪影(二值化+边界追踪)，
              "edge" 边缘描边(Sobel边缘检测)
        max_colors: 颜色量化数量（仅 photo 模式，2-16）
        max_size: 输出 SVG 画布最大边长（像素），越大越精细

    返回：
        SVG 字符串，或 None 表示失败
    """
    # ── VTracer 优先路径 ──
    opened_path = None
    try:
        import vtracer
        import tempfile

        # 模式映射
        if mode == "silhouette":
            colormode = "binary"
            vmode = "spline"
        elif mode == "edge":
            colormode = "binary"
            vmode = "none"
        else:
            colormode = "color"
            vmode = "spline"

        # 预处理：缩小到目标尺寸
        img, opened_path = _safe_open_image(image_path)
        if img is None:
            raise ValueError("无法打开图片")

        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            img = img.resize((int(img.width * ratio), int(img.height * ratio)),
                            Image.Resampling.LANCZOS)

        # 保存临时文件给 VTracer
        tmp_in = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp_in.close()
        tmp_out = tempfile.NamedTemporaryFile(suffix=".svg", delete=False)
        tmp_out.close()

        if mode == "silhouette":
            img = img.convert("L").point(lambda x: 0 if x < 128 else 255, "1")

        img.save(tmp_in.name, "PNG")

        vtracer.convert_image_to_svg_py(
            tmp_in.name,
            tmp_out.name,
            colormode=colormode,
            hierarchical="stacked",
            mode=vmode,
            filter_speckle=4,
            color_precision=max(2, min(8, max_colors)),
            layer_difference=16,
            corner_threshold=60,
            length_threshold=4.0,
            max_iterations=10,
            splice_threshold=45,
            path_precision=3,
        )

        with open(tmp_out.name, "r", encoding="utf-8") as f:
            svg = f.read()

        os.unlink(tmp_in.name)
        os.unlink(tmp_out.name)

        return svg

    except ImportError:
        pass  # VTracer 未安装，回退到内置算法
    except Exception:
        pass  # VTracer 失败，回退到内置算法
    finally:
        # 清理 HEIC 转换产生的临时文件（注意：绝不能动原文件）
        _cleanup_temp(opened_path, image_path)

    # ── 回退路径：内置 Moore 轮廓追踪 ──
    fallback_path = None
    try:
        img, fallback_path = _safe_open_image(image_path)
    except Exception as e:
        raise e
    
    try:
        if mode == "silhouette":
            # 优先 potrace（质量最好）
            potrace = _find_potrace()
            if potrace:
                try:
                    return _potrace_svg(img, potrace)
                except Exception:
                    pass
            return _vectorize_silhouette_mode(img, max_size)
        elif mode == "edge":
            return _vectorize_edge_mode(img, max_size)
        else:
            return _vectorize_photo_mode(img, max_colors, max_size)
    except Exception:
        return None
    finally:
        _cleanup_temp(fallback_path, image_path)


def _potrace_svg(img, potrace_cmd):
    """使用 potrace 生成 SVG（系统已安装时调用）"""
    gray = img.convert("L")
    threshold = _otsu_threshold(gray)
    bw = gray.point(lambda x: 0 if x < threshold else 255, "1")
    
    fd, pnm_path = tempfile.mkstemp(suffix=".pnm", prefix="snapsort_vec_")
    os.close(fd)
    bw.save(pnm_path)
    fd, svg_path = tempfile.mkstemp(suffix=".svg", prefix="snapsort_vec_")
    os.close(fd)
    subprocess.run(
        [potrace_cmd, "-s", "-o", svg_path, pnm_path],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60
    )
    with open(svg_path, "r", encoding="utf-8") as f:
        svg = f.read()
    for p in (pnm_path, svg_path):
        try:
            os.unlink(p)
        except Exception:
            pass
    return svg
