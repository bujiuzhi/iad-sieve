"""single-space union-find baseline 模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, write_records


LOGGER = logging.getLogger(__name__)
SUMMARY_FIELDS = [
    "system",
    "baseline_family",
    "execution_mode",
    "metric_target",
    "score_field",
    "threshold",
    "pair_count",
    "document_count",
    "cluster_count",
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
    "hard_negative_pair_count",
    "hard_negative_false_merge_count",
    "hard_negative_false_merge_rate",
    "same_agenda_negative_count",
    "same_agenda_false_merge_count",
    "same_agenda_false_merge_rate",
]


class _UnionFind:
    """最小并查集实现。"""

    def __init__(self, items: list[str]) -> None:
        """初始化并查集。

        参数:
            items: 初始元素列表。

        返回:
            无。
        """
        self.parent = {item: item for item in items}

    def find(self, item: str) -> str:
        """查找集合代表。

        参数:
            item: 元素 ID。

        返回:
            集合代表 ID。
        """
        if item not in self.parent:
            self.parent[item] = item
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        """合并两个元素所在集合。

        参数:
            left: 左侧元素。
            right: 右侧元素。

        返回:
            无。
        """
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root

    def cluster_count(self) -> int:
        """返回集合数量。

        参数:
            无。

        返回:
            去重后的集合数量。
        """
        return len({self.find(item) for item in self.parent})


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
        LOGGER.warning("single-space union 字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return 0.0


def _as_int(record: dict, field: str) -> int:
    """安全读取整数字段。

    参数:
        record: 输入记录。
        field: 字段名。

    返回:
        整数值，缺失或非法时返回 0。
    """
    try:
        return int(record.get(field, 0) or 0)
    except (TypeError, ValueError):
        LOGGER.warning("single-space union 字段无法转为整数: field=%s value=%r", field, record.get(field))
        return 0


def _safe_divide(numerator: int, denominator: int) -> float:
    """安全除法。

    参数:
        numerator: 分子。
        denominator: 分母。

    返回:
        四舍五入后的比例，分母为 0 时返回 0。
    """
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def _f1_score(precision: float, recall: float) -> float:
    """计算 F1。

    参数:
        precision: 查准率。
        recall: 查全率。

    返回:
        F1 分数。
    """
    if precision + recall == 0.0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 6)


def _is_hard_negative(record: dict) -> bool:
    """判断关系是否为 hard negative。

    参数:
        record: 关系记录。

    返回:
        hard_negative_level 非 none，或 same_agenda=1 且 same_work=0 时返回 True。
    """
    hard_negative_level = str(record.get("hard_negative_level", "none") or "none").lower()
    if hard_negative_level and hard_negative_level != "none":
        return True
    return _as_int(record, "expected_label") == 0 and _as_int(record, "expected_agenda_label") == 1


def _document_ids(relations: list[dict]) -> list[str]:
    """从关系中抽取文献 ID。

    参数:
        relations: pair 关系记录。

    返回:
        排序后的文献 ID 列表。
    """
    ids: set[str] = set()
    for relation in relations:
        ids.add(str(relation.get("source_document_id", "")))
        ids.add(str(relation.get("target_document_id", "")))
    return sorted(item for item in ids if item)


def run_single_space_union_baseline(
    relations: list[dict],
    system_name: str,
    score_field: str,
    threshold: float,
    baseline_family: str = "single_space_union",
    execution_mode: str = "actual_algorithm",
) -> tuple[list[dict], dict]:
    """运行普通 single-space union-find baseline。

    参数:
        relations: 含 baseline 分数与标签的 pair 记录。
        system_name: baseline 名称。
        score_field: 单空间分数字段。
        threshold: 合并阈值。
        baseline_family: baseline 家族。
        execution_mode: 执行模式。

    返回:
        pair 预测记录和摘要记录。
    """
    union_find = _UnionFind(_document_ids(relations))
    for relation in relations:
        if score_field not in relation:
            LOGGER.warning("single-space union 跳过缺失分数的关系: score_field=%s relation=%s", score_field, relation)
            continue
        if _as_float(relation, score_field) >= threshold:
            union_find.union(str(relation.get("source_document_id", "")), str(relation.get("target_document_id", "")))

    true_positive = false_positive = true_negative = false_negative = 0
    hard_negative_pair_count = hard_negative_false_merge_count = 0
    same_agenda_negative_count = same_agenda_false_merge_count = 0
    predictions: list[dict] = []
    for relation in relations:
        source_document_id = str(relation.get("source_document_id", ""))
        target_document_id = str(relation.get("target_document_id", ""))
        expected_label = _as_int(relation, "expected_label")
        expected_agenda_label = _as_int(relation, "expected_agenda_label")
        prediction = 1 if union_find.find(source_document_id) == union_find.find(target_document_id) else 0
        hard_negative = _is_hard_negative(relation)
        same_agenda_negative = expected_label == 0 and expected_agenda_label == 1
        error_type = ""
        if expected_label == 1 and prediction == 1:
            true_positive += 1
        elif expected_label == 0 and prediction == 1:
            false_positive += 1
            error_type = "hard_negative_false_merge" if hard_negative else "false_merge"
        elif expected_label == 0 and prediction == 0:
            true_negative += 1
        elif expected_label == 1 and prediction == 0:
            false_negative += 1
            error_type = "missed_same_work"
        if hard_negative:
            hard_negative_pair_count += 1
            if prediction == 1:
                hard_negative_false_merge_count += 1
        if same_agenda_negative:
            same_agenda_negative_count += 1
            if prediction == 1:
                same_agenda_false_merge_count += 1
        predictions.append(
            {
                **relation,
                "system": system_name,
                "baseline_family": baseline_family,
                "execution_mode": execution_mode,
                "threshold": threshold,
                "single_space_union_prediction": prediction,
                "source_cluster_id": union_find.find(source_document_id),
                "target_cluster_id": union_find.find(target_document_id),
                "error_type": error_type,
            }
        )

    precision = _safe_divide(true_positive, true_positive + false_positive)
    recall = _safe_divide(true_positive, true_positive + false_negative)
    summary = {
        "system": system_name,
        "baseline_family": baseline_family,
        "execution_mode": execution_mode,
        "metric_target": "same_work_false_merge",
        "score_field": score_field,
        "threshold": threshold,
        "pair_count": len(predictions),
        "document_count": len(_document_ids(relations)),
        "cluster_count": union_find.cluster_count(),
        "positive_label_count": true_positive + false_negative,
        "negative_label_count": false_positive + true_negative,
        "predicted_positive_count": true_positive + false_positive,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "true_negative": true_negative,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": _f1_score(precision, recall),
        "false_merge_rate": _safe_divide(false_positive, false_positive + true_negative),
        "hard_negative_pair_count": hard_negative_pair_count,
        "hard_negative_false_merge_count": hard_negative_false_merge_count,
        "hard_negative_false_merge_rate": _safe_divide(hard_negative_false_merge_count, hard_negative_pair_count),
        "same_agenda_negative_count": same_agenda_negative_count,
        "same_agenda_false_merge_count": same_agenda_false_merge_count,
        "same_agenda_false_merge_rate": _safe_divide(same_agenda_false_merge_count, same_agenda_negative_count),
    }
    LOGGER.info("single-space union baseline 完成: system=%s threshold=%s pairs=%s", system_name, threshold, len(predictions))
    return predictions, summary


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 记录列表。
        fields: 字段列表。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown_report(output_dir: Path, summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        output_dir: 输出目录。
        summary: 摘要记录。

    返回:
        无。
    """
    lines = [
        "# Single-Space Union Baseline",
        "",
        "| system | threshold | cluster_count | hard_negative_false_merge_rate | same_agenda_false_merge_rate | false_positive | false_negative |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| {system} | {threshold} | {cluster_count} | {hard_negative_false_merge_rate} | {same_agenda_false_merge_rate} | {false_positive} | {false_negative} |".format(
            **summary
        ),
        "",
    ]
    output_dir.joinpath("single_space_union_report.md").write_text("\n".join(lines), encoding="utf-8")


def write_single_space_union_outputs(predictions: list[dict], summary: dict, output_dir: str | Path) -> None:
    """写出 single-space union baseline 产物。

    参数:
        predictions: pair 预测记录。
        summary: 摘要记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    resolved_output_dir = ensure_directory(output_dir)
    write_records(predictions, resolved_output_dir / "single_space_union_predictions.jsonl")
    write_records([summary], resolved_output_dir / "single_space_union_summary.jsonl")
    _write_csv(resolved_output_dir / "single_space_union_summary.csv", [summary], SUMMARY_FIELDS)
    _write_markdown_report(resolved_output_dir, summary)
