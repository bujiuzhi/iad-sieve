"""候选对合并模块。"""

from __future__ import annotations

import logging
from collections import defaultdict


LOGGER = logging.getLogger(__name__)


def pair_key(source_id: str, target_id: str) -> tuple[str, str]:
    """生成无向候选对键。

    参数:
        source_id: 源文献 ID。
        target_id: 目标文献 ID。

    返回:
        排序后的二元组。
    """
    return tuple(sorted((source_id, target_id)))


def merge_candidate_pairs(candidate_groups: list[list[dict]], max_candidate_per_document: int = 100) -> list[dict]:
    """合并多路候选对并限制每篇候选数。

    参数:
        candidate_groups: 多个候选对列表。
        max_candidate_per_document: 每篇文献最多保留候选数。

    返回:
        合并后的候选对列表。
    """
    merged: dict[tuple[str, str], dict] = {}
    for candidates in candidate_groups:
        for candidate in candidates:
            source_id, target_id = pair_key(candidate["source_document_id"], candidate["target_document_id"])
            existing = merged.setdefault(
                (source_id, target_id),
                {
                    "source_document_id": source_id,
                    "target_document_id": target_id,
                    "candidate_sources": [],
                    "title_candidate_rank": None,
                    "dense_candidate_rank": None,
                    "lexical_candidate_rank": None,
                    "identifier_candidate_type": "",
                    "raw_similarity": 0.0,
                },
            )
            existing["candidate_sources"] = sorted(set(existing["candidate_sources"]) | set(candidate.get("candidate_sources", [])))
            for field in ["title_candidate_rank", "dense_candidate_rank", "lexical_candidate_rank", "identifier_candidate_type"]:
                if candidate.get(field) is not None:
                    existing[field] = candidate.get(field)
            existing["raw_similarity"] = max(float(existing.get("raw_similarity") or 0.0), float(candidate.get("raw_similarity") or 0.0))
    counts: dict[str, int] = defaultdict(int)
    output: list[dict] = []
    for candidate in sorted(merged.values(), key=lambda item: item["raw_similarity"], reverse=True):
        source_id = candidate["source_document_id"]
        target_id = candidate["target_document_id"]
        if counts[source_id] >= max_candidate_per_document or counts[target_id] >= max_candidate_per_document:
            continue
        counts[source_id] += 1
        counts[target_id] += 1
        output.append(candidate)
    return output
