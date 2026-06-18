"""IAD-Risk Transformer 双空间风险模型模块。"""

from __future__ import annotations

import json
import logging
import math
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

from iad_sieve.embedding.encoder import encode_documents
from iad_sieve.evaluation.baseline_runner import calculate_binary_metrics
from iad_sieve.evaluation.iad_classifier import predict_with_iad_model, train_iad_relation_model
from iad_sieve.evaluation.iad_risk_model import REQUIRED_HEADS
from iad_sieve.utils.io_utils import ensure_directory, write_records


LOGGER = logging.getLogger(__name__)
TRANSFORMER_IDENTITY_FEATURE_FIELDS = [
    "transformer_cosine",
    "transformer_l1_mean",
    "transformer_l2_distance",
    "transformer_absdiff_max",
    "title_similarity",
    "author_overlap",
    "first_author_match",
    "venue_similarity",
    "year_match",
    "year_distance_score",
    "same_doi",
    "same_arxiv_id",
    "same_openalex_work_id",
]
TRANSFORMER_AGENDA_FEATURE_FIELDS = [
    "transformer_cosine",
    "title_similarity",
    "venue_similarity",
    "topic_overlap",
    "reference_jaccard",
    "year_distance_score",
]
TRANSFORMER_RISK_FEATURE_FIELDS = [
    "transformer_cosine",
    "transformer_l1_mean",
    "transformer_l2_distance",
    "transformer_absdiff_max",
    "title_similarity",
    "author_overlap",
    "venue_similarity",
    "topic_overlap",
    "reference_jaccard",
    "year_conflict",
    "same_doi",
    "same_arxiv_id",
    "same_openalex_work_id",
    "different_identifier",
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
]


def _normalize_text(value: object) -> str:
    """归一化文本。

    参数:
        value: 原始文本、列表或空值。

    返回:
        小写并压缩空白后的文本。
    """
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return " ".join(str(value).lower().split())


def _text_similarity(left_value: object, right_value: object) -> float:
    """计算两个文本字段的字符相似度。

    参数:
        left_value: 左侧文本。
        right_value: 右侧文本。

    返回:
        0 到 1 的相似度。
    """
    left_text = _normalize_text(left_value)
    right_text = _normalize_text(right_value)
    if not left_text or not right_text:
        return 0.0
    if left_text == right_text:
        return 1.0
    return SequenceMatcher(None, left_text, right_text).ratio()


