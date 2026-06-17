"""测试 embedding 编码器。"""

from __future__ import annotations

import pytest

from iad_sieve.embedding import encoder
from iad_sieve.embedding.encoder import encode_documents


def _document(document_id: str, title: str) -> dict:
    """构造测试文献。

    参数:
        document_id: 文献 ID。
        title: 文献标题。

    返回:
        文献记录。
    """
    return {"document_id": document_id, "title": title, "abstract": ""}


def test_encode_documents_uses_transformers_backend_when_sentence_transformers_fails(monkeypatch) -> None:
    """验证 sentence-transformers 不适配时可回退到 transformers 后端而非 hashing。"""

    def _raise_sentence_transformer(*args, **kwargs):
        """模拟 sentence-transformers 加载失败。"""
        raise RuntimeError("not a sentence-transformers repo")

    def _fake_transformers_encoder(texts, model_name, batch_size, pooling_strategy):
        """模拟 transformers feature-extraction 编码成功。"""
        return [[1.0, 0.0], [0.0, 1.0]], {
            "embedding_model": model_name,
            "embedding_dim": 2,
            "embedding_version": "transformers",
            "pooling_strategy": pooling_strategy,
            "device": "cuda:0",
        }

    monkeypatch.setattr(encoder, "_encode_with_sentence_transformers", _raise_sentence_transformer)
    monkeypatch.setattr(encoder, "_encode_with_transformers", _fake_transformers_encoder)

    document_ids, embeddings, metadata = encode_documents(
        [_document("d1", "Neural Retrieval"), _document("d2", "Graph Clustering")],
        model_name="allenai/specter2_base",
        model_backend="auto",
        pooling_strategy="cls",
    )

    assert document_ids == ["d1", "d2"]
    assert embeddings == [[1.0, 0.0], [0.0, 1.0]]
    assert metadata["embedding_version"] == "transformers"
    assert metadata["embedding_model"] == "allenai/specter2_base"
    assert metadata["pooling_strategy"] == "cls"
    assert metadata["device"] == "cuda:0"


def test_encode_documents_keeps_sentence_transformer_device_metadata(monkeypatch) -> None:
    """验证 sentence-transformers 后端保留 device metadata。"""

    def _fake_sentence_transformers_encoder(texts, model_name, batch_size):
        """模拟 sentence-transformers 编码成功。"""
        return [[1.0, 0.0]], {
            "embedding_model": model_name,
            "embedding_dim": 2,
            "embedding_version": "sentence-transformers",
            "device": "cuda:0",
        }

    monkeypatch.setattr(encoder, "_encode_with_sentence_transformers", _fake_sentence_transformers_encoder)

    _, embeddings, metadata = encode_documents(
        [_document("d1", "Neural Retrieval")],
        model_name="malteos/scincl",
        model_backend="sentence-transformers",
    )

    assert embeddings == [[1.0, 0.0]]
    assert metadata["embedding_version"] == "sentence-transformers"
    assert metadata["device"] == "cuda:0"


def test_encode_documents_can_force_hashing_backend() -> None:
    """验证显式 hashing backend 不尝试外部模型。"""
    _, embeddings, metadata = encode_documents(
        [_document("d1", "Neural Retrieval")],
        model_name="allenai/specter2_base",
        model_backend="hashing",
    )

    assert len(embeddings) == 1
    assert metadata["embedding_version"] == "deterministic-hash-v1"


def test_encode_documents_raises_when_forced_transformers_backend_fails(monkeypatch) -> None:
    """验证强制 transformers 后端失败时不静默降级。"""

    def _raise_transformers(*args, **kwargs):
        """模拟 transformers 编码失败。"""
        raise RuntimeError("missing tokenizer")

    monkeypatch.setattr(encoder, "_encode_with_transformers", _raise_transformers)

    with pytest.raises(RuntimeError, match="transformers 编码失败"):
        encode_documents(
            [_document("d1", "Neural Retrieval")],
            model_name="allenai/specter2",
            model_backend="transformers",
        )


def test_encode_documents_auto_backend_can_fallback_to_hashing(monkeypatch) -> None:
    """验证 auto 后端在两个外部后端失败后仍可回退 hashing。"""

    def _raise_external(*args, **kwargs):
        """模拟外部编码器失败。"""
        raise RuntimeError("external unavailable")

    monkeypatch.setattr(encoder, "_encode_with_sentence_transformers", _raise_external)
    monkeypatch.setattr(encoder, "_encode_with_transformers", _raise_external)

    _, embeddings, metadata = encode_documents(
        [_document("d1", "Neural Retrieval")],
        model_name="allenai/specter2",
        model_backend="auto",
    )

    assert len(embeddings) == 1
    assert metadata["embedding_version"] == "deterministic-hash-v1"
