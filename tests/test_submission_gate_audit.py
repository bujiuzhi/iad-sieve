"""测试投稿门禁审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_submission_gate_audit
from iad_sieve.evaluation.submission_gate_audit import build_submission_gate_audit_rows, write_submission_gate_audit_outputs
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


def test_build_submission_gate_audit_rows_blocks_submission_when_advanced_outputs_missing() -> None:
    """验证强 baseline 输出缺失时投稿门禁为 blocked。"""
    readiness_rows = [
        {"gate_id": "overall_q2_b_readiness", "status": "needs_evidence", "severity": "high"},
        {"gate_id": "specter2_adapter_actual_model", "status": "needs_evidence", "severity": "high"},
    ]
    claim_rows = [{"claim_id": "state_of_the_art_superiority", "claim_status": "forbidden"}]
    depth_rows = [{"dimension_id": "advanced_baseline", "depth_status": "not_ready", "reviewer_risk_level": "high"}]
    remote_summary_rows = [{"all_outputs_valid": False, "missing_output_count": 14}]

    rows = build_submission_gate_audit_rows(readiness_rows, claim_rows, depth_rows, remote_summary_rows)
    by_gate = {row["submission_gate_id"]: row for row in rows}

    assert by_gate["overall_submission_gate"]["decision"] == "blocked"
    assert by_gate["overall_submission_gate"]["reviewer_risk_level"] == "high"
    assert "advanced_baseline" in by_gate["overall_submission_gate"]["blocking_reasons"]
    assert by_gate["advancedness_gate"]["decision"] == "blocked"
    assert by_gate["advancedness_gate"]["next_action"] == "完成 SPECTER2 adapter、LLM API baseline 与对应 bootstrap 后重建证据包。"
    assert by_gate["remote_output_gate"]["decision"] == "blocked"


def test_build_submission_gate_audit_rows_does_not_reask_ready_specter2_actions() -> None:
    """验证 SPECTER2 已 ready 时投稿门禁下一步聚焦剩余强基线缺口。"""
    readiness_rows = [
        {"gate_id": "overall_q2_b_readiness", "status": "needs_evidence", "severity": "high"},
        {"gate_id": "specter2_adapter_actual_model", "status": "evidence_ready", "severity": "high"},
        {"gate_id": "llm_pair_judge_api_model", "status": "needs_evidence", "severity": "high"},
        {"gate_id": "executed_strong_baselines", "status": "needs_evidence", "severity": "high"},
    ]
    claim_rows = [{"claim_id": "state_of_the_art_superiority", "claim_status": "forbidden"}]
    depth_rows = [
        {"dimension_id": "advanced_baseline", "depth_status": "not_ready", "reviewer_risk_level": "high"},
        {"dimension_id": "model_depth", "depth_status": "defensible", "reviewer_risk_level": "low"},
    ]
    remote_summary_rows = [{"all_outputs_valid": True, "missing_output_count": 0}]

    rows = build_submission_gate_audit_rows(readiness_rows, claim_rows, depth_rows, remote_summary_rows)
    by_gate = {row["submission_gate_id"]: row for row in rows}

    assert "SPECTER2 adapter" not in by_gate["advancedness_gate"]["next_action"]
    assert "LLM API baseline" in by_gate["advancedness_gate"]["next_action"]
    assert "SPECTER2 encoder 稳定性" not in by_gate["model_depth_gate"]["next_action"]


def test_build_submission_gate_audit_rows_blocks_source_bias_and_feature_leakage() -> None:
    """验证来源捷径和模型特征泄漏会阻断投稿门禁。"""
    readiness_rows = [{"gate_id": "overall_q2_b_readiness", "status": "evidence_ready", "severity": "high"}]
    claim_rows = [
        {"claim_id": "state_of_the_art_superiority", "claim_status": "supported"},
        {"claim_id": "q2_b_ready", "claim_status": "supported"},
    ]
    depth_rows = [
        {"dimension_id": "advanced_baseline", "depth_status": "defensible", "reviewer_risk_level": "medium"},
        {"dimension_id": "model_depth", "depth_status": "defensible", "reviewer_risk_level": "low"},
        {"dimension_id": "data_validity", "depth_status": "defensible", "reviewer_risk_level": "low"},
    ]
    remote_summary_rows = [{"all_outputs_valid": True, "missing_output_count": 0}]
    source_bias_summary_rows = [{"overall_source_bias_status": "high_risk", "high_risk_count": 3}]
    feature_guard_summary_rows = [{"overall_feature_guard_status": "high_risk", "violation_count": 2}]

    rows = build_submission_gate_audit_rows(
        readiness_rows,
        claim_rows,
        depth_rows,
        remote_summary_rows,
        source_bias_summary_rows=source_bias_summary_rows,
        feature_guard_summary_rows=feature_guard_summary_rows,
    )
    by_gate = {row["submission_gate_id"]: row for row in rows}

    assert by_gate["source_bias_gate"]["decision"] == "blocked"
    assert by_gate["model_feature_guard_gate"]["decision"] == "blocked"
    assert "source_bias_shortcut" in by_gate["overall_submission_gate"]["blocking_reasons"]
    assert "model_feature_leakage" in by_gate["overall_submission_gate"]["blocking_reasons"]


def test_build_submission_gate_audit_rows_blocks_provenance_imbalance() -> None:
    """验证 provenance 来源结构不平衡会阻断投稿门禁。"""
    readiness_rows = [{"gate_id": "overall_q2_b_readiness", "status": "evidence_ready", "severity": "high"}]
    claim_rows = [
        {"claim_id": "state_of_the_art_superiority", "claim_status": "supported"},
        {"claim_id": "q2_b_ready", "claim_status": "supported"},
    ]
    depth_rows = [
        {"dimension_id": "advanced_baseline", "depth_status": "defensible", "reviewer_risk_level": "medium"},
        {"dimension_id": "model_depth", "depth_status": "defensible", "reviewer_risk_level": "low"},
        {"dimension_id": "data_validity", "depth_status": "defensible", "reviewer_risk_level": "low"},
    ]
    remote_summary_rows = [{"all_outputs_valid": True, "missing_output_count": 0}]
    provenance_balance_summary_rows = [{"overall_provenance_balance_status": "blocked", "blocked_relation_count": 3, "high_risk_relation_count": 0}]

    rows = build_submission_gate_audit_rows(
        readiness_rows,
        claim_rows,
        depth_rows,
        remote_summary_rows,
        provenance_balance_summary_rows=provenance_balance_summary_rows,
    )
    by_gate = {row["submission_gate_id"]: row for row in rows}

    assert by_gate["provenance_balance_gate"]["decision"] == "blocked"
    assert "provenance_balance_blocked" in by_gate["overall_submission_gate"]["blocking_reasons"]


def test_build_submission_gate_audit_rows_blocks_training_input_not_ready() -> None:
    """验证 IAD-Risk 训练输入不可用会阻断投稿门禁。"""
    readiness_rows = [{"gate_id": "overall_q2_b_readiness", "status": "evidence_ready", "severity": "high"}]
    claim_rows = [
        {"claim_id": "state_of_the_art_superiority", "claim_status": "supported"},
        {"claim_id": "q2_b_ready", "claim_status": "supported"},
    ]
    depth_rows = [
        {"dimension_id": "advanced_baseline", "depth_status": "defensible", "reviewer_risk_level": "medium"},
        {"dimension_id": "model_depth", "depth_status": "defensible", "reviewer_risk_level": "low"},
        {"dimension_id": "data_validity", "depth_status": "defensible", "reviewer_risk_level": "low"},
    ]
    remote_summary_rows = [{"all_outputs_valid": True, "missing_output_count": 0}]
    training_input_summary_rows = [{"training_input_ready": False, "blocked_count": 4, "overall_training_input_status": "blocked"}]

    rows = build_submission_gate_audit_rows(
        readiness_rows,
        claim_rows,
        depth_rows,
        remote_summary_rows,
        training_input_summary_rows=training_input_summary_rows,
    )
    by_gate = {row["submission_gate_id"]: row for row in rows}

    assert by_gate["training_input_gate"]["decision"] == "blocked"
    assert by_gate["training_input_gate"]["reviewer_risk_level"] == "high"
    assert "training_input_not_ready" in by_gate["training_input_gate"]["blocking_reasons"]
    assert "training_input_not_ready" in by_gate["overall_submission_gate"]["blocking_reasons"]


def test_build_submission_gate_audit_rows_blocks_remote_connection_inputs() -> None:
    """验证远程连接字段或密钥未配置时投稿门禁明确阻断。"""
    readiness_rows = [{"gate_id": "overall_q2_b_readiness", "status": "evidence_ready", "severity": "high"}]
    claim_rows = [
        {"claim_id": "state_of_the_art_superiority", "claim_status": "supported"},
        {"claim_id": "q2_b_ready", "claim_status": "supported"},
    ]
    depth_rows = [
        {"dimension_id": "advanced_baseline", "depth_status": "defensible", "reviewer_risk_level": "medium"},
        {"dimension_id": "model_depth", "depth_status": "defensible", "reviewer_risk_level": "low"},
        {"dimension_id": "data_validity", "depth_status": "defensible", "reviewer_risk_level": "low"},
    ]
    remote_summary_rows = [{"all_outputs_valid": True, "missing_output_count": 0}]
    remote_connection_summary_rows = [
        {
            "all_connection_fields_ready": False,
            "all_remote_run_inputs_ready": False,
            "missing_required_field_count": 6,
            "blocked_secret_count": 1,
        }
    ]

    rows = build_submission_gate_audit_rows(
        readiness_rows,
        claim_rows,
        depth_rows,
        remote_summary_rows,
        remote_connection_summary_rows=remote_connection_summary_rows,
    )
    by_gate = {row["submission_gate_id"]: row for row in rows}

    assert by_gate["remote_connection_gate"]["decision"] == "blocked"
    assert by_gate["remote_connection_gate"]["reviewer_risk_level"] == "high"
    assert "remote_connection_profile" in by_gate["remote_connection_gate"]["blocking_reasons"]
    assert "remote_secret_configuration" in by_gate["remote_connection_gate"]["blocking_reasons"]
    assert "remote_connection_profile" in by_gate["overall_submission_gate"]["blocking_reasons"]
    assert "remote_secret_configuration" in by_gate["overall_submission_gate"]["blocking_reasons"]


def test_build_submission_gate_audit_rows_focuses_on_model_artifact_when_connection_fields_ready() -> None:
    """验证连接字段齐备但模型目录缺失时下一步只要求预置模型目录。"""
    readiness_rows = [{"gate_id": "overall_q2_b_readiness", "status": "needs_evidence", "severity": "high"}]
    claim_rows = [{"claim_id": "q2_b_ready", "claim_status": "forbidden"}]
    depth_rows = [{"dimension_id": "advanced_baseline", "depth_status": "not_ready", "reviewer_risk_level": "high"}]
    remote_summary_rows = [{"all_outputs_valid": False, "missing_output_count": 10}]
    remote_connection_summary_rows = [
        {
            "all_connection_fields_ready": True,
            "all_remote_run_inputs_ready": False,
            "missing_required_field_count": 0,
            "blocked_secret_count": 0,
            "missing_model_artifact_count": 1,
        }
    ]

    rows = build_submission_gate_audit_rows(
        readiness_rows,
        claim_rows,
        depth_rows,
        remote_summary_rows,
        remote_connection_summary_rows=remote_connection_summary_rows,
    )
    by_gate = {row["submission_gate_id"]: row for row in rows}
    remote_gate = by_gate["remote_connection_gate"]

    assert remote_gate["decision"] == "blocked"
    assert remote_gate["blocking_reasons"] == ["remote_model_artifact"]
    assert "模型目录" in remote_gate["evidence_status"]
    assert "outputs/models/local_llm_judge" in remote_gate["next_action"]
    assert "remote_host" not in remote_gate["next_action"]
    assert "remote_connection_profile" not in by_gate["overall_submission_gate"]["blocking_reasons"]
    assert "remote_model_artifact" in by_gate["overall_submission_gate"]["blocking_reasons"]


def test_build_submission_gate_audit_rows_blocks_unaccepted_remote_result_claim_gates() -> None:
    """验证远程输出未被论文门禁接收时仍阻断投稿。"""
    readiness_rows = [
        {"gate_id": "overall_q2_b_readiness", "status": "evidence_ready", "severity": "high"},
        {"gate_id": "specter2_adapter_actual_model", "status": "evidence_ready", "severity": "high"},
        {"gate_id": "llm_pair_judge_api_model", "status": "evidence_ready", "severity": "high"},
        {"gate_id": "executed_strong_baselines", "status": "evidence_ready", "severity": "high"},
    ]
    claim_rows = [
        {"claim_id": "state_of_the_art_superiority", "claim_status": "supported"},
        {"claim_id": "q2_b_ready", "claim_status": "supported"},
    ]
    depth_rows = [
        {"dimension_id": "advanced_baseline", "depth_status": "defensible", "reviewer_risk_level": "medium"},
        {"dimension_id": "model_depth", "depth_status": "defensible", "reviewer_risk_level": "low"},
        {"dimension_id": "data_validity", "depth_status": "defensible", "reviewer_risk_level": "low"},
    ]
    remote_summary_rows = [{"all_outputs_valid": True, "missing_output_count": 0}]
    remote_result_acceptance_summary_rows = [
        {
            "all_claim_gates_accepted": False,
            "accepted_gate_count": 0,
            "blocked_gate_count": 7,
            "missing_output_count": 47,
        }
    ]

    rows = build_submission_gate_audit_rows(
        readiness_rows,
        claim_rows,
        depth_rows,
        remote_summary_rows,
        remote_result_acceptance_summary_rows=remote_result_acceptance_summary_rows,
    )
    by_gate = {row["submission_gate_id"]: row for row in rows}

    assert by_gate["remote_result_acceptance_gate"]["decision"] == "blocked"
    assert "remote_result_acceptance" in by_gate["overall_submission_gate"]["blocking_reasons"]
    assert "远程结果尚未被论文门禁接收" in by_gate["remote_result_acceptance_gate"]["evidence_status"]


def test_build_submission_gate_audit_rows_allows_submission_when_all_gates_ready() -> None:
    """验证所有关键门禁通过时投稿门禁为 ready_for_draft_submission。"""
    readiness_rows = [
        {"gate_id": "overall_q2_b_readiness", "status": "evidence_ready", "severity": "high"},
        {"gate_id": "specter2_adapter_actual_model", "status": "evidence_ready", "severity": "high"},
        {"gate_id": "llm_pair_judge_api_model", "status": "evidence_ready", "severity": "high"},
        {"gate_id": "executed_strong_baselines", "status": "evidence_ready", "severity": "high"},
        {"gate_id": "venue_readiness", "status": "evidence_ready", "severity": "high"},
    ]
    claim_rows = [
        {"claim_id": "state_of_the_art_superiority", "claim_status": "supported"},
        {"claim_id": "q2_b_ready", "claim_status": "supported"},
    ]
    depth_rows = [
        {"dimension_id": "advanced_baseline", "depth_status": "defensible", "reviewer_risk_level": "medium"},
        {"dimension_id": "model_depth", "depth_status": "defensible", "reviewer_risk_level": "low"},
        {"dimension_id": "data_validity", "depth_status": "defensible", "reviewer_risk_level": "low"},
    ]
    remote_summary_rows = [{"all_outputs_valid": True, "missing_output_count": 0}]

    rows = build_submission_gate_audit_rows(readiness_rows, claim_rows, depth_rows, remote_summary_rows)
    by_gate = {row["submission_gate_id"]: row for row in rows}

    assert by_gate["overall_submission_gate"]["decision"] == "ready_for_draft_submission"
    assert by_gate["overall_submission_gate"]["blocking_reasons"] == []


def test_write_submission_gate_audit_outputs_writes_jsonl_csv_markdown_and_summary(tmp_path) -> None:
    """验证投稿门禁审计写出 JSONL、CSV、Markdown 和 summary。"""
    rows = [
        {
            "submission_gate_id": "overall_submission_gate",
            "decision": "blocked",
            "reviewer_risk_level": "high",
            "blocking_reasons": ["advanced_baseline"],
            "next_action": "补齐强 baseline。",
        }
    ]
    output_dir = tmp_path / "submission_gate_audit"

    write_submission_gate_audit_outputs(rows, output_dir)

    assert read_records(output_dir / "submission_gate_audit.jsonl")[0]["decision"] == "blocked"
    assert (output_dir / "submission_gate_audit.csv").exists()
    assert "# Submission Gate Audit" in (output_dir / "submission_gate_audit.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "submission_gate_audit_summary.jsonl")[0]
    assert summary["submission_decision"] == "blocked"


def test_build_submission_gate_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出投稿门禁审计。"""
    readiness = tmp_path / "journal_readiness.jsonl"
    claim = tmp_path / "paper_claim_audit.jsonl"
    depth = tmp_path / "research_depth_audit.jsonl"
    remote_summary = tmp_path / "remote_output_validation_summary.jsonl"
    output_dir = tmp_path / "submission_gate_audit"
    _write_jsonl(readiness, [{"gate_id": "overall_q2_b_readiness", "status": "needs_evidence", "severity": "high"}])
    _write_jsonl(claim, [{"claim_id": "q2_b_ready", "claim_status": "forbidden"}])
    _write_jsonl(depth, [{"dimension_id": "advanced_baseline", "depth_status": "not_ready", "reviewer_risk_level": "high"}])
    _write_jsonl(remote_summary, [{"all_outputs_valid": False, "missing_output_count": 14}])

    command_build_submission_gate_audit(
        Namespace(
            readiness_reports=[str(readiness)],
            claim_audits=[str(claim)],
            research_depth_audits=[str(depth)],
            remote_output_summaries=[str(remote_summary)],
            remote_result_acceptance_summaries=[],
            remote_connection_summaries=[],
            source_bias_summaries=[],
            feature_guard_summaries=[],
            provenance_balance_summaries=[],
            training_input_summaries=[],
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "submission_gate_audit.jsonl")
    assert (output_dir / "submission_gate_audit.md").exists()


def test_cli_includes_build_submission_gate_audit_command() -> None:
    """验证 CLI 暴露 build-submission-gate-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-submission-gate-audit",
            "--readiness-reports",
            "outputs/journal_readiness_fixture/journal_readiness.jsonl",
            "--claim-audits",
            "outputs/paper_claim_audit_fixture/paper_claim_audit.jsonl",
            "--research-depth-audits",
            "outputs/research_depth_audit_fixture/research_depth_audit.jsonl",
            "--remote-output-summaries",
            "outputs/remote_output_validation_fixture/remote_output_validation_summary.jsonl",
            "--remote-connection-summaries",
            "outputs/remote_connection_pack_fixture/remote_connection_pack_summary.jsonl",
            "--remote-result-acceptance-summaries",
            "outputs/remote_result_acceptance_fixture/remote_result_acceptance_summary.jsonl",
            "--source-bias-summaries",
            "outputs/iad_bench_source_bias_diagnostic_fixture/iad_bench_source_bias_diagnostic_summary.jsonl",
            "--feature-guard-summaries",
            "outputs/iad_model_feature_guard_fixture/iad_model_feature_guard_summary.jsonl",
            "--provenance-balance-summaries",
            "outputs/iad_bench_provenance_balance_plan_fixture/iad_bench_provenance_balance_plan_summary.jsonl",
            "--training-input-summaries",
            "outputs/iad_training_input_audit_source_heldout/iad_training_input_audit_summary.jsonl",
            "--output-dir",
            "outputs/submission_gate_audit_fixture",
        ]
    )

    assert args.command == "build-submission-gate-audit"
    assert args.remote_output_summaries == ["outputs/remote_output_validation_fixture/remote_output_validation_summary.jsonl"]
    assert args.remote_result_acceptance_summaries == ["outputs/remote_result_acceptance_fixture/remote_result_acceptance_summary.jsonl"]
    assert args.remote_connection_summaries == ["outputs/remote_connection_pack_fixture/remote_connection_pack_summary.jsonl"]
    assert args.source_bias_summaries == ["outputs/iad_bench_source_bias_diagnostic_fixture/iad_bench_source_bias_diagnostic_summary.jsonl"]
    assert args.feature_guard_summaries == ["outputs/iad_model_feature_guard_fixture/iad_model_feature_guard_summary.jsonl"]
    assert args.provenance_balance_summaries == ["outputs/iad_bench_provenance_balance_plan_fixture/iad_bench_provenance_balance_plan_summary.jsonl"]
    assert args.training_input_summaries == ["outputs/iad_training_input_audit_source_heldout/iad_training_input_audit_summary.jsonl"]
