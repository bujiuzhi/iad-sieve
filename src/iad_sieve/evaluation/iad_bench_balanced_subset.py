"""IAD-Bench 公开 gold 平衡子集构建模块。"""

from __future__ import annotations

import csv
import logging
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from iad_sieve.evaluation.iad_bench_builder import DOCUMENT_FIELDS, PAIR_FIELDS
from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)


def _clean(value: object) -> str:
    """清理字符串字段。

    参数:
        value: 原始字段值。

    返回:
        去除多余空白的字符串。
    """
    return " ".join(str(value or "").split())


def _parse_relation_labels(relation_labels: Iterable[str] | str | None) -> list[str]:
    """解析需要配平的关系标签。

    参数:
        relation_labels: 关系标签列表或逗号分隔字符串。

    返回:
        去重后的关系标签列表。
    """
    if relation_labels is None:
        return ["same_work", "unrelated"]
    if isinstance(relation_labels, str):
        raw_labels = relation_labels.split(",")
    else:
        raw_labels = list(relation_labels)
    labels: list[str] = []
    seen: set[str] = set()
    for label in raw_labels:
        cleaned_label = _clean(label)
        if cleaned_label and cleaned_label not in seen:
            labels.append(cleaned_label)
            seen.add(cleaned_label)
    if len(labels) < 2:
        raise ValueError("relation_labels 至少需要两个关系标签")
    return labels


def _parse_label_sources(label_sources: Iterable[str] | str | None) -> list[str]:
    """解析 label_source 过滤参数。

    参数:
        label_sources: label_source 列表、逗号分隔字符串或空值。

    返回:
        去重后的 label_source 列表。
    """
    if label_sources is None:
        return []
    if isinstance(label_sources, str):
        raw_sources = label_sources.split(",")
    else:
        raw_sources = list(label_sources)
    sources: list[str] = []
    seen: set[str] = set()
    for source in raw_sources:
        cleaned_source = _clean(source)
        if cleaned_source and cleaned_source not in seen:
            sources.append(cleaned_source)
            seen.add(cleaned_source)
    return sources


def _filter_pairs_by_label_source(
    pairs: list[dict],
    include_label_sources: Iterable[str] | str | None,
    exclude_label_sources: Iterable[str] | str | None,
) -> tuple[list[dict], list[str], list[str]]:
    """按 label_source 过滤 pair。

    参数:
        pairs: IAD-Bench pair 记录。
        include_label_sources: 允许保留的 label_source；为空时不限制。
        exclude_label_sources: 需要排除的 label_source。

    返回:
        过滤后的 pair、include label_source 列表、exclude label_source 列表。
    """
    include_sources = _parse_label_sources(include_label_sources)
    exclude_sources = _parse_label_sources(exclude_label_sources)
    include_set = set(include_sources)
    exclude_set = set(exclude_sources)
    filtered_pairs = []
    for pair in pairs:
        label_source = _clean(pair.get("label_source"))
        if include_set and label_source not in include_set:
            continue
        if label_source in exclude_set:
            continue
        filtered_pairs.append(pair)
    return filtered_pairs, include_sources, exclude_sources


def _validate_split_ratios(train_ratio: float, dev_ratio: float) -> None:
    """校验 split 比例。

    参数:
        train_ratio: train 比例。
        dev_ratio: dev 比例。

    返回:
        无。
    """
    if train_ratio < 0 or dev_ratio < 0 or train_ratio + dev_ratio > 1:
        raise ValueError("train_ratio 和 dev_ratio 必须非负，且二者之和不能超过 1")


