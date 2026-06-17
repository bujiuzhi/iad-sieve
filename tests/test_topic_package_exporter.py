"""测试最终课题包导出器。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_export_topic_package
from iad_sieve.evaluation.topic_package_exporter import export_topic_package
from iad_sieve.utils.io_utils import read_records


def _write_text(path, content: str) -> None:
    """写入文本文件。

    参数:
        path: 输出路径。
        content: 文本内容。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_jsonl(path, records: list[dict]) -> None:
    """写入 JSONL 文件。

    参数:
        path: 输出路径。
        records: 记录列表。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def test_export_topic_package_copies_docs_reports_models_and_manifest(tmp_path) -> None:
    """验证课题包导出核心文档、报告、模型和 manifest。"""
    workspace = tmp_path / "workspace"
    output_dir = tmp_path / "topic_package"
    _write_text(workspace / "README.md", "# iad-sieve\n")
    _write_text(workspace / "docs" / "README.md", "# Docs\n")
    _write_text(workspace / "docs" / "project-structure.md", "# Project Structure\n")
    _write_text(workspace / "docs" / "naming-convention.md", "# Naming\n")
    _write_text(workspace / "docs" / "GOAL.md", "# Goal\n")
    _write_text(workspace / "docs" / "method-design.md", "# Method\n")
    _write_text(workspace / "docs" / "experiment-plan.md", "# Experiment\n")
    _write_text(workspace / "docs" / "paper-outline.md", "# Paper\n")
    _write_text(workspace / "docs" / "iad-bench-contract.md", "# IAD-Bench Contract\n")
    _write_text(workspace / "docs" / "data-processing-pipeline.md", "# Data Processing Pipeline\n")
    _write_text(workspace / "docs" / "annotation-requirements.md", "# Annotation\n")
    _write_text(workspace / "docs" / "data-and-artifact-release.md", "# Data and Artifact Release\n")
    _write_text(workspace / "docs" / "public-release-checklist.md", "# Public Release Checklist\n")
    _write_text(workspace / "docs" / "current-work-summary.md", "# Summary\n")
    _write_text(workspace / "docs" / "remote-dev-setup.md", "# Remote Dev Setup\n")
    _write_text(workspace / "docs" / "superpowers" / "specs" / "2026-06-12-iad-risk-redesign.md", "# IAD-Risk\n")
    _write_text(workspace / "docs" / "superpowers" / "specs" / "2026-06-12-iad-evidence-bootstrap-design.md", "# IAD Evidence Bootstrap\n")
    _write_text(workspace / "docs" / "superpowers" / "specs" / "2026-06-13-iad-risk-open-v3-redesign.md", "# IAD-Risk Open-v3\n")
    _write_text(workspace / "docs" / "superpowers" / "specs" / "2026-06-13-iad-risk-no-annotation-q2b-upgrade.md", "# IAD-Risk No Annotation Q2/B Upgrade\n")
    _write_text(workspace / "docs" / "superpowers" / "plans" / "2026-06-13-iad-risk-open-v3-implementation.md", "# IAD-Risk Open-v3 Implementation Plan\n")
    _write_text(workspace / "docs" / "superpowers" / "plans" / "2026-06-13-iad-source-candidate-registry.md", "# IAD Source Candidate Registry Implementation Plan\n")
    _write_text(workspace / "docs" / "superpowers" / "plans" / "2026-06-13-iad-risk-no-annotation-q2b-upgrade-implementation.md", "# IAD-Risk No Annotation Q2/B Upgrade Implementation Plan\n")
    _write_text(workspace / "docs" / "superpowers" / "plans" / "2026-06-13-q2b-remote-execution-closure.md", "# Q2B Remote Execution Closure Implementation Plan\n")
    _write_text(workspace / "docs" / "superpowers" / "plans" / "2026-06-13-q2b-experiment-optimizer.md", "# Q2/B Experiment Optimizer Implementation Plan\n")
    _write_text(workspace / "outputs" / "iad_paper_report_fixture" / "paper_report.md", "# IAD-Sieve Paper Report\n")
    _write_text(workspace / "outputs" / "reviewer_audit_fixture" / "reviewer_audit.md", "# Reviewer Audit Matrix\n")
    _write_jsonl(workspace / "outputs" / "experiment_preflight_fixture" / "experiment_preflight.jsonl", [{"status": "blocked_remote_required"}])
    _write_text(workspace / "outputs" / "experiment_preflight_fixture" / "experiment_preflight.csv", "task_id,status\n")
    _write_text(workspace / "outputs" / "experiment_preflight_fixture" / "experiment_preflight.md", "# Experiment Preflight\n")
    _write_jsonl(workspace / "outputs" / "experiment_dependency_fixture" / "experiment_dependency.jsonl", [{"task_id": "run_encoder"}])
    _write_text(workspace / "outputs" / "experiment_dependency_fixture" / "experiment_dependency.csv", "task_id,status\n")
    _write_text(workspace / "outputs" / "experiment_dependency_fixture" / "experiment_dependency.md", "# Experiment Dependency Graph\n")
    _write_jsonl(workspace / "outputs" / "experiment_execution_pack_fixture" / "experiment_execution_plan.jsonl", [{"task_id": "run_encoder"}])
    _write_text(workspace / "outputs" / "experiment_execution_pack_fixture" / "experiment_execution_plan.csv", "task_id,status\n")
    _write_text(workspace / "outputs" / "experiment_execution_pack_fixture" / "experiment_execution_plan.md", "# Experiment Execution Pack\n")
    _write_jsonl(workspace / "outputs" / "experiment_execution_pack_fixture" / "experiment_execution_scripts.jsonl", [{"script_name": "run_stage_00.sh"}])
    _write_jsonl(workspace / "outputs" / "experiment_execution_pack_fixture" / "remote_output_manifest.jsonl", [{"task_id": "run_encoder"}])
    _write_text(workspace / "outputs" / "experiment_execution_pack_fixture" / "run_stage_00.sh", "#!/usr/bin/env bash\n")
    _write_text(workspace / "outputs" / "experiment_execution_pack_fixture" / "remote_handoff.md", "# Remote Experiment Handoff\n")
    _write_jsonl(workspace / "outputs" / "paper_claim_audit_fixture" / "paper_claim_audit.jsonl", [{"claim_id": "q2_b_ready"}])
    _write_text(workspace / "outputs" / "paper_claim_audit_fixture" / "paper_claim_audit.csv", "claim_id,claim_status\n")
    _write_text(workspace / "outputs" / "paper_claim_audit_fixture" / "paper_claim_audit.md", "# Paper Claim Audit\n")
    _write_jsonl(workspace / "outputs" / "remote_output_validation_fixture" / "remote_output_validation.jsonl", [{"validation_status": "missing"}])
    _write_text(workspace / "outputs" / "remote_output_validation_fixture" / "remote_output_validation.csv", "task_id,validation_status\n")
    _write_text(workspace / "outputs" / "remote_output_validation_fixture" / "remote_output_validation.md", "# Remote Output Validation\n")
    _write_jsonl(workspace / "outputs" / "remote_output_validation_fixture" / "remote_output_validation_summary.jsonl", [{"all_outputs_valid": False}])
    _write_jsonl(workspace / "outputs" / "remote_result_acceptance_fixture" / "remote_result_acceptance.jsonl", [{"acceptance_id": "gate:specter2_adapter_actual_model"}])
    _write_text(workspace / "outputs" / "remote_result_acceptance_fixture" / "remote_result_acceptance.csv", "acceptance_id,status\n")
    _write_text(workspace / "outputs" / "remote_result_acceptance_fixture" / "remote_result_acceptance.md", "# Remote Result Acceptance\n")
    _write_jsonl(workspace / "outputs" / "remote_result_acceptance_fixture" / "remote_result_acceptance_summary.jsonl", [{"all_claim_gates_accepted": False}])
    _write_jsonl(workspace / "outputs" / "remote_environment_audit_fixture" / "remote_environment_audit.jsonl", [{"dependency_name": "torch", "status": "missing"}])
    _write_text(workspace / "outputs" / "remote_environment_audit_fixture" / "remote_environment_audit.csv", "dependency_name,status\n")
    _write_text(workspace / "outputs" / "remote_environment_audit_fixture" / "remote_environment_audit.md", "# Remote Environment Audit\n")
    _write_jsonl(workspace / "outputs" / "remote_environment_audit_fixture" / "remote_environment_audit_summary.jsonl", [{"all_required_ready": False}])
    _write_jsonl(workspace / "outputs" / "remote_execution_blueprint_fixture" / "remote_execution_blueprint.jsonl", [{"blueprint_item_id": "root_task:run_encoder"}])
    _write_text(workspace / "outputs" / "remote_execution_blueprint_fixture" / "remote_execution_blueprint.csv", "blueprint_item_id,status\n")
    _write_text(workspace / "outputs" / "remote_execution_blueprint_fixture" / "remote_execution_blueprint.md", "# Remote Execution Blueprint\n")
    _write_jsonl(workspace / "outputs" / "remote_execution_blueprint_fixture" / "remote_execution_blueprint_summary.jsonl", [{"all_remote_prerequisites_ready": False}])
    _write_jsonl(workspace / "outputs" / "remote_connection_pack_fixture" / "remote_connection_pack.jsonl", [{"item_id": "connection_field:remote_host"}])
    _write_text(workspace / "outputs" / "remote_connection_pack_fixture" / "remote_connection_pack.csv", "item_id,status\n")
    _write_text(workspace / "outputs" / "remote_connection_pack_fixture" / "remote_connection_pack.md", "# Remote Connection Pack\n")
    _write_jsonl(workspace / "outputs" / "remote_connection_pack_fixture" / "remote_connection_pack_summary.jsonl", [{"all_remote_run_inputs_ready": False}])
    _write_text(workspace / "outputs" / "remote_connection_pack_fixture" / "remote_connection.env.example", "REMOTE_HOST=\n")
    _write_text(workspace / "outputs" / "remote_connection_pack_fixture" / "remote_connection_profile.template.json", "{}\n")
    _write_text(workspace / "outputs" / "remote_connection_pack_fixture" / "remote_preflight.template.sh", "#!/usr/bin/env bash\n")
    _write_text(workspace / "outputs" / "remote_connection_pack_fixture" / "remote_sync_and_run.template.sh", "#!/usr/bin/env bash\n")
    _write_text(workspace / "outputs" / "remote_connection_pack_fixture" / "remote_pull_outputs.template.sh", "#!/usr/bin/env bash\n")
    _write_text(workspace / "outputs" / "remote_connection_pack_fixture" / "remote_execution_runbook.md", "# Remote Execution Runbook\n")
    _write_jsonl(workspace / "outputs" / "remote_input_request_fixture" / "remote_input_request.jsonl", [{"request_id": "connection:remote_host"}])
    _write_text(workspace / "outputs" / "remote_input_request_fixture" / "remote_input_request.csv", "request_id,status\n")
    _write_text(workspace / "outputs" / "remote_input_request_fixture" / "remote_input_request.md", "# Remote Input Request\n")
    _write_jsonl(workspace / "outputs" / "remote_input_request_fixture" / "remote_input_request_summary.jsonl", [{"all_remote_inputs_ready": False}])
    _write_jsonl(workspace / "outputs" / "remote_execution_slice_fixture" / "remote_execution_slice.jsonl", [{"slice_id": "track:open_v3"}])
    _write_text(workspace / "outputs" / "remote_execution_slice_fixture" / "remote_execution_slice.csv", "slice_id,status\n")
    _write_text(workspace / "outputs" / "remote_execution_slice_fixture" / "remote_execution_slice.md", "# Remote Execution Slice\n")
    _write_jsonl(workspace / "outputs" / "remote_execution_slice_fixture" / "remote_execution_slice_summary.jsonl", [{"q2b_remote_execution_slice_ready": False}])
    _write_jsonl(workspace / "outputs" / "remote_slice_run_pack_fixture" / "remote_slice_run_pack.jsonl", [{"item_id": "slice_script:open_v3"}])
    _write_text(workspace / "outputs" / "remote_slice_run_pack_fixture" / "remote_slice_run_pack.csv", "item_id,status\n")
    _write_text(workspace / "outputs" / "remote_slice_run_pack_fixture" / "remote_slice_run_pack.md", "# Remote Slice Run Pack\n")
    _write_jsonl(workspace / "outputs" / "remote_slice_run_pack_fixture" / "remote_slice_run_pack_summary.jsonl", [{"q2b_remote_slice_run_pack_ready": True}])
    _write_jsonl(workspace / "outputs" / "remote_slice_run_pack_fixture" / "remote_slice_run_scripts.jsonl", [{"script_name": "run_remote_slice_open_v3.template.sh"}])
    _write_text(workspace / "outputs" / "remote_slice_run_pack_fixture" / "run_remote_slice_open_v3.template.sh", "#!/usr/bin/env bash\n")
    _write_jsonl(workspace / "outputs" / "primary_remote_readiness_fixture" / "primary_remote_readiness.jsonl", [{"readiness_id": "primary_track_remote_readiness"}])
    _write_text(workspace / "outputs" / "primary_remote_readiness_fixture" / "primary_remote_readiness.csv", "readiness_id,status\n")
    _write_text(workspace / "outputs" / "primary_remote_readiness_fixture" / "primary_remote_readiness.md", "# Primary Remote Readiness\n")
    _write_jsonl(workspace / "outputs" / "primary_remote_readiness_fixture" / "primary_remote_readiness_summary.jsonl", [{"primary_remote_ready": False}])
    _write_jsonl(workspace / "outputs" / "primary_remote_handoff_fixture" / "primary_remote_handoff.jsonl", [{"handoff_id": "primary_track_remote_handoff"}])
    _write_text(workspace / "outputs" / "primary_remote_handoff_fixture" / "primary_remote_handoff.csv", "handoff_id,status\n")
    _write_text(workspace / "outputs" / "primary_remote_handoff_fixture" / "primary_remote_handoff.md", "# Primary Remote Handoff\n")
    _write_jsonl(workspace / "outputs" / "primary_remote_handoff_fixture" / "primary_remote_handoff_summary.jsonl", [{"handoff_status": "waiting_for_connection_fields"}])
    _write_text(
        workspace / "outputs" / "primary_remote_handoff_fixture" / "run_primary_post_run_validation.sh",
        "#!/usr/bin/env bash\nset -euo pipefail\npython -m iad_sieve.cli validate-remote-outputs\n",
    )
    _write_jsonl(workspace / "outputs" / "primary_track_claim_gate_fixture" / "primary_track_claim_gate.jsonl", [{"gate_id": "primary_track_claim_gate"}])
    _write_text(workspace / "outputs" / "primary_track_claim_gate_fixture" / "primary_track_claim_gate.csv", "gate_id,status\n")
    _write_text(workspace / "outputs" / "primary_track_claim_gate_fixture" / "primary_track_claim_gate.md", "# Primary Track Claim Gate\n")
    _write_jsonl(workspace / "outputs" / "primary_track_claim_gate_fixture" / "primary_track_claim_gate_summary.jsonl", [{"claim_gate_status": "blocked"}])
    _write_jsonl(workspace / "outputs" / "primary_track_superiority_protocol_fixture" / "primary_track_superiority_protocol.jsonl", [{"protocol_item_id": "protocol_summary"}])
    _write_text(workspace / "outputs" / "primary_track_superiority_protocol_fixture" / "primary_track_superiority_protocol.csv", "protocol_item_id,status\n")
    _write_text(workspace / "outputs" / "primary_track_superiority_protocol_fixture" / "primary_track_superiority_protocol.md", "# Primary Track Superiority Protocol\n")
    _write_jsonl(workspace / "outputs" / "primary_track_superiority_protocol_fixture" / "primary_track_superiority_protocol_summary.jsonl", [{"protocol_status": "blocked_waiting_for_primary_models"}])
    _write_jsonl(workspace / "outputs" / "primary_track_superiority_evaluator_fixture" / "primary_track_superiority_evaluator.jsonl", [{"evaluator_item_id": "evaluator_summary"}])
    _write_text(workspace / "outputs" / "primary_track_superiority_evaluator_fixture" / "primary_track_superiority_evaluator.csv", "evaluator_item_id,status\n")
    _write_text(workspace / "outputs" / "primary_track_superiority_evaluator_fixture" / "primary_track_superiority_evaluator.md", "# Primary Track Superiority Evaluator\n")
    _write_jsonl(workspace / "outputs" / "primary_track_superiority_evaluator_fixture" / "primary_track_superiority_evaluator_summary.jsonl", [{"evaluation_status": "blocked_missing_primary_metrics"}])
    _write_jsonl(workspace / "outputs" / "no_annotation_protocol_fixture" / "no_annotation_protocol.jsonl", [{"protocol_id": "human_gold_deferred_boundary"}])
    _write_text(workspace / "outputs" / "no_annotation_protocol_fixture" / "no_annotation_protocol.csv", "protocol_id,status\n")
    _write_text(workspace / "outputs" / "no_annotation_protocol_fixture" / "no_annotation_protocol.md", "# No Annotation Stage Protocol\n")
    _write_jsonl(workspace / "outputs" / "no_annotation_protocol_fixture" / "no_annotation_protocol_summary.jsonl", [{"no_annotation_stage_allowed": True}])
    _write_jsonl(workspace / "outputs" / "research_depth_audit_fixture" / "research_depth_audit.jsonl", [{"dimension_id": "advanced_baseline"}])
    _write_text(workspace / "outputs" / "research_depth_audit_fixture" / "research_depth_audit.csv", "dimension_id,depth_status\n")
    _write_text(workspace / "outputs" / "research_depth_audit_fixture" / "research_depth_audit.md", "# Research Depth Audit\n")
    _write_jsonl(workspace / "outputs" / "submission_gate_audit_fixture" / "submission_gate_audit.jsonl", [{"submission_gate_id": "overall_submission_gate"}])
    _write_text(workspace / "outputs" / "submission_gate_audit_fixture" / "submission_gate_audit.csv", "submission_gate_id,decision\n")
    _write_text(workspace / "outputs" / "submission_gate_audit_fixture" / "submission_gate_audit.md", "# Submission Gate Audit\n")
    _write_jsonl(workspace / "outputs" / "submission_gate_audit_fixture" / "submission_gate_audit_summary.jsonl", [{"submission_decision": "blocked"}])
    _write_jsonl(workspace / "outputs" / "manuscript_evidence_matrix_fixture" / "manuscript_evidence_matrix.jsonl", [{"claim_id": "q2_b_ready"}])
    _write_text(workspace / "outputs" / "manuscript_evidence_matrix_fixture" / "manuscript_evidence_matrix.csv", "claim_id,writing_action\n")
    _write_text(workspace / "outputs" / "manuscript_evidence_matrix_fixture" / "manuscript_evidence_matrix.md", "# Manuscript Evidence Matrix\n")
    _write_jsonl(workspace / "outputs" / "manuscript_evidence_matrix_fixture" / "manuscript_evidence_summary.jsonl", [{"do_not_write_count": 1}])
    _write_jsonl(workspace / "outputs" / "reviewer_response_matrix_fixture" / "reviewer_response_matrix.jsonl", [{"concern_id": "innovation_depth"}])
    _write_text(workspace / "outputs" / "reviewer_response_matrix_fixture" / "reviewer_response_matrix.csv", "concern_id,response_status\n")
    _write_text(workspace / "outputs" / "reviewer_response_matrix_fixture" / "reviewer_response_matrix.md", "# Reviewer Response Matrix\n")
    _write_jsonl(workspace / "outputs" / "reviewer_response_matrix_fixture" / "reviewer_response_summary.jsonl", [{"ready_to_answer_count": 1}])
    _write_jsonl(workspace / "outputs" / "reviewer_iteration_audit_fixture" / "reviewer_iteration_audit.jsonl", [{"iteration_id": "r0_remote_reproducibility"}])
    _write_text(workspace / "outputs" / "reviewer_iteration_audit_fixture" / "reviewer_iteration_audit.csv", "iteration_id,status\n")
    _write_text(workspace / "outputs" / "reviewer_iteration_audit_fixture" / "reviewer_iteration_audit.md", "# Reviewer Iteration Audit\n")
    _write_jsonl(workspace / "outputs" / "reviewer_iteration_audit_fixture" / "reviewer_iteration_audit_summary.jsonl", [{"q2_b_ready_from_reviewer_view": False}])
    _write_jsonl(workspace / "outputs" / "reviewer_threat_model_fixture" / "reviewer_threat_model.jsonl", [{"threat_id": "threat_remote_reproducibility_acceptance"}])
    _write_text(workspace / "outputs" / "reviewer_threat_model_fixture" / "reviewer_threat_model.csv", "threat_id,severity\n")
    _write_text(workspace / "outputs" / "reviewer_threat_model_fixture" / "reviewer_threat_model.md", "# Reviewer Threat Model\n")
    _write_jsonl(workspace / "outputs" / "reviewer_threat_model_fixture" / "reviewer_threat_model_summary.jsonl", [{"q2b_reviewer_threats_closed": False}])
    _write_jsonl(workspace / "outputs" / "manuscript_draft_skeleton_fixture" / "manuscript_draft_skeleton.jsonl", [{"section_id": "abstract"}])
    _write_text(workspace / "outputs" / "manuscript_draft_skeleton_fixture" / "manuscript_draft_skeleton.md", "# Manuscript Draft Skeleton\n")
    _write_jsonl(workspace / "outputs" / "manuscript_draft_skeleton_fixture" / "manuscript_draft_skeleton_summary.jsonl", [{"restricted_section_count": 2}])
    _write_jsonl(workspace / "outputs" / "journal_upgrade_plan_fixture" / "journal_upgrade_plan.jsonl", [{"requirement_id": "remote_gpu_connection"}])
    _write_text(workspace / "outputs" / "journal_upgrade_plan_fixture" / "journal_upgrade_plan.csv", "requirement_id,status\n")
    _write_text(workspace / "outputs" / "journal_upgrade_plan_fixture" / "journal_upgrade_plan.md", "# Journal Upgrade Plan\n")
    _write_jsonl(workspace / "outputs" / "journal_upgrade_plan_fixture" / "journal_upgrade_plan_summary.jsonl", [{"blocked_external_input_count": 2}])
    _write_jsonl(workspace / "outputs" / "advanced_model_evidence_fixture" / "advanced_model_evidence.jsonl", [{"system": "scincl_cosine_open_v2"}])
    _write_text(workspace / "outputs" / "advanced_model_evidence_fixture" / "advanced_model_evidence.csv", "system,evidence_status\n")
    _write_text(workspace / "outputs" / "advanced_model_evidence_fixture" / "advanced_model_evidence.md", "# Advanced Model Evidence Matrix\n")
    _write_jsonl(workspace / "outputs" / "advanced_model_evidence_fixture" / "advanced_model_evidence_summary.jsonl", [{"missing_required_count": 2}])
    _write_jsonl(workspace / "outputs" / "model_innovation_blueprint_fixture" / "model_innovation_blueprint.jsonl", [{"blueprint_id": "specter2_encoder_stability"}])
    _write_text(workspace / "outputs" / "model_innovation_blueprint_fixture" / "model_innovation_blueprint.csv", "blueprint_id,status\n")
    _write_text(workspace / "outputs" / "model_innovation_blueprint_fixture" / "model_innovation_blueprint.md", "# Model Innovation Blueprint\n")
    _write_jsonl(workspace / "outputs" / "model_innovation_blueprint_fixture" / "model_innovation_blueprint_summary.jsonl", [{"overall_model_innovation_status": "blocked"}])
    _write_jsonl(workspace / "outputs" / "model_superiority_audit_fixture" / "model_superiority_audit.jsonl", [{"comparison_id": "iad_risk_transformer_open_v2_vs_scincl_cosine_open_v2"}])
    _write_text(workspace / "outputs" / "model_superiority_audit_fixture" / "model_superiority_audit.csv", "comparison_id,status\n")
    _write_text(workspace / "outputs" / "model_superiority_audit_fixture" / "model_superiority_audit.md", "# Model Superiority Audit\n")
    _write_jsonl(workspace / "outputs" / "model_superiority_audit_fixture" / "model_superiority_audit_summary.jsonl", [{"overall_superiority_status": "blocked"}])
    _write_jsonl(workspace / "outputs" / "innovation_depth_stress_test_fixture" / "innovation_depth_stress_test.jsonl", [{"stress_id": "overall_innovation_depth"}])
    _write_text(workspace / "outputs" / "innovation_depth_stress_test_fixture" / "innovation_depth_stress_test.csv", "stress_id,status\n")
    _write_text(workspace / "outputs" / "innovation_depth_stress_test_fixture" / "innovation_depth_stress_test.md", "# Innovation Depth Stress Test\n")
    _write_jsonl(workspace / "outputs" / "innovation_depth_stress_test_fixture" / "innovation_depth_stress_test_summary.jsonl", [{"overall_innovation_depth_status": "blocked"}])
    _write_jsonl(workspace / "outputs" / "novelty_falsification_matrix_fixture" / "novelty_falsification_matrix.jsonl", [{"contribution_id": "risk_decomposition_vs_single_space"}])
    _write_text(workspace / "outputs" / "novelty_falsification_matrix_fixture" / "novelty_falsification_matrix.csv", "contribution_id,status\n")
    _write_text(workspace / "outputs" / "novelty_falsification_matrix_fixture" / "novelty_falsification_matrix.md", "# Novelty Falsification Matrix\n")
    _write_jsonl(workspace / "outputs" / "novelty_falsification_matrix_fixture" / "novelty_falsification_matrix_summary.jsonl", [{"q2b_novelty_defensible": False}])
    _write_jsonl(workspace / "outputs" / "prior_art_novelty_audit_fixture" / "prior_art_novelty_audit.jsonl", [{"prior_art_family_id": "scientific_document_representation"}])
    _write_text(workspace / "outputs" / "prior_art_novelty_audit_fixture" / "prior_art_novelty_audit.csv", "prior_art_family_id,status\n")
    _write_text(workspace / "outputs" / "prior_art_novelty_audit_fixture" / "prior_art_novelty_audit.md", "# Prior Art Novelty Audit\n")
    _write_jsonl(workspace / "outputs" / "prior_art_novelty_audit_fixture" / "prior_art_novelty_audit_summary.jsonl", [{"q2b_prior_art_position_defensible": False}])
    _write_jsonl(workspace / "outputs" / "mechanism_triangulation_audit_fixture" / "mechanism_triangulation_audit.jsonl", [{"pair_id": "p1"}])
    _write_jsonl(workspace / "outputs" / "mechanism_triangulation_audit_fixture" / "mechanism_triangulation_systems.jsonl", [{"system": "scincl_cosine_open_v2"}])
    _write_jsonl(workspace / "outputs" / "mechanism_triangulation_audit_fixture" / "mechanism_triangulation_summary.jsonl", [{"triangulation_status": "cross_system_mechanism_evidence"}])
    _write_text(workspace / "outputs" / "mechanism_triangulation_audit_fixture" / "mechanism_triangulation_audit.csv", "pair_id,triangulation_pattern\n")
    _write_text(workspace / "outputs" / "mechanism_triangulation_audit_fixture" / "mechanism_triangulation_systems.csv", "system,baseline_false_merge_count\n")
    _write_text(workspace / "outputs" / "mechanism_triangulation_audit_fixture" / "mechanism_triangulation_audit.md", "# Mechanism Triangulation Audit\n")
    _write_jsonl(workspace / "outputs" / "mechanism_triangulation_sensitivity_fixture" / "mechanism_triangulation_sensitivity.jsonl", [{"setting_id": "triangulation_threshold_001"}])
    _write_jsonl(workspace / "outputs" / "mechanism_triangulation_sensitivity_fixture" / "mechanism_triangulation_sensitivity_summary.jsonl", [{"threshold_stability_status": "threshold_stable_cross_system_evidence"}])
    _write_text(workspace / "outputs" / "mechanism_triangulation_sensitivity_fixture" / "mechanism_triangulation_sensitivity.csv", "setting_id,threshold_setting\n")
    _write_text(workspace / "outputs" / "mechanism_triangulation_sensitivity_fixture" / "mechanism_triangulation_sensitivity.md", "# Mechanism Triangulation Sensitivity\n")
    _write_jsonl(workspace / "outputs" / "mechanism_case_pack_fixture" / "mechanism_case_pack.jsonl", [{"case_id": "mechanism_case_001"}])
    _write_jsonl(workspace / "outputs" / "mechanism_case_pack_fixture" / "mechanism_case_pack_summary.jsonl", [{"case_pack_status": "paper_ready_limited_case_pack"}])
    _write_text(workspace / "outputs" / "mechanism_case_pack_fixture" / "mechanism_case_pack.csv", "case_id,pair_id\n")
    _write_text(workspace / "outputs" / "mechanism_case_pack_fixture" / "mechanism_case_pack.md", "# Mechanism Case Pack\n")
    _write_jsonl(workspace / "outputs" / "q2b_action_board_fixture" / "q2b_action_board.jsonl", [{"action_id": "prepare_remote_environment"}])
    _write_text(workspace / "outputs" / "q2b_action_board_fixture" / "q2b_action_board.csv", "action_id,status\n")
    _write_text(workspace / "outputs" / "q2b_action_board_fixture" / "q2b_action_board.md", "# Q2/B Action Board\n")
    _write_jsonl(workspace / "outputs" / "q2b_action_board_fixture" / "q2b_action_board_summary.jsonl", [{"q2_b_ready": False}])
    _write_jsonl(workspace / "outputs" / "q2b_completion_audit_fixture" / "q2b_completion_audit.jsonl", [{"criterion_id": "q2b_final_goal"}])
    _write_text(workspace / "outputs" / "q2b_completion_audit_fixture" / "q2b_completion_audit.csv", "criterion_id,status\n")
    _write_text(workspace / "outputs" / "q2b_completion_audit_fixture" / "q2b_completion_audit.md", "# Q2/B Completion Audit\n")
    _write_jsonl(workspace / "outputs" / "q2b_completion_audit_fixture" / "q2b_completion_audit_summary.jsonl", [{"q2_b_goal_ready": False}])
    _write_jsonl(workspace / "outputs" / "q2b_external_blocker_audit_fixture" / "q2b_external_blocker_audit.jsonl", [{"blocker_id": "external_secret:OPENAI_API_KEY"}])
    _write_text(
        workspace / "outputs" / "q2b_external_blocker_audit_fixture" / "q2b_external_blocker_audit.csv",
        "blocker_id,status\n",
    )
    _write_text(
        workspace / "outputs" / "q2b_external_blocker_audit_fixture" / "q2b_external_blocker_audit.md",
        "# Q2/B External Blocker Audit\n",
    )
    _write_jsonl(
        workspace / "outputs" / "q2b_external_blocker_audit_fixture" / "q2b_external_blocker_audit_summary.jsonl",
        [{"external_secret_count": 1}],
    )
    _write_jsonl(workspace / "outputs" / "q2b_acceptance_rubric_fixture" / "q2b_acceptance_rubric.jsonl", [{"gate_id": "final_q2b_acceptance"}])
    _write_text(workspace / "outputs" / "q2b_acceptance_rubric_fixture" / "q2b_acceptance_rubric.csv", "gate_id,status\n")
    _write_text(workspace / "outputs" / "q2b_acceptance_rubric_fixture" / "q2b_acceptance_rubric.md", "# Q2/B Acceptance Rubric\n")
    _write_jsonl(workspace / "outputs" / "q2b_acceptance_rubric_fixture" / "q2b_acceptance_rubric_summary.jsonl", [{"q2b_acceptance_ready": False}])
    _write_jsonl(workspace / "outputs" / "q2b_experiment_optimizer_fixture" / "q2b_experiment_optimizer.jsonl", [{"experiment_id": "exp_remote_reproducibility_acceptance"}])
    _write_text(workspace / "outputs" / "q2b_experiment_optimizer_fixture" / "q2b_experiment_optimizer.csv", "experiment_id,status\n")
    _write_text(workspace / "outputs" / "q2b_experiment_optimizer_fixture" / "q2b_experiment_optimizer.md", "# Q2/B Experiment Optimizer\n")
    _write_jsonl(workspace / "outputs" / "q2b_experiment_optimizer_fixture" / "q2b_experiment_optimizer_summary.jsonl", [{"q2b_experiment_plan_ready": False}])
    _write_jsonl(workspace / "outputs" / "q2b_upgrade_roadmap_fixture" / "q2b_upgrade_roadmap.jsonl", [{"phase_id": "p0_remote_connection_and_secret"}])
    _write_text(workspace / "outputs" / "q2b_upgrade_roadmap_fixture" / "q2b_upgrade_roadmap.csv", "phase_id,status\n")
    _write_text(workspace / "outputs" / "q2b_upgrade_roadmap_fixture" / "q2b_upgrade_roadmap.md", "# Q2/B Upgrade Roadmap\n")
    _write_jsonl(workspace / "outputs" / "q2b_upgrade_roadmap_fixture" / "q2b_upgrade_roadmap_summary.jsonl", [{"q2_b_ready": False}])
    _write_jsonl(workspace / "outputs" / "public_data_validity_audit_fixture" / "public_data_validity_audit.jsonl", [{"dimension_id": "gold_scale"}])
    _write_text(workspace / "outputs" / "public_data_validity_audit_fixture" / "public_data_validity_audit.csv", "dimension_id,audit_status\n")
    _write_text(workspace / "outputs" / "public_data_validity_audit_fixture" / "public_data_validity_audit.md", "# Public Data Validity Audit\n")
    _write_jsonl(workspace / "outputs" / "public_data_validity_audit_fixture" / "public_data_validity_audit_summary.jsonl", [{"high_risk_count": 1}])
    _write_jsonl(workspace / "outputs" / "iad_bench_stratification_audit_fixture" / "iad_bench_stratification_audit.jsonl", [{"dimension_id": "label_strength_imbalance"}])
    _write_jsonl(workspace / "outputs" / "iad_bench_stratification_audit_fixture" / "iad_bench_strata_distribution.jsonl", [{"stratum_id": "label_strength_total"}])
    _write_text(workspace / "outputs" / "iad_bench_stratification_audit_fixture" / "iad_bench_stratification_audit.csv", "dimension_id,audit_status\n")
    _write_text(workspace / "outputs" / "iad_bench_stratification_audit_fixture" / "iad_bench_strata_distribution.csv", "stratum_id,pair_count\n")
    _write_text(workspace / "outputs" / "iad_bench_stratification_audit_fixture" / "iad_bench_stratification_audit.md", "# IAD-Bench Stratification Audit\n")
    _write_jsonl(workspace / "outputs" / "iad_bench_stratification_audit_fixture" / "iad_bench_stratification_audit_summary.jsonl", [{"high_risk_count": 1}])
    _write_jsonl(workspace / "outputs" / "iad_source_heldout_coverage_audit_fixture" / "iad_source_heldout_coverage_audit.jsonl", [{"relation_label": "agenda_non_identity"}])
    _write_text(workspace / "outputs" / "iad_source_heldout_coverage_audit_fixture" / "iad_source_heldout_coverage_audit.csv", "relation_label,audit_status\n")
    _write_text(workspace / "outputs" / "iad_source_heldout_coverage_audit_fixture" / "iad_source_heldout_coverage_audit.md", "# IAD Source-Heldout Coverage Audit\n")
    _write_jsonl(workspace / "outputs" / "iad_source_heldout_coverage_audit_fixture" / "iad_source_heldout_coverage_summary.jsonl", [{"source_heldout_full_iad_data_ready": False}])
    _write_jsonl(workspace / "outputs" / "iad_source_heldout_gap_plan_fixture" / "iad_source_heldout_gap_plan.jsonl", [{"relation_label": "agenda_non_identity"}])
    _write_text(workspace / "outputs" / "iad_source_heldout_gap_plan_fixture" / "iad_source_heldout_gap_plan.csv", "relation_label,gap_status\n")
    _write_text(workspace / "outputs" / "iad_source_heldout_gap_plan_fixture" / "iad_source_heldout_gap_plan.md", "# IAD Source-Heldout Gap Plan\n")
    _write_jsonl(workspace / "outputs" / "iad_source_heldout_gap_plan_fixture" / "iad_source_heldout_gap_plan_summary.jsonl", [{"source_heldout_gap_plan_ready": True}])
    _write_jsonl(workspace / "outputs" / "iad_bench_source_bias_diagnostic_fixture" / "iad_bench_source_bias_diagnostic.jsonl", [{"diagnostic_id": "label_source_to_relation_label"}])
    _write_jsonl(workspace / "outputs" / "iad_bench_source_bias_diagnostic_fixture" / "iad_bench_source_bias_predictions.jsonl", [{"pair_id": "p1"}])
    _write_text(workspace / "outputs" / "iad_bench_source_bias_diagnostic_fixture" / "iad_bench_source_bias_diagnostic.csv", "diagnostic_id,audit_status\n")
    _write_text(workspace / "outputs" / "iad_bench_source_bias_diagnostic_fixture" / "iad_bench_source_bias_predictions.csv", "pair_id,predicted_value\n")
    _write_text(workspace / "outputs" / "iad_bench_source_bias_diagnostic_fixture" / "iad_bench_source_bias_diagnostic.md", "# IAD-Bench Source Bias Diagnostic\n")
    _write_jsonl(workspace / "outputs" / "iad_bench_source_bias_diagnostic_fixture" / "iad_bench_source_bias_diagnostic_summary.jsonl", [{"high_risk_count": 1}])
    _write_jsonl(workspace / "outputs" / "iad_bench_source_candidate_registry_fixture" / "iad_bench_source_candidate_registry.jsonl", [{"candidate_id": "same_work_deepmatcher_dblp_scholar"}])
    _write_text(workspace / "outputs" / "iad_bench_source_candidate_registry_fixture" / "iad_bench_source_candidate_registry.csv", "candidate_id,candidate_status\n")
    _write_text(workspace / "outputs" / "iad_bench_source_candidate_registry_fixture" / "iad_bench_source_candidate_registry.md", "# IAD-Bench Source Candidate Registry\n")
    _write_jsonl(workspace / "outputs" / "iad_bench_source_candidate_registry_fixture" / "iad_bench_source_candidate_registry_summary.jsonl", [{"candidate_count": 1}])
    _write_jsonl(workspace / "outputs" / "iad_bench_source_acquisition_audit_fixture" / "iad_bench_source_acquisition_audit.jsonl", [{"candidate_id": "same_work_deepmatcher_dblp_scholar"}])
    _write_text(workspace / "outputs" / "iad_bench_source_acquisition_audit_fixture" / "iad_bench_source_acquisition_audit.csv", "candidate_id,local_status\n")
    _write_text(workspace / "outputs" / "iad_bench_source_acquisition_audit_fixture" / "iad_bench_source_acquisition_audit.md", "# IAD-Bench Source Acquisition Audit\n")
    _write_jsonl(workspace / "outputs" / "iad_bench_source_acquisition_audit_fixture" / "iad_bench_source_acquisition_audit_summary.jsonl", [{"candidate_count": 1}])
    _write_jsonl(workspace / "outputs" / "iad_model_feature_guard_fixture" / "iad_model_feature_guard.jsonl", [{"model_path": "model.json"}])
    _write_jsonl(workspace / "outputs" / "iad_model_feature_guard_fixture" / "iad_model_feature_guard_violations.jsonl", [{"feature_field": "label_source"}])
    _write_text(workspace / "outputs" / "iad_model_feature_guard_fixture" / "iad_model_feature_guard.csv", "model_path,audit_status\n")
    _write_text(workspace / "outputs" / "iad_model_feature_guard_fixture" / "iad_model_feature_guard_violations.csv", "feature_field,feature_path\n")
    _write_text(workspace / "outputs" / "iad_model_feature_guard_fixture" / "iad_model_feature_guard.md", "# IAD Model Feature Guard\n")
    _write_jsonl(workspace / "outputs" / "iad_model_feature_guard_fixture" / "iad_model_feature_guard_summary.jsonl", [{"violation_count": 1}])
    _write_jsonl(workspace / "outputs" / "open_v3_plan_audit_fixture" / "open_v3_plan_audit.jsonl", [{"dimension_id": "gold_pair_scale"}])
    _write_text(workspace / "outputs" / "open_v3_plan_audit_fixture" / "open_v3_plan_audit.csv", "dimension_id,audit_status\n")
    _write_text(workspace / "outputs" / "open_v3_plan_audit_fixture" / "open_v3_plan_audit.md", "# IAD-Bench-Open-v3 Plan Audit\n")
    _write_jsonl(workspace / "outputs" / "open_v3_plan_audit_fixture" / "open_v3_plan_audit_summary.jsonl", [{"blocked_count": 4}])
    _write_jsonl(workspace / "outputs" / "open_v3_source_plan_fixture" / "open_v3_source_plan.jsonl", [{"plan_id": "expand_openalex_topics"}])
    _write_text(workspace / "outputs" / "open_v3_source_plan_fixture" / "open_v3_source_plan.csv", "plan_id,status\n")
    _write_text(workspace / "outputs" / "open_v3_source_plan_fixture" / "open_v3_source_plan.md", "# IAD-Bench-Open-v3 Source Plan\n")
    _write_jsonl(workspace / "outputs" / "open_v3_source_plan_fixture" / "open_v3_source_plan_summary.jsonl", [{"needs_public_data_count": 2}])
    _write_jsonl(workspace / "outputs" / "open_v3_split_readiness_fixture" / "open_v3_split_readiness.jsonl", [{"dimension_id": "topic_held_out_readiness"}])
    _write_text(workspace / "outputs" / "open_v3_split_readiness_fixture" / "open_v3_split_readiness.csv", "dimension_id,audit_status\n")
    _write_text(workspace / "outputs" / "open_v3_split_readiness_fixture" / "open_v3_split_readiness.md", "# IAD-Bench-Open-v3 Split Readiness\n")
    _write_jsonl(workspace / "outputs" / "open_v3_split_readiness_fixture" / "open_v3_split_readiness_summary.jsonl", [{"blocked_count": 2}])
    _write_jsonl(workspace / "outputs" / "open_v3_heldout_split_plan_fixture" / "open_v3_heldout_split_plan.jsonl", [{"plan_id": "source_held_out_split"}])
    _write_jsonl(workspace / "outputs" / "open_v3_heldout_split_plan_fixture" / "open_v3_heldout_split_assignments.jsonl", [{"pair_id": "p1"}])
    _write_text(workspace / "outputs" / "open_v3_heldout_split_plan_fixture" / "open_v3_heldout_split_plan.csv", "plan_id,status\n")
    _write_text(workspace / "outputs" / "open_v3_heldout_split_plan_fixture" / "open_v3_heldout_split_assignments.csv", "pair_id,split\n")
    _write_text(workspace / "outputs" / "open_v3_heldout_split_plan_fixture" / "open_v3_heldout_split_plan.md", "# IAD-Bench-Open-v3 Held-out Split Plan\n")
    _write_jsonl(workspace / "outputs" / "open_v3_heldout_split_plan_fixture" / "open_v3_heldout_split_plan_summary.jsonl", [{"blocked_count": 2}])
    _write_jsonl(workspace / "outputs" / "mechanism_error_evidence_fixture" / "scincl" / "mechanism_error_evidence.jsonl", [{"system": "scincl_cosine_open_v2"}])
    _write_jsonl(workspace / "outputs" / "mechanism_error_evidence_fixture" / "scincl" / "mechanism_error_cases.jsonl", [{"pair_id": "p1"}])
    _write_jsonl(workspace / "outputs" / "mechanism_error_evidence_fixture" / "scincl" / "mechanism_error_strata.jsonl", [{"stratum_name": "hard_negative_level"}])
    _write_jsonl(workspace / "outputs" / "mechanism_error_evidence_fixture" / "scincl" / "mechanism_threshold_sensitivity.jsonl", [{"threshold": 0.9}])
    _write_text(workspace / "outputs" / "mechanism_error_evidence_fixture" / "scincl" / "mechanism_error_evidence.csv", "system,mechanism_status\n")
    _write_text(workspace / "outputs" / "mechanism_error_evidence_fixture" / "scincl" / "mechanism_error_cases.csv", "pair_id,case_type\n")
    _write_text(workspace / "outputs" / "mechanism_error_evidence_fixture" / "scincl" / "mechanism_error_strata.csv", "stratum_name,stratum_value\n")
    _write_text(workspace / "outputs" / "mechanism_error_evidence_fixture" / "scincl" / "mechanism_threshold_sensitivity.csv", "threshold,prevention_rate\n")
    _write_text(workspace / "outputs" / "mechanism_error_evidence_fixture" / "scincl" / "mechanism_error_evidence.md", "# Mechanism Error Evidence\n")
    _write_jsonl(workspace / "outputs" / "mechanism_error_evidence_fixture" / "scincl" / "mechanism_error_evidence_summary.jsonl", [{"case_count": 1}])
    _write_jsonl(workspace / "outputs" / "iad_bench_fixture" / "iad_bench_summary.jsonl", [{"evidence_layer": "iad_bench_provenance"}])
    _write_jsonl(workspace / "outputs" / "iad_bench_fixture" / "iad_bench_pairs.jsonl", [{"pair_id": "iadbench_000001"}])
    _write_jsonl(workspace / "outputs" / "iad_bench_fixture" / "iad_bench_documents.jsonl", [{"document_id": "doc1"}])
    _write_jsonl(workspace / "outputs" / "iad_bench_fixture" / "iad_bench_splits.jsonl", [{"pair_id": "iadbench_000001", "split": "train"}])
    _write_text(workspace / "outputs" / "iad_bench_fixture" / "label_provenance_summary.csv", "label_source,label_strength,relation_label,split,pair_count\n")
    _write_text(workspace / "outputs" / "iad_bench_fixture" / "dataset_card.md", "# IAD-Bench Dataset Card\n")
    _write_jsonl(workspace / "outputs" / "strong_baseline_fixture" / "baseline_scores.jsonl", [{"system": "hashing_representation_cosine"}])
    _write_jsonl(workspace / "outputs" / "strong_baseline_fixture" / "baseline_execution_summary.jsonl", [{"execution_mode": "fallback"}])
    _write_jsonl(workspace / "outputs" / "strong_baseline_fixture" / "baseline_metric_summary.jsonl", [{"execution_mode": "fallback", "f1": 0.5}])
    _write_jsonl(workspace / "outputs" / "strong_baseline_fixture" / "baseline_scored_relations.jsonl", [{"score": 0.5}])
    _write_jsonl(workspace / "outputs" / "strong_baseline_fixture" / "scincl_scores.jsonl", [{"system": "scincl_cosine"}])
    _write_jsonl(workspace / "outputs" / "strong_baseline_fixture" / "scincl_execution_summary.jsonl", [{"execution_mode": "actual_model"}])
    _write_jsonl(workspace / "outputs" / "strong_baseline_fixture" / "scincl_metric_summary.jsonl", [{"execution_mode": "actual_model", "f1": 0.5}])
    _write_jsonl(workspace / "outputs" / "strong_baseline_fixture" / "scincl_scored_relations.jsonl", [{"scincl_score": 0.5}])
    _write_jsonl(workspace / "outputs" / "baseline_error_analysis_fixture" / "scincl" / "baseline_error_summary.jsonl", [{"hard_negative_false_merge_rate": 1.0}])
    _write_jsonl(workspace / "outputs" / "baseline_error_analysis_fixture" / "scincl" / "baseline_error_cases.jsonl", [{"error_type": "hard_negative_false_merge"}])
    _write_text(workspace / "outputs" / "baseline_error_analysis_fixture" / "scincl" / "baseline_error_summary.csv", "system,hard_negative_false_merge_rate\n")
    _write_text(workspace / "outputs" / "baseline_error_analysis_fixture" / "scincl" / "baseline_error_cases.csv", "system,error_type\n")
    _write_text(workspace / "outputs" / "baseline_error_analysis_fixture" / "scincl" / "baseline_error_report.md", "# Baseline Error Report\n")
    _write_jsonl(workspace / "outputs" / "single_space_union_fixture" / "scincl" / "single_space_union_summary.jsonl", [{"f1": 0.5}])
    _write_jsonl(workspace / "outputs" / "single_space_union_fixture" / "scincl" / "single_space_union_predictions.jsonl", [{"single_space_union_prediction": 1}])
    _write_text(workspace / "outputs" / "single_space_union_fixture" / "scincl" / "single_space_union_summary.csv", "system,f1\n")
    _write_text(workspace / "outputs" / "single_space_union_fixture" / "scincl" / "single_space_union_report.md", "# Single-Space Union\n")
    _write_jsonl(workspace / "outputs" / "iad_risk_model_fixture" / "iad_risk_summary.jsonl", [{"evidence_layer": "iad_risk_model"}])
    _write_jsonl(workspace / "outputs" / "iad_risk_model_fixture" / "iad_risk_predictions.jsonl", [{"p_same_work": 0.9}])
    _write_text(workspace / "outputs" / "iad_risk_model_fixture" / "iad_risk_model.json", "{}\n")
    _write_jsonl(workspace / "outputs" / "iad_risk_transformer_scincl_provenance_blind_open_v2" / "iad_risk_transformer_summary.jsonl", [{"system": "iad_risk_transformer_scincl_provenance_blind_open_v2"}])
    _write_jsonl(workspace / "outputs" / "iad_risk_transformer_scincl_provenance_blind_open_v2" / "iad_risk_transformer_predictions.jsonl", [{"merge_prediction": 0}])
    _write_text(workspace / "outputs" / "iad_risk_transformer_scincl_provenance_blind_open_v2" / "iad_risk_transformer_model.json", "{}\n")
    _write_text(workspace / "outputs" / "iad_bootstrap_fixture" / "iad_risk_bootstrap_confidence.csv", "system,metric_scope\n")
    _write_jsonl(workspace / "outputs" / "openalex_api_ingestion_fixture" / "ingestion_summary.jsonl", [{"source": "openalex_api", "fetched_record_count": 10}])
    _write_jsonl(workspace / "outputs" / "openalex_api_fixture" / "dataset_summary.jsonl", [{"dataset_name": "openalex_api_sample", "pair_count": 2}])
    _write_jsonl(workspace / "outputs" / "openalex_api_fixture" / "eval_documents.jsonl", [{"document_id": "W1"}])
    _write_jsonl(workspace / "outputs" / "openalex_api_fixture" / "eval_pairs.jsonl", [{"expected_label": 0}])
    _write_jsonl(workspace / "outputs" / "iad_classifier_fixture" / "training_summary.jsonl", [{"target": "same_work", "trained": True}])
    _write_text(workspace / "outputs" / "iad_classifier_fixture" / "same_work_model.json", "{}\n")
    (workspace / "outputs" / "empty_parent_dir").mkdir(parents=True, exist_ok=True)

    manifest = export_topic_package(
        workspace_dir=workspace,
        output_dir=output_dir,
        report_dirs=[
            workspace / "outputs" / "iad_paper_report_fixture",
            workspace / "outputs" / "reviewer_audit_fixture",
            workspace / "outputs" / "experiment_preflight_fixture",
            workspace / "outputs" / "experiment_dependency_fixture",
                workspace / "outputs" / "experiment_execution_pack_fixture",
                workspace / "outputs" / "remote_output_validation_fixture",
                workspace / "outputs" / "remote_result_acceptance_fixture",
            workspace / "outputs" / "remote_environment_audit_fixture",
            workspace / "outputs" / "remote_execution_blueprint_fixture",
            workspace / "outputs" / "remote_connection_pack_fixture",
            workspace / "outputs" / "remote_input_request_fixture",
            workspace / "outputs" / "remote_execution_slice_fixture",
            workspace / "outputs" / "remote_slice_run_pack_fixture",
            workspace / "outputs" / "primary_remote_readiness_fixture",
            workspace / "outputs" / "primary_remote_handoff_fixture",
            workspace / "outputs" / "primary_track_claim_gate_fixture",
            workspace / "outputs" / "primary_track_superiority_protocol_fixture",
            workspace / "outputs" / "primary_track_superiority_evaluator_fixture",
            workspace / "outputs" / "no_annotation_protocol_fixture",
            workspace / "outputs" / "paper_claim_audit_fixture",
            workspace / "outputs" / "research_depth_audit_fixture",
            workspace / "outputs" / "submission_gate_audit_fixture",
            workspace / "outputs" / "manuscript_evidence_matrix_fixture",
            workspace / "outputs" / "reviewer_response_matrix_fixture",
            workspace / "outputs" / "reviewer_iteration_audit_fixture",
            workspace / "outputs" / "reviewer_threat_model_fixture",
            workspace / "outputs" / "manuscript_draft_skeleton_fixture",
            workspace / "outputs" / "journal_upgrade_plan_fixture",
            workspace / "outputs" / "advanced_model_evidence_fixture",
            workspace / "outputs" / "model_innovation_blueprint_fixture",
            workspace / "outputs" / "model_superiority_audit_fixture",
            workspace / "outputs" / "innovation_depth_stress_test_fixture",
            workspace / "outputs" / "novelty_falsification_matrix_fixture",
            workspace / "outputs" / "prior_art_novelty_audit_fixture",
            workspace / "outputs" / "mechanism_triangulation_audit_fixture",
            workspace / "outputs" / "mechanism_triangulation_sensitivity_fixture",
            workspace / "outputs" / "mechanism_case_pack_fixture",
            workspace / "outputs" / "q2b_action_board_fixture",
            workspace / "outputs" / "q2b_completion_audit_fixture",
            workspace / "outputs" / "q2b_external_blocker_audit_fixture",
            workspace / "outputs" / "q2b_acceptance_rubric_fixture",
            workspace / "outputs" / "q2b_experiment_optimizer_fixture",
            workspace / "outputs" / "q2b_upgrade_roadmap_fixture",
            workspace / "outputs" / "public_data_validity_audit_fixture",
            workspace / "outputs" / "iad_bench_stratification_audit_fixture",
            workspace / "outputs" / "iad_source_heldout_coverage_audit_fixture",
            workspace / "outputs" / "iad_source_heldout_gap_plan_fixture",
            workspace / "outputs" / "iad_bench_source_bias_diagnostic_fixture",
            workspace / "outputs" / "iad_bench_source_candidate_registry_fixture",
            workspace / "outputs" / "iad_bench_source_acquisition_audit_fixture",
            workspace / "outputs" / "iad_model_feature_guard_fixture",
            workspace / "outputs" / "open_v3_plan_audit_fixture",
            workspace / "outputs" / "open_v3_source_plan_fixture",
            workspace / "outputs" / "open_v3_split_readiness_fixture",
            workspace / "outputs" / "open_v3_heldout_split_plan_fixture",
            workspace / "outputs" / "mechanism_error_evidence_fixture" / "scincl",
            workspace / "outputs" / "iad_bench_fixture",
            workspace / "outputs" / "strong_baseline_fixture",
            workspace / "outputs" / "baseline_error_analysis_fixture" / "scincl",
            workspace / "outputs" / "single_space_union_fixture" / "scincl",
            workspace / "outputs" / "iad_risk_model_fixture",
            workspace / "outputs" / "iad_risk_transformer_scincl_provenance_blind_open_v2",
            workspace / "outputs" / "iad_bootstrap_fixture",
            workspace / "outputs" / "openalex_api_ingestion_fixture",
            workspace / "outputs" / "openalex_api_fixture",
            workspace / "outputs" / "empty_parent_dir",
        ],
        model_dir=workspace / "outputs" / "iad_classifier_fixture",
    )

    manifest_rows = read_records(output_dir / "manifest.jsonl")

    assert manifest
    assert (output_dir / "docs" / "README.md").exists()
    assert (output_dir / "docs" / "project-structure.md").exists()
    assert (output_dir / "docs" / "naming-convention.md").exists()
    assert (output_dir / "docs" / "GOAL.md").exists()
    assert (output_dir / "docs" / "iad-bench-contract.md").exists()
    assert (output_dir / "docs" / "data-processing-pipeline.md").exists()
    assert (output_dir / "docs" / "annotation-requirements.md").exists()
    assert (output_dir / "docs" / "data-and-artifact-release.md").exists()
    assert (output_dir / "docs" / "public-release-checklist.md").exists()
    assert not (output_dir / "docs" / "current-work-summary.md").exists()
    assert not (output_dir / "docs" / "remote-dev-setup.md").exists()
    assert not (output_dir / "docs" / "2026-06-12-iad-risk-redesign.md").exists()
    assert not (output_dir / "docs" / "2026-06-12-iad-evidence-bootstrap-design.md").exists()
    assert not (output_dir / "docs" / "2026-06-13-iad-risk-open-v3-redesign.md").exists()
    assert not (output_dir / "docs" / "2026-06-13-iad-risk-no-annotation-q2b-upgrade.md").exists()
    assert not (output_dir / "docs" / "2026-06-13-iad-risk-open-v3-implementation.md").exists()
    assert not (output_dir / "docs" / "2026-06-13-iad-risk-no-annotation-q2b-upgrade-implementation.md").exists()
    assert not (output_dir / "docs" / "2026-06-13-iad-source-candidate-registry.md").exists()
    assert not (output_dir / "docs" / "2026-06-13-q2b-remote-execution-closure.md").exists()
    assert not (output_dir / "docs" / "2026-06-13-q2b-experiment-optimizer.md").exists()
    assert (output_dir / "reports" / "iad_paper_report_fixture" / "paper_report.md").exists()
    assert (output_dir / "reports" / "experiment_preflight_fixture" / "experiment_preflight.jsonl").exists()
    assert (output_dir / "reports" / "experiment_preflight_fixture" / "experiment_preflight.csv").exists()
    assert (output_dir / "reports" / "experiment_preflight_fixture" / "experiment_preflight.md").exists()
    assert (output_dir / "reports" / "experiment_dependency_fixture" / "experiment_dependency.jsonl").exists()
    assert (output_dir / "reports" / "experiment_dependency_fixture" / "experiment_dependency.csv").exists()
    assert (output_dir / "reports" / "experiment_dependency_fixture" / "experiment_dependency.md").exists()
    assert (output_dir / "reports" / "experiment_execution_pack_fixture" / "experiment_execution_plan.jsonl").exists()
    assert (output_dir / "reports" / "experiment_execution_pack_fixture" / "experiment_execution_plan.csv").exists()
    assert (output_dir / "reports" / "experiment_execution_pack_fixture" / "experiment_execution_plan.md").exists()
    assert (output_dir / "reports" / "experiment_execution_pack_fixture" / "experiment_execution_scripts.jsonl").exists()
    assert (output_dir / "reports" / "experiment_execution_pack_fixture" / "remote_output_manifest.jsonl").exists()
    assert (output_dir / "reports" / "experiment_execution_pack_fixture" / "run_stage_00.sh").exists()
    assert (output_dir / "reports" / "experiment_execution_pack_fixture" / "remote_handoff.md").exists()
    assert (output_dir / "reports" / "remote_output_validation_fixture" / "remote_output_validation.jsonl").exists()
    assert (output_dir / "reports" / "remote_output_validation_fixture" / "remote_output_validation.csv").exists()
    assert (output_dir / "reports" / "remote_output_validation_fixture" / "remote_output_validation.md").exists()
    assert (output_dir / "reports" / "remote_output_validation_fixture" / "remote_output_validation_summary.jsonl").exists()
    assert (output_dir / "reports" / "remote_result_acceptance_fixture" / "remote_result_acceptance.jsonl").exists()
    assert (output_dir / "reports" / "remote_result_acceptance_fixture" / "remote_result_acceptance.csv").exists()
    assert (output_dir / "reports" / "remote_result_acceptance_fixture" / "remote_result_acceptance.md").exists()
    assert (output_dir / "reports" / "remote_result_acceptance_fixture" / "remote_result_acceptance_summary.jsonl").exists()
    assert (output_dir / "reports" / "remote_environment_audit_fixture" / "remote_environment_audit.jsonl").exists()
    assert (output_dir / "reports" / "remote_environment_audit_fixture" / "remote_environment_audit.csv").exists()
    assert (output_dir / "reports" / "remote_environment_audit_fixture" / "remote_environment_audit.md").exists()
    assert (output_dir / "reports" / "remote_environment_audit_fixture" / "remote_environment_audit_summary.jsonl").exists()
    assert (output_dir / "reports" / "remote_execution_blueprint_fixture" / "remote_execution_blueprint.jsonl").exists()
    assert (output_dir / "reports" / "remote_execution_blueprint_fixture" / "remote_execution_blueprint.csv").exists()
    assert (output_dir / "reports" / "remote_execution_blueprint_fixture" / "remote_execution_blueprint.md").exists()
    assert (output_dir / "reports" / "remote_execution_blueprint_fixture" / "remote_execution_blueprint_summary.jsonl").exists()
    assert (output_dir / "reports" / "remote_connection_pack_fixture" / "remote_connection_pack.jsonl").exists()
    assert (output_dir / "reports" / "remote_connection_pack_fixture" / "remote_connection_pack.csv").exists()
    assert (output_dir / "reports" / "remote_connection_pack_fixture" / "remote_connection_pack.md").exists()
    assert (output_dir / "reports" / "remote_connection_pack_fixture" / "remote_connection_pack_summary.jsonl").exists()
    assert (output_dir / "reports" / "remote_connection_pack_fixture" / "remote_connection.env.example").exists()
    assert (output_dir / "reports" / "remote_connection_pack_fixture" / "remote_connection_profile.template.json").exists()
    assert (output_dir / "reports" / "remote_connection_pack_fixture" / "remote_preflight.template.sh").exists()
    assert (output_dir / "reports" / "remote_connection_pack_fixture" / "remote_sync_and_run.template.sh").exists()
    assert (output_dir / "reports" / "remote_connection_pack_fixture" / "remote_pull_outputs.template.sh").exists()
    assert (output_dir / "reports" / "remote_connection_pack_fixture" / "remote_execution_runbook.md").exists()
    assert (output_dir / "reports" / "remote_input_request_fixture" / "remote_input_request.jsonl").exists()
    assert (output_dir / "reports" / "remote_input_request_fixture" / "remote_input_request.csv").exists()
    assert (output_dir / "reports" / "remote_input_request_fixture" / "remote_input_request.md").exists()
    assert (output_dir / "reports" / "remote_input_request_fixture" / "remote_input_request_summary.jsonl").exists()
    assert (output_dir / "reports" / "remote_execution_slice_fixture" / "remote_execution_slice.jsonl").exists()
    assert (output_dir / "reports" / "remote_execution_slice_fixture" / "remote_execution_slice.csv").exists()
    assert (output_dir / "reports" / "remote_execution_slice_fixture" / "remote_execution_slice.md").exists()
    assert (output_dir / "reports" / "remote_execution_slice_fixture" / "remote_execution_slice_summary.jsonl").exists()
    assert (output_dir / "reports" / "remote_slice_run_pack_fixture" / "remote_slice_run_pack.jsonl").exists()
    assert (output_dir / "reports" / "remote_slice_run_pack_fixture" / "remote_slice_run_pack.csv").exists()
    assert (output_dir / "reports" / "remote_slice_run_pack_fixture" / "remote_slice_run_pack.md").exists()
    assert (output_dir / "reports" / "remote_slice_run_pack_fixture" / "remote_slice_run_pack_summary.jsonl").exists()
    assert (output_dir / "reports" / "remote_slice_run_pack_fixture" / "remote_slice_run_scripts.jsonl").exists()
    assert (output_dir / "reports" / "remote_slice_run_pack_fixture" / "run_remote_slice_open_v3.template.sh").exists()
    assert (output_dir / "reports" / "primary_remote_readiness_fixture" / "primary_remote_readiness.jsonl").exists()
    assert (output_dir / "reports" / "primary_remote_readiness_fixture" / "primary_remote_readiness.csv").exists()
    assert (output_dir / "reports" / "primary_remote_readiness_fixture" / "primary_remote_readiness.md").exists()
    assert (output_dir / "reports" / "primary_remote_readiness_fixture" / "primary_remote_readiness_summary.jsonl").exists()
    assert (output_dir / "reports" / "primary_remote_handoff_fixture" / "primary_remote_handoff.jsonl").exists()
    assert (output_dir / "reports" / "primary_remote_handoff_fixture" / "primary_remote_handoff.csv").exists()
    assert (output_dir / "reports" / "primary_remote_handoff_fixture" / "primary_remote_handoff.md").exists()
    assert (output_dir / "reports" / "primary_remote_handoff_fixture" / "primary_remote_handoff_summary.jsonl").exists()
    assert (output_dir / "reports" / "primary_remote_handoff_fixture" / "run_primary_post_run_validation.sh").exists()
    assert (output_dir / "reports" / "primary_track_claim_gate_fixture" / "primary_track_claim_gate.jsonl").exists()
    assert (output_dir / "reports" / "primary_track_claim_gate_fixture" / "primary_track_claim_gate.csv").exists()
    assert (output_dir / "reports" / "primary_track_claim_gate_fixture" / "primary_track_claim_gate.md").exists()
    assert (output_dir / "reports" / "primary_track_claim_gate_fixture" / "primary_track_claim_gate_summary.jsonl").exists()
    assert (output_dir / "reports" / "primary_track_superiority_protocol_fixture" / "primary_track_superiority_protocol.jsonl").exists()
    assert (output_dir / "reports" / "primary_track_superiority_protocol_fixture" / "primary_track_superiority_protocol.csv").exists()
    assert (output_dir / "reports" / "primary_track_superiority_protocol_fixture" / "primary_track_superiority_protocol.md").exists()
    assert (output_dir / "reports" / "primary_track_superiority_protocol_fixture" / "primary_track_superiority_protocol_summary.jsonl").exists()
    assert (output_dir / "reports" / "primary_track_superiority_evaluator_fixture" / "primary_track_superiority_evaluator.jsonl").exists()
    assert (output_dir / "reports" / "primary_track_superiority_evaluator_fixture" / "primary_track_superiority_evaluator.csv").exists()
    assert (output_dir / "reports" / "primary_track_superiority_evaluator_fixture" / "primary_track_superiority_evaluator.md").exists()
    assert (output_dir / "reports" / "primary_track_superiority_evaluator_fixture" / "primary_track_superiority_evaluator_summary.jsonl").exists()
    assert (output_dir / "reports" / "no_annotation_protocol_fixture" / "no_annotation_protocol.jsonl").exists()
    assert (output_dir / "reports" / "no_annotation_protocol_fixture" / "no_annotation_protocol.csv").exists()
    assert (output_dir / "reports" / "no_annotation_protocol_fixture" / "no_annotation_protocol.md").exists()
    assert (output_dir / "reports" / "no_annotation_protocol_fixture" / "no_annotation_protocol_summary.jsonl").exists()
    assert (output_dir / "reports" / "paper_claim_audit_fixture" / "paper_claim_audit.jsonl").exists()
    assert (output_dir / "reports" / "paper_claim_audit_fixture" / "paper_claim_audit.csv").exists()
    assert (output_dir / "reports" / "paper_claim_audit_fixture" / "paper_claim_audit.md").exists()
    assert (output_dir / "reports" / "research_depth_audit_fixture" / "research_depth_audit.jsonl").exists()
    assert (output_dir / "reports" / "research_depth_audit_fixture" / "research_depth_audit.csv").exists()
    assert (output_dir / "reports" / "research_depth_audit_fixture" / "research_depth_audit.md").exists()
    assert (output_dir / "reports" / "submission_gate_audit_fixture" / "submission_gate_audit.jsonl").exists()
    assert (output_dir / "reports" / "submission_gate_audit_fixture" / "submission_gate_audit.csv").exists()
    assert (output_dir / "reports" / "submission_gate_audit_fixture" / "submission_gate_audit.md").exists()
    assert (output_dir / "reports" / "submission_gate_audit_fixture" / "submission_gate_audit_summary.jsonl").exists()
    assert (output_dir / "reports" / "manuscript_evidence_matrix_fixture" / "manuscript_evidence_matrix.jsonl").exists()
    assert (output_dir / "reports" / "manuscript_evidence_matrix_fixture" / "manuscript_evidence_matrix.csv").exists()
    assert (output_dir / "reports" / "manuscript_evidence_matrix_fixture" / "manuscript_evidence_matrix.md").exists()
    assert (output_dir / "reports" / "manuscript_evidence_matrix_fixture" / "manuscript_evidence_summary.jsonl").exists()
    assert (output_dir / "reports" / "reviewer_response_matrix_fixture" / "reviewer_response_matrix.jsonl").exists()
    assert (output_dir / "reports" / "reviewer_response_matrix_fixture" / "reviewer_response_matrix.csv").exists()
    assert (output_dir / "reports" / "reviewer_response_matrix_fixture" / "reviewer_response_matrix.md").exists()
    assert (output_dir / "reports" / "reviewer_response_matrix_fixture" / "reviewer_response_summary.jsonl").exists()
    assert (output_dir / "reports" / "reviewer_iteration_audit_fixture" / "reviewer_iteration_audit.jsonl").exists()
    assert (output_dir / "reports" / "reviewer_iteration_audit_fixture" / "reviewer_iteration_audit.csv").exists()
    assert (output_dir / "reports" / "reviewer_iteration_audit_fixture" / "reviewer_iteration_audit.md").exists()
    assert (output_dir / "reports" / "reviewer_iteration_audit_fixture" / "reviewer_iteration_audit_summary.jsonl").exists()
    assert (output_dir / "reports" / "reviewer_threat_model_fixture" / "reviewer_threat_model.jsonl").exists()
    assert (output_dir / "reports" / "reviewer_threat_model_fixture" / "reviewer_threat_model.csv").exists()
    assert (output_dir / "reports" / "reviewer_threat_model_fixture" / "reviewer_threat_model.md").exists()
    assert (output_dir / "reports" / "reviewer_threat_model_fixture" / "reviewer_threat_model_summary.jsonl").exists()
    assert (output_dir / "reports" / "manuscript_draft_skeleton_fixture" / "manuscript_draft_skeleton.jsonl").exists()
    assert (output_dir / "reports" / "manuscript_draft_skeleton_fixture" / "manuscript_draft_skeleton.md").exists()
    assert (output_dir / "reports" / "manuscript_draft_skeleton_fixture" / "manuscript_draft_skeleton_summary.jsonl").exists()
    assert (output_dir / "reports" / "journal_upgrade_plan_fixture" / "journal_upgrade_plan.jsonl").exists()
    assert (output_dir / "reports" / "journal_upgrade_plan_fixture" / "journal_upgrade_plan.csv").exists()
    assert (output_dir / "reports" / "journal_upgrade_plan_fixture" / "journal_upgrade_plan.md").exists()
    assert (output_dir / "reports" / "journal_upgrade_plan_fixture" / "journal_upgrade_plan_summary.jsonl").exists()
    assert (output_dir / "reports" / "advanced_model_evidence_fixture" / "advanced_model_evidence.jsonl").exists()
    assert (output_dir / "reports" / "advanced_model_evidence_fixture" / "advanced_model_evidence.csv").exists()
    assert (output_dir / "reports" / "advanced_model_evidence_fixture" / "advanced_model_evidence.md").exists()
    assert (output_dir / "reports" / "advanced_model_evidence_fixture" / "advanced_model_evidence_summary.jsonl").exists()
    assert (output_dir / "reports" / "model_innovation_blueprint_fixture" / "model_innovation_blueprint.jsonl").exists()
    assert (output_dir / "reports" / "model_innovation_blueprint_fixture" / "model_innovation_blueprint.csv").exists()
    assert (output_dir / "reports" / "model_innovation_blueprint_fixture" / "model_innovation_blueprint.md").exists()
    assert (output_dir / "reports" / "model_innovation_blueprint_fixture" / "model_innovation_blueprint_summary.jsonl").exists()
    assert (output_dir / "reports" / "model_superiority_audit_fixture" / "model_superiority_audit.jsonl").exists()
    assert (output_dir / "reports" / "model_superiority_audit_fixture" / "model_superiority_audit.csv").exists()
    assert (output_dir / "reports" / "model_superiority_audit_fixture" / "model_superiority_audit.md").exists()
    assert (output_dir / "reports" / "model_superiority_audit_fixture" / "model_superiority_audit_summary.jsonl").exists()
    assert (output_dir / "reports" / "innovation_depth_stress_test_fixture" / "innovation_depth_stress_test.jsonl").exists()
    assert (output_dir / "reports" / "innovation_depth_stress_test_fixture" / "innovation_depth_stress_test.csv").exists()
    assert (output_dir / "reports" / "innovation_depth_stress_test_fixture" / "innovation_depth_stress_test.md").exists()
    assert (output_dir / "reports" / "innovation_depth_stress_test_fixture" / "innovation_depth_stress_test_summary.jsonl").exists()
    assert (output_dir / "reports" / "novelty_falsification_matrix_fixture" / "novelty_falsification_matrix.jsonl").exists()
    assert (output_dir / "reports" / "novelty_falsification_matrix_fixture" / "novelty_falsification_matrix.csv").exists()
    assert (output_dir / "reports" / "novelty_falsification_matrix_fixture" / "novelty_falsification_matrix.md").exists()
    assert (output_dir / "reports" / "novelty_falsification_matrix_fixture" / "novelty_falsification_matrix_summary.jsonl").exists()
    assert (output_dir / "reports" / "prior_art_novelty_audit_fixture" / "prior_art_novelty_audit.jsonl").exists()
    assert (output_dir / "reports" / "prior_art_novelty_audit_fixture" / "prior_art_novelty_audit.csv").exists()
    assert (output_dir / "reports" / "prior_art_novelty_audit_fixture" / "prior_art_novelty_audit.md").exists()
    assert (output_dir / "reports" / "prior_art_novelty_audit_fixture" / "prior_art_novelty_audit_summary.jsonl").exists()
    assert (output_dir / "reports" / "mechanism_triangulation_audit_fixture" / "mechanism_triangulation_audit.jsonl").exists()
    assert (output_dir / "reports" / "mechanism_triangulation_audit_fixture" / "mechanism_triangulation_audit.csv").exists()
    assert (output_dir / "reports" / "mechanism_triangulation_audit_fixture" / "mechanism_triangulation_audit.md").exists()
    assert (output_dir / "reports" / "mechanism_triangulation_audit_fixture" / "mechanism_triangulation_systems.jsonl").exists()
    assert (output_dir / "reports" / "mechanism_triangulation_audit_fixture" / "mechanism_triangulation_systems.csv").exists()
    assert (output_dir / "reports" / "mechanism_triangulation_audit_fixture" / "mechanism_triangulation_summary.jsonl").exists()
    assert (output_dir / "reports" / "mechanism_triangulation_sensitivity_fixture" / "mechanism_triangulation_sensitivity.jsonl").exists()
    assert (output_dir / "reports" / "mechanism_triangulation_sensitivity_fixture" / "mechanism_triangulation_sensitivity.csv").exists()
    assert (output_dir / "reports" / "mechanism_triangulation_sensitivity_fixture" / "mechanism_triangulation_sensitivity.md").exists()
    assert (output_dir / "reports" / "mechanism_triangulation_sensitivity_fixture" / "mechanism_triangulation_sensitivity_summary.jsonl").exists()
    assert (output_dir / "reports" / "mechanism_case_pack_fixture" / "mechanism_case_pack.jsonl").exists()
    assert (output_dir / "reports" / "mechanism_case_pack_fixture" / "mechanism_case_pack.csv").exists()
    assert (output_dir / "reports" / "mechanism_case_pack_fixture" / "mechanism_case_pack.md").exists()
    assert (output_dir / "reports" / "mechanism_case_pack_fixture" / "mechanism_case_pack_summary.jsonl").exists()
    assert (output_dir / "reports" / "q2b_action_board_fixture" / "q2b_action_board.jsonl").exists()
    assert (output_dir / "reports" / "q2b_action_board_fixture" / "q2b_action_board.csv").exists()
    assert (output_dir / "reports" / "q2b_action_board_fixture" / "q2b_action_board.md").exists()
    assert (output_dir / "reports" / "q2b_action_board_fixture" / "q2b_action_board_summary.jsonl").exists()
    assert (output_dir / "reports" / "q2b_completion_audit_fixture" / "q2b_completion_audit.jsonl").exists()
    assert (output_dir / "reports" / "q2b_completion_audit_fixture" / "q2b_completion_audit.csv").exists()
    assert (output_dir / "reports" / "q2b_completion_audit_fixture" / "q2b_completion_audit.md").exists()
    assert (output_dir / "reports" / "q2b_completion_audit_fixture" / "q2b_completion_audit_summary.jsonl").exists()
    assert (output_dir / "reports" / "q2b_external_blocker_audit_fixture" / "q2b_external_blocker_audit.jsonl").exists()
    assert (output_dir / "reports" / "q2b_external_blocker_audit_fixture" / "q2b_external_blocker_audit.csv").exists()
    assert (output_dir / "reports" / "q2b_external_blocker_audit_fixture" / "q2b_external_blocker_audit.md").exists()
    assert (output_dir / "reports" / "q2b_external_blocker_audit_fixture" / "q2b_external_blocker_audit_summary.jsonl").exists()
    assert (output_dir / "reports" / "q2b_acceptance_rubric_fixture" / "q2b_acceptance_rubric.jsonl").exists()
    assert (output_dir / "reports" / "q2b_acceptance_rubric_fixture" / "q2b_acceptance_rubric.csv").exists()
    assert (output_dir / "reports" / "q2b_acceptance_rubric_fixture" / "q2b_acceptance_rubric.md").exists()
    assert (output_dir / "reports" / "q2b_acceptance_rubric_fixture" / "q2b_acceptance_rubric_summary.jsonl").exists()
    assert (output_dir / "reports" / "q2b_experiment_optimizer_fixture" / "q2b_experiment_optimizer.jsonl").exists()
    assert (output_dir / "reports" / "q2b_experiment_optimizer_fixture" / "q2b_experiment_optimizer.csv").exists()
    assert (output_dir / "reports" / "q2b_experiment_optimizer_fixture" / "q2b_experiment_optimizer.md").exists()
    assert (output_dir / "reports" / "q2b_experiment_optimizer_fixture" / "q2b_experiment_optimizer_summary.jsonl").exists()
    assert (output_dir / "reports" / "q2b_upgrade_roadmap_fixture" / "q2b_upgrade_roadmap.jsonl").exists()
    assert (output_dir / "reports" / "q2b_upgrade_roadmap_fixture" / "q2b_upgrade_roadmap.csv").exists()
    assert (output_dir / "reports" / "q2b_upgrade_roadmap_fixture" / "q2b_upgrade_roadmap.md").exists()
    assert (output_dir / "reports" / "q2b_upgrade_roadmap_fixture" / "q2b_upgrade_roadmap_summary.jsonl").exists()
    assert (output_dir / "reports" / "public_data_validity_audit_fixture" / "public_data_validity_audit.jsonl").exists()
    assert (output_dir / "reports" / "public_data_validity_audit_fixture" / "public_data_validity_audit.csv").exists()
    assert (output_dir / "reports" / "public_data_validity_audit_fixture" / "public_data_validity_audit.md").exists()
    assert (output_dir / "reports" / "public_data_validity_audit_fixture" / "public_data_validity_audit_summary.jsonl").exists()
    assert (output_dir / "reports" / "iad_bench_stratification_audit_fixture" / "iad_bench_stratification_audit.jsonl").exists()
    assert (output_dir / "reports" / "iad_bench_stratification_audit_fixture" / "iad_bench_strata_distribution.jsonl").exists()
    assert (output_dir / "reports" / "iad_bench_stratification_audit_fixture" / "iad_bench_stratification_audit.csv").exists()
    assert (output_dir / "reports" / "iad_bench_stratification_audit_fixture" / "iad_bench_strata_distribution.csv").exists()
    assert (output_dir / "reports" / "iad_bench_stratification_audit_fixture" / "iad_bench_stratification_audit.md").exists()
    assert (output_dir / "reports" / "iad_bench_stratification_audit_fixture" / "iad_bench_stratification_audit_summary.jsonl").exists()
    assert (output_dir / "reports" / "iad_source_heldout_coverage_audit_fixture" / "iad_source_heldout_coverage_audit.jsonl").exists()
    assert (output_dir / "reports" / "iad_source_heldout_coverage_audit_fixture" / "iad_source_heldout_coverage_audit.csv").exists()
    assert (output_dir / "reports" / "iad_source_heldout_coverage_audit_fixture" / "iad_source_heldout_coverage_audit.md").exists()
    assert (output_dir / "reports" / "iad_source_heldout_coverage_audit_fixture" / "iad_source_heldout_coverage_summary.jsonl").exists()
    assert (output_dir / "reports" / "iad_source_heldout_gap_plan_fixture" / "iad_source_heldout_gap_plan.jsonl").exists()
    assert (output_dir / "reports" / "iad_source_heldout_gap_plan_fixture" / "iad_source_heldout_gap_plan.csv").exists()
    assert (output_dir / "reports" / "iad_source_heldout_gap_plan_fixture" / "iad_source_heldout_gap_plan.md").exists()
    assert (output_dir / "reports" / "iad_source_heldout_gap_plan_fixture" / "iad_source_heldout_gap_plan_summary.jsonl").exists()
    assert (output_dir / "reports" / "iad_bench_source_bias_diagnostic_fixture" / "iad_bench_source_bias_diagnostic.jsonl").exists()
    assert (output_dir / "reports" / "iad_bench_source_bias_diagnostic_fixture" / "iad_bench_source_bias_predictions.jsonl").exists()
    assert (output_dir / "reports" / "iad_bench_source_bias_diagnostic_fixture" / "iad_bench_source_bias_diagnostic.csv").exists()
    assert (output_dir / "reports" / "iad_bench_source_bias_diagnostic_fixture" / "iad_bench_source_bias_predictions.csv").exists()
    assert (output_dir / "reports" / "iad_bench_source_bias_diagnostic_fixture" / "iad_bench_source_bias_diagnostic.md").exists()
    assert (output_dir / "reports" / "iad_bench_source_bias_diagnostic_fixture" / "iad_bench_source_bias_diagnostic_summary.jsonl").exists()
    assert (output_dir / "reports" / "iad_bench_source_candidate_registry_fixture" / "iad_bench_source_candidate_registry.jsonl").exists()
    assert (output_dir / "reports" / "iad_bench_source_candidate_registry_fixture" / "iad_bench_source_candidate_registry.csv").exists()
    assert (output_dir / "reports" / "iad_bench_source_candidate_registry_fixture" / "iad_bench_source_candidate_registry.md").exists()
    assert (output_dir / "reports" / "iad_bench_source_candidate_registry_fixture" / "iad_bench_source_candidate_registry_summary.jsonl").exists()
    assert (output_dir / "reports" / "iad_bench_source_acquisition_audit_fixture" / "iad_bench_source_acquisition_audit.jsonl").exists()
    assert (output_dir / "reports" / "iad_bench_source_acquisition_audit_fixture" / "iad_bench_source_acquisition_audit.csv").exists()
    assert (output_dir / "reports" / "iad_bench_source_acquisition_audit_fixture" / "iad_bench_source_acquisition_audit.md").exists()
    assert (output_dir / "reports" / "iad_bench_source_acquisition_audit_fixture" / "iad_bench_source_acquisition_audit_summary.jsonl").exists()
    assert (output_dir / "reports" / "iad_model_feature_guard_fixture" / "iad_model_feature_guard.jsonl").exists()
    assert (output_dir / "reports" / "iad_model_feature_guard_fixture" / "iad_model_feature_guard_violations.jsonl").exists()
    assert (output_dir / "reports" / "iad_model_feature_guard_fixture" / "iad_model_feature_guard.csv").exists()
    assert (output_dir / "reports" / "iad_model_feature_guard_fixture" / "iad_model_feature_guard_violations.csv").exists()
    assert (output_dir / "reports" / "iad_model_feature_guard_fixture" / "iad_model_feature_guard.md").exists()
    assert (output_dir / "reports" / "iad_model_feature_guard_fixture" / "iad_model_feature_guard_summary.jsonl").exists()
    assert (output_dir / "reports" / "open_v3_plan_audit_fixture" / "open_v3_plan_audit.jsonl").exists()
    assert (output_dir / "reports" / "open_v3_plan_audit_fixture" / "open_v3_plan_audit.csv").exists()
    assert (output_dir / "reports" / "open_v3_plan_audit_fixture" / "open_v3_plan_audit.md").exists()
    assert (output_dir / "reports" / "open_v3_plan_audit_fixture" / "open_v3_plan_audit_summary.jsonl").exists()
    assert (output_dir / "reports" / "open_v3_source_plan_fixture" / "open_v3_source_plan.jsonl").exists()
    assert (output_dir / "reports" / "open_v3_source_plan_fixture" / "open_v3_source_plan.csv").exists()
    assert (output_dir / "reports" / "open_v3_source_plan_fixture" / "open_v3_source_plan.md").exists()
    assert (output_dir / "reports" / "open_v3_source_plan_fixture" / "open_v3_source_plan_summary.jsonl").exists()
    assert (output_dir / "reports" / "open_v3_split_readiness_fixture" / "open_v3_split_readiness.jsonl").exists()
    assert (output_dir / "reports" / "open_v3_split_readiness_fixture" / "open_v3_split_readiness.csv").exists()
    assert (output_dir / "reports" / "open_v3_split_readiness_fixture" / "open_v3_split_readiness.md").exists()
    assert (output_dir / "reports" / "open_v3_split_readiness_fixture" / "open_v3_split_readiness_summary.jsonl").exists()
    assert (output_dir / "reports" / "open_v3_heldout_split_plan_fixture" / "open_v3_heldout_split_plan.jsonl").exists()
    assert (output_dir / "reports" / "open_v3_heldout_split_plan_fixture" / "open_v3_heldout_split_assignments.jsonl").exists()
    assert (output_dir / "reports" / "open_v3_heldout_split_plan_fixture" / "open_v3_heldout_split_plan.csv").exists()
    assert (output_dir / "reports" / "open_v3_heldout_split_plan_fixture" / "open_v3_heldout_split_assignments.csv").exists()
    assert (output_dir / "reports" / "open_v3_heldout_split_plan_fixture" / "open_v3_heldout_split_plan.md").exists()
    assert (output_dir / "reports" / "open_v3_heldout_split_plan_fixture" / "open_v3_heldout_split_plan_summary.jsonl").exists()
    assert (output_dir / "reports" / "scincl" / "mechanism_error_evidence.jsonl").exists()
    assert (output_dir / "reports" / "scincl" / "mechanism_error_cases.jsonl").exists()
    assert (output_dir / "reports" / "scincl" / "mechanism_error_strata.jsonl").exists()
    assert (output_dir / "reports" / "scincl" / "mechanism_threshold_sensitivity.jsonl").exists()
    assert (output_dir / "reports" / "scincl" / "mechanism_error_evidence.csv").exists()
    assert (output_dir / "reports" / "scincl" / "mechanism_error_cases.csv").exists()
    assert (output_dir / "reports" / "scincl" / "mechanism_error_strata.csv").exists()
    assert (output_dir / "reports" / "scincl" / "mechanism_threshold_sensitivity.csv").exists()
    assert (output_dir / "reports" / "scincl" / "mechanism_error_evidence.md").exists()
    assert (output_dir / "reports" / "scincl" / "mechanism_error_evidence_summary.jsonl").exists()
    assert (output_dir / "reports" / "iad_bench_fixture" / "iad_bench_summary.jsonl").exists()
    assert (output_dir / "reports" / "iad_bench_fixture" / "label_provenance_summary.csv").exists()
    assert (output_dir / "reports" / "iad_bench_fixture" / "dataset_card.md").exists()
    assert (output_dir / "reports" / "strong_baseline_fixture" / "baseline_scores.jsonl").exists()
    assert (output_dir / "reports" / "strong_baseline_fixture" / "baseline_execution_summary.jsonl").exists()
    assert (output_dir / "reports" / "strong_baseline_fixture" / "baseline_metric_summary.jsonl").exists()
    assert (output_dir / "reports" / "strong_baseline_fixture" / "baseline_scored_relations.jsonl").exists()
    assert (output_dir / "reports" / "strong_baseline_fixture" / "scincl_scores.jsonl").exists()
    assert (output_dir / "reports" / "strong_baseline_fixture" / "scincl_execution_summary.jsonl").exists()
    assert (output_dir / "reports" / "strong_baseline_fixture" / "scincl_metric_summary.jsonl").exists()
    assert (output_dir / "reports" / "strong_baseline_fixture" / "scincl_scored_relations.jsonl").exists()
    assert (output_dir / "reports" / "scincl" / "baseline_error_summary.jsonl").exists()
    assert (output_dir / "reports" / "scincl" / "baseline_error_cases.jsonl").exists()
    assert (output_dir / "reports" / "scincl" / "baseline_error_report.md").exists()
    assert (output_dir / "reports" / "scincl" / "single_space_union_summary.jsonl").exists()
    assert (output_dir / "reports" / "scincl" / "single_space_union_predictions.jsonl").exists()
    assert (output_dir / "reports" / "scincl" / "single_space_union_report.md").exists()
    assert (output_dir / "reports" / "iad_risk_model_fixture" / "iad_risk_summary.jsonl").exists()
    assert (output_dir / "reports" / "iad_risk_model_fixture" / "iad_risk_predictions.jsonl").exists()
    assert (output_dir / "reports" / "iad_risk_model_fixture" / "iad_risk_model.json").exists()
    assert (output_dir / "reports" / "iad_risk_transformer_scincl_provenance_blind_open_v2" / "iad_risk_transformer_summary.jsonl").exists()
    assert (output_dir / "reports" / "iad_risk_transformer_scincl_provenance_blind_open_v2" / "iad_risk_transformer_predictions.jsonl").exists()
    assert (output_dir / "reports" / "iad_risk_transformer_scincl_provenance_blind_open_v2" / "iad_risk_transformer_model.json").exists()
    assert (output_dir / "reports" / "iad_bootstrap_fixture" / "iad_risk_bootstrap_confidence.csv").exists()
    assert (output_dir / "reports" / "openalex_api_ingestion_fixture" / "ingestion_summary.jsonl").exists()
    assert (output_dir / "reports" / "openalex_api_fixture" / "dataset_summary.jsonl").exists()
    assert (output_dir / "reports" / "openalex_api_fixture" / "eval_documents.jsonl").exists()
    assert (output_dir / "reports" / "openalex_api_fixture" / "eval_pairs.jsonl").exists()
    assert (output_dir / "models" / "training_summary.jsonl").exists()
    assert (output_dir / "models" / "same_work_model.json").exists()
    assert (output_dir / "PACKAGE_README.md").exists()
    assert any(row["artifact_group"] == "core_doc" for row in manifest_rows)
    assert any(row["artifact_group"] == "report" for row in manifest_rows)
    assert not any(row["artifact_name"] == "empty_parent_dir" and row["status"] == "missing" for row in manifest_rows)


def test_export_topic_package_marks_missing_optional_sources(tmp_path) -> None:
    """验证缺失可选源文件会进入 manifest，而不是抛异常。"""
    workspace = tmp_path / "workspace"
    output_dir = tmp_path / "topic_package"
    workspace.mkdir()

    manifest = export_topic_package(workspace_dir=workspace, output_dir=output_dir, report_dirs=[], model_dir=None)

    missing_rows = [row for row in manifest if row["status"] == "missing"]

    assert missing_rows
    assert (output_dir / "manifest.jsonl").exists()


def test_export_topic_package_excludes_historical_superpowers_docs_and_cleans_stale_docs(tmp_path) -> None:
    """验证最终课题包不导出历史过程文档并清理旧 docs 残留。"""
    workspace = tmp_path / "workspace"
    output_dir = tmp_path / "topic_package"
    _write_text(workspace / "README.md", "# iad-sieve\n")
    _write_text(workspace / "docs" / "method-design.md", "# Method\n")
    _write_text(workspace / "docs" / "current-work-summary.md", "当前主轨道只需补齐 remote_host 等连接字段。\n")
    _write_text(
        workspace / "docs" / "superpowers" / "plans" / "2026-06-13-q2b-remote-execution-closure.md",
        "补齐远程连接字段和 OPENAI_API_KEY 的远程安全配置确认\n",
    )
    _write_text(
        workspace / "docs" / "superpowers" / "specs" / "2026-06-13-iad-risk-no-annotation-q2b-upgrade.md",
        "OPENAI_API_KEY 已在远程安全配置的确认\n",
    )
    _write_text(output_dir / "docs" / "2026-06-13-q2b-remote-execution-closure.md", "旧导出残留\n")

    manifest = export_topic_package(workspace_dir=workspace, output_dir=output_dir, report_dirs=[], model_dir=None)

    assert not (output_dir / "docs" / "2026-06-13-q2b-remote-execution-closure.md").exists()
    assert not (output_dir / "docs" / "2026-06-13-iad-risk-no-annotation-q2b-upgrade.md").exists()
    assert not any(row["artifact_name"] == "q2b_remote_execution_closure_plan" and row["status"] == "copied" for row in manifest)
    assert not any(row["artifact_name"] == "iad_risk_no_annotation_q2b_upgrade" and row["status"] == "copied" for row in manifest)
    assert not (output_dir / "docs" / "current-work-summary.md").exists()
    assert (output_dir / "docs" / "method-design.md").exists()


def test_export_topic_package_cli_writes_package(tmp_path) -> None:
    """验证 CLI 写出课题包。"""
    workspace = tmp_path / "workspace"
    output_dir = tmp_path / "topic_package"
    _write_text(workspace / "README.md", "# iad-sieve\n")
    _write_text(workspace / "docs" / "GOAL.md", "# Goal\n")

    command_export_topic_package(
        Namespace(
            workspace_dir=str(workspace),
            output_dir=str(output_dir),
            report_dirs=[],
            model_dir=None,
        )
    )

    assert (output_dir / "manifest.jsonl").exists()
    assert (output_dir / "PACKAGE_README.md").exists()


def test_cli_includes_export_topic_package_command() -> None:
    """验证 CLI 暴露 export-topic-package 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "export-topic-package",
            "--workspace-dir",
            ".",
            "--output-dir",
            "outputs/topic_package_final",
            "--report-dirs",
            "outputs/iad_paper_report_fixture",
            "outputs/reviewer_audit_fixture",
            "--model-dir",
            "outputs/iad_classifier_fixture",
        ]
    )

    assert args.command == "export-topic-package"
    assert args.report_dirs == ["outputs/iad_paper_report_fixture", "outputs/reviewer_audit_fixture"]
