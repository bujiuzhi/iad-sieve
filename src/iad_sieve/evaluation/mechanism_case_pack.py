"""机制案例包生成模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
CASE_FIELDS = [
    "case_id",
    "pair_id",
    "case_role",
    "triangulation_pattern",
    "failing_systems",
    "baseline_score_summary",
    "iad_decision",
    "p_same_work",
    "p_same_agenda",
    "p_agenda_non_identity",
    "p_false_merge_risk",
    "hard_negative_level",
    "source_document_id",
    "source_title",
    "source_year",
    "source_dataset",
    "source_topics",
    "target_document_id",
    "target_title",
    "target_year",
    "target_dataset",
    "target_topics",
    "reviewer_use",
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
        LOGGER.warning("机制案例包数值字段无法解析: %s", value)
        return default


def _is_positive(value: object) -> bool:
    """判断字段是否表示正例。

    参数:
        value: 原始字段值。

    返回:
        正例返回 True。
    """
    return value is True or _clean(value).lower() in {"1", "true", "yes"}


def _list_value(value: object) -> list[str]:
    """解析列表字段。

    参数:
        value: 原始字段值。

    返回:
        字符串列表。
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    return [item.strip() for item in str(value).split(";") if item.strip()]


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
        "threshold": _float(parts["threshold"]),
    }


def _document_index(document_rows: list[dict]) -> dict[str, dict]:
    """按 document_id 建立文档索引。

    参数:
        document_rows: 文档记录。

    返回:
        document_id 到文档记录的映射。
    """
    return {_clean(row.get("document_id")): row for row in document_rows if _clean(row.get("document_id"))}


def _prediction_index(iad_prediction_rows: list[dict]) -> dict[str, dict]:
    """按 pair_id 建立 IAD-Risk 预测索引。

    参数:
        iad_prediction_rows: IAD-Risk 预测记录。

    返回:
        pair_id 到预测记录的映射。
    """
    return {_clean(row.get("pair_id")): row for row in iad_prediction_rows if _clean(row.get("pair_id"))}


def _baseline_index(baseline_specs: list[dict]) -> dict[tuple[str, str], dict]:
    """按 system 和 pair_id 建立 baseline 分数索引。

    参数:
        baseline_specs: baseline specification 列表。

    返回:
        (system, pair_id) 到 baseline 分数记录的映射。
    """
    indexed: dict[tuple[str, str], dict] = {}
    for spec in baseline_specs:
        system = _clean(spec.get("system"))
        score_field = _clean(spec.get("score_field"))
        threshold = _float(spec.get("threshold"))
        for row in spec.get("rows", []) or []:
            pair_id = _clean(row.get("pair_id"))
            if not pair_id or not system:
                continue
            indexed[(system, pair_id)] = {
                "system": system,
                "score_field": score_field,
                "threshold": threshold,
                "score": _float(row.get(score_field)),
            }
    return indexed


def _system_order(baseline_specs: list[dict]) -> list[str]:
    """读取 baseline 系统顺序。

    参数:
        baseline_specs: baseline specification 列表。

    返回:
        系统名列表。
    """
    return [_clean(spec.get("system")) for spec in baseline_specs if _clean(spec.get("system"))]


def _score_summary(pair_id: str, failing_systems: list[str], baseline_by_pair: dict[tuple[str, str], dict]) -> str:
    """构建 baseline 分数摘要。

    参数:
        pair_id: pair ID。
        failing_systems: 失败系统列表。
        baseline_by_pair: baseline 分数索引。

    返回:
        baseline 分数摘要。
    """
    items: list[str] = []
    for system in failing_systems:
        record = baseline_by_pair.get((system, pair_id), {})
        if not record:
            items.append(f"{system}=missing")
            continue
        items.append(f"{system}={record['score']:.6f}@{record['threshold']:.6f}")
    return "; ".join(items)


def _case_role(triangulation_pattern: str, failing_systems: list[str]) -> str:
    """生成案例角色。

    参数:
        triangulation_pattern: 三角验证模式。
        failing_systems: 失败系统列表。

    返回:
        案例角色。
    """
    if triangulation_pattern == "cross_system_common_failure":
        return "shared_cross_system_failure"
    if len(failing_systems) == 1:
        return f"{failing_systems[0]}_specific_failure"
    return "limited_failure_case"


def _reviewer_use(case_role: str) -> str:
    """生成审稿用途说明。

    参数:
        case_role: 案例角色。

    返回:
        审稿用途说明。
    """
    if case_role == "shared_cross_system_failure":
        return "用于说明不同 baseline 家族会共同误合并同议题非同一文献，而 IAD-Risk 能阻断该共同错误。"
    return "用于说明某一 baseline 家族的独有误合并模式，不能单独外推为跨模型普遍机制。"


