"""测试主轨道论文主张门禁。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_primary_track_claim_gate
from iad_sieve.evaluation.primary_track_claim_gate import (
    build_primary_track_claim_gate_rows,
    write_primary_track_claim_gate_outputs,
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


def _handoff_row() -> dict:
    """构造主轨道远程交接记录。

    参数:
        无。

    返回:
        handoff 记录。
    """
    return {
        "handoff_id": "primary_track_remote_handoff",
        "handoff_status": "waiting_for_connection_fields",
        "primary_track": "open_v3_scholarly_balanced_gold",
        "connection_fields": ["remote_host", "remote_port", "remote_user", "ssh_key_path", "remote_workspace", "conda_env"],
        "connection_field_count": 6,
        "missing_primary_secret_names": [],
        "deferred_global_secret_names": ["OPENAI_API_KEY"],
        "remote_task_order": [
            "run_scincl_baseline_open_v3_scholarly_balanced_gold",
            "run_roberta_pair_baseline_open_v3_scholarly_balanced_gold",
            "run_scincl_provenance_blind_iad_risk_transformer_open_v3_scholarly_balanced_gold",
        ],
        "paper_claim_boundary": "主轨道远程输出未回传并通过验收前，不能声称强模型闭环。",
    }


def test_build_primary_track_claim_gate_rows_blocks_overclaiming_until_main_track_closes() -> None:
    """验证主轨道未闭环时锁定强创新、SOTA 和 Q2/B 主张。"""
    rows = build_primary_track_claim_gate_rows(
        primary_remote_handoff_rows=[_handoff_row()],
        advanced_track_summary_rows=[
            {
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
        ],
        model_superiority_summary_rows=[
            {
                "overall_superiority_status": "blocked",
                "sota_claim_allowed": False,
                "blocked_missing_comparison_count": 1,
            }
        ],
        innovation_depth_summary_rows=[
            {
                "overall_innovation_depth_status": "blocked",
                "q2_b_innovation_claim_allowed": False,
                "blocked_count": 4,
                "blocking_reasons": ["missing_strong_comparison", "provenance_blind_missing", "source_heldout_missing"],
            }
        ],
        q2b_acceptance_summary_rows=[
            {
                "q2b_acceptance_ready": False,
                "blocked_gate_count": 8,
                "highest_priority_blocker": "remote_reproducibility_acceptance",
            }
        ],
    )
    row = rows[0]

    assert row["gate_id"] == "primary_track_claim_gate"
    assert row["primary_track"] == "open_v3_scholarly_balanced_gold"
    assert row["claim_gate_status"] == "blocked"
    assert row["claim_allowed"] is False
    assert row["connection_field_count"] == 6
    assert row["missing_primary_secret_count"] == 0
    assert row["ready_model_count"] == 0
    assert row["missing_required_system_count"] == 3
    assert row["missing_required_systems"] == [
        "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
        "roberta_pair_open_v3_scholarly_balanced_gold",
        "scincl_cosine_open_v3_scholarly_balanced_gold",
    ]
    assert row["blocking_reasons"] == [
        "waiting_for_connection_fields",
        "missing_primary_track_models",
        "model_superiority_blocked",
        "innovation_depth_blocked",
        "q2b_acceptance_blocked",
    ]
    assert "只能写主轨道交接已就绪" in row["allowed_claim_boundary"]
    assert "不得声称 SOTA" in row["forbidden_claim_boundary"]
    assert "新 Transformer 架构" in row["forbidden_claim_boundary"]
    assert "OpenAlex silver 等同 gold" in row["forbidden_claim_boundary"]
    assert "提供 6 个连接字段" in row["next_action"]


def test_write_primary_track_claim_gate_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证主轨道论文主张门禁写出 JSONL、CSV、Markdown 和 summary。"""
    rows = build_primary_track_claim_gate_rows(
        primary_remote_handoff_rows=[_handoff_row()],
        advanced_track_summary_rows=[{"evaluation_track": "open_v3_scholarly_balanced_gold", "track_status": "blocked", "missing_required_count": 1}],
        model_superiority_summary_rows=[{"overall_superiority_status": "blocked", "sota_claim_allowed": False}],
        innovation_depth_summary_rows=[{"overall_innovation_depth_status": "blocked", "q2_b_innovation_claim_allowed": False}],
        q2b_acceptance_summary_rows=[{"q2b_acceptance_ready": False, "blocked_gate_count": 1}],
    )
    output_dir = tmp_path / "primary_track_claim_gate"

    write_primary_track_claim_gate_outputs(rows, output_dir)

    assert read_records(output_dir / "primary_track_claim_gate.jsonl")[0]["claim_gate_status"] == "blocked"
    assert (output_dir / "primary_track_claim_gate.csv").exists()
    markdown = (output_dir / "primary_track_claim_gate.md").read_text(encoding="utf-8")
    assert "# Primary Track Claim Gate" in markdown
    assert "不得声称" in markdown
    summary = read_records(output_dir / "primary_track_claim_gate_summary.jsonl")[0]
    assert summary["primary_track"] == "open_v3_scholarly_balanced_gold"
    assert summary["claim_gate_status"] == "blocked"
    assert summary["claim_allowed"] is False
    assert summary["blocking_reason_count"] >= 1


def test_build_primary_track_claim_gate_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出主轨道论文主张门禁。"""
    handoff = tmp_path / "primary_remote_handoff.jsonl"
    advanced_track = tmp_path / "advanced_model_evidence_track_summary.jsonl"
    superiority = tmp_path / "model_superiority_audit_summary.jsonl"
    innovation = tmp_path / "innovation_depth_stress_test_summary.jsonl"
    q2b = tmp_path / "q2b_acceptance_rubric_summary.jsonl"
    output_dir = tmp_path / "primary_track_claim_gate"
    _write_jsonl(handoff, [_handoff_row()])
    _write_jsonl(advanced_track, [{"evaluation_track": "open_v3_scholarly_balanced_gold", "track_status": "ready", "ready_model_count": 3, "missing_required_count": 0}])
    _write_jsonl(superiority, [{"overall_superiority_status": "ready", "sota_claim_allowed": True}])
    _write_jsonl(innovation, [{"overall_innovation_depth_status": "ready", "q2_b_innovation_claim_allowed": True}])
    _write_jsonl(q2b, [{"q2b_acceptance_ready": True, "blocked_gate_count": 0}])

    command_build_primary_track_claim_gate(
        Namespace(
            primary_remote_handoff=str(handoff),
            advanced_track_summary=str(advanced_track),
            model_superiority_summary=str(superiority),
            innovation_depth_summary=str(innovation),
            q2b_acceptance_summary=str(q2b),
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "primary_track_claim_gate_summary.jsonl").exists()
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-primary-track-claim-gate",
            "--primary-remote-handoff",
            str(handoff),
            "--advanced-track-summary",
            str(advanced_track),
            "--model-superiority-summary",
            str(superiority),
            "--innovation-depth-summary",
            str(innovation),
            "--q2b-acceptance-summary",
            str(q2b),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_primary_track_claim_gate
