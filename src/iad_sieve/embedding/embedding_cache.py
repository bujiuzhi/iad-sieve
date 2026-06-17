"""Embedding 缓存读写模块。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_jsonl, write_jsonl


LOGGER = logging.getLogger(__name__)


def save_embeddings(
    document_ids: list[str],
    embeddings: list[list[float]],
    output_dir: str | Path,
    metadata: dict,
) -> dict[str, str]:
    """保存 embedding 与 ID 映射。

    参数:
        document_ids: 文献 ID 列表。
        embeddings: 向量列表。
        output_dir: 输出目录。
        metadata: embedding 元数据。

    返回:
        输出文件路径字典。
    """
    directory = ensure_directory(output_dir)
    id_path = directory / "embedding_ids.jsonl"
    metadata_path = directory / "embedding_metadata.json"
    write_jsonl(
        (
            {
                "document_id": document_id,
                "embedding_model": metadata.get("embedding_model", ""),
                "embedding_dim": metadata.get("embedding_dim", 0),
                "embedding_version": metadata.get("embedding_version", ""),
            }
            for document_id in document_ids
        ),
        id_path,
    )
    try:
        import numpy as np  # type: ignore

        embedding_path = directory / "embeddings.npy"
        np.save(embedding_path, np.array(embeddings, dtype="float32"))
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("numpy 不可用，使用 JSONL 保存 embedding: %s", exc)
        embedding_path = directory / "embeddings.jsonl"
        write_jsonl(
            ({"document_id": document_id, "embedding": embedding} for document_id, embedding in zip(document_ids, embeddings, strict=True)),
            embedding_path,
        )
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"embeddings": str(embedding_path), "ids": str(id_path), "metadata": str(metadata_path)}


def load_embeddings(input_dir: str | Path) -> tuple[list[str], list[list[float]]]:
    """读取 embedding 缓存。

    参数:
        input_dir: embedding 输出目录。

    返回:
        document_id 列表和 embedding 列表。
    """
    directory = Path(input_dir)
    ids = [record["document_id"] for record in read_jsonl(directory / "embedding_ids.jsonl")]
    npy_path = directory / "embeddings.npy"
    jsonl_path = directory / "embeddings.jsonl"
    try:
        if npy_path.exists():
            import numpy as np  # type: ignore

            return ids, np.load(npy_path).astype("float32").tolist()
        records = list(read_jsonl(jsonl_path))
        return [record["document_id"] for record in records], [record["embedding"] for record in records]
    except Exception:
        LOGGER.exception("读取 embedding 缓存失败: %s", input_dir)
        raise