def _claim_boundary(case_role: str) -> str:
    """生成论文主张边界。

    参数:
        case_role: 案例角色。

    返回:
        论文主张边界。
    """
    if case_role == "shared_cross_system_failure":
        return "该案例只能支撑跨 baseline 机制存在性，不替代强 baseline 统计优势或 Q2/B 完成证据。"
    return "该案例只能作为错误分析示例，不得写成跨 baseline 普遍结论。"


def _group_key(row: dict) -> str:
    """生成案例抽样分组键。

    参数:
        row: 三角验证记录。

    返回:
        分组键。
    """
    systems = "+".join(_list_value(row.get("failing_systems")))
    return f"{_clean(row.get('triangulation_pattern'))}:{systems}"


def _sort_key(row: dict) -> tuple[int, int, str]:
    """生成案例排序键。

    参数:
        row: 三角验证记录。

    返回:
        排序键。
    """
    pattern_priority = 0 if _clean(row.get("triangulation_pattern")) == "cross_system_common_failure" else 1
    level_priority = {"high": 0, "medium": 1, "low": 2}.get(_clean(row.get("hard_negative_level")).lower(), 3)
    return (pattern_priority, level_priority, _clean(row.get("pair_id")))


def _select_rows(triangulation_rows: list[dict], max_cases_per_group: int) -> list[dict]:
    """按三角模式与失败系统抽样案例。

    参数:
        triangulation_rows: 三角验证记录。
        max_cases_per_group: 每个分组最多案例数。

    返回:
        选中的三角验证记录。
    """
    selected: list[dict] = []
    group_counts: dict[str, int] = {}
    for row in sorted(triangulation_rows, key=_sort_key):
        group = _group_key(row)
        if group_counts.get(group, 0) >= max_cases_per_group:
            continue
        selected.append(row)
        group_counts[group] = group_counts.get(group, 0) + 1
    return selected


def _document_fields(prefix: str, document: dict) -> dict:
    """生成文档展示字段。

    参数:
        prefix: 字段前缀。
        document: 文档记录。

    返回:
        文档展示字段。
    """
    topics = _list_value(document.get("topics"))
    return {
        f"{prefix}_title": _clean(document.get("title")),
        f"{prefix}_year": document.get("year", ""),
        f"{prefix}_dataset": _clean(document.get("source_dataset")),
        f"{prefix}_topics": _list_cell(topics),
    }


def build_mechanism_case_pack_rows(
    triangulation_rows: list[dict],
    document_rows: list[dict],
    iad_prediction_rows: list[dict],
    baseline_specs: list[dict],
    max_cases_per_group: int = 2,
) -> list[dict]:
    """构建机制案例包记录。

    参数:
        triangulation_rows: 机制三角验证 pair 级记录。
        document_rows: IAD-Bench 文档记录。
        iad_prediction_rows: IAD-Risk 预测记录。
        baseline_specs: baseline specification，每项包含 system、score_field、threshold 和 rows。
        max_cases_per_group: 每个案例分组最多输出案例数。

    返回:
        机制案例记录列表。
    """
    try:
        documents = _document_index(document_rows)
        predictions = _prediction_index(iad_prediction_rows)
        baseline_by_pair = _baseline_index(baseline_specs)
        rows: list[dict] = []
        for index, triangulation_row in enumerate(_select_rows(triangulation_rows, max_cases_per_group), start=1):
            pair_id = _clean(triangulation_row.get("pair_id"))
            failing_systems = _list_value(triangulation_row.get("failing_systems"))
            pattern = _clean(triangulation_row.get("triangulation_pattern"))
            prediction = predictions.get(pair_id, {})
            source_id = _clean(triangulation_row.get("source_document_id"))
            target_id = _clean(triangulation_row.get("target_document_id"))
            role = _case_role(pattern, failing_systems)
            row = {
                "case_id": f"mechanism_case_{index:03d}",
                "pair_id": pair_id,
                "case_role": role,
                "triangulation_pattern": pattern,
                "failing_systems": failing_systems,
                "baseline_score_summary": _score_summary(pair_id, failing_systems, baseline_by_pair),
                "iad_decision": "blocked_merge" if not _is_positive(prediction.get("merge_prediction")) else "still_merge",
                "p_same_work": _float(prediction.get("p_same_work")),
                "p_same_agenda": _float(prediction.get("p_same_agenda")),
                "p_agenda_non_identity": _float(prediction.get("p_agenda_non_identity")),
                "p_false_merge_risk": _float(prediction.get("p_false_merge_risk")),
                "hard_negative_level": _clean(triangulation_row.get("hard_negative_level")),
                "source_document_id": source_id,
                "target_document_id": target_id,
                "reviewer_use": _reviewer_use(role),
                "paper_claim_boundary": _claim_boundary(role),
            }
            row.update(_document_fields("source", documents.get(source_id, {})))
            row.update(_document_fields("target", documents.get(target_id, {})))
            rows.append(row)
        LOGGER.info("机制案例包生成完成: rows=%s systems=%s", len(rows), len(_system_order(baseline_specs)))
        return rows
    except Exception:
        LOGGER.exception("构建机制案例包失败")
        raise


