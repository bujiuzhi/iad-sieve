"""关键词短语抽取模块。"""

from __future__ import annotations

import logging
from collections import Counter

from iad_sieve.utils.text_similarity import tokenize


LOGGER = logging.getLogger(__name__)
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "are",
    "was",
    "were",
    "using",
    "use",
    "our",
    "their",
    "paper",
    "papers",
}


def extract_keyphrases(text: str | None, top_k: int = 12) -> list[str]:
    """抽取高频关键词。

    参数:
        text: 输入文本。
        top_k: 返回关键词数量。

    返回:
        关键词列表。
    """
    tokens = [token for token in tokenize(text) if token not in STOPWORDS and len(token) > 2]
    counter = Counter(tokens)
    return [token for token, _ in counter.most_common(top_k)]
