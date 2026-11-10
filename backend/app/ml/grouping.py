"""按正文模板及近似重复的连通分量隔离数据，不改正文或标签。"""

import hashlib
import re
from collections import Counter
from difflib import SequenceMatcher

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.neighbors import NearestNeighbors

from backend.app.ml.dataset import normalize_content


URL = re.compile(r"https?://[a-z0-9./?&=%#:@+~_-]+|(?:[a-z0-9-]+\.)+(?:com|cn|top|cc|net|xyz|vip|org)(?:/[a-z0-9./?&=%#:@+~_-]*)?", re.I)


def template_key(content):
    """只用于分组；沿用已有广告去重规则，不把掩码作为分类特征。"""
    text = normalize_content(content)
    text = re.sub(r"\[em\].*?\[/em\]", "", text, flags=re.I)
    text = re.sub(r"/(?:比心|玫瑰|爱心|汪汪|期待|色|沧桑|捂脸|笑哭)", "", text)
    text = URL.sub("网址", text)
    text = re.sub(r"(?:微信|微|薇信|vx|wx|qq|企鹅|扣扣)\s*[:：+➕= ]*\s*[a-z0-9_.-]{3,}", "联系账号", text, flags=re.I)
    text = re.sub(r"\d{5,}", "号码", text)
    text = re.sub(r"\d+(?:\.\d+)?\s*(?:元|米|块|刀|r\b)", "金额", text, flags=re.I)
    text = re.sub(r"(?<![a-z])dy(?![a-z])|斗音|都音|某音|dou音", "抖音", text, flags=re.I)
    text = re.sub(r"小红薯|小红📕|(?<!小)红薯|(?<!小)红书", "小红书", text)
    text = re.sub(r"[抄炒超吵钞]小说", "抄小说", text)
    text = re.sub(r"代fa", "代发", text, flags=re.I)
    text = re.sub(r"\d+(?:\.\d+)?", "数值", text)
    text = "".join(char for char in text.casefold() if char.isalnum())
    while len(text) >= 24 and len(text) % 2 == 0 and text[:len(text)//2] == text[len(text)//2:]:
        text = text[:len(text)//2]
    return text or normalize_content(content)


def build_template_groups(samples, cosine_threshold=0.70, sequence_threshold=0.90):
    """固定阈值；跨来源、跨标签合并相似边，包含传递关系 A≈B≈C。"""
    if not (0 < cosine_threshold <= 1 and 0 < sequence_threshold <= 1):
        raise ValueError("相似度阈值必须在 (0, 1] 内")
    keys = [template_key(row["content"]) for row in samples]
    seen = {}
    edges = []
    for index, key in enumerate(keys):
        if key in seen:
            other = seen[key]
            edges.append({"left": other, "right": index, "method": "template", "cosine": 1.0, "sequence": 1.0})
        else:
            seen[key] = index
    # 只在唯一模板代表间构建图，防止重复大组导致二次方边数。
    representatives = list(seen.values())
    usable = [i for i in representatives if len(keys[i]) >= 2]
    if len(usable) > 1:
        matrix = TfidfVectorizer(analyzer="char", ngram_range=(2, 4)).fit_transform(keys[i] for i in usable)
        graph = NearestNeighbors(metric="cosine", algorithm="brute", radius=1-cosine_threshold).fit(matrix).radius_neighbors_graph(matrix, mode="distance")
        for local, index in enumerate(usable):
            start, end = graph.indptr[local:local+2]
            for neighbor, distance in zip(graph.indices[start:end], graph.data[start:end]):
                if neighbor <= local:
                    continue
                other = usable[neighbor]
                # 长度差过大时，序列相似度的理论上限已低于阈值。
                if 2 * min(len(keys[index]), len(keys[other])) / (len(keys[index]) + len(keys[other])) < sequence_threshold:
                    continue
                ratio = SequenceMatcher(None, keys[index], keys[other], autojunk=False).ratio()
                if ratio >= sequence_threshold:
                    edges.append({"left": index, "right": other, "method": "near_duplicate", "cosine": float(1-distance), "sequence": ratio})
    # 相似边组成稀疏图，连通分量交给 SciPy 计算。
    adjacency = csr_matrix((
        np.ones(len(edges)),
        ([edge["left"] for edge in edges], [edge["right"] for edge in edges]),
    ), shape=(len(samples), len(samples)))
    _, components = connected_components(adjacency, directed=False)
    members = {}
    for index, key in enumerate(keys):
        members.setdefault(components[index], []).append(key)
    ids = {index: hashlib.sha256(min(group).encode("utf-8")).hexdigest() for index, group in members.items()}
    groups = [ids[component] for component in components]
    sizes = Counter(groups)
    return groups, {
        "cosine_threshold": cosine_threshold, "sequence_threshold": sequence_threshold,
        "group_count": len(sizes), "multi_sample_groups": sum(size > 1 for size in sizes.values()),
        "largest_group": max(sizes.values(), default=0), "edges": edges,
    }


def grouped_holdout_indices(samples, groups, n_splits=5, random_state=42):
    """预先固定第一折为测试集，不根据模型得分挑选随机种子或折。"""
    if len(samples) != len(groups):
        raise ValueError("分组与样本数量不一致")
    labels = np.array([int(row["label"]) for row in samples])
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    train, test = next(splitter.split(np.zeros(len(samples)), labels, groups))
    if set(labels[train]) != {0, 1} or set(labels[test]) != {0, 1}:
        raise ValueError("模板组不足以使训练集和测试集同时包含两类；请补充数据")
    if {groups[i] for i in train} & {groups[i] for i in test}:
        raise ValueError("训练集与测试集存在模板组交叉")
    return train, test
