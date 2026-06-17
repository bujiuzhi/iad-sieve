"""标识符标准化模块。"""

from __future__ import annotations

import logging
import re


LOGGER = logging.getLogger(__name__)
DOI_PREFIX_PATTERN = re.compile(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)


def normalize_doi(doi: str | None) -> str:
    """标准化 DOI。

    参数:
        doi: 原始 DOI。

    返回:
        小写且去除 URL 前缀的 DOI。
    """
    if not doi:
        return ""
    try:
        normalized = DOI_PREFIX_PATTERN.sub("", doi.strip()).strip().lower()
        return normalized.rstrip(".")
    except Exception:
        LOGGER.exception("DOI 标准化失败")
        raise


def normalize_arxiv_id(arxiv_id: str | None) -> str:
    """标准化 arXiv ID。

    参数:
        arxiv_id: 原始 arXiv ID。

    返回:
        去除 arXiv 前缀后的 ID。
    """
    if not arxiv_id:
        return ""
    return arxiv_id.strip().replace("arXiv:", "").replace("arxiv:", "")
