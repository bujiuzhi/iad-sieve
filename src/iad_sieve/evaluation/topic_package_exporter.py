"""最终课题包导出模块。"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, write_records


LOGGER = logging.getLogger(__name__)
CORE_DOCS = [
    ("README.md", "overview"),
    ("docs/README.md", "docs_index"),
    ("docs/project-structure.md", "project_structure"),
    ("docs/naming-convention.md", "naming_convention"),
    ("docs/GOAL.md", "research_goal"),
    ("docs/method-design.md", "method_design"),
    ("docs/experiment-plan.md", "experiment_plan"),
    ("docs/iad-bench-contract.md", "iad_bench_contract"),
    ("docs/data-processing-pipeline.md", "data_processing_pipeline"),
    ("docs/annotation-requirements.md", "annotation_requirements"),
    ("docs/paper-outline.md", "paper_outline"),
    ("docs/data-and-artifact-release.md", "data_artifact_release"),
    ("docs/public-release-checklist.md", "public_release_checklist"),
]
REPORT_FILE_NAMES = [
    "rq_summary.jsonl",
    "rq_summary.csv",
    "paper_report.md",
    "reviewer_audit.jsonl",
    "reviewer_audit.csv",
    "reviewer_audit.md",
    "journal_readiness.jsonl",
    "journal_readiness.csv",
    "journal_readiness.md",
    "experiment_queue.jsonl",
    "experiment_queue.csv",
    "experiment_queue.md",
    "experiment_preflight.jsonl",
    "experiment_preflight.csv",
    "experiment_preflight.md",
    "experiment_dependency.jsonl",
    "experiment_dependency.csv",
    "experiment_dependency.md",
    "experiment_execution_plan.jsonl",
    "experiment_execution_plan.csv",
    "experiment_execution_plan.md",
    "experiment_execution_scripts.jsonl",
    "remote_output_manifest.jsonl",
    "remote_handoff.md",
    "remote_output_validation.jsonl",
    "remote_output_validation.csv",
    "remote_output_validation.md",
    "remote_output_validation_summary.jsonl",
    "remote_result_acceptance.jsonl",
    "remote_result_acceptance.csv",
    "remote_result_acceptance.md",
    "remote_result_acceptance_summary.jsonl",
    "remote_environment_audit.jsonl",
    "remote_environment_audit.csv",
    "remote_environment_audit.md",
    "remote_environment_audit_summary.jsonl",
    "remote_execution_blueprint.jsonl",
    "remote_execution_blueprint.csv",
    "remote_execution_blueprint.md",
    "remote_execution_blueprint_summary.jsonl",
    "remote_connection_pack.jsonl",
    "remote_connection_pack.csv",
    "remote_connection_pack.md",
    "remote_connection_pack_summary.jsonl",
    "remote_connection.env.example",
    "remote_connection_profile.template.json",
    "remote_preflight.template.sh",
    "remote_sync_and_run.template.sh",
    "remote_pull_outputs.template.sh",
    "remote_execution_runbook.md",
    "remote_input_request.jsonl",
    "remote_input_request.csv",
    "remote_input_request.md",
    "remote_input_request_summary.jsonl",
    "remote_execution_slice.jsonl",
    "remote_execution_slice.csv",
    "remote_execution_slice.md",
    "remote_execution_slice_summary.jsonl",
    "remote_slice_run_pack.jsonl",
    "remote_slice_run_pack.csv",
    "remote_slice_run_pack.md",
    "remote_slice_run_pack_summary.jsonl",
    "remote_slice_run_scripts.jsonl",
    "primary_remote_readiness.jsonl",
    "primary_remote_readiness.csv",
    "primary_remote_readiness.md",
    "primary_remote_readiness_summary.jsonl",
    "primary_remote_handoff.jsonl",
    "primary_remote_handoff.csv",
    "primary_remote_handoff.md",
    "primary_remote_handoff_summary.jsonl",
    "run_primary_post_run_validation.sh",
    "primary_track_claim_gate.jsonl",
    "primary_track_claim_gate.csv",
    "primary_track_claim_gate.md",
    "primary_track_claim_gate_summary.jsonl",
    "primary_track_superiority_protocol.jsonl",
    "primary_track_superiority_protocol.csv",
    "primary_track_superiority_protocol.md",
    "primary_track_superiority_protocol_summary.jsonl",
    "primary_track_superiority_evaluator.jsonl",
    "primary_track_superiority_evaluator.csv",
    "primary_track_superiority_evaluator.md",
    "primary_track_superiority_evaluator_summary.jsonl",
    "no_annotation_protocol.jsonl",
    "no_annotation_protocol.csv",
    "no_annotation_protocol.md",
    "no_annotation_protocol_summary.jsonl",
    "paper_claim_audit.jsonl",
    "paper_claim_audit.csv",
    "paper_claim_audit.md",
    "research_depth_audit.jsonl",
    "research_depth_audit.csv",
    "research_depth_audit.md",
    "submission_gate_audit.jsonl",
    "submission_gate_audit.csv",
    "submission_gate_audit.md",
    "submission_gate_audit_summary.jsonl",
    "manuscript_evidence_matrix.jsonl",
    "manuscript_evidence_matrix.csv",
    "manuscript_evidence_matrix.md",
    "manuscript_evidence_summary.jsonl",
    "reviewer_response_matrix.jsonl",
    "reviewer_response_matrix.csv",
    "reviewer_response_matrix.md",
    "reviewer_response_summary.jsonl",
    "reviewer_iteration_audit.jsonl",
    "reviewer_iteration_audit.csv",
    "reviewer_iteration_audit.md",
    "reviewer_iteration_audit_summary.jsonl",
    "reviewer_threat_model.jsonl",
    "reviewer_threat_model.csv",
    "reviewer_threat_model.md",
    "reviewer_threat_model_summary.jsonl",
    "manuscript_draft_skeleton.jsonl",
    "manuscript_draft_skeleton.md",
    "manuscript_draft_skeleton_summary.jsonl",
    "journal_upgrade_plan.jsonl",
    "journal_upgrade_plan.csv",
    "journal_upgrade_plan.md",
    "journal_upgrade_plan_summary.jsonl",
    "advanced_model_evidence.jsonl",
    "advanced_model_evidence.csv",
    "advanced_model_evidence.md",
    "advanced_model_evidence_summary.jsonl",
    "advanced_model_evidence_track_summary.jsonl",
    "advanced_model_evidence_track_summary.csv",
    "model_innovation_blueprint.jsonl",
    "model_innovation_blueprint.csv",
    "model_innovation_blueprint.md",
    "model_innovation_blueprint_summary.jsonl",
    "model_superiority_audit.jsonl",
    "model_superiority_audit.csv",
    "model_superiority_audit.md",
    "model_superiority_audit_summary.jsonl",
    "innovation_depth_stress_test.jsonl",
    "innovation_depth_stress_test.csv",
    "innovation_depth_stress_test.md",
    "innovation_depth_stress_test_summary.jsonl",
    "novelty_falsification_matrix.jsonl",
    "novelty_falsification_matrix.csv",
    "novelty_falsification_matrix.md",
    "novelty_falsification_matrix_summary.jsonl",
    "prior_art_novelty_audit.jsonl",
    "prior_art_novelty_audit.csv",
    "prior_art_novelty_audit.md",
    "prior_art_novelty_audit_summary.jsonl",
    "q2b_action_board.jsonl",
    "q2b_action_board.csv",
    "q2b_action_board.md",
    "q2b_action_board_summary.jsonl",
    "q2b_completion_audit.jsonl",
    "q2b_completion_audit.csv",
    "q2b_completion_audit.md",
    "q2b_completion_audit_summary.jsonl",
    "q2b_external_blocker_audit.jsonl",
    "q2b_external_blocker_audit.csv",
    "q2b_external_blocker_audit.md",
    "q2b_external_blocker_audit_summary.jsonl",
    "q2b_acceptance_rubric.jsonl",
    "q2b_acceptance_rubric.csv",
    "q2b_acceptance_rubric.md",
    "q2b_acceptance_rubric_summary.jsonl",
    "q2b_experiment_optimizer.jsonl",
    "q2b_experiment_optimizer.csv",
    "q2b_experiment_optimizer.md",
    "q2b_experiment_optimizer_summary.jsonl",
    "q2b_upgrade_roadmap.jsonl",
    "q2b_upgrade_roadmap.csv",
    "q2b_upgrade_roadmap.md",
    "q2b_upgrade_roadmap_summary.jsonl",
    "public_data_validity_audit.jsonl",
    "public_data_validity_audit.csv",
    "public_data_validity_audit.md",
    "public_data_validity_audit_summary.jsonl",
    "iad_bench_stratification_audit.jsonl",
    "iad_bench_stratification_audit.csv",
    "iad_bench_stratification_audit.md",
    "iad_bench_stratification_audit_summary.jsonl",
    "iad_bench_strata_distribution.jsonl",
    "iad_bench_strata_distribution.csv",
    "iad_bench_source_bias_diagnostic.jsonl",
    "iad_bench_source_bias_diagnostic.csv",
    "iad_bench_source_bias_diagnostic.md",
    "iad_bench_source_bias_diagnostic_summary.jsonl",
    "iad_bench_source_bias_predictions.jsonl",
    "iad_bench_source_bias_predictions.csv",
    "iad_bench_provenance_balance_plan.jsonl",
    "iad_bench_provenance_balance_plan.csv",
    "iad_bench_provenance_balance_plan.md",
    "iad_bench_provenance_balance_plan_summary.jsonl",
    "iad_bench_source_candidate_registry.jsonl",
    "iad_bench_source_candidate_registry.csv",
    "iad_bench_source_candidate_registry.md",
    "iad_bench_source_candidate_registry_summary.jsonl",
    "iad_bench_source_acquisition_audit.jsonl",
    "iad_bench_source_acquisition_audit.csv",
    "iad_bench_source_acquisition_audit.md",
    "iad_bench_source_acquisition_audit_summary.jsonl",
    "iad_model_feature_guard.jsonl",
    "iad_model_feature_guard.csv",
    "iad_model_feature_guard.md",
    "iad_model_feature_guard_summary.jsonl",
    "iad_model_feature_guard_violations.jsonl",
    "iad_model_feature_guard_violations.csv",
    "open_v3_plan_audit.jsonl",
    "open_v3_plan_audit.csv",
    "open_v3_plan_audit.md",
    "open_v3_plan_audit_summary.jsonl",
    "open_v3_source_plan.jsonl",
    "open_v3_source_plan.csv",
    "open_v3_source_plan.md",
    "open_v3_source_plan_summary.jsonl",
    "open_v3_split_readiness.jsonl",
    "open_v3_split_readiness.csv",
    "open_v3_split_readiness.md",
    "open_v3_split_readiness_summary.jsonl",
    "open_v3_heldout_split_plan.jsonl",
    "open_v3_heldout_split_plan.csv",
    "open_v3_heldout_split_plan.md",
    "open_v3_heldout_split_plan_summary.jsonl",
    "open_v3_heldout_split_assignments.jsonl",
    "open_v3_heldout_split_assignments.csv",
    "heldout_assignment_summary.jsonl",
    "iad_ablation_summary.jsonl",
    "iad_ablation_summary.csv",
    "iad_ablation_report.md",
    "training_summary.jsonl",
    "iad_bench_summary.jsonl",
    "iad_bench_documents.jsonl",
    "iad_bench_pairs.jsonl",
    "iad_bench_splits.jsonl",
    "label_provenance_summary.csv",
    "dataset_card.md",
    "ingestion_summary.jsonl",
    "summary.jsonl",
    "dataset_summary.jsonl",
    "eval_documents.jsonl",
    "eval_pairs.jsonl",
    "scored_relations.jsonl",
    "baseline_scores.jsonl",
    "baseline_execution_summary.jsonl",
    "baseline_metric_summary.jsonl",
    "baseline_scored_relations.jsonl",
    "iad_risk_summary.jsonl",
    "iad_risk_predictions.jsonl",
    "iad_risk_model.json",
    "iad_risk_split_evaluation_audit.jsonl",
    "iad_risk_split_evaluation_audit.csv",
    "iad_risk_split_evaluation_audit.md",
    "iad_risk_split_evaluation_audit_summary.jsonl",
    "iad_source_heldout_coverage_audit.jsonl",
    "iad_source_heldout_coverage_audit.csv",
    "iad_source_heldout_coverage_audit.md",
    "iad_source_heldout_coverage_summary.jsonl",
    "iad_source_heldout_gap_plan.jsonl",
    "iad_source_heldout_gap_plan.csv",
    "iad_source_heldout_gap_plan.md",
    "iad_source_heldout_gap_plan_summary.jsonl",
    "iad_training_input_audit.jsonl",
    "iad_training_input_audit.csv",
    "iad_training_input_audit.md",
    "iad_training_input_audit_summary.jsonl",
    "iad_risk_transformer_summary.jsonl",
    "iad_risk_transformer_predictions.jsonl",
    "iad_risk_transformer_model.json",
    "baseline_error_summary.jsonl",
    "baseline_error_summary.csv",
    "baseline_error_cases.jsonl",
    "baseline_error_cases.csv",
    "baseline_error_report.md",
    "mechanism_error_evidence.jsonl",
    "mechanism_error_evidence.csv",
    "mechanism_error_evidence.md",
    "mechanism_error_cases.jsonl",
    "mechanism_error_cases.csv",
    "mechanism_error_strata.jsonl",
    "mechanism_error_strata.csv",
    "mechanism_threshold_sensitivity.jsonl",
    "mechanism_threshold_sensitivity.csv",
    "mechanism_error_evidence_summary.jsonl",
    "mechanism_case_pack.jsonl",
    "mechanism_case_pack.csv",
    "mechanism_case_pack.md",
    "mechanism_case_pack_summary.jsonl",
    "mechanism_triangulation_audit.jsonl",
    "mechanism_triangulation_audit.csv",
    "mechanism_triangulation_audit.md",
    "mechanism_triangulation_systems.jsonl",
    "mechanism_triangulation_systems.csv",
    "mechanism_triangulation_summary.jsonl",
    "mechanism_triangulation_sensitivity.jsonl",
    "mechanism_triangulation_sensitivity.csv",
    "mechanism_triangulation_sensitivity.md",
    "mechanism_triangulation_sensitivity_summary.jsonl",
    "single_space_union_summary.jsonl",
    "single_space_union_summary.csv",
    "single_space_union_predictions.jsonl",
    "single_space_union_report.md",
    "iad_bootstrap_confidence.csv",
]
REPORT_GLOB_PATTERNS = [
    "*_scores.jsonl",
    "*_execution_summary.jsonl",
    "*_metric_summary.jsonl",
    "*_scored_relations.jsonl",
    "*_bootstrap_confidence.csv",
    "run_stage_*.sh",
    "run_remote_slice_*.template.sh",
]


def _copy_text_file(source_path: Path, target_path: Path, artifact_group: str, artifact_name: str) -> dict:
    """复制文本文件并返回 manifest 行。

    参数:
        source_path: 源文件路径。
        target_path: 目标文件路径。
        artifact_group: 产物分组。
        artifact_name: 产物名称。

    返回:
        manifest 记录。
    """
    if not source_path.exists():
        LOGGER.warning("课题包源文件不存在: %s", source_path)
        return {
            "artifact_group": artifact_group,
            "artifact_name": artifact_name,
            "source_path": str(source_path),
            "package_path": str(target_path),
            "status": "missing",
            "size_bytes": 0,
        }
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    return {
        "artifact_group": artifact_group,
        "artifact_name": artifact_name,
        "source_path": str(source_path),
        "package_path": str(target_path),
        "status": "copied",
        "size_bytes": target_path.stat().st_size,
    }


def _copy_core_docs(workspace_dir: Path, output_dir: Path) -> list[dict]:
    """复制核心课题文档。

    参数:
        workspace_dir: 工作区目录。
        output_dir: 课题包输出目录。

    返回:
        manifest 记录列表。
    """
    rows: list[dict] = []
    for relative_path, artifact_name in CORE_DOCS:
        rows.append(
            _copy_text_file(
                workspace_dir / relative_path,
                output_dir / "docs" / Path(relative_path).name,
                "core_doc",
                artifact_name,
            )
        )
    return rows


def _reset_managed_package_paths(output_dir: Path) -> None:
    """清理课题包导出器管理的输出路径。

    参数:
        output_dir: 课题包输出目录。

    返回:
        无。
    """
    for name in ["docs", "reports", "models", "PACKAGE_README.md", "manifest.jsonl"]:
        target_path = output_dir / name
        try:
            if target_path.is_dir():
                shutil.rmtree(target_path)
            elif target_path.exists():
                target_path.unlink()
        except OSError:
            LOGGER.exception("清理课题包旧输出失败: %s", target_path)
            raise


def _copy_report_dir(report_dir: Path, output_dir: Path) -> list[dict]:
    """复制单个报告目录中的关键文件。

    参数:
        report_dir: 报告目录。
        output_dir: 课题包输出目录。

    返回:
        manifest 记录列表。
    """
    rows: list[dict] = []
    report_name = report_dir.name
    copied_names: set[str] = set()
    for file_name in REPORT_FILE_NAMES:
        source_path = report_dir / file_name
        if not source_path.exists():
            continue
        copied_names.add(file_name)
        rows.append(
            _copy_text_file(
                source_path,
                output_dir / "reports" / report_name / file_name,
                "report",
                f"{report_name}:{file_name}",
            )
        )
    for pattern in REPORT_GLOB_PATTERNS:
        for source_path in sorted(report_dir.glob(pattern)):
            if source_path.name in copied_names:
                continue
            copied_names.add(source_path.name)
            rows.append(
                _copy_text_file(
                    source_path,
                    output_dir / "reports" / report_name / source_path.name,
                    "report",
                    f"{report_name}:{source_path.name}",
                )
            )
    if not rows and not report_dir.exists():
        rows.append(
            {
                "artifact_group": "report",
                "artifact_name": report_name,
                "source_path": str(report_dir),
                "package_path": str(output_dir / "reports" / report_name),
                "status": "missing",
                "size_bytes": 0,
            }
        )
    elif not rows:
        LOGGER.debug("课题包报告目录无可复制文件，跳过: %s", report_dir)
    return rows


def _copy_model_dir(model_dir: Path | None, output_dir: Path) -> list[dict]:
    """复制模型目录中的 JSON/JSONL 文件。

    参数:
        model_dir: 模型目录。
        output_dir: 课题包输出目录。

    返回:
        manifest 记录列表。
    """
    if model_dir is None:
        return [
            {
                "artifact_group": "model",
                "artifact_name": "model_dir",
                "source_path": "",
                "package_path": str(output_dir / "models"),
                "status": "missing",
                "size_bytes": 0,
            }
        ]
    rows: list[dict] = []
    for source_path in sorted(model_dir.glob("*.json*")):
        rows.append(_copy_text_file(source_path, output_dir / "models" / source_path.name, "model", source_path.name))
    if not rows:
        rows.append(
            {
                "artifact_group": "model",
                "artifact_name": model_dir.name,
                "source_path": str(model_dir),
                "package_path": str(output_dir / "models"),
                "status": "missing",
                "size_bytes": 0,
            }
        )
    return rows


def _write_package_readme(output_dir: Path, manifest_rows: list[dict]) -> None:
    """写出课题包说明。

    参数:
        output_dir: 课题包输出目录。
        manifest_rows: manifest 记录。

    返回:
        无。
    """
    copied_count = sum(1 for row in manifest_rows if row["status"] == "copied")
    missing_count = sum(1 for row in manifest_rows if row["status"] == "missing")
    lines = [
        "# IAD-Risk Topic Package",
        "",
        "## 内容",
        "",
        "- `docs/`：课题目标、方法设计、实验计划、IAD-Bench 契约、标注规范、论文大纲、数据发布和公开发布边界。",
        "- `reports/`：RQ 汇总、readiness 门禁、投稿门禁审计、稿件证据矩阵、安全论文草稿骨架、期刊升级优化计划、高级模型证据矩阵、机制性错误证据、实验队列/preflight/依赖图/执行交接包、远程交接与输出验收清单、论文主张审计、研究深度审计、IAD-Bench provenance、强 baseline 执行摘要、IAD-Risk 模型证据、审稿回应矩阵、消融报告等实验写作材料。",
        "- `models/`：IAD 轻量分类器 JSON 模型和训练摘要。",
        "- `manifest.jsonl`：课题包文件索引。",
        "",
        "## 边界",
        "",
        "该目录是写作和评审材料包，不包含远程服务器凭据、密钥文件或未公开原始数据。",
        "",
        "## Manifest 摘要",
        "",
        f"- copied: {copied_count}",
        f"- missing: {missing_count}",
        "",
    ]
    output_dir.joinpath("PACKAGE_README.md").write_text("\n".join(lines), encoding="utf-8")


def export_topic_package(
    workspace_dir: str | Path,
    output_dir: str | Path,
    report_dirs: list[str | Path] | None = None,
    model_dir: str | Path | None = None,
) -> list[dict]:
    """导出最终课题包。

    参数:
        workspace_dir: 项目工作区目录。
        output_dir: 课题包输出目录。
        report_dirs: 可选报告目录列表。
        model_dir: 可选模型目录。

    返回:
        manifest 记录列表。
    """
    resolved_workspace_dir = Path(workspace_dir)
    resolved_output_dir = ensure_directory(output_dir)
    _reset_managed_package_paths(resolved_output_dir)
    manifest_rows: list[dict] = []
    manifest_rows.extend(_copy_core_docs(resolved_workspace_dir, resolved_output_dir))
    for report_dir in report_dirs or []:
        manifest_rows.extend(_copy_report_dir(Path(report_dir), resolved_output_dir))
    manifest_rows.extend(_copy_model_dir(Path(model_dir) if model_dir else None, resolved_output_dir))
    _write_package_readme(resolved_output_dir, manifest_rows)
    manifest_rows.append(
        {
            "artifact_group": "package",
            "artifact_name": "PACKAGE_README.md",
            "source_path": "",
            "package_path": str(resolved_output_dir / "PACKAGE_README.md"),
            "status": "copied",
            "size_bytes": (resolved_output_dir / "PACKAGE_README.md").stat().st_size,
        }
    )
    write_records(manifest_rows, resolved_output_dir / "manifest.jsonl")
    LOGGER.info("最终课题包导出完成: %s rows=%s", resolved_output_dir, len(manifest_rows))
    return manifest_rows
