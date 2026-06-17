"""bootstrap 置信区间评估模块。"""

from __future__ import annotations

import csv
import logging
import random
from pathlib import Path

from iad_sieve.evaluation.baseline_runner import calculate_binary_metrics, get_prediction_systems
from iad_sieve.evaluation.weak_label_builder import build_weak_labels


LOGGER = logging.getLogger(__name__)
METRIC_FIELDS = ["precision", "recall", "f1", "false_merge_rate"]
BOOTSTRAP_CSV_FIELDS = [
    "system",
    "description",
    "weak_label_count",
    "bootstrap_iterations",
    "confidence_level",
    "precision_mean",
    "precision_ci_low",
    "precision_ci_high",
    "recall_mean",
    "recall_ci_low",
    "recall_ci_high",
    "f1_mean",
    "f1_ci_low",
    "f1_ci_high",
    "false_merge_rate_mean",
    "false_merge_rate_ci_low",
    "false_merge_rate_ci_high",
]
IAD_BOOTSTRAP_CSV_FIELDS = [
    "system",
    "metric_scope",
    "stratum_name",
    "stratum_value",
    "prediction_field",
    "score_field",
    "threshold",
    "pair_count",
    "positive_label_count",
    "negative_label_count",
    "predicted_positive_count",
    "true_positive",
    "false_positive",
    "true_negative",
    "false_negative",
    "hard_negative_pair_count",
    "same_agenda_negative_count",
    "bootstrap_iterations",
    "confidence_level",
    "precision_mean",
    "precision_ci_low",
    "precision_ci_high",
    "recall_mean",
    "recall_ci_low",
    "recall_ci_high",
    "f1_mean",
    "f1_ci_low",
    "f1_ci_high",
    "false_merge_rate_mean",
    "false_merge_rate_ci_low",
    "false_merge_rate_ci_high",
    "hard_negative_false_merge_rate_mean",
    "hard_negative_false_merge_rate_ci_low",
    "hard_negative_false_merge_rate_ci_high",
    "same_agenda_false_merge_rate_mean",
    "same_agenda_false_merge_rate_ci_low",
    "same_agenda_false_merge_rate_ci_high",
    "split_field",
    "eval_splits",
]


def _pair_key(record: dict) -> tuple[str, str]:
    """生成无向文献对键。

    参数:
        record: 包含 source_document_id 与 target_document_id 的记录。

    返回:
        排序后的文献 ID 二元组。
    """
    source_id = str(record.get("source_document_id", ""))
    target_id = str(record.get("target_document_id", ""))
    return tuple(sorted((source_id, target_id)))


def _build_labeled_relations(relations: list[dict]) -> list[tuple[dict, int]]:
    """构建可用于 bootstrap 的弱标签关系。

    参数:
        relations: pair_relations 记录列表。

    返回:
        关系记录与弱标签组成的列表。
    """
    label_lookup = {_pair_key(label): int(label["weak_label"]) for label in build_weak_labels(relations)}
    return [(relation, label_lookup[_pair_key(relation)]) for relation in relations if _pair_key(relation) in label_lookup]


def _calculate_metrics_for_sample(labeled_sample: list[tuple[dict, int]], predicate) -> dict:
    """计算单个 bootstrap 样本的二分类指标。

    参数:
        labeled_sample: bootstrap 抽样后的关系与标签列表。
        predicate: 系统预测函数。

    返回:
        指标字典。
    """
    labels = [label for _, label in labeled_sample]
    predictions = [1 if predicate(relation) else 0 for relation, _ in labeled_sample]
    return calculate_binary_metrics(labels, predictions)


