"""测试 artifact release 骨架生成脚本。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "manuscript" / "scripts" / "build_artifact_release_skeleton.py"
MANIFEST_TEMPLATE_PATH = PROJECT_ROOT / "manuscript" / "artifact_release_manifest.template.json"
README_TEMPLATE_PATH = PROJECT_ROOT / "manuscript" / "artifact_release_README.template.md"
TEST_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def _load_builder_module():
    """加载 artifact release 骨架生成脚本模块。

    参数:
        无。

    返回:
        module: 已加载的 Python 模块。
    """
    spec = importlib.util.spec_from_file_location("build_artifact_release_skeleton", SCRIPT_PATH)
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


def _parse_checksum_file(checksum_path: Path) -> dict[str, str]:
    """解析测试生成的 checksum 文件。

    参数:
        checksum_path: checksums.sha256 路径。

    返回:
        dict[str, str]: 相对路径到 SHA256 摘要的映射。
    """
    checksums: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        digest, relative_path = line.split(maxsplit=1)
        checksums[relative_path.strip()] = digest
    return checksums


def test_build_artifact_release_skeleton_creates_reviewable_scaffold(tmp_path) -> None:
    """验证生成器创建可填写的外部 artifact release 骨架。"""

    module = _load_builder_module()
    output_dir = tmp_path / "artifact_release"

    manifest_path = module.build_artifact_release_skeleton(
        output_dir=output_dir,
        manifest_template_path=MANIFEST_TEMPLATE_PATH,
        readme_template_path=README_TEMPLATE_PATH,
        repository_commit=TEST_COMMIT,
        force=False,
    )

    assert manifest_path == output_dir / "manifest.json"
    assert (output_dir / "README.md").is_file()
    assert (output_dir / "manifest.json").is_file()
    assert (output_dir / "checksums.sha256").is_file()
    for directory_name in ["configs", "tables", "predictions", "reports", "logs"]:
        assert (output_dir / directory_name).is_dir()

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["release_status"] == module.SKELETON_RELEASE_STATUS
    assert manifest["repository"]["commit"] == TEST_COMMIT
    assert manifest["repository"]["source_tree_clean"] is True
    assert "generated_from_template" in manifest
    required_rows = [row for row in manifest["required_artifacts"] if row["required"] is True]
    assert required_rows
    assert all(row["sha256"] == module.ARTIFACT_SHA256_PLACEHOLDER for row in required_rows)

    checksums = _parse_checksum_file(output_dir / "checksums.sha256")
    assert set(checksums) == {"README.md", "manifest.json"}
    assert checksums["README.md"] == _sha256_file(output_dir / "README.md")
    assert checksums["manifest.json"] == _sha256_file(output_dir / "manifest.json")


def test_build_artifact_release_skeleton_refuses_existing_non_empty_output(tmp_path) -> None:
    """验证生成器默认拒绝覆盖已有非空目录。"""

    module = _load_builder_module()
    output_dir = tmp_path / "artifact_release"
    output_dir.mkdir()
    (output_dir / "existing.txt").write_text("keep\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        module.build_artifact_release_skeleton(
            output_dir=output_dir,
            manifest_template_path=MANIFEST_TEMPLATE_PATH,
            readme_template_path=README_TEMPLATE_PATH,
            repository_commit=TEST_COMMIT,
            force=False,
        )


def test_build_artifact_release_skeleton_force_replaces_previous_skeleton(tmp_path) -> None:
    """验证 force 模式可替换先前生成的骨架目录。"""

    module = _load_builder_module()
    output_dir = tmp_path / "artifact_release"
    module.build_artifact_release_skeleton(
        output_dir=output_dir,
        manifest_template_path=MANIFEST_TEMPLATE_PATH,
        readme_template_path=README_TEMPLATE_PATH,
        repository_commit=TEST_COMMIT,
        force=False,
    )
    (output_dir / "stale.txt").write_text("stale\n", encoding="utf-8")

    module.build_artifact_release_skeleton(
        output_dir=output_dir,
        manifest_template_path=MANIFEST_TEMPLATE_PATH,
        readme_template_path=README_TEMPLATE_PATH,
        repository_commit=TEST_COMMIT,
        force=True,
    )

    assert not (output_dir / "stale.txt").exists()
    assert (output_dir / "manifest.json").is_file()