def _group_pairs_by_source_and_relation(pairs: list[dict], relation_labels: list[str]) -> dict[str, dict[str, list[dict]]]:
    """按 label_source 和 relation_label 分组 pair。

    参数:
        pairs: IAD-Bench pair 记录。
        relation_labels: 需要配平的关系标签。

    返回:
        label_source -> relation_label -> pair 列表。
    """
    relation_set = set(relation_labels)
    grouped_pairs: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for pair in pairs:
        relation_label = _clean(pair.get("relation_label"))
        label_source = _clean(pair.get("label_source"))
        if relation_label not in relation_set or not label_source:
            continue
        grouped_pairs[label_source][relation_label].append(pair)
    return grouped_pairs


def _sample_pairs(candidates: list[dict], sample_count: int, rng: random.Random) -> list[dict]:
    """确定性抽样 pair。

    参数:
        candidates: 候选 pair。
        sample_count: 抽样数量。
        rng: 随机数生成器。

    返回:
        被选中的 pair。
    """
    ordered_candidates = sorted(candidates, key=lambda pair: _clean(pair.get("pair_id")))
    if sample_count >= len(ordered_candidates):
        return ordered_candidates
    return sorted(rng.sample(ordered_candidates, sample_count), key=lambda pair: _clean(pair.get("pair_id")))


def _copy_pair(pair: dict, original_pair_id: str) -> dict:
    """复制 pair 并保留原始 pair ID。

    参数:
        pair: 原始 pair。
        original_pair_id: 原始 pair ID。

    返回:
        新 pair 记录。
    """
    copied_pair = dict(pair)
    provenance = dict(copied_pair.get("label_provenance") or {})
    provenance["balanced_subset_source_pair_id"] = original_pair_id
    copied_pair["label_provenance"] = provenance
    copied_pair["source_pair_id"] = _clean(pair.get("source_pair_id")) or original_pair_id
    return copied_pair


def _assign_stratified_splits(pairs: list[dict], seed: int, train_ratio: float, dev_ratio: float) -> None:
    """按来源与关系分层分配 split。

    参数:
        pairs: 平衡后的 pair 列表，会被原地写入 split。
        seed: 随机种子。
        train_ratio: train 比例。
        dev_ratio: dev 比例。

    返回:
        无。
    """
    _validate_split_ratios(train_ratio, dev_ratio)
    grouped_indices: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, pair in enumerate(pairs):
        grouped_indices[(_clean(pair.get("label_source")), _clean(pair.get("relation_label")))].append(index)
    rng = random.Random(seed)
    for group_key in sorted(grouped_indices):
        indices = grouped_indices[group_key]
        rng.shuffle(indices)
        train_count = int(len(indices) * train_ratio)
        dev_count = int(len(indices) * dev_ratio)
        train_indices = set(indices[:train_count])
        dev_indices = set(indices[train_count : train_count + dev_count])
        for index in indices:
            if index in train_indices:
                pairs[index]["split"] = "train"
            elif index in dev_indices:
                pairs[index]["split"] = "dev"
            else:
                pairs[index]["split"] = "test"


def _selected_documents(documents: list[dict], pairs: list[dict]) -> list[dict]:
    """筛选平衡子集涉及的文档。

    参数:
        documents: 原始 IAD-Bench 文档。
        pairs: 平衡后的 pair。

    返回:
        仅包含被选 pair 引用的文档列表。
    """
    required_document_ids = {
        _clean(pair.get("source_document_id"))
        for pair in pairs
    } | {
        _clean(pair.get("target_document_id"))
        for pair in pairs
    }
    documents_by_id = {_clean(document.get("document_id")): document for document in documents}
    missing_document_ids = sorted(document_id for document_id in required_document_ids if document_id not in documents_by_id)
    if missing_document_ids:
        LOGGER.warning("平衡子集存在缺失文档引用: count=%s examples=%s", len(missing_document_ids), missing_document_ids[:5])
    return [documents_by_id[document_id] for document_id in sorted(required_document_ids) if document_id in documents_by_id]