def _metric_values_from_confusion_counts(tp_count: int, fp_count: int, tn_count: int, fn_count: int) -> dict[str, float]:
    """由混淆矩阵计数计算指标。

    参数:
        tp_count: true positive 数。
        fp_count: false positive 数。
        tn_count: true negative 数。
        fn_count: false negative 数。

    返回:
        指标字典。
    """
    precision_denominator = tp_count + fp_count
    recall_denominator = tp_count + fn_count
    false_merge_denominator = fp_count + tn_count
    precision = tp_count / precision_denominator if precision_denominator else 0.0
    recall = tp_count / recall_denominator if recall_denominator else 0.0
    f1_score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    false_merge_rate = fp_count / false_merge_denominator if false_merge_denominator else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1_score,
        "false_merge_rate": false_merge_rate,
    }


def _confusion_counts(labels: list[int], predictions: list[int]) -> tuple[int, int, int, int]:
    """统计二分类混淆矩阵。

    参数:
        labels: 标签列表。
        predictions: 预测列表。

    返回:
        TP、FP、TN、FN 四元组。
    """
    true_positive = sum(1 for label, prediction in zip(labels, predictions, strict=True) if label == 1 and prediction == 1)
    false_positive = sum(1 for label, prediction in zip(labels, predictions, strict=True) if label == 0 and prediction == 1)
    true_negative = sum(1 for label, prediction in zip(labels, predictions, strict=True) if label == 0 and prediction == 0)
    false_negative = sum(1 for label, prediction in zip(labels, predictions, strict=True) if label == 1 and prediction == 0)
    return true_positive, false_positive, true_negative, false_negative


def _bootstrap_metric_values_from_counts(
    labels: list[int],
    predictions: list[int],
    iterations: int,
    seed: int,
) -> dict[str, list[float]]:
    """基于混淆矩阵 multinomial 抽样生成 bootstrap 指标。

    参数:
        labels: 标签列表。
        predictions: 预测列表。
        iterations: bootstrap 抽样次数。
        seed: 随机种子。

    返回:
        指标名到 bootstrap 指标值列表的映射。
    """
    sampled_metrics: dict[str, list[float]] = {field: [] for field in METRIC_FIELDS}
    sample_count = len(labels)
    if sample_count == 0:
        return {field: [0.0 for _ in range(iterations)] for field in METRIC_FIELDS}
    true_positive, false_positive, true_negative, false_negative = _confusion_counts(labels, predictions)
    try:
        import numpy as np  # type: ignore

        probabilities = np.asarray([true_positive, false_positive, true_negative, false_negative], dtype="float64") / sample_count
        rng = np.random.default_rng(seed)
        sampled_counts = rng.multinomial(sample_count, probabilities, size=iterations)
        for true_pos, false_pos, true_neg, false_neg in sampled_counts:
            metric_values = _metric_values_from_confusion_counts(int(true_pos), int(false_pos), int(true_neg), int(false_neg))
            for field in METRIC_FIELDS:
                sampled_metrics[field].append(metric_values[field])
        return sampled_metrics
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("numpy multinomial bootstrap 不可用，回退到逐条抽样: %s", exc)
    rng = random.Random(seed)
    indexed_pairs = list(zip(labels, predictions, strict=True))
    for _ in range(iterations):
        sampled_pairs = [indexed_pairs[rng.randrange(sample_count)] for _ in range(sample_count)]
        sampled_labels = [label for label, _ in sampled_pairs]
        sampled_predictions = [prediction for _, prediction in sampled_pairs]
        metric_values = _metric_values_from_confusion_counts(*_confusion_counts(sampled_labels, sampled_predictions))
        for field in METRIC_FIELDS:
            sampled_metrics[field].append(metric_values[field])
    return sampled_metrics


