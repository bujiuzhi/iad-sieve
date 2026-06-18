"""测试 artifact release 填充脚本。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKELETON_SCRIPT_PATH = PROJECT_ROOT / "manuscript" / "scripts" / "build_artifact_release_skeleton.py"
POPULATE_SCRIPT_PATH = PROJECT_ROOT / "manuscript" / "scripts" / "populate_artifact_release.py"
VALIDATOR_SCRIPT_PATH = PROJECT_ROOT / "manuscript" / "scripts" / "validate_artifact_release.py"
MANIFEST_TEMPLATE_PATH = PROJECT_ROOT / "manuscript" / "artifact_release_manifest.template.json"
README_TEMPLATE_PATH = PROJECT_ROOT / "manuscript" / "artifact_release_README.template.md"
TEST_COMMIT = "0123456789abcdef0123456789abcdef01234567"


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
    """生成 artifact release 测试骨架。

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


def _write_source_artifacts(source_dir: Path, skip_artifact_id: str | None = None) -> None:
    """按 manifest expected_location 写入测试 source artifact。

    参数:
        source_dir: Source artifact 目录。
        skip_artifact_id: 可选跳过的 artifact ID。

    返回:
        无。
    """
    template = json.loads(MANIFEST_TEMPLATE_PATH.read_text(encoding="utf-8"))
    for row in template["required_artifacts"]:
        if row.get("required") is not True:
            continue
        if row["artifact_id"] == skip_artifact_id:
            continue
        _write_file(source_dir / row["expected_location"], f"{row['artifact_id']}\n")
    _write_file(source_dir / "configs" / "model_config.json", '{"seed": 7}\n')


def test_populate_artifact_release_copies_required_files_and_finalizes(tmp_path) -> None:
    """验证 source artifact 目录可填充 release 骨架并通过最终校验。"""

    artifact_dir = tmp_path / "artifact_release"
    source_dir = tmp_path / "source_artifacts"
    _build_skeleton(artifact_dir)
    _write_source_artifacts(source_dir)
    populator = _load_module("populate_artifact_release", POPULATE_SCRIPT_PATH)
    validator = _load_module("validate_artifact_release", VALIDATOR_SCRIPT_PATH)

    copied_rows = populator.populate_artifact_release(
        artifact_dir=artifact_dir,
        source_dir=source_dir,
        manifest_template_path=MANIFEST_TEMPLATE_PATH,
        mapping_path=None,
        finalize=True,
    )

    copied_ids = {row["artifact_id"] for row in copied_rows}
    assert {
        "open_v2_main_results",
        "iad_risk_predictions",
        "representation_baseline_scores",
        "supervised_baseline_predictions",
        "threshold_selection_logs",
        "iad_bench_split_summary",
    } <= copied_ids
    assert (artifact_dir / "tables" / "open_v2_main_results.csv").read_text(encoding="utf-8").strip()
    assert (artifact_dir / "logs" / "artifact_population_log.jsonl").is_file()
    assert validator.validate_artifact_release(artifact_dir, MANIFEST_TEMPLATE_PATH) == []


def test_populate_artifact_release_rejects_missing_required_source_file(tmp_path) -> None:
    """验证 source 目录缺少必需 artifact 时拒绝填充。"""

    artifact_dir = tmp_path / "artifact_release"
    source_dir = tmp_path / "source_artifacts"
    _build_skeleton(artifact_dir)
    _write_source_artifacts(source_dir, skip_artifact_id="open_v2_main_results")
    populator = _load_module("populate_artifact_release", POPULATE_SCRIPT_PATH)

    with pytest.raises(ValueError) as exc_info:
        populator.populate_artifact_release(
            artifact_dir=artifact_dir,
            source_dir=source_dir,
            manifest_template_path=MANIFEST_TEMPLATE_PATH,
            mapping_path=None,
            finalize=False,
        )

    message = str(exc_info.value)
    assert "missing required source artifact files" in message
    assert "open_v2_main_results" in message
