"""IAD-Sieve 轻量关系分类器训练模块。"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

from iad_sieve.evaluation.baseline_runner import calculate_binary_metrics
from iad_sieve.utils.io_utils import ensure_parent


LOGGER = logging.getLogger(__name__)

FEATURE_FIELDS = [
    "identity_score",
    "duplicate_score",
    "agenda_score",
    "topic_score",
    "agenda_non_identity_score",
    "false_merge_risk",
    "title_similarity",
    "full_similarity",
    "lexical_similarity",
    "author_overlap",
    "first_author_match",
    "year_score",
    "identifier_score",
    "category_overlap",
    "method_similarity",
    "object_similarity",
    "result_similarity",
    "problem_similarity",
    "keyphrase_similarity",
    "contribution_score",
    "conflict_score",
]
SUPPORTED_TARGETS = {"same_work", "same_agenda", "agenda_non_identity"}


def _as_float(record: dict, field: str) -> float:
    """安全读取浮点字段。

    参数:
        record: 输入记录。
        field: 字段名。

    返回:
        浮点值，缺失或非法时返回 0。
    """
    try:
        return float(record.get(field, 0.0) or 0.0)
    except (TypeError, ValueError):
        LOGGER.warning("IAD 分类器字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return 0.0


def _feature_vector(record: dict, feature_fields: list[str]) -> list[float]:
    """构造单条关系特征向量。

    参数:
        record: 关系记录。
        feature_fields: 特征字段列表。

    返回:
        特征向量。
    """
    return [_as_float(record, field) for field in feature_fields]


def _target_label(record: dict, target: str) -> int | None:
    """读取训练目标标签。

    参数:
        record: 关系记录。
        target: 目标名称。

    返回:
        0/1 标签；当前记录不适用该目标时返回 None。
    """
    if target == "same_work":
        return int(record["expected_label"]) if "expected_label" in record else None
    if target == "same_agenda":
        return int(record["expected_agenda_label"]) if "expected_agenda_label" in record else None
    if target == "agenda_non_identity":
        if "expected_label" not in record or "expected_agenda_label" not in record:
            return None
        return 1 if int(record["expected_label"]) == 0 and int(record["expected_agenda_label"]) == 1 else 0
    raise ValueError(f"不支持的 IAD 分类目标: {target}")


def _training_rows(relations: list[dict], target: str, feature_fields: list[str]) -> tuple[list[list[float]], list[int]]:
    """构造训练矩阵与标签。

    参数:
        relations: 关系记录列表。
        target: 目标名称。
        feature_fields: 特征字段列表。

    返回:
        特征矩阵与标签列表。
    """
    features: list[list[float]] = []
    labels: list[int] = []
    for relation in relations:
        label = _target_label(relation, target)
        if label is None:
            continue
        features.append(_feature_vector(relation, feature_fields))
        labels.append(label)
    return features, labels


def _skip_model(target: str, labels: list[int], reason: str, feature_fields: list[str]) -> dict:
    """构造未训练模型摘要。

    参数:
        target: 目标名称。
        labels: 标签列表。
        reason: 跳过原因。
        feature_fields: 特征字段列表。

    返回:
        模型摘要字典。
    """
    return {
        "target": target,
        "trained": False,
        "skip_reason": reason,
        "feature_fields": feature_fields,
        "training_metrics": {
            "weak_label_count": len(labels),
            "positive_label_count": sum(labels),
            "negative_label_count": len(labels) - sum(labels),
        },
    }


def _sigmoid(value: float) -> float:
    """计算 sigmoid 概率。

    参数:
        value: 线性模型输出。

    返回:
        0 到 1 的概率。
    """
    if value >= 0:
        z_value = math.exp(-value)
        return 1.0 / (1.0 + z_value)
    z_value = math.exp(value)
    return z_value / (1.0 + z_value)


def _feature_means(features: list[list[float]]) -> list[float]:
    """计算每个特征列的均值。

    参数:
        features: 特征矩阵。

    返回:
        特征均值列表。
    """
    column_count = len(features[0])
    return [sum(row[column_index] for row in features) / len(features) for column_index in range(column_count)]


def _feature_scales(features: list[list[float]], means: list[float]) -> list[float]:
    """计算每个特征列的标准差。

    参数:
        features: 特征矩阵。
        means: 特征均值列表。

    返回:
        特征标准差列表；常量列返回 1。
    """
    scales: list[float] = []
    for column_index, mean_value in enumerate(means):
        variance = sum((row[column_index] - mean_value) ** 2 for row in features) / len(features)
        scale = math.sqrt(variance)
        scales.append(scale if scale > 0.0 else 1.0)
    return scales


def _standardize_features(features: list[list[float]], means: list[float], scales: list[float]) -> list[list[float]]:
    """标准化特征矩阵。

    参数:
        features: 原始特征矩阵。
        means: 特征均值列表。
        scales: 特征标准差列表。

    返回:
        标准化后的特征矩阵。
    """
    return [[(value - means[index]) / scales[index] for index, value in enumerate(row)] for row in features]


def _centroid(features: list[list[float]]) -> list[float]:
    """计算特征中心。

    参数:
        features: 同一类别的标准化特征矩阵。

    返回:
        类别中心向量。
    """
    column_count = len(features[0])
    return [sum(row[column_index] for row in features) / len(features) for column_index in range(column_count)]


def _dot(left_values: list[float], right_values: list[float]) -> float:
    """计算向量点积。

    参数:
        left_values: 左侧向量。
        right_values: 右侧向量。

    返回:
        点积结果。
    """
    return sum(left_value * right_value for left_value, right_value in zip(left_values, right_values, strict=True))


def train_iad_relation_model(
    relations: list[dict],
    target: str,
    feature_fields: list[str] | None = None,
    random_seed: int = 42,
) -> dict:
    """训练单个 IAD 轻量关系分类器。

    参数:
        relations: 已评分且带标签的关系记录。
        target: 训练目标，支持 same_work、same_agenda、agenda_non_identity。
        feature_fields: 可选特征字段列表。
        random_seed: 随机种子。

    返回:
        透明 JSON 模型字典。
    """
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"不支持的 IAD 分类目标: {target}")
    active_feature_fields = feature_fields or FEATURE_FIELDS
    features, labels = _training_rows(relations, target, active_feature_fields)
    if len(labels) < 2 or len(set(labels)) < 2:
        return _skip_model(target, labels, "single_class_or_missing_label", active_feature_fields)
    means = _feature_means(features)
    scales = _feature_scales(features, means)
    scaled_features = _standardize_features(features, means, scales)
    positive_features = [row for row, label in zip(scaled_features, labels, strict=True) if label == 1]
    negative_features = [row for row, label in zip(scaled_features, labels, strict=True) if label == 0]
    positive_centroid = _centroid(positive_features)
    negative_centroid = _centroid(negative_features)
    coefficients = [positive_value - negative_value for positive_value, negative_value in zip(positive_centroid, negative_centroid, strict=True)]
    prior_offset = math.log(len(positive_features) / len(negative_features))
    intercept = -0.5 * (_dot(positive_centroid, positive_centroid) - _dot(negative_centroid, negative_centroid)) + prior_offset
    model = {
        "target": target,
        "trained": True,
        "model_type": "standardized_centroid_linear_classifier",
        "feature_fields": active_feature_fields,
        "feature_means": [float(value) for value in means],
        "feature_scales": [float(value) if float(value) != 0.0 else 1.0 for value in scales],
        "coefficients": [float(value) for value in coefficients],
        "intercept": float(intercept),
        "positive_probability_threshold": 0.5,
        "random_seed": random_seed,
    }
    probabilities = [predict_with_iad_model(model, relation) for relation in relations if _target_label(relation, target) is not None]
    predictions = [1 if probability >= 0.5 else 0 for probability in probabilities]
    model["training_metrics"] = calculate_binary_metrics(labels, predictions)
    LOGGER.info("IAD 轻量分类器训练完成: target=%s rows=%s", target, len(labels))
    return model


def predict_with_iad_model(model: dict, relation: dict) -> float:
    """使用透明 JSON 模型预测正类概率。

    参数:
        model: `train_iad_relation_model` 生成的模型字典。
        relation: 待预测关系记录。

    返回:
        正类概率；未训练模型返回 0。
    """
    if not model.get("trained"):
        return 0.0
    feature_fields = list(model["feature_fields"])
    features = _feature_vector(relation, feature_fields)
    means = list(model["feature_means"])
    scales = list(model["feature_scales"])
    coefficients = list(model["coefficients"])
    intercept = float(model["intercept"])
    linear_value = intercept
    for feature_value, mean_value, scale_value, coefficient in zip(features, means, scales, coefficients, strict=True):
        safe_scale = float(scale_value) if float(scale_value) != 0.0 else 1.0
        linear_value += ((feature_value - float(mean_value)) / safe_scale) * float(coefficient)
    return _sigmoid(linear_value)


def write_iad_model_json(model: dict, output_path: str | Path) -> None:
    """写出透明 JSON 模型。

    参数:
        model: 模型字典。
        output_path: 输出路径。

    返回:
        无。
    """
    resolved_path = ensure_parent(output_path)
    resolved_path.write_text(json.dumps(model, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_training_summary(model: dict, model_path: str | Path | None = None) -> dict:
    """构造训练摘要行。

    参数:
        model: 模型字典。
        model_path: 可选模型输出路径。

    返回:
        摘要字典。
    """
    metrics = dict(model.get("training_metrics", {}))
    return {
        "target": model["target"],
        "trained": bool(model.get("trained", False)),
        "model_type": model.get("model_type", ""),
        "skip_reason": model.get("skip_reason", ""),
        "model_path": str(model_path or ""),
        **metrics,
    }