def _percentile(values: list[float], quantile: float) -> float:
    """计算线性插值百分位数。

    参数:
        values: 数值列表。
        quantile: 分位点，范围为 0 到 1。

    返回:
        百分位数。
    """
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    bounded_quantile = min(1.0, max(0.0, quantile))
    position = bounded_quantile * (len(sorted_values) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = position - lower_index
    return float(sorted_values[lower_index] * (1.0 - fraction) + sorted_values[upper_index] * fraction)


def _summarize_metric(metric_values: list[float], confidence_level: float) -> dict[str, float]:
    """汇总单个指标的 bootstrap 均值与置信区间。

    参数:
        metric_values: bootstrap 指标值列表。
        confidence_level: 置信水平。

    返回:
        包含 mean、ci_low、ci_high 的字典。
    """
    if not metric_values:
        return {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    alpha = 1.0 - confidence_level
    mean_value = sum(metric_values) / len(metric_values)
    return {
        "mean": round(mean_value, 6),
        "ci_low": round(_percentile(metric_values, alpha / 2.0), 6),
        "ci_high": round(_percentile(metric_values, 1.0 - alpha / 2.0), 6),
    }


def _as_optional_int(record: dict, field: str) -> int | None:
    """安全读取可选整数字段。

    参数:
        record: 输入记录。
        field: 字段名。

    返回:
        整数值；字段缺失或非法时返回 None。
    """
    if field not in record:
        return None
    try:
        return int(float(record.get(field, 0) or 0))
    except (TypeError, ValueError):
        LOGGER.warning("IAD bootstrap 字段无法转为整数: field=%s value=%r", field, record.get(field))
        return None


def _as_optional_float(record: dict, field: str) -> float | None:
    """安全读取可选浮点字段。

    参数:
        record: 输入记录。
        field: 字段名。

    返回:
        浮点值；字段缺失或非法时返回 None。
    """
    if field not in record:
        return None
    try:
        return float(record.get(field, 0.0) or 0.0)
    except (TypeError, ValueError):
        LOGGER.warning("IAD bootstrap 字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return None


def _is_iad_hard_negative(record: dict, label: int) -> bool:
    """判断 IAD-Bench 记录是否为 hard negative。

    参数:
        record: IAD-Bench pair 或预测记录。
        label: same_work 标签。

    返回:
        same_work=0 且 hard_negative_level 非 none，或 same_agenda=1 时返回 True。
    """
    if label != 0:
        return False
    hard_negative_level = str(record.get("hard_negative_level", "none") or "none").lower()
    if hard_negative_level and hard_negative_level != "none":
        return True
    expected_agenda_label = _as_optional_int(record, "expected_agenda_label")
    return expected_agenda_label == 1


def _is_same_agenda_negative(record: dict, label: int) -> bool:
    """判断记录是否为 same_agenda negative。

    参数:
        record: IAD-Bench pair 或预测记录。
        label: same_work 标签。

    返回:
        same_work=0 且 expected_agenda_label=1 时返回 True。
    """
    expected_agenda_label = _as_optional_int(record, "expected_agenda_label")
    return label == 0 and expected_agenda_label == 1


def _build_iad_labeled_predictions(
    records: list[dict],
    prediction_field: str | None,
    score_field: str | None,
    threshold: float | None,
) -> list[tuple[dict, int, int]]:
    """构造 IAD bootstrap 需要的标签和预测。

    参数:
        records: IAD-Bench pair、baseline scored relation 或 IAD-Risk prediction。
        prediction_field: 直接 0/1 预测字段。
        score_field: 分数字段。
        threshold: 分数转预测阈值。

    返回:
        记录、same_work 标签、预测值组成的列表。
    """
    labeled_predictions: list[tuple[dict, int, int]] = []
    for record in records:
        label = _as_optional_int(record, "expected_label")
        if label is None:
            LOGGER.warning("IAD bootstrap 跳过缺失 expected_label 的记录: %s", record)
            continue
        if prediction_field:
            prediction = _as_optional_int(record, prediction_field)
            if prediction is None:
                LOGGER.warning("IAD bootstrap 跳过缺失预测字段的记录: prediction_field=%s record=%s", prediction_field, record)
                continue
            labeled_predictions.append((record, 1 if prediction else 0, label))
            continue
        if score_field:
            score = _as_optional_float(record, score_field)
            if score is None:
                LOGGER.warning("IAD bootstrap 跳过缺失分数字段的记录: score_field=%s record=%s", score_field, record)
                continue
            labeled_predictions.append((record, 1 if score >= float(threshold or 0.0) else 0, label))
    return labeled_predictions


def _summarize_rate_alias(
    labeled_predictions: list[tuple[dict, int, int]],
    iterations: int,
    seed: int,
    confidence_level: float,
    predicate,
) -> dict[str, float]:
    """对指定 negative 子集汇总误合并率置信区间。

    参数:
        labeled_predictions: 记录、预测和标签三元组。
        iterations: bootstrap 抽样次数。
        seed: 随机种子。
        confidence_level: 置信水平。
        predicate: 子集判断函数。

    返回:
        包含 mean、ci_low、ci_high 的误合并率摘要。
    """
    subset = [(prediction, label) for record, prediction, label in labeled_predictions if predicate(record, label)]
    sampled_metrics = _bootstrap_metric_values_from_counts(
        [label for _, label in subset],
        [prediction for prediction, _ in subset],
        iterations,
        seed,
    )
    return _summarize_metric(sampled_metrics["false_merge_rate"], confidence_level)


def _build_iad_bootstrap_row(
    labeled_predictions: list[tuple[dict, int, int]],
    system_name: str,
    metric_scope: str,
    stratum_name: str,
    stratum_value: str,
    prediction_field: str | None,
    score_field: str | None,
    threshold: float | None,
    iterations: int,
    seed: int,
    confidence_level: float,
    split_field: str | None,
    eval_splits: list[str],
) -> dict:
    """构造单个 IAD bootstrap 分层结果行。

    参数:
        labeled_predictions: 当前分层的记录、预测和标签三元组。
        system_name: 系统名称。
        metric_scope: 指标范围。
        stratum_name: 分层字段名。
        stratum_value: 分层字段值。
        prediction_field: 直接预测字段。
        score_field: 分数字段。
        threshold: 分数阈值。
        iterations: bootstrap 抽样次数。
        seed: 随机种子。
        confidence_level: 置信水平。
        split_field: split 字段名。
        eval_splits: 纳入评估的 split 名称列表。

    返回:
        IAD bootstrap CSV 行。
    """
    labels = [label for _, _, label in labeled_predictions]
    predictions = [prediction for _, prediction, _ in labeled_predictions]
    true_positive, false_positive, true_negative, false_negative = _confusion_counts(labels, predictions)
    hard_negative_count = sum(1 for record, _, label in labeled_predictions if _is_iad_hard_negative(record, label))
    same_agenda_negative_count = sum(1 for record, _, label in labeled_predictions if _is_same_agenda_negative(record, label))
    sampled_metrics = _bootstrap_metric_values_from_counts(labels, predictions, iterations, seed)
    row: dict[str, float | int | str] = {
        "system": system_name,
        "metric_scope": metric_scope,
        "stratum_name": stratum_name,
        "stratum_value": stratum_value,
        "prediction_field": prediction_field or "",
        "score_field": score_field or "",
        "threshold": "" if threshold is None else threshold,
        "pair_count": len(labeled_predictions),
        "positive_label_count": sum(labels),
        "negative_label_count": len(labels) - sum(labels),
        "predicted_positive_count": sum(predictions),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "true_negative": true_negative,
        "false_negative": false_negative,
        "hard_negative_pair_count": hard_negative_count,
        "same_agenda_negative_count": same_agenda_negative_count,
        "bootstrap_iterations": iterations,
        "confidence_level": confidence_level,
        "split_field": split_field or "",
        "eval_splits": ",".join(eval_splits),
    }
    for field in METRIC_FIELDS:
        summary = _summarize_metric(sampled_metrics[field], confidence_level)
        row[f"{field}_mean"] = summary["mean"]
        row[f"{field}_ci_low"] = summary["ci_low"]
        row[f"{field}_ci_high"] = summary["ci_high"]
    hard_negative_summary = _summarize_rate_alias(labeled_predictions, iterations, seed + 1009, confidence_level, _is_iad_hard_negative)
    same_agenda_summary = _summarize_rate_alias(labeled_predictions, iterations, seed + 2017, confidence_level, _is_same_agenda_negative)
    row["hard_negative_false_merge_rate_mean"] = hard_negative_summary["mean"]
    row["hard_negative_false_merge_rate_ci_low"] = hard_negative_summary["ci_low"]
    row["hard_negative_false_merge_rate_ci_high"] = hard_negative_summary["ci_high"]
    row["same_agenda_false_merge_rate_mean"] = same_agenda_summary["mean"]
    row["same_agenda_false_merge_rate_ci_low"] = same_agenda_summary["ci_low"]
    row["same_agenda_false_merge_rate_ci_high"] = same_agenda_summary["ci_high"]
    return row


def run_bootstrap_confidence(
    relations: list[dict],
    iterations: int = 1000,
    seed: int = 42,
    confidence_level: float = 0.95,
) -> list[dict]:
    """对 baseline 与 RSL-Sieve 指标运行 bootstrap 置信区间评估。

    参数:
        relations: pair_relations 记录列表。
        iterations: bootstrap 抽样次数。
        seed: 随机种子。
        confidence_level: 置信水平。

    返回:
        每个预测系统的置信区间记录。
    """
    if iterations < 1:
        raise ValueError("iterations 必须大于等于 1")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level 必须在 0 到 1 之间")
    labeled_relations = _build_labeled_relations(relations)
    if not labeled_relations:
        LOGGER.warning("bootstrap 未找到弱标签关系，输出空指标")
    rows: list[dict] = []
    labels = [label for _, label in labeled_relations]
    for system_index, (system_name, description, predicate) in enumerate(get_prediction_systems()):
        predictions = [1 if predicate(relation) else 0 for relation, _ in labeled_relations]
        sampled_metrics = _bootstrap_metric_values_from_counts(labels, predictions, iterations, seed + system_index)
        row: dict[str, float | int | str] = {
            "system": system_name,
            "description": description,
            "weak_label_count": len(labeled_relations),
            "bootstrap_iterations": iterations,
            "confidence_level": confidence_level,
        }
        for field in METRIC_FIELDS:
            summary = _summarize_metric(sampled_metrics[field], confidence_level)
            row[f"{field}_mean"] = summary["mean"]
            row[f"{field}_ci_low"] = summary["ci_low"]
            row[f"{field}_ci_high"] = summary["ci_high"]
        rows.append(row)
    return rows


def _parse_eval_splits(eval_splits: str | list[str] | None) -> list[str]:
    """解析 split 过滤配置。

    参数:
        eval_splits: 逗号分隔字符串或 split 列表。

    返回:
        去重且保持顺序的 split 名称列表。
    """
    if eval_splits is None:
        return []
    if isinstance(eval_splits, str):
        candidates = [part.strip() for part in eval_splits.split(",")]
    else:
        candidates = [str(part).strip() for part in eval_splits]
    parsed: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            parsed.append(candidate)
            seen.add(candidate)
    return parsed


def _filter_records_by_split(records: list[dict], split_field: str | None, eval_splits: list[str]) -> list[dict]:
    """按 split 字段过滤评估记录。

    参数:
        records: 原始评估记录。
        split_field: split 字段名。
        eval_splits: 纳入评估的 split 名称列表。

    返回:
        过滤后的评估记录；未提供过滤配置时返回原记录。
    """
    if not split_field or not eval_splits:
        return records
    allowed_splits = set(eval_splits)
    filtered_records = [record for record in records if str(record.get(split_field, "")).strip() in allowed_splits]
    LOGGER.info(
        "IAD bootstrap split 过滤完成: split_field=%s eval_splits=%s before=%s after=%s",
        split_field,
        ",".join(eval_splits),
        len(records),
        len(filtered_records),
    )
    return filtered_records


def run_iad_evidence_bootstrap(
    records: list[dict],
    system_name: str,
    prediction_field: str | None = None,
    score_field: str | None = None,
    threshold: float | None = None,
    iterations: int = 1000,
    seed: int = 42,
    confidence_level: float = 0.95,
    split_field: str | None = None,
    eval_splits: str | list[str] | None = None,
) -> list[dict]:
    """运行 IAD-Risk / baseline 分层 bootstrap 置信区间评估。

    参数:
        records: IAD prediction、single-space prediction 或 baseline scored relation。
        system_name: 系统名称。
        prediction_field: 直接读取的 0/1 预测字段。
        score_field: 可选分数字段。
        threshold: score_field 转 0/1 预测的阈值。
        iterations: bootstrap 抽样次数。
        seed: 随机种子。
        confidence_level: 置信水平。
        split_field: 可选 split 字段名。
        eval_splits: 可选评估 split；提供后仅在这些 split 上计算置信区间。

    返回:
        分层 bootstrap 结果记录。
    """
    if iterations < 1:
        raise ValueError("iterations 必须大于等于 1")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level 必须在 0 到 1 之间")
    if bool(prediction_field) == bool(score_field):
        raise ValueError("prediction_field 与 score_field 必须且只能提供一个")
    if score_field and threshold is None:
        raise ValueError("使用 score_field 时必须提供 threshold")
    parsed_eval_splits = _parse_eval_splits(eval_splits)
    filtered_records = _filter_records_by_split(records, split_field, parsed_eval_splits)
    labeled_predictions = _build_iad_labeled_predictions(filtered_records, prediction_field, score_field, threshold)
    if not labeled_predictions:
        LOGGER.warning("IAD bootstrap 未找到可评估记录，输出空指标")
    strata: list[tuple[str, str, str, list[tuple[dict, int, int]]]] = [
        ("all_pairs", "all", "all", labeled_predictions),
        (
            "hard_negative_pairs",
            "hard_negative_level",
            "any",
            [(record, prediction, label) for record, prediction, label in labeled_predictions if _is_iad_hard_negative(record, label)],
        ),
        (
            "same_agenda_negative_pairs",
            "expected_agenda_label",
            "1",
            [(record, prediction, label) for record, prediction, label in labeled_predictions if _is_same_agenda_negative(record, label)],
        ),
    ]
    label_strengths = sorted({str(record.get("label_strength", "") or "") for record, _, _ in labeled_predictions if str(record.get("label_strength", "") or "")})
    for label_strength in label_strengths:
        strata.append(
            (
                f"label_strength:{label_strength}",
                "label_strength",
                label_strength,
                [(record, prediction, label) for record, prediction, label in labeled_predictions if str(record.get("label_strength", "") or "") == label_strength],
            )
        )
    rows = []
    for stratum_index, (metric_scope, stratum_name, stratum_value, stratum_records) in enumerate(strata):
        rows.append(
            _build_iad_bootstrap_row(
                stratum_records,
                system_name,
                metric_scope,
                stratum_name,
                stratum_value,
                prediction_field,
                score_field,
                threshold,
                iterations,
                seed + stratum_index,
                confidence_level,
                split_field,
                parsed_eval_splits,
            )
        )
    LOGGER.info("IAD bootstrap 完成: system=%s rows=%s records=%s", system_name, len(rows), len(labeled_predictions))
    return rows


def write_bootstrap_csv(rows: list[dict], output_path: str | Path) -> None:
    """写入 bootstrap 置信区间 CSV。

    参数:
        rows: bootstrap 置信区间记录。
        output_path: 输出 CSV 路径。

    返回:
        无。
    """
    resolved_output_path = Path(output_path)
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=BOOTSTRAP_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_iad_bootstrap_csv(rows: list[dict], output_path: str | Path) -> None:
    """写入 IAD 分层 bootstrap 置信区间 CSV。

    参数:
        rows: IAD bootstrap 结果记录。
        output_path: 输出 CSV 路径。

    返回:
        无。
    """
    resolved_output_path = Path(output_path)
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=IAD_BOOTSTRAP_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
