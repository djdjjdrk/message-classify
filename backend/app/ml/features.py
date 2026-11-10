"""jieba 分词和广告信号交给 sklearn 的 TF-IDF 向量器处理。"""

import re

from sklearn.feature_extraction.text import TfidfVectorizer

from backend.app.ml.preprocessing import TextPreprocessor


_preprocessor = TextPreprocessor()
AD_SIGNAL_PATTERNS = (
    ("contact", re.compile(r"微信|wx|vx|qq|公众号|扫码|私聊|私信|联系我|加我|群")),
    ("money", re.compile(r"收益|赚钱|赚|返利|返现|提现|回本|稳赚|日赚|月入|暴富|翻倍|投资|股票|彩票|博彩|赌")),
    ("service", re.compile(r"出售|低价|免费|领取|优惠|代发|刷单|兼职|代理|招商|课程|名额")),
    ("medical", re.compile(r"治疗|疗效|疗程|病|医院|药|美白|祛斑|减肥|养生")),
    ("gamble", re.compile(r"博彩|彩票|六合彩|快三|时时彩|赌|包赢|返利|回本|充值|首充|上分|投注|开奖")),
)


def tokenize(content):
    """中文分词，过滤空白和纯标点。"""
    return _preprocessor.tokenize(content)


def ad_signal_tokens(content):
    tokens = []
    for name, pattern in AD_SIGNAL_PATTERNS:
        count = min(len(pattern.findall(content)), 3)
        tokens.extend([f"__ad_{name}__"] * count)
    return tokens


def tokenize_with_signals(content):
    words = tokenize(content)
    if not words:
        return []
    return words + ad_signal_tokens(content)


def create_vectorizer():
    return TfidfVectorizer(
        tokenizer=tokenize_with_signals, token_pattern=None, lowercase=False,
        min_df=2, sublinear_tf=True,
    )
