"""读取训练特征，训练手写朴素贝叶斯并保存模型和词表。"""

import argparse
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import load_npz

from backend.app.ml.dataset import PROJECT_ROOT
from backend.app.ml.features import DEFAULT_FEATURE_DIR, load_training_vectorizer
from backend.app.ml.naive_bayes import MultinomialNaiveBayes


DEFAULT_MODEL_PATH = PROJECT_ROOT / "artifacts" / "models" / "baseline" / "pipeline.joblib"


def train_model(feature_dir=DEFAULT_FEATURE_DIR, model_path=DEFAULT_MODEL_PATH, alpha=1.0, model_name="baseline_v1"):
    feature_dir = Path(feature_dir)
    model_path = Path(model_path)
    if model_path.exists():
        raise FileExistsError(f"模型文件已存在，请为新版本指定其他路径：{model_path}")

    X_train = load_npz(feature_dir / "X_train.npz")
    y_train = np.load(feature_dir / "y_train.npy", allow_pickle=False)
    vectorizer = load_training_vectorizer(feature_dir / "vocabulary.json")
    model = MultinomialNaiveBayes(alpha=alpha).fit(X_train, y_train)
    artifact = {
        "format_version": 1,
        "model_name": model_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "vectorizer": vectorizer,
        "training_sample_count": X_train.shape[0],
        "vocabulary_size": len(vectorizer.get_feature_names_out()),
        "alpha": model.alpha,
        "classes": model.classes_.tolist(),
        "threshold": 0.5,
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    # 已有模型不覆盖；保存失败时清理本次的半成品。
    output = model_path.open("xb")
    try:
        with output:
            joblib.dump(artifact, output, compress=3)
    except Exception:
        model_path.unlink(missing_ok=True)
        raise
    return artifact


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="训练朴素贝叶斯")
    parser.add_argument("--feature-dir", type=Path, default=DEFAULT_FEATURE_DIR)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--model-name", default="baseline_v1")
    parser.add_argument("--alpha", type=float, default=1.0)
    args = parser.parse_args()
    artifact = train_model(
        feature_dir=args.feature_dir, model_path=args.model_path,
        alpha=args.alpha, model_name=args.model_name,
    )
    print(f"模型：{artifact['model_name']}，alpha={artifact['alpha']}")
    print(f"训练样本：{artifact['training_sample_count']}，词表大小：{artifact['vocabulary_size']}")
    print(f"类别数量：{artifact['model'].class_count_}；保存位置：{args.model_path.resolve()}")
