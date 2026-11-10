"""pandas 读写固定训练样本，文本规范化供 jieba 分词使用。"""

import re
import unicodedata
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
DEFAULT_DATA_DIR = BACKEND_ROOT / "data" / "processed"
DEFAULT_SPLIT_DIR = BACKEND_ROOT / "data" / "split"
DEFAULT_MODEL_PATH = BACKEND_ROOT / "artifacts" / "models" / "final" / "pipeline.joblib"
COLUMNS = ["content", "label", "source"]


def read_csv(file_path):
    file_path = Path(file_path)
    try:
        frame = pd.read_csv(file_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return []
    frame["source"] = frame.get("source", file_path.stem)
    frame["source"] = frame["source"].replace("", file_path.stem)
    return frame[COLUMNS].to_dict("records")


def normalize_content(content):
    """统一全半角、不可见字符和连续空白。"""
    content = unicodedata.normalize("NFKC", content)
    characters = []
    for char in content:
        if unicodedata.category(char) != "Cf":
            characters.append(char)
    return re.sub(r"\s+", " ", "".join(characters)).strip()


def save_dataset(samples, file_path):
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(samples, columns=COLUMNS, dtype=object).to_csv(
        file_path, index=False, encoding="utf-8-sig",
    )
