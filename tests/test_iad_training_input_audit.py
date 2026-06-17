"""测试 IAD-Risk 训练输入完备性审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_iad_training_input_audit
from iad_sieve.evaluation.iad_training_input_audit import (
    build_iad_training_input_audit_rows,
    build_iad_training_input_audit_rows_from_paths,
    build_iad_training_input_audit_summary,
    write_iad_training_input_audit_outputs,
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


def _raw_pair(pair_id: str, expected_label: int, expected_agenda_label: int) -> dict:
    """构造缺少训练特征的 raw pair。

    参数:
        pair_id: pair ID。
        expected_label: 同一文献标签。
        expected_agenda_label: 同议题标签。

    返回:
        pair 记录。
    """
    return {
        "pair_id": pair_id,
        "expected_label": expected_label,
        "expected_agenda_label": expected_agenda_label,
        "relation_label": "same_work" if expected_label else ("agenda_non_identity" if expected_agenda_label else "unrelated"),
    }


def _feature_pair(pair_id: str, expected_label: int, expected_agenda_label: int, identity_score: float, agenda_score: float) -> dict:
    """构造特征完备的训练记录。

    参数:
        pair_id: pair ID。
        expected_label: 同一文献标签。
        expected_agenda_label: 同议题标签。
        identity_score: 身份空间分数。
        agenda_score: 议题空间分数。

    返回:
        训练记录。
    """
    false_merge_risk = max(0.0, agenda_score - identity_score)
    return {
        "pair_id": pair_id,
        "expected_label": expected_label,
        "expected_agenda_label": expected_agenda_label,
        "identity_score": identity_score,
        "duplicate_score": identity_score,
        "title_similarity": identity_score,
        "author_overlap": identity_score,
        "first_author_match": identity_score,
        "identifier_score": identity_score,
        "year_score": identity_score,
        "conflict_score": 0.0,
        "agenda_score": agenda_score,
        "topic_score": agenda_score,
        "full_similarity": agenda_score,
        "method_similarity": agenda_score,
        "object_similarity": agenda_score,
        "problem_similarity": agenda_score,
        "keyphrase_similarity": agenda_score,
        "category_overlap": agenda_score,
        "agenda_non_identity_score": false_merge_risk,
        "false_merge_risk": false_merge_risk,
        "contribution_score": 1.0,
    }


def test_build_iad_training_input_audit_blocks_raw_pairs_without_feature_signal() -> None:
    """验证 raw pair 缺少 IAD-Risk 特征时阻断训练声明。"""
    rows = build_iad_training_input_audit_rows(
        relations=[
            _raw_pair("p1", 1, 1),
            _raw_pair("p2", 0, 1),
            _raw_pair("p3", 0, 0),
        ]
    )
    summary = build_iad_training_input_audit_summary(rows)
    by_id = {row["audit_id"]: row for row in rows}

    assert by_id["feature_group:identity_space"]["audit_status"] == "blocked_missing_feature_signal"
    assert by_id["target_head:same_work"]["audit_status"] == "defensible"
    assert by_id["target_head:agenda_non_identity"]["audit_status"] == "defensible"
    assert summary["training_input_ready"] is False


def test_build_iad_training_input_audit_accepts_feature_complete_records() -> None:
    """验证特征和必要标签均齐全时训练输入可用。"""
    rows = build_iad_training_input_audit_rows(
        relations=[
            _feature_pair("p1", 1, 1, 0.95, 0.9),
            _feature_pair("p2", 0, 1, 0.2, 0.9),
            _feature_pair("p3", 0, 0, 0.1, 0.1),
            _feature_pair("p4", 1, 1, 0.9, 0.85),
        ]
    )
    summary = build_iad_training_input_audit_summary(rows)

    assert all(row["audit_status"] == "defensible" for row in rows)
    assert summary["training_input_ready"] is True


def test_build_iad_training_input_audit_rows_from_paths(tmp_path) -> None:
    """验证训练输入审计可从 JSONL 文件读取输入。"""
    relations_path = tmp_path / "relations.jsonl"
    _write_jsonl(relations_path, [_raw_pair("p1", 1, 1), _raw_pair("p2", 0, 0)])

    rows = build_iad_training_input_audit_rows_from_paths(relations_path)

    assert rows
    assert any(row["audit_status"] == "blocked_missing_feature_signal" for row in rows)


def test_write_iad_training_input_audit_outputs(tmp_path) -> None:
    """验证训练输入审计写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "iad_training_input_audit"
    rows = build_iad_training_input_audit_rows([_raw_pair("p1", 1, 1), _raw_pair("p2", 0, 0)])

    write_iad_training_input_audit_outputs(rows, output_dir)

    assert read_records(output_dir / "iad_training_input_audit.jsonl")
    assert read_records(output_dir / "iad_training_input_audit_summary.jsonl")
    assert (output_dir / "iad_training_input_audit.csv").exists()
    assert "# IAD-Risk Training Input Audit" in (output_dir / "iad_training_input_audit.md").read_text(encoding="utf-8")


def test_build_iad_training_input_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出训练输入审计。"""
    relations_path = tmp_path / "relations.jsonl"
    output_dir = tmp_path / "iad_training_input_audit"
    _write_jsonl(relations_path, [_raw_pair("p1", 1, 1), _raw_pair("p2", 0, 0)])

    command_build_iad_training_input_audit(Namespace(relations=str(relations_path), output_dir=str(output_dir)))

    assert (output_dir / "iad_training_input_audit.jsonl").exists()
    assert (output_dir / "iad_training_input_audit_summary.jsonl").exists()


def test_cli_includes_build_iad_training_input_audit_command() -> None:
    """验证 CLI 暴露 build-iad-training-input-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-iad-training-input-audit",
            "--relations",
            "outputs/iad_bench_open_v3_balanced_gold_source_heldout/iad_bench_pairs.jsonl",
            "--output-dir",
            "outputs/iad_training_input_audit_source_heldout",
        ]
    )

    assert args.command == "build-iad-training-input-audit"
    assert args.relations.endswith("iad_bench_pairs.jsonl")
