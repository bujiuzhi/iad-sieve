"""规范文献选择模块。"""

from __future__ import annotations

import logging

from iad_sieve.preprocessing.quality_filter import abstract_quality_score


LOGGER = logging.getLogger(__name__)


def document_quality_score(document: dict) -> float:
    """计算文献质量分。

    参数:
        document: 标准化文献。

    返回:
        0 到 1 的质量分。
    """
    has_doi = 1.0 if document.get("doi") else 0.0
    has_journal_ref = 1.0 if document.get("journal_ref") else 0.0
    abstract_quality = abstract_quality_score(document.get("abstract_normalized") or document.get("abstract", ""))
    metadata_fields = ["title", "abstract", "authors", "categories", "update_date"]
    metadata_completeness = sum(1 for field in metadata_fields if document.get(field)) / len(metadata_fields)
    not_withdrawn = 0.0 if document.get("withdrawn_flag") else 1.0
    version_signal = min(1.0, float(document.get("version_count", 0) or 0) / 3.0)
    category_confidence = 1.0 if document.get("categories") else 0.0
    return (
        0.20 * has_doi
        + 0.20 * has_journal_ref
        + 0.15 * abstract_quality
        + 0.15 * metadata_completeness
        + 0.10 * not_withdrawn
        + 0.10 * version_signal
        + 0.10 * category_confidence
    )


def select_canonical_document(documents: list[dict]) -> dict:
    """选择重复组规范文献。

    参数:
        documents: 组内文献列表。

    返回:
        增加 canonical_quality_score 的规范文献记录。
    """
    if not documents:
        raise ValueError("documents 不能为空")
    scored_documents = []
    for document in documents:
        scored = dict(document)
        scored["canonical_quality_score"] = document_quality_score(document)
        scored_documents.append(scored)
    return max(scored_documents, key=lambda item: (item["canonical_quality_score"], item.get("version_count", 0), item.get("document_id", "")))