def build_mechanism_case_pack_rows_from_paths(
    triangulation_path: str | Path,
    documents_path: str | Path,
    iad_predictions_path: str | Path,
    baseline_spec_values: list[str],
    max_cases_per_group: int = 2,
) -> list[dict]:
    """从路径构建机制案例包。

    参数:
        triangulation_path: mechanism_triangulation_audit JSONL 文件。
        documents_path: IAD-Bench documents JSONL 文件。
        iad_predictions_path: IAD-Risk predictions JSONL 文件。
        baseline_spec_values: baseline spec 字符串列表。
        max_cases_per_group: 每个案例分组最多输出案例数。

    返回:
        机制案例记录列表。
    """
    baseline_specs: list[dict] = []
    for spec_value in baseline_spec_values:
        spec = _parse_baseline_spec(spec_value)
        spec["rows"] = read_records(spec["path"])
        baseline_specs.append(spec)
    return build_mechanism_case_pack_rows(
        triangulation_rows=read_records(triangulation_path),
        document_rows=read_records(documents_path),
        iad_prediction_rows=read_records(iad_predictions_path),
        baseline_specs=baseline_specs,
        max_cases_per_group=max_cases_per_group,
    )


def build_mechanism_case_pack_summary(rows: list[dict]) -> dict:
    """构建机制案例包汇总。

    参数:
        rows: 机制案例记录。

    返回:
        汇总记录。
    """
    cross_count = sum(row.get("case_role") == "shared_cross_system_failure" for row in rows)
    single_count = len(rows) - cross_count
    still_merge_count = sum(row.get("iad_decision") == "still_merge" for row in rows)
    status = "paper_ready_limited_case_pack" if cross_count and single_count and not still_merge_count else "limited_case_pack"
    if not rows:
        status = "missing_case_pack"
    elif still_merge_count:
        status = "case_pack_with_unresolved_errors"
    return {
        "case_count": len(rows),
        "cross_system_case_count": cross_count,
        "single_system_case_count": single_count,
        "unresolved_case_count": still_merge_count,
        "case_pack_status": status,
        "paper_claim_boundary": (
            "案例包用于论文错误分析和机制解释；不能替代强 baseline 统计显著性、source-held-out 泛化或 Q2/B 完成证据。"
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


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 机制案例记录。

    返回:
        无。
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=CASE_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_cell(row.get(field, "")) for field in CASE_FIELDS})
    except OSError:
        LOGGER.exception("写出机制案例包 CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 机制案例包。

    参数:
        path: 输出路径。
        rows: 机制案例记录。
        summary: 汇总记录。

    返回:
        无。
    """
    lines = [
        "# Mechanism Case Pack",
        "",
        "## 使用边界",
        "",
        "该案例包用于论文错误分析和机制解释；案例不是统计显著性证明，也不是 Q2/B 完成证据。",
        "",
        "## 汇总",
        "",
        f"- case_count: {summary['case_count']}",
        f"- cross_system_case_count: {summary['cross_system_case_count']}",
        f"- single_system_case_count: {summary['single_system_case_count']}",
        f"- unresolved_case_count: {summary['unresolved_case_count']}",
        f"- case_pack_status: {summary['case_pack_status']}",
        "",
        "## 案例",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row.get('case_id', '')}: {row.get('case_role', '')}",
                "",
                f"- pair_id: {row.get('pair_id', '')}",
                f"- failing_systems: {_serialize_cell(row.get('failing_systems', []))}",
                f"- baseline_score_summary: {row.get('baseline_score_summary', '')}",
                f"- iad_decision: {row.get('iad_decision', '')}; p_false_merge_risk: {row.get('p_false_merge_risk', '')}",
                f"- source: {row.get('source_title', '')} ({row.get('source_year', '')})",
                f"- target: {row.get('target_title', '')} ({row.get('target_year', '')})",
                f"- reviewer_use: {row.get('reviewer_use', '')}",
                f"- paper_claim_boundary: {row.get('paper_claim_boundary', '')}",
                "",
            ]
        )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
    except OSError:
        LOGGER.exception("写出机制案例包 Markdown 失败: %s", path)
        raise


def write_mechanism_case_pack_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出机制案例包产物。

    参数:
        rows: 机制案例记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = build_mechanism_case_pack_summary(rows)
    try:
        write_records(rows, directory / "mechanism_case_pack.jsonl")
        write_records([summary], directory / "mechanism_case_pack_summary.jsonl")
        _write_csv(directory / "mechanism_case_pack.csv", rows)
        _write_markdown(directory / "mechanism_case_pack.md", rows, summary)
    except Exception:
        LOGGER.exception("写出机制案例包失败: %s", output_dir)
        raise
