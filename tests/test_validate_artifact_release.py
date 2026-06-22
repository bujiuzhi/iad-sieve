"""测试外部 artifact release 校验脚本。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "manuscript" / "scripts" / "validate_artifact_release.py"


def _load_artifact_release_validator_module():
    """加载 artifact release 校验脚本模块。

    参数:
        无。

    返回:
        module: 已加载的 Python 模块。
    """
    spec = importlib.util.spec_from_file_location("validate_artifact_release", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_file(path: Path, content: str) -> None:
    """写入测试文本文件。

    参数:
        path: 输出路径。
        content: 文件内容。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha256_file(path: Path) -> str:
    """计算测试文件的 SHA256。

    参数:
        path: 文件路径。

    返回:
        str: SHA256 十六进制摘要。
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl_row(row: dict) -> str:
    """序列化单行 JSONL 测试记录。

    参数:
        row: 测试记录。

    返回:
        str: 单行 JSONL 文本。
    """
    return json.dumps(row, sort_keys=True) + "\n"


def _required_artifact_content(artifact_id: str) -> str:
    """生成满足 release schema 的最小 artifact 内容。

    参数:
        artifact_id: Artifact ID。

    返回:
        str: 测试 artifact 文件内容。
    """
    if artifact_id == "open_v2_main_results":
        return (
            "\n".join(
                [
                    "system,scope_type,same_work_f1,fmr,hnfmr,same_work_f1_denominator,fmr_denominator,hnfmr_denominator,threshold_source,automatic_merge_count,block_count,defer_count,automatic_merge_coverage,defer_rate,capacity_normalized_review_load",
                    "IAD-Risk,Open-v2,0.61,0.08,0.12,100,200,50,threshold_selection_logs,64,120,16,0.32,0.08,0.24",
                ]
            )
            + "\n"
        )
    if artifact_id == "iad_risk_predictions":
        return _jsonl_row(
            {
                "system": "iad_risk_transformer",
                "pair_id": "p1",
                "source_document_id": "d1",
                "target_document_id": "d2",
                "expected_label": 0,
                "expected_agenda_label": 1,
                "label_strength": "silver",
                "hard_negative_level": "high",
                "split": "test",
                "p_same_work": 0.42,
                "p_same_agenda": 0.91,
                "p_agenda_non_identity": 0.88,
                "p_false_merge_risk": 0.88,
                "work_threshold": 0.5,
                "agenda_block_threshold": 0.5,
                "risk_threshold": 0.5,
                "threshold_source": "model_config",
                "merge_prediction": 0,
            }
        )
    if artifact_id == "representation_baseline_scores":
        return _jsonl_row(
            {
                "system": "scincl_cosine_open_v2",
                "pair_id": "p1",
                "source_document_id": "d1",
                "target_document_id": "d2",
                "expected_label": 0,
                "expected_agenda_label": 1,
                "label_strength": "silver",
                "hard_negative_level": "high",
                "split": "test",
                "score": 0.93,
                "score_field": "score",
                "threshold_value": 0.9,
                "threshold_source": "threshold_selection_logs",
                "merge_prediction": 1,
            }
        )
    if artifact_id == "supervised_baseline_predictions":
        return _jsonl_row(
            {
                "system": "roberta_pair_open_v2",
                "pair_id": "p1",
                "source_document_id": "d1",
                "target_document_id": "d2",
                "expected_label": 0,
                "expected_agenda_label": 1,
                "label_strength": "silver",
                "hard_negative_level": "high",
                "split": "test",
                "match_probability": 0.87,
                "threshold_value": 0.8,
                "threshold_source": "threshold_selection_logs",
                "merge_prediction": 1,
            }
        )
    if artifact_id == "threshold_selection_logs":
        return _jsonl_row(
            {
                "system": "scincl_cosine_open_v2",
                "threshold_name": "automatic_merge",
                "threshold_value": 0.9,
                "selection_split": "dev",
                "selection_metric": "f1_under_fmr_constraint",
                "selection_rule": "maximize_f1_subject_to_fmr",
                "applied_scope": "open_v2_test",
                "score_field": "score",
            }
        )
    if artifact_id == "source_input_manifest":
        return json.dumps(
            {
                "inputs": [
                    {
                        "source_name": "OpenAlex fixture",
                        "acquisition_date_or_version": "2026-06-19",
                        "original_provider": "OpenAlex",
                        "local_file_name": "works.jsonl",
                        "record_count": 2,
                        "license_boundary": "provider terms",
                        "sha256": "0" * 64,
                    }
                ]
            },
            sort_keys=True,
        ) + "\n"
    if artifact_id == "processing_run_log":
        return _jsonl_row(
            {
                "stage": "prepare-openalex-weak-labels",
                "command_line": "python -m iad_sieve.cli prepare-openalex-weak-labels",
                "code_commit": "0123456789abcdef0123456789abcdef01234567",
                "environment_summary": "python=3.11",
                "random_seed": 42,
                "started_at": "2026-06-19T00:00:00Z",
                "finished_at": "2026-06-19T00:01:00Z",
                "input_manifest_reference": "configs/source_input_manifest.json",
                "output_path": "reports/iad_bench_split_summary.jsonl",
                "exit_status": 0,
            }
        )
    return _jsonl_row({"artifact_id": artifact_id, "status": "present"})


def _complete_ablation_suite_csv() -> str:
    """生成满足消融协议 schema 的 CSV 内容。

    参数:
        无。

    返回:
        str: ablation_suite CSV 内容。
    """
    header = [
        "variant",
        "protocol_variant",
        "protocol_required",
        "accepted_for_component_causality",
        "metric_target",
        "threshold_source",
        "protocol_scope_rule",
        "requires_prediction_rows",
        "identity_threshold",
        "selected_identity_threshold",
        "weak_label_count",
        "precision",
        "recall",
        "f1",
        "false_merge_rate",
        "false_positive",
        "false_negative",
    ]
    rows = [
        ["without_false_merge_risk", "no-risk-gate", "true", "true", "same_work_false_merge", "predeclared_cli_argument"],
        ["without_agenda_non_identity", "no-ANI-head", "true", "true", "same_work_false_merge", "predeclared_cli_argument"],
        ["dense_single_space", "single-space", "true", "true", "same_work_false_merge", "predeclared_cli_argument"],
        ["without_cannot_link", "no-cannot-link", "true", "true", "same_work_false_merge", "predeclared_cli_argument"],
        ["post_hoc_threshold", "post-hoc-threshold", "true", "false", "same_work_false_merge", "post_hoc_labeled_sweep"],
    ]
    suffix = ["same_input_pair_scope_and_split_required", "true", "0.9", "0.9", "100", "0.9", "0.8", "0.85", "0.01", "1", "2"]
    lines = [",".join(header)]
    lines.extend(",".join(row + suffix) for row in rows)
    return "\n".join(lines) + "\n"


def _add_ablation_suite_artifact(artifact_dir: Path, csv_content: str | None = None, component_claimed: bool = True) -> None:
    """向测试 release 添加 ablation_suite artifact。

    参数:
        artifact_dir: Release 目录。
        csv_content: 可选 ablation_suite CSV 内容。
        component_claimed: 是否打开 component_causality_claimed。

    返回:
        无。
    """
    ablation_path = artifact_dir / "reports" / "iad_ablation_suite.csv"
    _write_file(ablation_path, csv_content or _complete_ablation_suite_csv())
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["claim_boundaries"]["component_causality_claimed"] = component_claimed
    manifest["required_artifacts"].append(
        {
            "artifact_id": "ablation_suite",
            "required": component_claimed,
            "expected_location": "reports/iad_ablation_suite.csv",
            "sha256": _sha256_file(ablation_path),
            "claim_support": "Component-causality artifact with protocol_variant coverage.",
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _refresh_checksums(artifact_dir)


def _complete_manual_validation_slice_csv(row_count: int = 500, omitted_strata: set[str] | None = None) -> str:
    """生成满足人工验证协议 schema 的 CSV 内容。

    参数:
        row_count: 人工验证样本行数。
        omitted_strata: 需要从测试样本中排除的 strata。

    返回:
        str: manual_validation_slice CSV 内容。
    """
    header = [
        "pair_id",
        "source_document_id",
        "target_document_id",
        "manual_validation_stratum",
        "reviewer_1_code",
        "reviewer_2_code",
        "reviewer_1_label",
        "reviewer_2_label",
        "adjudicated_label",
        "reviewer_blinding_confirmed",
        "model_score_hidden",
        "merge_decision_hidden",
        "adjudication_status",
        "adjudication_rationale",
        "pair_level_notes",
        "agreement_status",
    ]
    omitted_strata = omitted_strata or set()
    strata = [
        stratum
        for stratum in [
            "silver_hard_negative",
            "high_score_false_merge_candidate",
            "blocked_or_deferred",
            "model_disagreement",
            "version_boundary",
            "identifier_conflict",
            "sparse_metadata",
        ]
        if stratum not in omitted_strata
    ]
    label_cycle = ["same_work", "agenda_non_identity", "unrelated", "version_boundary", "uncertain"]
    lines = [",".join(header)]
    for index in range(row_count):
        stratum = strata[index % len(strata)]
        reviewer_1_label = label_cycle[index % len(label_cycle)]
        agreement_status = "disagreement" if index % 5 == 0 else "agreement"
        reviewer_2_label = reviewer_1_label if agreement_status == "agreement" else label_cycle[(index + 1) % len(label_cycle)]
        adjudication_status = "adjudicated" if agreement_status == "disagreement" else "agreement_confirmed"
        row = [
            f"pair-{index:04d}",
            f"source-{index:04d}",
            f"target-{index:04d}",
            stratum,
            "reviewer_a",
            "reviewer_b",
            reviewer_1_label,
            reviewer_2_label,
            reviewer_1_label,
            "true",
            "true",
            "true",
            adjudication_status,
            f"rationale-{index:04d}",
            f"pair-note-{index:04d}",
            agreement_status,
        ]
        lines.append(",".join(row))
    return "\n".join(lines) + "\n"


def _add_manual_validation_slice_artifact(
    artifact_dir: Path,
    csv_content: str | None = None,
    human_claimed: bool = True,
) -> None:
    """向测试 release 添加 manual_validation_slice artifact。

    参数:
        artifact_dir: Release 目录。
        csv_content: 可选 manual_validation_slice CSV 内容。
        human_claimed: 是否打开 human_validation_claimed。

    返回:
        无。
    """
    manual_validation_path = artifact_dir / "reports" / "manual_validation_slice.csv"
    _write_file(manual_validation_path, csv_content or _complete_manual_validation_slice_csv())
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["claim_boundaries"]["human_validation_claimed"] = human_claimed
    manifest["required_artifacts"].append(
        {
            "artifact_id": "manual_validation_slice",
            "required": human_claimed,
            "expected_location": "reports/manual_validation_slice.csv",
            "sha256": _sha256_file(manual_validation_path),
            "claim_support": "Manual validation artifact with 500-1000 blinded adjudicated rows.",
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _refresh_checksums(artifact_dir)


def _complete_threshold_sensitivity_grid_csv(
    row_count: int = 3,
    same_split: bool = False,
    mixed_prediction_checksums: bool = False,
) -> str:
    """生成满足阈值敏感性协议 schema 的 CSV 内容。

    参数:
        row_count: 阈值网格行数。
        same_split: 是否故意让 selection_split 与 evaluation_split 相同。
        mixed_prediction_checksums: 是否故意混用不同预测文件校验和。

    返回:
        str: threshold_sensitivity_grid CSV 内容。
    """
    header = [
        "system",
        "threshold_grid_id",
        "prediction_artifact_id",
        "prediction_file_sha256",
        "threshold_range_source",
        "threshold_source",
        "selection_split",
        "evaluation_split",
        "work_threshold",
        "agenda_block_threshold",
        "risk_threshold",
        "selected_operating_point",
        "same_work_f1",
        "fmr",
        "hnfmr",
        "same_work_f1_denominator",
        "fmr_denominator",
        "hnfmr_denominator",
        "automatic_merge_count",
        "block_count",
        "defer_count",
        "random_seed",
        "command_line",
    ]
    lines = [",".join(header)]
    for index in range(row_count):
        threshold_value = 0.35 + index * 0.1
        prediction_checksum = "1" * 64
        if mixed_prediction_checksums and index == row_count - 1:
            prediction_checksum = "2" * 64
        row = [
            "iad_risk_transformer",
            "open_v2_iad_risk_grid",
            "iad_risk_predictions",
            prediction_checksum,
            "predefined_grid",
            "threshold_selection_logs",
            "dev",
            "dev" if same_split else "test",
            f"{threshold_value:.2f}",
            "0.50",
            f"{threshold_value:.2f}",
            "true" if index == 1 else "false",
            f"{0.70 + index * 0.01:.2f}",
            f"{0.05 + index * 0.01:.2f}",
            f"{0.10 + index * 0.01:.2f}",
            "100",
            "200",
            "50",
            str(60 + index),
            str(20 + index),
            str(10 + index),
            "42",
            "python -m iad_sieve.cli run-threshold-sensitivity",
        ]
        lines.append(",".join(row))
    return "\n".join(lines) + "\n"


def _add_threshold_sensitivity_grid_artifact(
    artifact_dir: Path,
    csv_content: str | None = None,
    threshold_stability_claimed: bool = True,
) -> None:
    """向测试 release 添加 threshold_sensitivity_grid artifact。

    参数:
        artifact_dir: Release 目录。
        csv_content: 可选 threshold_sensitivity_grid CSV 内容。
        threshold_stability_claimed: 是否打开 threshold_stability_claimed。

    返回:
        无。
    """
    threshold_grid_path = artifact_dir / "reports" / "threshold_sensitivity_grid.csv"
    _write_file(threshold_grid_path, csv_content or _complete_threshold_sensitivity_grid_csv())
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["claim_boundaries"]["threshold_stability_claimed"] = threshold_stability_claimed
    manifest["required_artifacts"].append(
        {
            "artifact_id": "threshold_sensitivity_grid",
            "required": threshold_stability_claimed,
            "expected_location": "reports/threshold_sensitivity_grid.csv",
            "sha256": _sha256_file(threshold_grid_path),
            "claim_support": "Threshold-stability artifact with predefined grid and prediction checksum binding.",
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _refresh_checksums(artifact_dir)


def _complete_bootstrap_intervals_csv(
    missing_metric: str | None = None,
    invalid_interval: bool = False,
    low_resample_count: bool = False,
) -> str:
    """生成满足 bootstrap_intervals schema 的 CSV 内容。

    参数:
        missing_metric: 需要从测试样本中排除的指标名。
        invalid_interval: 是否故意写入不包含 point_estimate 的区间。
        low_resample_count: 是否故意写入过低 resample_count。

    返回:
        str: bootstrap_intervals CSV 内容。
    """
    header = [
        "system",
        "metric_name",
        "scope_type",
        "prediction_artifact_id",
        "prediction_file_sha256",
        "bootstrap_method",
        "resample_unit",
        "resample_count",
        "confidence_level",
        "alpha",
        "random_seed",
        "point_estimate",
        "interval_lower",
        "interval_upper",
        "metric_denominator",
        "threshold_source",
        "command_line",
    ]
    metric_rows = {
        "same_work_f1": ("0.80", "0.75", "0.85", "100"),
        "fmr": ("0.05", "0.02", "0.08", "200"),
        "hnfmr": ("0.10", "0.04", "0.16", "50"),
    }
    lines = [",".join(header)]
    for metric_name, (point_estimate, interval_lower, interval_upper, denominator) in metric_rows.items():
        if metric_name == missing_metric:
            continue
        if invalid_interval and metric_name == "fmr":
            interval_lower, interval_upper = "0.06", "0.08"
        row = [
            "iad_risk_transformer",
            metric_name,
            "open_v2_test",
            "iad_risk_predictions",
            "5" * 64,
            "stratified_pair_bootstrap",
            "pair_id",
            "50" if low_resample_count and metric_name == "hnfmr" else "1000",
            "0.95",
            "0.05",
            "42",
            point_estimate,
            interval_lower,
            interval_upper,
            denominator,
            "threshold_selection_logs",
            "python -m iad_sieve.cli run-iad-evidence-bootstrap",
        ]
        lines.append(",".join(row))
    return "\n".join(lines) + "\n"


def _add_bootstrap_intervals_artifact(
    artifact_dir: Path,
    csv_content: str | None = None,
    confidence_claimed: bool = True,
) -> None:
    """向测试 release 添加 bootstrap_intervals artifact。

    参数:
        artifact_dir: Release 目录。
        csv_content: 可选 bootstrap_intervals CSV 内容。
        confidence_claimed: 是否打开 confidence_intervals_claimed。

    返回:
        无。
    """
    bootstrap_path = artifact_dir / "reports" / "bootstrap_intervals.csv"
    _write_file(bootstrap_path, csv_content or _complete_bootstrap_intervals_csv())
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["claim_boundaries"]["confidence_intervals_claimed"] = confidence_claimed
    manifest["required_artifacts"].append(
        {
            "artifact_id": "bootstrap_intervals",
            "required": confidence_claimed,
            "expected_location": "reports/bootstrap_intervals.csv",
            "sha256": _sha256_file(bootstrap_path),
            "claim_support": "Bootstrap interval artifact with prediction checksum and resampling provenance.",
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _refresh_checksums(artifact_dir)


def _complete_cluster_metric_summary_csv(mixed_cluster_run: bool = False, invalid_ratio: bool = False) -> str:
    """生成满足 cluster_metric_summary schema 的 CSV 内容。

    参数:
        mixed_cluster_run: 是否故意混用 cluster_run_id。
        invalid_ratio: 是否故意写入非法比例值。

    返回:
        str: cluster_metric_summary CSV 内容。
    """
    header = [
        "system",
        "cluster_run_id",
        "merge_policy_id",
        "prediction_artifact_id",
        "prediction_file_sha256",
        "threshold_source",
        "work_threshold",
        "agenda_block_threshold",
        "risk_threshold",
        "cluster_assignment_file",
        "pair_to_cluster_trace_file",
        "cluster_id",
        "cluster_size",
        "accepted_link_count",
        "cannot_link_conflict_count",
        "unresolved_conflict_count",
        "cluster_contamination_rate",
        "singleton_rate",
        "merge_coverage",
        "random_seed",
        "command_line",
    ]
    rows = []
    for index in range(2):
        rows.append(
            [
                "iad_risk_transformer",
                "cluster-run-b" if mixed_cluster_run and index == 1 else "cluster-run-a",
                "fixed-risk-gate",
                "iad_risk_predictions",
                "3" * 64,
                "threshold_selection_logs",
                "0.50",
                "0.50",
                "0.45",
                "reports/cluster_assignments.csv",
                "reports/pair_to_cluster_trace.csv",
                f"cluster-{index}",
                str(index + 1),
                str(index),
                str(index),
                "0",
                "1.2" if invalid_ratio and index == 0 else "0.00",
                "0.50",
                "0.40",
                "42",
                "python -m iad_sieve.cli build-cluster-audit",
            ]
        )
    return "\n".join([",".join(header), *[",".join(row) for row in rows]]) + "\n"


def _complete_cannot_link_audit_csv(mixed_prediction_checksums: bool = False, invalid_boolean: bool = False) -> str:
    """生成满足 cannot_link_audit schema 的 CSV 内容。

    参数:
        mixed_prediction_checksums: 是否故意混用预测文件校验和。
        invalid_boolean: 是否故意写入非法布尔值。

    返回:
        str: cannot_link_audit CSV 内容。
    """
    header = [
        "system",
        "cluster_run_id",
        "merge_policy_id",
        "prediction_artifact_id",
        "prediction_file_sha256",
        "threshold_source",
        "work_threshold",
        "agenda_block_threshold",
        "risk_threshold",
        "cannot_link_rule_id",
        "conflict_type",
        "source_document_id",
        "target_document_id",
        "cannot_link_flag",
        "accepted_merge_blocked",
        "violation_detected",
        "unresolved_conflict",
        "cannot_link_coverage_rate",
        "identifier_conflict_rule",
        "pair_to_cluster_trace_file",
        "random_seed",
        "command_line",
    ]
    rows = []
    for index, conflict_type in enumerate(["doi_conflict", "version_boundary"]):
        rows.append(
            [
                "iad_risk_transformer",
                "cluster-run-a",
                "fixed-risk-gate",
                "iad_risk_predictions",
                "4" * 64 if mixed_prediction_checksums and index == 1 else "3" * 64,
                "threshold_selection_logs",
                "0.50",
                "0.50",
                "0.45",
                f"cannot-link-{index}",
                conflict_type,
                f"source-{index}",
                f"target-{index}",
                "maybe" if invalid_boolean and index == 0 else "true",
                "true",
                "false",
                "false",
                "0.95",
                "documented_identifier_conflict_blocks_merge",
                "reports/pair_to_cluster_trace.csv",
                "42",
                "python -m iad_sieve.cli build-cluster-audit",
            ]
        )
    return "\n".join([",".join(header), *[",".join(row) for row in rows]]) + "\n"


def _add_cluster_quality_artifacts(
    artifact_dir: Path,
    cluster_csv_content: str | None = None,
    cannot_link_csv_content: str | None = None,
    cluster_claimed: bool = True,
) -> None:
    """向测试 release 添加 cluster-level quality artifacts。

    参数:
        artifact_dir: Release 目录。
        cluster_csv_content: 可选 cluster_metric_summary CSV 内容。
        cannot_link_csv_content: 可选 cannot_link_audit CSV 内容。
        cluster_claimed: 是否打开 cluster_level_quality_claimed。

    返回:
        无。
    """
    cluster_path = artifact_dir / "reports" / "cluster_metric_summary.csv"
    cannot_link_path = artifact_dir / "reports" / "cannot_link_audit.csv"
    _write_file(cluster_path, cluster_csv_content or _complete_cluster_metric_summary_csv())
    _write_file(cannot_link_path, cannot_link_csv_content or _complete_cannot_link_audit_csv())
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["claim_boundaries"]["cluster_level_quality_claimed"] = cluster_claimed
    manifest["required_artifacts"].extend(
        [
            {
                "artifact_id": "cluster_metric_summary",
                "required": cluster_claimed,
                "expected_location": "reports/cluster_metric_summary.csv",
                "sha256": _sha256_file(cluster_path),
                "claim_support": "Cluster metric artifact with assignment and trace file bindings.",
            },
            {
                "artifact_id": "cannot_link_audit",
                "required": cluster_claimed,
                "expected_location": "reports/cannot_link_audit.csv",
                "sha256": _sha256_file(cannot_link_path),
                "claim_support": "Cannot-link audit artifact with coverage, violation, and conflict-rule fields.",
            },
        ]
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _refresh_checksums(artifact_dir)


def _complete_readme_text() -> str:
    """生成包含必需复现说明的测试 README。

    参数:
        无。

    返回:
        str: README.md 测试内容。
    """
    return "\n".join(
        [
            "# IAD-Risk Artifact Release",
            "",
            "Do not include raw third-party data.",
            "Required files include README.md, manifest.json, and checksums.sha256.",
            "Run sha256sum -c checksums.sha256 before manuscript validation.",
            "Run python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release.",
            "Run python -m pip install -e . before CLI discovery.",
            "Run python -m iad_sieve.cli --help to verify installable CLI discovery.",
            "Repository commit: 0123456789abcdef0123456789abcdef01234567.",
            "## Claim Boundaries",
            "Full numerical audit requires external artifacts.",
            "source_input_manifest records the public input boundary.",
            "processing_run_log records the processing command boundary.",
            "## Reproduction Levels",
            "L3 result audit checks released tables, predictions, logs, manifests, checksums, and commit identifiers.",
            "",
        ]
    )


def _write_complete_release(artifact_dir: Path, release_status: str = "release_candidate") -> None:
    """写入完整的测试 artifact release 目录。

    参数:
        artifact_dir: Release 目录。
        release_status: manifest.json 中的发布状态。

    返回:
        无。
    """
    artifact_locations = {
        "open_v2_main_results": "tables/open_v2_main_results.csv",
        "iad_risk_predictions": "predictions/iad_risk_transformer_predictions.jsonl",
        "representation_baseline_scores": "predictions/representation_baseline_scores.jsonl",
        "supervised_baseline_predictions": "predictions/roberta_pair_classifier_predictions.jsonl",
        "threshold_selection_logs": "logs/threshold_selection_logs.jsonl",
        "iad_bench_split_summary": "reports/iad_bench_split_summary.jsonl",
        "source_input_manifest": "configs/source_input_manifest.json",
        "processing_run_log": "logs/processing_run_log.jsonl",
    }
    _write_file(artifact_dir / "README.md", _complete_readme_text())
    _write_file(artifact_dir / "configs" / "model_config.json", '{"seed": 7}\n')
    for artifact_id, relative_path in artifact_locations.items():
        _write_file(artifact_dir / relative_path, _required_artifact_content(artifact_id))

    required_artifacts = [
        {
            "artifact_id": artifact_id,
            "required": True,
            "expected_location": relative_path,
            "sha256": _sha256_file(artifact_dir / relative_path),
            "claim_support": f"{artifact_id} claim support.",
        }
        for artifact_id, relative_path in artifact_locations.items()
    ]
    manifest = {
        "package_name": "iad-risk-paper-artifacts",
        "package_type": "result_artifact_release",
        "release_status": release_status,
        "manuscript_title": "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement",
        "repository": {
            "url": "https://github.com/bujiuzhi/iad-sieve",
            "commit": "0123456789abcdef0123456789abcdef01234567",
            "branch": "main",
            "source_tree_clean": True,
        },
        "data_policy": {
            "raw_third_party_data_included": False,
            "model_checkpoints_included": False,
            "personal_or_secret_material_included": False,
            "derived_evaluation_artifacts_included": True,
            "source_licenses_respected": True,
        },
        "required_top_level_files": ["README.md", "manifest.json", "checksums.sha256"],
        "required_directories": ["configs", "tables", "predictions", "reports", "logs"],
        "required_artifacts": required_artifacts,
        "minimum_validation_commands": [
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release",
            "sha256sum -c checksums.sha256",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
            "python -m pip install -e .",
            "python -m iad_sieve.cli --help",
            "python manuscript/scripts/validate_manuscript.py --strict-latex",
            "python manuscript/scripts/verify_fixture_rebuild.py",
            "python scripts/check_public_release.py",
        ],
        "claim_boundaries": {
            "silver_labels_are_not_human_gold": True,
            "manual_validation_required_for_human_gold_claims": True,
            "same_scope_prediction_files_required_for_broad_ranking": True,
            "threshold_grid_required_for_threshold_stability_claims": True,
            "cluster_artifacts_required_for_cluster_level_quality_claims": True,
            "confidence_intervals_claimed": False,
            "component_causality_claimed": False,
            "human_validation_claimed": False,
            "threshold_stability_claimed": False,
            "broad_method_ranking_claimed": False,
            "cluster_level_quality_claimed": False,
        },
    }
    _write_file(artifact_dir / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    checksum_lines = []
    for path in sorted(artifact_dir.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            relative_path = path.relative_to(artifact_dir).as_posix()
            checksum_lines.append(f"{_sha256_file(path)}  {relative_path}")
    _write_file(artifact_dir / "checksums.sha256", "\n".join(checksum_lines) + "\n")


def _refresh_checksums(artifact_dir: Path) -> None:
    """重新写入测试 release 的 checksums.sha256。

    参数:
        artifact_dir: Release 目录。

    返回:
        无。
    """
    checksum_lines = []
    for path in sorted(artifact_dir.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            relative_path = path.relative_to(artifact_dir).as_posix()
            checksum_lines.append(f"{_sha256_file(path)}  {relative_path}")
    (artifact_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")


def _refresh_manifest_artifact_checksums(artifact_dir: Path) -> None:
    """重新写入 manifest.json 中 artifact 文件的 SHA256。

    参数:
        artifact_dir: Release 目录。

    返回:
        无。
    """
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in manifest["required_artifacts"]:
        location = row.get("expected_location")
        if location:
            row["sha256"] = _sha256_file(artifact_dir / location)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def test_validate_artifact_release_accepts_complete_release(tmp_path) -> None:
    """验证完整 artifact release 目录可通过校验。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert errors == []


