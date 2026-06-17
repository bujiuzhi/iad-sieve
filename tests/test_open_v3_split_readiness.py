"""测试 IAD-Bench-Open-v3 split 泛化就绪度审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_open_v3_split_readiness
from iad_sieve.evaluation.open_v3_split_readiness import (
    build_open_v3_split_readiness_rows,
    build_open_v3_split_readiness_rows_from_paths,
    write_open_v3_split_readiness_outputs,
)
from iad_sieve.utils.io_utils import read_records


def _write_jsonl(path, records: list[dict]) -> None:
    """写入 JSONL 测试文件。

    参数:
        path: 输出路径。
        records: 记录列表。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def test_build_open_v3_split_readiness_rows_flags_source_and_topic_holdout_gaps() -> None:
    """验证 split 审计能识别 source-held-out 和 topic-held-out 不足。"""
    pairs = [
        {
            "pair_id": "g1",
            "source_document_id": "a",
            "target_document_id": "b",
            "label_strength": "gold",
            "label_source": "deepmatcher",
            "relation_label": "same_work",
            "split": "train",
        },
        {
            "pair_id": "g2",
            "source_document_id": "c",
            "target_document_id": "d",
            "label_strength": "gold",
            "label_source": "deepmatcher",
            "relation_label": "unrelated",
            "split": "dev",
        },
        {
            "pair_id": "s1",
            "source_document_id": "e",
            "target_document_id": "f",
            "label_strength": "silver",
            "label_source": "openalex",
            "relation_label": "agenda_non_identity",
            "split": "test",
            "label_provenance": {"primary_topic": "openalex:T1"},
        },
    ]

    rows = build_open_v3_split_readiness_rows(pairs, min_sources_per_relation=2, min_topics_for_topic_holdout=3)
    by_id = {row["dimension_id"]: row for row in rows}

    assert by_id["random_split_coverage"]["audit_status"] == "defensible"
    assert by_id["source_held_out_readiness"]["audit_status"] == "blocked"
    assert by_id["source_held_out_readiness"]["min_relation_source_count"] == 1
    assert by_id["topic_held_out_readiness"]["audit_status"] == "blocked"
    assert by_id["topic_held_out_readiness"]["topic_count"] == 1
    assert by_id["pair_leakage_guard"]["audit_status"] == "defensible"


def test_build_open_v3_split_readiness_rows_detects_pair_leakage() -> None:
    """验证同一无向 pair 重复出现在多个 split 时会标记泄漏风险。"""
    pairs = [
        {"pair_id": "p1", "source_document_id": "a", "target_document_id": "b", "label_strength": "gold", "label_source": "deepmatcher", "relation_label": "same_work", "split": "train"},
        {"pair_id": "p2", "source_document_id": "b", "target_document_id": "a", "label_strength": "gold", "label_source": "deepmatcher", "relation_label": "same_work", "split": "test"},
    ]

    rows = build_open_v3_split_readiness_rows(pairs)
    by_id = {row["dimension_id"]: row for row in rows}

    assert by_id["pair_leakage_guard"]["audit_status"] == "blocked"
    assert by_id["pair_leakage_guard"]["leaked_pair_count"] == 1


def test_build_open_v3_split_readiness_rows_from_paths_reads_pairs(tmp_path) -> None:
    """验证 split 审计可从 IAD-Bench pair 文件读取输入。"""
    pairs_path = tmp_path / "pairs.jsonl"
    _write_jsonl(
        pairs_path,
        [
            {"pair_id": "p1", "source_document_id": "a", "target_document_id": "b", "label_strength": "gold", "label_source": "deepmatcher", "relation_label": "same_work", "split": "train"}
        ],
    )

    rows = build_open_v3_split_readiness_rows_from_paths(pairs_path=pairs_path)

    assert any(row["dimension_id"] == "random_split_coverage" for row in rows)


def test_write_open_v3_split_readiness_outputs_writes_jsonl_csv_markdown_and_summary(tmp_path) -> None:
    """验证 split 审计写出 JSONL、CSV、Markdown 和 summary。"""
    rows = [
        {
            "dimension_id": "random_split_coverage",
            "audit_status": "defensible",
            "reviewer_risk_level": "low",
            "reviewer_interpretation": "random split 可用。",
            "next_optimization": "继续分层报告。",
        },
        {
            "dimension_id": "topic_held_out_readiness",
            "audit_status": "blocked",
            "reviewer_risk_level": "high",
            "reviewer_interpretation": "topic 数不足。",
            "next_optimization": "扩展多 topic。",
        },
    ]
    output_dir = tmp_path / "open_v3_split_readiness"

    write_open_v3_split_readiness_outputs(rows, output_dir)

    assert read_records(output_dir / "open_v3_split_readiness.jsonl")[0]["dimension_id"] == "random_split_coverage"
    assert (output_dir / "open_v3_split_readiness.csv").exists()
    assert "# IAD-Bench-Open-v3 Split Readiness" in (output_dir / "open_v3_split_readiness.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "open_v3_split_readiness_summary.jsonl")[0]
    assert summary["dimension_count"] == 2
    assert summary["blocked_count"] == 1


def test_build_open_v3_split_readiness_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 Open-v3 split 泛化就绪度审计。"""
    pairs_path = tmp_path / "pairs.jsonl"
    output_dir = tmp_path / "open_v3_split_readiness"
    _write_jsonl(
        pairs_path,
        [
            {"pair_id": "p1", "source_document_id": "a", "target_document_id": "b", "label_strength": "gold", "label_source": "deepmatcher", "relation_label": "same_work", "split": "train"}
        ],
    )

    command_build_open_v3_split_readiness(
        Namespace(
            pairs=str(pairs_path),
            output_dir=str(output_dir),
            min_sources_per_relation=2,
            min_topics_for_topic_holdout=30,
        )
    )

    assert (output_dir / "open_v3_split_readiness.jsonl").exists()
    assert (output_dir / "open_v3_split_readiness_summary.jsonl").exists()


def test_cli_includes_build_open_v3_split_readiness_command() -> None:
    """验证 CLI 暴露 build-open-v3-split-readiness 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-open-v3-split-readiness",
            "--pairs",
            "outputs/iad_bench_open_v2/iad_bench_pairs.jsonl",
            "--output-dir",
            "outputs/open_v3_split_readiness_fixture",
        ]
    )

    assert args.command == "build-open-v3-split-readiness"
    assert args.min_sources_per_relation == 2
    assert args.min_topics_for_topic_holdout == 30
