"""实体匹配强 baseline 分数生成模块。"""

from __future__ import annotations

import logging
import math
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from iad_sieve.utils.io_utils import write_records


LOGGER = logging.getLogger(__name__)


def _pair_key(source_document_id: object, target_document_id: object) -> tuple[str, str]:
    """构造无向 pair key。

    参数:
        source_document_id: 源文献 ID。
        target_document_id: 目标文献 ID。

    返回:
        排序后的二元组。
    """
    return tuple(sorted((str(source_document_id or ""), str(target_document_id or ""))))


def _normalize_text(value: object) -> str:
    """归一化文本字段。

    参数:
        value: 任意文本、列表或缺失值。

    返回:
        小写、压缩空白后的字符串。
    """
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return " ".join(str(value).lower().split())


def _document_text(record: dict) -> str:
    """构造实体匹配模型输入文本。

    参数:
        record: 文献记录。

    返回:
        串联 title、authors、venue、year、abstract 后的结构化文本。
    """
    fields = {
        "title": record.get("title_normalized") or record.get("title"),
        "authors": record.get("authors_normalized") or record.get("authors"),
        "venue": record.get("venue_normalized") or record.get("venue"),
        "year": record.get("year"),
        "abstract": record.get("abstract_normalized") or record.get("abstract"),
    }
    return " [SEP] ".join(f"{name}: {_normalize_text(value)}" for name, value in fields.items() if _normalize_text(value))


def _text_similarity(left_text: str, right_text: str) -> float:
    """计算文本相似度。

    参数:
        left_text: 左侧文本。
        right_text: 右侧文本。

    返回:
        0 到 1 的相似度。
    """
    if not left_text or not right_text:
        return 0.0
    if left_text == right_text:
        return 1.0
    return SequenceMatcher(None, left_text, right_text).ratio()


def _heuristic_entity_score(left_document: dict, right_document: dict) -> float:
    """计算 fallback 实体匹配分数。

    参数:
        left_document: 左侧文献。
        right_document: 右侧文献。

    返回:
        0 到 1 的启发式匹配概率。
    """
    left_text = _document_text(left_document)
    right_text = _document_text(right_document)
    if left_text and left_text == right_text:
        return 1.0
    title_score = _text_similarity(
        _normalize_text(left_document.get("title_normalized") or left_document.get("title")),
        _normalize_text(right_document.get("title_normalized") or right_document.get("title")),
    )
    abstract_score = _text_similarity(
        _normalize_text(left_document.get("abstract_normalized") or left_document.get("abstract")),
        _normalize_text(right_document.get("abstract_normalized") or right_document.get("abstract")),
    )
    author_score = _text_similarity(
        _normalize_text(left_document.get("authors_normalized") or left_document.get("authors")),
        _normalize_text(right_document.get("authors_normalized") or right_document.get("authors")),
    )
    year_score = 0.0
    if left_document.get("year") and right_document.get("year"):
        year_score = 1.0 if str(left_document.get("year")) == str(right_document.get("year")) else 0.0
    score = 0.62 * title_score + 0.23 * abstract_score + 0.10 * author_score + 0.05 * year_score
    return max(0.0, min(1.0, score))


def _positive_class_index(config: Any, class_count: int) -> int:
    """判断二分类模型的正类下标。

    参数:
        config: transformers 模型 config。
        class_count: logits 类别数量。

    返回:
        正类下标。
    """
    label2id = getattr(config, "label2id", None) or {}
    for label, index in label2id.items():
        normalized_label = str(label).lower()
        if any(keyword in normalized_label for keyword in ("match", "duplicate", "same", "equivalent", "entail")):
            return int(index)
    return 1 if class_count > 1 else 0


def _softmax_probability(values: list[float], positive_index: int) -> float:
    """计算 softmax 正类概率。

    参数:
        values: logits 数值。
        positive_index: 正类下标。

    返回:
        正类概率。
    """
    if not values:
        return 0.0
    max_value = max(values)
    exponents = [math.exp(value - max_value) for value in values]
    denominator = sum(exponents)
    if denominator == 0.0:
        return 0.0
    return exponents[min(positive_index, len(values) - 1)] / denominator


def _score_pairs_with_transformers(text_pairs: list[tuple[str, str]], model_name: str, batch_size: int) -> tuple[list[float], dict]:
    """使用 transformers 序列分类模型计算 pair 分数。

    参数:
        text_pairs: 左右文献文本二元组。
        model_name: Hugging Face 模型名或本地路径。
        batch_size: 推理批大小。

    返回:
        分数列表和模型元数据。
    """
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except Exception as exc:  # pragma: no cover - 依赖缺失场景由集成环境覆盖
        raise RuntimeError(f"transformers sequence classifier 依赖不可用: {exc}") from exc

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        model.eval()
        scores: list[float] = []
        with torch.no_grad():
            for start in range(0, len(text_pairs), batch_size):
                batch_pairs = text_pairs[start : start + batch_size]
                encoded = tokenizer(
                    [left for left, _ in batch_pairs],
                    [right for _, right in batch_pairs],
                    padding=True,
                    truncation=True,
                    return_tensors="pt",
                    max_length=512,
                )
                encoded = {name: value.to(device) for name, value in encoded.items()}
                outputs = model(**encoded)
                logits = outputs.logits.detach().cpu().tolist()
                for row in logits:
                    if len(row) == 1:
                        probability = 1.0 / (1.0 + math.exp(-float(row[0])))
                    else:
                        probability = _softmax_probability([float(value) for value in row], _positive_class_index(model.config, len(row)))
                    scores.append(round(float(probability), 6))
        return scores, {
            "resolved_model_name": model_name,
            "model_version": "transformers-sequence-classification",
            "class_count": int(getattr(model.config, "num_labels", 0) or 0),
            "device": str(device),
        }
    except Exception as exc:
        raise RuntimeError(f"transformers entity matching 模型执行失败: {model_name}: {exc}") from exc


