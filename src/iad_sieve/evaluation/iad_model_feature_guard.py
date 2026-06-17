"""IAD 模型特征泄漏审计模块。"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from iad_sieve.utils.io_utils import ensure_directory, write_records


LOGGER = logging.getLogger(__name__)
DEFAULT_DENIED_FIELDS = [
    "label_source",
    "label_strength",
    "label_provenance",
    "source_dataset",
    "same_source_dataset",
    "candidate_sources",
    "source_dir",
    "label_type",
    "split",
    "relation_label",
    "expected_label",
    "expected_agenda_label",
]
AUDIT_FIELDS = [
    "model_path",
    "audit_status",
    "reviewer_risk_level",
    "model_type",
    "feature_count",
    "denied_field_count",
    "violation_count",
    "denied_fields",
    "reviewer_interpretation",
    "next_optimization",
    "paper_claim_boundary",
]
VIOLATION_FIELDS = [
    "model_path",
    "model_type",
    "feature_path",
    "feature_field",
    "leakage_type",
    "reviewer_interpretation",
]


def _clean(value: object) -> str:
    """清理文本值。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _normalize_field(value: object) -> str:
    """规范化特征字段名。

    参数:
        value: 原始字段名。

    返回:
        小写字段名。
    """
    return _clean(value).lower()


def _parse_denied_fields(denied_fields: list[str] | tuple[str, ...] | str | None) -> list[str]:
    """解析禁止字段列表。

    参数:
        denied_fields: 字段列表或逗号分隔字符串。

    返回:
        去重后的禁止字段列表。
    """
    if denied_fields is None:
        return list(DEFAULT_DENIED_FIELDS)
    if isinstance(denied_fields, str):
        values = denied_fields.split(",")
    else:
        values = list(denied_fields)
    parsed = [_normalize_field(value) for value in values if _normalize_field(value)]
    return sorted(set(parsed)) if parsed else list(DEFAULT_DENIED_FIELDS)