def _build_summary(
    original_pair_count: int,
    filtered_pair_count: int,
    selected_pairs: list[dict],
    selected_documents: list[dict],
    relation_labels: list[str],
    include_label_sources: list[str],
    exclude_label_sources: list[str],
    excluded_source_count: int,
    train_ratio: float,
    dev_ratio: float,
    seed: int,
) -> dict:
    """构造平衡子集摘要。

    参数:
        original_pair_count: 输入 pair 数量。
        filtered_pair_count: label_source 过滤后的 pair 数量。
        selected_pairs: 被选中的 pair。
        selected_documents: 被选中的文档。
        relation_labels: 配平关系标签。
        include_label_sources: 保留的 label_source。
        exclude_label_sources: 排除的 label_source。
        excluded_source_count: 因缺少任一关系而排除的来源数。
        train_ratio: train 比例。
        dev_ratio: dev 比例。
        seed: 随机种子。

    返回:
        摘要记录。
    """
    relation_counts = Counter(_clean(pair.get("relation_label")) for pair in selected_pairs)
    label_source_counts = Counter(_clean(pair.get("label_source")) for pair in selected_pairs)
    label_strength_counts = Counter(_clean(pair.get("label_strength")) for pair in selected_pairs)
    return {
        "evidence_layer": "iad_bench_balanced_gold_subset",
        "system": "iad_bench_balanced_gold_subset",
        "metric_target": "label_provenance_balanced_subset",
        "document_count": len(selected_documents),
        "pair_count": len(selected_pairs),
        "original_pair_count": original_pair_count,
        "filtered_pair_count": filtered_pair_count,
        "filtered_out_pair_count": max(0, original_pair_count - filtered_pair_count),
        "dropped_pair_count": max(0, original_pair_count - len(selected_pairs)),
        "excluded_source_count": excluded_source_count,
        "relation_labels": relation_labels,
        "include_label_sources": include_label_sources,
        "exclude_label_sources": exclude_label_sources,
        "relation_label_counts": dict(sorted(relation_counts.items())),
        "label_source_counts": dict(sorted(label_source_counts.items())),
        "label_strength_counts": dict(sorted(label_strength_counts.items())),
        "gold_pair_count": label_strength_counts.get("gold", 0),
        "same_work_pair_count": relation_counts.get("same_work", 0),
        "unrelated_pair_count": relation_counts.get("unrelated", 0),
        "agenda_non_identity_pair_count": relation_counts.get("agenda_non_identity", 0),
        "train_ratio": train_ratio,
        "dev_ratio": dev_ratio,
        "seed": seed,
    }


