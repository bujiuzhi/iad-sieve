"""候选对特征抽取模块。"""

from __future__ import annotations

import logging

from iad_sieve.utils.text_similarity import jaccard_similarity, sequence_similarity, vector_cosine


LOGGER = logging.getLogger(__name__)


def _category_overlap(left: dict, right: dict) -> float:
    """计算分类重叠。

    参数:
        left: 左侧文献。
        right: 右侧文献。

    返回:
        0 到 1 的重叠分。
    """
    left_categories = set(left.get("categories") or [])
    right_categories = set(right.get("categories") or [])
    if not left_categories and not right_categories:
        return 0.0
    return len(left_categories & right_categories) / len(left_categories | right_categories)


def _author_overlap(left: dict, right: dict) -> float:
    """计算作者重叠。

    参数:
        left: 左侧文献。
        right: 右侧文献。

    返回:
        0 到 1 的重叠分。
    """
    left_authors = {author.lower() for author in left.get("authors", [])}
    right_authors = {author.lower() for author in right.get("authors", [])}
    if not left_authors or not right_authors:
        return 0.0
    return len(left_authors & right_authors) / len(left_authors | right_authors)


def _year_score(left: dict, right: dict) -> float:
    """计算年份接近度。

    参数:
        left: 左侧文献。
        right: 右侧文献。

    返回:
        0 到 1 的年份分。
    """
    left_year = left.get("publication_year")
    right_year = right.get("publication_year")
    if not left_year or not right_year:
        return 0.5
    gap = abs(int(left_year) - int(right_year))
    return max(0.0, 1.0 - gap / 5.0)


def _identifier_score(left: dict, right: dict) -> float:
    """计算标识符一致分。

    参数:
        left: 左侧文献。
        right: 右侧文献。

    返回:
        0 或 1 的一致分。
    """
    if left.get("doi") and left.get("doi") == right.get("doi"):
        return 1.0
    if left.get("arxiv_id") and left.get("arxiv_id") == right.get("arxiv_id"):
        return 1.0
    return 0.0


def extract_pair_features(
    candidate: dict,
    document_lookup: dict[str, dict],
    view_lookup: dict[str, dict] | None = None,
    embedding_lookup: dict[str, list[float]] | None = None,
) -> dict:
    """抽取候选文献对特征。

    参数:
        candidate: 候选对记录。
        document_lookup: document_id 到文献记录的映射。
        view_lookup: document_id 到语义视图的映射。
        embedding_lookup: document_id 到向量的映射。

    返回:
        候选对特征字典。
    """
    try:
        source_id = candidate["source_document_id"]
        target_id = candidate["target_document_id"]
        left = document_lookup[source_id]
        right = document_lookup[target_id]
        left_view = (view_lookup or {}).get(source_id, {})
        right_view = (view_lookup or {}).get(target_id, {})
        full_similarity = jaccard_similarity(
            f"{left.get('title_normalized', '')} {left.get('abstract_normalized', '')}",
            f"{right.get('title_normalized', '')} {right.get('abstract_normalized', '')}",
        )
        if embedding_lookup and source_id in embedding_lookup and target_id in embedding_lookup:
            full_similarity = max(full_similarity, vector_cosine(embedding_lookup[source_id], embedding_lookup[target_id]))
        method_similarity = jaccard_similarity(left_view.get("method_view", ""), right_view.get("method_view", ""))
        object_similarity = jaccard_similarity(left_view.get("object_view", ""), right_view.get("object_view", ""))
        result_similarity = jaccard_similarity(left_view.get("result_view", ""), right_view.get("result_view", ""))
        problem_similarity = jaccard_similarity(left_view.get("problem_view", ""), right_view.get("problem_view", ""))
        title_similarity = max(
            jaccard_similarity(left.get("title_normalized"), right.get("title_normalized")),
            sequence_similarity(left.get("title_normalized"), right.get("title_normalized")),
        )
        category_overlap = _category_overlap(left, right)
        author_overlap = _author_overlap(left, right)
        year_score = _year_score(left, right)
        identifier_score = _identifier_score(left, right)
        conflict_score = 0.0
        if category_overlap == 0 and problem_similarity < 0.2:
            conflict_score += 0.2
        if author_overlap == 0 and year_score < 0.4 and title_similarity < 0.4:
            conflict_score += 0.15
        return {
            **candidate,
            "title_similarity": title_similarity,
            "full_similarity": full_similarity,
            "problem_similarity": problem_similarity,
            "method_similarity": method_similarity,
            "object_similarity": object_similarity,
            "result_similarity": result_similarity,
            "lexical_similarity": float(candidate.get("raw_similarity") or full_similarity),
            "title_token_jaccard": jaccard_similarity(left.get("title_normalized"), right.get("title_normalized")),
            "title_edit_similarity": sequence_similarity(left.get("title_normalized"), right.get("title_normalized")),
            "author_overlap": author_overlap,
            "first_author_match": 1.0 if left.get("authors") and right.get("authors") and left["authors"][0] == right["authors"][0] else 0.0,
            "year_score": year_score,
            "identifier_score": identifier_score,
            "category_overlap": category_overlap,
            "journal_ref_signal": 1.0 if left.get("journal_ref") and left.get("journal_ref") == right.get("journal_ref") else 0.0,
            "version_signal": 1.0 if left.get("arxiv_id") and left.get("arxiv_id") == right.get("arxiv_id") else 0.0,
            "keyphrase_similarity": jaccard_similarity(" ".join(left_view.get("keyphrases", [])), " ".join(right_view.get("keyphrases", []))),
            "contribution_phrase_similarity": max(method_similarity, result_similarity),
            "conflict_score": min(1.0, conflict_score),
        }
    except Exception:
        LOGGER.exception("候选对特征抽取失败: %s", candidate)
        raise