def run_entity_matching_baseline(
    documents: list[dict],
    pairs: list[dict],
    system_name: str,
    model_name: str,
    score_field: str = "score",
    model_backend: str = "auto",
    batch_size: int = 32,
) -> tuple[list[dict], dict]:
    """运行实体匹配 pair classifier baseline。

    参数:
        documents: IAD-Bench 或 eval_documents 文献记录。
        pairs: IAD-Bench 或 eval_pairs 文献对记录。
        system_name: baseline 名称，如 roberta_entity_matcher。
        model_name: Hugging Face 模型名、本地路径或 heuristic-entity-matcher。
        score_field: 输出分数字段名。
        model_backend: `auto`、`transformers` 或 `heuristic`。
        batch_size: 模型推理批大小。

    返回:
        baseline 分数记录列表和执行摘要。
    """
    document_lookup = {str(record.get("document_id", "")): record for record in documents}
    rows: list[dict] = []
    pair_payloads: list[tuple[dict, dict, str, str]] = []
    missing_pair_count = 0
    seen_pairs: set[tuple[str, str]] = set()
    for pair in pairs:
        source_document_id = str(pair.get("source_document_id", ""))
        target_document_id = str(pair.get("target_document_id", ""))
        key = _pair_key(source_document_id, target_document_id)
        if key in seen_pairs:
            LOGGER.warning("entity matching baseline 跳过重复 pair: %s", key)
            continue
        seen_pairs.add(key)
        left_document = document_lookup.get(source_document_id)
        right_document = document_lookup.get(target_document_id)
        if left_document is None or right_document is None:
            missing_pair_count += 1
            LOGGER.warning("entity matching baseline pair 引用缺失文献: %s", pair)
            continue
        pair_payloads.append((left_document, right_document, source_document_id, target_document_id))

    scores: list[float]
    model_metadata: dict = {}
    execution_mode = "fallback"
    if model_backend in {"auto", "transformers"} and pair_payloads:
        text_pairs = [(_document_text(left_document), _document_text(right_document)) for left_document, right_document, _, _ in pair_payloads]
        try:
            scores, model_metadata = _score_pairs_with_transformers(text_pairs, model_name=model_name, batch_size=batch_size)
            execution_mode = "actual_model"
        except RuntimeError as exc:
            LOGGER.warning("entity matching baseline 回退 heuristic: %s", exc)
            scores = [_heuristic_entity_score(left_document, right_document) for left_document, right_document, _, _ in pair_payloads]
            model_metadata = {"fallback_reason": str(exc), "model_version": "heuristic-fallback"}
    else:
        scores = [_heuristic_entity_score(left_document, right_document) for left_document, right_document, _, _ in pair_payloads]
        model_metadata = {"model_version": "heuristic-fallback"}

    for (left_document, right_document, source_document_id, target_document_id), score in zip(pair_payloads, scores, strict=True):
        rows.append(
            {
                "source_document_id": source_document_id,
                "target_document_id": target_document_id,
                "system": system_name,
                "baseline_family": "entity_matching",
                "execution_mode": execution_mode,
                "model_name": model_metadata.get("resolved_model_name", model_name),
                "model_version": model_metadata.get("model_version", ""),
                "device": model_metadata.get("device", ""),
                score_field: round(float(score), 6),
            }
        )

    summary = {
        "system": system_name,
        "baseline_family": "entity_matching",
        "execution_mode": execution_mode,
        "requested_model_name": model_name,
        "resolved_model_name": model_metadata.get("resolved_model_name", model_name),
        "model_version": model_metadata.get("model_version", ""),
        "device": model_metadata.get("device", ""),
        "model_backend": model_backend,
        "score_field": score_field,
        "document_count": len(documents),
        "pair_count": len(rows),
        "missing_pair_count": missing_pair_count,
    }
    if "fallback_reason" in model_metadata:
        summary["fallback_reason"] = model_metadata["fallback_reason"]
    LOGGER.info(
        "entity matching baseline 完成: system=%s execution_mode=%s pairs=%s missing=%s",
        system_name,
        execution_mode,
        len(rows),
        missing_pair_count,
    )
    return rows, summary


def write_entity_matching_scores(rows: list[dict], summary: dict, output_path: str | Path, summary_path: str | Path) -> None:
    """写出实体匹配 baseline 分数和执行摘要。

    参数:
        rows: baseline 分数记录。
        summary: baseline 执行摘要。
        output_path: 分数 JSONL 输出路径。
        summary_path: 摘要 JSONL 输出路径。

    返回:
        无。
    """
    write_records(rows, output_path)
    write_records([summary], summary_path)
