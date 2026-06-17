"""IAD-Bench provenance 平衡优化计划模块。"""

from __future__ import annotations

import csv
import logging
import math
from collections import Counter
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "relation_label",
    "audit_status",
    "reviewer_risk_level",
    "pair_count",
    "current_source_count",
    "target_source_count",
    "missing_source_count",
    "dominant_source",
    "dominant_source_pair_count",
    "dominant_source_ratio",
    "max_dominant_source_ratio",
    "minimum_balance_pair_count",
    "target_pairs_per_new_source",
    "recommended_source_family",
    "recommended_action",
    "reviewer_value",
    "paper_claim_boundary",
]


def _clean(value: object) -> str:
    """清理字符串字段。

    参数:
        value: 原始值。

    返回:
        去除空白后的字符串。
    """
    return str(value or "").strip()


def _relation_label(row: dict) -> str:
    """读取 relation_label。

    参数:
        row: pair 记录。

    返回:
        relation 标签；缺失时返回 unknown。
    """
    return _clean(row.get("relation_label")) or "unknown"


def _label_source(row: dict) -> str:
    """读取 label_source。

    参数:
        row: pair 记录。

    返回:
        label_source；缺失时返回 unknown。
    """
    return _clean(row.get("label_source")) or "unknown"


def _recommended_source_family(relation_label: str) -> str:
    """根据 relation 类型推荐公开数据来源家族。

    参数:
        relation_label: relation 标签。

    返回:
        推荐数据来源类型。
    """
    normalized = relation_label.lower()
    if normalized in {"same_work", "unrelated"}:
        return "public_entity_matching_gold"
    if normalized == "agenda_non_identity":
        return "multi_topic_openalex_hard_negative"
    if normalized == "same_agenda":
        return "public_review_or_scirepeval_proxy"
    return "public_relation_source"


def _recommended_action(relation_label: str, missing_sources: int, minimum_balance_pairs: int, target_pairs_per_new_source: int) -> str:
    """生成 relation 级来源平衡动作。

    参数:
        relation_label: relation 标签。
        missing_sources: 缺失来源数。
        minimum_balance_pairs: 为降低主来源占比需要补充的最少 pair 数。
        target_pairs_per_new_source: 每个新增来源建议 pair 数。

    返回:
        可执行动作说明。
    """
    source_family = _recommended_source_family(relation_label)
    if missing_sources > 0:
        return (
            f"为 {relation_label} 至少补充 {missing_sources} 个 {source_family} 来源，"
            f"每个新增来源建议不少于 {target_pairs_per_new_source} 对。"
        )
    if minimum_balance_pairs > 0:
        return f"为 {relation_label} 的非主来源至少补充 {minimum_balance_pairs} 对，降低 dominant source 占比。"
    return f"保留 {relation_label} 的来源分布，并在 source-held-out split 中单独报告。"


def _minimum_balance_pairs(dominant_pair_count: int, total_pair_count: int, max_dominant_source_ratio: float) -> int:
    """计算降低主来源占比所需新增非主来源 pair 数。

    参数:
        dominant_pair_count: 主来源 pair 数。
        total_pair_count: 当前总 pair 数。
        max_dominant_source_ratio: 允许的主来源最大占比。

    返回:
        需要新增的最少非主来源 pair 数。
    """
    if max_dominant_source_ratio <= 0 or dominant_pair_count <= 0:
        return 0
    required_total = math.ceil(dominant_pair_count / max_dominant_source_ratio)
    return max(0, required_total - total_pair_count)


def build_iad_bench_provenance_balance_plan_rows(
    pairs: list[dict],
    min_sources_per_relation: int = 2,
    max_dominant_source_ratio: float = 0.8,
    target_pairs_per_new_source: int = 500,
) -> list[dict]:
    """构建 IAD-Bench provenance 平衡优化计划。

    参数:
        pairs: IAD-Bench pair 记录。
        min_sources_per_relation: 每类 relation 最少来源数。
        max_dominant_source_ratio: 单一来源最大建议占比。
        target_pairs_per_new_source: 每个新增来源建议 pair 数。

    返回:
        relation 级 provenance 平衡计划记录。
    """
    try:
        pairs_by_relation: dict[str, list[dict]] = {}
        for row in pairs:
            pairs_by_relation.setdefault(_relation_label(row), []).append(row)
        rows: list[dict] = []
        for relation_label in sorted(pairs_by_relation):
            relation_pairs = pairs_by_relation[relation_label]
            source_counts = Counter(_label_source(row) for row in relation_pairs)
            dominant_source, dominant_source_pair_count = source_counts.most_common(1)[0]
            pair_count = len(relation_pairs)
            current_source_count = len(source_counts)
            missing_source_count = max(0, min_sources_per_relation - current_source_count)
            dominant_source_ratio = dominant_source_pair_count / pair_count if pair_count else 0.0
            minimum_balance_pair_count = _minimum_balance_pairs(
                dominant_pair_count=dominant_source_pair_count,
                total_pair_count=pair_count,
                max_dominant_source_ratio=max_dominant_source_ratio,
            )
            if missing_source_count > 0:
                audit_status = "blocked"
                reviewer_risk_level = "high"
            elif dominant_source_ratio > max_dominant_source_ratio:
                audit_status = "high_risk"
                reviewer_risk_level = "high"
            else:
                audit_status = "defensible"
                reviewer_risk_level = "low"
            rows.append(
                {
                    "relation_label": relation_label,
                    "audit_status": audit_status,
                    "reviewer_risk_level": reviewer_risk_level,
                    "pair_count": pair_count,
                    "current_source_count": current_source_count,
                    "target_source_count": min_sources_per_relation,
                    "missing_source_count": missing_source_count,
                    "dominant_source": dominant_source,
                    "dominant_source_pair_count": dominant_source_pair_count,
                    "dominant_source_ratio": round(dominant_source_ratio, 6),
                    "max_dominant_source_ratio": max_dominant_source_ratio,
                    "minimum_balance_pair_count": minimum_balance_pair_count,
                    "target_pairs_per_new_source": target_pairs_per_new_source,
                    "recommended_source_family": _recommended_source_family(relation_label),
                    "recommended_action": _recommended_action(
                        relation_label,
                        missing_source_count,
                        minimum_balance_pair_count,
                        target_pairs_per_new_source,
                    ),
                    "reviewer_value": "把 source bias 诊断转成 relation 级公开数据补齐目标，支撑 source-held-out 与 provenance-blind 结论。",
                    "paper_claim_boundary": "该 relation 来源未平衡前，不能写成已排除 provenance shortcut。",
                }
            )
        LOGGER.info("IAD-Bench provenance 平衡优化计划完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建 IAD-Bench provenance 平衡优化计划失败")
        raise


