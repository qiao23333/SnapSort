"""生成 SnapSort 2.0 界面预览图（Apple 风格）"""
from PIL import Image, ImageDraw, ImageFont

W, H = 1300, 900
img = Image.new("RGB", (W, H), "#F5F5F7")
draw = ImageDraw.Draw(img)

font_path = "/System/Library/Fonts/Hiragino Sans GB.ttc"
try:
    font_logo = ImageFont.truetype(font_path, 26, index=0)
    font_title = ImageFont.truetype(font_path, 22, index=0)
    font_h2 = ImageFont.truetype(font_path, 18, index=0)
    font_body = ImageFont.truetype(font_path, 14, index=0)
    font_small = ImageFont.truetype(font_path, 12, index=0)
    font_stat = ImageFont.truetype(font_path, 32, index=0)
except Exception:
    font_logo = font_title = font_h2 = font_body = font_small = font_stat = ImageFont.load_default()

# 侧边栏
sidebar_w = 240
draw.rectangle([0, 0, sidebar_w, H], fill="#FFFFFF")
draw.line([(sidebar_w, 0), (sidebar_w, H)], fill="#E8E8ED", width=1)

# Logo
draw.text((28, 32), "SnapSort", fill="#1D1D1F", font=font_logo)
draw.text((28, 64), "AI 素材分类器", fill="#6E6E73", font=font_body)

# 导航项
nav_items = [
    ("📊  仪表盘", True),
    ("🚀  自动分类", False),
    ("🖼  素材库", False),
    ("📜  历史记录", False),
    ("⚙️  设置", False),
]
y = 120
for label, active in nav_items:
    if active:
        draw.rounded_rectangle([16, y, sidebar_w-16, y+44], radius=8, fill="#E8F4FD")
        draw.text((28, y+11), label, fill="#0071E3", font=font_body)
    else:
        draw.text((28, y+11), label, fill="#1D1D1F", font=font_body)
    y += 52

# 底部
draw.text((28, H-70), "本地 AI · 隐私安全", fill="#6E6E73", font=font_small)
draw.text((28, H-50), "v2.0", fill="#6E6E73", font=font_small)

# 主内容区 x 偏移
x0 = sidebar_w + 32

# 标题
draw.text((x0, 36), "仪表盘", fill="#1D1D1F", font=font_title)
draw.text((x0, 72), "欢迎使用 SnapSort，一键整理你的素材照片", fill="#6E6E73", font=font_body)

# 统计卡片
card_h = 140
card_w = 230
gap = 18
cards = [
    ("📊", "1,248", "累计处理", "张图片"),
    ("🚀", "23", "分类任务", "次"),
    ("🗂", "186", "素材文件夹", "张待处理"),
    ("✅", "1,062", "输出文件夹", "张已分类"),
]
for i, (icon, value, title, sub) in enumerate(cards):
    cx = x0 + i * (card_w + gap)
    cy = 120
    draw.rounded_rectangle([cx, cy, cx+card_w, cy+card_h], radius=12, fill="#FFFFFF", outline="#E8E8ED", width=1)
    draw.text((cx+18, cy+16), icon, fill="#1D1D1F", font=font_title)
    draw.text((cx+18, cy+52), value, fill="#1D1D1F", font=font_stat)
    draw.text((cx+18, cy+92), title, fill="#6E6E73", font=font_body)
    draw.text((cx+18, cy+112), sub, fill="#6E6E73", font=font_small)

# 快速操作卡片
action_y = 280
draw.rounded_rectangle([x0, action_y, W-32, action_y+110], radius=12, fill="#FFFFFF", outline="#E8E8ED", width=1)
draw.text((x0+18, action_y+16), "快速操作", fill="#1D1D1F", font=font_h2)
# 按钮
draw.rounded_rectangle([x0+18, action_y+52, x0+180, action_y+88], radius=8, fill="#0071E3")
draw.text((x0+40, action_y+61), "🚀 开始自动分类", fill="white", font=font_body)
draw.rounded_rectangle([x0+196, action_y+52, x0+360, action_y+88], radius=8, fill="#FFFFFF", outline="#D2D2D7", width=1)
draw.text((x0+222, action_y+61), "🗂 选择素材文件夹", fill="#1D1D1F", font=font_body)
draw.rounded_rectangle([x0+376, action_y+52, x0+540, action_y+88], radius=8, fill="#FFFFFF", outline="#D2D2D7", width=1)
draw.text((x0+400, action_y+61), "📂 打开输出文件夹", fill="#1D1D1F", font=font_body)

# 最近任务卡片
recent_y = 410
draw.rounded_rectangle([x0, recent_y, W-32, H-32], radius=12, fill="#FFFFFF", outline="#E8E8ED", width=1)
draw.text((x0+18, recent_y+16), "最近任务", fill="#1D1D1F", font=font_h2)
draw.text((W-120, recent_y+20), "查看全部 ›", fill="#0071E3", font=font_body)

# 任务行
rows = [
    ("2026-06-23 14:32", "llava:13b", "186 张", "工厂图: 42, 人物肖像图: 18, 本地风景图: 35, 办公室图: 28, 合作洽谈图: 63"),
    ("2026-06-22 20:18", "llava:7b", "94 张", "工厂图: 21, 人物肖像图: 9, 本地风景图: 19, 办公室图: 15, 合作洽谈图: 30"),
    ("2026-06-22 18:05", "llava:13b", "56 张", "工厂图: 12, 人物肖像图: 5, 本地风景图: 11, 办公室图: 9, 合作洽谈图: 19"),
]
ry = recent_y + 56
for time_str, model, total, dist in rows:
    draw.rounded_rectangle([x0+16, ry, W-48, ry+68], radius=8, fill="#F2F2F7")
    draw.text((x0+32, ry+12), time_str, fill="#1D1D1F", font=font_body)
    draw.text((x0+32, ry+34), f"模型：{model} ｜ 共 {total} ｜ 耗时 142s", fill="#6E6E73", font=font_small)
    draw.text((W-48-20-draw.textlength(dist, font=font_small), ry+24), dist, fill="#6E6E73", font=font_small)
    ry += 80

out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "preview_v2.png")
img.save(out_path)
print("预览图已生成：preview_v2.png")
