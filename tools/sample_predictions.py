# -*- coding: utf-8 -*-
"""用已保存模型对报告用例做真实预测，输出 JSON 供报告引用。"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.ml.predict import predict_text  # noqa: E402

cases = [
    "请问图书馆今晚几点关门？想去看书。",
    "有没有人一起拼车去高铁站，周日下午三点出发。",
    "兼职刷单日赚三百，加微信 13800000000 详聊。",
    "出一本高等数学教材，九成新，30 元，信息楼自取。",
    "低价代发各类广告，扫码进群领取名额。",
    "zxqv 8492 hjkl",
]

results = []
for content in cases:
    try:
        r = predict_text(content)
        results.append({"content": content, **asdict(r)})
    except ValueError as e:
        results.append({"content": content, "error": str(e)})

try:
    predict_text("   ")
except ValueError as e:
    results.append({"content": "   ", "error": str(e)})

print(json.dumps(results, ensure_ascii=False, indent=2))
