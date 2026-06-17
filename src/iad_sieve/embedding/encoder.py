"""文本 embedding 编码模块。"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import Iterable

from iad_sieve.utils.text_similarity import tokenize


LOGGER = logging.getLogger(__name__)


def _hashing_vector(text: str, dimension: int = 128) -> list[float]:
    """生成确定性 hashing 向量。

    参数:
        text: 输入文本。
        dimension: 向量维度。

    返回:
        归一化向量。
    """
    vector = [0.0] * dimension
    for token in tokenize(text):
        digest = hashlib.sha1(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def build_embedding_text(record: dict) -> str:
    """拼接文献 embedding 文本。

    参数:
        record: 文献记录。

    返回:
        用于编码的文本。
    """
    title = record.get("title_normalized") or record.get("title", "")
    abstract = record.get("abstract_normalized") or record.get("abstract", "")
    return f"{title}. {abstract}".strip()


def _normalize_vector(vector: list[float]) -> list[float]:
    """归一化向量。

    参数:
        vector: 原始向量。

    返回:
        L2 归一化向量；零向量原样返回。
    """
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def _encode_with_sentence_transformers(texts: list[str], model_name: str, batch_size: int) -> tuple[list[list[float]], dict]:
    """使用 sentence-transformers 编码文本。

    参数:
        texts: 输入文本列表。
        model_name: 模型名。
        batch_size: 批大小。

    返回:
        embedding 列表和元数据。
    """
    from sentence_transformers import SentenceTransformer  # type: ignore

    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
    embedding_list = embeddings.tolist()
    return embedding_list, {
        "embedding_model": model_name,
        "embedding_dim": len(embedding_list[0]) if embedding_list else 0,
        "embedding_version": "sentence-transformers",
        "device": str(getattr(model, "device", "")),
    }


def _pool_transformer_hidden_state(last_hidden_state, attention_mask, pooling_strategy: str):
    """池化 transformers hidden state。

    参数:
        last_hidden_state: 模型最后一层 hidden state。
        attention_mask: attention mask。
        pooling_strategy: `cls` 或 `mean`。

    返回:
        池化后的张量。
    """
    if pooling_strategy == "cls":
        return last_hidden_state[:, 0]
    if pooling_strategy != "mean":
        raise ValueError(f"不支持的 pooling_strategy: {pooling_strategy}")
    import torch  # type: ignore

    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    summed = torch.sum(last_hidden_state * mask, dim=1)
    counts = torch.clamp(mask.sum(dim=1), min=1e-9)
    return summed / counts


def _encode_with_transformers(
    texts: list[str],
    model_name: str,
    batch_size: int,
    pooling_strategy: str,
) -> tuple[list[list[float]], dict]:
    """使用 transformers feature-extraction 模型编码文本。

    参数:
        texts: 输入文本列表。
        model_name: 模型名。
        batch_size: 批大小。
        pooling_strategy: `cls` 或 `mean`。

    返回:
        embedding 列表和元数据。
    """
    import torch  # type: ignore
    from transformers import AutoModel, AutoTokenizer  # type: ignore

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    embeddings: list[list[float]] = []
    with torch.no_grad():
        for start_index in range(0, len(texts), batch_size):
            batch_texts = texts[start_index : start_index + batch_size]
            encoded = tokenizer(batch_texts, padding=True, truncation=True, return_tensors="pt", max_length=512)
            encoded = {name: value.to(device) for name, value in encoded.items()}
            outputs = model(**encoded)
            pooled = _pool_transformer_hidden_state(outputs.last_hidden_state, encoded["attention_mask"], pooling_strategy)
            for vector in pooled.detach().cpu().tolist():
                embeddings.append(_normalize_vector([float(value) for value in vector]))
    return embeddings, {
        "embedding_model": model_name,
        "embedding_dim": len(embeddings[0]) if embeddings else 0,
        "embedding_version": "transformers",
        "pooling_strategy": pooling_strategy,
        "device": str(device),
    }


def _encode_with_specter2_adapter(
    texts: list[str],
    base_model_name: str,
    adapter_model_name: str,
    batch_size: int,
    pooling_strategy: str,
) -> tuple[list[list[float]], dict]:
    """使用 SPECTER2 adapter 编码文本。

    参数:
        texts: 输入文本列表。
        base_model_name: SPECTER2 base 模型名。
        adapter_model_name: SPECTER2 adapter 模型名。
        batch_size: 批大小。
        pooling_strategy: `cls` 或 `mean`。

    返回:
        embedding 列表和元数据。
    """
    import torch  # type: ignore
    from adapters import AutoAdapterModel  # type: ignore
    from transformers import AutoTokenizer  # type: ignore

    tokenizer = AutoTokenizer.from_pretrained(base_model_name)
    model = AutoAdapterModel.from_pretrained(base_model_name)
    model.load_adapter(adapter_model_name, source="hf", load_as="specter2", set_active=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    embeddings: list[list[float]] = []
    with torch.no_grad():
        for start_index in range(0, len(texts), batch_size):
            batch_texts = texts[start_index : start_index + batch_size]
            encoded = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                return_tensors="pt",
                return_token_type_ids=False,
                max_length=512,
            )
            encoded = {name: value.to(device) for name, value in encoded.items()}
            outputs = model(**encoded)
            pooled = _pool_transformer_hidden_state(outputs.last_hidden_state, encoded["attention_mask"], pooling_strategy)
            for vector in pooled.detach().cpu().tolist():
                embeddings.append(_normalize_vector([float(value) for value in vector]))
    return embeddings, {
        "embedding_model": base_model_name,
        "adapter_model": adapter_model_name,
        "embedding_dim": len(embeddings[0]) if embeddings else 0,
        "embedding_version": "specter2-adapter",
        "pooling_strategy": pooling_strategy,
        "device": str(device),
    }


def encode_documents(
    records: Iterable[dict],
    model_name: str = "hashing-fallback",
    batch_size: int = 32,
    dimension: int = 128,
    model_backend: str = "auto",
    pooling_strategy: str = "cls",
    adapter_model: str | None = None,
) -> tuple[list[str], list[list[float]], dict]:
    """编码文献向量。

    参数:
        records: 文献记录。
        model_name: sentence-transformers 或 transformers 模型名；auto 后端失败时使用 hashing fallback。
        batch_size: 批大小。
        dimension: fallback 向量维度。
        model_backend: `auto`、`sentence-transformers`、`transformers`、`specter2-adapter` 或 `hashing`。
        pooling_strategy: transformers 后端池化策略。
        adapter_model: SPECTER2 adapter 模型名。

    返回:
        document_id 列表、embedding 列表和元数据。
    """
    record_list = list(records)
    document_ids = [record["document_id"] for record in record_list]
    texts = [build_embedding_text(record) for record in record_list]
    if model_backend not in {"auto", "sentence-transformers", "transformers", "specter2-adapter", "hashing"}:
        raise ValueError(f"不支持的 model_backend: {model_backend}")
    if model_backend == "hashing" or model_name == "hashing-fallback":
        embeddings = [_hashing_vector(text, dimension=dimension) for text in texts]
        return document_ids, embeddings, {
            "embedding_model": "hashing-fallback",
            "embedding_dim": dimension,
            "embedding_version": "deterministic-hash-v1",
        }
    if model_backend in {"auto", "sentence-transformers"}:
        try:
            embeddings, metadata = _encode_with_sentence_transformers(texts, model_name, batch_size)
            return document_ids, embeddings, metadata
        except Exception as exc:  # noqa: BLE001
            if model_backend == "sentence-transformers":
                raise RuntimeError(f"sentence-transformers 编码失败: {model_name}: {exc}") from exc
            else:
                LOGGER.warning("sentence-transformers 编码失败，尝试 transformers 后端: %s", exc)
    if model_backend in {"auto", "transformers"}:
        try:
            embeddings, metadata = _encode_with_transformers(texts, model_name, batch_size, pooling_strategy)
            return document_ids, embeddings, metadata
        except Exception as exc:  # noqa: BLE001
            if model_backend == "transformers":
                raise RuntimeError(f"transformers 编码失败: {model_name}: {exc}") from exc
            LOGGER.warning("transformers 编码失败，改用 hashing fallback: %s", exc)
    if model_backend == "specter2-adapter":
        active_adapter_model = adapter_model or "allenai/specter2"
        try:
            embeddings, metadata = _encode_with_specter2_adapter(texts, model_name, active_adapter_model, batch_size, pooling_strategy)
            return document_ids, embeddings, metadata
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"SPECTER2 adapter 编码失败: base={model_name} adapter={active_adapter_model}: {exc}") from exc
    embeddings = [_hashing_vector(text, dimension=dimension) for text in texts]
    return document_ids, embeddings, {
        "embedding_model": "hashing-fallback",
        "embedding_dim": dimension,
        "embedding_version": "deterministic-hash-v1",
    }
