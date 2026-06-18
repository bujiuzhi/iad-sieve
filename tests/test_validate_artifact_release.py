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
    }
    _write_file(artifact_dir / "README.md", "# IAD-Risk Artifact Release\n")
    _write_file(artifact_dir / "configs" / "model_config.json", '{"seed": 7}\n')
    for artifact_id, relative_path in artifact_locations.items():
        if artifact_id == "open_v2_main_results":
            _write_file(
                artifact_dir / relative_path,
                "\n".join(
                    [
                        "system,scope_type,same_work_f1,fmr,hnfmr,same_work_f1_denominator,fmr_denominator,hnfmr_denominator,threshold_source",
                        "IAD-Risk,Open-v2,0.61,0.08,0.12,100,200,50,threshold_selection_logs",
                    ]
                )
                + "\n",
            )
        else:
            _write_file(artifact_dir / relative_path, f"{artifact_id}\n")

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
