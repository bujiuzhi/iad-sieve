"""强 baseline 分数生成模块。"""

from __future__ import annotations

import logging
import math
from pathlib import Path

from iad_sieve.embedding.encoder import encode_documents
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


def _cosine_similarity(left_vector: list[float], right_vector: list[float]) -> float:
    """计算余弦相似度。

    参数:
        left_vector: 左侧向量。
        right_vector: 右侧向量。

    返回:
        余弦相似度，空向量或零范数返回 0。
    """
    if not left_vector or not right_vector or len(left_vector) != len(right_vector):
        return 0.0
    dot_product = sum(left * right for left, right in zip(left_vector, right_vector, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left_vector))
    right_norm = math.sqrt(sum(value * value for value in right_vector))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def _execution_mode(requested_model: str, metadata: dict) -> str:
    """根据编码元数据判断 baseline 执行模式。

    参数:
        requested_model: 用户请求的 embedding 模型。
        metadata: encode_documents 返回的元数据。

    返回:
        actual_model 或 fallback。
    """
    if metadata.get("embedding_version") in {"sentence-transformers", "transformers", "specter2-adapter"} and metadata.get("embedding_model") == requested_model:
        return "actual_model"
    return "fallback"


def run_representation_baseline(
    documents: list[dict],
    pairs: list[dict],
    system_name: str,
    embedding_model: str,
    score_field: str = "score",
    batch_size: int = 32,
    model_backend: str = "auto",
    pooling_strategy: str = "cls",
    adapter_model: str | None = None,
) -> tuple[list[dict], dict]:
    """运行科研表示相似度 baseline。

    参数:
        documents: IAD-Bench 或 eval_documents 文献记录。
        pairs: IAD-Bench 或 eval_pairs 文献对记录。
        system_name: baseline 名称，如 specter2_cosine。
        embedding_model: sentence-transformers 模型名，失败时会回退 hashing。
        score_field: 输出分数字段名。
        batch_size: embedding 批大小。
        model_backend: `auto`、`sentence-transformers`、`transformers` 或 `hashing`。
        pooling_strategy: transformers 后端池化策略。
        adapter_model: SPECTER2 adapter 模型名。

    返回:
        baseline 分数记录列表和执行摘要。
    """
    document_ids, embeddings, metadata = encode_documents(
        documents,
        model_name=embedding_model,
        batch_size=batch_size,
        model_backend=model_backend,
        pooling_strategy=pooling_strategy,
        adapter_model=adapter_model,
    )
    embedding_lookup = dict(zip(document_ids, embeddings, strict=True))
    execution_mode = _execution_mode(embedding_model, metadata)
    rows: list[dict] = []
    missing_pair_count = 0
    seen_pairs: set[tuple[str, str]] = set()
    for pair in pairs:
        source_document_id = str(pair.get("source_document_id", ""))
        target_document_id = str(pair.get("target_document_id", ""))
        key = _pair_key(source_document_id, target_document_id)
        if key in seen_pairs:
            LOGGER.warning("representation baseline 跳过重复 pair: %s", key)
            continue
        seen_pairs.add(key)
        if source_document_id not in embedding_lookup or target_document_id not in embedding_lookup:
            missing_pair_count += 1
            LOGGER.warning("representation baseline pair 引用缺失文献: %s", pair)
            continue
        score = _cosine_similarity(embedding_lookup[source_document_id], embedding_lookup[target_document_id])
        rows.append(
            {
                "source_document_id": source_document_id,
                "target_document_id": target_document_id,
                "system": system_name,
                "baseline_family": "representation",
                "execution_mode": execution_mode,
                "embedding_model": metadata.get("embedding_model", embedding_model),
                "adapter_model": metadata.get("adapter_model", adapter_model or ""),
                "embedding_version": metadata.get("embedding_version", ""),
                "pooling_strategy": metadata.get("pooling_strategy", pooling_strategy),
                "device": metadata.get("device", ""),
                score_field: round(score, 6),
            }
        )
    summary = {
        "system": system_name,
        "baseline_family": "representation",
        "execution_mode": execution_mode,
        "requested_embedding_model": embedding_model,
        "resolved_embedding_model": metadata.get("embedding_model", ""),
        "adapter_model": metadata.get("adapter_model", adapter_model or ""),
        "embedding_version": metadata.get("embedding_version", ""),
        "model_backend": model_backend,
        "pooling_strategy": metadata.get("pooling_strategy", pooling_strategy),
        "device": metadata.get("device", ""),
        "embedding_dim": metadata.get("embedding_dim", 0),
        "score_field": score_field,
        "document_count": len(documents),
        "pair_count": len(rows),
        "missing_pair_count": missing_pair_count,
    }
    LOGGER.info(
        "representation baseline 完成: system=%s execution_mode=%s pairs=%s missing=%s",
        system_name,
        execution_mode,
        len(rows),
        missing_pair_count,
    )
    return rows, summary


def write_baseline_scores(rows: list[dict], summary: dict, output_path: str | Path, summary_path: str | Path) -> None:
    """写出 baseline 分数和执行摘要。

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
