"""词法候选对召回模块。"""

from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict
from itertools import combinations

from iad_sieve.utils.text_similarity import cosine_from_counters, tokenize


LOGGER = logging.getLogger(__name__)
LEXICAL_STOPWORDS = {
    "about",
    "after",
    "also",
    "analysis",
    "based",
    "between",
    "both",
    "data",
    "different",
    "during",
    "each",
    "from",
    "have",
    "into",
    "method",
    "methods",
    "model",
    "models",
    "more",
    "most",
    "paper",
    "present",
    "problem",
    "results",
    "show",
    "such",
    "than",
    "that",
    "their",
    "these",
    "this",
    "using",
    "where",
    "which",
    "with",
}


def _candidate_text(record: dict, view: dict | None = None) -> str:
    """构造候选召回文本。

    参数:
        record: 文献记录。
        view: 可选语义视图。

    返回:
        拼接文本。
    """
    keyphrases = " ".join(view.get("keyphrases", [])) if view else ""
    return " ".join(
        [
            record.get("title_normalized") or record.get("title", ""),
            record.get("abstract_normalized") or record.get("abstract", ""),
            keyphrases,
        ]
    )


def _build_token_index(records: list[dict], views: list[dict] | None) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """构建文档 token 与倒排索引。

    参数:
        records: 标准化文献列表。
        views: 可选语义视图列表。

    返回:
        document_id 到 token 列表、token 到 document_id 列表的二元组。
    """
    view_lookup = {view["document_id"]: view for view in views or []}
    tokens_by_document: dict[str, list[str]] = {}
    postings: dict[str, list[str]] = defaultdict(list)
    for record in records:
        document_id = record["document_id"]
        tokens = [
            token
            for token in tokenize(_candidate_text(record, view_lookup.get(document_id)))
            if len(token) >= 4 and not token.isdigit() and token not in LEXICAL_STOPWORDS
        ]
        unique_tokens = sorted(set(tokens))
        tokens_by_document[document_id] = tokens
        for token in unique_tokens:
            postings[token].append(document_id)
    return tokens_by_document, postings


def generate_lexical_candidates(
    records: list[dict],
    views: list[dict] | None = None,
    top_k: int = 50,
    min_shared_tokens: int = 2,
    max_postings_per_token: int = 200,
    max_neighbors_per_token: int = 80,
    max_candidate_pairs: int = 2_000_000,
) -> list[dict]:
    """基于倒排索引和词频余弦相似度生成候选对。

    参数:
        records: 标准化文献列表。
        views: 可选语义视图列表。
        top_k: 每篇文献最多保留的词法候选数。
        min_shared_tokens: 产生候选所需的最少共享 token 数。
        max_postings_per_token: 高频 token 最大 postings，超过时跳过。
        max_neighbors_per_token: 每个 token 下每篇文献最多连接的近邻数量。
        max_candidate_pairs: 倒排阶段最多保留的候选 pair 数。

    返回:
        候选对列表。
    """
    tokens_by_document, postings = _build_token_index(records, views)
    shared_counts: Counter[tuple[str, str]] = Counter()
    for document_ids in postings.values():
        if len(document_ids) < 2 or len(document_ids) > max_postings_per_token:
            continue
        sorted_document_ids = sorted(document_ids)
        for index, source_id in enumerate(sorted_document_ids):
            for target_id in sorted_document_ids[index + 1 : index + 1 + max_neighbors_per_token]:
                if len(shared_counts) >= max_candidate_pairs and (source_id, target_id) not in shared_counts:
                    break
                shared_counts[(source_id, target_id)] += 1
            if len(shared_counts) >= max_candidate_pairs:
                break
        if len(shared_counts) >= max_candidate_pairs:
            LOGGER.warning("词法候选达到 max_candidate_pairs=%s，提前截断", max_candidate_pairs)
            break

    scored_pairs: list[tuple[float, str, str]] = []
    for (source_id, target_id), shared_count in shared_counts.items():
        if shared_count < min_shared_tokens:
            continue
        cosine_score = cosine_from_counters(tokens_by_document[source_id], tokens_by_document[target_id])
        overlap_score = shared_count / math.sqrt(max(1, len(set(tokens_by_document[source_id]))) * max(1, len(set(tokens_by_document[target_id]))))
        similarity = max(cosine_score, overlap_score)
        if similarity > 0:
            scored_pairs.append((similarity, source_id, target_id))

    scored_pairs.sort(reverse=True)
    candidates: list[dict] = []
    per_document_counts: dict[str, int] = {}
    for similarity, source_id, target_id in scored_pairs:
        if per_document_counts.get(source_id, 0) >= top_k or per_document_counts.get(target_id, 0) >= top_k:
            continue
        per_document_counts[source_id] = per_document_counts.get(source_id, 0) + 1
        per_document_counts[target_id] = per_document_counts.get(target_id, 0) + 1
        candidates.append(
            {
                "source_document_id": source_id,
                "target_document_id": target_id,
                "candidate_sources": ["lexical"],
                "lexical_candidate_rank": per_document_counts[source_id],
                "raw_similarity": similarity,
                "lexical_shared_token_score": similarity,
            }
        )
    return candidates
