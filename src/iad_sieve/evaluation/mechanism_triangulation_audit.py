"""机制三角验证审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
AUDIT_FIELDS = [
    "pair_id",
    "triangulation_pattern",
    "failing_system_count",
    "failing_systems",
    "iad_prevented",
    "iad_merge_prediction",
    "hard_negative_level",
    "source_document_id",
    "target_document_id",
]
SYSTEM_FIELDS = [
    "system",
    "baseline_false_merge_count",
    "iad_prevented_false_merge_count",
    "iad_unresolved_false_merge_count",
    "common_failure_count",
    "unique_failure_count",
    "prevention_rate",
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
        LOGGER.warning("机制三角验证数值字段无法解析: %s", value)
        return default


def _is_positive(value: object) -> bool:
    """判断标签或预测是否为正。

    参数:
        value: 原始字段值。

    返回:
        表示正例时返回 True。
    """
    return value is True or _clean(value).lower() in {"1", "true", "yes"}


def _is_hard_negative(row: dict) -> bool:
    """判断 pair 是否为同议题非同一文献 hard negative。

    参数:
        row: baseline pair 记录。

    返回:
        hard negative 返回 True。
    """
    hard_negative_level = _clean(row.get("hard_negative_level")).lower()
    return not _is_positive(row.get("expected_label")) and (
        _is_positive(row.get("expected_agenda_label")) or hard_negative_level not in {"", "none"}
    )


def _iad_lookup(iad_prediction_rows: list[dict]) -> dict[str, dict]:
    """按 pair_id 建立 IAD-Risk 预测索引。

    参数:
        iad_prediction_rows: IAD-Risk 预测记录。

    返回:
        pair_id 到预测记录的映射。
    """
    return {_clean(row.get("pair_id")): row for row in iad_prediction_rows if _clean(row.get("pair_id"))}


def _list_cell(values: list[str]) -> str:
    """序列化列表单元格。

    参数:
        values: 字符串列表。

    返回:
        分号分隔字符串。
    """
    return "; ".join(value for value in values if value)


def _parse_baseline_spec(spec_value: str) -> dict:
    """解析 baseline spec 字符串。

    参数:
        spec_value: 形如 system=...,path=...,score_field=...,threshold=... 的字符串。

    返回:
        baseline spec 字典。
    """
    parts: dict[str, str] = {}
    for item in spec_value.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[_clean(key)] = _clean(value)
    required = {"system", "path", "score_field", "threshold"}
    missing = sorted(required - set(parts))
    if missing:
        raise ValueError(f"baseline spec 缺少字段: {', '.join(missing)}")
    return {
        "system": parts["system"],
        "path": parts["path"],
        "score_field": parts["score_field"],
        "threshold": _float(parts["threshold"], default=-1.0),
    }


def _collect_failures(baseline_specs: list[dict], iad_by_pair: dict[str, dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    """收集各 baseline 的 hard-negative 误合并。

    参数:
        baseline_specs: baseline specification 列表。
        iad_by_pair: IAD-Risk pair_id 索引。

    返回:
        pair_id 到失败记录的映射、system 到统计记录的映射。
    """
    pair_failures: dict[str, dict] = {}
    system_stats: dict[str, dict] = {}
    for spec in baseline_specs:
        system = _clean(spec.get("system"))
        score_field = _clean(spec.get("score_field"))
        threshold = _float(spec.get("threshold"))
        if not system or not score_field:
            continue
        system_stats.setdefault(
            system,
            {
                "system": system,
                "baseline_false_merge_count": 0,
                "iad_prevented_false_merge_count": 0,
                "iad_unresolved_false_merge_count": 0,
                "common_failure_count": 0,
                "unique_failure_count": 0,
            },
        )
        for baseline_row in spec.get("rows", []) or []:
            if not _is_hard_negative(baseline_row):
                continue
            if _float(baseline_row.get(score_field), default=-1.0) < threshold:
                continue
            pair_id = _clean(baseline_row.get("pair_id"))
            if not pair_id:
                continue
            iad_row = iad_by_pair.get(pair_id, {})
            iad_merge = int(_is_positive(iad_row.get("merge_prediction")))
            iad_prevented = iad_merge == 0
            system_stats[system]["baseline_false_merge_count"] += 1
            if iad_prevented:
                system_stats[system]["iad_prevented_false_merge_count"] += 1
            else:
                system_stats[system]["iad_unresolved_false_merge_count"] += 1
            if pair_id not in pair_failures:
                pair_failures[pair_id] = {
                    "pair_id": pair_id,
                    "failing_systems": [],
                    "iad_merge_prediction": iad_merge,
                    "iad_prevented": iad_prevented,
                    "hard_negative_level": baseline_row.get("hard_negative_level", ""),
                    "source_document_id": baseline_row.get("source_document_id", ""),
                    "target_document_id": baseline_row.get("target_document_id", ""),
                }
            pair_failures[pair_id]["failing_systems"].append(system)
            pair_failures[pair_id]["iad_prevented"] = bool(pair_failures[pair_id]["iad_prevented"]) and iad_prevented
            if iad_merge:
                pair_failures[pair_id]["iad_merge_prediction"] = 1
    return pair_failures, system_stats


def _finalize_audit_rows(pair_failures: dict[str, dict], system_stats: dict[str, dict]) -> list[dict]:
    """生成 pair 级三角验证记录。

    参数:
        pair_failures: pair_id 到失败记录的映射。
        system_stats: system 到统计记录的映射。

    返回:
        pair 级审计记录。
    """
    rows: list[dict] = []
    for pair_id, row in sorted(pair_failures.items()):
        failing_systems = sorted(set(row.get("failing_systems", [])))
        failing_count = len(failing_systems)
        pattern = "cross_system_common_failure" if failing_count >= 2 else "single_system_failure"
        for system in failing_systems:
            if pattern == "cross_system_common_failure":
                system_stats[system]["common_failure_count"] += 1
            else:
                system_stats[system]["unique_failure_count"] += 1
        rows.append(
            {
                "pair_id": pair_id,
                "triangulation_pattern": pattern,
                "failing_system_count": failing_count,
                "failing_systems": failing_systems,
                "iad_prevented": bool(row.get("iad_prevented")),
                "iad_merge_prediction": int(row.get("iad_merge_prediction", 0)),
                "hard_negative_level": row.get("hard_negative_level", ""),
                "source_document_id": row.get("source_document_id", ""),
                "target_document_id": row.get("target_document_id", ""),
            }
        )
    return rows


def _finalize_system_rows(system_stats: dict[str, dict]) -> list[dict]:
    """生成 system 级三角验证统计。

    参数:
        system_stats: system 到统计记录的映射。

    返回:
        system 级统计记录。
    """
    rows: list[dict] = []
    for row in system_stats.values():
        false_merge_count = int(row.get("baseline_false_merge_count", 0))
        prevented_count = int(row.get("iad_prevented_false_merge_count", 0))
        finalized = dict(row)
        finalized["prevention_rate"] = round(prevented_count / false_merge_count, 6) if false_merge_count else 0.0
        rows.append(finalized)
    return sorted(rows, key=lambda item: str(item.get("system", "")))


def build_mechanism_triangulation_rows(
    baseline_specs: list[dict],
    iad_prediction_rows: list[dict],
) -> tuple[list[dict], list[dict]]:
    """构建机制三角验证审计记录。

    参数:
        baseline_specs: baseline specification，每项包含 system、score_field、threshold 和 rows。
        iad_prediction_rows: IAD-Risk 预测记录。

    返回:
        pair 级审计记录和 system 级统计记录。
    """
    try:
        pair_failures, system_stats = _collect_failures(baseline_specs, _iad_lookup(iad_prediction_rows))
        audit_rows = _finalize_audit_rows(pair_failures, system_stats)
        system_rows = _finalize_system_rows(system_stats)
        LOGGER.info("机制三角验证审计完成: pairs=%s systems=%s", len(audit_rows), len(system_rows))
        return audit_rows, system_rows
    except Exception:
        LOGGER.exception("构建机制三角验证审计失败")
        raise


def build_mechanism_triangulation_rows_from_paths(
    iad_predictions_path: str | Path,
    baseline_spec_values: list[str],
) -> tuple[list[dict], list[dict]]:
    """从路径构建机制三角验证审计记录。

    参数:
        iad_predictions_path: IAD-Risk predictions JSONL 文件路径。
        baseline_spec_values: baseline spec 字符串列表。

    返回:
        pair 级审计记录和 system 级统计记录。
    """
    baseline_specs: list[dict] = []
    for spec_value in baseline_spec_values:
        spec = _parse_baseline_spec(spec_value)
        spec["rows"] = read_records(spec["path"])
        baseline_specs.append(spec)
    return build_mechanism_triangulation_rows(baseline_specs, read_records(iad_predictions_path))


def build_mechanism_triangulation_summary(audit_rows: list[dict], system_rows: list[dict]) -> dict:
    """构建机制三角验证汇总。

    参数:
        audit_rows: pair 级审计记录。
        system_rows: system 级统计记录。

    返回:
        汇总记录。
    """
    system_count = len(system_rows)
    false_merge_pair_count = len(audit_rows)
    cross_system_count = sum(row.get("triangulation_pattern") == "cross_system_common_failure" for row in audit_rows)
    unresolved_count = sum(not bool(row.get("iad_prevented")) for row in audit_rows)
    systems_with_failures = sum(int(row.get("baseline_false_merge_count", 0)) > 0 for row in system_rows)
    if system_count < 2 or false_merge_pair_count == 0:
        status = "insufficient_failure_signal"
    elif unresolved_count:
        status = "partial_mechanism_evidence"
    elif cross_system_count:
        status = "cross_system_mechanism_evidence"
    elif systems_with_failures >= 2:
        status = "parallel_family_mechanism_evidence"
    else:
        status = "single_family_mechanism_evidence"
    return {
        "system_count": system_count,
        "false_merge_pair_count": false_merge_pair_count,
        "cross_system_failure_pair_count": cross_system_count,
        "single_system_failure_pair_count": false_merge_pair_count - cross_system_count,
        "unresolved_pair_count": unresolved_count,
        "triangulation_status": status,
        "q2b_mechanism_depth_ready": status == "cross_system_mechanism_evidence",
        "paper_claim_boundary": (
            "只有 cross_system_mechanism_evidence 可支撑跨 baseline 机制深度；"
            "parallel 或 single-family 证据只能写成受限机制解释。"
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
        return _list_cell([str(item) for item in value])
    return value


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 记录列表。
        fields: 字段列表。

    返回:
        无。
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_cell(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出机制三角验证 CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, audit_rows: list[dict], system_rows: list[dict], summary: dict) -> None:
    """写出 Markdown 审计报告。

    参数:
        path: 输出路径。
        audit_rows: pair 级审计记录。
        system_rows: system 级统计记录。
        summary: 汇总记录。

    返回:
        无。
    """
    lines = [
        "# Mechanism Triangulation Audit",
        "",
        "## 使用边界",
        "",
        "该报告用于检验 IAD-Risk 机制证据是否跨 baseline 家族成立；parallel 或 single-family 证据不得写成完整机制深度。",
        "",
        "## 汇总",
        "",
        f"- system_count: {summary['system_count']}",
        f"- false_merge_pair_count: {summary['false_merge_pair_count']}",
        f"- cross_system_failure_pair_count: {summary['cross_system_failure_pair_count']}",
        f"- unresolved_pair_count: {summary['unresolved_pair_count']}",
        f"- triangulation_status: {summary['triangulation_status']}",
        f"- q2b_mechanism_depth_ready: {str(summary['q2b_mechanism_depth_ready']).lower()}",
        "",
        "## 系统统计",
        "",
        "| system | baseline_false_merge_count | common_failure_count | unique_failure_count | prevention_rate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in system_rows:
        lines.append(
            "| {system} | {baseline_false_merge_count} | {common_failure_count} | {unique_failure_count} | {prevention_rate} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Pair 模式",
            "",
            "| pair_id | triangulation_pattern | failing_system_count | iad_prevented | failing_systems |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for row in audit_rows[:50]:
        lines.append(
            "| {pair_id} | {triangulation_pattern} | {failing_system_count} | {iad_prevented} | {failing_systems} |".format(
                pair_id=row.get("pair_id", ""),
                triangulation_pattern=row.get("triangulation_pattern", ""),
                failing_system_count=row.get("failing_system_count", ""),
                iad_prevented=row.get("iad_prevented", ""),
                failing_systems=_serialize_cell(row.get("failing_systems", [])),
            )
        )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出机制三角验证 Markdown 失败: %s", path)
        raise


def write_mechanism_triangulation_outputs(audit_rows: list[dict], system_rows: list[dict], output_dir: str | Path) -> None:
    """写出机制三角验证审计产物。

    参数:
        audit_rows: pair 级审计记录。
        system_rows: system 级统计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = build_mechanism_triangulation_summary(audit_rows, system_rows)
    try:
        write_records(audit_rows, directory / "mechanism_triangulation_audit.jsonl")
        write_records(system_rows, directory / "mechanism_triangulation_systems.jsonl")
        write_records([summary], directory / "mechanism_triangulation_summary.jsonl")
        _write_csv(directory / "mechanism_triangulation_audit.csv", audit_rows, AUDIT_FIELDS)
        _write_csv(directory / "mechanism_triangulation_systems.csv", system_rows, SYSTEM_FIELDS)
        _write_markdown(directory / "mechanism_triangulation_audit.md", audit_rows, system_rows, summary)
    except Exception:
        LOGGER.exception("写出机制三角验证审计失败: %s", output_dir)
        raise
