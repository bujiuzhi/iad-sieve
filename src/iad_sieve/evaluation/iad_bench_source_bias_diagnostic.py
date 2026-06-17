"""IAD-Bench 来源字段偏置诊断模块。"""

from __future__ import annotations

import csv
import logging
from collections import Counter, defaultdict
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
DIAGNOSTIC_FIELDS = [
    "diagnostic_id",
    "audit_status",
    "reviewer_risk_level",
    "predictor_field",
    "target_field",
    "train_split",
    "eval_splits",
    "train_pair_count",
    "eval_pair_count",
    "correct_count",
    "eval_accuracy",
    "macro_f1",
    "unseen_group_count",
    "max_shortcut_accuracy",
    "reviewer_interpretation",
    "next_optimization",
    "paper_claim_boundary",
]
PREDICTION_FIELDS = [
    "diagnostic_id",
    "pair_id",
    "split",
    "predictor_field",
    "predictor_value",
    "target_field",
    "actual_value",
    "predicted_value",
    "is_correct",
    "prediction_source",
]


def _clean(value: object) -> str:
    """清理文本值。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _split_name(row: dict) -> str:
    """读取 split 名称。

    参数:
        row: pair 记录。

    返回:
        小写 split 名称。
    """
    return _clean(row.get("split")).lower() or "unknown"


def _pair_id(row: dict, index: int) -> str:
    """读取 pair ID。

    参数:
        row: pair 记录。
        index: 当前序号。

    返回:
        pair ID，缺失时返回稳定兜底 ID。
    """
    return _clean(row.get("pair_id")) or f"pair_{index}"


def _field_value(row: dict, field_name: str) -> str:
    """读取诊断字段值。

    参数:
        row: pair 记录。
        field_name: 字段名称。

    返回:
        规范化后的字段值。
    """
    if field_name == "expected_label":
        return str(int(row.get(field_name, 0) or 0))
    return _clean(row.get(field_name)).lower() or "unknown"


def _majority_label(values: list[str]) -> str:
    """返回多数类标签。

    参数:
        values: 标签值列表。

    返回:
        多数类标签；并列时按字典序稳定选择。
    """
    counts = Counter(values)
    if not counts:
        return "unknown"
    max_count = max(counts.values())
    return sorted(label for label, count in counts.items() if count == max_count)[0]


def _fit_majority_map(train_rows: list[dict], predictor_field: str, target_field: str) -> tuple[dict[str, str], str]:
    """基于训练集拟合 predictor value 到目标多数类的映射。

    参数:
        train_rows: 训练 split pair。
        predictor_field: 预测字段。
        target_field: 目标字段。

    返回:
        分组多数类映射和全局多数类。
    """
    targets_by_group: dict[str, list[str]] = defaultdict(list)
    all_targets: list[str] = []
    for row in train_rows:
        target_value = _field_value(row, target_field)
        targets_by_group[_field_value(row, predictor_field)].append(target_value)
        all_targets.append(target_value)
    group_map = {group: _majority_label(values) for group, values in targets_by_group.items()}
    return group_map, _majority_label(all_targets)


def _macro_f1(actual_values: list[str], predicted_values: list[str]) -> float:
    """计算多类 macro F1。

    参数:
        actual_values: 真实标签。
        predicted_values: 预测标签。

    返回:
        macro F1，保留 6 位小数。
    """
    labels = sorted(set(actual_values) | set(predicted_values))
    if not labels:
        return 0.0
    f1_values = []
    for label in labels:
        true_positive = sum(1 for actual, predicted in zip(actual_values, predicted_values, strict=True) if actual == label and predicted == label)
        false_positive = sum(1 for actual, predicted in zip(actual_values, predicted_values, strict=True) if actual != label and predicted == label)
        false_negative = sum(1 for actual, predicted in zip(actual_values, predicted_values, strict=True) if actual == label and predicted != label)
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1_values.append((2 * precision * recall / (precision + recall)) if precision + recall else 0.0)
    return round(sum(f1_values) / len(f1_values), 6)


def _run_diagnostic(
    pairs: list[dict],
    train_rows: list[dict],
    eval_rows: list[dict],
    predictor_field: str,
    target_field: str,
    train_split: str,
    eval_splits: list[str],
    max_shortcut_accuracy: float,
) -> tuple[dict, list[dict]]:
    """运行单个来源偏置诊断。

    参数:
        pairs: 全部 pair 记录。
        train_rows: 训练 split pair。
        eval_rows: 评估 split pair。
        predictor_field: 预测字段。
        target_field: 目标字段。
        train_split: 训练 split 名称。
        eval_splits: 评估 split 名称。
        max_shortcut_accuracy: shortcut 风险准确率阈值。

    返回:
        诊断记录和预测记录。
    """
    group_map, global_majority = _fit_majority_map(train_rows, predictor_field, target_field)
    diagnostic_id = f"{predictor_field}_to_{target_field}"
    actual_values: list[str] = []
    predicted_values: list[str] = []
    prediction_rows: list[dict] = []
    unseen_group_count = 0
    for index, row in enumerate(eval_rows):
        predictor_value = _field_value(row, predictor_field)
        actual_value = _field_value(row, target_field)
        if predictor_value in group_map:
            predicted_value = group_map[predictor_value]
            prediction_source = "group_majority"
        else:
            predicted_value = global_majority
            prediction_source = "global_majority"
            unseen_group_count += 1
        actual_values.append(actual_value)
        predicted_values.append(predicted_value)
        prediction_rows.append(
            {
                "diagnostic_id": diagnostic_id,
                "pair_id": _pair_id(row, index),
                "split": _split_name(row),
                "predictor_field": predictor_field,
                "predictor_value": predictor_value,
                "target_field": target_field,
                "actual_value": actual_value,
                "predicted_value": predicted_value,
                "is_correct": predicted_value == actual_value,
                "prediction_source": prediction_source,
            }
        )
    correct_count = sum(1 for actual, predicted in zip(actual_values, predicted_values, strict=True) if actual == predicted)
    eval_count = len(eval_rows)
    accuracy = round(correct_count / eval_count, 6) if eval_count else 0.0
    macro_f1 = _macro_f1(actual_values, predicted_values)
    status = "high_risk" if eval_count and accuracy >= max_shortcut_accuracy else "defensible"
    diagnostic_row = {
        "diagnostic_id": diagnostic_id,
        "audit_status": status,
        "reviewer_risk_level": "high" if status == "high_risk" else "low",
        "predictor_field": predictor_field,
        "target_field": target_field,
        "train_split": train_split,
        "eval_splits": ",".join(eval_splits),
        "train_pair_count": len(train_rows),
        "eval_pair_count": eval_count,
        "correct_count": correct_count,
        "eval_accuracy": accuracy,
        "macro_f1": macro_f1,
        "unseen_group_count": unseen_group_count,
        "max_shortcut_accuracy": max_shortcut_accuracy,
        "reviewer_interpretation": (
            f"仅使用 {predictor_field} 即可高准确预测 {target_field}，存在来源捷径风险。"
            if status == "high_risk"
            else f"仅使用 {predictor_field} 不能高准确预测 {target_field}。"
        ),
        "next_optimization": "补充多来源同类 relation，执行 source-held-out split，并在模型特征中禁止使用 provenance 字段。",
        "paper_claim_boundary": "该诊断为 high_risk 时，不得声称已排除数据来源混淆。",
        "pair_count": len(pairs),
    }
    return diagnostic_row, prediction_rows


def build_iad_bench_source_bias_diagnostic_rows(
    pairs: list[dict],
    train_split: str = "train",
    eval_splits: list[str] | tuple[str, ...] | None = None,
    max_shortcut_accuracy: float = 0.8,
) -> tuple[list[dict], list[dict]]:
    """构建 IAD-Bench 来源字段偏置诊断。

    参数:
        pairs: IAD-Bench pair 记录。
        train_split: 拟合多数类映射使用的 split。
        eval_splits: 评估 split 列表；默认 dev/test。
        max_shortcut_accuracy: shortcut 风险准确率阈值。

    返回:
        诊断记录列表和预测记录列表。
    """
    try:
        train_split_name = _clean(train_split).lower() or "train"
        target_eval_splits = [(_clean(split).lower() or split) for split in (eval_splits or ["dev", "test"])]
        train_rows = [row for row in pairs if _split_name(row) == train_split_name]
        eval_rows = [row for row in pairs if _split_name(row) in set(target_eval_splits)]
        diagnostic_specs = [
            ("label_source", "relation_label"),
            ("label_strength", "relation_label"),
            ("label_source", "expected_label"),
        ]
        diagnostic_rows: list[dict] = []
        prediction_rows: list[dict] = []
        for predictor_field, target_field in diagnostic_specs:
            diagnostic_row, rows = _run_diagnostic(
                pairs=pairs,
                train_rows=train_rows,
                eval_rows=eval_rows,
                predictor_field=predictor_field,
                target_field=target_field,
                train_split=train_split_name,
                eval_splits=target_eval_splits,
                max_shortcut_accuracy=max_shortcut_accuracy,
            )
            diagnostic_rows.append(diagnostic_row)
            prediction_rows.extend(rows)
        LOGGER.info("IAD-Bench 来源偏置诊断完成: diagnostics=%s predictions=%s", len(diagnostic_rows), len(prediction_rows))
        return diagnostic_rows, prediction_rows
    except Exception:
        LOGGER.exception("构建 IAD-Bench 来源偏置诊断失败")
        raise


def build_iad_bench_source_bias_diagnostic_rows_from_paths(
    pairs_path: str | Path,
    train_split: str = "train",
    eval_splits: list[str] | tuple[str, ...] | None = None,
    max_shortcut_accuracy: float = 0.8,
) -> tuple[list[dict], list[dict]]:
    """从 pair 文件构建 IAD-Bench 来源字段偏置诊断。

    参数:
        pairs_path: IAD-Bench pair JSONL。
        train_split: 拟合多数类映射使用的 split。
        eval_splits: 评估 split 列表。
        max_shortcut_accuracy: shortcut 风险准确率阈值。

    返回:
        诊断记录列表和预测记录列表。
    """
    try:
        return build_iad_bench_source_bias_diagnostic_rows(
            pairs=read_records(pairs_path),
            train_split=train_split,
            eval_splits=eval_splits,
            max_shortcut_accuracy=max_shortcut_accuracy,
        )
    except Exception:
        LOGGER.exception("读取 IAD-Bench 来源偏置诊断输入失败: %s", pairs_path)
        raise


def _write_csv(path: Path, rows: list[dict], preferred_fields: list[str]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 记录列表。
        preferred_fields: 优先字段顺序。

    返回:
        无。
    """
    fields = list(preferred_fields) if not rows else [field for field in preferred_fields if any(field in row for row in rows)]
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    except OSError:
        LOGGER.exception("写出 IAD-Bench 来源偏置诊断 CSV 失败: %s", path)
        raise


