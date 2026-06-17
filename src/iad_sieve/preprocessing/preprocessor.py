"""文献标准化流水线。"""

from __future__ import annotations

import logging
from datetime import datetime

from iad_sieve.preprocessing.author_normalizer import normalize_authors
from iad_sieve.preprocessing.identifier_normalizer import normalize_arxiv_id, normalize_doi
from iad_sieve.preprocessing.quality_filter import build_quality_flags
from iad_sieve.preprocessing.text_normalizer import (
    build_content_hash,
    build_title_fingerprint,
    normalize_abstract,
    normalize_title,
)


LOGGER = logging.getLogger(__name__)


def extract_publication_year(record: dict) -> int | None:
    """提取出版年份。

    参数:
        record: 原始或解析后的文献记录。

    返回:
        年份整数；无法提取时返回 None。
    """
    try:
        versions = record.get("versions") or []
        if versions and isinstance(versions, list):
            created = versions[0].get("created", "") if isinstance(versions[0], dict) else ""
            if created:
                return datetime.strptime(created[:10], "%Y-%m-%d").year
        update_date = record.get("update_date", "")
        if update_date:
            return int(str(update_date)[:4])
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("年份提取失败: %s", exc)
    return None


def normalize_document(record: dict) -> dict:
    """标准化单篇文献。

    参数:
        record: 原始或解析后的文献记录。

    返回:
        标准化文献记录。
    """
    try:
        title_normalized = normalize_title(record.get("title", ""))
        abstract_normalized = normalize_abstract(record.get("abstract", ""))
        authors = normalize_authors(record.get("authors"))
        quality_flags = build_quality_flags(title_normalized, abstract_normalized)
        categories = record.get("categories") or []
        versions = record.get("versions") or []
        return {
            "document_id": record.get("document_id") or f"arxiv:{record.get('id', record.get('arxiv_id', ''))}",
            "arxiv_id": normalize_arxiv_id(record.get("arxiv_id", record.get("id", ""))),
            "title": record.get("title", "") or "",
            "abstract": record.get("abstract", "") or "",
            "authors": authors,
            "categories": categories,
            "primary_category": record.get("primary_category") or (categories[0] if categories else ""),
            "doi": normalize_doi(record.get("doi", "")),
            "journal_ref": record.get("journal_ref", record.get("journal-ref", "")) or "",
            "comments": record.get("comments", "") or "",
            "versions": versions,
            "version_count": len(versions),
            "update_date": record.get("update_date", "") or "",
            "publication_year": extract_publication_year(record),
            "title_normalized": title_normalized,
            "abstract_normalized": abstract_normalized,
            "title_fingerprint": build_title_fingerprint(title_normalized),
            "content_hash": build_content_hash(title_normalized, abstract_normalized),
            "metadata_json": record.get("metadata_json", record),
            **quality_flags,
        }
    except Exception:
        LOGGER.exception("文献标准化失败: %s", record.get("id", record.get("document_id", "")))
        raise


def normalize_documents(records: list[dict]) -> list[dict]:
    """批量标准化文献记录。

    参数:
        records: 文献记录列表。

    返回:
        标准化文献列表。
    """
    return [normalize_document(record) for record in records]
