# -*- coding: utf-8 -*-
"""生成报告插图：系统分层结构图与两种评估口径的混淆矩阵。"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "figs"
OUT.mkdir(exist_ok=True)

FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def center_text(draw, box, text, f, fill="#1f1f1f"):
    x0, y0, x1, y1 = box
    bbox = draw.textbbox((0, 0), text, font=f)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((x0 + x1 - w) / 2 - bbox[0], (y0 + y1 - h) / 2 - bbox[1]), text, font=f, fill=fill)


def rounded(draw, box, fill, outline, radius=14, width=3):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def arrow(draw, x, y0, y1, color="#5b6b7b", width=4):
    draw.line([(x, y0), (x, y1 - 14)], fill=color, width=width)
    draw.polygon([(x - 10, y1 - 16), (x + 10, y1 - 16), (x, y1)], fill=color)


# ---------------- 图1：系统分层结构 ----------------
W, H = 1700, 1085
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)

layers = [
    ("前端展示层（Vue 3 + Vite）", "登录/注册 · 留言管理 · 分类标注 · 留言审核 · 留言统计", "#e8f1fb", "#5b8db8"),
    ("接口层（FastAPI 路由，JWT + 角色权限）", "auth · messages · classification · annotation · review · statistics", "#e9f6ec", "#5d9c6b"),
    ("业务服务层（service，事务与校验）", "发布与检索 · 审核 · 人工标注 · 统计聚合", "#fdf1e3", "#c08a4a"),
    ("数据访问层（SQLAlchemy 2.x ORM + Session）", "User / Message / AnnotationRecord / ReviewRecord", "#f0ecf9", "#7b6bb0"),
    ("数据库（MySQL 8，InnoDB / utf8mb4）", "users · messages · annotation_records · review_records", "#eceff2", "#6b7785"),
]

x0, x1 = 90, 1180
top, gap, bh = 70, 84, 120
boxes = []
for i, (title, sub, fill, line) in enumerate(layers):
    y = top + i * (bh + gap)
    box = (x0, y, x1, y + bh)
    boxes.append(box)
    rounded(d, box, fill, line, radius=16, width=4)
    center_text(d, (x0, y + 18, x1, y + 62), title, font(38, True))
    center_text(d, (x0, y + 66, x1, y + 104), sub, font(27), fill="#3d4a56")
    if i > 0:
        arrow(d, (x0 + x1) // 2, boxes[i - 1][3], y)

# 右侧：模型模块与说明
mx0, mx1 = 1270, 1630
ml_box = (mx0, 452, mx1, 700)
rounded(d, ml_box, "#f6e7f1", "#a8638e", radius=16, width=4)
center_text(d, (mx0, ml_box[1] + 12, mx1, ml_box[1] + 46), "机器学习模块", font(30, True))
ml_lines = ["TextPreprocessor", "jieba 分词", "TF-IDF + 广告信号", "MultinomialNB", "阈值 0.36"]
for k, line in enumerate(ml_lines):
    center_text(d, (mx0, ml_box[1] + 52 + k * 30, mx1, ml_box[1] + 80 + k * 30), line, font(22), fill="#4a3040")

# 双向箭头：业务层与模型模块
y_link = top + 2 * (bh + gap) + bh // 2
d.line([(x1 + 6, y_link), (mx0 - 8, y_link)], fill="#a8638e", width=4)
for xx, sign in ((x1 + 6, 1), (mx0 - 8, -1)):
    d.polygon([(xx + sign * 2, y_link - 10), (xx + sign * 2, y_link + 10), (xx + sign * 16, y_link)], fill="#a8638e")

# 左侧标注：请求方向
d.text((90, 22), "请求自上而下，数据自下而上", font=font(26), fill="#6b7785")
# 底部：模型文件
note_y = top + 5 * (bh + gap) - 55
center_text(d, (x0, note_y, x1, note_y + 44),
            "模型文件 artifacts/models/final/pipeline.joblib 保存向量器、分类器与阈值", font(25), fill="#5b6b7b")

img.save(OUT / "fig_pipeline.png", dpi=(200, 200))
print("saved", OUT / "fig_pipeline.png")

# ---------------- 图2：混淆矩阵 ----------------
W2, H2 = 1600, 700
img2 = Image.new("RGB", (W2, H2), "white")
d2 = ImageDraw.Draw(img2)

panels = [
    {
        "title": "同分布测试集（817 条）",
        "cells": [["TN = 502", "FP = 15"], ["FN = 0", "TP = 300"]],
        "rates": [["正常判对 97.10%", "正常误判 2.90%"], ["垃圾漏判 0.00%", "垃圾检出 100.00%"]],
        "hits": [(True, False), (False, True)],
    },
    {
        "title": "IAD 来源压力测试（613 条）",
        "cells": [["TN = 502", "FP = 15"], ["FN = 20", "TP = 76"]],
        "rates": [["正常判对 97.10%", "正常误判 2.90%"], ["垃圾漏判 20.83%", "垃圾检出 79.17%"]],
        "hits": [(True, False), (False, True)],
    },
]

for p, panel in enumerate(panels):
    ox = 130 + p * 780
    oy = 130
    # 标题
    center_text(d2, (ox - 90, 40, ox + 520, 96), panel["title"], font(32, True))
    # 列标题
    center_text(d2, (ox, 96, ox + 240, 132), "预测正常", font(24), fill="#3d4a56")
    center_text(d2, (ox + 240, 96, ox + 480, 132), "预测垃圾", font(24), fill="#3d4a56")
    for r in range(2):
        y = oy + r * 200
        label = "实际正常" if r == 0 else "实际垃圾"
        # 行标题（竖排改为横排小字）
        center_text(d2, (ox - 128, y, ox - 8, y + 200), "", font(20))
        for c in range(2):
            x = ox + c * 240
            hit = panel["hits"][r][c]
            fill = "#e7f4e9" if hit else "#fbe8e6"
            line = "#5d9c6b" if hit else "#c0675d"
            rounded(d2, (x, y, x + 236, y + 196), fill, line, radius=12, width=3)
            center_text(d2, (x, y + 34, x + 236, y + 92), panel["cells"][r][c], font(34, True))
            center_text(d2, (x, y + 104, x + 236, y + 150), panel["rates"][r][c], font(21), fill="#4a4f55")
        # 行标题
        center_text(d2, (ox - 132, y + 62, ox - 12, y + 138), "正常" if r == 0 else "垃圾", font(24), fill="#3d4a56")

d2.text((130, H2 - 92), "注：同分布测试正常 517 条、垃圾 300 条；来源压力测试正常 517 条、IAD 广告 96 条。",
        font=font(22), fill="#6b7785")
d2.text((130, H2 - 58), "准确率分别为 98.16%、94.29%；平衡准确率分别为 98.55%、88.13%。",
        font=font(22), fill="#6b7785")

img2.save(OUT / "fig_confusion.png", dpi=(200, 200))
print("saved", OUT / "fig_confusion.png")
