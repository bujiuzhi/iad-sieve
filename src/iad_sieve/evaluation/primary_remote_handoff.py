"""主轨道远程执行交接包模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "handoff_id",
    "handoff_status",
    "primary_track",
    "primary_script_path",
    "connection_fields",
    "connection_field_count",
    "primary_required_secret_names",
    "missing_primary_secret_names",
    "deferred_global_secret_names",
    "unmapped_systems",
    "remote_task_order",
    "expected_outputs",
    "profile_command",
    "run_command",
    "post_run_validation",
    "post_run_validation_script",
    "post_run_validation_script_path",
    "post_run_validation_step_count",
    "post_run_validation_expected_outputs",
    "operator_note",
    "paper_claim_boundary",
]
TASK_ORDER = [
    "run_scincl_baseline_open_v3_scholarly_balanced_gold",
    "run_roberta_pair_baseline_open_v3_scholarly_balanced_gold",
    "run_scincl_provenance_blind_iad_risk_transformer_open_v3_scholarly_balanced_gold",
    "train_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
    "run_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
    "run_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout",
]
POST_RUN_VALIDATION_SCRIPT_NAME = "run_primary_post_run_validation.sh"
POST_RUN_VALIDATION_EXPECTED_OUTPUTS = [
    "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_metric_summary.jsonl",
    "outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_metric_summary.jsonl",
    "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_metric_summary.jsonl",
    "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_metric_summary.jsonl",
    "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/iad_risk_transformer_scincl_bootstrap_confidence.csv",
    "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/scincl_bootstrap_confidence.csv",
    "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/roberta_pair_bootstrap_confidence.csv",
    "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/ditto_style_em_source_heldout_bootstrap_confidence.csv",
    "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/gpt_pair_judge_source_heldout_bootstrap_confidence.csv",
    "outputs/advanced_model_evidence_fixture/advanced_model_evidence_track_summary.jsonl",
    "outputs/model_superiority_audit_fixture/model_superiority_audit_summary.jsonl",
    "outputs/q2b_acceptance_rubric_fixture/q2b_acceptance_rubric_summary.jsonl",
    "outputs/primary_track_superiority_evaluator_fixture/primary_track_superiority_evaluator_summary.jsonl",
    "outputs/q2b_experiment_optimizer_fixture/q2b_experiment_optimizer_summary.jsonl",
    "outputs/reviewer_threat_model_fixture/reviewer_threat_model_summary.jsonl",
]


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    if value is None:
        return ""
    return str(value).strip()


def _list_value(value: object) -> list[str]:
    """解析列表或分号分隔字符串。

    参数:
        value: 原始字段值。

    返回:
        字符串列表。
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    return [item.strip() for item in str(value).split(";") if item.strip()]


