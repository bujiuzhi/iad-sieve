"""arXiv metadata 流式读取模块。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterator

from iad_sieve.data.schema import build_document_id, parse_categories


LOGGER = logging.getLogger(__name__)


def parse_arxiv_record(raw_record: dict) -> dict:
    """解析单条 arXiv metadata 记录。

    参数:
        raw_record: Kaggle arXiv metadata 原始记录。

    返回:
        字段规范后的基础记录。
    """
    try:
        arxiv_id = str(raw_record.get("id", "")).strip()
        categories, primary_category = parse_categories(raw_record.get("categories"))
        return {
            "document_id": build_document_id(arxiv_id),
            "arxiv_id": arxiv_id,
            "submitter": raw_record.get("submitter", "") or "",
            "authors": raw_record.get("authors", "") or "",
            "title": raw_record.get("title", "") or "",
            "comments": raw_record.get("comments", "") or "",
            "journal_ref": raw_record.get("journal-ref", raw_record.get("journal_ref", "")) or "",
            "doi": raw_record.get("doi", "") or "",
            "report_no": raw_record.get("report-no", raw_record.get("report_no", "")) or "",
            "categories": categories,
            "primary_category": primary_category,
            "license": raw_record.get("license", "") or "",
            "abstract": raw_record.get("abstract", "") or "",
            "versions": raw_record.get("versions", []) or [],
            "update_date": raw_record.get("update_date", "") or "",
            "metadata_json": raw_record,
        }
    except Exception:
        LOGGER.exception("解析 arXiv 记录失败")
        raise


def stream_arxiv_metadata(input_path: str | Path, limit: int | None = None) -> Iterator[dict]:
    """流式读取 arXiv metadata JSON Lines 文件。

    参数:
        input_path: 输入 JSONL 文件路径。
        limit: 最多读取的原始行数。

    返回:
        解析后的记录迭代器。
    """
    path = Path(input_path)
    try:
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if limit is not None and line_number > limit:
                    break
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    yield parse_arxiv_record(json.loads(stripped))
                except json.JSONDecodeError:
                    LOGGER.exception("arXiv JSON 行解析失败: path=%s line=%s", path, line_number)
                    continue
    except OSError:
        LOGGER.exception("读取 arXiv metadata 失败: %s", path)
        raise
