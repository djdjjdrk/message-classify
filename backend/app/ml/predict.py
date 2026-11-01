"""加载已保存的词频向量器及手写分类器，预测单条原文；不训练。"""

import argparse
import json
from dataclasses import asdict, dataclass, field
from typing import Literal, TypedDict

import joblib

from backend.app.ml.train import DEFAULT_MODEL_PATH


class WordContribution(TypedDict):
    word: str
    count: int
    contribution: float
    direction: Literal["normal", "spam"]


@dataclass
class PredictionResult:
    status: Literal["success", "no_features"]
    model_name: str
    label: int | None = None
    spam_probability: float | None = None
    explanation: list[WordContribution] = field(default_factory=list)


def predict_text(content: str, model_path=DEFAULT_MODEL_PATH) -> PredictionResult:
    """空原文抛出参数错误；全未知词拒判；部分未知词由 transform 忽略。"""
    if not content.strip():
        raise ValueError("留言内容不能为空")

    artifact = joblib.load(model_path)
    vectorizer = artifact["vectorizer"]
    model = artifact["model"]
    model_name = artifact["model_name"]
    threshold = artifact["threshold"]

    # tokenizer 仍由 artifact 内的向量器调用；线上不额外处理一遍原文。
    row = vectorizer.transform([content]).tocsr()
    if row.nnz == 0:
        return PredictionResult(status="no_features", model_name=model_name)

    probability = float(model.predict_proba(row)[0, 1])
    label = int(probability >= threshold)
    direction = "spam" if label == 1 else "normal"
    words = vectorizer.get_feature_names_out()
    contributions: list[WordContribution] = []
    for index, count in zip(row.indices, row.data):
        value = float(count * (model.feature_log_prob_[1, index] - model.feature_log_prob_[0, index]))
        if value == 0:
            continue
        contributions.append({
            "word": str(words[index]),
            "count": int(count),
            "contribution": value,
            "direction": "spam" if value > 0 else "normal",
        })
    # 先选支持预测类别的词，再按贡献绝对值排序；不以词频充当依据。
    contributions.sort(key=lambda item: (
        item["direction"] != direction, -abs(item["contribution"]), item["word"],
    ))
    return PredictionResult(
        status="success", model_name=model_name, label=label,
        spam_probability=probability, explanation=contributions[:5],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="使用已有模型预测一条原文，不重新训练")
    parser.add_argument("content")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    args = parser.parse_args()
    try:
        result = predict_text(args.content, args.model_path)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
