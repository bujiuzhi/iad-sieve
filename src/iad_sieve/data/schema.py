"""arXiv 元数据字段契约。"""

from __future__ import annotations

import logging
from hashlib import sha1


LOGGER = logging.getLogger(__name__)

ARXIV_REQUIRED_FIELDS = ["id", "title", "abstract", "authors", "categories", "versions", "update_date"]


def build_document_id(arxiv_id: str | None) -> str:
    """构造稳定文献 ID。

    参数:
        arxiv_id: arXiv 原始 ID。

    返回:
        规范 document_id。
    """
    if arxiv_id:
        return f"arxiv:{arxiv_id.strip()}"
    digest = sha1(b"missing-arxiv-id").hexdigest()[:12]
    return f"missing:{digest}"


def parse_categories(categories: str | list[str] | None) -> tuple[list[str], str]:
    """解析 arXiv 分类字段。

    参数:
        categories: 原始分类字符串或列表。

    返回:
        分类列表和主分类。
    """
    if isinstance(categories, list):
        category_list = [str(category).strip() for category in categories if str(category).strip()]
    elif isinstance(categories, str):
        category_list = [category.strip() for category in categories.split() if category.strip()]
    else:
        category_list = []
    primary_category = category_list[0] if category_list else ""
    return category_list, primary_category