def _as_list(value: object) -> list[str]:
    """将字段转为字符串列表。

    参数:
        value: 原始字段值。

    返回:
        字符串列表。
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _author_tokens(value: object) -> set[str]:
    """提取作者 token 集合。

    参数:
        value: authors 字段。

    返回:
        作者 token 集合。
    """
    tokens: set[str] = set()
    for item in _as_list(value):
        for part in item.replace(";", ",").split(","):
            normalized = _normalize_text(part)
            if normalized:
                tokens.add(normalized)
    return tokens


def _jaccard(left_values: Iterable[str], right_values: Iterable[str]) -> float:
    """计算 Jaccard 相似度。

    参数:
        left_values: 左侧集合元素。
        right_values: 右侧集合元素。

    返回:
        0 到 1 的 Jaccard 相似度。
    """
    left_set = {_normalize_text(value) for value in left_values if _normalize_text(value)}
    right_set = {_normalize_text(value) for value in right_values if _normalize_text(value)}
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _first_author(value: object) -> str:
    """读取第一作者。

    参数:
        value: authors 字段。

    返回:
        第一作者归一化文本。
    """
    tokens = sorted(_author_tokens(value))
    return tokens[0] if tokens else ""


def _safe_year(value: object) -> int | None:
    """安全读取年份。

    参数:
        value: 年份字段。

    返回:
        整数年份；失败返回 None。
    """
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        LOGGER.warning("年份字段无法转为整数: %r", value)
        return None


def _same_nonempty(left_value: object, right_value: object) -> float:
    """判断两个非空标识符是否相同。

    参数:
        left_value: 左侧标识符。
        right_value: 右侧标识符。

    返回:
        相同返回 1，否则返回 0。
    """
    left_text = _normalize_text(left_value)
    right_text = _normalize_text(right_value)
    return 1.0 if left_text and right_text and left_text == right_text else 0.0


def _different_identifier(left_document: dict, right_document: dict) -> float:
    """判断是否存在明确不同的身份标识符。

    参数:
        left_document: 左侧文献。
        right_document: 右侧文献。

    返回:
        存在同类非空但不同的 DOI、arXiv ID 或 OpenAlex Work ID 时返回 1。
    """
    for field in ["doi", "arxiv_id", "openalex_work_id"]:
        left_value = _normalize_text(left_document.get(field))
        right_value = _normalize_text(right_document.get(field))
        if left_value and right_value and left_value != right_value:
            return 1.0
    return 0.0


def _cosine_similarity(left_vector: list[float], right_vector: list[float]) -> float:
    """计算向量余弦相似度。

    参数:
        left_vector: 左侧向量。
        right_vector: 右侧向量。

    返回:
        余弦相似度。
    """
    if not left_vector or not right_vector or len(left_vector) != len(right_vector):
        return 0.0
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left_vector, right_vector, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left_vector))
    right_norm = math.sqrt(sum(value * value for value in right_vector))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def _embedding_distance_features(left_vector: list[float], right_vector: list[float]) -> dict:
    """构造 embedding 距离特征。

    参数:
        left_vector: 左侧 embedding。
        right_vector: 右侧 embedding。

    返回:
        余弦、L1、L2 和最大绝对差特征。
    """
    if not left_vector or not right_vector or len(left_vector) != len(right_vector):
        return {
            "transformer_cosine": 0.0,
            "transformer_l1_mean": 1.0,
            "transformer_l2_distance": 1.0,
            "transformer_absdiff_max": 1.0,
        }
    differences = [abs(left_value - right_value) for left_value, right_value in zip(left_vector, right_vector, strict=True)]
    return {
        "transformer_cosine": round(_cosine_similarity(left_vector, right_vector), 6),
        "transformer_l1_mean": round(sum(differences) / len(differences), 6),
        "transformer_l2_distance": round(math.sqrt(sum(value * value for value in differences)), 6),
        "transformer_absdiff_max": round(max(differences), 6),
    }


def _pair_document_features(left_document: dict, right_document: dict) -> dict:
    """构造不依赖标签来源的文献 pair 特征。

    参数:
        left_document: 左侧文献。
        right_document: 右侧文献。

    返回:
        标题、作者、标识符、主题和引用特征。
    """
    left_authors = _author_tokens(left_document.get("authors"))
    right_authors = _author_tokens(right_document.get("authors"))
    left_year = _safe_year(left_document.get("year"))
    right_year = _safe_year(right_document.get("year"))
    year_gap = abs(left_year - right_year) if left_year is not None and right_year is not None else None
    first_left_author = _first_author(left_document.get("authors"))
    first_right_author = _first_author(right_document.get("authors"))
    return {
        "title_similarity": round(_text_similarity(left_document.get("title"), right_document.get("title")), 6),
        "author_overlap": round(len(left_authors & right_authors) / len(left_authors | right_authors), 6) if left_authors and right_authors else 0.0,
        "first_author_match": 1.0 if first_left_author and first_left_author == first_right_author else 0.0,
        "venue_similarity": round(_text_similarity(left_document.get("venue"), right_document.get("venue")), 6),
        "year_match": 1.0 if year_gap == 0 else 0.0,
        "year_distance_score": round(1.0 / (1.0 + year_gap), 6) if year_gap is not None else 0.0,
        "year_conflict": 1.0 if year_gap is not None and year_gap > 1 else 0.0,
        "same_doi": _same_nonempty(left_document.get("doi"), right_document.get("doi")),
        "same_arxiv_id": _same_nonempty(left_document.get("arxiv_id"), right_document.get("arxiv_id")),
        "same_openalex_work_id": _same_nonempty(left_document.get("openalex_work_id"), right_document.get("openalex_work_id")),
        "different_identifier": _different_identifier(left_document, right_document),
        "topic_overlap": round(_jaccard(_as_list(left_document.get("topics")), _as_list(right_document.get("topics"))), 6),
        "reference_jaccard": round(_jaccard(_as_list(left_document.get("references")), _as_list(right_document.get("references"))), 6),
    }


def build_transformer_pair_features(
    documents: list[dict],
    relations: list[dict],
    embedding_model: str = "hashing-fallback",
    adapter_model: str | None = None,
    model_backend: str = "auto",
    batch_size: int = 32,
    pooling_strategy: str = "cls",
) -> tuple[list[dict], dict]:
    """使用冻结 Transformer 或 hashing fallback 构造 pair 特征。

    参数:
        documents: 文献记录列表。
        relations: IAD-Bench pair 记录。
        embedding_model: 编码模型名。
        adapter_model: SPECTER2 adapter 模型名。
        model_backend: `auto`、`sentence-transformers`、`transformers` 或 `hashing`。
        batch_size: 编码批大小。
        pooling_strategy: transformers 后端池化策略。

    返回:
        增强后的关系记录和 embedding 元数据。
    """
    document_ids, embeddings, metadata = encode_documents(
        documents,
        model_name=embedding_model,
        batch_size=batch_size,
        model_backend=model_backend,
        pooling_strategy=pooling_strategy,
        adapter_model=adapter_model,
    )
    document_lookup = {str(document.get("document_id", "")): document for document in documents}
    embedding_lookup = dict(zip(document_ids, embeddings, strict=True))
    augmented_relations: list[dict] = []
    missing_pair_count = 0
    for relation in relations:
        source_document_id = str(relation.get("source_document_id", ""))
        target_document_id = str(relation.get("target_document_id", ""))
        left_document = document_lookup.get(source_document_id)
        right_document = document_lookup.get(target_document_id)
        left_embedding = embedding_lookup.get(source_document_id)
        right_embedding = embedding_lookup.get(target_document_id)
        if left_document is None or right_document is None or left_embedding is None or right_embedding is None:
            missing_pair_count += 1
            LOGGER.warning("IAD-Risk Transformer 跳过缺失文献或 embedding 的 pair: %s", relation)
            continue
        augmented = dict(relation)
        augmented.update(_embedding_distance_features(left_embedding, right_embedding))
        augmented.update(_pair_document_features(left_document, right_document))
        augmented_relations.append(augmented)
    metadata = dict(metadata)
    metadata["document_count"] = len(documents)
    metadata["pair_count"] = len(augmented_relations)
    metadata["missing_pair_count"] = missing_pair_count
    return augmented_relations, metadata


def _training_subset(relations: list[dict], train_split: str | None) -> list[dict]:
    """读取训练 split。

    参数:
        relations: 增强后的关系记录。
        train_split: 训练 split 名称；为空时使用全部记录。

    返回:
        训练关系记录。
    """
    if not train_split:
        return relations
    subset = [relation for relation in relations if str(relation.get("split", "")) == train_split]
    return subset or relations


def _execution_mode(metadata: dict, requested_model: str) -> str:
    """根据编码元数据判断执行模式。

    参数:
        metadata: embedding 元数据。
        requested_model: 请求模型名。

    返回:
        actual_model 或 fallback。
    """
    if metadata.get("embedding_version") in {"sentence-transformers", "transformers", "specter2-adapter"} and metadata.get("embedding_model") == requested_model:
        return "actual_model"
    return "fallback"


def train_iad_risk_transformer_model(
    documents: list[dict],
    relations: list[dict],
    extra_train_relations: list[dict] | None = None,
    system_name: str = "iad_risk_transformer",
    embedding_model: str = "hashing-fallback",
    adapter_model: str | None = None,
    model_backend: str = "auto",
    batch_size: int = 32,
    pooling_strategy: str = "cls",
    train_split: str | None = "train",
    random_seed: int = 42,
    work_threshold: float = 0.5,
    agenda_block_threshold: float = 0.5,
    risk_threshold: float = 0.5,
) -> tuple[dict, list[dict]]:
    """训练 IAD-Risk Transformer 双空间风险模型。

    参数:
        documents: IAD-Bench 文献记录。
        relations: 用于预测和评估的 IAD-Bench pair 记录。
        extra_train_relations: 只参与训练、不进入预测输出的额外 pair 记录。
        system_name: 输出摘要中的系统名称。
        embedding_model: 冻结编码模型名。
        adapter_model: SPECTER2 adapter 模型名。
        model_backend: embedding 后端。
        batch_size: 编码批大小。
        pooling_strategy: transformers 池化策略。
        train_split: 训练 split 名称；为空则全量训练。
        random_seed: 随机种子。
        work_threshold: same_work 合并阈值。
        agenda_block_threshold: agenda_non_identity 阻断阈值。
        risk_threshold: false_merge_risk 阻断阈值。

    返回:
        模型字典与增强后的关系记录。
    """
    scoped_relations = [{**relation, "__iad_relation_scope": "eval"} for relation in relations]
    for relation in extra_train_relations or []:
        scoped_relation = {**relation, "__iad_relation_scope": "extra_train"}
        if train_split and "split" not in scoped_relation:
            scoped_relation["split"] = train_split
        scoped_relations.append(scoped_relation)
    augmented_relations, encoder_metadata = build_transformer_pair_features(
        documents=documents,
        relations=scoped_relations,
        embedding_model=embedding_model,
        adapter_model=adapter_model,
        model_backend=model_backend,
        batch_size=batch_size,
        pooling_strategy=pooling_strategy,
    )
    eval_relations = [relation for relation in augmented_relations if relation.get("__iad_relation_scope") == "eval"]
    training_relations = _training_subset(augmented_relations, train_split)
    same_work_head = train_iad_relation_model(
        training_relations,
        target="same_work",
        feature_fields=TRANSFORMER_IDENTITY_FEATURE_FIELDS,
        random_seed=random_seed,
    )
    same_agenda_head = train_iad_relation_model(
        training_relations,
        target="same_agenda",
        feature_fields=TRANSFORMER_AGENDA_FEATURE_FIELDS,
        random_seed=random_seed,
    )
    agenda_non_identity_head = train_iad_relation_model(
        training_relations,
        target="agenda_non_identity",
        feature_fields=TRANSFORMER_RISK_FEATURE_FIELDS,
        random_seed=random_seed,
    )
    heads = {
        "same_work": same_work_head,
        "same_agenda": same_agenda_head,
        "agenda_non_identity": agenda_non_identity_head,
    }
    trained_head_count = sum(1 for head in heads.values() if head.get("trained"))
    same_work_trained = bool(heads["same_work"].get("trained"))
    full_risk_trained = all(bool(heads[head_name].get("trained")) for head_name in REQUIRED_HEADS)
    prediction_mode = "full_iad_risk" if full_risk_trained else "identity_only" if same_work_trained else "untrained"
    model = {
        "trained": same_work_trained,
        "full_risk_trained": full_risk_trained,
        "prediction_mode": prediction_mode,
        "trained_head_count": trained_head_count,
        "required_head_count": len(REQUIRED_HEADS),
        "model_type": "iad_risk_transformer_frozen_encoder_centroid_model",
        "system_name": system_name,
        "random_seed": random_seed,
        "train_split": train_split or "all",
        "train_pair_count": len(training_relations),
        "eval_pair_count": len(eval_relations),
        "extra_train_pair_count": max(0, len(augmented_relations) - len(eval_relations)),
        "heads": heads,
        "encoder": {
            "embedding_model": encoder_metadata.get("embedding_model", embedding_model),
            "adapter_model": encoder_metadata.get("adapter_model", adapter_model or ""),
            "embedding_version": encoder_metadata.get("embedding_version", ""),
            "embedding_dim": encoder_metadata.get("embedding_dim", 0),
            "model_backend": model_backend,
            "pooling_strategy": encoder_metadata.get("pooling_strategy", pooling_strategy),
            "execution_mode": _execution_mode(encoder_metadata, embedding_model),
            "device": encoder_metadata.get("device", ""),
            "document_count": encoder_metadata.get("document_count", 0),
            "pair_count": encoder_metadata.get("pair_count", 0),
            "missing_pair_count": encoder_metadata.get("missing_pair_count", 0),
        },
        "feature_groups": {
            "identity_space": TRANSFORMER_IDENTITY_FEATURE_FIELDS,
            "agenda_space": TRANSFORMER_AGENDA_FEATURE_FIELDS,
            "risk_space": TRANSFORMER_RISK_FEATURE_FIELDS,
        },
        "merge_policy": {
            "work_threshold": work_threshold,
            "agenda_block_threshold": agenda_block_threshold,
            "risk_threshold": risk_threshold,
        },
    }
    LOGGER.info(
        "IAD-Risk Transformer 模型训练完成: trained=%s mode=%s train_pairs=%s eval_pairs=%s encoder=%s",
        same_work_trained,
        prediction_mode,
        len(training_relations),
        len(augmented_relations),
        model["encoder"],
    )
    return model, eval_relations


def predict_with_iad_risk_transformer_model(model: dict, relation: dict) -> dict:
    """使用 IAD-Risk Transformer 模型预测 pair 风险。

    参数:
        model: `train_iad_risk_transformer_model` 生成的模型。
        relation: 带 Transformer 特征的关系记录。

    返回:
        概率与合并决策。
    """
    heads = model.get("heads", {})
    if not model.get("trained") or not bool(heads.get("same_work", {}).get("trained")):
        return {
            "p_same_work": 0.0,
            "p_same_agenda": 0.0,
            "p_agenda_non_identity": 0.0,
            "p_false_merge_risk": 1.0,
            "merge_prediction": 0,
        }
    p_same_work = predict_with_iad_model(heads["same_work"], relation)
    p_same_agenda = predict_with_iad_model(heads["same_agenda"], relation) if heads.get("same_agenda", {}).get("trained") else 0.0
    p_agenda_non_identity = (
        predict_with_iad_model(heads["agenda_non_identity"], relation)
        if heads.get("agenda_non_identity", {}).get("trained")
        else 0.0
    )
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


def _summary_for_scope(model: dict, prediction_rows: list[dict], eval_split: str) -> dict:
    """构造指定 split 的摘要记录。

    参数:
        model: IAD-Risk Transformer 模型。
        prediction_rows: 预测记录。
        eval_split: `all`、`train`、`dev` 或 `test`。

    返回:
        RQ 报告可读取的摘要记录。
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
    merge_predictions = [int(row.get("merge_prediction", 0) or 0) for row in active_rows]
    merge_metrics = calculate_binary_metrics(same_work_labels, merge_predictions) if active_rows else {}
    encoder = model.get("encoder", {})
    return {
        "evidence_layer": "iad_risk_model",
        "system": model.get("system_name", "iad_risk_transformer"),
        "metric_target": "transformer_dual_space_risk_model",
        "eval_split": eval_split,
        "trained": bool(model.get("trained", False)),
        "full_risk_trained": bool(model.get("full_risk_trained", False)),
        "prediction_mode": model.get("prediction_mode", ""),
        "model_type": model.get("model_type", ""),
        "head_count": len(model.get("heads", {})),
        "trained_head_count": int(model.get("trained_head_count", 0)),
        "required_head_count": int(model.get("required_head_count", len(REQUIRED_HEADS))),
        "agenda_non_identity_head_trained": bool(model.get("heads", {}).get("agenda_non_identity", {}).get("trained", False)),
        "train_pair_count": int(model.get("train_pair_count", 0)),
        "eval_pair_count": len(active_rows),
        "weak_label_count": len(active_rows),
        "embedding_model": encoder.get("embedding_model", ""),
        "adapter_model": encoder.get("adapter_model", ""),
        "embedding_version": encoder.get("embedding_version", ""),
        "embedding_dim": encoder.get("embedding_dim", 0),
        "model_backend": encoder.get("model_backend", ""),
        "pooling_strategy": encoder.get("pooling_strategy", ""),
        "execution_mode": encoder.get("execution_mode", ""),
        "device": encoder.get("device", ""),
        "same_work_f1": round(_binary_f1(same_work_labels, same_work_predictions), 6),
        "same_agenda_f1": round(_binary_f1(same_agenda_labels, same_agenda_predictions), 6),
        "agenda_non_identity_f1": round(_binary_f1(agenda_non_identity_labels, agenda_non_identity_predictions), 6),
        "precision": merge_metrics.get("precision", 0.0),
        "recall": merge_metrics.get("recall", 0.0),
        "f1": merge_metrics.get("f1", 0.0),
        "false_merge_rate": merge_metrics.get("false_merge_rate", 0.0),
    }


