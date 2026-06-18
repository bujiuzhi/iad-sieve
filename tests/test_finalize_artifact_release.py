"""测试 artifact release 定稿脚本。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKELETON_SCRIPT_PATH = PROJECT_ROOT / "manuscript" / "scripts" / "build_artifact_release_skeleton.py"
FINALIZE_SCRIPT_PATH = PROJECT_ROOT / "manuscript" / "scripts" / "finalize_artifact_release.py"
VALIDATOR_SCRIPT_PATH = PROJECT_ROOT / "manuscript" / "scripts" / "validate_artifact_release.py"
MANIFEST_TEMPLATE_PATH = PROJECT_ROOT / "manuscript" / "artifact_release_manifest.template.json"
README_TEMPLATE_PATH = PROJECT_ROOT / "manuscript" / "artifact_release_README.template.md"
TEST_COMMIT = "0123456789abcdef0123456789abcdef01234567"
OPEN_V2_MAIN_RESULTS_CSV = "\n".join(
    [
        "system,scope_type,same_work_f1,fmr,hnfmr,same_work_f1_denominator,fmr_denominator,hnfmr_denominator,threshold_source",
        "IAD-Risk,Open-v2,0.61,0.08,0.12,100,200,50,threshold_selection_logs",
    ]
) + "\n"


def _load_module(module_name: str, script_path: Path):
    """加载指定脚本模块。

    参数:
        module_name: 运行期模块名。
        script_path: 脚本文件路径。

    返回:
        module: 已加载的 Python 模块。
    """
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256_file(path: Path) -> str:
    """计算文件 SHA256。

    参数:
        path: 文件路径。

    返回:
        str: SHA256 十六进制摘要。
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_file(path: Path, content: str) -> None:
    """写入测试文件。

    参数:
        path: 输出路径。
        content: 文件内容。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_skeleton(artifact_dir: Path) -> None:
    """生成测试 artifact release 骨架。

    参数:
        artifact_dir: Release 目录。

    返回:
        无。
    """
    skeleton_builder = _load_module("build_artifact_release_skeleton", SKELETON_SCRIPT_PATH)
    skeleton_builder.build_artifact_release_skeleton(
        output_dir=artifact_dir,
        manifest_template_path=MANIFEST_TEMPLATE_PATH,
        readme_template_path=README_TEMPLATE_PATH,
        repository_commit=TEST_COMMIT,
        force=False,
    )


def _write_required_artifacts(artifact_dir: Path) -> list[str]:
    """按 manifest 写入必需 artifact 文件。

    参数:
        artifact_dir: Release 目录。

    返回:
        list[str]: 已写入的相对路径列表。
    """
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    written_paths = []
    for row in manifest["required_artifacts"]:
        if row.get("required") is not True:
            continue
        relative_path = row["expected_location"]
        if row["artifact_id"] == "open_v2_main_results":
            _write_file(artifact_dir / relative_path, OPEN_V2_MAIN_RESULTS_CSV)
        else:
            _write_file(artifact_dir / relative_path, f"{row['artifact_id']}\n")
        written_paths.append(relative_path)
    _write_file(artifact_dir / "configs" / "model_config.json", '{"seed": 7}\n')
    written_paths.append("configs/model_config.json")
    return written_paths


def _read_checksums(artifact_dir: Path) -> dict[str, str]:
    """读取 checksums.sha256。

    参数:
        artifact_dir: Release 目录。

    返回:
        dict[str, str]: 相对路径到 SHA256 摘要的映射。
    """
    checksums: dict[str, str] = {}
    for line in (artifact_dir / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, relative_path = line.split(maxsplit=1)
        checksums[relative_path.strip()] = digest
    return checksums


def test_finalize_artifact_release_updates_manifest_and_passes_validator(tmp_path) -> None:
    """验证完整 artifact release 可自动刷新 checksum 和 manifest。"""

    artifact_dir = tmp_path / "artifact_release"
    _build_skeleton(artifact_dir)
    written_paths = _write_required_artifacts(artifact_dir)
    finalizer = _load_module("finalize_artifact_release", FINALIZE_SCRIPT_PATH)
    validator = _load_module("validate_artifact_release", VALIDATOR_SCRIPT_PATH)

    manifest_path = finalizer.finalize_artifact_release(
        artifact_dir=artifact_dir,
        manifest_template_path=MANIFEST_TEMPLATE_PATH,
        release_status="release_candidate",
        validate=True,
    )

    assert manifest_path == artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["release_status"] == "release_candidate"
    assert manifest["generated_from_template"]["artifact_files_pending"] is False
    artifact_rows = {row["artifact_id"]: row for row in manifest["required_artifacts"]}
    for row in artifact_rows.values():
        if row.get("required") is True:
            assert row["sha256"] == _sha256_file(artifact_dir / row["expected_location"])
    checksums = _read_checksums(artifact_dir)
    for relative_path in ["README.md", "manifest.json", *written_paths]:
        assert checksums[relative_path] == _sha256_file(artifact_dir / relative_path)
    assert "checksums.sha256" not in checksums
    assert validator.validate_artifact_release(artifact_dir, MANIFEST_TEMPLATE_PATH) == []


def test_finalize_artifact_release_rejects_missing_required_artifacts(tmp_path) -> None:
    """验证缺少必需 artifact 文件时定稿脚本拒绝继续。"""

    artifact_dir = tmp_path / "artifact_release"
    _build_skeleton(artifact_dir)
    finalizer = _load_module("finalize_artifact_release", FINALIZE_SCRIPT_PATH)

    with pytest.raises(ValueError) as exc_info:
        finalizer.finalize_artifact_release(
            artifact_dir=artifact_dir,
            manifest_template_path=MANIFEST_TEMPLATE_PATH,
            release_status="release_candidate",
            validate=False,
        )

    message = str(exc_info.value)
    assert "missing required artifact files" in message
    assert "open_v2_main_results" in message


def test_finalize_artifact_release_restores_required_validation_command(tmp_path) -> None:
    """验证定稿脚本会补齐旧骨架缺失的 finalizer 校验命令。"""

    artifact_dir = tmp_path / "artifact_release"
    _build_skeleton(artifact_dir)
    _write_required_artifacts(artifact_dir)
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["minimum_validation_commands"] = [
        command
        for command in manifest["minimum_validation_commands"]
        if "finalize_artifact_release.py" not in command
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    finalizer = _load_module("finalize_artifact_release", FINALIZE_SCRIPT_PATH)
    validator = _load_module("validate_artifact_release", VALIDATOR_SCRIPT_PATH)

    finalizer.finalize_artifact_release(
        artifact_dir=artifact_dir,
        manifest_template_path=MANIFEST_TEMPLATE_PATH,
        release_status="release_candidate",
        validate=True,
    )

    finalized_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation_text = "\n".join(finalized_manifest["minimum_validation_commands"])
    assert "python manuscript/scripts/finalize_artifact_release.py --artifact-dir" in validation_text
    assert validator.validate_artifact_release(artifact_dir, MANIFEST_TEMPLATE_PATH) == []
