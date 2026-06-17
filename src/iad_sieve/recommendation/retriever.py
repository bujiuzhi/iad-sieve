"""查询召回模块。"""

from __future__ import annotations

import logging

from iad_sieve.utils.text_similarity import jaccard_similarity


LOGGER = logging.getLogger(__name__)


def lexical_query_scores(query: str, documents: list[dict]) -> dict[str, float]:
    """计算查询与文献的词法相关性。

    参数:
        query: 查询文本。
        documents: 文献列表。

    返回:
        document_id 到相关性分的映射。
    """
    scores: dict[str, float] = {}
    for document in documents:
        text = " ".join(
            [
                document.get("title_normalized") or document.get("title", ""),
                document.get("abstract_normalized") or document.get("abstract", ""),
            ]
        )
        scores[document["document_id"]] = jaccard_similarity(query, text)
    return scores
