"""arXiv 样本抽取模块。"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Iterable

from iad_sieve.data.arxiv_loader import stream_arxiv_metadata
from iad_sieve.utils.io_utils import write_jsonl


LOGGER = logging.getLogger(__name__)


def record_matches_primary_category(record: dict, primary_category: str | None) -> bool:
    """判断记录是否匹配主分类。

    参数:
        record: 文献记录。
        primary_category: 目标主分类，空值表示不过滤。

    返回:
        是否匹配。
    """
    if not primary_category:
        return True
    return record.get("primary_category") == primary_category or primary_category in record.get("categories", [])


def reservoir_sample(records: Iterable[dict], sample_size: int, seed: int) -> list[dict]:
    """对记录流执行蓄水池抽样。

    参数:
        records: 输入记录流。
        sample_size: 样本数量。
        seed: 随机种子。

    返回:
        抽样记录列表。
    """
    if sample_size <= 0:
        raise ValueError("sample_size 必须大于 0")
    rng = random.Random(seed)
    sample: list[dict] = []
    for index, record in enumerate(records):
        if index < sample_size:
            sample.append(record)
            continue
        replacement_index = rng.randint(0, index)
        if replacement_index < sample_size:
            sample[replacement_index] = record
    return sample


def prepare_sample(
    input_path: str | Path,
    output_path: str | Path,
    sample_size: int,
    seed: int,
    primary_category: str | None = None,
    limit: int | None = None,
) -> int:
    """读取 arXiv metadata 并输出抽样 JSONL。

    参数:
        input_path: 输入 arXiv metadata 文件。
        output_path: 输出 JSONL 文件。
        sample_size: 抽样数量。
        seed: 随机种子。
        primary_category: 可选主分类过滤。
        limit: 最多读取原始记录数。

    返回:
        输出记录数。
    """
    try:
        filtered_records = (
            record
            for record in stream_arxiv_metadata(input_path, limit=limit)
            if record_matches_primary_category(record, primary_category)
        )
        sampled_records = reservoir_sample(filtered_records, sample_size=sample_size, seed=seed)
        return write_jsonl(sampled_records, output_path)
    except Exception:
        LOGGER.exception("准备样本失败")
        raise
