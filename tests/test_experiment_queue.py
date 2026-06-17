"""测试下一轮期刊实验队列生成。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_experiment_queue
from iad_sieve.evaluation.experiment_queue import build_experiment_queue_rows, write_experiment_queue_outputs
from iad_sieve.utils.io_utils import read_records


def _write_jsonl(path, records: list[dict]) -> None:
    """写入 JSONL 测试文件。

    参数:
        path: 输出路径。
        records: 记录列表。

    返回:
        无。
    """
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def test_build_experiment_queue_rows_generates_commands_for_missing_high_priority_gates(tmp_path) -> None:
    """验证缺失的 high priority readiness gate 会生成可执行实验命令。"""
    readiness = tmp_path / "journal_readiness.jsonl"
    _write_jsonl(
        readiness,
        [
            {"gate_id": "specter2_adapter_actual_model", "status": "needs_evidence", "severity": "high", "next_experiment_rank": 1},
            {"gate_id": "llm_pair_judge_api_model", "status": "needs_evidence", "severity": "high", "next_experiment_rank": 2},
            {"gate_id": "scincl_actual_model", "status": "evidence_ready", "severity": "medium", "next_experiment_rank": 4},
        ],
    )

    rows = build_experiment_queue_rows([readiness])
    by_task = {row["task_id"]: row for row in rows}

    assert "run_specter2_adapter_baseline_open_v2" in by_task
    assert "run_specter2_adapter_iad_risk_transformer_open_v2" in by_task
    assert "run_llm_pair_judge_api_model_open_v2" in by_task
    assert "--model-backend specter2-adapter" in by_task["run_specter2_adapter_baseline_open_v2"]["command"]
    assert "--api-backend transformers" in by_task["run_llm_pair_judge_api_model_open_v2"]["command"]
    assert "--model-name outputs/models/local_llm_judge" in by_task["run_llm_pair_judge_api_model_open_v2"]["command"]
    assert "--max-new-tokens 120" in by_task["run_llm_pair_judge_api_model_open_v2"]["command"]
    assert "--batch-size 16" in by_task["run_llm_pair_judge_api_model_open_v2"]["command"]
    assert "outputs/iad_risk_transformer_specter2_open_v2/iad_risk_transformer_predictions.jsonl" in by_task["run_specter2_adapter_iad_risk_transformer_open_v2"]["expected_outputs"]
    assert by_task["run_specter2_adapter_baseline_open_v2"]["resolves_gate"] == "specter2_adapter_actual_model"
    assert by_task["run_llm_pair_judge_api_model_open_v2"]["requires_remote"] is True
    assert by_task["run_llm_pair_judge_api_model_open_v2"]["requires_secret"] == ""


def test_build_experiment_queue_rows_includes_bootstrap_tasks_for_new_strong_baselines(tmp_path) -> None:
    """验证新强 baseline 队列包含 bootstrap 置信区间任务。"""
    readiness = tmp_path / "journal_readiness.jsonl"
    _write_jsonl(
        readiness,
        [
            {"gate_id": "specter2_adapter_actual_model", "status": "needs_evidence", "severity": "high", "next_experiment_rank": 1},
            {"gate_id": "llm_pair_judge_api_model", "status": "needs_evidence", "severity": "high", "next_experiment_rank": 2},
        ],
    )

    rows = build_experiment_queue_rows([readiness])
    by_task = {row["task_id"]: row for row in rows}

    assert "bootstrap_specter2_adapter_baseline_open_v2" in by_task
    assert "bootstrap_specter2_adapter_iad_risk_transformer_open_v2" in by_task
    assert "evaluate_llm_pair_judge_api_model_open_v2" in by_task
    assert "bootstrap_llm_pair_judge_api_model_open_v2" in by_task
    assert "--records outputs/strong_baseline_open_v2/specter2_adapter_scored_relations.jsonl" in by_task["bootstrap_specter2_adapter_baseline_open_v2"]["command"]
    assert "--execution-mode actual_model" in by_task["evaluate_llm_pair_judge_api_model_open_v2"]["command"]
    assert "--records outputs/strong_baseline_open_v2/gpt_pair_judge_scored_relations.jsonl" in by_task["bootstrap_llm_pair_judge_api_model_open_v2"]["command"]


def test_build_experiment_queue_rows_adds_balanced_gold_strong_baseline_tasks(tmp_path) -> None:
    """验证 balanced gold 主评估集进入强 baseline 和 IAD-Risk 队列。"""
    readiness = tmp_path / "journal_readiness.jsonl"
    _write_jsonl(
        readiness,
        [
            {"gate_id": "venue_readiness", "status": "needs_evidence", "severity": "high", "next_experiment_rank": 7},
            {"gate_id": "executed_strong_baselines", "status": "needs_evidence", "severity": "high", "next_experiment_rank": 8},
        ],
    )

    rows = build_experiment_queue_rows([readiness])
    by_task = {row["task_id"]: row for row in rows}

    assert "run_scincl_baseline_open_v3_balanced_gold" in by_task
    assert "evaluate_scincl_baseline_open_v3_balanced_gold" in by_task
    assert "run_roberta_pair_baseline_open_v3_balanced_gold" in by_task
    assert "evaluate_roberta_pair_baseline_open_v3_balanced_gold" in by_task
    assert "run_scincl_provenance_blind_iad_risk_transformer_open_v3_balanced_gold" in by_task
    assert "bootstrap_scincl_provenance_blind_iad_risk_transformer_open_v3_balanced_gold" in by_task
    assert "apply_source_heldout_split_open_v3_balanced_gold" in by_task
    assert "run_scincl_baseline_open_v3_balanced_gold_source_heldout" in by_task
    assert "evaluate_scincl_baseline_open_v3_balanced_gold_source_heldout" in by_task
    assert "run_roberta_pair_baseline_open_v3_balanced_gold_source_heldout" in by_task
    assert "evaluate_roberta_pair_baseline_open_v3_balanced_gold_source_heldout" in by_task
    assert "run_scincl_iad_risk_transformer_open_v3_balanced_gold_source_heldout" in by_task
    assert (
        "--documents outputs/iad_bench_open_v3_balanced_gold/iad_bench_documents.jsonl"
        in by_task["run_scincl_baseline_open_v3_balanced_gold"]["command"]
    )
    assert (
        "--pairs outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl"
        in by_task["run_roberta_pair_baseline_open_v3_balanced_gold"]["command"]
    )
    assert (
        "--output-dir outputs/iad_risk_transformer_scincl_open_v3_balanced_gold"
        in by_task["run_scincl_provenance_blind_iad_risk_transformer_open_v3_balanced_gold"]["command"]
    )
    assert (
        "--assignments outputs/open_v3_heldout_split_plan_balanced_gold/open_v3_heldout_split_assignments.jsonl"
        in by_task["apply_source_heldout_split_open_v3_balanced_gold"]["command"]
    )
    assert (
        "--pairs outputs/iad_bench_open_v3_balanced_gold_source_heldout/iad_bench_pairs.jsonl"
        in by_task["run_scincl_baseline_open_v3_balanced_gold_source_heldout"]["command"]
    )
    assert (
        "--split-field split --eval-splits test"
        in by_task["evaluate_scincl_baseline_open_v3_balanced_gold_source_heldout"]["command"]
    )
    assert by_task["run_scincl_baseline_open_v3_balanced_gold"]["requires_remote"] is True
    assert by_task["run_roberta_pair_baseline_open_v3_balanced_gold"]["requires_remote"] is True


def test_build_experiment_queue_rows_adds_scholarly_balanced_gold_tasks(tmp_path) -> None:
    """验证 scholarly-only 主评估集进入强 baseline 和 IAD-Risk 队列。"""
    readiness = tmp_path / "journal_readiness.jsonl"
    _write_jsonl(
        readiness,
        [
            {"gate_id": "venue_readiness", "status": "needs_evidence", "severity": "high", "next_experiment_rank": 7},
            {"gate_id": "executed_strong_baselines", "status": "needs_evidence", "severity": "high", "next_experiment_rank": 8},
        ],
    )

    rows = build_experiment_queue_rows([readiness])
    by_task = {row["task_id"]: row for row in rows}

    assert "run_scincl_baseline_open_v3_scholarly_balanced_gold" in by_task
    assert "evaluate_scincl_baseline_open_v3_scholarly_balanced_gold" in by_task
    assert "run_roberta_pair_baseline_open_v3_scholarly_balanced_gold" in by_task
    assert "evaluate_roberta_pair_baseline_open_v3_scholarly_balanced_gold" in by_task
    assert "run_scincl_provenance_blind_iad_risk_transformer_open_v3_scholarly_balanced_gold" in by_task
    assert "bootstrap_scincl_provenance_blind_iad_risk_transformer_open_v3_scholarly_balanced_gold" in by_task
    assert "bootstrap_scincl_baseline_open_v3_scholarly_balanced_gold" in by_task
    assert "bootstrap_roberta_pair_baseline_open_v3_scholarly_balanced_gold" in by_task
    assert "apply_source_heldout_split_open_v3_scholarly_balanced_gold" in by_task
    assert "run_scincl_baseline_open_v3_scholarly_balanced_gold_source_heldout" in by_task
    assert "evaluate_scincl_baseline_open_v3_scholarly_balanced_gold_source_heldout" in by_task
    assert "run_roberta_pair_baseline_open_v3_scholarly_balanced_gold_source_heldout" in by_task
    assert "evaluate_roberta_pair_baseline_open_v3_scholarly_balanced_gold_source_heldout" in by_task
    assert "train_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout" in by_task
    assert "run_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout" in by_task
    assert "evaluate_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout" in by_task
    assert "bootstrap_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout" in by_task
    assert "run_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout" in by_task
    assert "evaluate_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout" in by_task
    assert "bootstrap_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout" in by_task
    assert "run_scincl_iad_risk_transformer_open_v3_scholarly_balanced_gold_source_heldout" in by_task
    assert (
        "--documents outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_documents.jsonl"
        in by_task["run_scincl_baseline_open_v3_scholarly_balanced_gold"]["command"]
    )
    assert (
        "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl"
        in by_task["run_roberta_pair_baseline_open_v3_scholarly_balanced_gold"]["command"]
    )
    assert (
        "--output-dir outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold"
        in by_task["run_scincl_provenance_blind_iad_risk_transformer_open_v3_scholarly_balanced_gold"]["command"]
    )
    assert (
        "--records outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_scored_relations.jsonl"
        in by_task["bootstrap_scincl_baseline_open_v3_scholarly_balanced_gold"]["command"]
    )
    assert (
        "--output outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/scincl_bootstrap_confidence.csv"
        in by_task["bootstrap_scincl_baseline_open_v3_scholarly_balanced_gold"]["command"]
    )
    assert "--score-field scincl_score" in by_task["bootstrap_scincl_baseline_open_v3_scholarly_balanced_gold"]["command"]
    assert "--threshold 0.8" in by_task["bootstrap_scincl_baseline_open_v3_scholarly_balanced_gold"]["command"]
    assert (
        "--records outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_scored_relations.jsonl"
        in by_task["bootstrap_roberta_pair_baseline_open_v3_scholarly_balanced_gold"]["command"]
    )
    assert (
        "--output outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/roberta_pair_bootstrap_confidence.csv"
        in by_task["bootstrap_roberta_pair_baseline_open_v3_scholarly_balanced_gold"]["command"]
    )
    assert "--score-field roberta_pair_score" in by_task["bootstrap_roberta_pair_baseline_open_v3_scholarly_balanced_gold"]["command"]
    assert "--threshold 0.8" in by_task["bootstrap_roberta_pair_baseline_open_v3_scholarly_balanced_gold"]["command"]
    assert (
        "--assignments outputs/open_v3_heldout_split_plan_scholarly_balanced_gold/open_v3_heldout_split_assignments.jsonl"
        in by_task["apply_source_heldout_split_open_v3_scholarly_balanced_gold"]["command"]
    )
    assert (
        "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl"
        in by_task["run_scincl_baseline_open_v3_scholarly_balanced_gold_source_heldout"]["command"]
    )
    assert (
        "--split-field split --eval-splits test"
        in by_task["evaluate_scincl_baseline_open_v3_scholarly_balanced_gold_source_heldout"]["command"]
    )
    assert (
        "--system-name ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout"
        in by_task["train_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout"]["command"]
    )
    assert (
        "train-entity-matching-baseline"
        in by_task["train_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout"]["command"]
    )
    assert (
        "--output-dir outputs/models/ditto_style_em_source_heldout"
        in by_task["train_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout"]["command"]
    )
    assert (
        "--label-field expected_label"
        in by_task["train_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout"]["command"]
    )
    assert (
        "outputs/models/ditto_style_em_source_heldout_training_summary.jsonl"
        in by_task["train_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout"]["expected_outputs"]
    )
    assert (
        "--system-name ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout"
        in by_task["run_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout"]["command"]
    )
    assert (
        "--model-name outputs/models/ditto_style_em_source_heldout"
        in by_task["run_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout"]["command"]
    )
    assert (
        "--score-field ditto_match_probability"
        in by_task["run_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout"]["command"]
    )
    assert (
        "--system-name gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout"
        in by_task["run_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout"]["command"]
    )
    assert (
        "--api-backend transformers"
        in by_task["run_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout"]["command"]
    )
    assert (
        "--model-name outputs/models/local_llm_judge"
        in by_task["run_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout"]["command"]
    )
    assert (
        "--execution-mode actual_model"
        in by_task["evaluate_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout"]["command"]
    )
    assert by_task["train_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout"]["requires_remote"] is True
    assert by_task["run_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout"]["requires_remote"] is True
    assert by_task["run_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout"]["requires_remote"] is True
    assert by_task["run_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout"]["requires_secret"] == ""
    assert by_task["run_scincl_baseline_open_v3_scholarly_balanced_gold"]["requires_remote"] is True
    assert by_task["run_roberta_pair_baseline_open_v3_scholarly_balanced_gold"]["requires_remote"] is True


def test_build_experiment_queue_rows_adds_report_rebuild_after_blockers(tmp_path) -> None:
    """验证存在 blocker 时追加报告重建任务。"""
    readiness = tmp_path / "journal_readiness.jsonl"
    _write_jsonl(readiness, [{"gate_id": "venue_readiness", "status": "needs_evidence", "severity": "high", "next_experiment_rank": 7}])

    rows = build_experiment_queue_rows([readiness])
    task_ids = [row["task_id"] for row in rows]

    assert "rebuild_evidence_package_after_strong_baselines" in task_ids
    assert task_ids[-1] == "rebuild_evidence_package_after_strong_baselines"
    assert all("..." not in row["command"] for row in rows)
    rebuild_command = rows[-1]["command"]
    assert "check-experiment-queue" in rebuild_command
    assert "--output-dir outputs/experiment_preflight_fixture" in rebuild_command
    assert "build-experiment-dependency" in rebuild_command
    assert "--output-dir outputs/experiment_dependency_fixture" in rebuild_command
    assert "build-experiment-execution-pack" in rebuild_command
    assert "--output-dir outputs/experiment_execution_pack_fixture" in rebuild_command
    assert "validate-remote-outputs" in rebuild_command
    assert "--output-dir outputs/remote_output_validation_fixture" in rebuild_command
    assert "build-remote-result-acceptance" in rebuild_command
    assert "--remote-output-validation outputs/remote_output_validation_fixture/remote_output_validation.jsonl" in rebuild_command
    assert "--output-dir outputs/remote_result_acceptance_fixture" in rebuild_command
    assert "build-remote-environment-audit" in rebuild_command
    assert "--output-dir outputs/remote_environment_audit_fixture" in rebuild_command
    assert "build-remote-execution-blueprint" in rebuild_command
    assert "--execution-plan outputs/experiment_execution_pack_fixture/experiment_execution_plan.jsonl" in rebuild_command
    assert "--environment-audit outputs/remote_environment_audit_fixture/remote_environment_audit.jsonl" in rebuild_command
    assert "--remote-output-validation outputs/remote_output_validation_fixture/remote_output_validation.jsonl" in rebuild_command
    assert "--output-dir outputs/remote_execution_blueprint_fixture" in rebuild_command
    assert "build-remote-connection-pack" in rebuild_command
    assert "--execution-plan outputs/experiment_execution_pack_fixture/experiment_execution_plan.jsonl" in rebuild_command
    assert "--remote-blueprint outputs/remote_execution_blueprint_fixture/remote_execution_blueprint.jsonl" in rebuild_command
    assert "--profile outputs/remote_connection_profile.local.json" in rebuild_command
    assert "--output-dir outputs/remote_connection_pack_fixture" in rebuild_command
    assert "build-paper-claim-audit" in rebuild_command
    assert "--output-dir outputs/paper_claim_audit_fixture" in rebuild_command
    assert "build-research-depth-audit" in rebuild_command
    assert "--output-dir outputs/research_depth_audit_fixture" in rebuild_command
    assert "build-submission-gate-audit" in rebuild_command
    assert "--remote-connection-summaries outputs/remote_connection_pack_fixture/remote_connection_pack_summary.jsonl" in rebuild_command
    assert "--remote-result-acceptance-summaries outputs/remote_result_acceptance_fixture/remote_result_acceptance_summary.jsonl" in rebuild_command
    assert (
        "--source-bias-summaries outputs/iad_bench_source_bias_diagnostic_open_v3_balanced_gold/iad_bench_source_bias_diagnostic_summary.jsonl "
        "outputs/iad_bench_source_bias_diagnostic_open_v3_scholarly_balanced_gold/iad_bench_source_bias_diagnostic_summary.jsonl "
        "outputs/iad_bench_source_bias_diagnostic_fixture/iad_bench_source_bias_diagnostic_summary.jsonl"
        in rebuild_command
    )
    assert "--feature-guard-summaries outputs/iad_model_feature_guard_fixture/iad_model_feature_guard_summary.jsonl" in rebuild_command
    assert (
        "--provenance-balance-summaries outputs/iad_bench_provenance_balance_plan_open_v3_balanced_gold/iad_bench_provenance_balance_plan_summary.jsonl "
        "outputs/iad_bench_provenance_balance_plan_open_v3_scholarly_balanced_gold/iad_bench_provenance_balance_plan_summary.jsonl "
        "outputs/iad_bench_provenance_balance_plan_fixture/iad_bench_provenance_balance_plan_summary.jsonl"
        in rebuild_command
    )
    assert "score-eval-set" in rebuild_command
    assert "--output outputs/iad_bench_open_v3_balanced_gold_source_heldout/scored_relations.jsonl" in rebuild_command
    assert "build-iad-training-blend" in rebuild_command
    assert "--output-dir outputs/iad_training_blend_open_v3_gold_silver" in rebuild_command
    assert "--relations outputs/iad_training_blend_open_v3_gold_silver/iad_training_relations.jsonl" in rebuild_command
    assert "--output-dir outputs/iad_training_input_audit_open_v3_gold_silver" in rebuild_command
    assert "train-iad-risk-model" in rebuild_command
    assert "--output-dir outputs/iad_risk_open_v3_gold_silver" in rebuild_command
    assert "build-iad-risk-split-evaluation-audit" in rebuild_command
    assert "--output-dir outputs/iad_risk_split_evaluation_audit_open_v3_gold_silver" in rebuild_command
    assert "--training-input-summaries outputs/iad_training_input_audit_open_v3_gold_silver/iad_training_input_audit_summary.jsonl" in rebuild_command
    assert "--output-dir outputs/submission_gate_audit_fixture" in rebuild_command
    assert "build-manuscript-evidence-matrix" in rebuild_command
    assert "--output-dir outputs/manuscript_evidence_matrix_fixture" in rebuild_command
    assert "build-reviewer-response-matrix" in rebuild_command
    assert "--reviewer-audits outputs/reviewer_audit_fixture/reviewer_audit.jsonl" in rebuild_command
    assert "--research-depth-audits outputs/research_depth_audit_fixture/research_depth_audit.jsonl" in rebuild_command
    assert "--manuscript-evidence outputs/manuscript_evidence_matrix_fixture/manuscript_evidence_matrix.jsonl" in rebuild_command
    assert "--submission-gate-audits outputs/submission_gate_audit_fixture/submission_gate_audit.jsonl" in rebuild_command
    assert "--prior-art-audits outputs/prior_art_novelty_audit_fixture/prior_art_novelty_audit.jsonl" in rebuild_command
    assert "--output-dir outputs/reviewer_response_matrix_fixture" in rebuild_command
    assert "build-manuscript-draft-skeleton" in rebuild_command
    assert "--output-dir outputs/manuscript_draft_skeleton_fixture" in rebuild_command
    assert "build-journal-upgrade-plan" in rebuild_command
    assert "--output-dir outputs/journal_upgrade_plan_fixture" in rebuild_command
    assert "build-advanced-model-evidence" in rebuild_command
    assert "--output-dir outputs/advanced_model_evidence_fixture" in rebuild_command
    assert "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/deberta_pair_metric_summary.jsonl" in rebuild_command
    assert "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/deberta_pair_execution_summary.jsonl" in rebuild_command
    assert "deberta_pair_open_v3_scholarly_balanced_gold_source_heldout" in rebuild_command
    assert "build-q2b-action-board" in rebuild_command
    assert "--submission-gates outputs/submission_gate_audit_fixture/submission_gate_audit.jsonl" in rebuild_command
    assert "--remote-blueprint outputs/remote_execution_blueprint_fixture/remote_execution_blueprint.jsonl" in rebuild_command
    assert "--journal-upgrade-plan outputs/journal_upgrade_plan_fixture/journal_upgrade_plan.jsonl" in rebuild_command
    assert "--advanced-model-evidence outputs/advanced_model_evidence_fixture/advanced_model_evidence.jsonl" in rebuild_command
    assert "--remote-connection-pack outputs/remote_connection_pack_fixture/remote_connection_pack.jsonl" in rebuild_command
    assert "--output-dir outputs/q2b_action_board_fixture" in rebuild_command
    assert "build-q2b-completion-audit" in rebuild_command
    assert "--submission-summaries outputs/submission_gate_audit_fixture/submission_gate_audit_summary.jsonl" in rebuild_command
    assert "--q2b-summaries outputs/q2b_action_board_fixture/q2b_action_board_summary.jsonl" in rebuild_command
    assert "--reviewer-response-summaries outputs/reviewer_response_matrix_fixture/reviewer_response_summary.jsonl" in rebuild_command
    assert "--remote-connection-summaries outputs/remote_connection_pack_fixture/remote_connection_pack_summary.jsonl" in rebuild_command
    assert "--remote-result-acceptance-summaries outputs/remote_result_acceptance_fixture/remote_result_acceptance_summary.jsonl" in rebuild_command
    assert "--innovation-depth-summaries outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test_summary.jsonl" in rebuild_command
    assert "--advanced-model-summaries outputs/advanced_model_evidence_fixture/advanced_model_evidence_summary.jsonl" in rebuild_command
    assert (
        "--split-readiness-summaries outputs/open_v3_split_readiness_balanced_gold/open_v3_split_readiness_summary.jsonl "
        "outputs/open_v3_split_readiness_multitopic_silver_patch/open_v3_split_readiness_summary.jsonl "
        "outputs/open_v3_split_readiness_scholarly_balanced_gold/open_v3_split_readiness_summary.jsonl"
        in rebuild_command
    )
    assert (
        "--split-readiness-audits outputs/open_v3_split_readiness_balanced_gold/open_v3_split_readiness.jsonl "
        "outputs/open_v3_split_readiness_multitopic_silver_patch/open_v3_split_readiness.jsonl "
        "outputs/open_v3_split_readiness_scholarly_balanced_gold/open_v3_split_readiness.jsonl"
        in rebuild_command
    )
    assert "--training-input-summaries outputs/iad_training_input_audit_open_v3_gold_silver/iad_training_input_audit_summary.jsonl" in rebuild_command
    assert (
        "--source-heldout-coverage-summaries outputs/iad_source_heldout_coverage_audit_open_v3_balanced_gold/iad_source_heldout_coverage_summary.jsonl "
        "outputs/iad_source_heldout_coverage_audit_open_v3_scholarly_balanced_gold/iad_source_heldout_coverage_summary.jsonl "
        "outputs/iad_source_heldout_coverage_audit_coci_source_patch/iad_source_heldout_coverage_summary.jsonl"
        in rebuild_command
    )
    assert (
        "--split-evaluation-summaries outputs/iad_risk_split_evaluation_audit_open_v3_gold_silver/iad_risk_split_evaluation_audit_summary.jsonl "
        "outputs/iad_risk_split_evaluation_audit_source_heldout/iad_risk_split_evaluation_audit_summary.jsonl "
        "outputs/iad_risk_split_evaluation_audit_coci_source_patch_source_heldout/iad_risk_split_evaluation_audit_summary.jsonl"
        in rebuild_command
    )
    assert "--output-dir outputs/q2b_completion_audit_fixture" in rebuild_command
    assert "build-q2b-upgrade-roadmap" in rebuild_command
    assert "--completion-audit outputs/q2b_completion_audit_fixture/q2b_completion_audit.jsonl" in rebuild_command
    assert "--action-board outputs/q2b_action_board_fixture/q2b_action_board.jsonl" in rebuild_command
    assert "--output-dir outputs/q2b_upgrade_roadmap_fixture" in rebuild_command
    assert "build-reviewer-iteration-audit" in rebuild_command
    assert "--q2b-roadmap outputs/q2b_upgrade_roadmap_fixture/q2b_upgrade_roadmap.jsonl" in rebuild_command
    assert "--q2b-completion-audit outputs/q2b_completion_audit_fixture/q2b_completion_audit.jsonl" in rebuild_command
    assert "--output-dir outputs/reviewer_iteration_audit_fixture" in rebuild_command
    assert "build-remote-input-request" in rebuild_command
    assert "--remote-connection-pack outputs/remote_connection_pack_fixture/remote_connection_pack.jsonl" in rebuild_command
    assert "--reviewer-iteration outputs/reviewer_iteration_audit_fixture/reviewer_iteration_audit.jsonl" in rebuild_command
    assert "--output-dir outputs/remote_input_request_fixture" in rebuild_command
    assert "build-remote-execution-slice" in rebuild_command
    assert "--q2b-action-board outputs/q2b_action_board_fixture/q2b_action_board.jsonl" in rebuild_command
    assert "--remote-input-request outputs/remote_input_request_fixture/remote_input_request.jsonl" in rebuild_command
    assert "--remote-execution-blueprint outputs/remote_execution_blueprint_fixture/remote_execution_blueprint.jsonl" in rebuild_command
    assert "--output-dir outputs/remote_execution_slice_fixture" in rebuild_command
    assert "build-remote-slice-run-pack" in rebuild_command
    assert "--remote-execution-slice outputs/remote_execution_slice_fixture/remote_execution_slice.jsonl" in rebuild_command
    assert "--execution-plan outputs/experiment_execution_pack_fixture/experiment_execution_plan.jsonl" in rebuild_command
    assert "--output-dir outputs/remote_slice_run_pack_fixture" in rebuild_command
    assert rebuild_command.index("build-remote-execution-slice") < rebuild_command.index("build-remote-slice-run-pack")
    assert "build-primary-remote-readiness" in rebuild_command
    assert "--remote-input-request outputs/remote_input_request_fixture/remote_input_request.jsonl" in rebuild_command
    assert "--remote-execution-slice outputs/remote_execution_slice_fixture/remote_execution_slice.jsonl" in rebuild_command
    assert "--remote-slice-run-pack outputs/remote_slice_run_pack_fixture/remote_slice_run_pack.jsonl" in rebuild_command
    assert "--output-dir outputs/primary_remote_readiness_fixture" in rebuild_command
    assert rebuild_command.index("build-remote-slice-run-pack") < rebuild_command.index("build-primary-remote-readiness")
    assert "build-primary-remote-handoff" in rebuild_command
    assert "--primary-remote-readiness outputs/primary_remote_readiness_fixture/primary_remote_readiness.jsonl" in rebuild_command
    assert "--output-dir outputs/primary_remote_handoff_fixture" in rebuild_command
    assert rebuild_command.index("build-primary-remote-readiness") < rebuild_command.index("build-primary-remote-handoff")
    assert rebuild_command.index("build-primary-remote-handoff") < rebuild_command.index("build-no-annotation-protocol")
    assert "build-no-annotation-protocol" in rebuild_command
    assert "--public-data-validity outputs/public_data_validity_audit_open_v3_balanced_gold/public_data_validity_audit.jsonl" in rebuild_command
    assert "--remote-input-request outputs/remote_input_request_fixture/remote_input_request.jsonl" in rebuild_command
    assert "--output-dir outputs/no_annotation_protocol_fixture" in rebuild_command
    assert "build-q2b-acceptance-rubric" in rebuild_command
    assert "--remote-output-summary outputs/remote_output_validation_fixture/remote_output_validation_summary.jsonl" in rebuild_command
    assert "--remote-result-acceptance-summary outputs/remote_result_acceptance_fixture/remote_result_acceptance_summary.jsonl" in rebuild_command
    assert "--advanced-model-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_summary.jsonl" in rebuild_command
    assert "--model-superiority-summary outputs/model_superiority_audit_fixture/model_superiority_audit_summary.jsonl" in rebuild_command
    assert "--innovation-depth-summary outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test_summary.jsonl" in rebuild_command
    assert "--no-annotation-summary outputs/no_annotation_protocol_fixture/no_annotation_protocol_summary.jsonl" in rebuild_command
    assert "--novelty-summary outputs/novelty_falsification_matrix_fixture/novelty_falsification_matrix_summary.jsonl" in rebuild_command
    assert "--prior-art-summary outputs/prior_art_novelty_audit_fixture/prior_art_novelty_audit_summary.jsonl" in rebuild_command
    assert "--q2b-completion-summary outputs/q2b_completion_audit_fixture/q2b_completion_audit_summary.jsonl" in rebuild_command
    assert "--reviewer-iteration-summary outputs/reviewer_iteration_audit_fixture/reviewer_iteration_audit_summary.jsonl" in rebuild_command
    assert "--output-dir outputs/q2b_acceptance_rubric_fixture" in rebuild_command
    assert "build-primary-track-claim-gate" in rebuild_command
    assert "--primary-remote-handoff outputs/primary_remote_handoff_fixture/primary_remote_handoff.jsonl" in rebuild_command
    assert "--advanced-track-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_track_summary.jsonl" in rebuild_command
    assert "--model-superiority-summary outputs/model_superiority_audit_fixture/model_superiority_audit_summary.jsonl" in rebuild_command
    assert "--innovation-depth-summary outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test_summary.jsonl" in rebuild_command
    assert "--q2b-acceptance-summary outputs/q2b_acceptance_rubric_fixture/q2b_acceptance_rubric_summary.jsonl" in rebuild_command
    assert "--output-dir outputs/primary_track_claim_gate_fixture" in rebuild_command
    assert "build-primary-track-superiority-protocol" in rebuild_command
    assert "--primary-track-claim-gate outputs/primary_track_claim_gate_fixture/primary_track_claim_gate.jsonl" in rebuild_command
    assert "--advanced-track-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_track_summary.jsonl" in rebuild_command
    assert "--model-superiority-summary outputs/model_superiority_audit_fixture/model_superiority_audit_summary.jsonl" in rebuild_command
    assert "--output-dir outputs/primary_track_superiority_protocol_fixture" in rebuild_command
    assert "build-primary-track-superiority-evaluator" in rebuild_command
    assert (
        "--primary-track-superiority-protocol outputs/primary_track_superiority_protocol_fixture/primary_track_superiority_protocol.jsonl"
        in rebuild_command
    )
    assert (
        "--metric-summaries outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold/iad_risk_transformer_summary.jsonl "
        "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_metric_summary.jsonl "
        "outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_metric_summary.jsonl"
        in rebuild_command
    )
    assert (
        "--bootstrap-summaries outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/iad_risk_transformer_scincl_bootstrap_confidence.csv "
        "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/scincl_bootstrap_confidence.csv "
        "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/roberta_pair_bootstrap_confidence.csv"
        in rebuild_command
    )
    assert "--output-dir outputs/primary_track_superiority_evaluator_fixture" in rebuild_command
    assert "build-q2b-experiment-optimizer" in rebuild_command
    assert "--q2b-acceptance-rubric outputs/q2b_acceptance_rubric_fixture/q2b_acceptance_rubric.jsonl" in rebuild_command
    assert "--reviewer-iteration outputs/reviewer_iteration_audit_fixture/reviewer_iteration_audit.jsonl" in rebuild_command
    assert "--remote-input-request outputs/remote_input_request_fixture/remote_input_request.jsonl" in rebuild_command
    assert "--remote-execution-slice outputs/remote_execution_slice_fixture/remote_execution_slice.jsonl" in rebuild_command
    assert "--advanced-track-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_track_summary.jsonl" in rebuild_command
    assert "--output-dir outputs/q2b_experiment_optimizer_fixture" in rebuild_command
    assert "build-q2b-external-blocker-audit" in rebuild_command
    assert "--completion-audit outputs/q2b_completion_audit_fixture/q2b_completion_audit.jsonl" in rebuild_command
    assert "--action-board outputs/q2b_action_board_fixture/q2b_action_board.jsonl" in rebuild_command
    assert "--remote-result-acceptance outputs/remote_result_acceptance_fixture/remote_result_acceptance.jsonl" in rebuild_command
    assert "--advanced-model-evidence outputs/advanced_model_evidence_fixture/advanced_model_evidence.jsonl" in rebuild_command
    assert "--output-dir outputs/q2b_external_blocker_audit_fixture" in rebuild_command
    assert "build-reviewer-threat-model" in rebuild_command
    assert "--q2b-experiment-optimizer outputs/q2b_experiment_optimizer_fixture/q2b_experiment_optimizer.jsonl" in rebuild_command
    assert "--prior-art-audits outputs/prior_art_novelty_audit_fixture/prior_art_novelty_audit.jsonl" in rebuild_command
    assert "--reviewer-iterations outputs/reviewer_iteration_audit_fixture/reviewer_iteration_audit.jsonl" in rebuild_command
    assert "--output-dir outputs/reviewer_threat_model_fixture" in rebuild_command
    assert "outputs/remote_slice_run_pack_fixture" in rows[-1]["expected_outputs"]
    assert "outputs/primary_remote_readiness_fixture" in rows[-1]["expected_outputs"]
    assert "outputs/primary_remote_handoff_fixture" in rows[-1]["expected_outputs"]
    assert "outputs/primary_track_claim_gate_fixture" in rows[-1]["expected_outputs"]
    assert "outputs/primary_track_superiority_protocol_fixture" in rows[-1]["expected_outputs"]
    assert "outputs/primary_track_superiority_evaluator_fixture" in rows[-1]["expected_outputs"]
    assert "outputs/q2b_experiment_optimizer_fixture" in rows[-1]["expected_outputs"]
    assert "outputs/q2b_external_blocker_audit_fixture" in rows[-1]["expected_outputs"]
    assert "outputs/reviewer_threat_model_fixture" in rows[-1]["expected_outputs"]
    assert "build-novelty-falsification-matrix" in rebuild_command
    assert "build-prior-art-novelty-audit" in rebuild_command
    assert rebuild_command.index("build-novelty-falsification-matrix") < rebuild_command.index("build-q2b-acceptance-rubric")
    assert rebuild_command.index("build-novelty-falsification-matrix") < rebuild_command.index("build-prior-art-novelty-audit")
    assert rebuild_command.index("build-prior-art-novelty-audit") < rebuild_command.index("build-q2b-acceptance-rubric")
    assert rebuild_command.index("build-q2b-acceptance-rubric") < rebuild_command.index("build-q2b-experiment-optimizer")
    assert rebuild_command.index("build-q2b-acceptance-rubric") < rebuild_command.index("build-primary-track-claim-gate")
    assert rebuild_command.index("build-primary-track-claim-gate") < rebuild_command.index("build-q2b-experiment-optimizer")
    assert rebuild_command.index("build-primary-track-claim-gate") < rebuild_command.index("build-primary-track-superiority-protocol")
    assert rebuild_command.index("build-primary-track-superiority-protocol") < rebuild_command.index("build-primary-track-superiority-evaluator")
    assert rebuild_command.index("build-primary-track-superiority-evaluator") < rebuild_command.index("build-q2b-experiment-optimizer")
    assert rebuild_command.index("build-q2b-experiment-optimizer") < rebuild_command.index("build-q2b-external-blocker-audit")
    assert rebuild_command.index("build-q2b-external-blocker-audit") < rebuild_command.index("build-reviewer-threat-model")
    assert rebuild_command.index("build-reviewer-threat-model") < rebuild_command.index("export-topic-package")
    assert "mapfile -t REPORT_DIRS" not in rebuild_command
    assert "REPORT_DIRS=()" in rebuild_command
    assert "while IFS= read -r report_dir" in rebuild_command
    assert 'REPORT_DIRS+=("$report_dir")' in rebuild_command
    assert "find outputs -path outputs/topic_package_final -prune" in rebuild_command
    assert '--report-dirs "${REPORT_DIRS[@]}"' in rebuild_command
    assert "--model-innovation-blueprints outputs/model_innovation_blueprint_fixture/model_innovation_blueprint.jsonl" in rebuild_command
    assert "--innovation-depth-audits outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test.jsonl" in rebuild_command
    assert "--model-superiority-summary outputs/model_superiority_audit_fixture/model_superiority_audit_summary.jsonl" in rebuild_command
    assert "--no-annotation-summary outputs/no_annotation_protocol_fixture/no_annotation_protocol_summary.jsonl" in rebuild_command
    assert "--output-dir outputs/novelty_falsification_matrix_fixture" in rebuild_command
    assert "--novelty-matrices outputs/novelty_falsification_matrix_fixture/novelty_falsification_matrix.jsonl" in rebuild_command
    assert "--advanced-model-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_summary.jsonl" in rebuild_command
    assert "--snapshot-date 2026-06-13" in rebuild_command
    assert "--output-dir outputs/prior_art_novelty_audit_fixture" in rebuild_command
    assert "build-model-innovation-blueprint" in rebuild_command
    assert "--advanced-model-evidence outputs/advanced_model_evidence_fixture/advanced_model_evidence.jsonl" in rebuild_command
    assert "--q2b-completion-audits outputs/q2b_completion_audit_fixture/q2b_completion_audit.jsonl" in rebuild_command
    assert (
        "--split-readiness-audits outputs/open_v3_split_readiness_balanced_gold/open_v3_split_readiness.jsonl "
        "outputs/open_v3_split_readiness_multitopic_silver_patch/open_v3_split_readiness.jsonl "
        "outputs/open_v3_split_readiness_scholarly_balanced_gold/open_v3_split_readiness.jsonl"
        in rebuild_command
    )
    assert "--output-dir outputs/model_innovation_blueprint_fixture" in rebuild_command
    assert "build-model-superiority-audit" in rebuild_command
    assert "--model-innovation-blueprints outputs/model_innovation_blueprint_fixture/model_innovation_blueprint.jsonl" in rebuild_command
    assert "--main-system iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout" in rebuild_command
    assert (
        "--risk-protocols outputs/risk_protocol_iad_risk_open_v3_scholarly_balanced_gold_source_heldout/risk_calibrated_protocol.jsonl "
        "outputs/risk_protocol_scincl_open_v3_scholarly_balanced_gold_source_heldout/risk_calibrated_protocol.jsonl "
        "outputs/risk_protocol_roberta_open_v3_scholarly_balanced_gold_source_heldout/risk_calibrated_protocol.jsonl "
        "outputs/risk_protocol_deberta_open_v3_scholarly_balanced_gold_source_heldout/risk_calibrated_protocol.jsonl "
        "outputs/risk_protocol_specter2_adapter_open_v3_scholarly_balanced_gold_source_heldout/risk_calibrated_protocol.jsonl "
        "outputs/risk_protocol_iad_risk_specter2_open_v3_scholarly_balanced_gold_source_heldout/risk_calibrated_protocol.jsonl"
        in rebuild_command
    )
    assert "--output-dir outputs/model_superiority_audit_fixture" in rebuild_command
    assert "build-innovation-depth-stress-test" in rebuild_command
    assert "--model-superiority-audits outputs/model_superiority_audit_fixture/model_superiority_audit.jsonl" in rebuild_command
    assert "--mechanism-evidence outputs/mechanism_error_evidence_fixture/scincl/mechanism_error_evidence.jsonl outputs/mechanism_error_evidence_fixture/roberta_pair/mechanism_error_evidence.jsonl" in rebuild_command
    assert (
        "--split-readiness-audits outputs/open_v3_split_readiness_balanced_gold/open_v3_split_readiness.jsonl "
        "outputs/open_v3_split_readiness_multitopic_silver_patch/open_v3_split_readiness.jsonl "
        "outputs/open_v3_split_readiness_scholarly_balanced_gold/open_v3_split_readiness.jsonl"
        in rebuild_command
    )
    assert "--output-dir outputs/innovation_depth_stress_test_fixture" in rebuild_command
    assert "build-public-data-validity-audit" in rebuild_command
    assert "--output-dir outputs/public_data_validity_audit_fixture" in rebuild_command
    assert "--max-dominant-relation-label-ratio 0.8" in rebuild_command
    assert "build-iad-bench-stratification-audit" in rebuild_command
    assert "--output-dir outputs/iad_bench_stratification_audit_fixture" in rebuild_command
    assert "--max-top-strength-ratio 0.8" in rebuild_command
    assert "build-iad-bench-source-bias-diagnostic" in rebuild_command
    assert "--output-dir outputs/iad_bench_source_bias_diagnostic_fixture" in rebuild_command
    assert "--max-shortcut-accuracy 0.8" in rebuild_command
    assert "build-iad-bench-provenance-balance-plan" in rebuild_command
    assert "--output-dir outputs/iad_bench_provenance_balance_plan_fixture" in rebuild_command
    assert "--target-pairs-per-new-source 500" in rebuild_command
    assert "build-iad-bench-source-candidate-registry" in rebuild_command
    assert "--output-dir outputs/iad_bench_source_candidate_registry_fixture" in rebuild_command
    assert "--public-gold-source-ids deepmatcher_dblp_scholar deepmatcher_amazon_google" in rebuild_command
    assert "--openalex-topic-seed-ids T10009" in rebuild_command
    assert "build-iad-bench-source-acquisition-audit" in rebuild_command
    assert "--registry outputs/iad_bench_source_candidate_registry_fixture/iad_bench_source_candidate_registry.jsonl" in rebuild_command
    assert "--output-dir outputs/iad_bench_source_acquisition_audit_fixture" in rebuild_command
    assert "build-iad-model-feature-guard" in rebuild_command
    assert "--output-dir outputs/iad_model_feature_guard_fixture" in rebuild_command
    assert "outputs/iad_risk_transformer_open_v2/iad_risk_transformer_model.json" in rebuild_command
    assert "run_scincl_provenance_blind_iad_risk_transformer_open_v2" in task_ids
    assert "bootstrap_scincl_provenance_blind_iad_risk_transformer_open_v2" in task_ids
    assert "outputs/iad_risk_transformer_scincl_provenance_blind_open_v2/iad_risk_transformer_model.json" in rebuild_command
    assert "outputs/iad_risk_transformer_scincl_provenance_blind_open_v2/iad_risk_transformer_summary.jsonl" in rebuild_command
    assert "iad_risk_transformer_scincl_provenance_blind_open_v2" in rebuild_command
    assert "build-open-v3-plan-audit" in rebuild_command
    assert "--output-dir outputs/open_v3_plan_audit_fixture" in rebuild_command
    assert "--min-gold-pairs 2000" in rebuild_command
    assert "--min-topics 30" in rebuild_command
    assert "--max-top-topic-ratio 0.15" in rebuild_command
    assert "build-open-v3-source-plan" in rebuild_command
    assert "--output-dir outputs/open_v3_source_plan_fixture" in rebuild_command
    assert "--target-records-per-topic 2000" in rebuild_command
    assert "--topic-seed-ids T10009" in rebuild_command
    assert "build-open-v3-split-readiness" in rebuild_command
    assert "--output-dir outputs/open_v3_split_readiness_fixture" in rebuild_command
    assert "--min-topics-for-topic-holdout 30" in rebuild_command
    assert "build-open-v3-heldout-split-plan" in rebuild_command
    assert "--output-dir outputs/open_v3_heldout_split_plan_fixture" in rebuild_command
    assert "--topic-test-ratio 0.2" in rebuild_command
    assert "build-mechanism-error-evidence" in rebuild_command
    assert "--sweep-thresholds 0.5,0.7,0.8,0.9,0.95" in rebuild_command
    assert "--output-dir outputs/mechanism_error_evidence_fixture/scincl" in rebuild_command
    assert "--output-dir outputs/mechanism_error_evidence_fixture/roberta_pair" in rebuild_command
    assert "build-mechanism-triangulation-audit" in rebuild_command
    assert "--baseline-specs system=scincl_cosine_open_v2,path=outputs/strong_baseline_open_v2/scincl_scored_relations.jsonl,score_field=scincl_score,threshold=0.9" in rebuild_command
    assert "system=roberta_pair_open_v2,path=outputs/strong_baseline_open_v2/roberta_pair_scored_relations.jsonl,score_field=roberta_pair_score,threshold=0.8" in rebuild_command
    assert "--output-dir outputs/mechanism_triangulation_audit_fixture" in rebuild_command
    assert "build-mechanism-triangulation-sensitivity" in rebuild_command
    assert "thresholds=0.5|0.7|0.8|0.9|0.95" in rebuild_command
    assert (
        "'system=scincl_cosine_open_v2,path=outputs/strong_baseline_open_v2/scincl_scored_relations.jsonl,score_field=scincl_score,thresholds=0.5|0.7|0.8|0.9|0.95'"
        in rebuild_command
    )
    assert (
        "'system=roberta_pair_open_v2,path=outputs/strong_baseline_open_v2/roberta_pair_scored_relations.jsonl,score_field=roberta_pair_score,thresholds=0.5|0.7|0.8|0.9|0.95'"
        in rebuild_command
    )
    assert "--output-dir outputs/mechanism_triangulation_sensitivity_fixture" in rebuild_command
    assert "build-mechanism-case-pack" in rebuild_command
    assert "--triangulation outputs/mechanism_triangulation_audit_fixture/mechanism_triangulation_audit.jsonl" in rebuild_command
    assert "--documents outputs/iad_bench_open_v2/iad_bench_documents.jsonl" in rebuild_command
    assert "--max-cases-per-group 2" in rebuild_command
    assert "--output-dir outputs/mechanism_case_pack_fixture" in rebuild_command
    assert "--mechanism-triangulation-summaries outputs/mechanism_triangulation_audit_fixture/mechanism_triangulation_summary.jsonl" in rebuild_command
    assert "--mechanism-triangulation-sensitivity-summaries outputs/mechanism_triangulation_sensitivity_fixture/mechanism_triangulation_sensitivity_summary.jsonl" in rebuild_command
    assert "outputs/experiment_preflight_fixture" in rebuild_command
    assert "outputs/experiment_dependency_fixture" in rebuild_command
    assert "outputs/experiment_execution_pack_fixture" in rebuild_command
    assert "outputs/remote_output_validation_fixture" in rebuild_command
    assert "outputs/remote_result_acceptance_fixture" in rebuild_command
    assert "outputs/remote_environment_audit_fixture" in rebuild_command
    assert "outputs/remote_execution_blueprint_fixture" in rebuild_command
    assert "outputs/remote_connection_pack_fixture" in rebuild_command
    assert "outputs/remote_input_request_fixture" in rebuild_command
    assert "outputs/remote_execution_slice_fixture" in rebuild_command
    assert "outputs/no_annotation_protocol_fixture" in rebuild_command
    assert "outputs/q2b_acceptance_rubric_fixture" in rebuild_command
    assert "outputs/prior_art_novelty_audit_fixture" in rebuild_command
    assert "outputs/paper_claim_audit_fixture" in rebuild_command
    assert "outputs/research_depth_audit_fixture" in rebuild_command
    assert "outputs/submission_gate_audit_fixture" in rebuild_command
    assert "outputs/manuscript_evidence_matrix_fixture" in rebuild_command
    assert "outputs/reviewer_response_matrix_fixture" in rebuild_command
    assert "outputs/reviewer_iteration_audit_fixture" in rebuild_command
    assert "outputs/manuscript_draft_skeleton_fixture" in rebuild_command
    assert "outputs/journal_upgrade_plan_fixture" in rebuild_command
    assert "outputs/advanced_model_evidence_fixture" in rebuild_command
    assert "outputs/model_innovation_blueprint_fixture" in rebuild_command
    assert "outputs/model_superiority_audit_fixture" in rebuild_command
    assert "outputs/innovation_depth_stress_test_fixture" in rebuild_command
    assert "outputs/q2b_action_board_fixture" in rebuild_command
    assert "outputs/q2b_completion_audit_fixture" in rebuild_command
    assert "outputs/q2b_upgrade_roadmap_fixture" in rebuild_command
    assert "outputs/public_data_validity_audit_fixture" in rebuild_command
    assert "outputs/iad_bench_stratification_audit_fixture" in rebuild_command
    assert "outputs/iad_bench_source_bias_diagnostic_fixture" in rebuild_command
    assert "outputs/iad_bench_provenance_balance_plan_fixture" in rebuild_command
    assert "outputs/iad_bench_source_candidate_registry_fixture" in rebuild_command
    assert "outputs/iad_bench_source_acquisition_audit_fixture" in rebuild_command
    assert "outputs/iad_model_feature_guard_fixture" in rebuild_command
    assert "outputs/iad_risk_transformer_scincl_provenance_blind_open_v2" in rebuild_command
    assert "outputs/open_v3_plan_audit_fixture" in rebuild_command
    assert "outputs/open_v3_source_plan_fixture" in rebuild_command
    assert "outputs/open_v3_split_readiness_fixture" in rebuild_command
    assert "outputs/open_v3_heldout_split_plan_fixture" in rebuild_command
    assert "outputs/mechanism_error_evidence_fixture/scincl" in rebuild_command
    assert "outputs/mechanism_error_evidence_fixture/roberta_pair" in rebuild_command
    assert "outputs/mechanism_case_pack_fixture" in rebuild_command
    assert "outputs/mechanism_triangulation_audit_fixture" in rebuild_command
    assert "outputs/mechanism_triangulation_sensitivity_fixture" in rebuild_command


def test_build_experiment_queue_rebuilds_balanced_gold_evidence_package(tmp_path) -> None:
    """验证证据包重建命令包含 balanced gold 数据、审计和导出目录。"""
    readiness = tmp_path / "journal_readiness.jsonl"
    _write_jsonl(readiness, [{"gate_id": "venue_readiness", "status": "needs_evidence", "severity": "high", "next_experiment_rank": 7}])

    rows = build_experiment_queue_rows([readiness])
    rebuild_command = rows[-1]["command"]

    assert "build-iad-bench-balanced-subset" in rebuild_command
    assert "--output-dir outputs/iad_bench_open_v3_balanced_gold" in rebuild_command
    assert "--output-dir outputs/iad_bench_open_v3_scholarly_balanced_gold" in rebuild_command
    assert "--include-label-sources deepmatcher_dblp_scholar,deepmatcher_py_entitymatching_dblp_acm" in rebuild_command
    assert "outputs/iad_bench_open_v3/iad_bench_summary.jsonl" in rebuild_command
    assert "outputs/iad_bench_open_v3_balanced_gold/iad_bench_summary.jsonl" in rebuild_command
    assert "outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_summary.jsonl" in rebuild_command
    assert "--output-dir outputs/public_data_validity_audit_open_v3_balanced_gold" in rebuild_command
    assert "--output-dir outputs/public_data_validity_audit_open_v3_scholarly_balanced_gold" in rebuild_command
    assert "--output-dir outputs/iad_bench_stratification_audit_open_v3_balanced_gold" in rebuild_command
    assert "--output-dir outputs/iad_bench_stratification_audit_open_v3_scholarly_balanced_gold" in rebuild_command
    assert "--output-dir outputs/iad_bench_source_bias_diagnostic_open_v3_balanced_gold" in rebuild_command
    assert "--output-dir outputs/iad_bench_source_bias_diagnostic_open_v3_scholarly_balanced_gold" in rebuild_command
    assert "--output-dir outputs/iad_bench_provenance_balance_plan_open_v3_balanced_gold" in rebuild_command
    assert "--output-dir outputs/iad_bench_provenance_balance_plan_open_v3_scholarly_balanced_gold" in rebuild_command
    assert "--output-dir outputs/open_v3_split_readiness_balanced_gold" in rebuild_command
    assert "--output-dir outputs/open_v3_split_readiness_scholarly_balanced_gold" in rebuild_command
    assert "--output-dir outputs/open_v3_heldout_split_plan_balanced_gold" in rebuild_command
    assert "--output-dir outputs/open_v3_heldout_split_plan_scholarly_balanced_gold" in rebuild_command
    assert "outputs/strong_baseline_open_v3_balanced_gold/scincl_metric_summary.jsonl" in rebuild_command
    assert "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_metric_summary.jsonl" in rebuild_command
    assert "outputs/strong_baseline_open_v3_balanced_gold/roberta_pair_metric_summary.jsonl" in rebuild_command
    assert "outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_metric_summary.jsonl" in rebuild_command
    assert "outputs/iad_risk_transformer_scincl_open_v3_balanced_gold/iad_risk_transformer_summary.jsonl" in rebuild_command
    assert "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold/iad_risk_transformer_summary.jsonl" in rebuild_command
    assert "apply-heldout-split-assignment" in rebuild_command
    assert "--output-dir outputs/iad_bench_open_v3_balanced_gold_source_heldout" in rebuild_command
    assert "--output-dir outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout" in rebuild_command
    assert "build-iad-training-blend" in rebuild_command
    assert "--output-dir outputs/iad_training_blend_open_v3_gold_silver" in rebuild_command
    assert "build-iad-training-input-audit" in rebuild_command
    assert "--output-dir outputs/iad_training_input_audit_open_v3_gold_silver" in rebuild_command
    assert "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/scincl_metric_summary.jsonl" in rebuild_command
    assert "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_metric_summary.jsonl" in rebuild_command
    assert "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_metric_summary.jsonl" in rebuild_command
    assert "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_metric_summary.jsonl" in rebuild_command
    assert "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_execution_summary.jsonl" in rebuild_command
    assert "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_execution_summary.jsonl" in rebuild_command
    assert "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/ditto_style_em_source_heldout_bootstrap_confidence.csv" in rebuild_command
    assert "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/gpt_pair_judge_source_heldout_bootstrap_confidence.csv" in rebuild_command
    assert "ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout" in rebuild_command
    assert "gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout" in rebuild_command
    assert "outputs/iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout/iad_risk_transformer_summary.jsonl" in rebuild_command
    assert "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout/iad_risk_transformer_summary.jsonl" in rebuild_command
    assert "mapfile -t REPORT_DIRS" not in rebuild_command
    assert "REPORT_DIRS=()" in rebuild_command
    assert "while IFS= read -r report_dir" in rebuild_command
    assert 'REPORT_DIRS+=("$report_dir")' in rebuild_command
    assert "find outputs -path outputs/topic_package_final -prune" in rebuild_command
    assert '--report-dirs "${REPORT_DIRS[@]}"' in rebuild_command
    assert "outputs/iad_training_input_audit_source_heldout " not in rebuild_command
    assert "outputs/iad_risk_open_v3_gold_silver" in rebuild_command
    assert "outputs/iad_risk_split_evaluation_audit_open_v3_gold_silver" in rebuild_command
    assert "outputs/iad_bench_source_bias_diagnostic_open_v3_balanced_gold" in rebuild_command
    assert "outputs/iad_bench_source_bias_diagnostic_open_v3_scholarly_balanced_gold" in rebuild_command
    assert "outputs/open_v3_heldout_split_plan_balanced_gold" in rebuild_command
    assert "outputs/open_v3_heldout_split_plan_scholarly_balanced_gold" in rebuild_command


def test_write_experiment_queue_outputs_writes_jsonl_csv_and_markdown(tmp_path) -> None:
    """验证实验队列写出 JSONL、CSV 和 Markdown。"""
    output_dir = tmp_path / "experiment_queue"
    rows = [
        {
            "task_id": "run_specter2_adapter_baseline_open_v2",
            "priority": 1,
            "resolves_gate": "specter2_adapter_actual_model",
            "requires_remote": True,
            "requires_secret": "",
            "command": "python -m iad_sieve.cli run-representation-baseline --model-backend specter2-adapter",
            "expected_outputs": "outputs/strong_baseline_open_v2/specter2_adapter_scores.jsonl",
        }
    ]

    write_experiment_queue_outputs(rows, output_dir)

    assert read_records(output_dir / "experiment_queue.jsonl")[0]["task_id"] == "run_specter2_adapter_baseline_open_v2"
    assert (output_dir / "experiment_queue.csv").exists()
    assert "# Experiment Queue" in (output_dir / "experiment_queue.md").read_text(encoding="utf-8")


def test_build_experiment_queue_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出实验队列。"""
    readiness = tmp_path / "journal_readiness.jsonl"
    output_dir = tmp_path / "experiment_queue"
    _write_jsonl(readiness, [{"gate_id": "specter2_adapter_actual_model", "status": "needs_evidence", "severity": "high", "next_experiment_rank": 1}])

    command_build_experiment_queue(
        Namespace(
            readiness_reports=[str(readiness)],
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "experiment_queue.jsonl")
    assert (output_dir / "experiment_queue.md").exists()


def test_cli_includes_build_experiment_queue_command() -> None:
    """验证 CLI 暴露 build-experiment-queue 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-experiment-queue",
            "--readiness-reports",
            "outputs/journal_readiness_fixture/journal_readiness.jsonl",
            "--output-dir",
            "outputs/experiment_queue_fixture",
        ]
    )

    assert args.command == "build-experiment-queue"
    assert args.readiness_reports == ["outputs/journal_readiness_fixture/journal_readiness.jsonl"]
