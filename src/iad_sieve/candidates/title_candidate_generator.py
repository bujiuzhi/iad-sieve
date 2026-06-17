"""标题候选对召回模块。"""

from __future__ import annotations

import logging
from collections import defaultdict
from itertools import combinations

from iad_sieve.utils.text_similarity import jaccard_similarity, sequence_similarity, tokenize


LOGGER = logging.getLogger(__name__)


def _title_block_key(record: dict) -> str:
    """生成标题模糊召回 block key。

    参数:
        record: 标准化文献记录。

    返回:
        主分类与标题首个 token 组成的 block key。
    """
    tokens = tokenize(record.get("title_normalized") or record.get("title", ""))
    first_token = tokens[0] if tokens else ""
    return f"{record.get('primary_category', '')}:{first_token}"


def _append_title_candidate(candidates: dict[tuple[str, str], dict], left: dict, right: dict, similarity: float, reason: str) -> None:
    """添加标题候选对。

    参数:
        candidates: 候选对映射。
        left: 左侧文献。
        right: 右侧文献。
        similarity: 原始相似度。
        reason: 召回原因。

    返回:
        无。
    """
    source_id, target_id = sorted((left["document_id"], right["document_id"]))
    key = (source_id, target_id)
    existing = candidates.get(key)
    if existing:
        existing["raw_similarity"] = max(float(existing["raw_similarity"]), similarity)
        existing["title_candidate_reason"] = f"{existing['title_candidate_reason']}|{reason}"
        return
    candidates[key] = {
        "source_document_id": source_id,
        "target_document_id": target_id,
        "candidate_sources": ["title"],
        "title_candidate_rank": 1,
        "title_candidate_reason": reason,
        "raw_similarity": similarity,
    }


def generate_title_candidates(
    records: list[dict],
    jaccard_threshold: float = 0.85,
    sequence_threshold: float = 0.9,
    max_block_size: int = 500,
) -> list[dict]:
    """基于标题指纹和标题相似度生成候选对。

    参数:
        records: 标准化文献列表。
        jaccard_threshold: token Jaccard 阈值。
        sequence_threshold: 字符序列相似度阈值。
        max_block_size: 模糊比较的最大 block 大小。

    返回:
        候选对列表。
    """
    candidates: dict[tuple[str, str], dict] = {}
    fingerprint_groups: dict[str, list[dict]] = defaultdict(list)
    block_groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        if record.get("title_fingerprint"):
            fingerprint_groups[record["title_fingerprint"]].append(record)
        block_groups[_title_block_key(record)].append(record)

    for group_records in fingerprint_groups.values():
        if len(group_records) < 2:
            continue
        for left, right in combinations(group_records, 2):
            _append_title_candidate(candidates, left, right, 1.0, "same_title_fingerprint")

    for group_records in block_groups.values():
        if len(group_records) < 2 or len(group_records) > max_block_size:
            continue
        for left, right in combinations(group_records, 2):
            if left["document_id"] == right["document_id"]:
                continue
            key = tuple(sorted((left["document_id"], right["document_id"])))
            if key in candidates:
                continue
            jaccard = jaccard_similarity(left.get("title_normalized"), right.get("title_normalized"))
            sequence = sequence_similarity(left.get("title_normalized"), right.get("title_normalized"))
            if jaccard >= jaccard_threshold or sequence >= sequence_threshold:
                _append_title_candidate(candidates, left, right, max(jaccard, sequence), "blocked_fuzzy_title")
    return sorted(candidates.values(), key=lambda item: item["raw_similarity"], reverse=True)
