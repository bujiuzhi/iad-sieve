"""测试 IAD-Bench 公开 gold 平衡子集构建器。"""

from __future__ import annotations

import json
from argparse import Namespace
from collections import Counter

from iad_sieve.cli import build_parser, command_build_iad_bench_balanced_subset
from iad_sieve.evaluation.iad_bench_balanced_subset import (
    build_iad_bench_balanced_subset,
    build_iad_bench_balanced_subset_from_paths,
    write_iad_bench_balanced_subset_outputs,
)
from iad_sieve.utils.io_utils import read_records


def _write_jsonl(path, records: list[dict]) -> None:
    """写入 JSONL 测试文件。

    参数:
        path: 输出路径。
        records: JSON 记录。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def _document(document_id: str) -> dict:
    """构造测试文档。

    参数:
        document_id: 文档 ID。

    返回:
        IAD-Bench 文档记录。
    """
    return {
        "document_id": document_id,
        "title": f"title {document_id}",
        "abstract": "",
        "authors": [],
        "year": 2024,
        "venue": "",
        "doi": "",
        "arxiv_id": "",
        "openalex_work_id": "",
        "topics": [],
        "references": [],
        "source_dataset": "fixture",
    }


def _pair(pair_id: str, source: str, relation: str) -> dict:
    """构造测试 pair。

    参数:
        pair_id: pair ID。
        source: label_source。
        relation: relation_label。

    返回:
        IAD-Bench pair 记录。
    """
    same_work = 1 if relation == "same_work" else 0
    return {
        "pair_id": pair_id,
        "source_document_id": f"{pair_id}:left",
        "target_document_id": f"{pair_id}:right",
        "relation_label": relation,
        "expected_label": same_work,
        "expected_agenda_label": same_work,
        "label_source": source,
        "label_strength": "gold",
        "label_provenance": {"source_pair_id": pair_id},
        "split": "train",
        "hard_negative_level": "none",
    }


def _imbalanced_fixture() -> tuple[list[dict], list[dict]]:
    """构造来源内正负不平衡 fixture。

    参数:
        无。

    返回:
        文档列表与 pair 列表。
    """
    pairs = []
    pairs.extend([_pair(f"a_same_{index}", "source_a", "same_work") for index in range(3)])
    pairs.extend([_pair(f"a_unrelated_{index}", "source_a", "unrelated") for index in range(5)])
    pairs.extend([_pair(f"b_same_{index}", "source_b", "same_work") for index in range(2)])
    pairs.append(_pair("b_unrelated_0", "source_b", "unrelated"))
    pairs.append(_pair("c_same_0", "source_c", "same_work"))
    document_ids = sorted({pair["source_document_id"] for pair in pairs} | {pair["target_document_id"] for pair in pairs} | {"orphan"})
    return [_document(document_id) for document_id in document_ids], pairs


def test_build_iad_bench_balanced_subset_matches_relation_counts_per_source() -> None:
    """验证按 label_source 内正负样本数量配平。"""
    documents, pairs = _imbalanced_fixture()

    selected_documents, selected_pairs, summary = build_iad_bench_balanced_subset(
        documents=documents,
        pairs=pairs,
        relation_labels=["same_work", "unrelated"],
        seed=13,
        train_ratio=0.5,
        dev_ratio=0.25,
    )
    counts = Counter((pair["label_source"], pair["relation_label"]) for pair in selected_pairs)

    assert summary["pair_count"] == 8
    assert summary["dropped_pair_count"] == 4
    assert summary["excluded_source_count"] == 1
    assert counts[("source_a", "same_work")] == 3
    assert counts[("source_a", "unrelated")] == 3
    assert counts[("source_b", "same_work")] == 1
    assert counts[("source_b", "unrelated")] == 1
    assert Counter(pair["relation_label"] for pair in selected_pairs) == {"same_work": 4, "unrelated": 4}
    assert all(pair["pair_id"].startswith("iadbench_balanced_") for pair in selected_pairs)
    assert "orphan" not in {document["document_id"] for document in selected_documents}


def test_build_iad_bench_balanced_subset_from_paths_reads_inputs(tmp_path) -> None:
    """验证平衡子集可从 IAD-Bench 文件读取输入。"""
    documents, pairs = _imbalanced_fixture()
    documents_path = tmp_path / "documents.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    _write_jsonl(documents_path, documents)
    _write_jsonl(pairs_path, pairs)

    _, selected_pairs, summary = build_iad_bench_balanced_subset_from_paths(
        documents_path=documents_path,
        pairs_path=pairs_path,
    )

    assert len(selected_pairs) == summary["pair_count"]
    assert summary["relation_labels"] == ["same_work", "unrelated"]


def test_build_iad_bench_balanced_subset_filters_label_sources() -> None:
    """验证平衡子集支持按 label_source 筛选主评估来源。"""
    documents, pairs = _imbalanced_fixture()

    selected_documents, selected_pairs, summary = build_iad_bench_balanced_subset(
        documents=documents,
        pairs=pairs,
        include_label_sources="source_a",
        seed=13,
    )

    assert summary["original_pair_count"] == 12
    assert summary["filtered_pair_count"] == 8
    assert summary["filtered_out_pair_count"] == 4
    assert summary["pair_count"] == 6
    assert summary["include_label_sources"] == ["source_a"]
    assert summary["exclude_label_sources"] == []
    assert set(summary["label_source_counts"]) == {"source_a"}
    assert {pair["label_source"] for pair in selected_pairs} == {"source_a"}
    assert {document["document_id"] for document in selected_documents} == {
        pair["source_document_id"] for pair in selected_pairs
    } | {pair["target_document_id"] for pair in selected_pairs}


def test_build_iad_bench_balanced_subset_excludes_label_sources() -> None:
    """验证平衡子集可排除非目标来源。"""
    documents, pairs = _imbalanced_fixture()

    _, selected_pairs, summary = build_iad_bench_balanced_subset(
        documents=documents,
        pairs=pairs,
        exclude_label_sources=["source_a"],
        seed=13,
    )

    assert summary["filtered_pair_count"] == 4
    assert summary["filtered_out_pair_count"] == 8
    assert summary["pair_count"] == 2
    assert summary["exclude_label_sources"] == ["source_a"]
    assert {pair["label_source"] for pair in selected_pairs} == {"source_b"}


def test_write_iad_bench_balanced_subset_outputs_writes_contract_files(tmp_path) -> None:
    """验证平衡子集写出 IAD-Bench 契约文件。"""
    documents, pairs = _imbalanced_fixture()
    selected_documents, selected_pairs, summary = build_iad_bench_balanced_subset(documents, pairs, seed=7)
    output_dir = tmp_path / "balanced"

    write_iad_bench_balanced_subset_outputs(selected_documents, selected_pairs, summary, output_dir)

    assert (output_dir / "iad_bench_documents.jsonl").exists()
    assert (output_dir / "iad_bench_pairs.jsonl").exists()
    assert (output_dir / "iad_bench_splits.jsonl").exists()
    assert (output_dir / "iad_bench_summary.jsonl").exists()
    assert (output_dir / "label_provenance_summary.csv").exists()
    assert "IAD-Bench Balanced Gold Subset" in (output_dir / "dataset_card.md").read_text(encoding="utf-8")


def test_build_iad_bench_balanced_subset_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出平衡子集。"""
    documents, pairs = _imbalanced_fixture()
    documents_path = tmp_path / "documents.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    output_dir = tmp_path / "balanced"
    _write_jsonl(documents_path, documents)
    _write_jsonl(pairs_path, pairs)

    command_build_iad_bench_balanced_subset(
        Namespace(
            documents=str(documents_path),
            pairs=str(pairs_path),
            output_dir=str(output_dir),
            relation_labels="same_work,unrelated",
            include_label_sources="source_a,source_b",
            exclude_label_sources="source_c",
            seed=5,
            train_ratio=0.8,
            dev_ratio=0.1,
        )
    )

    assert read_records(output_dir / "iad_bench_summary.jsonl")[0]["pair_count"] == 8
    assert read_records(output_dir / "iad_bench_summary.jsonl")[0]["include_label_sources"] == ["source_a", "source_b"]


def test_cli_includes_build_iad_bench_balanced_subset_command() -> None:
    """验证 CLI 暴露 build-iad-bench-balanced-subset 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-iad-bench-balanced-subset",
            "--documents",
            "outputs/iad_bench_open_v3/iad_bench_documents.jsonl",
            "--pairs",
            "outputs/iad_bench_open_v3/iad_bench_pairs.jsonl",
            "--output-dir",
            "outputs/iad_bench_open_v3_balanced_gold",
            "--include-label-sources",
            "deepmatcher_dblp_scholar,deepmatcher_py_entitymatching_dblp_acm",
        ]
    )

    assert args.command == "build-iad-bench-balanced-subset"
    assert args.relation_labels == "same_work,unrelated"
    assert args.include_label_sources == "deepmatcher_dblp_scholar,deepmatcher_py_entitymatching_dblp_acm"
