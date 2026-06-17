"""IAD-Risk 训练输入完备性审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.evaluation.iad_risk_model import AGENDA_FEATURE_FIELDS, IDENTITY_FEATURE_FIELDS, REQUIRED_HEADS, RISK_FEATURE_FIELDS
from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
FEATURE_GROUPS = {
    "identity_space": IDENTITY_FEATURE_FIELDS,
    "agenda_space": AGENDA_FEATURE_FIELDS,
    "risk_space": RISK_FEATURE_FIELDS,
}
AUDIT_FIELDS = [
    "audit_id",
    "audit_type",
    "audit_status",
    "reviewer_risk_level",
    "relation_count",
    "feature_group",
    "target_head",
    "required_feature_count",
    "present_feature_count",
    "nonconstant_feature_count",
    "missing_features",
    "positive_label_count",
    "negative_label_count",
    "reviewer_interpretation",
    "next_action",
    "paper_claim_boundary",
]


def _safe_float(value: object, default: float = 0.0) -> float:
    """安全解析浮点数。

    参数:
        value: 原始值。
        default: 解析失败时返回的默认值。

    返回:
        浮点值。
    """
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        LOGGER.warning("IAD-Risk 训练输入审计数值字段无法解析: %s", value)
        return default


def _target_label(record: dict, target: str) -> int | None:
    """读取目标 head 的二分类标签。

    参数:
        record: 输入关系记录。
        target: head 名称。

    返回:
        0/1 标签；无法读取时返回 None。
    """
    if target == "same_work":
        if "expected_label" not in record:
            return None
        return int(record.get("expected_label", 0) or 0)
    if target == "agenda_non_identity":
        if "expected_label" not in record or "expected_agenda_label" not in record:
            return None
        return 1 if int(record.get("expected_label", 0) or 0) == 0 and int(record.get("expected_agenda_label", 0) or 0) == 1 else 0
    return None


def _feature_values(relations: list[dict], feature_name: str) -> list[float]:
    """读取某个特征的数值列表。

    参数:
        relations: 关系记录。
        feature_name: 特征字段名。

    返回:
        数值列表。
    """
    return [_safe_float(row.get(feature_name)) for row in relations if feature_name in row]


def _feature_group_row(group_name: str, feature_names: list[str], relations: list[dict], min_nonconstant_features: int) -> dict:
    """构建特征组审计记录。

    参数:
        group_name: 特征组名称。
        feature_names: 必需特征字段。
        relations: 关系记录。
        min_nonconstant_features: 最少非恒定特征数。

    返回:
        特征组审计记录。
    """
    present_features: list[str] = []
    nonconstant_features: list[str] = []
    missing_features: list[str] = []
    for feature_name in feature_names:
        values = _feature_values(relations, feature_name)
        if not values:
            missing_features.append(feature_name)
            continue
        present_features.append(feature_name)
        if len(set(round(value, 12) for value in values)) > 1:
            nonconstant_features.append(feature_name)
    status = "defensible" if len(nonconstant_features) >= min_nonconstant_features else "blocked_missing_feature_signal"
    return {
        "audit_id": f"feature_group:{group_name}",
        "audit_type": "feature_group",
        "audit_status": status,
        "reviewer_risk_level": "low" if status == "defensible" else "high",
        "relation_count": len(relations),
        "feature_group": group_name,
        "required_feature_count": len(feature_names),
        "present_feature_count": len(present_features),
        "nonconstant_feature_count": len(nonconstant_features),
        "missing_features": "; ".join(missing_features),
        "reviewer_interpretation": (
            "该特征组存在足够非恒定训练信号。"
            if status == "defensible"
            else "该特征组缺少可学习的非恒定特征；raw pair 或 baseline-only 文件不能作为 IAD-Risk 训练输入。"
        ),
        "next_action": "使用 score-eval-pairs 或 relation pipeline 生成 identity/agenda/risk 特征后再训练 IAD-Risk。",
        "paper_claim_boundary": "训练输入审计未通过时，不得把对应模型结果写成有效 IAD-Risk 模型证据。",
    }


def _target_head_row(target_head: str, relations: list[dict]) -> dict:
    """构建目标 head 标签覆盖审计记录。

    参数:
        target_head: 目标 head 名称。
        relations: 关系记录。

    返回:
        目标 head 审计记录。
    """
    labels = [label for label in (_target_label(row, target_head) for row in relations) if label is not None]
    positive_count = sum(labels)
    negative_count = len(labels) - positive_count
    status = "defensible" if positive_count > 0 and negative_count > 0 else "blocked_missing_label_class"
    return {
        "audit_id": f"target_head:{target_head}",
        "audit_type": "target_head",
        "audit_status": status,
        "reviewer_risk_level": "low" if status == "defensible" else "high",
        "relation_count": len(relations),
        "target_head": target_head,
        "positive_label_count": positive_count,
        "negative_label_count": negative_count,
        "reviewer_interpretation": (
            "该 head 同时包含正负训练标签。"
            if status == "defensible"
            else "该 head 缺少正类或负类训练标签，训练完成声明不成立。"
        ),
        "next_action": "补充同一文献、同议题非同一文献和无关样本，使每个 required head 都有正负标签。",
        "paper_claim_boundary": "必要 head 标签覆盖未通过时，不得声称完整 IAD-Risk 已训练。",
    }


def build_iad_training_input_audit_rows(relations: list[dict], min_nonconstant_features: int = 2) -> list[dict]:
    """构建 IAD-Risk 训练输入完备性审计记录。

    参数:
        relations: 待训练关系记录。
        min_nonconstant_features: 每个特征组最少非恒定特征数。

    返回:
        审计记录列表。
    """
    try:
        rows: list[dict] = []
        for group_name, feature_names in FEATURE_GROUPS.items():
            rows.append(_feature_group_row(group_name, feature_names, relations, min_nonconstant_features))
        for target_head in REQUIRED_HEADS:
            rows.append(_target_head_row(target_head, relations))
        LOGGER.info("IAD-Risk 训练输入审计完成: rows=%s relations=%s", len(rows), len(relations))
        return rows
    except Exception:
        LOGGER.exception("构建 IAD-Risk 训练输入审计失败")
        raise


def build_iad_training_input_audit_rows_from_paths(relations_path: str | Path, min_nonconstant_features: int = 2) -> list[dict]:
    """从文件构建 IAD-Risk 训练输入完备性审计记录。

    参数:
        relations_path: 关系记录 JSONL 或 Parquet 路径。
        min_nonconstant_features: 每个特征组最少非恒定特征数。

    返回:
        审计记录列表。
    """
    try:
        return build_iad_training_input_audit_rows(read_records(relations_path), min_nonconstant_features=min_nonconstant_features)
    except Exception:
        LOGGER.exception("读取 IAD-Risk 训练输入审计输入失败: %s", relations_path)
        raise


def build_iad_training_input_audit_summary(rows: list[dict]) -> dict:
    """构建 IAD-Risk 训练输入审计汇总。

    参数:
        rows: 审计记录。

    返回:
        汇总记录。
    """
    blocked_count = sum(1 for row in rows if str(row.get("audit_status")) != "defensible")
    return {
        "audit_count": len(rows),
        "feature_group_count": sum(1 for row in rows if row.get("audit_type") == "feature_group"),
        "target_head_count": sum(1 for row in rows if row.get("audit_type") == "target_head"),
        "blocked_count": blocked_count,
        "defensible_count": sum(1 for row in rows if row.get("audit_status") == "defensible"),
        "training_input_ready": blocked_count == 0 and bool(rows),
        "overall_training_input_status": "defensible" if blocked_count == 0 and rows else "blocked",
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 审计记录。

    返回:
        无。
    """
    fields = [field for field in AUDIT_FIELDS if any(field in row for row in rows)]
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
        LOGGER.exception("写出 IAD-Risk 训练输入审计 CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        rows: 审计记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = ["audit_id", "audit_status", "reviewer_risk_level", "reviewer_interpretation", "next_action"]
    lines = [
        "# IAD-Risk Training Input Audit",
        "",
        "## 使用边界",
        "",
        "该报告审计关系文件是否含有 IAD-Risk 所需的 identity/agenda/risk 特征信号和必要 head 标签；未通过时不得把训练输出写成有效模型证据。",
        "",
        "## 汇总",
        "",
        f"- audit_count: {summary['audit_count']}",
        f"- blocked_count: {summary['blocked_count']}",
        f"- defensible_count: {summary['defensible_count']}",
        f"- training_input_ready: {summary['training_input_ready']}",
        f"- overall_training_input_status: {summary['overall_training_input_status']}",
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
        LOGGER.exception("写出 IAD-Risk 训练输入审计 Markdown 失败: %s", path)
        raise


def write_iad_training_input_audit_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 IAD-Risk 训练输入审计产物。

    参数:
        rows: 审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = build_iad_training_input_audit_summary(rows)
    try:
        write_records(rows, directory / "iad_training_input_audit.jsonl")
        write_records([summary], directory / "iad_training_input_audit_summary.jsonl")
        _write_csv(directory / "iad_training_input_audit.csv", rows)
        _write_markdown(directory / "iad_training_input_audit.md", rows, summary)
    except Exception:
        LOGGER.exception("写出 IAD-Risk 训练输入审计失败: %s", output_dir)
        raise
