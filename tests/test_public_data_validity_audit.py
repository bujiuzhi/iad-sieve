"""测试公开数据有效性审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_public_data_validity_audit
from iad_sieve.evaluation.public_data_validity_audit import (
    build_public_data_validity_audit_rows,
    write_public_data_validity_audit_outputs,
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


def test_build_public_data_validity_audit_rows_flags_gold_scale_and_topic_concentration() -> None:
    """验证公开数据有效性审计能识别 gold 规模和 silver 主题集中风险。"""
    pairs = [
        {"pair_id": "g1", "label_strength": "gold", "label_source": "deepmatcher", "relation_label": "same_work", "split": "train"},
        {"pair_id": "g2", "label_strength": "gold", "label_source": "deepmatcher", "relation_label": "unrelated", "split": "dev"},
        {
            "pair_id": "s1",
            "label_strength": "silver",
            "label_source": "openalex",
            "relation_label": "agenda_non_identity",
            "split": "train",
            "label_provenance": {"primary_topic": "T1"},
        },
        {
            "pair_id": "s2",
            "label_strength": "silver",
            "label_source": "openalex",
            "relation_label": "agenda_non_identity",
            "split": "dev",
            "label_provenance": {"primary_topic": "T1"},
        },
        {
            "pair_id": "s3",
            "label_strength": "silver",
            "label_source": "openalex",
            "relation_label": "agenda_non_identity",
            "split": "test",
            "label_provenance": {"primary_topic": "T1"},
        },
    ]
    documents = [
        {"document_id": "d1", "source_dataset": "deepmatcher"},
        {"document_id": "d2", "source_dataset": "openalex", "topics": ["T1"]},
    ]

    rows = build_public_data_validity_audit_rows(pairs, documents, min_gold_pairs=5, max_single_silver_topic_ratio=0.8)
    by_dimension = {row["dimension_id"]: row for row in rows}

    assert by_dimension["gold_scale"]["audit_status"] == "conditional"
    assert by_dimension["gold_scale"]["gold_pair_count"] == 2
    assert by_dimension["silver_topic_concentration"]["audit_status"] == "high_risk"
    assert by_dimension["silver_topic_concentration"]["top_silver_topic"] == "T1"
    assert by_dimension["silver_topic_concentration"]["top_silver_topic_ratio"] == 1.0
    assert by_dimension["relation_label_balance"]["audit_status"] == "defensible"
    assert by_dimension["relation_label_balance"]["dominant_relation_label"] == "agenda_non_identity"
    assert by_dimension["relation_label_balance"]["dominant_relation_label_ratio"] == 0.6
    assert by_dimension["evidence_tier_separation"]["audit_status"] == "defensible"
    assert by_dimension["evidence_tier_separation"]["evidence_tier_count"] == 2
    assert by_dimension["human_audit_absence"]["audit_status"] == "deferred_enhancement"


def test_write_public_data_validity_audit_outputs_writes_jsonl_csv_markdown_and_summary(tmp_path) -> None:
    """验证公开数据有效性审计写出 JSONL、CSV、Markdown 和 summary。"""
    rows = [
        {
            "dimension_id": "gold_scale",
            "audit_status": "conditional",
            "reviewer_risk_level": "medium",
            "gold_pair_count": 2,
            "next_optimization": "补充公开 gold 或 human audit。",
        },
        {
            "dimension_id": "silver_topic_concentration",
            "audit_status": "high_risk",
            "reviewer_risk_level": "high",
            "top_silver_topic_ratio": 1.0,
            "next_optimization": "补充跨主题 OpenAlex hard negative。",
        },
        {
            "dimension_id": "evidence_tier_separation",
            "audit_status": "defensible",
            "reviewer_risk_level": "low",
            "unknown_label_strength_count": 0,
            "missing_label_source_count": 0,
            "next_optimization": "按标签来源分层。",
        },
    ]
    output_dir = tmp_path / "public_data_validity_audit"

    write_public_data_validity_audit_outputs(rows, output_dir)

    assert read_records(output_dir / "public_data_validity_audit.jsonl")[0]["dimension_id"] == "gold_scale"
    assert (output_dir / "public_data_validity_audit.csv").exists()
    assert "# Public Data Validity Audit" in (output_dir / "public_data_validity_audit.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "public_data_validity_audit_summary.jsonl")[0]
    assert summary["dimension_count"] == 3
    assert summary["high_risk_count"] == 1


def test_build_public_data_validity_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出公开数据有效性审计。"""
    pairs_path = tmp_path / "pairs.jsonl"
    documents_path = tmp_path / "documents.jsonl"
    output_dir = tmp_path / "public_data_validity_audit"
    _write_jsonl(pairs_path, [{"pair_id": "p1", "label_strength": "gold", "relation_label": "same_work", "split": "train"}])
    _write_jsonl(documents_path, [{"document_id": "d1", "source_dataset": "deepmatcher"}])

    command_build_public_data_validity_audit(
        Namespace(
            pairs=str(pairs_path),
            documents=str(documents_path),
            output_dir=str(output_dir),
            min_gold_pairs=5,
            max_single_silver_topic_ratio=0.8,
            max_dominant_relation_label_ratio=0.8,
        )
    )

    assert (output_dir / "public_data_validity_audit.jsonl").exists()
    assert (output_dir / "public_data_validity_audit_summary.jsonl").exists()


def test_cli_includes_build_public_data_validity_audit_command() -> None:
    """验证 CLI 暴露 build-public-data-validity-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-public-data-validity-audit",
            "--pairs",
            "outputs/iad_bench_open_v2/iad_bench_pairs.jsonl",
            "--documents",
            "outputs/iad_bench_open_v2/iad_bench_documents.jsonl",
            "--output-dir",
            "outputs/public_data_validity_audit_fixture",
        ]
    )

    assert args.command == "build-public-data-validity-audit"
    assert args.min_gold_pairs == 500
    assert args.max_dominant_relation_label_ratio == 0.8


def test_build_public_data_validity_audit_rows_flags_unknown_evidence_tiers() -> None:
    """验证缺失标签来源或未知标签强度会触发证据分层高风险。"""
    rows = build_public_data_validity_audit_rows(
        pairs=[
            {"pair_id": "p1", "label_strength": "unknown", "relation_label": "same_work", "split": "train"},
            {"pair_id": "p2", "label_strength": "gold", "label_source": "deepmatcher", "relation_label": "same_work", "split": "dev"},
        ],
        documents=[{"document_id": "d1"}],
    )
    by_dimension = {row["dimension_id"]: row for row in rows}

    assert by_dimension["evidence_tier_separation"]["audit_status"] == "high_risk"
    assert by_dimension["evidence_tier_separation"]["unknown_label_strength_count"] == 1
    assert by_dimension["evidence_tier_separation"]["missing_label_source_count"] == 1
    assert by_dimension["relation_label_balance"]["audit_status"] == "conditional"
