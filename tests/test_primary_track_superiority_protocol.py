"""测试主轨道优势判定协议。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_primary_track_superiority_protocol
from iad_sieve.evaluation.primary_track_superiority_protocol import (
    build_primary_track_superiority_protocol_rows,
    write_primary_track_superiority_protocol_outputs,
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


def _claim_gate_row() -> dict:
    """构造主轨道论文主张门禁记录。

    参数:
        无。

    返回:
        claim gate 记录。
    """
    return {
        "gate_id": "primary_track_claim_gate",
        "primary_track": "open_v3_scholarly_balanced_gold",
        "claim_gate_status": "blocked",
        "claim_allowed": False,
        "blocking_reasons": [
            "waiting_for_connection_fields",
            "missing_primary_track_models",
            "model_superiority_blocked",
        ],
    }


def _advanced_track_row() -> dict:
    """构造主轨道强模型摘要记录。

    参数:
        无。

    返回:
        advanced track summary 记录。
    """
    return {
        "evaluation_track": "open_v3_scholarly_balanced_gold",
        "track_status": "blocked",
        "ready_model_count": 0,
        "missing_required_count": 3,
        "missing_required_systems": [
            "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
            "roberta_pair_open_v3_scholarly_balanced_gold",
            "scincl_cosine_open_v3_scholarly_balanced_gold",
        ],
    }


def test_build_primary_track_superiority_protocol_rows_preregisters_effect_size_and_ci_rules() -> None:
    """验证主轨道优势判定协议预注册效果量、置信区间和主张边界。"""
    rows = build_primary_track_superiority_protocol_rows(
        primary_track_claim_gate_rows=[_claim_gate_row()],
        advanced_track_summary_rows=[_advanced_track_row()],
        model_superiority_summary_rows=[{"overall_superiority_status": "blocked", "sota_claim_allowed": False}],
    )
    by_id = {row["protocol_item_id"]: row for row in rows}

    assert by_id["protocol_summary"]["protocol_status"] == "blocked_waiting_for_primary_models"
    assert by_id["protocol_summary"]["primary_track"] == "open_v3_scholarly_balanced_gold"
    assert by_id["protocol_summary"]["required_system_count"] == 3
    assert by_id["protocol_summary"]["required_comparison_count"] == 2
    assert by_id["protocol_summary"]["minimum_f1_delta"] == 0.0
    assert by_id["protocol_summary"]["minimum_false_merge_reduction"] == 0.02
    assert by_id["protocol_summary"]["minimum_hard_negative_reduction"] == 0.05
    assert by_id["protocol_summary"]["requires_bootstrap_ci"] is True
    assert by_id["protocol_summary"]["missing_required_systems"] == [
        "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
        "roberta_pair_open_v3_scholarly_balanced_gold",
        "scincl_cosine_open_v3_scholarly_balanced_gold",
    ]
    assert by_id["iad_vs_scincl"]["baseline_system"] == "scincl_cosine_open_v3_scholarly_balanced_gold"
    assert by_id["iad_vs_roberta_pair"]["baseline_system"] == "roberta_pair_open_v3_scholarly_balanced_gold"
    assert by_id["iad_vs_scincl"]["acceptance_rule"] == (
        "same_work_f1_delta>=0.0; false_merge_rate_reduction>=0.02; "
        "hard_negative_false_merge_rate_reduction>=0.05; bootstrap_95ci_lower_bound>=0"
    )
    assert "不得仅凭均值提升" in by_id["iad_vs_roberta_pair"]["paper_claim_boundary"]
    assert "选择性报告" in by_id["protocol_summary"]["reviewer_zero_hypothesis"]


def test_write_primary_track_superiority_protocol_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证主轨道优势判定协议写出 JSONL、CSV、Markdown 和 summary。"""
    rows = build_primary_track_superiority_protocol_rows(
        primary_track_claim_gate_rows=[_claim_gate_row()],
        advanced_track_summary_rows=[_advanced_track_row()],
        model_superiority_summary_rows=[{"overall_superiority_status": "blocked", "sota_claim_allowed": False}],
    )
    output_dir = tmp_path / "primary_track_superiority_protocol"

    write_primary_track_superiority_protocol_outputs(rows, output_dir)

    assert read_records(output_dir / "primary_track_superiority_protocol.jsonl")[0]["protocol_item_id"] == "protocol_summary"
    assert (output_dir / "primary_track_superiority_protocol.csv").exists()
    markdown = (output_dir / "primary_track_superiority_protocol.md").read_text(encoding="utf-8")
    assert "# Primary Track Superiority Protocol" in markdown
    assert "bootstrap_95ci_lower_bound" in markdown
    summary = read_records(output_dir / "primary_track_superiority_protocol_summary.jsonl")[0]
    assert summary["primary_track"] == "open_v3_scholarly_balanced_gold"
    assert summary["protocol_status"] == "blocked_waiting_for_primary_models"
    assert summary["required_comparison_count"] == 2
    assert summary["claim_allowed_after_protocol"] is False


def test_build_primary_track_superiority_protocol_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出主轨道优势判定协议。"""
    claim_gate = tmp_path / "primary_track_claim_gate.jsonl"
    advanced_track = tmp_path / "advanced_model_evidence_track_summary.jsonl"
    superiority = tmp_path / "model_superiority_audit_summary.jsonl"
    output_dir = tmp_path / "primary_track_superiority_protocol"
    _write_jsonl(claim_gate, [_claim_gate_row()])
    _write_jsonl(advanced_track, [_advanced_track_row()])
    _write_jsonl(superiority, [{"overall_superiority_status": "blocked", "sota_claim_allowed": False}])

    command_build_primary_track_superiority_protocol(
        Namespace(
            primary_track_claim_gate=str(claim_gate),
            advanced_track_summary=str(advanced_track),
            model_superiority_summary=str(superiority),
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "primary_track_superiority_protocol_summary.jsonl").exists()
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-primary-track-superiority-protocol",
            "--primary-track-claim-gate",
            str(claim_gate),
            "--advanced-track-summary",
            str(advanced_track),
            "--model-superiority-summary",
            str(superiority),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_primary_track_superiority_protocol
