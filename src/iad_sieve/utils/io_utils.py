"""文件读写工具。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, Iterator


LOGGER = logging.getLogger(__name__)


def ensure_parent(path: str | Path) -> Path:
    """确保文件父目录存在。

    参数:
        path: 文件路径。

    返回:
        标准化后的 Path 对象。
    """
    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    return target_path


def ensure_directory(path: str | Path) -> Path:
    """确保目录存在。

    参数:
        path: 目录路径。

    返回:
        标准化后的 Path 对象。
    """
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def read_jsonl(path: str | Path, limit: int | None = None) -> Iterator[dict]:
    """流式读取 JSONL 文件。

    参数:
        path: JSONL 文件路径。
        limit: 最多读取的记录数。

    返回:
        字典记录迭代器。
    """
    try:
        with Path(path).open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if limit is not None and line_number > limit:
                    break
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    yield json.loads(stripped)
                except json.JSONDecodeError:
                    LOGGER.exception("JSONL 解析失败: path=%s line=%s", path, line_number)
                    continue
    except OSError:
        LOGGER.exception("读取 JSONL 文件失败: %s", path)
        raise


def write_jsonl(records: Iterable[dict], path: str | Path) -> int:
    """写入 JSONL 文件。

    参数:
        records: 待写入记录。
        path: 输出路径。

    返回:
        写入记录数。
    """
    output_path = ensure_parent(path)
    count = 0
    try:
        with output_path.open("w", encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                count += 1
    except OSError:
        LOGGER.exception("写入 JSONL 文件失败: %s", path)
        raise
    return count


def read_records(path: str | Path, limit: int | None = None) -> list[dict]:
    """读取 JSONL 或 Parquet 记录。

    参数:
        path: 输入文件路径。
        limit: 最多读取记录数。

    返回:
        记录列表。
    """
    input_path = Path(path)
    try:
        if input_path.suffix == ".parquet":
            import pandas as pd  # type: ignore

            frame = pd.read_parquet(input_path)
            if limit is not None:
                frame = frame.head(limit)
            return frame.to_dict(orient="records")
        return list(read_jsonl(input_path, limit=limit))
    except Exception:
        LOGGER.exception("读取记录失败: %s", path)
        raise


def write_records(records: Iterable[dict], path: str | Path) -> int:
    """写入 JSONL 或 Parquet 记录。

    参数:
        records: 待写入记录。
        path: 输出文件路径。

    返回:
        写入记录数。
    """
    output_path = ensure_parent(path)
    record_list = list(records)
    try:
        if output_path.suffix == ".parquet":
            import pandas as pd  # type: ignore

            pd.DataFrame(record_list).to_parquet(output_path, index=False)
            return len(record_list)
        return write_jsonl(record_list, output_path)
    except Exception:
        LOGGER.exception("写入记录失败: %s", path)
        raise