def _collect_feature_fields(value: Any, path: str = "model") -> list[tuple[str, str]]:
    """递归收集模型中的 feature fields。

    参数:
        value: 模型节点。
        path: 当前 JSON 路径。

    返回:
        `(路径, 字段名)` 列表。
    """
    fields: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in {"feature_fields", "identity_space", "agenda_space", "risk_space"} and isinstance(child, list):
                fields.extend((child_path, _clean(item)) for item in child if _clean(item))
            else:
                fields.extend(_collect_feature_fields(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            fields.extend(_collect_feature_fields(child, f"{path}[{index}]"))
    return fields


def _leakage_type(field_name: str) -> str:
    """判断泄漏字段类型。

    参数:
        field_name: 特征字段名。

    返回:
        泄漏类型。
    """
    normalized = _normalize_field(field_name)
    if "label" in normalized or normalized in {"relation_label", "expected_label", "expected_agenda_label"}:
        return "label_leakage"
    if "source" in normalized or "provenance" in normalized or normalized == "split":
        return "provenance_shortcut"
    return "restricted_feature"


def build_iad_model_feature_guard_rows(
    models: list[dict],
    model_paths: list[str] | tuple[str, ...] | None = None,
    denied_fields: list[str] | tuple[str, ...] | str | None = None,
) -> tuple[list[dict], list[dict]]:
    """构建 IAD 模型特征泄漏审计。

    参数:
        models: 模型 JSON 记录列表。
        model_paths: 模型路径列表。
        denied_fields: 禁止作为训练特征的字段。

    返回:
        审计记录列表和违规记录列表。
    """
    denied = _parse_denied_fields(denied_fields)
    denied_set = set(denied)
    audit_rows: list[dict] = []
    violation_rows: list[dict] = []
    try:
        for index, model in enumerate(models):
            model_path = _clean((model_paths or [])[index] if model_paths and index < len(model_paths) else f"model_{index + 1}")
            model_type = _clean(model.get("model_type"))
            feature_fields = _collect_feature_fields(model)
            violations = [(path, field) for path, field in feature_fields if _normalize_field(field) in denied_set]
            for feature_path, feature_field in violations:
                violation_rows.append(
                    {
                        "model_path": model_path,
                        "model_type": model_type,
                        "feature_path": feature_path,
                        "feature_field": feature_field,
                        "leakage_type": _leakage_type(feature_field),
                        "reviewer_interpretation": f"{feature_field} 属于禁止训练特征，可能造成标签或来源捷径。",
                    }
                )
            status = "high_risk" if violations else "defensible"
            audit_rows.append(
                {
                    "model_path": model_path,
                    "audit_status": status,
                    "reviewer_risk_level": "high" if status == "high_risk" else "low",
                    "model_type": model_type,
                    "feature_count": len(feature_fields),
                    "denied_field_count": len(denied),
                    "violation_count": len(violations),
                    "denied_fields": ",".join(denied),
                    "reviewer_interpretation": (
                        "模型训练特征包含标签或来源字段，存在 shortcut leakage 风险。"
                        if status == "high_risk"
                        else "模型训练特征未包含显式标签或来源字段。"
                    ),
                    "next_optimization": "移除违规字段，重训模型，并重跑 source-bias 与 feature-guard 审计。",
                    "paper_claim_boundary": "feature guard 未通过时，不得声称模型为 provenance-blind。",
                }
            )
        LOGGER.info("IAD 模型特征泄漏审计完成: audits=%s violations=%s", len(audit_rows), len(violation_rows))
        return audit_rows, violation_rows
    except Exception:
        LOGGER.exception("构建 IAD 模型特征泄漏审计失败")
        raise


def build_iad_model_feature_guard_rows_from_paths(
    model_paths: list[str | Path] | tuple[str | Path, ...],
    denied_fields: list[str] | tuple[str, ...] | str | None = None,
) -> tuple[list[dict], list[dict]]:
    """从模型文件构建 IAD 模型特征泄漏审计。

    参数:
        model_paths: 模型 JSON 文件路径列表。
        denied_fields: 禁止作为训练特征的字段。

    返回:
        审计记录列表和违规记录列表。
    """
    normalized_paths = [str(path) for path in model_paths]
    existing_models: list[dict] = []
    existing_paths: list[str] = []
    missing_audit_rows: list[dict] = []
    try:
        for path in normalized_paths:
            model_path = Path(path)
            if not model_path.exists():
                LOGGER.warning("IAD 模型文件缺失，记录为审稿证据缺口: %s", path)
                missing_audit_rows.append(
                    {
                        "model_path": path,
                        "audit_status": "missing_model_file",
                        "reviewer_risk_level": "high",
                        "model_type": "missing",
                        "feature_count": 0,
                        "denied_field_count": len(_parse_denied_fields(denied_fields)),
                        "violation_count": 0,
                        "denied_fields": ",".join(_parse_denied_fields(denied_fields)),
                        "reviewer_interpretation": "模型文件缺失，无法证明训练特征已排除标签或来源捷径。",
                        "next_optimization": "先生成对应模型文件，再重跑 feature guard。",
                        "paper_claim_boundary": "模型文件缺失时，不得声称该模型已通过 provenance-blind 特征审计。",
                    }
                )
                continue
            existing_models.append(json.loads(model_path.read_text(encoding="utf-8")))
            existing_paths.append(path)
        audit_rows, violation_rows = build_iad_model_feature_guard_rows(
            models=existing_models,
            model_paths=existing_paths,
            denied_fields=denied_fields,
        )
        return audit_rows + missing_audit_rows, violation_rows
    except Exception:
        LOGGER.exception("读取 IAD 模型特征泄漏审计输入失败: %s", normalized_paths)
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
        LOGGER.exception("写出 IAD 模型特征泄漏审计 CSV 失败: %s", path)
        raise


def _summary(audit_rows: list[dict], violation_rows: list[dict]) -> dict:
    """构建 IAD 模型特征泄漏审计汇总。

    参数:
        audit_rows: 审计记录。
        violation_rows: 违规记录。

    返回:
        汇总记录。
    """
    return {
        "audit_count": len(audit_rows),
        "violation_count": len(violation_rows),
        "missing_model_count": sum(1 for row in audit_rows if row.get("audit_status") == "missing_model_file"),
        "high_risk_count": sum(1 for row in audit_rows if row.get("reviewer_risk_level") == "high" or row.get("audit_status") in {"high_risk", "missing_model_file"}),
        "defensible_count": sum(1 for row in audit_rows if row.get("audit_status") == "defensible"),
        "overall_feature_guard_status": "high_risk" if violation_rows or any(row.get("audit_status") != "defensible" for row in audit_rows) else "defensible",
    }


def _write_markdown(path: Path, audit_rows: list[dict], violation_rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        audit_rows: 审计记录。
        violation_rows: 违规记录。
        summary: 汇总记录。

    返回:
        无。
    """
    audit_fields = ["model_path", "audit_status", "feature_count", "violation_count", "reviewer_interpretation"]
    violation_fields = ["model_path", "feature_path", "feature_field", "leakage_type"]
    lines = [
        "# IAD Model Feature Guard",
        "",
        "## 使用边界",
        "",
        "该报告检查 IAD 模型 JSON 中的训练特征，防止 label_source、label_strength、label_provenance、same_source_dataset 等字段进入模型训练。",
        "",
        "## 汇总",
        "",
        f"- audit_count: {summary['audit_count']}",
        f"- violation_count: {summary['violation_count']}",
        f"- missing_model_count: {summary['missing_model_count']}",
        f"- high_risk_count: {summary['high_risk_count']}",
        f"- defensible_count: {summary['defensible_count']}",
        f"- overall_feature_guard_status: {summary['overall_feature_guard_status']}",
        "",
        "## 模型审计",
        "",
        "| " + " | ".join(audit_fields) + " |",
        "| " + " | ".join(["---"] * len(audit_fields)) + " |",
    ]
    for row in audit_rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in audit_fields) + " |")
    lines.extend(["", "## 违规字段", "", "| " + " | ".join(violation_fields) + " |", "| " + " | ".join(["---"] * len(violation_fields)) + " |"])
    for row in violation_rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in violation_fields) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 IAD 模型特征泄漏审计 Markdown 失败: %s", path)
        raise


def write_iad_model_feature_guard_outputs(audit_rows: list[dict], violation_rows: list[dict], output_dir: str | Path) -> None:
    """写出 IAD 模型特征泄漏审计产物。

    参数:
        audit_rows: 审计记录。
        violation_rows: 违规记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _summary(audit_rows, violation_rows)
    try:
        write_records(audit_rows, directory / "iad_model_feature_guard.jsonl")
        write_records(violation_rows, directory / "iad_model_feature_guard_violations.jsonl")
        write_records([summary], directory / "iad_model_feature_guard_summary.jsonl")
        _write_csv(directory / "iad_model_feature_guard.csv", audit_rows, AUDIT_FIELDS)
        _write_csv(directory / "iad_model_feature_guard_violations.csv", violation_rows, VIOLATION_FIELDS)
        _write_markdown(directory / "iad_model_feature_guard.md", audit_rows, violation_rows, summary)
    except Exception:
        LOGGER.exception("写出 IAD 模型特征泄漏审计失败: %s", output_dir)
        raise