def build_iad_bench_provenance_balance_plan_rows_from_paths(
    pairs_path: str | Path,
    min_sources_per_relation: int = 2,
    max_dominant_source_ratio: float = 0.8,
    target_pairs_per_new_source: int = 500,
) -> list[dict]:
    """从 IAD-Bench pairs 文件构建 provenance 平衡优化计划。

    参数:
        pairs_path: IAD-Bench pairs JSONL 文件。
        min_sources_per_relation: 每类 relation 最少来源数。
        max_dominant_source_ratio: 单一来源最大建议占比。
        target_pairs_per_new_source: 每个新增来源建议 pair 数。

    返回:
        provenance 平衡计划记录。
    """
    try:
        return build_iad_bench_provenance_balance_plan_rows(
            pairs=read_records(pairs_path),
            min_sources_per_relation=min_sources_per_relation,
            max_dominant_source_ratio=max_dominant_source_ratio,
            target_pairs_per_new_source=target_pairs_per_new_source,
        )
    except Exception:
        LOGGER.exception("读取 IAD-Bench provenance 平衡优化计划输入失败: %s", pairs_path)
        raise


def _serialize_cell(value: object) -> object:
    """序列化 CSV / Markdown 单元格。

    参数:
        value: 原始值。

    返回:
        可写入单元格的值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 provenance 平衡计划 CSV。

    参数:
        path: 输出路径。
        rows: 计划记录。

    返回:
        无。
    """
    fields = [field for field in PREFERRED_FIELDS if any(field in row for row in rows)]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_cell(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出 IAD-Bench provenance 平衡计划 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建 provenance 平衡计划汇总。

    参数:
        rows: 计划记录。

    返回:
        summary 记录。
    """
    return {
        "relation_count": len(rows),
        "blocked_relation_count": sum(1 for row in rows if row.get("audit_status") == "blocked"),
        "high_risk_relation_count": sum(1 for row in rows if row.get("audit_status") == "high_risk"),
        "defensible_relation_count": sum(1 for row in rows if row.get("audit_status") == "defensible"),
        "max_dominant_source_ratio": max((float(row.get("dominant_source_ratio", 0.0) or 0.0) for row in rows), default=0.0),
        "overall_provenance_balance_status": "blocked"
        if any(row.get("audit_status") == "blocked" for row in rows)
        else ("high_risk" if any(row.get("audit_status") == "high_risk" for row in rows) else "defensible"),
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 provenance 平衡计划 Markdown。

    参数:
        path: 输出路径。
        rows: 计划记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = [
        "relation_label",
        "audit_status",
        "current_source_count",
        "dominant_source",
        "dominant_source_ratio",
        "minimum_balance_pair_count",
        "recommended_action",
    ]
    lines = [
        "# IAD-Bench Provenance Balance Plan",
        "",
        "## 使用边界",
        "",
        "该计划把来源捷径风险转换为 relation 级公开数据补齐目标；它不是新增实验结果，不能替代真实 source-held-out 评估。",
        "",
        "## 汇总",
        "",
        f"- relation_count: {summary['relation_count']}",
        f"- blocked_relation_count: {summary['blocked_relation_count']}",
        f"- high_risk_relation_count: {summary['high_risk_relation_count']}",
        f"- defensible_relation_count: {summary['defensible_relation_count']}",
        f"- max_dominant_source_ratio: {summary['max_dominant_source_ratio']}",
        f"- overall_provenance_balance_status: {summary['overall_provenance_balance_status']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        values = [str(_serialize_cell(row.get(field, ""))).replace("\n", " ").replace("|", "/") for field in fields]
        lines.append("| " + " | ".join(values) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 IAD-Bench provenance 平衡计划 Markdown 失败: %s", path)
        raise


def write_iad_bench_provenance_balance_plan_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 provenance 平衡计划产物。

    参数:
        rows: 计划记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "iad_bench_provenance_balance_plan.jsonl")
        write_records([summary], directory / "iad_bench_provenance_balance_plan_summary.jsonl")
        _write_csv(directory / "iad_bench_provenance_balance_plan.csv", rows)
        _write_markdown(directory / "iad_bench_provenance_balance_plan.md", rows, summary)
    except Exception:
        LOGGER.exception("写出 IAD-Bench provenance 平衡计划失败: %s", output_dir)
        raise
