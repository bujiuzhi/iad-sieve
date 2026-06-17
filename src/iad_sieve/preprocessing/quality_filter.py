"""文献质量标记模块。"""

from __future__ import annotations

import logging

from iad_sieve.utils.text_similarity import tokenize


LOGGER = logging.getLogger(__name__)


def build_quality_flags(title: str | None, abstract: str | None) -> dict[str, bool]:
    """生成基础质量标记。

    参数:
        title: 标题文本。
        abstract: 摘要文本。

    返回:
        质量标记字典。
    """
    title_tokens = tokenize(title)
    abstract_tokens = tokenize(abstract)
    combined = f"{title or ''} {abstract or ''}".lower()
    return {
        "low_quality_title": len(title_tokens) < 5,
        "low_quality_abstract": len(abstract_tokens) < 50,
        "withdrawn_flag": "withdrawn" in combined,
    }


def abstract_quality_score(abstract: str | None) -> float:
    """计算摘要质量分。

    参数:
        abstract: 摘要文本。

    返回:
        0 到 1 的摘要质量分。
    """
    token_count = len(tokenize(abstract))
    if token_count >= 80:
        return 1.0
    if token_count <= 10:
        return 0.0
    return token_count / 80
