# -*- coding: utf-8 -*-
"""把四张界面截图拼成一张报告插图。"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SHOTS = Path(__file__).resolve().parent / "shots"
OUT = Path(__file__).resolve().parent / "figs" / "fig_ui.png"

FONT = r"C:\Windows\Fonts\msyh.ttc"

items = [
    ("messages.png", "（a）留言管理页：发布表单、列表切换、检索与删除"),
    ("classification.png", "（b）分类标注页：模型结论、主要依据与人工纠正"),
    ("review.png", "（c）留言审核页：待审核列表与通过、驳回"),
    ("statistics.png", "（d）留言统计页：总量、类别分布与审核情况"),
]

CROP_H = 800          # 每张截图截取高度
CELL_W = 700          # 单元格宽度
IMG_H = int(CROP_H * CELL_W / 1440)
LABEL_H = 34
GAP = 14
MARGIN = 14

font = ImageFont.truetype(FONT, 20)
width = MARGIN * 2 + CELL_W * 2 + GAP
height = MARGIN * 2 + (LABEL_H + IMG_H) * 2 + GAP
canvas = Image.new("RGB", (width, height), "white")
draw = ImageDraw.Draw(canvas)

for index, (name, label) in enumerate(items):
    row, col = divmod(index, 2)
    x = MARGIN + col * (CELL_W + GAP)
    y = MARGIN + row * (LABEL_H + IMG_H + GAP)
    img = Image.open(SHOTS / name).convert("RGB")
    img = img.crop((0, 0, img.width, CROP_H)).resize((CELL_W, IMG_H), Image.LANCZOS)
    canvas.paste(img, (x, y + LABEL_H))
    draw.rectangle([x - 1, y + LABEL_H - 1, x + CELL_W, y + LABEL_H + IMG_H],
                   outline="#c8cdd2", width=1)
    draw.text((x + 2, y + 4), label, font=font, fill="#1f2933")

canvas.save(OUT, dpi=(200, 200))
print("saved", OUT, canvas.size)
