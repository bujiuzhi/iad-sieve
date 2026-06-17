"""外部强基线分数评估适配模块。"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from iad_sieve.evaluation.baseline_runner import calculate_binary_metrics
from iad_sieve.utils.io_utils import read_jsonl


LOGGER = logging.getLogger(__name__)
SUPPORTED_METRIC_TARGETS = {"same_work", "same_agenda"}


def _pair_key(source_id: object, target_id: object) -> tuple[str, str]:
    """生成无向文献对键。

    参数:
        source_id: 源文献 ID。
        target_id: 目标文献 ID。

    返回:
        排序后的文献 ID 二元组。
    """
    return tuple(sorted((str(source_id or ""), str(target_id or ""))))


def _as_float(record: dict, field: str) -> float | None:
    """安全读取浮点字段。

    参数:
        record: 输入记录。
        field: 字段名。

    返回:
        浮点值；缺失或非法时返回 None。
    """
    if field not in record:
        return None
    try:
        return float(record.get(field))
    except (TypeError, ValueError):
        LOGGER.warning("外部 baseline 分数字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return None


def _read_records(path: str | Path) -> list[dict]:
    """读取 CSV、JSONL 或 JSON 记录。

    参数:
        path: 输入文件路径。

    返回:
        记录列表。
    """
    input_path = Path(path)
    try:
        if input_path.suffix == ".jsonl":
            return list(read_jsonl(input_path))
        if input_path.suffix == ".json":
            payload = json.loads(input_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return [dict(record) for record in payload]
            if isinstance(payload, dict):
                for field in ["data", "records", "predictions", "rows"]:
                    value = payload.get(field)
                    if isinstance(value, list):
                        return [dict(record) for record in value]
                return [payload]
        with input_path.open("r", encoding="utf-8", newline="") as file:
            return [dict(row) for row in csv.DictReader(file)]
    except Exception:
        LOGGER.exception("读取外部 baseline 文件失败: %s", path)
        raise
    raise ValueError(f"不支持的外部 baseline 文件格式: {path}")


def _first_non_empty(record: dict, fields: list[str]) -> object:
    """读取第一个非空字段。

    参数:
        record: 输入记录。
        fields: 候选字段名。

    返回:
        字段值；全部缺失时返回空字符串。
    """
    for field in fields:
        value = record.get(field)
        if value is not None and value != "":
            return value
    return ""


def read_external_baseline_scores(path: str | Path, score_field: str) -> dict[tuple[str, str], float]:
    """读取外部模型 pair 分数。

    参数:
        path: CSV/JSONL/JSON 分数文件。
        score_field: 分数字段名。

    返回:
        无向 pair key 到分数的映射。
    """
    scores: dict[tuple[str, str], float] = {}
    for row in _read_records(path):
        source_id = _first_non_empty(row, ["source_document_id", "source_id", "left_id", "query_id", "paper_id_1", "id1"])
        target_id = _first_non_empty(row, ["target_document_id", "target_id", "right_id", "candidate_id", "paper_id_2", "id2"])
        score = _as_float(row, score_field)
        if not source_id or not target_id or score is None:
            LOGGER.warning("外部 baseline 记录缺少 pair ID 或分数，跳过: %s", row)
            continue
        scores[_pair_key(source_id, target_id)] = score
    LOGGER.info("外部 baseline 分数读取完成: path=%s scores=%s", path, len(scores))
    return scores


def attach_external_baseline_scores(
    relations: list[dict],
    scores: dict[tuple[str, str], float],
    output_score_field: str,
) -> list[dict]:
    """将外部 baseline 分数合并到关系记录。

    参数:
        relations: 已评分关系记录。
        scores: 无向 pair key 到分数的映射。
        output_score_field: 写入关系记录的分数字段。

    返回:
        合并后的关系记录列表。
    """
    attached_relations: list[dict] = []
    matched_count = 0
    for relation in relations:
        output_relation = dict(relation)
        key = _pair_key(relation.get("source_document_id"), relation.get("target_document_id"))
        if key in scores:
            output_relation[output_score_field] = scores[key]
            matched_count += 1
        attached_relations.append(output_relation)
    LOGGER.info("外部 baseline 分数合并完成: relations=%s matched=%s", len(relations), matched_count)
    return attached_relations


def _target_label(relation: dict, metric_target: str) -> int | None:
    """读取评估目标标签。

    参数:
        relation: 关系记录。
        metric_target: same_work 或 same_agenda。

    返回:
        0/1 标签；缺失时返回 None。
    """
    if metric_target == "same_work":
        return int(relation["expected_label"]) if "expected_label" in relation else None
    if metric_target == "same_agenda":
        return int(relation["expected_agenda_label"]) if "expected_agenda_label" in relation else None
    raise ValueError(f"不支持的外部 baseline 评估目标: {metric_target}")


def evaluate_external_baseline(
    relations: list[dict],
    system_name: str,
    score_field: str,
    thresholds: list[float],
    metric_target: str = "same_work",
    baseline_family: str = "unknown",
    execution_mode: str = "precomputed_scores",
    split_field: str = "",
    eval_splits: list[str] | None = None,
) -> list[dict]:
    """按阈值评估外部 baseline 分数。

    参数:
        relations: 已合并外部分数的关系记录。
        system_name: 外部 baseline 名称。
        score_field: 关系记录中的分数字段。
        thresholds: 分数阈值列表。
        metric_target: same_work 或 same_agenda。
        baseline_family: baseline 家族，如 representation、entity_matching、llm_judge。
        execution_mode: 执行模式，如 actual_model、api_model、fallback。
        split_field: 可选 split 字段；为空时评估全部记录。
        eval_splits: 可选目标 split 列表；为空时使用 split_field 中观察到的所有 split。

    返回:
        指标摘要记录列表。
    """
    if metric_target not in SUPPORTED_METRIC_TARGETS:
        raise ValueError(f"不支持的外部 baseline 评估目标: {metric_target}")
    cleaned_eval_splits = [str(split) for split in eval_splits or [] if str(split)]
    if split_field:
        observed_splits = sorted({str(relation.get(split_field, "")) for relation in relations if relation.get(split_field)})
        target_splits = cleaned_eval_splits or observed_splits
        split_groups = [
            (split, [relation for relation in relations if str(relation.get(split_field, "")) == split])
            for split in target_splits
        ]
    else:
        split_groups = [("", relations)]
    rows: list[dict] = []
    for split, split_relations in split_groups:
        labeled_rows: list[tuple[int, float]] = []
        missing_score_count = 0
        missing_label_count = 0
        for relation in split_relations:
            label = _target_label(relation, metric_target)
            if label is None:
                missing_label_count += 1
                continue
            score = _as_float(relation, score_field)
            if score is None:
                missing_score_count += 1
                continue
            labeled_rows.append((label, score))
        labels = [label for label, _ in labeled_rows]
        for threshold in thresholds:
            predictions = [1 if score >= threshold else 0 for _, score in labeled_rows]
            metrics = calculate_binary_metrics(labels, predictions)
            row = {
                "system": system_name,
                "metric_target": metric_target,
                "baseline_family": baseline_family,
                "execution_mode": execution_mode,
                "score_field": score_field,
                "threshold": threshold,
                "missing_score_count": missing_score_count,
                "missing_label_count": missing_label_count,
                **metrics,
            }
            if split_field:
                row["split_field"] = split_field
                row["eval_split"] = split
            rows.append(row)
    LOGGER.info("外部 baseline 评估完成: system=%s rows=%s", system_name, len(rows))
    return rows
