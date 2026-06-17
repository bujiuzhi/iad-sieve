"""错误分析与人工标注样本导出模块。"""

from __future__ import annotations

import csv
import logging
import random
from pathlib import Path

from iad_sieve.evaluation.baseline_runner import calculate_binary_metrics, get_prediction_systems
from iad_sieve.evaluation.weak_label_builder import build_weak_labels
from iad_sieve.utils.io_utils import ensure_directory, write_jsonl


LOGGER = logging.getLogger(__name__)
SUMMARY_FIELDS = [
    "system",
    "weak_label_count",
    "positive_label_count",
    "negative_label_count",
    "predicted_positive_count",
    "true_positive",
    "false_positive",
    "true_negative",
    "false_negative",
    "precision",
    "recall",
    "f1",
    "false_merge_rate",
]
CASE_FIELDS = [
    "system",
    "error_type",
    "source_document_id",
    "target_document_id",
    "weak_label",
    "prediction",
    "relation_type",
    "duplicate_score",
    "topic_score",
    "full_similarity",
    "lexical_similarity",
    "title_similarity",
    "conflict_score",
    "candidate_sources",
]
ANNOTATION_FIELDS = [
    "annotation_id",
    "source_document_id",
    "target_document_id",
    "suggested_label",
    "label_reason",
    "relation_type",
    "duplicate_score",
    "topic_score",
    "full_similarity",
    "lexical_similarity",
    "title_similarity",
    "conflict_score",
    "candidate_sources",
    "source_title",
    "target_title",
    "source_abstract",
    "target_abstract",
    "source_authors",
    "target_authors",
    "source_categories",
    "target_categories",
    "source_publication_year",
    "target_publication_year",
    "annotator_label",
    "annotation_notes",
]


def _pair_key(record: dict) -> tuple[str, str]:
    """生成无向文献对键。

    参数:
        record: 包含 source_document_id 与 target_document_id 的记录。

    返回:
        排序后的文献 ID 二元组。
    """
    return tuple(sorted((str(record.get("source_document_id", "")), str(record.get("target_document_id", "")))))