def build_iad_bench_balanced_subset(
    documents: list[dict],
    pairs: list[dict],
    relation_labels: Iterable[str] | str | None = None,
    include_label_sources: Iterable[str] | str | None = None,
    exclude_label_sources: Iterable[str] | str | None = None,
    seed: int = 42,
    train_ratio: float = 0.8,
    dev_ratio: float = 0.1,
) -> tuple[list[dict], list[dict], dict]:
    """构建 IAD-Bench 来源内关系平衡子集。

    参数:
        documents: IAD-Bench 文档记录。
        pairs: IAD-Bench pair 记录。
        relation_labels: 需要在每个 label_source 内配平的关系标签。
        include_label_sources: 只保留这些 label_source；为空时不限制。
        exclude_label_sources: 排除这些 label_source。
        seed: 抽样与 split 随机种子。
        train_ratio: train split 比例。
        dev_ratio: dev split 比例。

    返回:
        平衡后的文档、pair 和摘要。
    """
    parsed_relation_labels = _parse_relation_labels(relation_labels)
    _validate_split_ratios(train_ratio, dev_ratio)
    rng = random.Random(seed)
    filtered_pairs, parsed_include_sources, parsed_exclude_sources = _filter_pairs_by_label_source(
        pairs=pairs,
        include_label_sources=include_label_sources,
        exclude_label_sources=exclude_label_sources,
    )
    grouped_pairs = _group_pairs_by_source_and_relation(filtered_pairs, parsed_relation_labels)
    selected_pairs: list[dict] = []
    excluded_source_count = 0
    for label_source in sorted(grouped_pairs):
        relation_groups = grouped_pairs[label_source]
        relation_counts = [len(relation_groups.get(relation_label, [])) for relation_label in parsed_relation_labels]
        target_count = min(relation_counts) if relation_counts else 0
        if target_count <= 0:
            excluded_source_count += 1
            continue
        for relation_label in parsed_relation_labels:
            sampled_pairs = _sample_pairs(relation_groups[relation_label], target_count, rng)
            selected_pairs.extend(_copy_pair(pair, _clean(pair.get("pair_id"))) for pair in sampled_pairs)
    selected_pairs.sort(key=lambda pair: (_clean(pair.get("label_source")), _clean(pair.get("relation_label")), _clean(pair.get("pair_id"))))
    for index, pair in enumerate(selected_pairs, start=1):
        pair["pair_id"] = f"iadbench_balanced_{index:06d}"
    _assign_stratified_splits(selected_pairs, seed=seed, train_ratio=train_ratio, dev_ratio=dev_ratio)
    selected_documents = _selected_documents(documents, selected_pairs)
    summary = _build_summary(
        original_pair_count=len(pairs),
        filtered_pair_count=len(filtered_pairs),
        selected_pairs=selected_pairs,
        selected_documents=selected_documents,
        relation_labels=parsed_relation_labels,
        include_label_sources=parsed_include_sources,
        exclude_label_sources=parsed_exclude_sources,
        excluded_source_count=excluded_source_count,
        train_ratio=train_ratio,
        dev_ratio=dev_ratio,
        seed=seed,
    )
    LOGGER.info(
        "IAD-Bench 平衡子集构建完成: documents=%s pairs=%s dropped=%s",
        len(selected_documents),
        len(selected_pairs),
        summary["dropped_pair_count"],
    )
    return selected_documents, selected_pairs, summary


def build_iad_bench_balanced_subset_from_paths(
    documents_path: str | Path,
    pairs_path: str | Path,
    relation_labels: Iterable[str] | str | None = None,
    include_label_sources: Iterable[str] | str | None = None,
    exclude_label_sources: Iterable[str] | str | None = None,
    seed: int = 42,
    train_ratio: float = 0.8,
    dev_ratio: float = 0.1,
) -> tuple[list[dict], list[dict], dict]:
    """从文件构建 IAD-Bench 平衡子集。

    参数:
        documents_path: IAD-Bench documents JSONL 路径。
        pairs_path: IAD-Bench pairs JSONL 路径。
        relation_labels: 需要配平的关系标签。
        include_label_sources: 只保留这些 label_source；为空时不限制。
        exclude_label_sources: 排除这些 label_source。
        seed: 抽样与 split 随机种子。
        train_ratio: train split 比例。
        dev_ratio: dev split 比例。

    返回:
        平衡后的文档、pair 和摘要。
    """
    try:
        return build_iad_bench_balanced_subset(
            documents=read_records(documents_path),
            pairs=read_records(pairs_path),
            relation_labels=relation_labels,
            include_label_sources=include_label_sources,
            exclude_label_sources=exclude_label_sources,
            seed=seed,
            train_ratio=train_ratio,
            dev_ratio=dev_ratio,
        )
    except Exception:
        LOGGER.exception("读取 IAD-Bench 平衡子集输入失败: documents=%s pairs=%s", documents_path, pairs_path)
        raise


