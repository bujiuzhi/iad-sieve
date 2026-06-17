"""IAD source-held-out 关系覆盖审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
DEFAULT_RELATION_LABELS = ["same_work", "unrelated", "agenda_non_identity"]
AUDIT_FIELDS = [
    "relation_label",
    "audit_status",
    "reviewer_risk_level",
    "train_pair_count",
    "test_pair_count",
    "train_label_source_count",
    "test_label_source_count",
    "train_label_sources",
    "test_label_sources",
    "overlapping_label_source_count",
    "overlapping_label_sources",
    "coverage_blockers",
    "reviewer_interpretation",
    "next_action",
    "paper_claim_boundary",
]


def _clean(value: object) -> str:
    """清理字符串值。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _parse_relation_labels(value: str | list[str] | None) -> list[str]:
    """解析必需关系标签。

    参数:
        value: 逗号分隔字符串、列表或空值。

    返回:
        去重后的关系标签列表。
    """
    raw_values = DEFAULT_RELATION_LABELS if value is None else value
    candidates = raw_values.split(",") if isinstance(raw_values, str) else list(raw_values)
    labels: list[str] = []
    for candidate in candidates:
        label = _clean(candidate)
        if label and label not in labels:
            labels.append(label)
    if not labels:
        raise ValueError("relation_labels 不能为空")
    return labels


def _split(row: dict) -> str:
    """读取 split 名称。

    参数:
        row: pair 记录。

    返回:
        小写 split 名称。
    """
    return _clean(row.get("split")).lower()


def _relation_label(row: dict) -> str:
    """读取 relation_label。

    参数:
        row: pair 记录。

    返回:
        relation_label。
    """
    return _clean(row.get("relation_label"))


def _label_source(row: dict) -> str:
    """读取 label_source。

    参数:
        row: pair 记录。

    返回:
        label_source，缺失返回 unknown。
    """
    return _clean(row.get("label_source")) or "unknown"


def _split_strategy(row: dict) -> str:
    """读取评估 split 策略。

    参数:
        row: pair 记录。

    返回:
        split 策略名称。
    """
    return _clean(row.get("evaluation_split_strategy")).lower()