def _as_float(record: dict, field: str) -> float:
    """安全读取浮点字段。

    参数:
        record: 输入记录。
        field: 字段名。

    返回:
        浮点值，缺失或非法时返回 0。
    """
    try:
        return float(record.get(field, 0.0) or 0.0)
    except (TypeError, ValueError):
        LOGGER.warning("错误分析字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return 0.0


def _build_labeled_relations(relations: list[dict]) -> list[tuple[dict, dict]]:
    """构建关系记录与弱标签记录列表。

    参数:
        relations: pair_relations 记录列表。

    返回:
        关系记录与弱标签记录组成的列表。
    """
    label_lookup = {_pair_key(label): label for label in build_weak_labels(relations)}
    return [(relation, label_lookup[_pair_key(relation)]) for relation in relations if _pair_key(relation) in label_lookup]


def _case_priority(case_row: dict) -> tuple[float, float, str, str]:
    """计算错误案例排序键。

    参数:
        case_row: 错误案例记录。

    返回:
        排序键，高风险案例优先。
    """
    if case_row["error_type"] == "false_positive":
        primary_score = _as_float(case_row, "duplicate_score")
    else:
        primary_score = _as_float(case_row, "topic_score")
    secondary_score = _as_float(case_row, "full_similarity")
    return (-primary_score, -secondary_score, str(case_row["source_document_id"]), str(case_row["target_document_id"]))


def _build_case_row(system_name: str, error_type: str, relation: dict, weak_label: int, prediction: int) -> dict:
    """构造错误案例记录。

    参数:
        system_name: 系统名称。
        error_type: 错误类型。
        relation: 关系记录。
        weak_label: 弱标签。
        prediction: 系统预测。

    返回:
        错误案例记录。
    """
    return {
        "system": system_name,
        "error_type": error_type,
        "source_document_id": relation.get("source_document_id", ""),
        "target_document_id": relation.get("target_document_id", ""),
        "weak_label": weak_label,
        "prediction": prediction,
        "relation_type": relation.get("relation_type", ""),
        "duplicate_score": _as_float(relation, "duplicate_score"),
        "topic_score": _as_float(relation, "topic_score"),
        "full_similarity": _as_float(relation, "full_similarity"),
        "lexical_similarity": _as_float(relation, "lexical_similarity"),
        "title_similarity": _as_float(relation, "title_similarity"),
        "conflict_score": _as_float(relation, "conflict_score"),
        "candidate_sources": ",".join(str(value) for value in relation.get("candidate_sources", [])),
    }


def _format_authors(document: dict) -> str:
    """格式化作者字段。

    参数:
        document: 文献记录。

    返回:
        逗号分隔作者字符串。
    """
    authors = document.get("authors", [])
    if isinstance(authors, list):
        return ", ".join(str(author) for author in authors)
    return str(authors or "")


def _build_annotation_row(index: int, relation: dict, label: dict, document_lookup: dict[str, dict] | None = None) -> dict:
    """构造人工标注样本记录。

    参数:
        index: 样本序号。
        relation: 关系记录。
        label: 弱标签记录。
        document_lookup: 可选文献 ID 到文献记录的映射。

    返回:
        人工标注样本记录。
    """
    documents = document_lookup or {}
    source_document = documents.get(str(relation.get("source_document_id", "")), {})
    target_document = documents.get(str(relation.get("target_document_id", "")), {})
    return {
        "annotation_id": f"ann-{index:06d}",
        "source_document_id": relation.get("source_document_id", ""),
        "target_document_id": relation.get("target_document_id", ""),
        "suggested_label": int(label.get("weak_label", 0)),
        "label_reason": label.get("label_reason", ""),
        "relation_type": relation.get("relation_type", ""),
        "duplicate_score": _as_float(relation, "duplicate_score"),
        "topic_score": _as_float(relation, "topic_score"),
        "full_similarity": _as_float(relation, "full_similarity"),
        "lexical_similarity": _as_float(relation, "lexical_similarity"),
        "title_similarity": _as_float(relation, "title_similarity"),
        "conflict_score": _as_float(relation, "conflict_score"),
        "candidate_sources": ",".join(str(value) for value in relation.get("candidate_sources", [])),
        "source_title": source_document.get("title") or source_document.get("title_normalized", ""),
        "target_title": target_document.get("title") or target_document.get("title_normalized", ""),
        "source_abstract": source_document.get("abstract") or source_document.get("abstract_normalized", ""),
        "target_abstract": target_document.get("abstract") or target_document.get("abstract_normalized", ""),
        "source_authors": _format_authors(source_document),
        "target_authors": _format_authors(target_document),
        "source_categories": source_document.get("categories", ""),
        "target_categories": target_document.get("categories", ""),
        "source_publication_year": source_document.get("publication_year", ""),
        "target_publication_year": target_document.get("publication_year", ""),
        "annotator_label": "",
        "annotation_notes": "",
    }


def _select_annotation_sample(labeled_relations: list[tuple[dict, dict]], annotation_sample_size: int, seed: int) -> list[tuple[dict, dict]]:
    """选择人工标注样本。

    参数:
        labeled_relations: 关系记录与弱标签记录列表。
        annotation_sample_size: 样本数量。
        seed: 随机种子。

    返回:
        抽样后的关系与标签列表。
    """
    if annotation_sample_size <= 0 or not labeled_relations:
        return []
    positives = [(relation, label) for relation, label in labeled_relations if int(label["weak_label"]) == 1]
    negatives = [(relation, label) for relation, label in labeled_relations if int(label["weak_label"]) == 0]
    rng = random.Random(seed)
    rng.shuffle(positives)
    rng.shuffle(negatives)
    positive_target = min(len(positives), annotation_sample_size // 2)
    negative_target = min(len(negatives), annotation_sample_size - positive_target)
    selected = positives[:positive_target] + negatives[:negative_target]
    remaining = [item for item in labeled_relations if item not in selected]
    rng.shuffle(remaining)
    selected.extend(remaining[: max(0, annotation_sample_size - len(selected))])
    return selected[:annotation_sample_size]


def build_error_analysis(
    relations: list[dict],
    documents: list[dict] | None = None,
    systems: list[str] | None = None,
    max_cases_per_bucket: int = 50,
    annotation_sample_size: int = 100,
    seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    """构建错误分析摘要、错误案例和人工标注样本。

    参数:
        relations: pair_relations 记录列表。
        documents: 可选标准化文献记录，用于补充人工标注上下文。
        systems: 可选系统名称列表，空值表示全部系统。
        max_cases_per_bucket: 每个系统每类错误最多导出的案例数。
        annotation_sample_size: 人工标注样本数量。
        seed: 随机种子。

    返回:
        摘要记录、错误案例记录、人工标注样本记录三元组。
    """
    if max_cases_per_bucket < 0:
        raise ValueError("max_cases_per_bucket 必须大于等于 0")
    if annotation_sample_size < 0:
        raise ValueError("annotation_sample_size 必须大于等于 0")
    active_systems = get_prediction_systems()
    if systems:
        requested = set(systems)
        active_systems = [system for system in active_systems if system[0] in requested]
    labeled_relations = _build_labeled_relations(relations)
    document_lookup = {str(document.get("document_id", "")): document for document in documents or []}
    summary_rows: list[dict] = []
    case_rows: list[dict] = []
    for system_name, _, predicate in active_systems:
        labels = [int(label["weak_label"]) for _, label in labeled_relations]
        predictions = [1 if predicate(relation) else 0 for relation, _ in labeled_relations]
        metrics = calculate_binary_metrics(labels, predictions)
        summary_rows.append({"system": system_name, **metrics})
        buckets: dict[str, list[dict]] = {"false_positive": [], "false_negative": [], "true_positive": [], "true_negative": []}
        for (relation, label), prediction in zip(labeled_relations, predictions, strict=True):
            weak_label = int(label["weak_label"])
            if weak_label == 1 and prediction == 1:
                bucket = "true_positive"
            elif weak_label == 0 and prediction == 1:
                bucket = "false_positive"
            elif weak_label == 0 and prediction == 0:
                bucket = "true_negative"
            else:
                bucket = "false_negative"
            buckets[bucket].append(_build_case_row(system_name, bucket, relation, weak_label, prediction))
        for bucket_name, rows in buckets.items():
            if bucket_name in {"false_positive", "false_negative"}:
                selected_rows = sorted(rows, key=_case_priority)[:max_cases_per_bucket]
            else:
                selected_rows = sorted(rows, key=_case_priority)[: min(5, max_cases_per_bucket)]
            case_rows.extend(selected_rows)
    annotation_rows = [
        _build_annotation_row(index, relation, label, document_lookup)
        for index, (relation, label) in enumerate(_select_annotation_sample(labeled_relations, annotation_sample_size, seed), start=1)
    ]
    return summary_rows, case_rows, annotation_rows


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    """写入 CSV 文件。

    参数:
        path: 输出路径。
        rows: 记录列表。
        fieldnames: 字段顺序。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_error_analysis_outputs(
    summary_rows: list[dict],
    case_rows: list[dict],
    annotation_rows: list[dict],
    output_dir: str | Path,
) -> None:
    """写入错误分析与人工标注样本文件。

    参数:
        summary_rows: 摘要记录。
        case_rows: 错误案例记录。
        annotation_rows: 人工标注样本记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    resolved_output_dir = ensure_directory(output_dir)
    _write_csv(resolved_output_dir / "error_analysis_summary.csv", summary_rows, SUMMARY_FIELDS)
    write_jsonl(case_rows, resolved_output_dir / "error_cases.jsonl")
    write_jsonl(annotation_rows, resolved_output_dir / "manual_annotation_sample.jsonl")
