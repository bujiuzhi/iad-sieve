"""向量索引构建模块。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory


LOGGER = logging.getLogger(__name__)


def build_vector_index(embeddings: list[list[float]], output_dir: str | Path) -> str:
    """构建向量索引。

    参数:
        embeddings: 文献向量列表。
        output_dir: 输出目录。

    返回:
        索引文件路径。
    """
    directory = ensure_directory(output_dir)
    index_path = directory / "faiss.index"
    try:
        import faiss  # type: ignore
        import numpy as np  # type: ignore

        array = np.array(embeddings, dtype="float32")
        if len(array.shape) != 2:
            raise ValueError("embedding 必须是二维数组")
        index = faiss.IndexFlatIP(array.shape[1])
        index.add(array)
        faiss.write_index(index, str(index_path))
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("FAISS 不可用，写入 brute-force 索引元数据: %s", exc)
        index_path.write_text(
            json.dumps({"index_type": "brute_force", "count": len(embeddings)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return str(index_path)