def test_validate_artifact_release_rejects_manifest_without_cli_discovery_command(tmp_path) -> None:
    """验证 release manifest 必须记录 CLI discovery 命令。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["minimum_validation_commands"] = [
        command
        for command in manifest["minimum_validation_commands"]
        if command != "python -m iad_sieve.cli --help"
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _refresh_checksums(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("python -m iad_sieve.cli --help" in error for error in errors)


def test_validate_artifact_release_rejects_manifest_without_editable_install_command(tmp_path) -> None:
    """验证 release manifest 必须记录 editable install 命令。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["minimum_validation_commands"] = [
        command
        for command in manifest["minimum_validation_commands"]
        if command != "python -m pip install -e ."
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _refresh_checksums(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("python -m pip install -e ." in error for error in errors)


def test_validate_artifact_release_rejects_readme_without_reproducibility_markers(tmp_path) -> None:
    """验证 release README 缺少复现说明时会被拒绝。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _write_file(artifact_dir / "README.md", "# IAD-Risk Artifact Release\n")
    _refresh_checksums(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("README.md missing required release instruction" in error for error in errors)
    assert any("manifest.json" in error for error in errors)
    assert any("validate_artifact_release.py" in error for error in errors)
    assert any("python -m pip install -e ." in error for error in errors)
    assert any("python -m iad_sieve.cli --help" in error for error in errors)
    assert any("Repository commit" in error for error in errors)


def test_validate_artifact_release_rejects_open_v2_results_without_row_audit_columns(tmp_path) -> None:
    """验证 Open-v2 主结果表缺少行级审计列时会被拒绝。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _write_file(artifact_dir / "tables" / "open_v2_main_results.csv", "system,same_work_f1,fmr,hnfmr\nIAD-Risk,0.1,0.2,0.3\n")
    _refresh_manifest_artifact_checksums(artifact_dir)
    _refresh_checksums(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("scope_type" in error for error in errors)
    assert any("same_work_f1_denominator" in error for error in errors)
    assert any("threshold_source" in error for error in errors)
    assert any("automatic_merge_coverage" in error for error in errors)
    assert any("defer_rate" in error for error in errors)
    assert any("capacity_normalized_review_load" in error for error in errors)


def test_validate_artifact_release_rejects_prediction_jsonl_without_row_audit_fields(tmp_path) -> None:
    """验证 prediction JSONL 缺少行级审计字段时会被拒绝。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _write_file(artifact_dir / "predictions" / "iad_risk_transformer_predictions.jsonl", _jsonl_row({"pair_id": "p1"}))
    _refresh_manifest_artifact_checksums(artifact_dir)
    _refresh_checksums(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("iad_risk_predictions JSONL line 1" in error for error in errors)
    assert any("p_same_work" in error for error in errors)
    assert any("merge_prediction" in error for error in errors)
    assert any("threshold_source" in error for error in errors)


def test_validate_artifact_release_rejects_source_input_manifest_without_chain_of_custody_fields(tmp_path) -> None:
    """验证 source_input_manifest 必须记录公开输入链路字段。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _write_file(
        artifact_dir / "configs" / "source_input_manifest.json",
        json.dumps(
            {
                "inputs": [
                    {
                        "source_name": "",
                        "local_file_name": "/tmp/private/raw.jsonl",
                        "record_count": "many",
                        "sha256": "not-a-sha",
                    }
                ]
            },
            sort_keys=True,
        )
        + "\n",
    )
    _refresh_manifest_artifact_checksums(artifact_dir)
    _refresh_checksums(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("source_input_manifest inputs[1]" in error for error in errors)
    assert any("source_name" in error for error in errors)
    assert any("acquisition_date_or_version" in error for error in errors)
    assert any("original_provider" in error for error in errors)
    assert any("license_boundary" in error for error in errors)
    assert any("local_file_name must be a safe relative path" in error for error in errors)
    assert any("sha256 must be a valid SHA256 digest" in error for error in errors)
    assert any("record_count must be a non-negative integer" in error for error in errors)


def test_validate_artifact_release_rejects_processing_run_log_without_rebuild_audit_fields(tmp_path) -> None:
    """验证 processing_run_log 必须记录每个处理阶段的复现审计字段。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _write_file(artifact_dir / "logs" / "processing_run_log.jsonl", _jsonl_row({"stage": "prepare-openalex-weak-labels"}))
    _refresh_manifest_artifact_checksums(artifact_dir)
    _refresh_checksums(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("processing_run_log JSONL line 1" in error for error in errors)
    assert any("command_line" in error for error in errors)
    assert any("code_commit" in error for error in errors)
    assert any("environment_summary" in error for error in errors)
    assert any("input_manifest_reference" in error for error in errors)
    assert any("output_path" in error for error in errors)
    assert any("exit_status" in error for error in errors)


def test_validate_artifact_release_rejects_processing_run_log_unbound_failed_stage(tmp_path) -> None:
    """验证 processing_run_log 必须绑定提交号、输入 manifest、输出 checksum 和成功状态。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _write_file(
        artifact_dir / "logs" / "processing_run_log.jsonl",
        _jsonl_row(
            {
                "stage": "prepare-openalex-weak-labels",
                "command_line": "python -m iad_sieve.cli prepare-openalex-weak-labels",
                "code_commit": "abcdef1234567890abcdef1234567890abcdef12",
                "environment_summary": "python=3.11",
                "random_seed": "not-a-seed",
                "started_at": "2026-06-19T00:02:00Z",
                "finished_at": "2026-06-19T00:01:00Z",
                "input_manifest_reference": "configs/other_source_manifest.json",
                "output_path": "reports/not_listed_in_release.jsonl",
                "exit_status": 1,
            }
        ),
    )
    _refresh_manifest_artifact_checksums(artifact_dir)
    _refresh_checksums(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("code_commit must match manifest.json repository.commit" in error for error in errors)
    assert any("input_manifest_reference must be configs/source_input_manifest.json" in error for error in errors)
    assert any("input_manifest_reference must be listed in checksums.sha256" in error for error in errors)
    assert any("output_path must be listed in checksums.sha256" in error for error in errors)
    assert any("exit_status must be 0" in error for error in errors)
    assert any("random_seed must be an integer or not_applicable" in error for error in errors)
    assert any("finished_at must not be earlier than started_at" in error for error in errors)


def test_validate_artifact_release_rejects_missing_checksum_entry(tmp_path) -> None:
    """验证缺少 checksum 条目的 release 会被拒绝。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    checksum_path = artifact_dir / "checksums.sha256"
    checksum_lines = [
        line for line in checksum_path.read_text(encoding="utf-8").splitlines() if "open_v2_main_results.csv" not in line
    ]
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("checksums.sha256 missing entries" in error for error in errors)
    assert any("open_v2_main_results.csv" in error for error in errors)


def test_validate_artifact_release_rejects_raw_data_directory(tmp_path) -> None:
    """验证 release 目录不得包含原始数据目录。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _write_file(artifact_dir / "data" / "raw.csv", "raw third-party data\n")

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("forbidden path part" in error for error in errors)
    assert any("data/raw.csv" in error for error in errors)


def test_validate_artifact_release_rejects_template_status_and_placeholder_commit(tmp_path) -> None:
    """验证真实 release 不得保留模板状态或占位 commit。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir, release_status="template_pending_external_artifact")
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["repository"]["commit"] = "fill-with-release-commit"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    checksum_lines = []
    for path in sorted(artifact_dir.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            relative_path = path.relative_to(artifact_dir).as_posix()
            checksum_lines.append(f"{_sha256_file(path)}  {relative_path}")
    (artifact_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("release_status" in error for error in errors)
    assert any("repository.commit" in error for error in errors)


def test_validate_artifact_release_rejects_malformed_repository_commit(tmp_path) -> None:
    """验证 artifact release manifest 的提交号必须是 Git SHA。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["repository"]["commit"] = "not-a-commit"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _refresh_checksums(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("repository.commit" in error for error in errors)
    assert any("hexadecimal Git commit" in error for error in errors)


def test_validate_artifact_release_rejects_readme_manifest_commit_mismatch(tmp_path) -> None:
    """验证 release README 和 manifest 必须记录同一个 Git 提交号。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["repository"]["commit"] = "abcdef1234567890abcdef1234567890abcdef12"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _refresh_checksums(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("README.md repository commit" in error for error in errors)
    assert any("manifest.json repository.commit" in error for error in errors)


def test_validate_artifact_release_rejects_skeleton_status(tmp_path) -> None:
    """验证真实 release 不得保留骨架生成状态。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir, release_status="skeleton_pending_artifacts")

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("release_status" in error for error in errors)
    assert any("skeleton_pending_artifacts" in error for error in errors)


def test_validate_artifact_release_rejects_claimed_confidence_without_bootstrap_artifact(tmp_path) -> None:
    """验证声明置信区间时必须提供 bootstrap artifact。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["claim_boundaries"]["confidence_intervals_claimed"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _refresh_checksums(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("confidence_intervals_claimed" in error for error in errors)
    assert any("bootstrap_intervals" in error for error in errors)


def test_validate_artifact_release_accepts_claimed_confidence_with_protocol_bootstrap_intervals(tmp_path) -> None:
    """验证 confidence interval claim 只有在 bootstrap 字段完整时通过。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_bootstrap_intervals_artifact(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert errors == []


def test_validate_artifact_release_rejects_bootstrap_intervals_missing_core_metric(tmp_path) -> None:
    """验证 bootstrap_intervals 缺少核心指标行时会被拒绝。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_bootstrap_intervals_artifact(artifact_dir, _complete_bootstrap_intervals_csv(missing_metric="hnfmr"))

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("bootstrap_intervals CSV missing required metric_name rows" in error for error in errors)
    assert any("hnfmr" in error for error in errors)


def test_validate_artifact_release_rejects_bootstrap_intervals_invalid_interval(tmp_path) -> None:
    """验证 bootstrap_intervals 的点估计必须落在区间内。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_bootstrap_intervals_artifact(artifact_dir, _complete_bootstrap_intervals_csv(invalid_interval=True))

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("interval_lower <= point_estimate <= interval_upper" in error for error in errors)


def test_validate_artifact_release_rejects_bootstrap_intervals_low_resample_count(tmp_path) -> None:
    """验证 bootstrap_intervals 的重采样次数不能过低。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_bootstrap_intervals_artifact(artifact_dir, _complete_bootstrap_intervals_csv(low_resample_count=True))

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("resample_count to an integer >= 100" in error for error in errors)


def test_validate_artifact_release_rejects_claimed_cluster_quality_without_cluster_artifacts(tmp_path) -> None:
    """验证声明 cluster-level 质量时必须提供 cluster audit artifact。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["claim_boundaries"]["cluster_level_quality_claimed"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _refresh_checksums(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("cluster_level_quality_claimed" in error for error in errors)
    assert any("cluster_metric_summary" in error for error in errors)
    assert any("cannot_link_audit" in error for error in errors)


def test_validate_artifact_release_accepts_claimed_cluster_quality_with_protocol_artifacts(tmp_path) -> None:
    """验证 cluster-level quality claim 只有在 cluster artifacts 字段完整时通过。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_cluster_quality_artifacts(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert errors == []


def test_validate_artifact_release_rejects_cluster_metric_summary_without_trace_file(tmp_path) -> None:
    """验证 cluster_metric_summary 缺少 pair-to-cluster trace 时会被拒绝。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    invalid_csv = _complete_cluster_metric_summary_csv().replace("reports/pair_to_cluster_trace.csv", "", 1)
    _add_cluster_quality_artifacts(artifact_dir, cluster_csv_content=invalid_csv)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("cluster_metric_summary CSV line 2 missing required value: pair_to_cluster_trace_file" in error for error in errors)


def test_validate_artifact_release_rejects_cluster_metric_summary_mixed_cluster_run(tmp_path) -> None:
    """验证 cluster_metric_summary 不得混用多个 cluster_run_id。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_cluster_quality_artifacts(artifact_dir, cluster_csv_content=_complete_cluster_metric_summary_csv(mixed_cluster_run=True))

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("cluster_metric_summary CSV must describe exactly one cluster_run_id" in error for error in errors)


def test_validate_artifact_release_rejects_cluster_metric_summary_invalid_ratio(tmp_path) -> None:
    """验证 cluster_metric_summary 的比例字段必须在 0 到 1 之间。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_cluster_quality_artifacts(artifact_dir, cluster_csv_content=_complete_cluster_metric_summary_csv(invalid_ratio=True))

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("cluster_contamination_rate between 0 and 1" in error for error in errors)


def test_validate_artifact_release_rejects_cannot_link_audit_mixed_prediction_files(tmp_path) -> None:
    """验证 cannot_link_audit 必须绑定同一个预测文件校验和。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_cluster_quality_artifacts(artifact_dir, cannot_link_csv_content=_complete_cannot_link_audit_csv(mixed_prediction_checksums=True))

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("cannot_link_audit CSV must be generated from exactly one prediction_file_sha256" in error for error in errors)


def test_validate_artifact_release_rejects_cannot_link_audit_invalid_boolean(tmp_path) -> None:
    """验证 cannot_link_audit 的布尔字段必须可解析。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_cluster_quality_artifacts(artifact_dir, cannot_link_csv_content=_complete_cannot_link_audit_csv(invalid_boolean=True))

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("cannot_link_audit CSV line 2 must set cannot_link_flag to a boolean value" in error for error in errors)


def test_validate_artifact_release_accepts_claimed_component_causality_with_protocol_ablation_suite(tmp_path) -> None:
    """验证组件因果 claim 只有在消融协议字段完整时通过。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_ablation_suite_artifact(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert errors == []


def test_validate_artifact_release_rejects_ablation_suite_missing_protocol_variants(tmp_path) -> None:
    """验证 ablation_suite 缺少协议变体覆盖时会被拒绝。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    incomplete_csv = _complete_ablation_suite_csv().replace(
        "without_cannot_link,no-cannot-link,true,true,same_work_false_merge,predeclared_cli_argument,"
        "same_input_pair_scope_and_split_required,true,0.9,0.9,100,0.9,0.8,0.85,0.01,1,2\n",
        "",
    )
    _add_ablation_suite_artifact(artifact_dir, incomplete_csv)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("ablation_suite CSV missing required protocol_variant rows" in error for error in errors)
    assert any("no-cannot-link" in error for error in errors)


def test_validate_artifact_release_rejects_post_hoc_ablation_as_component_causality(tmp_path) -> None:
    """验证 post-hoc-threshold 行不能标记为组件因果证据。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    invalid_csv = _complete_ablation_suite_csv().replace(
        "post_hoc_threshold,post-hoc-threshold,true,false,same_work_false_merge,post_hoc_labeled_sweep",
        "post_hoc_threshold,post-hoc-threshold,true,true,same_work_false_merge,post_hoc_labeled_sweep",
    )
    _add_ablation_suite_artifact(artifact_dir, invalid_csv)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("post-hoc-threshold row must not be accepted for component causality" in error for error in errors)


def test_validate_artifact_release_accepts_claimed_human_validation_with_protocol_slice(tmp_path) -> None:
    """验证 human validation claim 只有在人工验证协议字段完整时通过。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_manual_validation_slice_artifact(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert errors == []


def test_validate_artifact_release_rejects_manual_validation_slice_below_protocol_size(tmp_path) -> None:
    """验证人工验证 slice 少于 500 行时会被拒绝。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_manual_validation_slice_artifact(artifact_dir, _complete_manual_validation_slice_csv(row_count=499))

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("manual_validation_slice CSV row count must be between 500 and 1000" in error for error in errors)


def test_validate_artifact_release_rejects_manual_validation_slice_missing_required_stratum(tmp_path) -> None:
    """验证人工验证 slice 缺少必要 strata 时会被拒绝。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    csv_content = _complete_manual_validation_slice_csv(omitted_strata={"identifier_conflict"})
    _add_manual_validation_slice_artifact(artifact_dir, csv_content)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("manual_validation_slice CSV missing required strata" in error for error in errors)
    assert any("identifier_conflict" in error for error in errors)


def test_validate_artifact_release_rejects_manual_validation_slice_without_blinding(tmp_path) -> None:
    """验证人工验证 slice 缺少盲审确认时会被拒绝。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    invalid_csv = _complete_manual_validation_slice_csv().replace(
        "pair-0000,source-0000,target-0000,silver_hard_negative,reviewer_a,reviewer_b,"
        "same_work,agenda_non_identity,same_work,true,true,true,adjudicated,rationale-0000,pair-note-0000,disagreement",
        "pair-0000,source-0000,target-0000,silver_hard_negative,reviewer_a,reviewer_b,"
        "same_work,agenda_non_identity,same_work,false,true,true,adjudicated,rationale-0000,pair-note-0000,disagreement",
    )
    _add_manual_validation_slice_artifact(artifact_dir, invalid_csv)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("manual_validation_slice CSV line 2 must set reviewer_blinding_confirmed=true" in error for error in errors)


def test_validate_artifact_release_accepts_claimed_threshold_stability_with_protocol_grid(tmp_path) -> None:
    """验证 threshold stability claim 只有在阈值网格字段完整时通过。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_threshold_sensitivity_grid_artifact(artifact_dir)

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert errors == []


def test_validate_artifact_release_rejects_threshold_grid_with_single_row(tmp_path) -> None:
    """验证阈值敏感性网格少于两个阈值行时会被拒绝。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_threshold_sensitivity_grid_artifact(artifact_dir, _complete_threshold_sensitivity_grid_csv(row_count=1))

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("threshold_sensitivity_grid CSV must include at least two threshold rows" in error for error in errors)


def test_validate_artifact_release_rejects_threshold_grid_with_selection_leakage(tmp_path) -> None:
    """验证阈值网格不得使用同一 split 选择和评估阈值。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_threshold_sensitivity_grid_artifact(artifact_dir, _complete_threshold_sensitivity_grid_csv(same_split=True))

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("must separate selection_split and evaluation_split" in error for error in errors)


def test_validate_artifact_release_rejects_threshold_grid_from_mixed_prediction_files(tmp_path) -> None:
    """验证阈值网格必须绑定同一个预测文件校验和。"""

    module = _load_artifact_release_validator_module()
    artifact_dir = tmp_path / "artifact_release"
    _write_complete_release(artifact_dir)
    _add_threshold_sensitivity_grid_artifact(
        artifact_dir,
        _complete_threshold_sensitivity_grid_csv(mixed_prediction_checksums=True),
    )

    errors = module.validate_artifact_release(artifact_dir, module.DEFAULT_TEMPLATE_PATH)

    assert any("exactly one prediction_file_sha256" in error for error in errors)
