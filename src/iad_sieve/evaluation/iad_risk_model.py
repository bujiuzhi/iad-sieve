"""IAD-Risk 双空间风险模型模块。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from iad_sieve.evaluation.baseline_runner import calculate_binary_metrics
from iad_sieve.evaluation.iad_classifier import predict_with_iad_model, train_iad_relation_model
from iad_sieve.utils.io_utils import ensure_directory, write_records


LOGGER = logging.getLogger(__name__)
IDENTITY_FEATURE_FIELDS = [
    "identity_score",
    "duplicate_score",
    "title_similarity",
    "author_overlap",
    "first_author_match",
    "identifier_score",
    "year_score",
    "conflict_score",
]
AGENDA_FEATURE_FIELDS = [
    "agenda_score",
    "topic_score",
    "full_similarity",
    "method_similarity",
    "object_similarity",
    "problem_similarity",
    "keyphrase_similarity",
    "category_overlap",
]
RISK_FEATURE_FIELDS = [
    "identity_score",
    "agenda_score",
    "agenda_non_identity_score",
    "false_merge_risk",
    "full_similarity",
    "contribution_score",
    "conflict_score",
    "identifier_score",
]
PREDICTION_METADATA_FIELDS = [
    "pair_id",
    "source_pair_id",
    "relation_label",
    "label_strength",
    "label_source",
    "label_provenance",
    "hard_negative_level",
    "split",
    "original_split",
    "evaluation_split_strategy",
    "training_evidence_scope",
    "training_label_boundary",
]
REQUIRED_HEADS = ("same_work", "agenda_non_identity")


def train_iad_risk_model(
    relations: list[dict],
    random_seed: int = 42,
    work_threshold: float = 0.5,
    agenda_block_threshold: float = 0.5,
    risk_threshold: float = 0.5,
    train_split: str | None = None,
) -> dict:
    """训练 lightweight IAD-Risk 双空间风险模型。

    参数:
        relations: 已评分且带 IAD 标签的关系记录。
        random_seed: 随机种子。
        work_threshold: same_work 合并阈值。
        agenda_block_threshold: agenda_non_identity 阻断阈值。
        risk_threshold: false_merge_risk 阻断阈值。
        train_split: 训练 split 名称；为空时使用全部记录。

    返回:
        IAD-Risk 透明 JSON 模型。
    """
    completed_relations = _complete_training_labels(relations)
    training_relations = _training_subset(completed_relations, train_split)
    same_work_head = train_iad_relation_model(training_relations, target="same_work", feature_fields=IDENTITY_FEATURE_FIELDS, random_seed=random_seed)
    same_agenda_head = train_iad_relation_model(training_relations, target="same_agenda", feature_fields=AGENDA_FEATURE_FIELDS, random_seed=random_seed)
    agenda_non_identity_head = train_iad_relation_model(
        training_relations,
        target="agenda_non_identity",
        feature_fields=RISK_FEATURE_FIELDS,
        random_seed=random_seed,
    )
    heads = {
        "same_work": same_work_head,
        "same_agenda": same_agenda_head,
        "agenda_non_identity": agenda_non_identity_head,
    }
    trained_head_count = sum(1 for head in heads.values() if head.get("trained"))
    required_head_count = len(REQUIRED_HEADS)
    trained = all(bool(heads[head_name].get("trained")) for head_name in REQUIRED_HEADS)
    model = {
        "trained": trained,
        "trained_head_count": trained_head_count,
        "required_head_count": required_head_count,
        "model_type": "iad_risk_dual_space_centroid_model",
        "random_seed": random_seed,
        "train_split": train_split or "all",
        "train_pair_count": len(training_relations),
        "heads": heads,
        "feature_groups": {
            "identity_space": IDENTITY_FEATURE_FIELDS,
            "agenda_space": AGENDA_FEATURE_FIELDS,
            "risk_space": RISK_FEATURE_FIELDS,
        },
        "merge_policy": {
            "work_threshold": work_threshold,
            "agenda_block_threshold": agenda_block_threshold,
            "risk_threshold": risk_threshold,
        },
    }
    LOGGER.info("IAD-Risk 模型训练完成: trained=%s relations=%s", trained, len(training_relations))
    return model


def _training_subset(relations: list[dict], train_split: str | None) -> list[dict]:
    """读取训练 split。

    参数:
        relations: 补全标签后的关系记录。
        train_split: 训练 split 名称；为空时使用全部记录。

    返回:
        训练关系记录。
    """
    if not train_split:
        return relations
    subset = [relation for relation in relations if str(relation.get("split", "")) == train_split]
    return subset or relations


def _complete_training_labels(relations: list[dict]) -> list[dict]:
    """补全 IAD-Risk 训练所需标签。

    参数:
        relations: 原始关系记录。

    返回:
        补全后的训练关系记录。
    """
    completed_relations: list[dict] = []
    for relation in relations:
        completed_relation = dict(relation)
        if int(completed_relation.get("expected_label", 0) or 0) == 1 and "expected_agenda_label" not in completed_relation:
            completed_relation["expected_agenda_label"] = 1
        completed_relations.append(completed_relation)
    return completed_relations


def predict_with_iad_risk_model(model: dict, relation: dict) -> dict:
    """使用 IAD-Risk 模型预测 pair 风险。

    参数:
        model: `train_iad_risk_model` 生成的模型。
        relation: 待预测关系记录。

    返回:
        包含三个 head 概率、风险概率和合并决策的记录。
    """
    heads = model.get("heads", {})
    if not model.get("trained") or not all(bool(heads.get(head_name, {}).get("trained")) for head_name in REQUIRED_HEADS):
        return {
            "p_same_work": 0.0,
            "p_same_agenda": 0.0,
            "p_agenda_non_identity": 0.0,
            "p_false_merge_risk": 1.0,
            "merge_prediction": 0,
        }
    p_same_work = predict_with_iad_model(heads["same_work"], relation)
    p_same_agenda = predict_with_iad_model(heads["same_agenda"], relation) if heads.get("same_agenda", {}).get("trained") else 0.0
    p_agenda_non_identity = predict_with_iad_model(heads["agenda_non_identity"], relation)
    p_false_merge_risk = max(p_agenda_non_identity, p_same_agenda * (1.0 - p_same_work))
    merge_policy = model.get("merge_policy", {})
    work_threshold = float(merge_policy.get("work_threshold", 0.5))
    agenda_block_threshold = float(merge_policy.get("agenda_block_threshold", 0.5))
    risk_threshold = float(merge_policy.get("risk_threshold", 0.5))
    merge_prediction = 1 if p_same_work >= work_threshold and p_agenda_non_identity < agenda_block_threshold and p_false_merge_risk < risk_threshold else 0
    return {
        "p_same_work": round(p_same_work, 6),
        "p_same_agenda": round(p_same_agenda, 6),
        "p_agenda_non_identity": round(p_agenda_non_identity, 6),
        "p_false_merge_risk": round(p_false_merge_risk, 6),
        "merge_prediction": merge_prediction,
    }


def _head_metric(model: dict, head_name: str, field: str) -> float:
    """读取 head 训练指标。

    参数:
        model: IAD-Risk 模型。
        head_name: head 名称。
        field: 指标字段。

    返回:
        指标值，缺失返回 0。
    """
    try:
        return float(model["heads"][head_name].get("training_metrics", {}).get(field, 0.0) or 0.0)
    except (KeyError, TypeError, ValueError):
        return 0.0


def _safe_int(value: object, default: int = 0) -> int:
    """安全转换整数。

    参数:
        value: 待转换值。
        default: 转换失败时返回的默认值。

    返回:
        整数值。
    """
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _infer_label_strength(relation: dict) -> str:
    """从关系记录推断 IAD-Bench 标签强度。

    参数:
        relation: 已评分关系记录。

    返回:
        标签强度，无法推断时返回空字符串。
    """
    explicit_value = str(relation.get("label_strength", "") or "")
    if explicit_value:
        return explicit_value
    label_type = str(relation.get("label_type", "") or "").lower()
    if "deepmatcher" in label_type or "gold" in label_type:
        return "gold"
    if "scirepeval" in label_type or "scidocs" in label_type or "proxy" in label_type:
        return "proxy"
    if "openalex" in label_type or "opencitations" in label_type or "weak" in label_type:
        return "silver"
    return ""


def _infer_label_source(relation: dict, label_strength: str) -> str:
    """从关系记录推断标签来源。

    参数:
        relation: 已评分关系记录。
        label_strength: 已推断的标签强度。

    返回:
        标签来源。
    """
    explicit_value = str(relation.get("label_source", "") or "")
    if explicit_value:
        return explicit_value
    label_type = str(relation.get("label_type", "") or "").lower()
    if "deepmatcher" in label_type:
        return "deepmatcher"
    if "scirepeval" in label_type or "scidocs" in label_type:
        return "scirepeval"
    candidate_sources = " ".join(str(source).lower() for source in relation.get("candidate_sources", []))
    if "opencitations" in label_type or "opencitations" in candidate_sources:
        return "openalex_opencitations"
    if "openalex" in label_type or "openalex" in candidate_sources:
        return "openalex"
    return label_strength


def _infer_relation_label(relation: dict) -> str:
    """从 expected label 推断 IAD 关系标签。

    参数:
        relation: 已评分关系记录。

    返回:
        `same_work`、`agenda_non_identity`、`unrelated` 或原始显式标签。
    """
    explicit_value = str(relation.get("relation_label", "") or "")
    if explicit_value:
        return explicit_value
    expected_label = _safe_int(relation.get("expected_label"))
    expected_agenda_label = _safe_int(relation.get("expected_agenda_label"))
    if expected_label == 1:
        return "same_work"
    if expected_agenda_label == 1:
        return "agenda_non_identity"
    return "unrelated"


def _infer_hard_negative_level(relation: dict, label_strength: str) -> str:
    """推断 hard negative 等级。

    参数:
        relation: 已评分关系记录。
        label_strength: 标签强度。

    返回:
        `high`、`medium` 或 `none`。
    """
    explicit_value = str(relation.get("hard_negative_level", "") or "")
    if explicit_value:
        return explicit_value
    expected_label = _safe_int(relation.get("expected_label"))
    expected_agenda_label = _safe_int(relation.get("expected_agenda_label"))
    if expected_label == 0 and expected_agenda_label == 1:
        return "high" if label_strength == "silver" else "medium"
    return "none"


def _build_prediction_metadata(relation: dict) -> dict:
    """构造 IAD-Risk prediction 的 provenance 元数据。

    参数:
        relation: 已评分关系记录。

    返回:
        可写入 prediction JSONL 的元数据。
    """
    metadata = {field: relation.get(field, "") for field in PREDICTION_METADATA_FIELDS if field in relation}
    label_strength = _infer_label_strength(relation)
    label_source = _infer_label_source(relation, label_strength)
    if "label_strength" not in metadata and label_strength:
        metadata["label_strength"] = label_strength
    if "label_source" not in metadata and label_source:
        metadata["label_source"] = label_source
    if "relation_label" not in metadata:
        metadata["relation_label"] = _infer_relation_label(relation)
    if "hard_negative_level" not in metadata:
        metadata["hard_negative_level"] = _infer_hard_negative_level(relation, label_strength)
    if "label_provenance" not in metadata:
        metadata["label_provenance"] = {
            "candidate_sources": relation.get("candidate_sources", []),
            "label_reason": relation.get("label_reason", ""),
            "label_type": relation.get("label_type", ""),
            "raw_similarity": relation.get("raw_similarity", ""),
            "source_pair_id": relation.get("source_pair_id", ""),
        }
    return metadata


def build_iad_risk_summary(model: dict, model_path: str | Path | None = None) -> dict:
    """构造 IAD-Risk 模型摘要。

    参数:
        model: IAD-Risk 模型。
        model_path: 可选模型路径。

    返回:
        RQ 报告可读取的摘要记录。
    """
    same_work_f1 = _head_metric(model, "same_work", "f1")
    same_agenda_f1 = _head_metric(model, "same_agenda", "f1")
    agenda_non_identity_f1 = _head_metric(model, "agenda_non_identity", "f1")
    weak_label_count = int(_head_metric(model, "same_work", "weak_label_count"))
    required_f1_values = [_head_metric(model, head_name, "f1") for head_name in REQUIRED_HEADS]
    return {
        "evidence_layer": "iad_risk_model",
        "system": "iad_risk_dual_space",
        "metric_target": "dual_space_risk_model",
        "trained": bool(model.get("trained", False)),
        "model_type": model.get("model_type", ""),
        "head_count": len(model.get("heads", {})),
        "trained_head_count": int(model.get("trained_head_count", 0)),
        "required_head_count": int(model.get("required_head_count", len(REQUIRED_HEADS))),
        "train_split": model.get("train_split", "all"),
        "train_pair_count": int(model.get("train_pair_count", 0)),
        "model_path": str(model_path or ""),
        "weak_label_count": weak_label_count,
        "same_work_f1": same_work_f1,
        "same_agenda_f1": same_agenda_f1,
        "agenda_non_identity_f1": agenda_non_identity_f1,
        "f1": min(required_f1_values) if required_f1_values else 0.0,
    }


def _binary_f1(labels: list[int], predictions: list[int]) -> float:
    """计算二分类 F1。

    参数:
        labels: 标签列表。
        predictions: 预测列表。

    返回:
        F1 值。
    """
    if not labels or len(set(labels)) < 2:
        return 0.0
    return float(calculate_binary_metrics(labels, predictions).get("f1", 0.0) or 0.0)


def _summary_for_scope(model: dict, prediction_rows: list[dict], eval_split: str, model_path: str | Path | None = None) -> dict:
    """构造指定 split 的 IAD-Risk 摘要记录。

    参数:
        model: IAD-Risk 模型。
        prediction_rows: 预测记录。
        eval_split: all、train、dev 或 test。
        model_path: 可选模型路径。

    返回:
        split 摘要记录。
    """
    if eval_split == "all":
        active_rows = prediction_rows
    else:
        active_rows = [row for row in prediction_rows if str(row.get("split", "")) == eval_split]
    same_work_labels = [int(row.get("expected_label", 0) or 0) for row in active_rows]
    same_work_predictions = [1 if float(row.get("p_same_work", 0.0) or 0.0) >= 0.5 else 0 for row in active_rows]
    same_agenda_labels = [int(row.get("expected_agenda_label", 0) or 0) for row in active_rows if "expected_agenda_label" in row]
    same_agenda_predictions = [1 if float(row.get("p_same_agenda", 0.0) or 0.0) >= 0.5 else 0 for row in active_rows if "expected_agenda_label" in row]
    agenda_non_identity_labels = [
        1 if int(row.get("expected_label", 0) or 0) == 0 and int(row.get("expected_agenda_label", 0) or 0) == 1 else 0
        for row in active_rows
        if "expected_label" in row and "expected_agenda_label" in row
    ]
    agenda_non_identity_predictions = [
        1 if float(row.get("p_agenda_non_identity", 0.0) or 0.0) >= 0.5 else 0
        for row in active_rows
        if "expected_label" in row and "expected_agenda_label" in row
    ]
    same_work_positive_count = sum(1 for label in same_work_labels if label == 1)
    same_work_negative_count = sum(1 for label in same_work_labels if label == 0)
    same_agenda_positive_count = sum(1 for label in same_agenda_labels if label == 1)
    same_agenda_negative_count = sum(1 for label in same_agenda_labels if label == 0)
    agenda_non_identity_positive_count = sum(1 for label in agenda_non_identity_labels if label == 1)
    agenda_non_identity_negative_count = sum(1 for label in agenda_non_identity_labels if label == 0)
    merge_predictions = [int(row.get("merge_prediction", 0) or 0) for row in active_rows]
    merge_metrics = calculate_binary_metrics(same_work_labels, merge_predictions) if active_rows else {}
    split_strategies = sorted({str(row.get("evaluation_split_strategy", "") or "") for row in active_rows if row.get("evaluation_split_strategy")})
    evidence_scopes = sorted({str(row.get("training_evidence_scope", "") or "") for row in active_rows if row.get("training_evidence_scope")})
    summary = build_iad_risk_summary(model, model_path=model_path)
    summary.update(
        {
            "eval_split": eval_split,
            "eval_pair_count": len(active_rows),
            "evaluation_split_strategy": "; ".join(split_strategies),
            "training_evidence_scope": "; ".join(evidence_scopes),
            "weak_label_count": len(active_rows),
            "same_work_f1": round(_binary_f1(same_work_labels, same_work_predictions), 6),
            "same_agenda_f1": round(_binary_f1(same_agenda_labels, same_agenda_predictions), 6),
            "agenda_non_identity_f1": round(_binary_f1(agenda_non_identity_labels, agenda_non_identity_predictions), 6),
            "same_work_positive_count": same_work_positive_count,
            "same_work_negative_count": same_work_negative_count,
            "same_agenda_positive_count": same_agenda_positive_count,
            "same_agenda_negative_count": same_agenda_negative_count,
            "agenda_non_identity_positive_count": agenda_non_identity_positive_count,
            "agenda_non_identity_negative_count": agenda_non_identity_negative_count,
            "precision": merge_metrics.get("precision", 0.0),
            "recall": merge_metrics.get("recall", 0.0),
            "f1": merge_metrics.get("f1", 0.0),
            "false_merge_rate": merge_metrics.get("false_merge_rate", 0.0),
        }
    )
    return summary


def _prediction_rows(model: dict, relations: list[dict]) -> list[dict]:
    """构造 IAD-Risk 预测记录。

    参数:
        model: IAD-Risk 模型。
        relations: 关系记录。

    返回:
        预测记录列表。
    """
    rows: list[dict] = []
    for relation in relations:
        prediction = predict_with_iad_risk_model(model, relation)
        metadata = _build_prediction_metadata(relation)
        rows.append(
            {
                "source_document_id": relation.get("source_document_id", ""),
                "target_document_id": relation.get("target_document_id", ""),
                "expected_label": relation.get("expected_label", ""),
                "expected_agenda_label": relation.get("expected_agenda_label", ""),
                **metadata,
                **prediction,
            }
        )
    return rows


def write_iad_risk_outputs(
    model: dict,
    relations: list[dict],
    output_dir: str | Path,
    eval_splits: list[str] | None = None,
) -> None:
    """写出 IAD-Risk 模型、摘要和预测。

    参数:
        model: IAD-Risk 模型。
        relations: 关系记录。
        output_dir: 输出目录。
        eval_splits: 可选评估 split 列表；为空时保持单条 summary 兼容输出。

    返回:
        无。
    """
    resolved_output_dir = ensure_directory(output_dir)
    model_path = resolved_output_dir / "iad_risk_model.json"
    model_path.write_text(json.dumps(model, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    prediction_rows = _prediction_rows(model, relations)
    if eval_splits:
        summary_rows = [_summary_for_scope(model, prediction_rows, eval_split, model_path=model_path) for eval_split in eval_splits]
    else:
        summary_rows = [build_iad_risk_summary(model, model_path=model_path)]
    write_records(summary_rows, resolved_output_dir / "iad_risk_summary.jsonl")
    write_records(prediction_rows, resolved_output_dir / "iad_risk_predictions.jsonl")
