"""测试 IAD-Sieve 专用消融实验套件。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_run_iad_ablation_suite
from iad_sieve.evaluation.iad_ablation_suite import run_iad_ablation_suite
from iad_sieve.utils.io_utils import read_records


def _relation(
    source_id: str,
    target_id: str,
    expected_label: int,
    identity_score: float,
    agenda_score: float,
    agenda_non_identity_score: float,
    false_merge_risk: float,
    expected_agenda_label: int | None = None,
) -> dict:
    """构造测试关系记录。

    参数:
        source_id: 源文献 ID。
        target_id: 目标文献 ID。
        expected_label: same_work 标签。
        identity_score: 身份分数。
        agenda_score: 议题分数。
        agenda_non_identity_score: 同议题非同身份分数。
        false_merge_risk: 误合并风险分数。
        expected_agenda_label: 可选 same_agenda 标签。

    返回:
        关系记录。
    """
    record = {
        "source_document_id": source_id,
        "target_document_id": target_id,
        "expected_label": expected_label,
        "identity_score": identity_score,
        "duplicate_score": identity_score,
        "agenda_score": agenda_score,
        "topic_score": agenda_score,
        "agenda_non_identity_score": agenda_non_identity_score,
        "false_merge_risk": false_merge_risk,
        "full_similarity": agenda_score,
        "title_similarity": identity_score,
        "first_author_match": 1.0 if identity_score >= 0.9 else 0.0,
        "conflict_score": 0.0,
    }
    if expected_agenda_label is not None:
        record["expected_agenda_label"] = expected_agenda_label
    return record


def test_run_iad_ablation_suite_shows_agenda_gate_reduces_false_merge() -> None:
    """验证移除 agenda_non_identity 门控会提高 hard negative 误合并。"""
    relations = [
        _relation("a", "b", 1, 0.95, 0.90, 0.05, 0.05, expected_agenda_label=1),
        _relation("c", "d", 0, 0.93, 0.92, 0.80, 0.10, expected_agenda_label=1),
        _relation("e", "f", 0, 0.20, 0.20, 0.00, 0.00, expected_agenda_label=0),
    ]

    rows = run_iad_ablation_suite(relations, identity_threshold=0.9, agenda_block_threshold=0.6, false_merge_risk_threshold=0.5)

    full = next(row for row in rows if row["variant"] == "iad_full" and row["metric_target"] == "same_work_false_merge")
    no_agenda_gate = next(row for row in rows if row["variant"] == "without_agenda_non_identity" and row["metric_target"] == "same_work_false_merge")
    agenda_row = next(row for row in rows if row["variant"] == "agenda_score_only" and row["metric_target"] == "same_agenda_proxy")

    assert full["false_positive"] == 0
    assert no_agenda_gate["false_positive"] == 1
    assert no_agenda_gate["false_merge_rate"] > full["false_merge_rate"]
    assert agenda_row["recall"] == 1.0


def test_run_iad_ablation_suite_skips_missing_labels() -> None:
    """验证缺失标签的记录不会污染指标。"""
    relations = [
        _relation("a", "b", 1, 0.95, 0.90, 0.05, 0.05),
        {"source_document_id": "x", "target_document_id": "y", "identity_score": 0.95},
    ]

    rows = run_iad_ablation_suite(relations)
    full = next(row for row in rows if row["variant"] == "iad_full" and row["metric_target"] == "same_work_false_merge")

    assert full["weak_label_count"] == 1


def test_run_iad_ablation_suite_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 JSONL、CSV 和 Markdown 消融报告。"""
    relations_path = tmp_path / "relations.jsonl"
    output_dir = tmp_path / "ablation"
    relations = [
        _relation("a", "b", 1, 0.95, 0.90, 0.05, 0.05, expected_agenda_label=1),
        _relation("c", "d", 0, 0.93, 0.92, 0.80, 0.10, expected_agenda_label=1),
    ]
    relations_path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in relations) + "\n", encoding="utf-8")

    command_run_iad_ablation_suite(
        Namespace(
            relations=[str(relations_path)],
            output_dir=str(output_dir),
            identity_threshold=0.9,
            agenda_block_threshold=0.6,
            false_merge_risk_threshold=0.5,
            agenda_threshold=0.65,
            dense_threshold=0.9,
            limit=None,
        )
    )

    rows = read_records(output_dir / "iad_ablation_summary.jsonl")

    assert rows
    assert (output_dir / "iad_ablation_summary.csv").exists()
    assert "# IAD-Sieve Ablation Suite" in (output_dir / "iad_ablation_report.md").read_text(encoding="utf-8")


def test_run_iad_ablation_suite_cli_accepts_multiple_relation_files(tmp_path) -> None:
    """验证 CLI 可合并多份已评分关系文件。"""
    first_path = tmp_path / "deepmatcher_relations.jsonl"
    second_path = tmp_path / "scirepeval_relations.jsonl"
    output_dir = tmp_path / "ablation"
    first_path.write_text(json.dumps(_relation("a", "b", 1, 0.95, 0.90, 0.05, 0.05), ensure_ascii=False) + "\n", encoding="utf-8")
    second_path.write_text(json.dumps(_relation("c", "d", 0, 0.93, 0.92, 0.80, 0.10), ensure_ascii=False) + "\n", encoding="utf-8")

    command_run_iad_ablation_suite(
        Namespace(
            relations=[str(first_path), str(second_path)],
            output_dir=str(output_dir),
            identity_threshold=0.9,
            agenda_block_threshold=0.6,
            false_merge_risk_threshold=0.5,
            agenda_threshold=0.65,
            dense_threshold=0.9,
            limit=None,
        )
    )

    rows = read_records(output_dir / "iad_ablation_summary.jsonl")
    full = next(row for row in rows if row["variant"] == "iad_full" and row["metric_target"] == "same_work_false_merge")

    assert full["weak_label_count"] == 2


def test_cli_includes_run_iad_ablation_suite_command() -> None:
    """验证 CLI 暴露 run-iad-ablation-suite 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-iad-ablation-suite",
            "--relations",
            "outputs/scored_relations.jsonl",
            "--output-dir",
            "outputs/iad_ablation",
        ]
    )

    assert args.command == "run-iad-ablation-suite"
    assert args.relations == ["outputs/scored_relations.jsonl"]
