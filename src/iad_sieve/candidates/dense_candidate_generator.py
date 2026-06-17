"""稠密向量候选对召回模块。"""

from __future__ import annotations

import logging
from itertools import combinations

from iad_sieve.utils.text_similarity import vector_cosine


LOGGER = logging.getLogger(__name__)


def _append_dense_pair(pairs: dict[tuple[str, str], float], source_id: str, target_id: str, similarity: float) -> None:
    """添加稠密候选对。

    参数:
        pairs: 候选对到相似度的映射。
        source_id: 源文献 ID。
        target_id: 目标文献 ID。
        similarity: 相似度。

    返回:
        无。
    """
    if source_id == target_id or similarity <= 0:
        return
    key = tuple(sorted((source_id, target_id)))
    pairs[key] = max(pairs.get(key, 0.0), float(similarity))


def _rank_dense_pairs(scored_pairs: list[tuple[float, str, str]], top_k: int) -> list[dict]:
    """按每篇 top-k 约束输出 dense 候选对。

    参数:
        scored_pairs: 相似度和文献对列表。
        top_k: 每篇文献最大候选数。

    返回:
        dense 候选对列表。
    """
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
                "candidate_sources": ["dense"],
                "dense_candidate_rank": per_document_counts[source_id],
                "raw_similarity": similarity,
            }
        )
    return candidates


def _generate_faiss_candidates(document_ids: list[str], embeddings: list[list[float]], top_k: int) -> list[dict]:
    """使用 FAISS 生成 dense top-k 候选。

    参数:
        document_ids: 文献 ID 列表。
        embeddings: 向量列表。
        top_k: 每篇文献最大候选数。

    返回:
        dense 候选对列表。
    """
    import faiss  # type: ignore
    import numpy as np  # type: ignore

    vectors = np.asarray(embeddings, dtype="float32")
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    scores, indices = index.search(vectors, min(top_k + 1, len(document_ids)))
    pair_scores: dict[tuple[str, str], float] = {}
    for row_index, neighbor_indices in enumerate(indices):
        source_id = document_ids[row_index]
        for score, neighbor_index in zip(scores[row_index], neighbor_indices, strict=True):
            if neighbor_index < 0:
                continue
            _append_dense_pair(pair_scores, source_id, document_ids[int(neighbor_index)], float(score))
    scored_pairs = [(score, source_id, target_id) for (source_id, target_id), score in pair_scores.items()]
    return _rank_dense_pairs(scored_pairs, top_k=top_k)


def generate_dense_candidates(
    document_ids: list[str],
    embeddings: list[list[float]],
    top_k: int = 50,
    brute_force_limit: int = 5000,
) -> list[dict]:
    """基于向量余弦相似度生成候选对。

    参数:
        document_ids: 文献 ID 列表。
        embeddings: 向量列表。
        top_k: 每篇文献最多保留候选数。
        brute_force_limit: 无 FAISS 时允许 brute-force 的最大文献数。

    返回:
        候选对列表。
    """
    if not document_ids or not embeddings:
        return []
    try:
        return _generate_faiss_candidates(document_ids, embeddings, top_k=top_k)
    except Exception as exc:  # noqa: BLE001
        LOGGER.info("FAISS dense 召回不可用，使用 fallback: %s", exc)
    if len(document_ids) > brute_force_limit:
        LOGGER.warning("样本量 %s 超过 brute_force_limit=%s，跳过 dense fallback 候选", len(document_ids), brute_force_limit)
        return []
    scored_pairs: list[tuple[float, str, str]] = []
    for left_index, right_index in combinations(range(len(document_ids)), 2):
        similarity = vector_cosine(embeddings[left_index], embeddings[right_index])
        if similarity > 0:
            scored_pairs.append((similarity, document_ids[left_index], document_ids[right_index]))
    return _rank_dense_pairs(scored_pairs, top_k=top_k)
