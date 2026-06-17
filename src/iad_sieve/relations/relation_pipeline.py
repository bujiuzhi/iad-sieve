"""关系评分流水线模块。"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator

from iad_sieve.relations.adaptive_threshold import build_threshold_bucket, get_default_thresholds
from iad_sieve.relations.pair_feature_extractor import extract_pair_features
from iad_sieve.relations.relation_classifier import classify_relation
from iad_sieve.relations.relation_scorer import score_relation


LOGGER = logging.getLogger(__name__)


def score_candidate_pairs(
    candidates: list[dict],
    documents: list[dict],
    views: list[dict] | None = None,
    embeddings: dict[str, list[float]] | None = None,
    thresholds: dict[str, float] | None = None,
) -> list[dict]:
    """对候选文献对执行特征抽取、评分和分类。

    参数:
        candidates: 候选对列表。
        documents: 标准化文献列表。
        views: 语义视图列表。
        embeddings: 可选向量映射。
        thresholds: 可选阈值配置。

    返回:
        pair_relations 记录列表。
    """
    document_lookup = {document["document_id"]: document for document in documents}
    view_lookup = {view["document_id"]: view for view in views or []}
    active_thresholds = thresholds or get_default_thresholds()
    return list(score_candidate_pairs_iter(candidates, document_lookup, view_lookup, embeddings, active_thresholds))


def score_candidate_pairs_iter(
    candidates: Iterable[dict],
    documents: list[dict] | dict[str, dict],
    views: list[dict] | dict[str, dict] | None = None,
    embeddings: dict[str, list[float]] | None = None,
    thresholds: dict[str, float] | None = None,
    log_interval: int = 100_000,
) -> Iterator[dict]:
    """流式执行候选文献对特征抽取、评分和分类。

    参数:
        candidates: 候选对迭代器。
        documents: 标准化文献列表或 document_id 映射。
        views: 语义视图列表或 document_id 映射。
        embeddings: 可选向量映射。
        thresholds: 可选阈值配置。
        log_interval: 进度日志间隔。

    返回:
        pair_relations 记录迭代器。
    """
    document_lookup = documents if isinstance(documents, dict) else {document["document_id"]: document for document in documents}
    if isinstance(views, dict):
        view_lookup = views
    else:
        view_lookup = {view["document_id"]: view for view in views or []}
    active_thresholds = thresholds or get_default_thresholds()
    for index, candidate in enumerate(candidates, start=1):
        features = extract_pair_features(candidate, document_lookup, view_lookup, embeddings)
        scored = score_relation(features)
        source_record = document_lookup[scored["source_document_id"]]
        scored["threshold_bucket"] = build_threshold_bucket(source_record)
        scored["duplicate_threshold"] = active_thresholds["duplicate_threshold"]
        scored["topic_threshold"] = active_thresholds["topic_threshold"]
        scored["review_threshold"] = active_thresholds["review_threshold"]
        scored["review_candidate_threshold"] = active_thresholds["review_candidate_threshold"]
        scored["relation_type"] = classify_relation(scored, active_thresholds)
        if log_interval > 0 and index % log_interval == 0:
            LOGGER.info("关系评分进度: %s pairs", index)
        yield scored
