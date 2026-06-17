"""标识符候选对召回模块。"""

from __future__ import annotations

import logging
from collections import defaultdict
from itertools import combinations


LOGGER = logging.getLogger(__name__)


def generate_identifier_candidates(records: list[dict]) -> list[dict]:
    """基于 DOI、arXiv ID 和标题作者年份生成候选对。

    参数:
        records: 标准化文献列表。

    返回:
        候选对列表。
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for record in records:
        document_id = record["document_id"]
        if record.get("doi"):
            groups[f"doi:{record['doi']}"].append(document_id)
        if record.get("arxiv_id"):
            groups[f"arxiv:{record['arxiv_id']}"].append(document_id)
        authors = record.get("authors") or []
        first_author = authors[0].lower() if authors else ""
        title_key = record.get("title_fingerprint", "")
        year = record.get("publication_year") or ""
        if title_key and first_author:
            groups[f"title-author-year:{title_key}:{first_author}:{year}"].append(document_id)
    candidates: list[dict] = []
    for key, document_ids in groups.items():
        unique_ids = sorted(set(document_ids))
        for source_id, target_id in combinations(unique_ids, 2):
            candidates.append(
                {
                    "source_document_id": source_id,
                    "target_document_id": target_id,
                    "candidate_sources": ["identifier"],
                    "identifier_candidate_type": key.split(":", 1)[0],
                    "raw_similarity": 1.0,
                }
            )
    return candidates
