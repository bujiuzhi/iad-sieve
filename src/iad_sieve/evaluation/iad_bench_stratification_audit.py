"""IAD-Bench 标签分层分布审计模块。"""

from __future__ import annotations

import csv
import logging
from collections import Counter, defaultdict
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
AUDIT_FIELDS = [
    "dimension_id",
    "audit_status",
    "reviewer_risk_level",
    "pair_count",
    "split_count",
    "relation_label_count",
    "label_strength_count",
    "label_source_count",
    "missing_cells",
    "top_label_strength",
    "top_label_strength_count",
    "top_label_strength_ratio",
    "min_relation_source_count",
    "missing_provenance_count",
    "reviewer_interpretation",
    "next_optimization",
]
DISTRIBUTION_FIELDS = [
    "stratum_id",
    "split",
    "relation_label",
    "label_strength",
    "label_source",
    "pair_count",
    "pair_ratio",
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


def _relation_label(row: dict) -> str:
    """读取 relation_label。

    参数:
        row: pair 记录。

    返回:
        relation_label；缺失时返回 unknown。
    """
    return _clean(row.get("relation_label")) or "unknown"


def _label_strength(row: dict) -> str:
    """读取 label_strength。

    参数:
        row: pair 记录。

    返回:
        小写 label_strength；缺失时返回 unknown。
    """
    return _clean(row.get("label_strength")).lower() or "unknown"


def _label_source(row: dict) -> str:
    """读取 label_source。

    参数:
        row: pair 记录。

    返回:
        小写 label_source；缺失时返回 unknown。
    """
    return _clean(row.get("label_source")).lower() or "unknown"


def _has_provenance(row: dict) -> bool:
    """判断 pair 是否包含可复核 label provenance。

    参数:
        row: pair 记录。

    返回:
        有 provenance 返回 True。
    """
    provenance = row.get("label_provenance")
    return isinstance(provenance, dict) and bool(provenance)


def _is_label_strength_imbalance_risky(strength_counts: Counter, top_strength: str, top_strength_ratio: float, max_top_strength_ratio: float) -> bool:
    """判断 label_strength 占比是否构成审稿风险。

    参数:
        strength_counts: label_strength 计数。
        top_strength: 最大占比 label_strength。
        top_strength_ratio: 最大占比。
        max_top_strength_ratio: 风险阈值。

    返回:
        构成风险返回 True。
    """
    if not strength_counts or top_strength_ratio <= max_top_strength_ratio:
        return False
    if set(strength_counts) == {"gold"} and top_strength == "gold":
        return False
    return True


def _label_strength_interpretation(imbalance_status: str, top_strength: str) -> str:
    """构造 label_strength 审计解释。

    参数:
        imbalance_status: 审计状态。
        top_strength: 最大占比 label_strength。

    返回:
        审稿解释。
    """
    if imbalance_status == "high_risk":
        return "单一 label_strength 占比过高，主结果容易被某一证据层主导。"
    if top_strength == "gold":
        return "公开 gold-only 子集可作为独立强标签评估，但不能替代 silver/proxy 分层结论。"
    return "label_strength 总体占比未超过风险阈值。"


def _normalize_required(values: list[str] | tuple[str, ...] | None, observed_values: set[str]) -> list[str]:
    """规范化必需值列表。

    参数:
        values: 外部传入的必需值。
        observed_values: 当前观察到的值集合。

    返回:
        去重后的必需值列表。
    """
    raw_values = values if values is not None else sorted(observed_values)
    normalized: list[str] = []
    for value in raw_values:
        cleaned = _clean(value).lower()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return normalized


def _count_rows_by_fields(pairs: list[dict], fields: list[str]) -> Counter[tuple[str, ...]]:
    """按字段组合统计 pair 数。

    参数:
        pairs: pair 记录。
        fields: 字段名称列表。

    返回:
        字段值 tuple 到数量的计数器。
    """
    extractors = {
        "split": _split_name,
        "relation_label": _relation_label,
        "label_strength": _label_strength,
        "label_source": _label_source,
    }
    counts: Counter[tuple[str, ...]] = Counter()
    for row in pairs:
        counts[tuple(extractors[field](row) for field in fields)] += 1
    return counts


def _distribution_rows(pairs: list[dict]) -> list[dict]:
    """构建分层分布记录。

    参数:
        pairs: pair 记录。

    返回:
        分层分布记录列表。
    """
    total_count = len(pairs)
    specs = [
        ("split_x_label_strength", ["split", "label_strength"]),
        ("split_x_relation_label", ["split", "relation_label"]),
        ("relation_label_x_label_source", ["relation_label", "label_source"]),
        ("label_strength_total", ["label_strength"]),
        ("label_source_total", ["label_source"]),
    ]
    rows: list[dict] = []
    for stratum_id, fields in specs:
        counts = _count_rows_by_fields(pairs, fields)
        for key, count in sorted(counts.items()):
            row = {"stratum_id": stratum_id, "pair_count": count, "pair_ratio": round(count / total_count, 6) if total_count else 0.0}
            for field, value in zip(fields, key, strict=True):
                row[field] = value
            rows.append(row)
    return rows


def _missing_split_strength_cells(pairs: list[dict], required_splits: list[str], required_label_strengths: list[str]) -> list[str]:
    """统计 split x label_strength 缺失格。

    参数:
        pairs: pair 记录。
        required_splits: 必需 split。
        required_label_strengths: 必需 label_strength。

    返回:
        缺失格列表。
    """
    counts = _count_rows_by_fields(pairs, ["split", "label_strength"])
    missing = []
    for split in required_splits:
        for strength in required_label_strengths:
            if counts.get((split, strength), 0) == 0:
                missing.append(f"{split}:{strength}")
    return missing


def _missing_split_relation_cells(pairs: list[dict], required_splits: list[str], required_relations: list[str]) -> list[str]:
    """统计 split x relation_label 缺失格。

    参数:
        pairs: pair 记录。
        required_splits: 必需 split。
        required_relations: 必需 relation_label。

    返回:
        缺失格列表。
    """
    counts = _count_rows_by_fields(pairs, ["split", "relation_label"])
    missing = []
    for split in required_splits:
        for relation in required_relations:
            if counts.get((split, relation), 0) == 0:
                missing.append(f"{split}:{relation}")
    return missing


def _relation_source_counts(pairs: list[dict]) -> dict[str, int]:
    """统计每类 relation 覆盖的来源数。

    参数:
        pairs: pair 记录。

    返回:
        relation_label 到 label_source 数的映射。
    """
    sources_by_relation: dict[str, set[str]] = defaultdict(set)
    for row in pairs:
        sources_by_relation[_relation_label(row)].add(_label_source(row))
    return {relation: len(sources) for relation, sources in sources_by_relation.items()}


def build_iad_bench_stratification_audit_rows(
    pairs: list[dict],
    required_splits: list[str] | tuple[str, ...] | None = None,
    required_label_strengths: list[str] | tuple[str, ...] | None = None,
    required_relations: list[str] | tuple[str, ...] | None = None,
    max_top_strength_ratio: float = 0.8,
    min_sources_per_relation: int = 2,
) -> tuple[list[dict], list[dict]]:
    """构建 IAD-Bench 分层分布审计记录。

    参数:
        pairs: IAD-Bench pair 记录。
        required_splits: 必需 split 列表；默认使用 train/dev/test。
        required_label_strengths: 必需 label_strength；默认使用数据中观察到的强度。
        required_relations: 必需 relation_label；默认使用数据中观察到的 relation。
        max_top_strength_ratio: 单一 label_strength 最大占比阈值。
        min_sources_per_relation: 每类 relation 需要的最少 label_source 数。

    返回:
        审计记录列表和分层分布记录列表。
    """
    try:
        observed_splits = {_split_name(row) for row in pairs}
        observed_strengths = {_label_strength(row) for row in pairs}
        observed_relations = {_relation_label(row) for row in pairs}
        observed_sources = {_label_source(row) for row in pairs}
        target_splits = _normalize_required(required_splits or ["train", "dev", "test"], observed_splits)
        target_strengths = _normalize_required(required_label_strengths, observed_strengths)
        target_relations = _normalize_required(required_relations, observed_relations)
        strength_counts = Counter(_label_strength(row) for row in pairs)
        top_strength, top_strength_count = strength_counts.most_common(1)[0] if strength_counts else ("", 0)
        top_strength_ratio = round(top_strength_count / len(pairs), 6) if pairs else 0.0
        missing_strength_cells = _missing_split_strength_cells(pairs, target_splits, target_strengths)
        missing_relation_cells = _missing_split_relation_cells(pairs, target_splits, target_relations)
        relation_source_counts = _relation_source_counts(pairs)
        min_relation_source_count = min(relation_source_counts.values()) if relation_source_counts else 0
        missing_provenance_count = sum(1 for row in pairs if not _has_provenance(row))
        strength_status = "blocked" if missing_strength_cells else "defensible"
        relation_status = "blocked" if missing_relation_cells else "defensible"
        imbalance_status = (
            "high_risk"
            if _is_label_strength_imbalance_risky(strength_counts, top_strength, top_strength_ratio, max_top_strength_ratio)
            else "defensible"
        )
        source_status = "blocked" if min_relation_source_count < min_sources_per_relation else "defensible"
        provenance_status = "blocked" if missing_provenance_count else "defensible"
        audit_rows = [
            {
                "dimension_id": "split_label_strength_coverage",
                "audit_status": strength_status,
                "reviewer_risk_level": "high" if strength_status == "blocked" else "low",
                "pair_count": len(pairs),
                "split_count": len(observed_splits),
                "label_strength_count": len(observed_strengths),
                "missing_cells": missing_strength_cells,
                "reviewer_interpretation": "每个 split 均覆盖必需 label_strength。" if strength_status == "defensible" else "部分 split 缺少必需 label_strength，指标可能被 split 偏置放大。",
                "next_optimization": "按 split x label_strength 分层重采样，确保 gold/silver/proxy 在 train/dev/test 均有覆盖。",
            },
            {
                "dimension_id": "split_relation_coverage",
                "audit_status": relation_status,
                "reviewer_risk_level": "high" if relation_status == "blocked" else "low",
                "pair_count": len(pairs),
                "split_count": len(observed_splits),
                "relation_label_count": len(observed_relations),
                "missing_cells": missing_relation_cells,
                "reviewer_interpretation": "每个 split 均覆盖必需 relation_label。" if relation_status == "defensible" else "部分 split 缺少必需 relation_label，relation 级指标不可直接泛化。",
                "next_optimization": "按 split x relation_label 分层重采样，避免只在单一 split 看到某类关系。",
            },
            {
                "dimension_id": "label_strength_imbalance",
                "audit_status": imbalance_status,
                "reviewer_risk_level": "high" if imbalance_status == "high_risk" else "low",
                "pair_count": len(pairs),
                "label_strength_count": len(observed_strengths),
                "top_label_strength": top_strength,
                "top_label_strength_count": top_strength_count,
                "top_label_strength_ratio": top_strength_ratio,
                "reviewer_interpretation": _label_strength_interpretation(imbalance_status, top_strength),
                "next_optimization": "补充公开 gold/proxy 或下采样 silver，报告按 label_strength 分层的主指标。",
            },
            {
                "dimension_id": "source_relation_confounding",
                "audit_status": source_status,
                "reviewer_risk_level": "high" if source_status == "blocked" else "low",
                "pair_count": len(pairs),
                "relation_label_count": len(observed_relations),
                "label_source_count": len(observed_sources),
                "min_relation_source_count": min_relation_source_count,
                "reviewer_interpretation": "每类 relation 已覆盖多个 label_source。" if source_status == "defensible" else "relation_label 与 label_source 绑定过强，模型可能学习来源差异而非关系本身。",
                "next_optimization": "为 same_work、unrelated、agenda_non_identity 分别补充至少两个公开来源，并做 source-held-out 复核。",
            },
            {
                "dimension_id": "provenance_completeness",
                "audit_status": provenance_status,
                "reviewer_risk_level": "high" if provenance_status == "blocked" else "low",
                "pair_count": len(pairs),
                "missing_provenance_count": missing_provenance_count,
                "reviewer_interpretation": "所有 pair 均包含 label_provenance。" if provenance_status == "defensible" else "部分 pair 缺少 label_provenance，无法解释标签来源。",
                "next_optimization": "修复缺失 provenance 的 pair，确保 label_type、source_dir、topic 或 gold 依据可追溯。",
            },
        ]
        distributions = _distribution_rows(pairs)
        LOGGER.info("IAD-Bench 分层分布审计完成: audit_rows=%s distribution_rows=%s", len(audit_rows), len(distributions))
        return audit_rows, distributions
    except Exception:
        LOGGER.exception("构建 IAD-Bench 分层分布审计失败")
        raise


def build_iad_bench_stratification_audit_rows_from_paths(
    pairs_path: str | Path,
    max_top_strength_ratio: float = 0.8,
    min_sources_per_relation: int = 2,
) -> tuple[list[dict], list[dict]]:
    """从 pair 文件构建 IAD-Bench 分层分布审计。

    参数:
        pairs_path: IAD-Bench pair JSONL。
        max_top_strength_ratio: 单一 label_strength 最大占比阈值。
        min_sources_per_relation: 每类 relation 需要的最少 label_source 数。

    返回:
        审计记录列表和分层分布记录列表。
    """
    try:
        return build_iad_bench_stratification_audit_rows(
            pairs=read_records(pairs_path),
            max_top_strength_ratio=max_top_strength_ratio,
            min_sources_per_relation=min_sources_per_relation,
        )
    except Exception:
        LOGGER.exception("读取 IAD-Bench 分层分布审计输入失败: %s", pairs_path)
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
        LOGGER.exception("写出 IAD-Bench 分层分布审计 CSV 失败: %s", path)
        raise


def _summary(audit_rows: list[dict], distribution_rows: list[dict]) -> dict:
    """构建 IAD-Bench 分层分布审计汇总。

    参数:
        audit_rows: 审计记录。
        distribution_rows: 分布记录。

    返回:
        汇总记录。
    """
    return {
        "dimension_count": len(audit_rows),
        "distribution_row_count": len(distribution_rows),
        "blocked_count": sum(1 for row in audit_rows if row.get("audit_status") == "blocked"),
        "high_risk_count": sum(1 for row in audit_rows if row.get("audit_status") == "high_risk"),
        "defensible_count": sum(1 for row in audit_rows if row.get("audit_status") == "defensible"),
        "overall_stratification_status": "blocked" if any(row.get("audit_status") in {"blocked", "high_risk"} for row in audit_rows) else "defensible",
    }


def _write_markdown(path: Path, audit_rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        audit_rows: 审计记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = ["dimension_id", "audit_status", "reviewer_risk_level", "reviewer_interpretation", "next_optimization"]
    lines = [
        "# IAD-Bench Stratification Audit",
        "",
        "## 使用边界",
        "",
        "该报告审计 IAD-Bench 的 split、relation_label、label_strength 和 label_source 分层分布；若存在 blocked 或 high_risk，论文必须按对应分层限制主张。",
        "",
        "## 汇总",
        "",
        f"- dimension_count: {summary['dimension_count']}",
        f"- distribution_row_count: {summary['distribution_row_count']}",
        f"- blocked_count: {summary['blocked_count']}",
        f"- high_risk_count: {summary['high_risk_count']}",
        f"- defensible_count: {summary['defensible_count']}",
        f"- overall_stratification_status: {summary['overall_stratification_status']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in audit_rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 IAD-Bench 分层分布审计 Markdown 失败: %s", path)
        raise


def write_iad_bench_stratification_audit_outputs(audit_rows: list[dict], distribution_rows: list[dict], output_dir: str | Path) -> None:
    """写出 IAD-Bench 分层分布审计产物。

    参数:
        audit_rows: 审计记录。
        distribution_rows: 分层分布记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _summary(audit_rows, distribution_rows)
    try:
        write_records(audit_rows, directory / "iad_bench_stratification_audit.jsonl")
        write_records(distribution_rows, directory / "iad_bench_strata_distribution.jsonl")
        write_records([summary], directory / "iad_bench_stratification_audit_summary.jsonl")
        _write_csv(directory / "iad_bench_stratification_audit.csv", audit_rows, AUDIT_FIELDS)
        _write_csv(directory / "iad_bench_strata_distribution.csv", distribution_rows, DISTRIBUTION_FIELDS)
        _write_markdown(directory / "iad_bench_stratification_audit.md", audit_rows, summary)
    except Exception:
        LOGGER.exception("写出 IAD-Bench 分层分布审计失败: %s", output_dir)
        raise