def _int_value(value: object) -> int:
    """解析整数。

    参数:
        value: 原始值。

    返回:
        整数；无法解析时返回 0。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _ordered_tasks(task_ids: list[str]) -> list[str]:
    """按主轨道推荐执行顺序排列任务。

    参数:
        task_ids: 原始任务 ID 列表。

    返回:
        排序后的任务 ID 列表。
    """
    priority = {task_id: index for index, task_id in enumerate(TASK_ORDER)}
    return sorted(task_ids, key=lambda task_id: (priority.get(task_id, len(TASK_ORDER)), task_id))


def _handoff_status(readiness_row: dict) -> str:
    """判定交接状态。

    参数:
        readiness_row: 主轨道 readiness 记录。

    返回:
        handoff 状态。
    """
    if _list_value(readiness_row.get("missing_connection_fields")):
        return "waiting_for_connection_fields"
    if _list_value(readiness_row.get("missing_primary_secret_names")):
        return "waiting_for_primary_secret"
    if _clean(readiness_row.get("readiness_status")) == "ready_to_run_primary_slice":
        return "ready_to_execute_primary_script"
    if _clean(readiness_row.get("readiness_status")) == "ready_primary_track_no_remote_tasks":
        return "ready_for_post_run_validation_only"
    if _clean(readiness_row.get("readiness_status")) == "blocked_unmapped_primary_tasks":
        return "waiting_for_primary_task_mapping"
    return "blocked_by_primary_readiness"


def _operator_note(readiness_row: dict, primary_tasks: list[str]) -> str:
    """生成主轨道交接说明。

    参数:
        readiness_row: 主轨道 readiness 记录。
        primary_tasks: 已排序的主轨道任务。

    返回:
        交接说明。
    """
    unmapped_systems = _list_value(readiness_row.get("unmapped_systems"))
    if unmapped_systems and not primary_tasks:
        return (
            "主轨道缺失系统尚未映射到可执行远程 task: "
            f"{'; '.join(unmapped_systems)}。不要重复执行已验收的 open_v3 SciNCL/RoBERTa/SPECTER2 任务。"
        )
    if not primary_tasks:
        return "主轨道当前没有待执行远程任务；本交接包只保留回传后的本地验证与证据包重建步骤。"
    missing_primary_secret_names = _list_value(readiness_row.get("missing_primary_secret_names"))
    if missing_primary_secret_names:
        return (
            f"先安全配置主轨道密钥: {', '.join(missing_primary_secret_names)}；"
            f"随后运行主轨道任务: {'; '.join(primary_tasks)}。"
        )
    if any("gpt_pair_judge" in task_id for task_id in primary_tasks):
        return (
            "主轨道使用本地 Transformers LLM judge；"
            "先确认 outputs/models/local_llm_judge 已在远程项目目录预置；"
            f"随后运行主轨道任务: {'; '.join(primary_tasks)}。"
        )
    return (
        "OPENAI_API_KEY 不属于 open_v3 scholarly 主轨道前置条件；"
        "主轨道先跑 SciNCL baseline、RoBERTa pair baseline 与 IAD-Risk Transformer。"
    )


def _profile_command(connection_fields: list[str]) -> str:
    """构造本地 profile 生成命令模板。

    参数:
        connection_fields: 连接字段列表。

    返回:
        profile 生成命令。
    """
    field_arguments = {
        "remote_host": '--remote-host "<remote_host>"',
        "remote_port": '--remote-port "<remote_port>"',
        "remote_user": '--remote-user "<remote_user>"',
        "ssh_key_path": '--ssh-key-path "<ssh_key_path>"',
        "remote_workspace": '--remote-workspace "<remote_workspace>"',
        "conda_env": '--conda-env "<conda_env>"',
    }
    parts = ["python -m iad_sieve.cli build-remote-connection-profile"]
    parts.extend(field_arguments[field] for field in connection_fields if field in field_arguments)
    parts.append("--output-path outputs/remote_connection_profile.local.json")
    return " ".join(parts)


def _post_run_validation_commands() -> list[str]:
    """构造主轨道远程回传后的本地证据闭环命令。

    参数:
        无。

    返回:
        按执行顺序排列的本地后处理命令列表。
    """
    return [
        (
            "python -m iad_sieve.cli validate-remote-outputs "
            "--manifest outputs/experiment_execution_pack_fixture/remote_output_manifest.jsonl "
            "--workspace-dir . --output-dir outputs/remote_output_validation_fixture"
        ),
        (
            "python -m iad_sieve.cli build-remote-result-acceptance "
            "--execution-plan outputs/experiment_execution_pack_fixture/experiment_execution_plan.jsonl "
            "--remote-output-validation outputs/remote_output_validation_fixture/remote_output_validation.jsonl "
            "--output-dir outputs/remote_result_acceptance_fixture"
        ),
        (
            "python -m iad_sieve.cli evaluate-external-baseline "
            "--relations outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
            "--baseline outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_scores.jsonl "
            "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_scored_relations.jsonl "
            "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_metric_summary.jsonl "
            "--system-name scincl_cosine_open_v3_scholarly_balanced_gold "
            "--score-field scincl_score --output-score-field scincl_score "
            "--thresholds 0.5,0.8,0.9 --metric-target same_work "
            "--baseline-family representation --execution-mode actual_model"
        ),
        (
            "python -m iad_sieve.cli evaluate-external-baseline "
            "--relations outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
            "--baseline outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_scores.jsonl "
            "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_scored_relations.jsonl "
            "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_metric_summary.jsonl "
            "--system-name roberta_pair_open_v3_scholarly_balanced_gold "
            "--score-field roberta_pair_score --output-score-field roberta_pair_score "
            "--thresholds 0.5,0.8,0.9 --metric-target same_work "
            "--baseline-family pair_classifier --execution-mode actual_model"
        ),
        (
            "python -m iad_sieve.cli evaluate-external-baseline "
            "--relations outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
            "--baseline outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_scores.jsonl "
            "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_scored_relations.jsonl "
            "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_metric_summary.jsonl "
            "--system-name ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout "
            "--score-field ditto_match_probability "
            "--output-score-field ditto_match_probability "
            "--thresholds 0.5,0.8,0.9 --metric-target same_work "
            "--baseline-family entity_matching --execution-mode actual_model "
            "--split-field split --eval-splits test"
        ),
        (
            "python -m iad_sieve.cli evaluate-external-baseline "
            "--relations outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
            "--baseline outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_scores.jsonl "
            "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_scored_relations.jsonl "
            "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_metric_summary.jsonl "
            "--system-name gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout "
            "--score-field gpt_same_work_probability "
            "--output-score-field gpt_same_work_probability "
            "--thresholds 0.5,0.8,0.9 --metric-target same_work "
            "--baseline-family llm_judge --execution-mode actual_model "
            "--split-field split --eval-splits test"
        ),
        (
            "python -m iad_sieve.cli run-iad-evidence-bootstrap "
            "--records outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold/iad_risk_transformer_predictions.jsonl "
            "--output outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/iad_risk_transformer_scincl_bootstrap_confidence.csv "
            "--system-name iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold "
            "--prediction-field merge_prediction --iterations 1000 --confidence-level 0.95 --seed 42"
        ),
        (
            "python -m iad_sieve.cli run-iad-evidence-bootstrap "
            "--records outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_scored_relations.jsonl "
            "--output outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/scincl_bootstrap_confidence.csv "
            "--system-name scincl_cosine_open_v3_scholarly_balanced_gold "
            "--score-field scincl_score --threshold 0.8 --iterations 1000 --confidence-level 0.95 --seed 42"
        ),
        (
            "python -m iad_sieve.cli run-iad-evidence-bootstrap "
            "--records outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_scored_relations.jsonl "
            "--output outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/roberta_pair_bootstrap_confidence.csv "
            "--system-name roberta_pair_open_v3_scholarly_balanced_gold "
            "--score-field roberta_pair_score --threshold 0.8 --iterations 1000 --confidence-level 0.95 --seed 42"
        ),
        (
            "python -m iad_sieve.cli run-iad-evidence-bootstrap "
            "--records outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_scored_relations.jsonl "
            "--output outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/ditto_style_em_source_heldout_bootstrap_confidence.csv "
            "--system-name ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout "
            "--score-field ditto_match_probability --threshold 0.8 --iterations 1000 --confidence-level 0.95 --seed 42"
        ),
        (
            "python -m iad_sieve.cli run-iad-evidence-bootstrap "
            "--records outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_scored_relations.jsonl "
            "--output outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/gpt_pair_judge_source_heldout_bootstrap_confidence.csv "
            "--system-name gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout "
            "--score-field gpt_same_work_probability --threshold 0.8 --iterations 1000 --confidence-level 0.95 --seed 42"
        ),
        (
            "python -m iad_sieve.cli build-advanced-model-evidence "
            "--baseline-metric-summaries "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_metric_summary.jsonl "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_metric_summary.jsonl "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/specter2_adapter_metric_summary.jsonl "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/deberta_pair_metric_summary.jsonl "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_metric_summary.jsonl "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_metric_summary.jsonl "
            "--execution-summaries "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_execution_summary.jsonl "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_execution_summary.jsonl "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/specter2_adapter_execution_summary.jsonl "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/deberta_pair_execution_summary.jsonl "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_execution_summary.jsonl "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_execution_summary.jsonl "
            "--transformer-summaries "
            "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout/iad_risk_transformer_summary.jsonl "
            "outputs/iad_risk_transformer_specter2_open_v3_scholarly_balanced_gold_source_heldout/iad_risk_transformer_summary.jsonl "
            "--bootstrap-summaries "
            "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/scincl_source_heldout_bootstrap_confidence.csv "
            "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/roberta_pair_source_heldout_bootstrap_confidence.csv "
            "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/iad_risk_transformer_scincl_source_heldout_bootstrap_confidence.csv "
            "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/ditto_style_em_source_heldout_bootstrap_confidence.csv "
            "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/gpt_pair_judge_source_heldout_bootstrap_confidence.csv "
            "--remote-output-summaries outputs/remote_output_validation_fixture/remote_output_validation_summary.jsonl "
            "--required-systems ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout "
            "gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout "
            "--output-dir outputs/advanced_model_evidence_fixture"
        ),
        (
            "python -m iad_sieve.cli build-model-innovation-blueprint "
            "--advanced-model-evidence outputs/advanced_model_evidence_fixture/advanced_model_evidence.jsonl "
            "--q2b-completion-audits outputs/q2b_completion_audit_fixture/q2b_completion_audit.jsonl "
            "--split-readiness-audits outputs/open_v3_split_readiness_balanced_gold/open_v3_split_readiness.jsonl "
            "outputs/open_v3_split_readiness_multitopic_silver_patch/open_v3_split_readiness.jsonl "
            "outputs/open_v3_split_readiness_scholarly_balanced_gold/open_v3_split_readiness.jsonl "
            "--output-dir outputs/model_innovation_blueprint_fixture"
        ),
        (
            "python -m iad_sieve.cli build-model-superiority-audit "
            "--advanced-model-evidence outputs/advanced_model_evidence_fixture/advanced_model_evidence.jsonl "
            "--model-innovation-blueprints outputs/model_innovation_blueprint_fixture/model_innovation_blueprint.jsonl "
            "--main-system iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold "
            "--output-dir outputs/model_superiority_audit_fixture"
        ),
        (
            "python -m iad_sieve.cli build-innovation-depth-stress-test "
            "--model-innovation-blueprints outputs/model_innovation_blueprint_fixture/model_innovation_blueprint.jsonl "
            "--model-superiority-audits outputs/model_superiority_audit_fixture/model_superiority_audit.jsonl "
            "--mechanism-evidence outputs/mechanism_error_evidence_fixture/scincl/mechanism_error_evidence.jsonl "
            "outputs/mechanism_error_evidence_fixture/roberta_pair/mechanism_error_evidence.jsonl "
            "--mechanism-sensitivity outputs/mechanism_error_evidence_fixture/scincl/mechanism_threshold_sensitivity.jsonl "
            "outputs/mechanism_error_evidence_fixture/roberta_pair/mechanism_threshold_sensitivity.jsonl "
            "--mechanism-triangulation-summaries outputs/mechanism_triangulation_audit_fixture/mechanism_triangulation_summary.jsonl "
            "--mechanism-triangulation-sensitivity-summaries outputs/mechanism_triangulation_sensitivity_fixture/mechanism_triangulation_sensitivity_summary.jsonl "
            "--split-readiness-audits outputs/open_v3_split_readiness_balanced_gold/open_v3_split_readiness.jsonl "
            "outputs/open_v3_split_readiness_multitopic_silver_patch/open_v3_split_readiness.jsonl "
            "outputs/open_v3_split_readiness_scholarly_balanced_gold/open_v3_split_readiness.jsonl "
            "--output-dir outputs/innovation_depth_stress_test_fixture"
        ),
        (
            "python -m iad_sieve.cli build-q2b-completion-audit "
            "--submission-summaries outputs/submission_gate_audit_fixture/submission_gate_audit_summary.jsonl "
            "--q2b-summaries outputs/q2b_action_board_fixture/q2b_action_board_summary.jsonl "
            "--reviewer-response-summaries outputs/reviewer_response_matrix_fixture/reviewer_response_summary.jsonl "
            "--remote-connection-summaries outputs/remote_connection_pack_fixture/remote_connection_pack_summary.jsonl "
            "--remote-result-acceptance-summaries outputs/remote_result_acceptance_fixture/remote_result_acceptance_summary.jsonl "
            "--innovation-depth-summaries outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test_summary.jsonl "
            "--advanced-model-summaries outputs/advanced_model_evidence_fixture/advanced_model_evidence_summary.jsonl "
            "--split-readiness-summaries outputs/open_v3_split_readiness_balanced_gold/open_v3_split_readiness_summary.jsonl "
            "outputs/open_v3_split_readiness_multitopic_silver_patch/open_v3_split_readiness_summary.jsonl "
            "outputs/open_v3_split_readiness_scholarly_balanced_gold/open_v3_split_readiness_summary.jsonl "
            "--split-readiness-audits outputs/open_v3_split_readiness_balanced_gold/open_v3_split_readiness.jsonl "
            "outputs/open_v3_split_readiness_multitopic_silver_patch/open_v3_split_readiness.jsonl "
            "outputs/open_v3_split_readiness_scholarly_balanced_gold/open_v3_split_readiness.jsonl "
            "--training-input-summaries outputs/iad_training_input_audit_open_v3_gold_silver/iad_training_input_audit_summary.jsonl "
            "--source-heldout-coverage-summaries outputs/iad_source_heldout_coverage_audit_open_v3_balanced_gold/iad_source_heldout_coverage_summary.jsonl "
            "outputs/iad_source_heldout_coverage_audit_open_v3_scholarly_balanced_gold/iad_source_heldout_coverage_summary.jsonl "
            "outputs/iad_source_heldout_coverage_audit_coci_source_patch/iad_source_heldout_coverage_summary.jsonl "
            "--split-evaluation-summaries outputs/iad_risk_split_evaluation_audit_open_v3_gold_silver/iad_risk_split_evaluation_audit_summary.jsonl "
            "outputs/iad_risk_split_evaluation_audit_source_heldout/iad_risk_split_evaluation_audit_summary.jsonl "
            "outputs/iad_risk_split_evaluation_audit_coci_source_patch_source_heldout/iad_risk_split_evaluation_audit_summary.jsonl "
            "--output-dir outputs/q2b_completion_audit_fixture"
        ),
        (
            "python -m iad_sieve.cli build-q2b-upgrade-roadmap "
            "--completion-audit outputs/q2b_completion_audit_fixture/q2b_completion_audit.jsonl "
            "--action-board outputs/q2b_action_board_fixture/q2b_action_board.jsonl "
            "--remote-acceptance outputs/remote_result_acceptance_fixture/remote_result_acceptance.jsonl "
            "--remote-output-summary outputs/remote_output_validation_fixture/remote_output_validation_summary.jsonl "
            "--model-superiority-audit outputs/model_superiority_audit_fixture/model_superiority_audit.jsonl "
            "--output-dir outputs/q2b_upgrade_roadmap_fixture"
        ),
        (
            "python -m iad_sieve.cli build-reviewer-iteration-audit "
            "--q2b-roadmap outputs/q2b_upgrade_roadmap_fixture/q2b_upgrade_roadmap.jsonl "
            "--q2b-completion-audit outputs/q2b_completion_audit_fixture/q2b_completion_audit.jsonl "
            "--model-superiority-audit outputs/model_superiority_audit_fixture/model_superiority_audit.jsonl "
            "--innovation-depth outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test.jsonl "
            "--public-data-validity outputs/public_data_validity_audit_fixture/public_data_validity_audit.jsonl "
            "--feature-guard outputs/iad_model_feature_guard_fixture/iad_model_feature_guard.jsonl "
            "--reviewer-response outputs/reviewer_response_matrix_fixture/reviewer_response_matrix.jsonl "
            "--output-dir outputs/reviewer_iteration_audit_fixture"
        ),
        (
            "python -m iad_sieve.cli build-no-annotation-protocol "
            "--public-data-validity outputs/public_data_validity_audit_open_v3_balanced_gold/public_data_validity_audit.jsonl "
            "--q2b-roadmap outputs/q2b_upgrade_roadmap_fixture/q2b_upgrade_roadmap.jsonl "
            "--reviewer-iteration outputs/reviewer_iteration_audit_fixture/reviewer_iteration_audit.jsonl "
            "--remote-input-request outputs/remote_input_request_fixture/remote_input_request.jsonl "
            "--output-dir outputs/no_annotation_protocol_fixture"
        ),
        (
            "python -m iad_sieve.cli build-novelty-falsification-matrix "
            "--model-innovation-blueprints outputs/model_innovation_blueprint_fixture/model_innovation_blueprint.jsonl "
            "--innovation-depth-audits outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test.jsonl "
            "--model-superiority-summary outputs/model_superiority_audit_fixture/model_superiority_audit_summary.jsonl "
            "--no-annotation-summary outputs/no_annotation_protocol_fixture/no_annotation_protocol_summary.jsonl "
            "--output-dir outputs/novelty_falsification_matrix_fixture"
        ),
        (
            "python -m iad_sieve.cli build-prior-art-novelty-audit "
            "--novelty-matrices outputs/novelty_falsification_matrix_fixture/novelty_falsification_matrix.jsonl "
            "--advanced-model-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_summary.jsonl "
            "--snapshot-date 2026-06-13 --output-dir outputs/prior_art_novelty_audit_fixture"
        ),
        (
            "python -m iad_sieve.cli build-q2b-acceptance-rubric "
            "--remote-output-summary outputs/remote_output_validation_fixture/remote_output_validation_summary.jsonl "
            "--remote-result-acceptance-summary outputs/remote_result_acceptance_fixture/remote_result_acceptance_summary.jsonl "
            "--advanced-model-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_summary.jsonl "
            "--model-superiority-summary outputs/model_superiority_audit_fixture/model_superiority_audit_summary.jsonl "
            "--innovation-depth-summary outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test_summary.jsonl "
            "--no-annotation-summary outputs/no_annotation_protocol_fixture/no_annotation_protocol_summary.jsonl "
            "--novelty-summary outputs/novelty_falsification_matrix_fixture/novelty_falsification_matrix_summary.jsonl "
            "--prior-art-summary outputs/prior_art_novelty_audit_fixture/prior_art_novelty_audit_summary.jsonl "
            "--q2b-completion-summary outputs/q2b_completion_audit_fixture/q2b_completion_audit_summary.jsonl "
            "--reviewer-iteration-summary outputs/reviewer_iteration_audit_fixture/reviewer_iteration_audit_summary.jsonl "
            "--output-dir outputs/q2b_acceptance_rubric_fixture"
        ),
        (
            "python -m iad_sieve.cli build-primary-track-claim-gate "
            "--primary-remote-handoff outputs/primary_remote_handoff_fixture/primary_remote_handoff.jsonl "
            "--advanced-track-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_track_summary.jsonl "
            "--model-superiority-summary outputs/model_superiority_audit_fixture/model_superiority_audit_summary.jsonl "
            "--innovation-depth-summary outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test_summary.jsonl "
            "--q2b-acceptance-summary outputs/q2b_acceptance_rubric_fixture/q2b_acceptance_rubric_summary.jsonl "
            "--output-dir outputs/primary_track_claim_gate_fixture"
        ),
        (
            "python -m iad_sieve.cli build-primary-track-superiority-protocol "
            "--primary-track-claim-gate outputs/primary_track_claim_gate_fixture/primary_track_claim_gate.jsonl "
            "--advanced-track-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_track_summary.jsonl "
            "--model-superiority-summary outputs/model_superiority_audit_fixture/model_superiority_audit_summary.jsonl "
            "--output-dir outputs/primary_track_superiority_protocol_fixture"
        ),
        (
            "python -m iad_sieve.cli build-primary-track-superiority-evaluator "
            "--primary-track-superiority-protocol outputs/primary_track_superiority_protocol_fixture/primary_track_superiority_protocol.jsonl "
            "--metric-summaries outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout/iad_risk_transformer_summary.jsonl "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_metric_summary.jsonl "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_metric_summary.jsonl "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_metric_summary.jsonl "
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_metric_summary.jsonl "
            "--bootstrap-summaries outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/iad_risk_transformer_scincl_source_heldout_bootstrap_confidence.csv "
            "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/scincl_source_heldout_bootstrap_confidence.csv "
            "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/roberta_pair_source_heldout_bootstrap_confidence.csv "
            "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/ditto_style_em_source_heldout_bootstrap_confidence.csv "
            "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/gpt_pair_judge_source_heldout_bootstrap_confidence.csv "
            "--output-dir outputs/primary_track_superiority_evaluator_fixture"
        ),
        (
            "python -m iad_sieve.cli build-q2b-experiment-optimizer "
            "--q2b-acceptance-rubric outputs/q2b_acceptance_rubric_fixture/q2b_acceptance_rubric.jsonl "
            "--reviewer-iteration outputs/reviewer_iteration_audit_fixture/reviewer_iteration_audit.jsonl "
            "--remote-input-request outputs/remote_input_request_fixture/remote_input_request.jsonl "
            "--remote-execution-slice outputs/remote_execution_slice_fixture/remote_execution_slice.jsonl "
            "--advanced-track-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_track_summary.jsonl "
            "--output-dir outputs/q2b_experiment_optimizer_fixture"
        ),
        (
            "python -m iad_sieve.cli build-reviewer-threat-model "
            "--q2b-acceptance-rubric outputs/q2b_acceptance_rubric_fixture/q2b_acceptance_rubric.jsonl "
            "--q2b-experiment-optimizer outputs/q2b_experiment_optimizer_fixture/q2b_experiment_optimizer.jsonl "
            "--model-innovation-blueprints outputs/model_innovation_blueprint_fixture/model_innovation_blueprint.jsonl "
            "--innovation-depth-audits outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test.jsonl "
            "--novelty-matrices outputs/novelty_falsification_matrix_fixture/novelty_falsification_matrix.jsonl "
            "--prior-art-audits outputs/prior_art_novelty_audit_fixture/prior_art_novelty_audit.jsonl "
            "--reviewer-iterations outputs/reviewer_iteration_audit_fixture/reviewer_iteration_audit.jsonl "
            "--output-dir outputs/reviewer_threat_model_fixture"
        ),
    ]


def _post_run_validation_command() -> str:
    """构造主轨道远程回传后的单行执行命令。

    参数:
        无。

    返回:
        使用 shell AND 串联的后处理命令。
    """
    return " && ".join(_post_run_validation_commands())


def _post_run_validation_script_text() -> str:
    """构造主轨道回传验收脚本文本。

    参数:
        无。

    返回:
        可直接写入 shell 脚本的文本。
    """
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
    ]
    for index, command in enumerate(_post_run_validation_commands(), start=1):
        lines.append(f'echo "[primary-post-run:{index:02d}] {command.split()[3]}"')
        lines.append(command)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_primary_remote_handoff_rows(primary_remote_readiness_rows: list[dict]) -> list[dict]:
    """构建主轨道远程执行交接记录。

    参数:
        primary_remote_readiness_rows: 主轨道远程就绪审计记录。

    返回:
        主轨道远程交接记录列表。
    """
    try:
        readiness_row = primary_remote_readiness_rows[0] if primary_remote_readiness_rows else {}
        connection_fields = _list_value(readiness_row.get("missing_connection_fields"))
        primary_tasks = _ordered_tasks(_list_value(readiness_row.get("source_task_ids")))
        script_path = _clean(readiness_row.get("primary_template_path"))
        row = {
            "handoff_id": "primary_track_remote_handoff",
            "handoff_status": _handoff_status(readiness_row),
            "primary_track": _clean(readiness_row.get("primary_track")),
            "primary_script_path": script_path,
            "connection_fields": connection_fields,
            "connection_field_count": len(connection_fields),
            "primary_required_secret_names": _list_value(readiness_row.get("primary_required_secret_names")),
            "missing_primary_secret_names": _list_value(readiness_row.get("missing_primary_secret_names")),
            "deferred_global_secret_names": _list_value(readiness_row.get("deferred_global_secret_names")),
            "unmapped_systems": _list_value(readiness_row.get("unmapped_systems")),
            "remote_task_order": primary_tasks,
            "expected_outputs": _list_value(readiness_row.get("missing_outputs")),
            "profile_command": _profile_command(connection_fields),
            "run_command": f"bash {script_path}" if script_path else "",
            "post_run_validation": _post_run_validation_command(),
            "post_run_validation_script": POST_RUN_VALIDATION_SCRIPT_NAME,
            "post_run_validation_step_count": len(_post_run_validation_commands()),
            "post_run_validation_expected_outputs": POST_RUN_VALIDATION_EXPECTED_OUTPUTS,
            "operator_note": _operator_note(readiness_row, primary_tasks),
            "paper_claim_boundary": _clean(readiness_row.get("paper_claim_boundary")),
        }
        LOGGER.info("主轨道远程交接包生成完成: primary_track=%s", row["primary_track"])
        return [row]
    except Exception:
        LOGGER.exception("构建主轨道远程交接包失败")
        raise


def build_primary_remote_handoff_rows_from_paths(primary_remote_readiness_path: str | Path) -> list[dict]:
    """从文件构建主轨道远程交接记录。

    参数:
        primary_remote_readiness_path: primary_remote_readiness JSONL 路径。

    返回:
        主轨道远程交接记录列表。
    """
    try:
        readiness_rows = read_records(primary_remote_readiness_path)
    except Exception:
        LOGGER.exception("读取主轨道远程就绪审计失败: %s", primary_remote_readiness_path)
        raise
    return build_primary_remote_handoff_rows(readiness_rows)


def _serialize_csv_value(value: object) -> object:
    """序列化 CSV 单元格。

    参数:
        value: 原始值。

    返回:
        CSV 可写值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 报告。

    参数:
        path: 输出路径。
        rows: 交接记录。

    返回:
        无。
    """
    fields = list(PREFERRED_FIELDS)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_csv_value(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出主轨道远程交接 CSV 失败: %s", path)
        raise


def _summary(rows: list[dict]) -> dict:
    """构建主轨道远程交接摘要。

    参数:
        rows: 交接记录。

    返回:
        摘要记录。
    """
    row = rows[0] if rows else {}
    return {
        "primary_track": row.get("primary_track", ""),
        "handoff_status": row.get("handoff_status", "missing"),
        "connection_field_count": len(_list_value(row.get("connection_fields"))),
        "primary_task_count": len(_list_value(row.get("remote_task_order"))),
        "missing_primary_secret_count": len(_list_value(row.get("missing_primary_secret_names"))),
        "deferred_global_secret_count": len(_list_value(row.get("deferred_global_secret_names"))),
        "unmapped_system_count": len(_list_value(row.get("unmapped_systems"))),
        "primary_script_path": row.get("primary_script_path", ""),
        "post_run_validation_script": _clean(row.get("post_run_validation_script")),
        "post_run_validation_script_path": _clean(row.get("post_run_validation_script_path")),
        "post_run_validation_step_count": _int_value(row.get("post_run_validation_step_count")),
        "post_run_validation_expected_output_count": len(_list_value(row.get("post_run_validation_expected_outputs"))),
    }


def _rows_with_post_run_script_path(rows: list[dict], directory: Path) -> list[dict]:
    """补充可从当前工作目录执行的回传验收脚本路径。

    参数:
        rows: 原始交接记录。
        directory: 交接包输出目录。

    返回:
        补充脚本路径后的交接记录副本。
    """
    script_path = str(directory / POST_RUN_VALIDATION_SCRIPT_NAME)
    return [dict(row, post_run_validation_script_path=script_path) for row in rows]


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 交接报告。

    参数:
        path: 输出路径。
        rows: 交接记录。
        summary: 摘要记录。

    返回:
        无。
    """
    row = rows[0] if rows else {}
    lines = [
        "# Primary Remote Handoff",
        "",
        "## 摘要",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## 需要提供的连接字段",
            "",
        ]
    )
    for field in _list_value(row.get("connection_fields")):
        lines.append(f"- {field}")
    lines.extend(
        [
            "",
            "## 主轨道任务顺序",
            "",
        ]
    )
    for index, task_id in enumerate(_list_value(row.get("remote_task_order")), start=1):
        lines.append(f"{index}. {task_id}")
    lines.extend(
        [
            "",
            "## 回传派生产物",
            "",
        ]
    )
    for output_path in _list_value(row.get("post_run_validation_expected_outputs")):
        lines.append(f"- {output_path}")
    lines.extend(
        [
            "",
            "## 执行命令",
            "",
            "```bash",
            _clean(row.get("profile_command")),
            _clean(row.get("run_command")),
            "```",
            "",
            "## 回传验收",
            "",
            "```bash",
            f"bash {_clean(row.get('post_run_validation_script_path')) or _clean(row.get('post_run_validation_script'))}",
            "```",
            "",
            "## 回传验收完整命令",
            "",
            "```bash",
            _clean(row.get("post_run_validation")),
            "```",
            "",
            "## 操作边界",
            "",
            _clean(row.get("operator_note")),
            "",
            "## 论文边界",
            "",
            _clean(row.get("paper_claim_boundary")),
        ]
    )
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出主轨道远程交接 Markdown 失败: %s", path)
        raise


def _write_post_run_validation_script(path: Path) -> None:
    """写出主轨道回传验收脚本。

    参数:
        path: 脚本输出路径。

    返回:
        无。
    """
    try:
        path.write_text(_post_run_validation_script_text(), encoding="utf-8")
        path.chmod(0o755)
    except OSError:
        LOGGER.exception("写出主轨道回传验收脚本失败: %s", path)
        raise


def write_primary_remote_handoff_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出主轨道远程交接包产物。

    参数:
        rows: 主轨道远程交接记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        enriched_rows = _rows_with_post_run_script_path(rows, directory)
        write_records(enriched_rows, directory / "primary_remote_handoff.jsonl")
        _write_csv(directory / "primary_remote_handoff.csv", enriched_rows)
        summary = _summary(enriched_rows)
        write_records([summary], directory / "primary_remote_handoff_summary.jsonl")
        _write_post_run_validation_script(directory / POST_RUN_VALIDATION_SCRIPT_NAME)
        _write_markdown(directory / "primary_remote_handoff.md", enriched_rows, summary)
    except Exception:
        LOGGER.exception("写出主轨道远程交接包失败: %s", output_dir)
        raise
