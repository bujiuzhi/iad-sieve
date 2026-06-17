"""主轨道实际优势判定器模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "evaluator_item_id",
    "evaluation_status",
    "comparison_status",
    "primary_track",
    "main_system",
    "baseline_system",
    "missing_systems",
    "missing_metric_fields",
    "same_work_f1_delta",
    "false_merge_rate_reduction",
    "hard_negative_false_merge_rate_reduction",
    "f1_ci_delta_low",
    "false_merge_reduction_ci_low",
    "hard_negative_reduction_ci_low",
    "bootstrap_ci_passed",
    "threshold_passed",
    "claim_allowed_by_evaluator",
    "passed_comparison_count",
    "blocked_comparison_count",
    "failed_comparison_count",
    "paper_claim_boundary",
    "next_action",
]


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    if value is None:
        return ""
    return str(value).strip()


def _bool_value(value: object) -> bool:
    """解析布尔值。

    参数:
        value: 原始值。

    返回:
        布尔值。
    """
    if isinstance(value, bool):
        return value
    return _clean(value).lower() in {"true", "1", "yes", "ready"}


def _float_or_none(value: object) -> float | None:
    """解析浮点数。

    参数:
        value: 原始值。

    返回:
        浮点数；无法解析时返回 None。
    """
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        LOGGER.warning("优势判定数值字段无法解析: %s", value)
        return None


def _round(value: float | None) -> float | str:
    """统一数值显示精度。

    参数:
        value: 原始数值。

    返回:
        四舍五入后的浮点数；None 返回空字符串。
    """
    if value is None:
        return ""
    return round(value, 6)


def _first(rows: list[dict]) -> dict:
    """返回首条记录。

    参数:
        rows: 记录列表。

    返回:
        首条记录；为空时返回空字典。
    """
    return rows[0] if rows else {}


def _comparison_protocol_rows(protocol_rows: list[dict]) -> list[dict]:
    """筛选比较协议行。

    参数:
        protocol_rows: primary_track_superiority_protocol 记录。

    返回:
        包含 baseline_system 的比较协议行。
    """
    return [row for row in protocol_rows if _clean(row.get("baseline_system"))]


def _metric_index(metric_rows: list[dict]) -> dict[str, list[dict]]:
    """按 system 建立 metric summary 索引。

    参数:
        metric_rows: metric summary 记录。

    返回:
        system 到指标记录列表的映射。
    """
    index: dict[str, list[dict]] = {}
    for row in metric_rows:
        system = _clean(row.get("system"))
        if system:
            index.setdefault(system, []).append(row)
    return index


def _select_metric(metric_by_system: dict[str, list[dict]], system: str, bootstrap_row: dict) -> dict:
    """选择与 bootstrap 阈值和评估 split 一致的 metric summary 行。

    参数:
        metric_by_system: system 到 metric summary 列表的映射。
        system: 系统名称。
        bootstrap_row: bootstrap 记录。

    返回:
        优先匹配 threshold 与 test split 的 metric summary 行；无记录时返回空字典。
    """
    rows = metric_by_system.get(system, [])
    if not rows:
        return {}
    bootstrap_threshold = _float_or_none(bootstrap_row.get("threshold"))
    if bootstrap_threshold is not None:
        threshold_rows = [
            row
            for row in rows
            if (row_threshold := _float_or_none(row.get("threshold"))) is not None
            and abs(row_threshold - bootstrap_threshold) <= 1e-9
        ]
        if threshold_rows:
            return _prefer_test_split_metric(threshold_rows)
    return _prefer_test_split_metric(rows)


def _prefer_test_split_metric(rows: list[dict]) -> dict:
    """在同一系统的 metric summary 中优先返回 test split 行。

    参数:
        rows: 同一系统、同一阈值范围内的 metric summary 记录。

    返回:
        test split 记录；若不存在 test split，则返回第一条记录。
    """
    for row in rows:
        if _clean(row.get("eval_split")) == "test":
            return row
    return rows[0] if rows else {}


def _bootstrap_index(bootstrap_rows: list[dict]) -> dict[str, dict]:
    """按 system 建立 bootstrap all_pairs 索引。

    参数:
        bootstrap_rows: bootstrap confidence 记录。

    返回:
        system 到 all_pairs bootstrap 记录的映射。
    """
    index: dict[str, dict] = {}
    for row in bootstrap_rows:
        system = _clean(row.get("system"))
        scope = _clean(row.get("metric_scope")) or "all_pairs"
        if system and scope == "all_pairs" and system not in index:
            index[system] = row
    return index


def _metric_value(metric_row: dict, bootstrap_row: dict, metric_name: str) -> float | None:
    """读取 metric summary 或 bootstrap mean 指标。

    参数:
        metric_row: metric summary 记录。
        bootstrap_row: bootstrap 记录。
        metric_name: 指标名。

    返回:
        指标值；缺失时返回 None。
    """
    value = _float_or_none(metric_row.get(metric_name))
    if value is not None:
        return value
    return _float_or_none(bootstrap_row.get(f"{metric_name}_mean"))


def _ci_value(bootstrap_row: dict, field_name: str) -> float | None:
    """读取 bootstrap 置信区间字段。

    参数:
        bootstrap_row: bootstrap 记录。
        field_name: 置信区间字段名。

    返回:
        字段值；缺失时返回 None。
    """
    return _float_or_none(bootstrap_row.get(field_name))


def _thresholds(protocol_summary: dict) -> tuple[float, float, float, bool]:
    """读取协议阈值。

    参数:
        protocol_summary: 协议摘要记录。

    返回:
        F1 差值阈值、不良合并率降低阈值、hard-negative 降低阈值、是否需要 CI。
    """
    minimum_f1_delta = _float_or_none(protocol_summary.get("minimum_f1_delta"))
    minimum_false_merge_reduction = _float_or_none(protocol_summary.get("minimum_false_merge_reduction"))
    minimum_hard_negative_reduction = _float_or_none(protocol_summary.get("minimum_hard_negative_reduction"))
    return (
        minimum_f1_delta if minimum_f1_delta is not None else 0.0,
        minimum_false_merge_reduction if minimum_false_merge_reduction is not None else 0.02,
        minimum_hard_negative_reduction if minimum_hard_negative_reduction is not None else 0.05,
        _bool_value(protocol_summary.get("requires_bootstrap_ci")),
    )


def _comparison_row(
    protocol_row: dict,
    protocol_summary: dict,
    metric_by_system: dict[str, list[dict]],
    bootstrap_by_system: dict[str, dict],
) -> dict:
    """构建单个比较判定行。

    参数:
        protocol_row: 比较协议行。
        protocol_summary: 协议摘要行。
        metric_by_system: system 到 metric summary 的映射。
        bootstrap_by_system: system 到 bootstrap 的映射。

    返回:
        比较判定行。
    """
    main_system = _clean(protocol_row.get("main_system")) or _clean(protocol_summary.get("main_system"))
    baseline_system = _clean(protocol_row.get("baseline_system"))
    main_bootstrap = bootstrap_by_system.get(main_system, {})
    baseline_bootstrap = bootstrap_by_system.get(baseline_system, {})
    main_metric = _select_metric(metric_by_system, main_system, main_bootstrap)
    baseline_metric = _select_metric(metric_by_system, baseline_system, baseline_bootstrap)
    missing_systems = [system for system, row in ((main_system, main_metric), (baseline_system, baseline_metric)) if system and not row]
    minimum_f1_delta, minimum_false_merge_reduction, minimum_hard_negative_reduction, requires_bootstrap_ci = _thresholds(protocol_summary)

    if missing_systems:
        return {
            "evaluator_item_id": _clean(protocol_row.get("protocol_item_id")),
            "evaluation_status": "",
            "comparison_status": "blocked_missing_metric",
            "primary_track": _clean(protocol_summary.get("primary_track")),
            "main_system": main_system,
            "baseline_system": baseline_system,
            "missing_systems": missing_systems,
            "missing_metric_fields": [],
            "bootstrap_ci_passed": False,
            "threshold_passed": False,
            "claim_allowed_by_evaluator": False,
            "paper_claim_boundary": "主轨道指标缺失时，不得写主轨道模型优势。",
            "next_action": "运行主轨道远程强模型任务，并回传 metric summary 与 bootstrap confidence。",
        }

    main_f1 = _metric_value(main_metric, main_bootstrap, "f1")
    baseline_f1 = _metric_value(baseline_metric, baseline_bootstrap, "f1")
    main_false_merge = _metric_value(main_metric, main_bootstrap, "false_merge_rate")
    baseline_false_merge = _metric_value(baseline_metric, baseline_bootstrap, "false_merge_rate")
    main_hard_negative = _metric_value(main_metric, main_bootstrap, "hard_negative_false_merge_rate")
    baseline_hard_negative = _metric_value(baseline_metric, baseline_bootstrap, "hard_negative_false_merge_rate")
    main_f1_ci_low = _ci_value(main_bootstrap, "f1_ci_low")
    baseline_f1_ci_high = _ci_value(baseline_bootstrap, "f1_ci_high")
    baseline_false_merge_ci_low = _ci_value(baseline_bootstrap, "false_merge_rate_ci_low")
    main_false_merge_ci_high = _ci_value(main_bootstrap, "false_merge_rate_ci_high")
    baseline_hard_negative_ci_low = _ci_value(baseline_bootstrap, "hard_negative_false_merge_rate_ci_low")
    main_hard_negative_ci_high = _ci_value(main_bootstrap, "hard_negative_false_merge_rate_ci_high")
    required_values = {
        "main_system.f1": main_f1,
        "baseline_system.f1": baseline_f1,
        "main_system.false_merge_rate": main_false_merge,
        "baseline_system.false_merge_rate": baseline_false_merge,
        "main_system.hard_negative_false_merge_rate": main_hard_negative,
        "baseline_system.hard_negative_false_merge_rate": baseline_hard_negative,
    }
    if requires_bootstrap_ci:
        required_values.update(
            {
                "main_system.f1_ci_low": main_f1_ci_low,
                "baseline_system.f1_ci_high": baseline_f1_ci_high,
                "baseline_system.false_merge_rate_ci_low": baseline_false_merge_ci_low,
                "main_system.false_merge_rate_ci_high": main_false_merge_ci_high,
                "baseline_system.hard_negative_false_merge_rate_ci_low": baseline_hard_negative_ci_low,
                "main_system.hard_negative_false_merge_rate_ci_high": main_hard_negative_ci_high,
            }
        )
    missing_metric_fields = [field for field, value in required_values.items() if value is None]
    if missing_metric_fields:
        return {
            "evaluator_item_id": _clean(protocol_row.get("protocol_item_id")),
            "evaluation_status": "",
            "comparison_status": "blocked_missing_metric_field",
            "primary_track": _clean(protocol_summary.get("primary_track")),
            "main_system": main_system,
            "baseline_system": baseline_system,
            "missing_systems": [],
            "missing_metric_fields": missing_metric_fields,
            "bootstrap_ci_passed": False,
            "threshold_passed": False,
            "claim_allowed_by_evaluator": False,
            "paper_claim_boundary": "主轨道关键指标字段缺失时，不得写主轨道模型优势。",
            "next_action": "补齐 metric summary 与 bootstrap confidence 中的缺失字段后重建判定器。",
        }

    same_work_f1_delta = main_f1 - baseline_f1
    false_merge_rate_reduction = baseline_false_merge - main_false_merge
    hard_negative_reduction = baseline_hard_negative - main_hard_negative
    f1_ci_delta_low = main_f1_ci_low - baseline_f1_ci_high if requires_bootstrap_ci else 0.0
    false_merge_reduction_ci_low = baseline_false_merge_ci_low - main_false_merge_ci_high if requires_bootstrap_ci else 0.0
    hard_negative_reduction_ci_low = baseline_hard_negative_ci_low - main_hard_negative_ci_high if requires_bootstrap_ci else 0.0
    threshold_passed = (
        same_work_f1_delta >= minimum_f1_delta
        and false_merge_rate_reduction >= minimum_false_merge_reduction
        and hard_negative_reduction >= minimum_hard_negative_reduction
    )
    bootstrap_ci_passed = (not requires_bootstrap_ci) or (
        f1_ci_delta_low >= 0 and false_merge_reduction_ci_low >= 0 and hard_negative_reduction_ci_low >= 0
    )
    comparison_status = "passed" if threshold_passed and bootstrap_ci_passed else "failed_protocol_threshold"
    return {
        "evaluator_item_id": _clean(protocol_row.get("protocol_item_id")),
        "evaluation_status": "",
        "comparison_status": comparison_status,
        "primary_track": _clean(protocol_summary.get("primary_track")),
        "main_system": main_system,
        "baseline_system": baseline_system,
        "missing_systems": [],
        "missing_metric_fields": [],
        "same_work_f1_delta": _round(same_work_f1_delta),
        "false_merge_rate_reduction": _round(false_merge_rate_reduction),
        "hard_negative_false_merge_rate_reduction": _round(hard_negative_reduction),
        "f1_ci_delta_low": _round(f1_ci_delta_low),
        "false_merge_reduction_ci_low": _round(false_merge_reduction_ci_low),
        "hard_negative_reduction_ci_low": _round(hard_negative_reduction_ci_low),
        "bootstrap_ci_passed": bootstrap_ci_passed,
        "threshold_passed": threshold_passed,
        "claim_allowed_by_evaluator": comparison_status == "passed",
        "paper_claim_boundary": "只有该比较 passed 时，才能把该 baseline 写入主轨道模型优势证据。",
        "next_action": "若未通过，报告失败指标、阈值和代表性错误样本，不能选择性隐藏。",
    }


def _summary_row(protocol_summary: dict, comparison_rows: list[dict]) -> dict:
    """构建优势判定摘要行。

    参数:
        protocol_summary: 协议摘要行。
        comparison_rows: 比较判定行。

    返回:
        摘要行。
    """
    passed = [row for row in comparison_rows if row.get("comparison_status") == "passed"]
    blocked = [row for row in comparison_rows if str(row.get("comparison_status", "")).startswith("blocked")]
    failed = [row for row in comparison_rows if str(row.get("comparison_status", "")).startswith("failed")]
    if blocked:
        statuses = {row.get("comparison_status") for row in blocked}
        status = "blocked_missing_primary_metric_fields" if statuses == {"blocked_missing_metric_field"} else "blocked_missing_primary_metrics"
    elif failed:
        status = "failed_protocol_threshold"
    else:
        status = "passed"
    return {
        "evaluator_item_id": "evaluator_summary",
        "evaluation_status": status,
        "comparison_status": "",
        "primary_track": _clean(protocol_summary.get("primary_track")),
        "main_system": _clean(protocol_summary.get("main_system")),
        "baseline_system": "",
        "missing_systems": sorted({system for row in blocked for system in row.get("missing_systems", [])}),
        "missing_metric_fields": sorted({field for row in blocked for field in row.get("missing_metric_fields", [])}),
        "bootstrap_ci_passed": all(row.get("bootstrap_ci_passed") for row in comparison_rows) if comparison_rows else False,
        "threshold_passed": all(row.get("threshold_passed") for row in comparison_rows) if comparison_rows else False,
        "claim_allowed_by_evaluator": status == "passed",
        "passed_comparison_count": len(passed),
        "blocked_comparison_count": len(blocked),
        "failed_comparison_count": len(failed),
        "paper_claim_boundary": "判定器未 passed 前，不得写主轨道模型优势、SOTA 或二区/B类先进性。",
        "next_action": "补齐主轨道 metric summary 与 bootstrap confidence，然后重建本判定器。",
    }


def build_primary_track_superiority_evaluator_rows(
    protocol_rows: list[dict],
    metric_rows: list[dict],
    bootstrap_rows: list[dict],
) -> list[dict]:
    """构建主轨道实际优势判定记录。

    参数:
        protocol_rows: primary_track_superiority_protocol 记录。
        metric_rows: metric summary 记录。
        bootstrap_rows: bootstrap confidence 记录。

    返回:
        主轨道实际优势判定记录列表。
    """
    try:
        protocol_summary = _first(protocol_rows)
        metric_by_system = _metric_index(metric_rows)
        bootstrap_by_system = _bootstrap_index(bootstrap_rows)
        comparison_rows = [
            _comparison_row(row, protocol_summary, metric_by_system, bootstrap_by_system)
            for row in _comparison_protocol_rows(protocol_rows)
        ]
        rows = [_summary_row(protocol_summary, comparison_rows)] + comparison_rows
        LOGGER.info("主轨道实际优势判定完成: status=%s", rows[0]["evaluation_status"])
        return rows
    except Exception:
        LOGGER.exception("构建主轨道实际优势判定失败")
        raise


def _read_many_jsonl(paths: list[str | Path]) -> list[dict]:
    """读取多个 JSONL 文件，跳过缺失文件。

    参数:
        paths: JSONL 路径列表。

    返回:
        合并后的记录列表。
    """
    rows: list[dict] = []
    for path_value in paths:
        path = Path(path_value)
        if not path.exists():
            LOGGER.warning("主轨道实际优势判定输入缺失，跳过: %s", path)
            continue
        rows.extend(read_records(path))
    return rows


def _read_many_csv(paths: list[str | Path]) -> list[dict]:
    """读取多个 CSV 文件，跳过缺失文件。

    参数:
        paths: CSV 路径列表。

    返回:
        合并后的记录列表。
    """
    rows: list[dict] = []
    for path_value in paths:
        path = Path(path_value)
        if not path.exists():
            LOGGER.warning("主轨道实际优势判定 bootstrap 输入缺失，跳过: %s", path)
            continue
        with path.open("r", encoding="utf-8", newline="") as file:
            rows.extend(dict(row) for row in csv.DictReader(file))
    return rows


def build_primary_track_superiority_evaluator_rows_from_paths(
    primary_track_superiority_protocol_path: str | Path,
    metric_summary_paths: list[str | Path],
    bootstrap_summary_paths: list[str | Path],
) -> list[dict]:
    """从文件构建主轨道实际优势判定记录。

    参数:
        primary_track_superiority_protocol_path: primary_track_superiority_protocol JSONL 路径。
        metric_summary_paths: metric summary JSONL 路径列表。
        bootstrap_summary_paths: bootstrap confidence CSV 路径列表。

    返回:
        主轨道实际优势判定记录列表。
    """
    try:
        protocol_rows = read_records(primary_track_superiority_protocol_path)
        metric_rows = _read_many_jsonl(metric_summary_paths)
        bootstrap_rows = _read_many_csv(bootstrap_summary_paths)
        return build_primary_track_superiority_evaluator_rows(protocol_rows, metric_rows, bootstrap_rows)
    except Exception:
        LOGGER.exception("读取主轨道实际优势判定输入失败")
        raise


def _serialize_csv_value(value: object) -> object:
    """序列化 CSV 单元格。

    参数:
        value: 原始值。

    返回:
        CSV 可写值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 报告。

    参数:
        path: 输出路径。
        rows: 判定记录。

    返回:
        无。
    """
    fields = list(PREFERRED_FIELDS)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_csv_value(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出主轨道实际优势判定 CSV 失败: %s", path)
        raise


def _summary(rows: list[dict]) -> dict:
    """构建主轨道实际优势判定摘要。

    参数:
        rows: 判定记录。

    返回:
        摘要记录。
    """
    row = rows[0] if rows else {}
    return {
        "primary_track": row.get("primary_track", ""),
        "evaluation_status": row.get("evaluation_status", "missing"),
        "claim_allowed_by_evaluator": row.get("claim_allowed_by_evaluator", False),
        "passed_comparison_count": row.get("passed_comparison_count", 0),
        "blocked_comparison_count": row.get("blocked_comparison_count", 0),
        "failed_comparison_count": row.get("failed_comparison_count", 0),
        "bootstrap_ci_passed": row.get("bootstrap_ci_passed", False),
        "threshold_passed": row.get("threshold_passed", False),
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 判定报告。

    参数:
        path: 输出路径。
        rows: 判定记录。
        summary: 摘要记录。

    返回:
        无。
    """
    lines = ["# Primary Track Superiority Evaluator", "", "## 摘要", ""]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## 比较项", ""])
    for row in rows[1:]:
        lines.append(f"### {row.get('evaluator_item_id')}")
        lines.append("")
        lines.append(f"- comparison_status: {row.get('comparison_status')}")
        lines.append(f"- baseline_system: {row.get('baseline_system')}")
        lines.append(f"- same_work_f1_delta: {row.get('same_work_f1_delta', '')}")
        lines.append(f"- false_merge_rate_reduction: {row.get('false_merge_rate_reduction', '')}")
        lines.append(f"- hard_negative_false_merge_rate_reduction: {row.get('hard_negative_false_merge_rate_reduction', '')}")
        lines.append(f"- bootstrap_ci_passed: {row.get('bootstrap_ci_passed')}")
        lines.append(f"- paper_claim_boundary: {row.get('paper_claim_boundary')}")
        lines.append("")
    try:
        path.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        LOGGER.exception("写出主轨道实际优势判定 Markdown 失败: %s", path)
        raise


def write_primary_track_superiority_evaluator_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出主轨道实际优势判定产物。

    参数:
        rows: 主轨道实际优势判定记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(rows, directory / "primary_track_superiority_evaluator.jsonl")
        _write_csv(directory / "primary_track_superiority_evaluator.csv", rows)
        summary = _summary(rows)
        write_records([summary], directory / "primary_track_superiority_evaluator_summary.jsonl")
        _write_markdown(directory / "primary_track_superiority_evaluator.md", rows, summary)
    except Exception:
        LOGGER.exception("写出主轨道实际优势判定失败: %s", output_dir)
        raise
