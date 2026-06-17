"""测试二区/B类最终目标完成度审计。"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from iad_sieve.cli import build_parser, command_build_q2b_completion_audit
from iad_sieve.evaluation.q2b_completion_audit import (
    build_q2b_completion_audit_rows,
    build_q2b_completion_audit_rows_from_paths,
    write_q2b_completion_audit_outputs,
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


def test_build_q2b_completion_audit_rows_blocks_when_core_evidence_missing() -> None:
    """验证强模型、远程连接和审稿回应未闭环时最终目标保持 blocked。"""
    rows = build_q2b_completion_audit_rows(
        submission_summary_rows=[
            {
                "submission_decision": "blocked",
                "blocking_reasons": ["advanced_baseline", "remote_connection_profile"],
            }
        ],
        q2b_summary_rows=[
            {
                "q2_b_ready": False,
                "blocked_action_count": 38,
                "external_input_count": 7,
            }
        ],
        reviewer_response_summary_rows=[
            {
                "do_not_answer_as_claim_count": 4,
                "must_not_claim_count": 6,
                "limited_answer_count": 4,
            }
        ],
        remote_connection_summary_rows=[
            {
                "all_connection_fields_ready": False,
                "all_remote_run_inputs_ready": False,
                "missing_required_field_count": 6,
                "blocked_secret_count": 1,
            }
        ],
        remote_result_acceptance_summary_rows=[
            {
                "all_claim_gates_accepted": False,
                "blocked_gate_count": 7,
                "missing_output_count": 47,
            }
        ],
        innovation_depth_summary_rows=[
            {
                "overall_innovation_depth_status": "blocked",
                "blocked_count": 3,
                "q2_b_innovation_claim_allowed": False,
                "blocking_reasons": ["missing_strong_comparison"],
            }
        ],
        advanced_model_summary_rows=[
            {
                "missing_required_count": 10,
                "ready_actual_model_count": 4,
            }
        ],
        split_readiness_summary_rows=[
            {
                "overall_split_readiness": "blocked",
                "blocked_count": 1,
            }
        ],
        training_input_summary_rows=[
            {
                "training_input_ready": False,
                "blocked_count": 4,
                "overall_training_input_status": "blocked",
            }
        ],
    )

    by_id = {row["criterion_id"]: row for row in rows}

    assert by_id["remote_execution_readiness"]["status"] == "blocked"
    assert by_id["remote_result_acceptance_closure"]["status"] == "blocked"
    assert by_id["innovation_depth_closure"]["status"] == "blocked"
    assert "missing_strong_comparison" in by_id["innovation_depth_closure"]["blocking_reasons"]
    assert "remote_result_acceptance" in by_id["remote_result_acceptance_closure"]["blocking_reasons"]
    assert "remote_connection_profile" in by_id["remote_execution_readiness"]["blocking_reasons"]
    assert by_id["advanced_model_closure"]["status"] == "blocked"
    assert by_id["model_training_input_readiness"]["status"] == "blocked"
    assert "training_input_not_ready" in by_id["model_training_input_readiness"]["blocking_reasons"]
    assert by_id["reviewer_response_safety"]["status"] == "blocked"
    assert by_id["q2b_action_closure"]["status"] == "blocked"
    assert by_id["final_submission_gate"]["status"] == "blocked"
    assert by_id["q2b_final_goal"]["status"] == "blocked"
    assert "不能声称已经达到二区/B类" in by_id["q2b_final_goal"]["paper_claim_boundary"]


def test_build_q2b_completion_audit_rows_omits_stale_connection_profile_action() -> None:
    """验证连接字段已齐备时远程审计不再提示补 profile。"""
    rows = build_q2b_completion_audit_rows(
        submission_summary_rows=[{"submission_decision": "blocked"}],
        q2b_summary_rows=[{"q2_b_ready": False, "blocked_action_count": 1, "external_input_count": 1}],
        reviewer_response_summary_rows=[{"do_not_answer_as_claim_count": 0, "must_not_claim_count": 0, "limited_answer_count": 0}],
        remote_connection_summary_rows=[
            {
                "all_connection_fields_ready": True,
                "all_remote_run_inputs_ready": False,
                "missing_required_field_count": 0,
                "blocked_secret_count": 1,
            }
        ],
        remote_result_acceptance_summary_rows=[{"all_claim_gates_accepted": False, "blocked_gate_count": 1, "missing_output_count": 1}],
        innovation_depth_summary_rows=[{"overall_innovation_depth_status": "blocked", "blocked_count": 1}],
        advanced_model_summary_rows=[{"missing_required_count": 1, "ready_actual_model_count": 0}],
        split_readiness_summary_rows=[{"overall_split_readiness": "defensible", "blocked_count": 0}],
        training_input_summary_rows=[{"training_input_ready": True, "blocked_count": 0, "overall_training_input_status": "defensible"}],
    )

    remote_row = {row["criterion_id"]: row for row in rows}["remote_execution_readiness"]

    assert remote_row["status"] == "blocked"
    assert "remote_connection_profile" not in remote_row["blocking_reasons"]
    assert "连接字段已齐备" in remote_row["next_action"]
    assert "补齐远程连接 profile" not in remote_row["next_action"]


def test_build_q2b_completion_audit_rows_accepts_limited_nonclaim_boundaries() -> None:
    """验证限制性边界不是 unsafe claim 时不阻塞最终目标。"""
    rows = build_q2b_completion_audit_rows(
        submission_summary_rows=[{"submission_decision": "ready_for_draft_submission"}],
        q2b_summary_rows=[{"q2_b_ready": True, "blocked_action_count": 0, "external_input_count": 0}],
        reviewer_response_summary_rows=[
            {
                "do_not_answer_as_claim_count": 0,
                "must_not_claim_count": 2,
                "unsafe_must_not_claim_count": 0,
                "limitation_boundary_count": 2,
                "limited_answer_count": 2,
            }
        ],
        remote_connection_summary_rows=[
            {
                "all_connection_fields_ready": True,
                "all_remote_run_inputs_ready": True,
                "missing_required_field_count": 0,
                "blocked_secret_count": 0,
            }
        ],
        remote_result_acceptance_summary_rows=[{"all_claim_gates_accepted": True, "blocked_gate_count": 0, "missing_output_count": 0}],
        innovation_depth_summary_rows=[{"overall_innovation_depth_status": "ready", "blocked_count": 0, "q2_b_innovation_claim_allowed": True}],
        advanced_model_summary_rows=[{"missing_required_count": 0, "ready_actual_model_count": 8}],
        split_readiness_summary_rows=[{"overall_split_readiness": "defensible", "blocked_count": 0}],
        split_readiness_audit_rows=[
            {"dimension_id": "random_split_coverage", "audit_status": "defensible"},
            {"dimension_id": "source_held_out_readiness", "audit_status": "defensible"},
            {"dimension_id": "pair_leakage_guard", "audit_status": "defensible"},
            {"dimension_id": "topic_held_out_readiness", "audit_status": "defensible"},
        ],
        training_input_summary_rows=[{"training_input_ready": True, "blocked_count": 0, "overall_training_input_status": "defensible"}],
    )
    by_id = {row["criterion_id"]: row for row in rows}

    assert by_id["reviewer_response_safety"]["status"] == "ready"
    assert "limitation_boundary_count=2" in by_id["reviewer_response_safety"]["current_evidence"]
    assert by_id["q2b_final_goal"]["status"] == "ready"


def test_build_q2b_completion_audit_rows_treats_only_topic_holdout_gap_as_conditional() -> None:
    """验证只有 topic-held-out 缺口时泛化完成度为 conditional。"""
    rows = build_q2b_completion_audit_rows(
        submission_summary_rows=[{"submission_decision": "ready_for_draft_submission"}],
        q2b_summary_rows=[{"q2_b_ready": True, "blocked_action_count": 0, "external_input_count": 0}],
        reviewer_response_summary_rows=[
            {
                "do_not_answer_as_claim_count": 0,
                "must_not_claim_count": 0,
                "limited_answer_count": 0,
            }
        ],
        remote_connection_summary_rows=[
            {
                "all_connection_fields_ready": True,
                "all_remote_run_inputs_ready": True,
                "missing_required_field_count": 0,
                "blocked_secret_count": 0,
            }
        ],
        remote_result_acceptance_summary_rows=[{"all_claim_gates_accepted": True, "blocked_gate_count": 0, "missing_output_count": 0}],
        innovation_depth_summary_rows=[{"overall_innovation_depth_status": "ready", "blocked_count": 0, "q2_b_innovation_claim_allowed": True}],
        advanced_model_summary_rows=[{"missing_required_count": 0, "ready_actual_model_count": 8}],
        split_readiness_summary_rows=[{"overall_split_readiness": "blocked", "blocked_count": 1}],
        split_readiness_audit_rows=[
            {"dimension_id": "random_split_coverage", "audit_status": "defensible"},
            {"dimension_id": "source_held_out_readiness", "audit_status": "defensible"},
            {"dimension_id": "pair_leakage_guard", "audit_status": "defensible"},
            {"dimension_id": "topic_held_out_readiness", "audit_status": "blocked"},
        ],
        training_input_summary_rows=[{"training_input_ready": True, "blocked_count": 0, "overall_training_input_status": "defensible"}],
    )

    by_id = {row["criterion_id"]: row for row in rows}

    assert by_id["generalization_split_readiness"]["status"] == "conditional"
    assert by_id["generalization_split_readiness"]["blocking_reasons"] == ["topic_held_out_deferred"]
    assert "不能声称跨 topic 泛化" in by_id["generalization_split_readiness"]["paper_claim_boundary"]
    assert by_id["q2b_final_goal"]["status"] == "conditional"


def test_build_q2b_completion_audit_rows_merges_split_evidence_across_datasets() -> None:
    """验证多套 split 审计可分别提供 source-held-out 与 topic-held-out 证据。"""
    rows = build_q2b_completion_audit_rows(
        submission_summary_rows=[{"submission_decision": "ready_for_draft_submission"}],
        q2b_summary_rows=[{"q2_b_ready": True, "blocked_action_count": 0, "external_input_count": 0}],
        reviewer_response_summary_rows=[
            {
                "do_not_answer_as_claim_count": 0,
                "must_not_claim_count": 0,
                "limited_answer_count": 0,
            }
        ],
        remote_connection_summary_rows=[
            {
                "all_connection_fields_ready": True,
                "all_remote_run_inputs_ready": True,
                "missing_required_field_count": 0,
                "blocked_secret_count": 0,
            }
        ],
        remote_result_acceptance_summary_rows=[{"all_claim_gates_accepted": True, "blocked_gate_count": 0, "missing_output_count": 0}],
        innovation_depth_summary_rows=[{"overall_innovation_depth_status": "ready", "blocked_count": 0, "q2_b_innovation_claim_allowed": True}],
        advanced_model_summary_rows=[{"missing_required_count": 0, "ready_actual_model_count": 8}],
        split_readiness_summary_rows=[{"overall_split_readiness": "blocked", "blocked_count": 1}],
        split_readiness_audit_rows=[
            {"dimension_id": "random_split_coverage", "audit_status": "defensible", "evidence_scope": "balanced_gold"},
            {"dimension_id": "source_held_out_readiness", "audit_status": "defensible", "evidence_scope": "balanced_gold"},
            {"dimension_id": "pair_leakage_guard", "audit_status": "defensible", "evidence_scope": "balanced_gold"},
            {"dimension_id": "topic_held_out_readiness", "audit_status": "blocked", "evidence_scope": "balanced_gold"},
            {"dimension_id": "source_held_out_readiness", "audit_status": "blocked", "evidence_scope": "multi_topic_silver"},
            {"dimension_id": "topic_held_out_readiness", "audit_status": "defensible", "evidence_scope": "multi_topic_silver"},
            {"dimension_id": "pair_leakage_guard", "audit_status": "defensible", "evidence_scope": "multi_topic_silver"},
        ],
        training_input_summary_rows=[{"training_input_ready": True, "blocked_count": 0, "overall_training_input_status": "defensible"}],
    )

    by_id = {row["criterion_id"]: row for row in rows}

    assert by_id["generalization_split_readiness"]["status"] == "ready"
    assert "topic_heldout_deferred" not in by_id["generalization_split_readiness"]["blocking_reasons"]
    assert "topic_held_out_readiness=defensible" in by_id["generalization_split_readiness"]["current_evidence"]
    assert by_id["q2b_final_goal"]["status"] == "ready"


def test_build_q2b_completion_audit_rows_treats_stratified_blend_as_conditional() -> None:
    """验证 gold/silver 分层诊断不能替代 source-held-out 泛化证据。"""
    rows = build_q2b_completion_audit_rows(
        submission_summary_rows=[{"submission_decision": "ready_for_draft_submission"}],
        q2b_summary_rows=[{"q2_b_ready": True, "blocked_action_count": 0, "external_input_count": 0}],
        reviewer_response_summary_rows=[{"do_not_answer_as_claim_count": 0, "must_not_claim_count": 0, "limited_answer_count": 0}],
        remote_connection_summary_rows=[{"all_connection_fields_ready": True, "all_remote_run_inputs_ready": True, "blocked_secret_count": 0}],
        remote_result_acceptance_summary_rows=[{"all_claim_gates_accepted": True, "blocked_gate_count": 0, "missing_output_count": 0}],
        innovation_depth_summary_rows=[{"overall_innovation_depth_status": "ready", "blocked_count": 0, "q2_b_innovation_claim_allowed": True}],
        advanced_model_summary_rows=[{"missing_required_count": 0, "ready_actual_model_count": 8}],
        split_readiness_summary_rows=[{"overall_split_readiness": "defensible", "blocked_count": 0}],
        split_readiness_audit_rows=[
            {"dimension_id": "random_split_coverage", "audit_status": "defensible"},
            {"dimension_id": "source_held_out_readiness", "audit_status": "defensible"},
            {"dimension_id": "pair_leakage_guard", "audit_status": "defensible"},
        ],
        training_input_summary_rows=[{"training_input_ready": True, "blocked_count": 0, "overall_training_input_status": "defensible"}],
        split_evaluation_summary_rows=[
            {
                "overall_split_evaluation_status": "stratified_blend_diagnostic_only",
                "source_heldout_full_iad_ready": False,
                "limited_source_heldout_count": 0,
                "limited_stratified_blend_count": 1,
                "blocked_count": 0,
                "missing_eval_split_count": 0,
            }
        ],
    )

    by_id = {row["criterion_id"]: row for row in rows}

    assert by_id["iad_risk_split_evaluation_readiness"]["status"] == "conditional"
    assert "stratified_blend_diagnostic_only" in by_id["iad_risk_split_evaluation_readiness"]["blocking_reasons"]
    assert "gold/silver 分层诊断不能写成 source-held-out" in by_id["iad_risk_split_evaluation_readiness"]["paper_claim_boundary"]
    assert by_id["q2b_final_goal"]["status"] == "conditional"


def test_build_q2b_completion_audit_rows_blocks_missing_source_heldout_relation_coverage() -> None:
    """验证 source-held-out 缺少核心 IAD 关系覆盖时阻断最终目标。"""
    rows = build_q2b_completion_audit_rows(
        submission_summary_rows=[{"submission_decision": "ready_for_draft_submission"}],
        q2b_summary_rows=[{"q2_b_ready": True, "blocked_action_count": 0, "external_input_count": 0}],
        reviewer_response_summary_rows=[{"do_not_answer_as_claim_count": 0, "must_not_claim_count": 0, "limited_answer_count": 0}],
        remote_connection_summary_rows=[{"all_connection_fields_ready": True, "all_remote_run_inputs_ready": True, "blocked_secret_count": 0}],
        remote_result_acceptance_summary_rows=[{"all_claim_gates_accepted": True, "blocked_gate_count": 0, "missing_output_count": 0}],
        innovation_depth_summary_rows=[{"overall_innovation_depth_status": "ready", "blocked_count": 0, "q2_b_innovation_claim_allowed": True}],
        advanced_model_summary_rows=[{"missing_required_count": 0, "ready_actual_model_count": 8}],
        split_readiness_summary_rows=[{"overall_split_readiness": "defensible", "blocked_count": 0}],
        split_readiness_audit_rows=[
            {"dimension_id": "random_split_coverage", "audit_status": "defensible"},
            {"dimension_id": "source_held_out_readiness", "audit_status": "defensible"},
            {"dimension_id": "pair_leakage_guard", "audit_status": "defensible"},
        ],
        training_input_summary_rows=[{"training_input_ready": True, "blocked_count": 0, "overall_training_input_status": "defensible"}],
        source_heldout_coverage_summary_rows=[
            {
                "source_heldout_full_iad_data_ready": False,
                "blocked_relation_count": 1,
                "missing_relation_labels": ["agenda_non_identity"],
                "highest_priority_blocker": "agenda_non_identity_source_heldout_missing",
            }
        ],
    )

    by_id = {row["criterion_id"]: row for row in rows}

    assert by_id["iad_source_heldout_data_coverage"]["status"] == "blocked"
    assert "source_heldout_relation_coverage_missing" in by_id["iad_source_heldout_data_coverage"]["blocking_reasons"]
    assert "agenda_non_identity_source_heldout_missing" in by_id["iad_source_heldout_data_coverage"]["blocking_reasons"]
    assert by_id["q2b_final_goal"]["status"] == "blocked"


def test_build_q2b_completion_audit_rows_accepts_any_ready_source_heldout_coverage() -> None:
    """验证多个 source-held-out 覆盖摘要中存在 ready 时解除数据覆盖阻塞。"""
    rows = build_q2b_completion_audit_rows(
        submission_summary_rows=[{"submission_decision": "ready_for_draft_submission"}],
        q2b_summary_rows=[{"q2_b_ready": True, "blocked_action_count": 0, "external_input_count": 0}],
        reviewer_response_summary_rows=[{"do_not_answer_as_claim_count": 0, "must_not_claim_count": 0, "limited_answer_count": 0}],
        remote_connection_summary_rows=[{"all_connection_fields_ready": True, "all_remote_run_inputs_ready": True, "blocked_secret_count": 0}],
        remote_result_acceptance_summary_rows=[{"all_claim_gates_accepted": True, "blocked_gate_count": 0, "missing_output_count": 0}],
        innovation_depth_summary_rows=[{"overall_innovation_depth_status": "ready", "blocked_count": 0, "q2_b_innovation_claim_allowed": True}],
        advanced_model_summary_rows=[{"missing_required_count": 0, "ready_actual_model_count": 8}],
        split_readiness_summary_rows=[{"overall_split_readiness": "defensible", "blocked_count": 0}],
        split_readiness_audit_rows=[
            {"dimension_id": "random_split_coverage", "audit_status": "defensible"},
            {"dimension_id": "source_held_out_readiness", "audit_status": "defensible"},
            {"dimension_id": "pair_leakage_guard", "audit_status": "defensible"},
        ],
        training_input_summary_rows=[{"training_input_ready": True, "blocked_count": 0, "overall_training_input_status": "defensible"}],
        source_heldout_coverage_summary_rows=[
            {
                "source_heldout_full_iad_data_ready": False,
                "ready_relation_count": 2,
                "blocked_relation_count": 1,
                "missing_relation_labels": ["agenda_non_identity"],
                "highest_priority_blocker": "agenda_non_identity_source_heldout_missing",
            },
            {
                "source_heldout_full_iad_data_ready": True,
                "relation_count": 3,
                "ready_relation_count": 3,
                "blocked_relation_count": 0,
                "missing_relation_labels": [],
                "highest_priority_blocker": "",
            },
        ],
    )
    by_id = {row["criterion_id"]: row for row in rows}

    assert by_id["iad_source_heldout_data_coverage"]["status"] == "ready"
    assert by_id["iad_source_heldout_data_coverage"]["blocking_reasons"] == []


def test_build_q2b_completion_audit_rows_aggregates_multiple_split_evaluation_summaries() -> None:
    """验证多个 split 审计摘要会按最严格结果聚合。"""
    rows = build_q2b_completion_audit_rows(
        submission_summary_rows=[{"submission_decision": "ready_for_draft_submission"}],
        q2b_summary_rows=[{"q2_b_ready": True, "blocked_action_count": 0, "external_input_count": 0}],
        reviewer_response_summary_rows=[{"do_not_answer_as_claim_count": 0, "must_not_claim_count": 0, "limited_answer_count": 0}],
        remote_connection_summary_rows=[{"all_connection_fields_ready": True, "all_remote_run_inputs_ready": True, "blocked_secret_count": 0}],
        remote_result_acceptance_summary_rows=[{"all_claim_gates_accepted": True, "blocked_gate_count": 0, "missing_output_count": 0}],
        innovation_depth_summary_rows=[{"overall_innovation_depth_status": "ready", "blocked_count": 0, "q2_b_innovation_claim_allowed": True}],
        advanced_model_summary_rows=[{"missing_required_count": 0, "ready_actual_model_count": 8}],
        split_readiness_summary_rows=[{"overall_split_readiness": "defensible", "blocked_count": 0}],
        split_readiness_audit_rows=[
            {"dimension_id": "random_split_coverage", "audit_status": "defensible"},
            {"dimension_id": "source_held_out_readiness", "audit_status": "defensible"},
            {"dimension_id": "pair_leakage_guard", "audit_status": "defensible"},
        ],
        training_input_summary_rows=[{"training_input_ready": True, "blocked_count": 0, "overall_training_input_status": "defensible"}],
        split_evaluation_summary_rows=[
            {
                "overall_split_evaluation_status": "stratified_blend_diagnostic_only",
                "source_heldout_full_iad_ready": False,
                "limited_source_heldout_count": 0,
                "limited_stratified_blend_count": 1,
                "blocked_count": 0,
                "missing_eval_split_count": 0,
            },
            {
                "overall_split_evaluation_status": "blocked_eval_label_coverage",
                "source_heldout_full_iad_ready": False,
                "limited_source_heldout_count": 0,
                "limited_stratified_blend_count": 0,
                "blocked_count": 1,
                "eval_label_blocked_count": 1,
                "missing_eval_split_count": 0,
            },
        ],
    )

    by_id = {row["criterion_id"]: row for row in rows}

    assert by_id["iad_risk_split_evaluation_readiness"]["status"] == "blocked"
    assert "iad_risk_split_evaluation_blocked" in by_id["iad_risk_split_evaluation_readiness"]["blocking_reasons"]
    assert "eval_label_blocked_count=1" in by_id["iad_risk_split_evaluation_readiness"]["current_evidence"]
    assert by_id["q2b_final_goal"]["status"] == "blocked"


def test_build_q2b_completion_audit_rows_accepts_any_ready_split_evaluation() -> None:
    """验证多个 split 评估摘要中存在 source-held-out ready 时解除评估阻塞。"""
    rows = build_q2b_completion_audit_rows(
        submission_summary_rows=[{"submission_decision": "ready_for_draft_submission"}],
        q2b_summary_rows=[{"q2_b_ready": True, "blocked_action_count": 0, "external_input_count": 0}],
        reviewer_response_summary_rows=[{"do_not_answer_as_claim_count": 0, "must_not_claim_count": 0, "limited_answer_count": 0}],
        remote_connection_summary_rows=[{"all_connection_fields_ready": True, "all_remote_run_inputs_ready": True, "blocked_secret_count": 0}],
        remote_result_acceptance_summary_rows=[{"all_claim_gates_accepted": True, "blocked_gate_count": 0, "missing_output_count": 0}],
        innovation_depth_summary_rows=[{"overall_innovation_depth_status": "ready", "blocked_count": 0, "q2_b_innovation_claim_allowed": True}],
        advanced_model_summary_rows=[{"missing_required_count": 0, "ready_actual_model_count": 8}],
        split_readiness_summary_rows=[{"overall_split_readiness": "defensible", "blocked_count": 0}],
        split_readiness_audit_rows=[
            {"dimension_id": "random_split_coverage", "audit_status": "defensible"},
            {"dimension_id": "source_held_out_readiness", "audit_status": "defensible"},
            {"dimension_id": "pair_leakage_guard", "audit_status": "defensible"},
            {"dimension_id": "topic_held_out_readiness", "audit_status": "defensible"},
        ],
        training_input_summary_rows=[{"training_input_ready": True, "blocked_count": 0, "overall_training_input_status": "defensible"}],
        split_evaluation_summary_rows=[
            {
                "overall_split_evaluation_status": "blocked_full_iad_risk_generalization",
                "source_heldout_full_iad_ready": False,
                "limited_source_heldout_count": 0,
                "limited_stratified_blend_count": 1,
                "blocked_count": 1,
                "eval_label_blocked_count": 0,
                "missing_eval_split_count": 0,
            },
            {
                "overall_split_evaluation_status": "source_heldout_full_iad_limited_ready",
                "source_heldout_full_iad_ready": True,
                "limited_source_heldout_count": 1,
                "limited_stratified_blend_count": 0,
                "blocked_count": 0,
                "eval_label_blocked_count": 0,
                "missing_eval_split_count": 0,
            },
        ],
    )

    by_id = {row["criterion_id"]: row for row in rows}

    assert by_id["iad_risk_split_evaluation_readiness"]["status"] == "ready"
    assert "limited_source_heldout_count=1" in by_id["iad_risk_split_evaluation_readiness"]["current_evidence"]
    assert by_id["iad_risk_split_evaluation_readiness"]["blocking_reasons"] == []
    assert by_id["q2b_final_goal"]["status"] == "ready"


def test_build_q2b_completion_audit_rows_ready_only_when_all_core_gates_ready() -> None:
    """验证所有核心证据 ready 后最终目标才允许 ready。"""
    rows = build_q2b_completion_audit_rows(
        submission_summary_rows=[{"submission_decision": "ready_for_draft_submission", "blocking_reasons": []}],
        q2b_summary_rows=[{"q2_b_ready": True, "blocked_action_count": 0, "external_input_count": 0}],
        reviewer_response_summary_rows=[
            {
                "do_not_answer_as_claim_count": 0,
                "must_not_claim_count": 0,
                "limited_answer_count": 0,
            }
        ],
        remote_connection_summary_rows=[
            {
                "all_connection_fields_ready": True,
                "all_remote_run_inputs_ready": True,
                "missing_required_field_count": 0,
                "blocked_secret_count": 0,
            }
        ],
        remote_result_acceptance_summary_rows=[{"all_claim_gates_accepted": True, "blocked_gate_count": 0, "missing_output_count": 0}],
        innovation_depth_summary_rows=[{"overall_innovation_depth_status": "ready", "blocked_count": 0, "q2_b_innovation_claim_allowed": True}],
        advanced_model_summary_rows=[{"missing_required_count": 0, "ready_actual_model_count": 8}],
        split_readiness_summary_rows=[{"overall_split_readiness": "defensible", "blocked_count": 0}],
        split_readiness_audit_rows=[
            {"dimension_id": "random_split_coverage", "audit_status": "defensible"},
            {"dimension_id": "source_held_out_readiness", "audit_status": "defensible"},
            {"dimension_id": "pair_leakage_guard", "audit_status": "defensible"},
            {"dimension_id": "topic_held_out_readiness", "audit_status": "defensible"},
        ],
        training_input_summary_rows=[{"training_input_ready": True, "blocked_count": 0, "overall_training_input_status": "defensible"}],
    )

    by_id = {row["criterion_id"]: row for row in rows}

    assert all(row["status"] == "ready" for row in rows)
    assert by_id["q2b_final_goal"]["acceptance_evidence"] == "所有核心二区/B类完成度门禁均 ready。"


def test_build_q2b_completion_audit_rows_accepts_ready_api_model_count() -> None:
    """验证 api_model 可作为强模型闭环证据。"""
    rows = build_q2b_completion_audit_rows(
        submission_summary_rows=[],
        q2b_summary_rows=[],
        reviewer_response_summary_rows=[],
        remote_connection_summary_rows=[],
        advanced_model_summary_rows=[{"missing_required_count": 0, "ready_actual_model_count": 0, "ready_api_model_count": 1, "ready_model_count": 1}],
        split_readiness_summary_rows=[],
    )
    by_id = {row["criterion_id"]: row for row in rows}

    assert by_id["advanced_model_closure"]["status"] == "ready"
    assert "ready_api_model_count=1" in by_id["advanced_model_closure"]["current_evidence"]


def test_build_q2b_completion_audit_rows_focuses_advanced_model_next_action_on_remaining_gaps() -> None:
    """验证已有多项 actual_model 时 advanced_model 下一步不再要求补 SPECTER2。"""
    rows = build_q2b_completion_audit_rows(
        submission_summary_rows=[],
        q2b_summary_rows=[],
        reviewer_response_summary_rows=[],
        remote_connection_summary_rows=[],
        advanced_model_summary_rows=[{"missing_required_count": 2, "ready_actual_model_count": 6, "ready_api_model_count": 0, "ready_model_count": 6}],
        split_readiness_summary_rows=[],
    )
    by_id = {row["criterion_id"]: row for row in rows}

    assert by_id["advanced_model_closure"]["status"] == "blocked"
    assert "SPECTER2" not in by_id["advanced_model_closure"]["next_action"]
    assert "LLM judge" in by_id["advanced_model_closure"]["next_action"]


def test_write_q2b_completion_audit_outputs_writes_jsonl_csv_markdown_and_summary(tmp_path) -> None:
    """验证最终目标完成度审计写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "q2b_completion_audit"
    rows = [
        {
            "criterion_id": "q2b_final_goal",
            "status": "blocked",
            "reviewer_risk_level": "high",
            "evidence_scope": "final_goal",
            "current_evidence": "submission_decision=blocked",
            "blocking_reasons": ["advanced_baseline"],
            "next_action": "补齐强 baseline。",
            "acceptance_evidence": "submission_decision=ready_for_draft_submission",
            "paper_claim_boundary": "不能声称已经达到二区/B类。",
        }
    ]

    write_q2b_completion_audit_outputs(rows, output_dir)

    assert read_records(output_dir / "q2b_completion_audit.jsonl")[0]["criterion_id"] == "q2b_final_goal"
    assert (output_dir / "q2b_completion_audit.csv").exists()
    assert "# Q2/B Completion Audit" in (output_dir / "q2b_completion_audit.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "q2b_completion_audit_summary.jsonl")[0]
    assert summary["overall_completion_status"] == "blocked"
    assert summary["q2_b_goal_ready"] is False


def test_q2b_completion_fixture_includes_coci_source_heldout_ready_evidence() -> None:
    """验证当前完成度 fixture 纳入 COCI source-held-out ready 证据。"""
    fixture_dir = Path("tests/fixtures/q2b_completion_audit")
    rows = read_records(fixture_dir / "q2b_completion_audit.jsonl")
    summary = read_records(fixture_dir / "q2b_completion_audit_summary.jsonl")[0]
    by_id = {row["criterion_id"]: row for row in rows}

    assert summary["ready_count"] == summary["criterion_count"]
    assert summary["blocked_count"] == 0
    assert summary["q2_b_goal_ready"] is True
    assert by_id["q2b_final_goal"]["status"] == "ready"
    assert by_id["iad_source_heldout_data_coverage"]["status"] == "ready"
    assert by_id["iad_risk_split_evaluation_readiness"]["status"] == "ready"
    assert "agenda_non_identity_source_heldout_missing" not in by_id["q2b_final_goal"]["blocking_reasons"]
    assert "source_heldout_full_iad_missing" not in by_id["q2b_final_goal"]["blocking_reasons"]


def test_build_q2b_completion_audit_rows_from_paths_reads_inputs(tmp_path) -> None:
    """验证从路径读取完成度审计输入。"""
    submission = tmp_path / "submission_gate_audit_summary.jsonl"
    q2b = tmp_path / "q2b_action_board_summary.jsonl"
    reviewer = tmp_path / "reviewer_response_summary.jsonl"
    remote = tmp_path / "remote_connection_pack_summary.jsonl"
    remote_result = tmp_path / "remote_result_acceptance_summary.jsonl"
    innovation_depth = tmp_path / "innovation_depth_stress_test_summary.jsonl"
    advanced = tmp_path / "advanced_model_evidence_summary.jsonl"
    split = tmp_path / "open_v3_split_readiness_summary.jsonl"
    split_audit = tmp_path / "open_v3_split_readiness.jsonl"
    training_input = tmp_path / "iad_training_input_audit_summary.jsonl"
    split_evaluation = tmp_path / "iad_risk_split_evaluation_audit_summary.jsonl"
    _write_jsonl(submission, [{"submission_decision": "blocked"}])
    _write_jsonl(q2b, [{"q2_b_ready": False}])
    _write_jsonl(reviewer, [{"do_not_answer_as_claim_count": 1, "must_not_claim_count": 1}])
    _write_jsonl(remote, [{"all_remote_run_inputs_ready": False}])
    _write_jsonl(remote_result, [{"all_claim_gates_accepted": False, "blocked_gate_count": 1}])
    _write_jsonl(innovation_depth, [{"overall_innovation_depth_status": "blocked", "blocked_count": 1}])
    _write_jsonl(advanced, [{"missing_required_count": 1}])
    _write_jsonl(split, [{"overall_split_readiness": "blocked"}])
    _write_jsonl(split_audit, [{"dimension_id": "source_held_out_readiness", "audit_status": "blocked"}])
    _write_jsonl(training_input, [{"training_input_ready": False, "blocked_count": 1, "overall_training_input_status": "blocked"}])
    _write_jsonl(split_evaluation, [{"overall_split_evaluation_status": "blocked_full_iad_risk_generalization", "blocked_count": 1}])

    rows = build_q2b_completion_audit_rows_from_paths(
        submission_summary_paths=[submission],
        q2b_summary_paths=[q2b],
        reviewer_response_summary_paths=[reviewer],
        remote_connection_summary_paths=[remote],
        remote_result_acceptance_summary_paths=[remote_result],
        innovation_depth_summary_paths=[innovation_depth],
        advanced_model_summary_paths=[advanced],
        split_readiness_summary_paths=[split],
        split_readiness_audit_paths=[split_audit],
        training_input_summary_paths=[training_input],
        split_evaluation_summary_paths=[split_evaluation],
    )

    assert rows[-1]["criterion_id"] == "q2b_final_goal"
    assert rows[-1]["status"] == "blocked"


def test_build_q2b_completion_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出最终目标完成度审计。"""
    submission = tmp_path / "submission_gate_audit_summary.jsonl"
    output_dir = tmp_path / "q2b_completion_audit"
    _write_jsonl(submission, [{"submission_decision": "ready_for_draft_submission"}])

    command_build_q2b_completion_audit(
        Namespace(
            submission_summaries=[str(submission)],
            q2b_summaries=[],
            reviewer_response_summaries=[],
            remote_connection_summaries=[],
            remote_result_acceptance_summaries=[],
            innovation_depth_summaries=[],
            advanced_model_summaries=[],
            split_readiness_summaries=[],
            split_readiness_audits=[],
            training_input_summaries=[],
            split_evaluation_summaries=[],
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "q2b_completion_audit.jsonl").exists()
    assert (output_dir / "q2b_completion_audit_summary.jsonl").exists()


def test_cli_includes_build_q2b_completion_audit_command() -> None:
    """验证 CLI 暴露 build-q2b-completion-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-q2b-completion-audit",
            "--submission-summaries",
            "outputs/submission_gate_audit_fixture/submission_gate_audit_summary.jsonl",
            "--output-dir",
            "outputs/q2b_completion_audit_fixture",
            "--remote-result-acceptance-summaries",
            "outputs/remote_result_acceptance_fixture/remote_result_acceptance_summary.jsonl",
            "--innovation-depth-summaries",
            "outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test_summary.jsonl",
            "--training-input-summaries",
            "outputs/iad_training_input_audit_open_v3_gold_silver/iad_training_input_audit_summary.jsonl",
            "--split-evaluation-summaries",
            "outputs/iad_risk_split_evaluation_audit_open_v3_gold_silver/iad_risk_split_evaluation_audit_summary.jsonl",
        ]
    )

    assert args.command == "build-q2b-completion-audit"
    assert args.remote_result_acceptance_summaries == ["outputs/remote_result_acceptance_fixture/remote_result_acceptance_summary.jsonl"]
    assert args.innovation_depth_summaries == ["outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test_summary.jsonl"]
    assert args.training_input_summaries == ["outputs/iad_training_input_audit_open_v3_gold_silver/iad_training_input_audit_summary.jsonl"]
    assert args.split_evaluation_summaries == [
        "outputs/iad_risk_split_evaluation_audit_open_v3_gold_silver/iad_risk_split_evaluation_audit_summary.jsonl"
    ]
    assert args.func == command_build_q2b_completion_audit
