"""训练与预测共用的文本预处理，不改变已有规范化和分词规则。"""

import jieba

from backend.app.ml.dataset import normalize_content


class TextPreprocessor:
    def normalize(self, content: str) -> str:
        return normalize_content(content)

    def tokenize(self, content: str) -> list[str]:
        """保留含文字或数字的词，过滤空白和纯标点；保留英文大小写。"""
        return [
            word for word in jieba.lcut(self.normalize(content))
            if any(char.isalnum() for char in word)
        ]