def _prediction_metadata(relation: dict) -> dict:
    """复制预测记录中的 provenance 元数据。

    参数:
        relation: 增强后的关系记录。

    返回:
        元数据字段。
    """
    return {field: relation.get(field, "") for field in PREDICTION_METADATA_FIELDS if field in relation}


def _prediction_rows(model: dict, relations: list[dict]) -> list[dict]:
    """构造 IAD-Risk Transformer 预测记录。

    参数:
        model: IAD-Risk Transformer 模型。
        relations: 增强后的关系记录。

    返回:
        预测记录列表。
    """
    rows: list[dict] = []
    merge_policy = model.get("merge_policy", {})
    for relation in relations:
        prediction = predict_with_iad_risk_transformer_model(model, relation)
        rows.append(
            {
                "system": model.get("system_name", "iad_risk_transformer"),
                "source_document_id": relation.get("source_document_id", ""),
                "target_document_id": relation.get("target_document_id", ""),
                "expected_label": relation.get("expected_label", ""),
                "expected_agenda_label": relation.get("expected_agenda_label", ""),
                **_prediction_metadata(relation),
                "work_threshold": merge_policy.get("work_threshold", 0.5),
                "agenda_block_threshold": merge_policy.get("agenda_block_threshold", 0.5),
                "risk_threshold": merge_policy.get("risk_threshold", 0.5),
                "threshold_source": merge_policy.get("threshold_source", "model_config"),
                **prediction,
            }
        )
    return rows


def write_iad_risk_transformer_outputs(model: dict, relations: list[dict], output_dir: str | Path) -> None:
    """写出 IAD-Risk Transformer 模型、摘要和预测。

    参数:
        model: IAD-Risk Transformer 模型。
        relations: 增强后的关系记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    resolved_output_dir = ensure_directory(output_dir)
    model_path = resolved_output_dir / "iad_risk_transformer_model.json"
    model_path.write_text(json.dumps(model, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    prediction_rows = _prediction_rows(model, relations)
    summary_rows = [_summary_for_scope(model, prediction_rows, split_name) for split_name in ["all", "train", "dev", "test"]]
    write_records(summary_rows, resolved_output_dir / "iad_risk_transformer_summary.jsonl")
    write_records(prediction_rows, resolved_output_dir / "iad_risk_transformer_predictions.jsonl")