def _row_for_relation(
    relation_label: str,
    pairs: list[dict],
    min_train_pairs: int,
    min_test_pairs: int,
) -> dict:
    """构建单个关系标签的 source-held-out 覆盖记录。

    参数:
        relation_label: 关系标签。
        pairs: 全部 pair 记录。
        min_train_pairs: 最少 train pair 数。
        min_test_pairs: 最少 test pair 数。

    返回:
        覆盖审计记录。
    """
    relation_pairs = [pair for pair in pairs if _relation_label(pair) == relation_label]
    if relation_pairs and any(_split_strategy(pair) != "source_held_out" for pair in relation_pairs):
        train_pairs = [pair for pair in relation_pairs if _split(pair) == "train"]
        test_pairs = [pair for pair in relation_pairs if _split(pair) == "test"]
        train_sources = sorted({_label_source(pair) for pair in train_pairs})
        test_sources = sorted({_label_source(pair) for pair in test_pairs})
        return {
            "relation_label": relation_label,
            "audit_status": "blocked_not_source_heldout_split",
            "reviewer_risk_level": "high",
            "train_pair_count": len(train_pairs),
            "test_pair_count": len(test_pairs),
            "train_label_source_count": len(train_sources),
            "test_label_source_count": len(test_sources),
            "train_label_sources": "; ".join(train_sources),
            "test_label_sources": "; ".join(test_sources),
            "overlapping_label_source_count": len(set(train_sources) & set(test_sources)),
            "overlapping_label_sources": "; ".join(sorted(set(train_sources) & set(test_sources))),
            "coverage_blockers": "missing_source_heldout_strategy",
            "reviewer_interpretation": "输入 pair 未标记为 source-held-out split，不能作为 source-held-out 泛化覆盖证据。",
            "next_action": "先应用 source-held-out assignment，再重新运行覆盖审计。",
            "paper_claim_boundary": "普通 random split 覆盖不得写成 source-held-out 泛化证据。",
        }
    train_pairs = [pair for pair in relation_pairs if _split(pair) == "train"]
    test_pairs = [pair for pair in relation_pairs if _split(pair) == "test"]
    train_sources = sorted({_label_source(pair) for pair in train_pairs})
    test_sources = sorted({_label_source(pair) for pair in test_pairs})
    overlapping_sources = sorted(set(train_sources) & set(test_sources))
    blockers: list[str] = []
    if len(train_pairs) < min_train_pairs:
        blockers.append("missing_train_pairs")
    if len(test_pairs) < min_test_pairs:
        blockers.append("missing_test_pairs")
    if train_pairs and test_pairs and overlapping_sources:
        blockers.append("overlapping_train_test_label_sources")
    if not relation_pairs:
        status = "blocked_missing_relation"
    elif "overlapping_train_test_label_sources" in blockers:
        status = "blocked_source_overlap"
    elif blockers:
        status = "blocked_incomplete_split_coverage"
    else:
        status = "limited_source_heldout_coverage"
    risk = "low" if status == "limited_source_heldout_coverage" else "high"
    if status == "limited_source_heldout_coverage":
        interpretation = "该关系在 source-held-out train/test 中均有样本，可作为有限数据覆盖证据。"
        boundary = "仍需强模型结果和统计置信区间后，才能写成 source-held-out 泛化证据。"
        next_action = "继续执行同口径强模型和 IAD-Risk Transformer source-held-out 实验。"
    elif status == "blocked_missing_relation":
        interpretation = f"source-held-out 数据缺少 {relation_label}，不能支撑完整 IAD 关系泛化。"
        boundary = "缺少任一核心关系标签时，不得写完整 IAD source-held-out 泛化。"
        next_action = f"补充公开 {relation_label} 来源，并重新生成 source-held-out split。"
    elif status == "blocked_source_overlap":
        interpretation = f"{relation_label} 的 train/test 共享同一 label_source，不能证明该关系跨公开来源泛化。"
        boundary = "train/test 来源重叠时，不得把该关系写成 source-held-out 泛化证据。"
        next_action = f"为 {relation_label} 补充第二个独立公开来源，重新生成 source-held-out assignment。"
    else:
        interpretation = f"{relation_label} 未同时覆盖 train/test，source-held-out 结论不可复核。"
        boundary = "关系标签未覆盖 train/test 前，只能写数据构建限制。"
        next_action = f"补齐 {relation_label} 的 train/test 样本后重建覆盖审计。"
    return {
        "relation_label": relation_label,
        "audit_status": status,
        "reviewer_risk_level": risk,
        "train_pair_count": len(train_pairs),
        "test_pair_count": len(test_pairs),
        "train_label_source_count": len(train_sources),
        "test_label_source_count": len(test_sources),
        "train_label_sources": "; ".join(train_sources),
        "test_label_sources": "; ".join(test_sources),
        "overlapping_label_source_count": len(overlapping_sources),
        "overlapping_label_sources": "; ".join(overlapping_sources),
        "coverage_blockers": "; ".join(blockers),
        "reviewer_interpretation": interpretation,
        "next_action": next_action,
        "paper_claim_boundary": boundary,
    }


def build_iad_source_heldout_coverage_rows(
    pairs: list[dict],
    relation_labels: str | list[str] | None = None,
    min_train_pairs: int = 1,
    min_test_pairs: int = 1,
) -> list[dict]:
    """构建 IAD source-held-out 关系覆盖审计记录。

    参数:
        pairs: source-held-out pair 或 scored relation 记录。
        relation_labels: 必需关系标签。
        min_train_pairs: 每个关系标签最少 train pair 数。
        min_test_pairs: 每个关系标签最少 test pair 数。

    返回:
        覆盖审计记录列表。
    """
    labels = _parse_relation_labels(relation_labels)
    rows = [_row_for_relation(label, pairs, min_train_pairs=max(1, min_train_pairs), min_test_pairs=max(1, min_test_pairs)) for label in labels]
    LOGGER.info("IAD source-held-out 覆盖审计完成: rows=%s", len(rows))
    return rows


