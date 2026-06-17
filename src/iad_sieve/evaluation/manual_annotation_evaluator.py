"""人工标注结果评估模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.evaluation.baseline_runner import calculate_binary_metrics
from iad_sieve.utils.io_utils import ensure_directory, write_jsonl


LOGGER = logging.getLogger(__name__)
POSITIVE_LABELS = {"1", "true", "yes", "y", "duplicate", "dup", "same", "positive"}
NEGATIVE_LABELS = {"0", "false", "no", "n", "not_duplicate", "non_duplicate", "different", "negative"}
SUMMARY_FIELDS = [
    "sample_count",
    "labeled_count",
    "unlabeled_count",
    "manual_positive_count",
    "manual_negative_count",
    "suggested_positive_count",
    "suggested_agreement_count",
    "suggested_disagreement_count",
    "suggested_agreement_rate",
    "suggested_label_precision",
    "suggested_label_recall",
    "suggested_label_f1",
    "suggested_label_false_merge_rate",
]


def _normalize_label(raw_value: object) -> int | None:
    """归一化人工标签。

    参数:
        raw_value: 原始标签值。

    返回:
        1 表示重复，0 表示非重复，无法识别或空值返回 None。
    """
    if raw_value is None:
        return None
    normalized = str(raw_value).strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return None
    if normalized in POSITIVE_LABELS:
        return 1
    if normalized in NEGATIVE_LABELS:
        return 0
    LOGGER.warning("无法识别人工标注标签: %r", raw_value)
    return None


def _normalize_suggested_label(record: dict) -> int:
    """归一化建议标签。

    参数:
        record: 人工标注记录。

    返回:
        建议标签，无法识别时默认 0。
    """
    normalized = _normalize_label(record.get("suggested_label"))
    return int(normalized or 0)


def evaluate_manual_annotations(annotation_records: list[dict]) -> tuple[list[dict], list[dict]]:
    """评估人工标注结果。

    参数:
        annotation_records: 人工标注 JSONL 记录。

    返回:
        摘要记录列表和分歧记录列表。
    """
    labeled_rows: list[tuple[dict, int, int]] = []
    unlabeled_count = 0
    for record in annotation_records:
        manual_label = _normalize_label(record.get("annotator_label"))
        if manual_label is None:
            unlabeled_count += 1
            continue
        suggested_label = _normalize_suggested_label(record)
        labeled_rows.append((record, manual_label, suggested_label))
    manual_labels = [manual_label for _, manual_label, _ in labeled_rows]
    suggested_labels = [suggested_label for _, _, suggested_label in labeled_rows]
    metrics = calculate_binary_metrics(manual_labels, suggested_labels)
    agreement_count = sum(1 for manual_label, suggested_label in zip(manual_labels, suggested_labels, strict=True) if manual_label == suggested_label)
    disagreement_rows = []
    for record, manual_label, suggested_label in labeled_rows:
        if manual_label == suggested_label:
            continue
        disagreement = dict(record)
        disagreement["manual_label_normalized"] = manual_label
        disagreement["suggested_label_normalized"] = suggested_label
        disagreement_rows.append(disagreement)
    labeled_count = len(labeled_rows)
    summary = {
        "sample_count": len(annotation_records),
        "labeled_count": labeled_count,
        "unlabeled_count": unlabeled_count,
        "manual_positive_count": sum(manual_labels),
        "manual_negative_count": labeled_count - sum(manual_labels),
        "suggested_positive_count": sum(suggested_labels),
        "suggested_agreement_count": agreement_count,
        "suggested_disagreement_count": len(disagreement_rows),
        "suggested_agreement_rate": round(agreement_count / labeled_count, 6) if labeled_count else 0.0,
        "suggested_label_precision": metrics["precision"],
        "suggested_label_recall": metrics["recall"],
        "suggested_label_f1": metrics["f1"],
        "suggested_label_false_merge_rate": metrics["false_merge_rate"],
    }
    return [summary], disagreement_rows


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


def write_manual_annotation_outputs(summary_rows: list[dict], disagreement_rows: list[dict], output_dir: str | Path) -> None:
    """写入人工标注评估结果。

    参数:
        summary_rows: 摘要记录。
        disagreement_rows: 建议标签与人工标签分歧记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    resolved_output_dir = ensure_directory(output_dir)
    _write_csv(resolved_output_dir / "manual_annotation_summary.csv", summary_rows, SUMMARY_FIELDS)
    write_jsonl(disagreement_rows, resolved_output_dir / "manual_annotation_disagreements.jsonl")
