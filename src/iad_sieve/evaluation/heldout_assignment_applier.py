"""held-out split assignment 应用模块。"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)


def _clean(value: object) -> str:
    """清理字符串字段。

    参数:
        value: 原始字段值。

    返回:
        去除多余空白后的字符串。
    """
    return " ".join(str(value or "").split())


def _assignment_by_pair(assignments: list[dict], split_strategy: str) -> dict[str, dict]:
    """按 pair_id 建立指定策略的 assignment 索引。

    参数:
        assignments: held-out assignment 记录。
        split_strategy: 目标 split 策略。

    返回:
        pair_id 到 assignment 的映射。
    """
    selected: dict[str, dict] = {}
    for assignment in assignments:
        if _clean(assignment.get("split_strategy")) != split_strategy:
            continue
        pair_id = _clean(assignment.get("pair_id"))
        if not pair_id:
            continue
        selected[pair_id] = assignment
    return selected


def _build_summary(assigned_pairs: list[dict], assignment_count: int, matched_assignment_count: int, split_strategy: str) -> dict:
    """构建 held-out assignment 应用摘要。

    参数:
        assigned_pairs: 应用 assignment 后的 pair。
        assignment_count: 指定策略 assignment 数量。
        matched_assignment_count: 成功匹配到 pair 的 assignment 数量。
        split_strategy: 目标 split 策略。

    返回:
        摘要记录。
    """
    split_counts = Counter(_clean(pair.get("split")) for pair in assigned_pairs)
    heldout_keys = {_clean(pair.get("heldout_key")) for pair in assigned_pairs if _clean(pair.get("heldout_key"))}
    return {
        "split_strategy": split_strategy,
        "pair_count": len(assigned_pairs),
        "assignment_count": assignment_count,
        "matched_assignment_count": matched_assignment_count,
        "missing_assignment_count": max(0, len(assigned_pairs) - matched_assignment_count),
        "train_pair_count": split_counts.get("train", 0),
        "dev_pair_count": split_counts.get("dev", 0),
        "test_pair_count": split_counts.get("test", 0),
        "heldout_key_count": len(heldout_keys),
    }


def apply_heldout_split_assignments(
    pairs: list[dict],
    assignments: list[dict],
    split_strategy: str,
) -> tuple[list[dict], dict]:
    """把 held-out split assignment 应用到 IAD-Bench pair。

    参数:
        pairs: IAD-Bench pair 记录。
        assignments: held-out split assignment 记录。
        split_strategy: 要应用的 split 策略，如 source_held_out。

    返回:
        应用后的 pair 记录和摘要。
    """
    strategy = _clean(split_strategy)
    if not strategy:
        raise ValueError("split_strategy 不能为空")
    assignments_by_pair = _assignment_by_pair(assignments, strategy)
    assigned_pairs: list[dict] = []
    matched_assignment_count = 0
    for pair in pairs:
        pair_id = _clean(pair.get("pair_id"))
        assigned_pair = dict(pair)
        assignment = assignments_by_pair.get(pair_id)
        if assignment:
            matched_assignment_count += 1
            assigned_pair["original_split"] = _clean(pair.get("split"))
            assigned_pair["split"] = _clean(assignment.get("split")) or _clean(pair.get("split"))
            assigned_pair["evaluation_split_strategy"] = strategy
            assigned_pair["heldout_key"] = _clean(assignment.get("heldout_key"))
            assigned_pair["heldout_assignment_reason"] = _clean(assignment.get("assignment_reason"))
            assigned_pair["heldout_assignment_status"] = "matched"
        else:
            assigned_pair["heldout_assignment_status"] = "missing_assignment"
        assigned_pairs.append(assigned_pair)
    summary = _build_summary(
        assigned_pairs,
        assignment_count=len(assignments_by_pair),
        matched_assignment_count=matched_assignment_count,
        split_strategy=strategy,
    )
    LOGGER.info(
        "held-out assignment 应用完成: strategy=%s pairs=%s matched=%s",
        strategy,
        len(assigned_pairs),
        matched_assignment_count,
    )
    return assigned_pairs, summary


def apply_heldout_split_assignments_from_paths(
    pairs_path: str | Path,
    assignments_path: str | Path,
    split_strategy: str,
) -> tuple[list[dict], dict]:
    """从文件读取并应用 held-out split assignment。

    参数:
        pairs_path: IAD-Bench pair JSONL。
        assignments_path: held-out assignment JSONL。
        split_strategy: 要应用的 split 策略。

    返回:
        应用后的 pair 记录和摘要。
    """
    try:
        pairs = read_records(pairs_path)
        assignments = read_records(assignments_path)
        return apply_heldout_split_assignments(pairs, assignments, split_strategy)
    except Exception:
        LOGGER.exception("读取或应用 held-out assignment 失败: pairs=%s assignments=%s", pairs_path, assignments_path)
        raise


def write_heldout_split_assignment_outputs(assigned_pairs: list[dict], summary: dict, output_dir: str | Path) -> None:
    """写出 held-out assignment 应用产物。

    参数:
        assigned_pairs: 应用后的 pair 记录。
        summary: 摘要记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(assigned_pairs, directory / "iad_bench_pairs.jsonl")
        write_records([summary], directory / "heldout_assignment_summary.jsonl")
    except Exception:
        LOGGER.exception("写出 held-out assignment 应用产物失败: %s", output_dir)
        raise
