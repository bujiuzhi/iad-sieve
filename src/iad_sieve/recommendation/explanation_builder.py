"""推荐解释构造模块。"""

from __future__ import annotations

import logging

from iad_sieve.utils.text_similarity import tokenize


LOGGER = logging.getLogger(__name__)


def build_recommendation_reason(query: str, document: dict, role: str) -> str:
    """生成推荐理由。

    参数:
        query: 查询文本。
        document: 文献记录。
        role: 推荐角色。

    返回:
        推荐理由文本。
    """
    query_tokens = set(tokenize(query))
    document_tokens = set(tokenize(f"{document.get('title', '')} {document.get('abstract', '')}"))
    matched_tokens = sorted(query_tokens & document_tokens)
    if matched_tokens:
        return f"匹配关键词: {', '.join(matched_tokens[:6])}; 角色: {role}"
    return f"根据主题和质量分推荐; 角色: {role}"
