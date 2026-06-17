"""机制三角验证阈值敏感性审计模块。"""

from __future__ import annotations

import csv
import itertools
import logging
from pathlib import Path

from iad_sieve.evaluation.mechanism_triangulation_audit import (
    build_mechanism_triangulation_rows,
    build_mechanism_triangulation_summary,
)
from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
SENSITIVITY_FIELDS = [
    "setting_id",
    "threshold_setting",
    "system_count",
    "false_merge_pair_count",
    "cross_system_failure_pair_count",
    "single_system_failure_pair_count",
    "unresolved_pair_count",
    "triangulation_status",
    "q2b_mechanism_depth_ready",
    "reviewer_risk_level",
    "paper_claim_boundary",
]


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _float(value: object, default: float = 0.0) -> float:
    """解析浮点数。

    参数:
        value: 原始值。
        default: 解析失败时的默认值。

    返回:
        浮点数。
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        LOGGER.warning("机制三角敏感性数值字段无法解析: %s", value)
        return default


def _bool(value: object) -> bool:
    """解析布尔值。

    参数:
        value: 原始值。

    返回:
        表示真值时返回 True。
    """
    if isinstance(value, bool):
        return value
    return _clean(value).lower() in {"1", "true", "yes", "y", "ready"}


def _thresholds(value: object) -> list[float]:
    """解析阈值列表。

    参数:
        value: 原始阈值字段。

    返回:
        阈值列表。
    """
    if isinstance(value, list):
        return [_float(item) for item in value]
    text = _clean(value)
    if not text:
        return []
    normalized = text.replace(";", "|").replace("/", "|")
    return [_float(item) for item in normalized.split("|") if _clean(item)]


def _parse_baseline_spec(spec_value: str) -> dict:
    """解析 baseline spec 字符串。

    参数:
        spec_value: 形如 system=...,path=...,score_field=...,thresholds=... 的字符串。

    返回:
        baseline spec 字典。
    """
    parts: dict[str, str] = {}
    for item in spec_value.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[_clean(key)] = _clean(value)
    required = {"system", "path", "score_field"}
    missing = sorted(required - set(parts))
    if missing:
        raise ValueError(f"baseline spec 缺少字段: {', '.join(missing)}")
    thresholds = _thresholds(parts.get("thresholds") or parts.get("threshold"))
    if not thresholds:
        raise ValueError("baseline spec 缺少 thresholds 或 threshold")
    return {
        "system": parts["system"],
        "path": parts["path"],
        "score_field": parts["score_field"],
        "thresholds": thresholds,
    }


def _threshold_setting(specs: list[dict]) -> str:
    """序列化阈值组合。

    参数:
        specs: 当前阈值组合的 baseline specification。

    返回:
        阈值组合字符串。
    """
    return "; ".join(f"{spec['system']}={float(spec['threshold']):.6f}" for spec in specs)


def _risk_level(summary: dict) -> str:
    """判断审稿风险等级。

    参数:
        summary: 单个阈值组合三角验证 summary。

    返回:
        审稿风险等级。
    """
    if not _bool(summary.get("q2b_mechanism_depth_ready")):
        return "high"
    if int(summary.get("cross_system_failure_pair_count", 0)) < 2:
        return "medium"
    return "low"


def _claim_boundary(summary: dict) -> str:
    """生成论文主张边界。

    参数:
        summary: 单个阈值组合三角验证 summary。

    返回:
        论文主张边界。
    """
    if not _bool(summary.get("q2b_mechanism_depth_ready")):
        return "该阈值组合不能支撑跨 baseline 机制深度，只能作为负面或受限敏感性结果。"
    if int(summary.get("cross_system_failure_pair_count", 0)) < 2:
        return "该阈值组合只有少量共同失败案例，只能支撑机制存在性，不能写成稳定广泛现象。"
    return "该阈值组合可支撑跨 baseline 机制稳定性，但仍不能替代强 baseline 统计优势。"


def _threshold_grid(baseline_specs: list[dict]) -> list[list[dict]]:
    """生成 baseline 阈值组合。

    参数:
        baseline_specs: baseline specification 列表。

    返回:
        每个阈值组合对应的 baseline specification 列表。
    """
    choices: list[list[dict]] = []
    for spec in baseline_specs:
        thresholds = _thresholds(spec.get("thresholds") or spec.get("threshold"))
        choices.append(
            [
                {
                    "system": spec.get("system"),
                    "score_field": spec.get("score_field"),
                    "threshold": threshold,
                    "rows": spec.get("rows", []),
                }
                for threshold in thresholds
            ]
        )
    return [list(items) for items in itertools.product(*choices)]


def build_mechanism_triangulation_sensitivity_rows(
    baseline_specs: list[dict],
    iad_prediction_rows: list[dict],
) -> list[dict]:
    """构建机制三角验证阈值敏感性记录。

    参数:
        baseline_specs: baseline specification，每项包含 system、score_field、thresholds 和 rows。
        iad_prediction_rows: IAD-Risk 预测记录。

    返回:
        阈值组合审计记录列表。
    """
    try:
        rows: list[dict] = []
        for index, setting_specs in enumerate(_threshold_grid(baseline_specs), start=1):
            audit_rows, system_rows = build_mechanism_triangulation_rows(setting_specs, iad_prediction_rows)
            summary = build_mechanism_triangulation_summary(audit_rows, system_rows)
            rows.append(
                {
                    "setting_id": f"triangulation_threshold_{index:03d}",
                    "threshold_setting": _threshold_setting(setting_specs),
                    "system_count": summary["system_count"],
                    "false_merge_pair_count": summary["false_merge_pair_count"],
                    "cross_system_failure_pair_count": summary["cross_system_failure_pair_count"],
                    "single_system_failure_pair_count": summary["single_system_failure_pair_count"],
                    "unresolved_pair_count": summary["unresolved_pair_count"],
                    "triangulation_status": summary["triangulation_status"],
                    "q2b_mechanism_depth_ready": summary["q2b_mechanism_depth_ready"],
                    "reviewer_risk_level": _risk_level(summary),
                    "paper_claim_boundary": _claim_boundary(summary),
                }
            )
        LOGGER.info("机制三角验证阈值敏感性完成: settings=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建机制三角验证阈值敏感性失败")
        raise


def build_mechanism_triangulation_sensitivity_rows_from_paths(
    iad_predictions_path: str | Path,
    baseline_spec_values: list[str],
) -> list[dict]:
    """从路径构建机制三角验证阈值敏感性记录。

    参数:
        iad_predictions_path: IAD-Risk predictions JSONL 文件。
        baseline_spec_values: baseline spec 字符串列表。

    返回:
        阈值组合审计记录列表。
    """
    baseline_specs: list[dict] = []
    for spec_value in baseline_spec_values:
        spec = _parse_baseline_spec(spec_value)
        spec["rows"] = read_records(spec["path"])
        baseline_specs.append(spec)
    return build_mechanism_triangulation_sensitivity_rows(baseline_specs, read_records(iad_predictions_path))


def build_mechanism_triangulation_sensitivity_summary(rows: list[dict]) -> dict:
    """构建机制三角验证阈值敏感性汇总。

    参数:
        rows: 阈值组合审计记录。

    返回:
        汇总记录。
    """
    ready_rows = [row for row in rows if _bool(row.get("q2b_mechanism_depth_ready")) and int(row.get("unresolved_pair_count", 0)) == 0]
    cross_rows = [row for row in rows if int(row.get("cross_system_failure_pair_count", 0)) > 0]
    max_cross = max((int(row.get("cross_system_failure_pair_count", 0)) for row in rows), default=0)
    best_row = max(rows, key=lambda row: int(row.get("cross_system_failure_pair_count", 0)), default={})
    if len(ready_rows) >= 2 and max_cross >= 2:
        status = "threshold_stable_cross_system_evidence"
        ready = True
    elif ready_rows:
        status = "threshold_limited_cross_system_evidence"
        ready = False
    elif rows:
        status = "threshold_unstable_or_absent_cross_system_evidence"
        ready = False
    else:
        status = "missing_threshold_sensitivity"
        ready = False
    return {
        "setting_count": len(rows),
        "ready_setting_count": len(ready_rows),
        "cross_system_setting_count": len(cross_rows),
        "max_cross_system_failure_pair_count": max_cross,
        "best_threshold_setting": best_row.get("threshold_setting", ""),
        "threshold_stability_status": status,
        "q2b_threshold_stability_ready": ready,
        "paper_claim_boundary": (
            "阈值稳定性只能支撑机制解释稳健性；不能替代强模型、source-held-out、provenance-blind 或 Q2/B 完成证据。"
        ),
    }


def _serialize_cell(value: object) -> object:
    """序列化 CSV/Markdown 单元格。

    参数:
        value: 原始值。

    返回:
        可写入单元格的值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 阈值组合审计记录。

    返回:
        无。
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=SENSITIVITY_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_cell(row.get(field, "")) for field in SENSITIVITY_FIELDS})
    except OSError:
        LOGGER.exception("写出机制三角验证阈值敏感性 CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 阈值敏感性审计。

    参数:
        path: 输出路径。
        rows: 阈值组合审计记录。
        summary: 汇总记录。

    返回:
        无。
    """
    lines = [
        "# Mechanism Triangulation Sensitivity",
        "",
        "## 使用边界",
        "",
        "该报告用于审计跨 baseline 机制证据是否依赖单一阈值；它不能替代强模型或泛化实验。",
        "",
        "## 汇总",
        "",
        f"- setting_count: {summary['setting_count']}",
        f"- ready_setting_count: {summary['ready_setting_count']}",
        f"- cross_system_setting_count: {summary['cross_system_setting_count']}",
        f"- max_cross_system_failure_pair_count: {summary['max_cross_system_failure_pair_count']}",
        f"- best_threshold_setting: {summary['best_threshold_setting']}",
        f"- threshold_stability_status: {summary['threshold_stability_status']}",
        f"- q2b_threshold_stability_ready: {str(summary['q2b_threshold_stability_ready']).lower()}",
        "",
        "## 阈值组合",
        "",
        "| threshold_setting | cross_system_failure_pair_count | false_merge_pair_count | triangulation_status | reviewer_risk_level |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {threshold_setting} | {cross_system_failure_pair_count} | {false_merge_pair_count} | {triangulation_status} | {reviewer_risk_level} |".format(
                **row
            )
        )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出机制三角验证阈值敏感性 Markdown 失败: %s", path)
        raise


def write_mechanism_triangulation_sensitivity_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出机制三角验证阈值敏感性产物。

    参数:
        rows: 阈值组合审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = build_mechanism_triangulation_sensitivity_summary(rows)
    try:
        write_records(rows, directory / "mechanism_triangulation_sensitivity.jsonl")
        write_records([summary], directory / "mechanism_triangulation_sensitivity_summary.jsonl")
        _write_csv(directory / "mechanism_triangulation_sensitivity.csv", rows)
        _write_markdown(directory / "mechanism_triangulation_sensitivity.md", rows, summary)
    except Exception:
        LOGGER.exception("写出机制三角验证阈值敏感性失败: %s", output_dir)
        raise
