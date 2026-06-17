"""测试 IAD-Bench 分层分布审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_iad_bench_stratification_audit
from iad_sieve.evaluation.iad_bench_stratification_audit import (
    build_iad_bench_stratification_audit_rows,
    build_iad_bench_stratification_audit_rows_from_paths,
    write_iad_bench_stratification_audit_outputs,
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


def _pair(pair_id: str, split: str, relation: str, strength: str, source: str) -> dict:
    """构造测试 pair。

    参数:
        pair_id: pair ID。
        split: 数据划分。
        relation: relation_label。
        strength: label_strength。
        source: label_source。

    返回:
        pair 记录。
    """
    return {
        "pair_id": pair_id,
        "split": split,
        "relation_label": relation,
        "label_strength": strength,
        "label_source": source,
        "label_provenance": {"label_type": f"{source}_{strength}"},
    }


def test_build_iad_bench_stratification_audit_rows_flags_imbalance_and_confounding() -> None:
    """验证分层审计能识别标签强度失衡与 relation-source 绑定。"""
    pairs = [
        _pair("p1", "train", "same_work", "gold", "deepmatcher"),
        _pair("p2", "dev", "same_work", "gold", "deepmatcher"),
        _pair("p3", "test", "same_work", "gold", "deepmatcher"),
        _pair("p4", "train", "agenda_non_identity", "silver", "openalex"),
        _pair("p5", "dev", "agenda_non_identity", "silver", "openalex"),
        _pair("p6", "test", "agenda_non_identity", "silver", "openalex"),
        _pair("p7", "train", "agenda_non_identity", "silver", "openalex"),
        _pair("p8", "dev", "agenda_non_identity", "silver", "openalex"),
        _pair("p9", "test", "agenda_non_identity", "silver", "openalex"),
        _pair("p10", "train", "agenda_non_identity", "silver", "openalex"),
    ]

    audit_rows, distribution_rows = build_iad_bench_stratification_audit_rows(
        pairs=pairs,
        required_splits=["train", "dev", "test"],
        max_top_strength_ratio=0.6,
        min_sources_per_relation=2,
    )
    by_dimension = {row["dimension_id"]: row for row in audit_rows}

    assert by_dimension["split_label_strength_coverage"]["audit_status"] == "defensible"
    assert by_dimension["label_strength_imbalance"]["audit_status"] == "high_risk"
    assert by_dimension["source_relation_confounding"]["audit_status"] == "blocked"
    assert by_dimension["provenance_completeness"]["audit_status"] == "defensible"
    assert any(row["stratum_id"] == "split_x_label_strength" and row["split"] == "train" for row in distribution_rows)


def test_build_iad_bench_stratification_audit_rows_blocks_missing_split_strength() -> None:
    """验证 split 缺少 gold 或 silver 时会阻塞分层可信度。"""
    pairs = [
        _pair("p1", "train", "same_work", "gold", "deepmatcher"),
        _pair("p2", "dev", "same_work", "gold", "deepmatcher"),
        _pair("p3", "test", "agenda_non_identity", "silver", "openalex"),
    ]

    audit_rows, _ = build_iad_bench_stratification_audit_rows(pairs=pairs, required_label_strengths=["gold", "silver"])
    by_dimension = {row["dimension_id"]: row for row in audit_rows}

    assert by_dimension["split_label_strength_coverage"]["audit_status"] == "blocked"
    assert "train:silver" in by_dimension["split_label_strength_coverage"]["missing_cells"]


def test_build_iad_bench_stratification_audit_rows_all_gold_is_defensible() -> None:
    """验证公开 gold-only 子集不会因单一 label_strength 被误判为高风险。"""
    pairs = [
        _pair("p1", "train", "same_work", "gold", "source_a"),
        _pair("p2", "dev", "same_work", "gold", "source_b"),
        _pair("p3", "test", "unrelated", "gold", "source_a"),
        _pair("p4", "train", "unrelated", "gold", "source_b"),
        _pair("p5", "dev", "same_work", "gold", "source_a"),
        _pair("p6", "test", "unrelated", "gold", "source_b"),
    ]

    audit_rows, _ = build_iad_bench_stratification_audit_rows(
        pairs=pairs,
        max_top_strength_ratio=0.8,
        min_sources_per_relation=2,
    )
    by_dimension = {row["dimension_id"]: row for row in audit_rows}

    assert by_dimension["label_strength_imbalance"]["audit_status"] == "defensible"
    assert by_dimension["label_strength_imbalance"]["top_label_strength"] == "gold"


def test_build_iad_bench_stratification_audit_rows_from_paths_reads_pairs(tmp_path) -> None:
    """验证分层审计可从 pair 文件读取输入。"""
    pairs_path = tmp_path / "pairs.jsonl"
    _write_jsonl(pairs_path, [_pair("p1", "train", "same_work", "gold", "deepmatcher")])

    audit_rows, distribution_rows = build_iad_bench_stratification_audit_rows_from_paths(pairs_path=pairs_path)

    assert audit_rows
    assert distribution_rows


def test_write_iad_bench_stratification_audit_outputs_writes_files(tmp_path) -> None:
    """验证分层审计写出审计、分布、CSV、Markdown 和 summary。"""
    audit_rows = [
        {
            "dimension_id": "label_strength_imbalance",
            "audit_status": "high_risk",
            "reviewer_risk_level": "high",
            "reviewer_interpretation": "silver 占比过高。",
            "next_optimization": "补充 gold。",
        }
    ]
    distribution_rows = [{"stratum_id": "label_strength_total", "label_strength": "silver", "pair_count": 7, "pair_ratio": 0.7}]
    output_dir = tmp_path / "stratification_audit"

    write_iad_bench_stratification_audit_outputs(audit_rows, distribution_rows, output_dir)

    assert read_records(output_dir / "iad_bench_stratification_audit.jsonl")[0]["dimension_id"] == "label_strength_imbalance"
    assert read_records(output_dir / "iad_bench_strata_distribution.jsonl")[0]["stratum_id"] == "label_strength_total"
    assert (output_dir / "iad_bench_stratification_audit.csv").exists()
    assert (output_dir / "iad_bench_strata_distribution.csv").exists()
    assert "# IAD-Bench Stratification Audit" in (output_dir / "iad_bench_stratification_audit.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "iad_bench_stratification_audit_summary.jsonl")[0]
    assert summary["dimension_count"] == 1
    assert summary["high_risk_count"] == 1


def test_build_iad_bench_stratification_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 IAD-Bench 分层审计。"""
    pairs_path = tmp_path / "pairs.jsonl"
    output_dir = tmp_path / "stratification_audit"
    _write_jsonl(pairs_path, [_pair("p1", "train", "same_work", "gold", "deepmatcher")])

    command_build_iad_bench_stratification_audit(
        Namespace(
            pairs=str(pairs_path),
            output_dir=str(output_dir),
            max_top_strength_ratio=0.8,
            min_sources_per_relation=2,
        )
    )

    assert (output_dir / "iad_bench_stratification_audit.jsonl").exists()
    assert (output_dir / "iad_bench_stratification_audit_summary.jsonl").exists()


def test_cli_includes_build_iad_bench_stratification_audit_command() -> None:
    """验证 CLI 暴露 build-iad-bench-stratification-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-iad-bench-stratification-audit",
            "--pairs",
            "outputs/iad_bench_open_v2/iad_bench_pairs.jsonl",
            "--output-dir",
            "outputs/iad_bench_stratification_audit_fixture",
        ]
    )

    assert args.command == "build-iad-bench-stratification-audit"
    assert args.max_top_strength_ratio == 0.8
    assert args.min_sources_per_relation == 2
