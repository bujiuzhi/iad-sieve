"""文本相似度工具。"""

from __future__ import annotations

import difflib
import logging
import math
import re
from collections import Counter


LOGGER = logging.getLogger(__name__)
TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_\-]*", re.IGNORECASE)


def tokenize(text: str | None) -> list[str]:
    """将文本切分为小写 token。

    参数:
        text: 输入文本。

    返回:
        token 列表。
    """
    if not text:
        return []
    try:
        return [token.lower() for token in TOKEN_PATTERN.findall(text)]
    except Exception:
        LOGGER.exception("文本切分失败")
        raise


def jaccard_similarity(left_text: str | None, right_text: str | None) -> float:
    """计算 token Jaccard 相似度。

    参数:
        left_text: 左侧文本。
        right_text: 右侧文本。

    返回:
        0 到 1 的相似度。
    """
    left_tokens = set(tokenize(left_text))
    right_tokens = set(tokenize(right_text))
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def sequence_similarity(left_text: str | None, right_text: str | None) -> float:
    """计算字符序列相似度。

    参数:
        left_text: 左侧文本。
        right_text: 右侧文本。

    返回:
        0 到 1 的相似度。
    """
    return difflib.SequenceMatcher(None, left_text or "", right_text or "").ratio()


def cosine_from_counters(left_tokens: list[str], right_tokens: list[str]) -> float:
    """使用词频 Counter 计算余弦相似度。

    参数:
        left_tokens: 左侧 token 列表。
        right_tokens: 右侧 token 列表。

    返回:
        0 到 1 的余弦相似度。
    """
    if not left_tokens or not right_tokens:
        return 0.0
    left_counter = Counter(left_tokens)
    right_counter = Counter(right_tokens)
    common = set(left_counter) & set(right_counter)
    dot_product = sum(left_counter[token] * right_counter[token] for token in common)
    left_norm = math.sqrt(sum(value * value for value in left_counter.values()))
    right_norm = math.sqrt(sum(value * value for value in right_counter.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def vector_cosine(left_vector: list[float], right_vector: list[float]) -> float:
    """计算两个向量的余弦相似度。

    参数:
        left_vector: 左侧向量。
        right_vector: 右侧向量。

    返回:
        -1 到 1 的余弦相似度，空向量返回 0。
    """
    if not left_vector or not right_vector or len(left_vector) != len(right_vector):
        return 0.0
    dot_product = sum(left * right for left, right in zip(left_vector, right_vector, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left_vector))
    right_norm = math.sqrt(sum(value * value for value in right_vector))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)
