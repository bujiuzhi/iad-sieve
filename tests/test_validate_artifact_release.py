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
