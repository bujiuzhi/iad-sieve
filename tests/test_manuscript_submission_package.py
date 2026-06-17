"""测试投稿包生成脚本。"""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "manuscript" / "scripts" / "build_submission_package.py"
VALIDATOR_SCRIPT_PATH = PROJECT_ROOT / "manuscript" / "scripts" / "validate_submission_package.py"
REQUIRED_TEXT_FILES = [
    "main.tex",
    "supplementary_material.tex",
    "references.bib",
    "cover_letter.md",
    "highlights.md",
    "keywords.md",
]


def _load_submission_package_module():
    """加载投稿包生成脚本模块。

    参数:
        无。

    返回:
        module: 已加载的 Python 模块。
    """
    spec = importlib.util.spec_from_file_location("build_submission_package", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_submission_validator_module():
    """加载投稿包校验脚本模块。

    参数:
        无。

    返回:
        module: 已加载的 Python 模块。
    """
    spec = importlib.util.spec_from_file_location("validate_submission_package", VALIDATOR_SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_file(path: Path, content: bytes | str) -> None:
    """写入测试文件。

    参数:
        path: 输出路径。
        content: 文件内容。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def _write_required_manuscript_files(manuscript_root: Path) -> None:
    """写入投稿包测试所需的稿件文件。

    参数:
        manuscript_root: 临时稿件目录。

    返回:
        无。
    """
    for relative_path in REQUIRED_TEXT_FILES:
        _write_file(manuscript_root / relative_path, f"{relative_path}\n")
    _write_file(manuscript_root / "build" / "iad-risk-manuscript-latex.pdf", b"%PDF-1.5 main\n")
    _write_file(manuscript_root / "build" / "iad-risk-supplementary-material.pdf", b"%PDF-1.5 supp\n")


def test_build_submission_package_writes_manifest_checksums_and_zip(tmp_path) -> None:
    """验证投稿包生成器只打包正式投稿材料。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_file(manuscript_root / "data" / "raw.csv", "must not be packaged\n")

    summary = module.build_submission_package(manuscript_root, output_dir, zip_path)

    manifest = json.loads((output_dir / "submission_manifest.json").read_text(encoding="utf-8"))
    checksum_lines = (output_dir / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    with zipfile.ZipFile(zip_path) as archive:
        zip_names = archive.namelist()

    assert summary["file_count"] == 10
    assert manifest["package_type"] == "journal_submission"
    assert manifest["submission_stage"] == "template_independent_anonymous_pre_submission"
    assert manifest["anonymization"]["author_status"] == "anonymous_placeholder"
    assert manifest["journal_template"]["target_journal_bound"] is False
    assert "target journal document class" in manifest["journal_template"]["final_upload_requirements"]
    assert manifest["reproducibility_level"]["raw_data_distribution"] == "excluded"
    assert manifest["claim_boundary"]["no_broad_method_ranking"] is True
    assert len(manifest["files"]) == 8
    assert any(row["role"] == "main_pdf" for row in manifest["files"])
    assert any("submission_manifest.json" in line for line in checksum_lines)
    assert all("data/" not in name for name in zip_names)
    assert "submission_package/main.tex" in zip_names
    assert "submission_package/checksums.sha256" in zip_names


def test_validate_submission_package_accepts_generated_package(tmp_path) -> None:
    """验证投稿包校验器接受生成器产物。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    errors = validator.validate_submission_package(output_dir, zip_path)

    assert errors == []


def test_validate_submission_package_rejects_forbidden_zip_member(tmp_path) -> None:
    """验证投稿包校验器拒绝 zip 内混入数据目录。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    builder.build_submission_package(manuscript_root, output_dir, zip_path)

    with zipfile.ZipFile(zip_path, mode="a") as archive:
        archive.writestr("submission_package/data/raw.csv", "forbidden")
    errors = validator.validate_zip_archive(zip_path)

    assert any("forbidden path part" in error for error in errors)


def test_validate_submission_package_rejects_incomplete_manifest_metadata(tmp_path) -> None:
    """验证投稿包校验器拒绝缺少正式投稿元数据的 manifest。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    manifest_path = output_dir / "submission_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("claim_boundary")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    errors = validator.validate_package_directory(output_dir)

    assert any("missing top-level fields" in error for error in errors)


def test_validate_submission_package_rejects_extra_package_directory(tmp_path) -> None:
    """验证投稿包校验器拒绝目录中混入额外子目录。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    _write_file(output_dir / "data" / "raw.csv", "forbidden")

    errors = validator.validate_package_directory(output_dir)

    assert any("unexpected directories" in error for error in errors)
    assert any("forbidden path part" in error for error in errors)


def test_validate_submission_package_rejects_extra_zip_member(tmp_path) -> None:
    """验证投稿包校验器拒绝 zip 根目录混入额外文件。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    builder.build_submission_package(manuscript_root, output_dir, zip_path)

    with zipfile.ZipFile(zip_path, mode="a") as archive:
        archive.writestr("notes.txt", "forbidden")
    errors = validator.validate_zip_archive(zip_path)

    assert any("unexpected members" in error for error in errors)


def test_validate_submission_package_rejects_malformed_checksums(tmp_path) -> None:
    """验证投稿包校验器拒绝格式损坏的 checksum 文件。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    (output_dir / "checksums.sha256").write_text("not-a-valid-checksum-line\n", encoding="utf-8")

    errors = validator.validate_package_directory(output_dir)

    assert any("checksums.sha256 is invalid" in error for error in errors)
