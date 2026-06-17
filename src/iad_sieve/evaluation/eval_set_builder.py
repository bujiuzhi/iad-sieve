"""合成重复与硬负例评估集构建模块。"""

from __future__ import annotations

import logging
import random
from collections.abc import Iterable

from iad_sieve.evaluation.baseline_runner import calculate_binary_metrics
from iad_sieve.relations.relation_pipeline import score_candidate_pairs
from iad_sieve.views.semantic_view_extractor import build_semantic_views


LOGGER = logging.getLogger(__name__)


def _mutate_title(title: str) -> str:
    """生成标题扰动。

    参数:
        title: 原始标题。

    返回:
        扰动后的标题。
    """
    normalized = " ".join(str(title or "").split())
    if ":" in normalized:
        normalized = normalized.split(":", maxsplit=1)[0]
    replacements = {
        " using ": " with ",
        " via ": " through ",
        " for ": " for ",
        " and ": " & ",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized.strip(" .") or str(title or "")


def _mutate_abstract(abstract: str) -> str:
    """生成摘要扰动。

    参数:
        abstract: 原始摘要。

    返回:
        扰动后的摘要。
    """
    text = " ".join(str(abstract or "").split())
    replacements = {
        "method": "approach",
        "model": "framework",
        "models": "frameworks",
        "data": "dataset",
        "results": "findings",
        "show": "demonstrate",
    }
    for source, target in replacements.items():
        text = text.replace(source, target).replace(source.capitalize(), target.capitalize())
    sentences = [sentence.strip() for sentence in text.split(".") if sentence.strip()]
    if len(sentences) > 2:
        sentences = sentences[:-1]
    return ". ".join(sentences).strip() + ("." if sentences else "")


def _abbreviate_author(author: str) -> str:
    """生成作者缩写。

    参数:
        author: 原作者名。

    返回:
        缩写后的作者名。
    """
    parts = [part for part in str(author or "").replace(",", " ").split() if part]
    if len(parts) < 2:
        return str(author or "")
    return f"{parts[0][0]}. {parts[-1]}"


def _drop_last_sentence(abstract: str) -> str:
    """删除摘要末句。

    参数:
        abstract: 原始摘要。

    返回:
        删除末句后的摘要。
    """
    sentences = [sentence.strip() for sentence in str(abstract or "").split(".") if sentence.strip()]
    if len(sentences) <= 1:
        return str(abstract or "")
    return ". ".join(sentences[:-1]) + "."


def _synthetic_rule(index: int) -> str:
    """根据序号选择合成扰动规则。

    参数:
        index: 合成文献序号。

    返回:
        扰动规则名。
    """
    rules = [
        "title_subtitle_drop",
        "author_abbreviation",
        "abstract_sentence_drop",
        "synonym_replacement",
        "combined_title_author_abstract",
    ]
    return rules[(index - 1) % len(rules)]


def _build_synthetic_duplicate(document: dict, index: int) -> dict:
    """构造单篇合成重复文献。

    参数:
        document: 原始标准化文献。
        index: 合成文献序号。

    返回:
        合成文献记录。
    """
    synthetic = dict(document)
    synthetic["document_id"] = f"{document['document_id']}::synthetic-{index:06d}"
    synthetic["arxiv_id"] = ""
    synthetic["doi"] = ""
    synthetic["journal_ref"] = ""
    rule = _synthetic_rule(index)
    title = str(document.get("title", ""))
    abstract = str(document.get("abstract", ""))
    authors = list(document.get("authors") or [])
    if rule == "title_subtitle_drop":
        title = _mutate_title(title)
    elif rule == "author_abbreviation":
        authors = [_abbreviate_author(authors[0]), *authors[1:]] if authors else authors
    elif rule == "abstract_sentence_drop":
        abstract = _drop_last_sentence(abstract)
    elif rule == "synonym_replacement":
        abstract = _mutate_abstract(abstract)
    else:
        title = _mutate_title(title)
        abstract = _mutate_abstract(_drop_last_sentence(abstract))
        authors = [_abbreviate_author(authors[0]), *authors[1:]] if authors else authors
    synthetic["title"] = title
    synthetic["abstract"] = abstract
    synthetic["authors"] = authors
    synthetic["title_normalized"] = title.lower()
    synthetic["abstract_normalized"] = abstract.lower()
    synthetic["metadata_json"] = {"synthetic_source_document_id": document["document_id"], "synthetic_rule": rule}
    return synthetic


def _eligible_for_synthetic(document: dict) -> bool:
    """判断文献是否适合生成合成重复样本。

    参数:
        document: 标准化文献。

    返回:
        适合返回 True，否则返回 False。
    """
    return bool(document.get("document_id") and document.get("title") and len(str(document.get("abstract", ""))) >= 30)


def _pair_key(source_id: str, target_id: str) -> tuple[str, str]:
    """生成无向 pair key。

    参数:
        source_id: 源文献 ID。
        target_id: 目标文献 ID。

    返回:
        排序后的二元组。
    """
    return tuple(sorted((source_id, target_id)))


def _build_synthetic_pairs(documents: list[dict], synthetic_count: int, random_generator: random.Random) -> tuple[list[dict], list[dict]]:
    """构造合成重复文献和 pair。

    参数:
        documents: 标准化文献列表。
        synthetic_count: 合成正例数量。
        random_generator: 随机数生成器。

    返回:
        合成文献列表与 pair 列表。
    """
    eligible_documents = [document for document in documents if _eligible_for_synthetic(document)]
    random_generator.shuffle(eligible_documents)
    selected_documents = eligible_documents[:synthetic_count]
    synthetic_documents: list[dict] = []
    pairs: list[dict] = []
    for index, document in enumerate(selected_documents, start=1):
        synthetic = _build_synthetic_duplicate(document, index)
        synthetic_documents.append(synthetic)
        pairs.append(
            {
                "source_document_id": document["document_id"],
                "target_document_id": synthetic["document_id"],
                "candidate_sources": ["synthetic_duplicate"],
                "raw_similarity": 1.0,
                "expected_label": 1,
                "label_type": "synthetic_duplicate",
                "label_reason": synthetic["metadata_json"]["synthetic_rule"],
            }
        )
    return synthetic_documents, pairs


def _build_hard_negative_pairs(
    documents: list[dict],
    relations: list[dict],
    hard_negative_count: int,
    random_generator: random.Random,
) -> list[dict]:
    """构造同主题非重复硬负例 pair。

    参数:
        documents: 标准化文献列表。
        relations: 已有关系记录。
        hard_negative_count: 硬负例数量。
        random_generator: 随机数生成器。

    返回:
        硬负例 pair 列表。
    """
    document_ids = {document["document_id"] for document in documents}
    relation_candidates = [
        relation
        for relation in relations
        if relation.get("relation_type") == "same_topic_non_duplicate"
        and relation.get("source_document_id") in document_ids
        and relation.get("target_document_id") in document_ids
    ]
    random_generator.shuffle(relation_candidates)
    pairs: list[dict] = []
    seen_pairs: set[tuple[str, str]] = set()
    for relation in relation_candidates:
        source_id = relation["source_document_id"]
        target_id = relation["target_document_id"]
        pair_key = _pair_key(source_id, target_id)
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        pairs.append(
            {
                "source_document_id": source_id,
                "target_document_id": target_id,
                "candidate_sources": ["hard_negative"],
                "raw_similarity": float(relation.get("topic_score", relation.get("full_similarity", 0.0)) or 0.0),
                "expected_label": 0,
                "label_type": "hard_negative",
                "label_reason": relation.get("relation_type", "same_topic_non_duplicate"),
            }
        )
        if len(pairs) >= hard_negative_count:
            break
    return pairs


def _collect_pair_documents(documents: list[dict], synthetic_documents: list[dict], pairs: list[dict]) -> list[dict]:
    """收集评估 pair 需要的文献记录。

    参数:
        documents: 原始标准化文献列表。
        synthetic_documents: 合成文献列表。
        pairs: 评估 pair 列表。

    返回:
        去重后的评估文献列表。
    """
    lookup = {document["document_id"]: document for document in documents}
    lookup.update({document["document_id"]: document for document in synthetic_documents})
    needed_ids = {pair["source_document_id"] for pair in pairs} | {pair["target_document_id"] for pair in pairs}
    return [lookup[document_id] for document_id in sorted(needed_ids) if document_id in lookup]


def build_evaluation_set(
    documents: Iterable[dict],
    relations: Iterable[dict] | None = None,
    synthetic_count: int = 200,
    hard_negative_count: int = 200,
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """构造 synthetic duplicate 与 hard negative 评估集。

    参数:
        documents: 标准化文献记录。
        relations: 可选已有 pair_relations，用于抽取同主题非重复硬负例。
        synthetic_count: 合成正例数量。
        hard_negative_count: 硬负例数量。
        seed: 随机种子。

    返回:
        评估文献列表与评估 pair 列表。
    """
    document_list = list(documents)
    relation_list = list(relations or [])
    random_generator = random.Random(seed)
    synthetic_documents, synthetic_pairs = _build_synthetic_pairs(document_list, synthetic_count, random_generator)
    hard_negative_pairs = _build_hard_negative_pairs(document_list, relation_list, hard_negative_count, random_generator)
    pairs = synthetic_pairs + hard_negative_pairs
    eval_documents = _collect_pair_documents(document_list, synthetic_documents, pairs)
    LOGGER.info("评估集构建完成: documents=%s pairs=%s", len(eval_documents), len(pairs))
    return eval_documents, pairs


def score_evaluation_pairs(documents: Iterable[dict], pairs: Iterable[dict]) -> list[dict]:
    """对评估 pair 运行现有关系评分器。

    参数:
        documents: 评估文献记录。
        pairs: 评估 pair 记录。

    返回:
        带评分、分类和 expected_label 的关系记录。
    """
    document_list = list(documents)
    pair_list = list(pairs)
    views = build_semantic_views(document_list)
    return score_candidate_pairs(pair_list, document_list, views)


def _predict_relation(relation: dict, system: str) -> int:
    """按系统名称生成二分类预测。

    参数:
        relation: 评分后的关系记录。
        system: 系统名称。

    返回:
        预测标签，1 表示重复。
    """
    relation_type = relation.get("relation_type")
    if system in {"iad_sieve_conservative", "rsl_sieve_conservative"}:
        return 1 if relation_type in {"exact_duplicate", "high_confidence_duplicate"} else 0
    if system in {"iad_sieve_review_inclusive", "rsl_sieve_review_inclusive"}:
        return 1 if relation_type in {"exact_duplicate", "high_confidence_duplicate", "suspected_duplicate"} else 0
    if system == "duplicate_score_threshold":
        return 1 if float(relation.get("duplicate_score", 0.0) or 0.0) >= 0.82 else 0
    if system == "title_author_rule":
        return 1 if float(relation.get("title_similarity", 0.0) or 0.0) >= 0.99 and float(relation.get("first_author_match", 0.0) or 0.0) >= 1.0 else 0
    return 0


def _predict_agenda_relation(relation: dict, system: str) -> int:
    """按系统名称生成 same_agenda 预测。

    参数:
        relation: 评分后的关系记录。
        system: 系统名称。

    返回:
        预测标签，1 表示预测为议题相关。
    """
    if system == "iad_agenda_score_threshold":
        return 1 if float(relation.get("agenda_score", relation.get("topic_score", 0.0)) or 0.0) >= 0.65 else 0
    if system == "same_topic_non_duplicate_relation":
        return 1 if relation.get("relation_type") == "same_topic_non_duplicate" else 0
    if system == "dense_agenda_threshold":
        return 1 if float(relation.get("full_similarity", 0.0) or 0.0) >= 0.65 else 0
    return 0


def summarize_scored_eval_pairs(relations: Iterable[dict]) -> list[dict]:
    """汇总已评分评估 pair 的二分类指标。

    参数:
        relations: 评分后的评估关系记录。

    返回:
        系统指标记录列表。
    """
    relation_list = [relation for relation in relations if "expected_label" in relation]
    labels = [int(relation["expected_label"]) for relation in relation_list]
    rows: list[dict] = []
    systems = [
        "iad_sieve_conservative",
        "iad_sieve_review_inclusive",
        "rsl_sieve_conservative",
        "rsl_sieve_review_inclusive",
        "duplicate_score_threshold",
        "title_author_rule",
    ]
    for system in systems:
        predictions = [_predict_relation(relation, system) for relation in relation_list]
        metrics = calculate_binary_metrics(labels, predictions)
        rows.append({"system": system, "metric_target": "same_work_false_merge", **metrics})
    agenda_relations = [relation for relation in relation_list if "expected_agenda_label" in relation]
    if agenda_relations:
        agenda_labels = [int(relation["expected_agenda_label"]) for relation in agenda_relations]
        agenda_systems = ["iad_agenda_score_threshold", "same_topic_non_duplicate_relation", "dense_agenda_threshold"]
        for system in agenda_systems:
            predictions = [_predict_agenda_relation(relation, system) for relation in agenda_relations]
            metrics = calculate_binary_metrics(agenda_labels, predictions)
            rows.append({"system": system, "metric_target": "same_agenda_proxy", **metrics})
    return rows
