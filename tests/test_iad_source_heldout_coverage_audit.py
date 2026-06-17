"""测试 IAD source-held-out 覆盖审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_iad_source_heldout_coverage_audit
from iad_sieve.evaluation.iad_source_heldout_coverage_audit import (
    build_iad_source_heldout_coverage_rows,
    build_iad_source_heldout_coverage_rows_from_paths,
    build_iad_source_heldout_coverage_summary,
    write_iad_source_heldout_coverage_outputs,
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


def _pair(pair_id: str, split: str, relation_label: str, label_source: str) -> dict:
    """构造 source-held-out 覆盖审计测试 pair。

    参数:
        pair_id: pair ID。
        split: 数据划分。
        relation_label: IAD 关系标签。
        label_source: 标签来源。

    返回:
        pair 记录。
    """
    return {
        "pair_id": pair_id,
        "split": split,
        "relation_label": relation_label,
        "label_source": label_source,
        "label_strength": "gold" if relation_label != "agenda_non_identity" else "silver",
        "evaluation_split_strategy": "source_held_out",
    }


def _random_pair(pair_id: str, split: str, relation_label: str, label_source: str) -> dict:
    """构造普通 random split 测试 pair。

    参数:
        pair_id: pair ID。
        split: 数据划分。
        relation_label: IAD 关系标签。
        label_source: 标签来源。

    返回:
        pair 记录。
    """
    row = _pair(pair_id, split, relation_label, label_source)
    row.pop("evaluation_split_strategy")
    return row


def test_build_iad_source_heldout_coverage_rows_blocks_non_source_heldout_split() -> None:
    """验证普通 random split 不能被误判为 source-held-out 覆盖证据。"""
    rows = build_iad_source_heldout_coverage_rows(
        [
            _random_pair("p1", "train", "same_work", "source_a"),
            _random_pair("p2", "test", "same_work", "source_b"),
            _random_pair("p3", "train", "unrelated", "source_a"),
            _random_pair("p4", "test", "unrelated", "source_b"),
            _random_pair("p5", "train", "agenda_non_identity", "openalex"),
            _random_pair("p6", "test", "agenda_non_identity", "openalex"),
        ]
    )
    summary = build_iad_source_heldout_coverage_summary(rows)

    assert all(row["audit_status"] == "blocked_not_source_heldout_split" for row in rows)
    assert all("missing_source_heldout_strategy" in row["coverage_blockers"] for row in rows)
    assert summary["source_heldout_full_iad_data_ready"] is False
    assert summary["highest_priority_blocker"] == "not_source_heldout_split"


def test_build_iad_source_heldout_coverage_rows_blocks_missing_agenda_relation() -> None:
    """验证缺少 agenda_non_identity 时阻断完整 IAD source-held-out 主张。"""
    rows = build_iad_source_heldout_coverage_rows(
        [
            _pair("p1", "train", "same_work", "source_a"),
            _pair("p2", "test", "same_work", "source_b"),
            _pair("p3", "train", "unrelated", "source_a"),
            _pair("p4", "test", "unrelated", "source_b"),
        ]
    )
    summary = build_iad_source_heldout_coverage_summary(rows)
    by_relation = {row["relation_label"]: row for row in rows}

    assert by_relation["agenda_non_identity"]["audit_status"] == "blocked_missing_relation"
    assert "missing_train_pairs" in by_relation["agenda_non_identity"]["coverage_blockers"]
    assert "missing_test_pairs" in by_relation["agenda_non_identity"]["coverage_blockers"]
    assert summary["source_heldout_full_iad_data_ready"] is False
    assert summary["blocked_relation_count"] == 1
    assert summary["highest_priority_blocker"] == "agenda_non_identity_source_heldout_missing"


def test_build_iad_source_heldout_coverage_rows_blocks_overlapping_sources() -> None:
    """验证同一来源跨 train/test 出现时不能算作 source-held-out 覆盖。"""
    rows = build_iad_source_heldout_coverage_rows(
        [
            _pair("p1", "train", "agenda_non_identity", "openalex"),
            _pair("p2", "test", "agenda_non_identity", "openalex"),
        ],
        relation_labels=["agenda_non_identity"],
    )
    summary = build_iad_source_heldout_coverage_summary(rows)
    row = rows[0]

    assert row["audit_status"] == "blocked_source_overlap"
    assert row["overlapping_label_source_count"] == 1
    assert row["overlapping_label_sources"] == "openalex"
    assert "overlapping_train_test_label_sources" in row["coverage_blockers"]
    assert summary["source_heldout_full_iad_data_ready"] is False
    assert summary["highest_priority_blocker"] == "train_test_label_source_overlap"


def test_build_iad_source_heldout_coverage_rows_allows_limited_ready_when_all_relations_have_train_test() -> None:
    """验证三类关系均覆盖 train/test 时允许有限 source-held-out 数据证据。"""
    rows = build_iad_source_heldout_coverage_rows(
        [
            _pair("p1", "train", "same_work", "source_a"),
            _pair("p2", "test", "same_work", "source_b"),
            _pair("p3", "train", "unrelated", "source_a"),
            _pair("p4", "test", "unrelated", "source_b"),
            _pair("p5", "train", "agenda_non_identity", "source_c"),
            _pair("p6", "test", "agenda_non_identity", "source_d"),
        ]
    )
    summary = build_iad_source_heldout_coverage_summary(rows)

    assert all(row["audit_status"] == "limited_source_heldout_coverage" for row in rows)
    assert summary["source_heldout_full_iad_data_ready"] is True
    assert summary["ready_relation_count"] == 3


def test_build_iad_source_heldout_coverage_rows_from_paths_reads_pairs(tmp_path) -> None:
    """验证 source-held-out 覆盖审计可从文件读取输入。"""
    pairs_path = tmp_path / "pairs.jsonl"
    _write_jsonl(pairs_path, [_pair("p1", "train", "same_work", "source_a")])

    rows = build_iad_source_heldout_coverage_rows_from_paths(pairs_path)

    assert rows
    assert rows[0]["relation_label"] == "same_work"


def test_write_iad_source_heldout_coverage_outputs_writes_files(tmp_path) -> None:
    """验证 source-held-out 覆盖审计写出 JSONL、CSV、Markdown 和 summary。"""
    rows = build_iad_source_heldout_coverage_rows([_pair("p1", "train", "same_work", "source_a")])
    output_dir = tmp_path / "source_heldout_coverage"

    write_iad_source_heldout_coverage_outputs(rows, output_dir)

    assert read_records(output_dir / "iad_source_heldout_coverage_audit.jsonl")
    assert read_records(output_dir / "iad_source_heldout_coverage_summary.jsonl")
    assert (output_dir / "iad_source_heldout_coverage_audit.csv").exists()
    assert "# IAD Source-Heldout Coverage Audit" in (
        output_dir / "iad_source_heldout_coverage_audit.md"
    ).read_text(encoding="utf-8")


def test_build_iad_source_heldout_coverage_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 source-held-out 覆盖审计。"""
    pairs_path = tmp_path / "pairs.jsonl"
    output_dir = tmp_path / "source_heldout_coverage"
    _write_jsonl(pairs_path, [_pair("p1", "train", "same_work", "source_a")])

    command_build_iad_source_heldout_coverage_audit(
        Namespace(
            pairs=str(pairs_path),
            output_dir=str(output_dir),
            relation_labels="same_work,unrelated,agenda_non_identity",
            min_train_pairs=1,
            min_test_pairs=1,
        )
    )

    assert (output_dir / "iad_source_heldout_coverage_audit.jsonl").exists()
    assert (output_dir / "iad_source_heldout_coverage_summary.jsonl").exists()


def test_cli_includes_build_iad_source_heldout_coverage_audit_command() -> None:
    """验证 CLI 暴露 build-iad-source-heldout-coverage-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-iad-source-heldout-coverage-audit",
            "--pairs",
            "outputs/iad_bench_open_v3_balanced_gold_source_heldout/scored_relations.jsonl",
            "--output-dir",
            "outputs/iad_source_heldout_coverage_audit_open_v3_balanced_gold",
        ]
    )

    assert args.command == "build-iad-source-heldout-coverage-audit"
    assert args.relation_labels == "same_work,unrelated,agenda_non_identity"