def build_iad_source_heldout_coverage_rows_from_paths(
    pairs_path: str | Path,
    relation_labels: str | list[str] | None = None,
    min_train_pairs: int = 1,
    min_test_pairs: int = 1,
) -> list[dict]:
    """从文件构建 IAD source-held-out 关系覆盖审计记录。

    参数:
        pairs_path: pair JSONL/Parquet 文件。
        relation_labels: 必需关系标签。
        min_train_pairs: 每个关系标签最少 train pair 数。
        min_test_pairs: 每个关系标签最少 test pair 数。

    返回:
        覆盖审计记录列表。
    """
    try:
        return build_iad_source_heldout_coverage_rows(
            pairs=read_records(pairs_path),
            relation_labels=relation_labels,
            min_train_pairs=min_train_pairs,
            min_test_pairs=min_test_pairs,
        )
    except Exception:
        LOGGER.exception("读取 IAD source-held-out 覆盖审计输入失败: %s", pairs_path)
        raise


def build_iad_source_heldout_coverage_summary(rows: list[dict]) -> dict:
    """构建 IAD source-held-out 覆盖审计 summary。

    参数:
        rows: 覆盖审计记录。

    返回:
        summary 记录。
    """
    blocked_rows = [row for row in rows if str(row.get("audit_status", "")).startswith("blocked")]
    ready_rows = [row for row in rows if row.get("audit_status") == "limited_source_heldout_coverage"]
    missing_relations = [row["relation_label"] for row in rows if row.get("audit_status") == "blocked_missing_relation"]
    highest_priority_blocker = ""
    if any(row.get("audit_status") == "blocked_not_source_heldout_split" for row in blocked_rows):
        highest_priority_blocker = "not_source_heldout_split"
    elif any(row.get("audit_status") == "blocked_source_overlap" for row in blocked_rows):
        highest_priority_blocker = "train_test_label_source_overlap"
    elif any(row.get("relation_label") == "agenda_non_identity" for row in blocked_rows):
        highest_priority_blocker = "agenda_non_identity_source_heldout_missing"
    elif blocked_rows:
        highest_priority_blocker = f"{blocked_rows[0].get('relation_label')}_source_heldout_missing"
    return {
        "relation_count": len(rows),
        "ready_relation_count": len(ready_rows),
        "blocked_relation_count": len(blocked_rows),
        "missing_relation_labels": missing_relations,
        "highest_priority_blocker": highest_priority_blocker,
        "source_heldout_full_iad_data_ready": bool(rows) and not blocked_rows,
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出覆盖审计 CSV。

    参数:
        path: 输出路径。
        rows: 覆盖审计记录。

    返回:
        无。
    """
    fields = [field for field in AUDIT_FIELDS if any(field in row for row in rows)]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    except OSError:
        LOGGER.exception("写出 IAD source-held-out 覆盖审计 CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出覆盖审计 Markdown。

    参数:
        path: 输出路径。
        rows: 覆盖审计记录。
        summary: summary 记录。

    返回:
        无。
    """
    fields = ["relation_label", "audit_status", "train_pair_count", "test_pair_count", "coverage_blockers", "paper_claim_boundary"]
    lines = [
        "# IAD Source-Heldout Coverage Audit",
        "",
        "## 使用边界",
        "",
        "该报告只审计 source-held-out 数据是否覆盖完整 IAD 关系标签；它不能替代模型运行、强 baseline 对比或统计置信区间。",
        "",
        "## 汇总",
        "",
        f"- relation_count: {summary['relation_count']}",
        f"- ready_relation_count: {summary['ready_relation_count']}",
        f"- blocked_relation_count: {summary['blocked_relation_count']}",
        f"- missing_relation_labels: {summary['missing_relation_labels']}",
        f"- highest_priority_blocker: {summary['highest_priority_blocker']}",
        f"- source_heldout_full_iad_data_ready: {summary['source_heldout_full_iad_data_ready']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 IAD source-held-out 覆盖审计 Markdown 失败: %s", path)
        raise


def write_iad_source_heldout_coverage_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 IAD source-held-out 覆盖审计产物。

    参数:
        rows: 覆盖审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = build_iad_source_heldout_coverage_summary(rows)
    try:
        write_records(rows, directory / "iad_source_heldout_coverage_audit.jsonl")
        write_records([summary], directory / "iad_source_heldout_coverage_summary.jsonl")
        _write_csv(directory / "iad_source_heldout_coverage_audit.csv", rows)
        _write_markdown(directory / "iad_source_heldout_coverage_audit.md", rows, summary)
    except Exception:
        LOGGER.exception("写出 IAD source-held-out 覆盖审计失败: %s", output_dir)
        raise
