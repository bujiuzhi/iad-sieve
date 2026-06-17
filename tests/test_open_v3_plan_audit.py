"""测试 IAD-Bench-Open-v3 数据目标差距审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_open_v3_plan_audit
from iad_sieve.evaluation.open_v3_plan_audit import (
    build_open_v3_plan_audit_rows_from_paths,
    write_open_v3_plan_audit_outputs,
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


def test_open_v3_plan_audit_flags_topic_concentration_and_gold_gap(tmp_path) -> None:
    """验证 Open-v3 审计能识别 gold 规模不足和 silver topic 过度集中。"""
    pairs = tmp_path / "pairs.jsonl"
    documents = tmp_path / "documents.jsonl"
    _write_jsonl(
        pairs,
        [
            {"pair_id": "g1", "label_strength": "gold", "label_source": "deepmatcher", "topic_id": "t1", "expected_label": 1, "split": "train"},
            {
                "pair_id": "s1",
                "label_strength": "silver",
                "label_source": "openalex",
                "topic_id": "t1",
                "relation_label": "agenda_non_identity",
                "expected_label": 0,
                "split": "test",
            },
            {
                "pair_id": "s2",
                "label_strength": "silver",
                "label_source": "openalex",
                "topic_id": "t1",
                "relation_label": "agenda_non_identity",
                "expected_label": 0,
                "split": "test",
            },
        ],
    )
    _write_jsonl(documents, [{"document_id": "d1"}, {"document_id": "d2"}])

    rows = build_open_v3_plan_audit_rows_from_paths(
        pairs_path=pairs,
        documents_path=documents,
        min_documents=20_000,
        min_gold_pairs=2_000,
        min_silver_pairs=50_000,
        min_topics=30,
        max_top_topic_ratio=0.15,
    )

    by_id = {row["dimension_id"]: row for row in rows}
    assert by_id["document_scale"]["audit_status"] == "blocked"
    assert by_id["gold_pair_scale"]["audit_status"] == "blocked"
    assert by_id["silver_pair_scale"]["audit_status"] == "blocked"
    assert by_id["silver_topic_diversity"]["audit_status"] == "blocked"
    assert by_id["human_audit_position"]["audit_status"] == "deferred_enhancement"
    assert by_id["silver_topic_diversity"]["top_topic_ratio"] == 1.0


def test_write_open_v3_plan_audit_outputs_writes_jsonl_csv_markdown_and_summary(tmp_path) -> None:
    """验证 Open-v3 审计写出 JSONL、CSV、Markdown 和 summary。"""
    rows = [
        {
            "dimension_id": "gold_pair_scale",
            "audit_status": "blocked",
            "reviewer_risk_level": "high",
            "actual_value": 415,
            "target_value": 2000,
            "reviewer_interpretation": "公开 gold 未达到 Open-v3 目标。",
            "next_optimization": "补充公开 DBLP 系列 gold。",
        },
        {
            "dimension_id": "human_audit_position",
            "audit_status": "deferred_enhancement",
            "reviewer_risk_level": "medium",
            "actual_value": 0,
            "target_value": "500-1000",
            "reviewer_interpretation": "人工 gold 后置。",
            "next_optimization": "标注协调完成后接入。",
        },
    ]
    output_dir = tmp_path / "open_v3_plan_audit"

    write_open_v3_plan_audit_outputs(rows, output_dir)

    assert read_records(output_dir / "open_v3_plan_audit.jsonl")[0]["dimension_id"] == "gold_pair_scale"
    assert (output_dir / "open_v3_plan_audit.csv").exists()
    assert "# IAD-Bench-Open-v3 Plan Audit" in (output_dir / "open_v3_plan_audit.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "open_v3_plan_audit_summary.jsonl")[0]
    assert summary["dimension_count"] == 2
    assert summary["blocked_count"] == 1
    assert summary["deferred_enhancement_count"] == 1


def test_build_open_v3_plan_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 Open-v3 数据目标差距审计。"""
    pairs = tmp_path / "pairs.jsonl"
    documents = tmp_path / "documents.jsonl"
    output_dir = tmp_path / "open_v3_plan_audit"
    _write_jsonl(pairs, [{"pair_id": "g1", "label_strength": "gold", "split": "train"}])
    _write_jsonl(documents, [{"document_id": "d1"}])

    command_build_open_v3_plan_audit(
        Namespace(
            pairs=str(pairs),
            documents=str(documents),
            output_dir=str(output_dir),
            min_documents=20_000,
            min_gold_pairs=2_000,
            min_silver_pairs=50_000,
            min_topics=30,
            max_top_topic_ratio=0.15,
        )
    )

    assert (output_dir / "open_v3_plan_audit.jsonl").exists()
    assert (output_dir / "open_v3_plan_audit_summary.jsonl").exists()


def test_cli_includes_build_open_v3_plan_audit_command() -> None:
    """验证 CLI 暴露 build-open-v3-plan-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-open-v3-plan-audit",
            "--pairs",
            "outputs/iad_bench_open_v2/iad_bench_pairs.jsonl",
            "--documents",
            "outputs/iad_bench_open_v2/iad_bench_documents.jsonl",
            "--output-dir",
            "outputs/open_v3_plan_audit_fixture",
        ]
    )

    assert args.command == "build-open-v3-plan-audit"
    assert args.min_gold_pairs == 2000
    assert args.min_topics == 30
