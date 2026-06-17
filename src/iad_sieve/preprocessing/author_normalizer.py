"""作者字段标准化模块。"""

from __future__ import annotations

import logging
import re


LOGGER = logging.getLogger(__name__)


def normalize_authors(authors: str | list[str] | None) -> list[str]:
    """标准化作者列表。

    参数:
        authors: 原始作者字符串或列表。

    返回:
        作者名称列表。
    """
    if not authors:
        return []
    try:
        if isinstance(authors, list):
            return [str(author).strip() for author in authors if str(author).strip()]
        normalized = re.sub(r"\s+and\s+", ",", authors, flags=re.IGNORECASE)
        return [author.strip() for author in normalized.split(",") if author.strip()]
    except Exception:
        LOGGER.exception("作者标准化失败")
        raise


def first_author(authors: str | list[str] | None) -> str:
    """提取第一作者。

    参数:
        authors: 原始作者字符串或列表。

    返回:
        第一作者小写名称。
    """
    author_list = normalize_authors(authors)
    return author_list[0].lower() if author_list else ""