def _summary(diagnostic_rows: list[dict], prediction_rows: list[dict]) -> dict:
    """构建 IAD-Bench 来源偏置诊断汇总。

    参数:
        diagnostic_rows: 诊断记录。
        prediction_rows: 预测记录。

    返回:
        汇总记录。
    """
    return {
        "diagnostic_count": len(diagnostic_rows),
        "prediction_count": len(prediction_rows),
        "high_risk_count": sum(1 for row in diagnostic_rows if row.get("audit_status") == "high_risk"),
        "defensible_count": sum(1 for row in diagnostic_rows if row.get("audit_status") == "defensible"),
        "max_eval_accuracy": max((float(row.get("eval_accuracy", 0.0) or 0.0) for row in diagnostic_rows), default=0.0),
        "overall_source_bias_status": "high_risk" if any(row.get("audit_status") == "high_risk" for row in diagnostic_rows) else "defensible",
    }


def _write_markdown(path: Path, diagnostic_rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        diagnostic_rows: 诊断记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = ["diagnostic_id", "audit_status", "eval_accuracy", "macro_f1", "reviewer_interpretation", "next_optimization"]
    lines = [
        "# IAD-Bench Source Bias Diagnostic",
        "",
        "## 使用边界",
        "",
        "该报告用 label_source 和 label_strength 的多数类预测器诊断 provenance shortcut。若该弱预测器已能高准确预测任务标签，论文必须限制因果和泛化主张。",
        "",
        "## 汇总",
        "",
        f"- diagnostic_count: {summary['diagnostic_count']}",
        f"- prediction_count: {summary['prediction_count']}",
        f"- high_risk_count: {summary['high_risk_count']}",
        f"- defensible_count: {summary['defensible_count']}",
        f"- max_eval_accuracy: {summary['max_eval_accuracy']}",
        f"- overall_source_bias_status: {summary['overall_source_bias_status']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in diagnostic_rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 IAD-Bench 来源偏置诊断 Markdown 失败: %s", path)
        raise


def write_iad_bench_source_bias_diagnostic_outputs(diagnostic_rows: list[dict], prediction_rows: list[dict], output_dir: str | Path) -> None:
    """写出 IAD-Bench 来源字段偏置诊断产物。

    参数:
        diagnostic_rows: 诊断记录。
        prediction_rows: 预测记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _summary(diagnostic_rows, prediction_rows)
    try:
        write_records(diagnostic_rows, directory / "iad_bench_source_bias_diagnostic.jsonl")
        write_records(prediction_rows, directory / "iad_bench_source_bias_predictions.jsonl")
        write_records([summary], directory / "iad_bench_source_bias_diagnostic_summary.jsonl")
        _write_csv(directory / "iad_bench_source_bias_diagnostic.csv", diagnostic_rows, DIAGNOSTIC_FIELDS)
        _write_csv(directory / "iad_bench_source_bias_predictions.csv", prediction_rows, PREDICTION_FIELDS)
        _write_markdown(directory / "iad_bench_source_bias_diagnostic.md", diagnostic_rows, summary)
    except Exception:
        LOGGER.exception("写出 IAD-Bench 来源偏置诊断失败: %s", output_dir)
        raise