def _write_provenance_summary(path: Path, pairs: list[dict]) -> None:
    """写出 provenance 汇总 CSV。

    参数:
        path: 输出 CSV 路径。
        pairs: 平衡后的 pair。

    返回:
        无。
    """
    rows = []
    grouped_counts = Counter(
        (
            _clean(pair.get("label_source")),
            _clean(pair.get("label_strength")),
            _clean(pair.get("relation_label")),
            _clean(pair.get("split")),
        )
        for pair in pairs
    )
    for (label_source, label_strength, relation_label, split), pair_count in sorted(grouped_counts.items()):
        rows.append(
            {
                "label_source": label_source,
                "label_strength": label_strength,
                "relation_label": relation_label,
                "split": split,
                "pair_count": pair_count,
            }
        )
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["label_source", "label_strength", "relation_label", "split", "pair_count"])
        writer.writeheader()
        writer.writerows(rows)


def _write_dataset_card(path: Path, summary: dict) -> None:
    """写出平衡子集数据卡。

    参数:
        path: 数据卡路径。
        summary: 平衡子集摘要。

    返回:
        无。
    """
    lines = [
        "# IAD-Bench Balanced Gold Subset",
        "",
        "## 数据边界",
        "",
        "该子集按 label_source 内 relation_label 数量成对下采样，用于缓解类别不平衡和来源捷径风险。",
        "",
        "## 规模摘要",
        "",
        f"- document_count: {summary['document_count']}",
        f"- pair_count: {summary['pair_count']}",
        f"- original_pair_count: {summary['original_pair_count']}",
        f"- filtered_pair_count: {summary.get('filtered_pair_count', summary['original_pair_count'])}",
        f"- filtered_out_pair_count: {summary.get('filtered_out_pair_count', 0)}",
        f"- dropped_pair_count: {summary['dropped_pair_count']}",
        f"- excluded_source_count: {summary['excluded_source_count']}",
        "",
        "## 来源过滤",
        "",
        f"- include_label_sources: {', '.join(summary.get('include_label_sources') or []) or '未限制'}",
        f"- exclude_label_sources: {', '.join(summary.get('exclude_label_sources') or []) or '未限制'}",
        "",
        "## 关系分布",
        "",
    ]
    for relation_label, count in summary["relation_label_counts"].items():
        lines.append(f"- {relation_label}: {count}")
    lines.extend(
        [
            "",
            "## 写作边界",
            "",
            "- 该子集用于 balanced evaluation，不替代全量公开 gold 结果。",
            "- 主文应同时报告 full open_v3 和 balanced open_v3，避免只选择有利子集。",
            "- 若扩展 OpenAlex/OpenCitations silver，应单独分层报告，不得混写为 gold。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_iad_bench_balanced_subset_outputs(
    documents: list[dict],
    pairs: list[dict],
    summary: dict,
    output_dir: str | Path,
) -> None:
    """写出 IAD-Bench 平衡子集产物。

    参数:
        documents: 平衡子集文档。
        pairs: 平衡子集 pair。
        summary: 平衡子集摘要。
        output_dir: 输出目录。

    返回:
        无。
    """
    try:
        directory = ensure_directory(output_dir)
        document_rows = [{field: document.get(field) for field in DOCUMENT_FIELDS} for document in documents]
        pair_rows = [{**{field: pair.get(field) for field in PAIR_FIELDS}, "source_pair_id": pair.get("source_pair_id", "")} for pair in pairs]
        split_rows = [
            {
                "pair_id": pair["pair_id"],
                "source_document_id": pair["source_document_id"],
                "target_document_id": pair["target_document_id"],
                "split": pair["split"],
                "label_source": pair["label_source"],
                "label_strength": pair["label_strength"],
            }
            for pair in pairs
        ]
        write_records(document_rows, directory / "iad_bench_documents.jsonl")
        write_records(pair_rows, directory / "iad_bench_pairs.jsonl")
        write_records(split_rows, directory / "iad_bench_splits.jsonl")
        write_records([summary], directory / "iad_bench_summary.jsonl")
        _write_provenance_summary(directory / "label_provenance_summary.csv", pairs)
        _write_dataset_card(directory / "dataset_card.md", summary)
    except Exception:
        LOGGER.exception("写出 IAD-Bench 平衡子集失败: %s", output_dir)
        raise
