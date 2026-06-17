"""测试投稿包生成脚本。"""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "manuscript" / "scripts" / "build_submission_package.py"


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


def test_build_submission_package_writes_manifest_checksums_and_zip(tmp_path) -> None:
    """验证投稿包生成器只打包正式投稿材料。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    required_text_files = [
        "main.tex",
        "supplementary_material.tex",
        "references.bib",
        "cover_letter.md",
        "highlights.md",
        "keywords.md",
    ]
    for relative_path in required_text_files:
        _write_file(manuscript_root / relative_path, f"{relative_path}\n")
    _write_file(manuscript_root / "build" / "iad-risk-manuscript-latex.pdf", b"%PDF-1.5 main\n")
    _write_file(manuscript_root / "build" / "iad-risk-supplementary-material.pdf", b"%PDF-1.5 supp\n")
    _write_file(manuscript_root / "data" / "raw.csv", "must not be packaged\n")

    summary = module.build_submission_package(manuscript_root, output_dir, zip_path)

    manifest = json.loads((output_dir / "submission_manifest.json").read_text(encoding="utf-8"))
    checksum_lines = (output_dir / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    with zipfile.ZipFile(zip_path) as archive:
        zip_names = archive.namelist()

    assert summary["file_count"] == 10
    assert len(manifest["files"]) == 8
    assert any(row["role"] == "main_pdf" for row in manifest["files"])
    assert any("submission_manifest.json" in line for line in checksum_lines)
    assert all("data/" not in name for name in zip_names)
    assert "submission_package/main.tex" in zip_names
    assert "submission_package/checksums.sha256" in zip_names
