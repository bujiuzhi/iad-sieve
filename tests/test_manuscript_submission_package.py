"""测试投稿包生成脚本。"""

from __future__ import annotations

import importlib.util
import json
import os
import zipfile
from pathlib import Path

import pytest


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
    "submission_metadata.yml",
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


def _write_dke_preflight_files(manuscript_root: Path) -> None:
    """写入DKE预投稿包测试所需的Elsevier文件。

    参数:
        manuscript_root: 临时稿件目录。

    返回:
        无。
    """
    _write_file(manuscript_root / "build" / "iad-risk-manuscript-elsevier.tex", "\\documentclass{elsarticle}\n")
    _write_file(manuscript_root / "build" / "iad-risk-manuscript-elsevier.pdf", b"%PDF-1.5 dke\n")


def _clean_source_control_state(commit: str = "abcdef1234567890") -> dict:
    """构造测试用 Git 源状态。

    参数:
        commit: 仓库提交号。

    返回:
        dict: 投稿包 manifest 使用的 source_control 字段。
    """
    return {
        "available": True,
        "repository_commit": commit,
        "repository_branch": "main",
        "worktree_dirty": False,
        "tracked_state": "clean",
    }


def _write_unresolved_submission_metadata(manuscript_root: Path) -> None:
    """写入未完成正式投稿信息的元数据。

    参数:
        manuscript_root: 临时稿件目录。

    返回:
        无。
    """
    _write_file(
        manuscript_root / "submission_metadata.yml",
        "\n".join(
            [
                "submission:",
                '  target_journal: ""',
                "  target_journal_template_bound: false",
                "  author_metadata_required_before_final_upload: true",
                "",
                "authors: []",
                "",
                "corresponding_author:",
                '  name: ""',
                '  affiliation: ""',
                '  email: ""',
                "",
                "final_upload_checklist:",
                "  target_journal_selected: false",
                "  article_type_confirmed: false",
                "  review_mode_confirmed: false",
                "  target_journal_template_applied: false",
                "  author_metadata_completed: false",
                "  author_biographies_and_photos_ready: false",
                "  corresponding_author_completed: false",
                "  funding_statement_text_ready: false",
                "  contribution_statement_complete: false",
                "  permissions_statement_complete: false",
                "  manuscript_pdf_rebuilt_after_template: false",
                "  supplementary_pdf_rebuilt_after_template: false",
                "  submission_system_files_verified: false",
                "  first_screen_claim_lockdown_confirmed: false",
                "  artifact_release_prepared_or_linked: false",
            ]
        )
        + "\n",
    )


def _write_final_upload_metadata(manuscript_root: Path) -> None:
    """写入满足正式上传门禁的投稿元数据。

    参数:
        manuscript_root: 临时稿件目录。

    返回:
        无。
    """
    _write_file(
        manuscript_root / "submission_metadata.yml",
        "\n".join(
            [
                "submission:",
                '  title: "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication"',
                '  article_type: "research_article"',
                '  review_mode: "anonymous_review"',
                '  target_journal: "Journal of Scholarly Data"',
                "  target_journal_template_bound: true",
                "  author_metadata_required_before_final_upload: true",
                "",
                "authors:",
                '  - name: "Example Author"',
                '    affiliation: "Example University"',
                '    email: "author@example.edu"',
                '    orcid: "0000-0002-1825-0097"',
                "",
                "corresponding_author:",
                '  name: "Example Author"',
                '  affiliation: "Example University"',
                '  email: "author@example.edu"',
                '  orcid: "0000-0002-1825-0097"',
                "",
                "funding:",
                "  no_external_funding_declared: true",
                '  funding_statement: "The authors received no external funding for this work."',
                "  funding_sources: []",
                "  grant_numbers: []",
                "",
                "statements:",
                '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
                '  author_approval: "All listed authors have approved the submitted version."',
                '  competing_interests: "The authors declare no competing interests."',
                '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
                '  data_code_availability: "Source code and fixtures are available at https://example.org/iad-sieve.git commit abcdef1234567890; full result artifacts are available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
                "",
                "author_contributions:",
                "  credit_taxonomy_required_before_final_upload: true",
                '  contribution_statement: "Example Author: conceptualization, methodology, software, validation, and writing - original draft."',
                "  roles:",
                '    - author: "Example Author"',
                '      credit_roles: "Conceptualization; Methodology; Software; Validation; Writing - original draft"',
                "",
                "permissions:",
                "  no_third_party_material_requiring_permission_declared: true",
                "  third_party_material_requires_permission: false",
                '  permissions_statement: "No third-party material requiring permission is included."',
                "  permission_files: []",
                "",
                "generative_ai:",
                "  declaration_required_before_final_upload: true",
                '  ai_tools_used_in_manuscript_preparation: "none"',
                '  declaration_statement: "No generative AI tools were used in manuscript preparation."',
                "  author_review_and_responsibility_confirmed: true",
                "  ai_not_listed_as_author_confirmed: true",
                "  ai_generated_images_or_artwork_included: false",
                "",
                "repository_reference:",
                '  repository_url: "https://example.org/iad-sieve.git"',
                '  repository_commit: "abcdef1234567890"',
                '  repository_branch: "main"',
                "",
                "artifact_boundary:",
                "  raw_third_party_data_included: false",
                "  full_numeric_audit_requires_external_artifact: true",
                "  broad_method_ranking_claimed: false",
                "  silver_labels_claimed_as_human_gold: false",
                '  artifact_release_url: "https://doi.org/10.0000/example"',
                '  artifact_release_doi: "10.0000/example"',
                "",
                "final_upload_checklist:",
                "  target_journal_selected: true",
                "  article_type_confirmed: true",
                "  review_mode_confirmed: true",
                "  target_journal_template_applied: true",
                "  author_metadata_completed: true",
                "  author_biographies_and_photos_ready: true",
                "  corresponding_author_completed: true",
                "  funding_statement_text_ready: true",
                "  contribution_statement_complete: true",
                "  permissions_statement_complete: true",
                "  generative_ai_declaration_complete: true",
                "  manuscript_pdf_rebuilt_after_template: true",
                "  supplementary_pdf_rebuilt_after_template: true",
                "  submission_system_files_verified: true",
                "  first_screen_claim_lockdown_confirmed: true",
                "  artifact_release_prepared_or_linked: true",
            ]
        )
        + "\n",
    )


def _blank_final_upload_repository_reference(manuscript_root: Path) -> None:
    """清空正式上传元数据中的仓库引用字段。

    参数:
        manuscript_root: 临时稿件目录。

    返回:
        无。
    """
    metadata_path = manuscript_root / "submission_metadata.yml"
    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata_text = metadata_text.replace('  repository_url: "https://example.org/iad-sieve.git"', '  repository_url: ""')
    metadata_text = metadata_text.replace('  repository_commit: "abcdef1234567890"', '  repository_commit: ""')
    metadata_text = metadata_text.replace('  repository_branch: "main"', '  repository_branch: ""')
    metadata_text = metadata_text.replace(
        '  data_code_availability: "Source code and fixtures are available at https://example.org/iad-sieve.git commit abcdef1234567890; full result artifacts are available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
        '  data_code_availability: "The repository provides source code, small public fixtures, schema contracts, build scripts, and artifact-release instructions. Raw third-party data and full experimental outputs are not redistributed in Git."',
    )
    metadata_path.write_text(metadata_text, encoding="utf-8")


def _write_final_upload_cover_letter(manuscript_root: Path) -> None:
    """写入满足正式上传门禁的投稿信。

    参数:
        manuscript_root: 临时稿件目录。

    返回:
        无。
    """
    _write_file(
        manuscript_root / "cover_letter.md",
        "\n".join(
            [
                "# Cover Letter",
                "",
                "Dear Editors of Journal of Scholarly Data,",
                "",
                "We submit the manuscript titled "
                '"IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication" '
                "for consideration as a research article in Journal of Scholarly Data.",
                "The final-upload manuscript uses the selected journal template and the author metadata in the submission system.",
                "The artifact release is available at https://doi.org/10.0000/example "
                "with DOI 10.0000/example and supports result-level review.",
                "",
                "Sincerely,",
                "",
                "Example Author",
            ]
        )
        + "\n",
    )


def _write_dke_final_upload_metadata(manuscript_root: Path) -> None:
    """写入满足 DKE 正式上传门禁的投稿元数据。

    参数:
        manuscript_root: 临时稿件目录。

    返回:
        无。
    """
    _write_file(
        manuscript_root / "submission_metadata.yml",
        "\n".join(
            [
                "submission:",
                '  title: "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication"',
                '  article_type: "research_article"',
                '  review_mode: "single_anonymized_author_visible_final_upload"',
                '  target_journal: "Data & Knowledge Engineering"',
                "  target_journal_template_bound: true",
                "  author_metadata_required_before_final_upload: true",
                "",
                "authors:",
                '  - name: "Example Author"',
                '    affiliation: "Example University"',
                '    email: "author@example.edu"',
                '    orcid: "0000-0002-1825-0097"',
                "",
                "corresponding_author:",
                '  name: "Example Author"',
                '  affiliation: "Example University"',
                '  email: "author@example.edu"',
                '  orcid: "0000-0002-1825-0097"',
                "",
                "funding:",
                "  no_external_funding_declared: true",
                '  funding_statement: "The authors received no external funding for this work."',
                "  funding_sources: []",
                "  grant_numbers: []",
                "",
                "statements:",
                '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
                '  author_approval: "All listed authors have approved the submitted version."',
                '  competing_interests: "The authors declare no competing interests."',
                '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
                '  data_code_availability: "Source code and fixtures are available at https://example.org/iad-sieve.git commit abcdef1234567890; full result artifacts are available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
                '  research_data_statement: "Source code and small fixtures are available in the repository; the full result artifact is available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
                "",
                "author_contributions:",
                "  credit_taxonomy_required_before_final_upload: true",
                '  contribution_statement: "Example Author: conceptualization, methodology, software, validation, and writing - original draft."',
                "  roles:",
                '    - author: "Example Author"',
                '      credit_roles: "Conceptualization; Methodology; Software; Validation; Writing - original draft"',
                "",
                "permissions:",
                "  no_third_party_material_requiring_permission_declared: true",
                "  third_party_material_requires_permission: false",
                '  permissions_statement: "No third-party material requiring permission is included."',
                "  permission_files: []",
                "",
                "generative_ai:",
                "  declaration_required_before_final_upload: true",
                '  ai_tools_used_in_manuscript_preparation: "none"',
                '  declaration_statement: "No generative AI tools were used in manuscript preparation."',
                "  author_review_and_responsibility_confirmed: true",
                "  ai_not_listed_as_author_confirmed: true",
                "  ai_generated_images_or_artwork_included: false",
                "",
                "repository_reference:",
                '  repository_url: "https://example.org/iad-sieve.git"',
                '  repository_commit: "abcdef1234567890"',
                '  repository_branch: "main"',
                "",
                "artifact_boundary:",
                '  artifact_release_url: "https://doi.org/10.0000/example"',
                '  artifact_release_doi: "10.0000/example"',
                "",
                "final_upload_checklist:",
                "  target_journal_selected: true",
                "  article_type_confirmed: true",
                "  review_mode_confirmed: true",
                "  target_journal_template_applied: true",
                "  author_metadata_completed: true",
                "  author_biographies_and_photos_ready: true",
                "  corresponding_author_completed: true",
                "  funding_statement_text_ready: true",
                "  contribution_statement_complete: true",
                "  permissions_statement_complete: true",
                "  generative_ai_declaration_complete: true",
                "  manuscript_pdf_rebuilt_after_template: true",
                "  supplementary_pdf_rebuilt_after_template: true",
                "  submission_system_files_verified: true",
                "  first_screen_claim_lockdown_confirmed: true",
                "  artifact_release_prepared_or_linked: true",
            ]
        )
        + "\n",
    )


def _write_dke_final_upload_cover_letter(manuscript_root: Path) -> None:
    """写入满足 DKE 正式上传门禁的投稿信。

    参数:
        manuscript_root: 临时稿件目录。

    返回:
        无。
    """
    _write_file(
        manuscript_root / "cover_letter.md",
        "\n".join(
            [
                "# Cover Letter",
                "",
                "Dear Editors of Data & Knowledge Engineering,",
                "",
                "We submit the manuscript titled "
                '"IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication" '
                "for consideration as a research article in Data & Knowledge Engineering.",
                "The final-upload manuscript uses the selected Elsevier template and author-visible title page.",
                "The artifact release is available at https://doi.org/10.0000/example "
                "with DOI 10.0000/example and supports result-level review.",
                "",
                "Sincerely,",
                "",
                "Example Author",
            ]
        )
        + "\n",
    )


def _write_malformed_final_upload_metadata(manuscript_root: Path) -> None:
    """写入结构不完整的正式上传元数据。

    参数:
        manuscript_root: 临时稿件目录。

    返回:
        无。
    """
    _write_file(
        manuscript_root / "submission_metadata.yml",
        "\n".join(
            [
                "submission:",
                '  title: "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication"',
                '  target_journal: "Journal of Scholarly Data"',
                "  target_journal_template_bound: true",
                "",
                "authors:",
                '  - name: "Example Author"',
                '    affiliation: "Example University"',
                "",
                "corresponding_author:",
                '  name: "Example Author"',
                '  affiliation: "Example University"',
                '  email: "not-an-email"',
                '  orcid: "bad-orcid"',
                "",
                "artifact_boundary:",
                "  raw_third_party_data_included: false",
                "  full_numeric_audit_requires_external_artifact: true",
                "  broad_method_ranking_claimed: false",
                "  silver_labels_claimed_as_human_gold: false",
                '  artifact_release_url: ""',
                '  artifact_release_doi: ""',
                "",
                "final_upload_checklist:",
                "  target_journal_selected: true",
                "  article_type_confirmed: true",
                "  review_mode_confirmed: true",
                "  target_journal_template_applied: true",
                "  author_metadata_completed: true",
                "  author_biographies_and_photos_ready: true",
                "  corresponding_author_completed: true",
                "  manuscript_pdf_rebuilt_after_template: true",
                "  supplementary_pdf_rebuilt_after_template: true",
                "  submission_system_files_verified: true",
                "  first_screen_claim_lockdown_confirmed: true",
                "  artifact_release_prepared_or_linked: true",
            ]
        )
        + "\n",
    )


def _write_artifact_release_manifest(artifact_dir: Path, repository_commit: str = "abcdef1234567890") -> None:
    """写入测试用外部 artifact release manifest。

    参数:
        artifact_dir: Artifact release 目录。
        repository_commit: Artifact manifest 记录的源码提交号。

    返回:
        无。
    """
    _write_file(
        artifact_dir / "manifest.json",
        json.dumps({"repository": {"commit": repository_commit}}, indent=2) + "\n",
    )


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

    assert summary["file_count"] == 11
    assert manifest["package_type"] == "journal_submission"
    assert manifest["submission_stage"] == "template_independent_anonymous_pre_submission"
    assert manifest["anonymization"]["author_status"] == "anonymous_placeholder"
    assert manifest["journal_template"]["target_journal_bound"] is False
    assert "target journal document class" in manifest["journal_template"]["final_upload_requirements"]
    assert manifest["reproducibility_level"]["raw_data_distribution"] == "excluded"
    assert manifest["claim_boundary"]["no_broad_method_ranking"] is True
    assert set(manifest["source_control"]) == {
        "available",
        "repository_commit",
        "repository_branch",
        "worktree_dirty",
        "tracked_state",
    }
    assert len(manifest["files"]) == 9
    assert any(row["role"] == "main_pdf" for row in manifest["files"])
    assert any(row["role"] == "submission_metadata" for row in manifest["files"])
    assert any("submission_manifest.json" in line for line in checksum_lines)
    assert all("data/" not in name for name in zip_names)
    assert "submission_package/main.tex" in zip_names
    assert "submission_package/submission_metadata.yml" in zip_names
    assert "submission_package/checksums.sha256" in zip_names


def test_build_submission_package_rejects_final_upload_with_unresolved_metadata(tmp_path) -> None:
    """验证投稿包生成器在正式上传模式下拒绝未填写元数据。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_unresolved_submission_metadata(manuscript_root)

    with pytest.raises(ValueError) as exc_info:
        module.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)

    assert "target journal is empty" in str(exc_info.value)
    assert "author list is empty" in str(exc_info.value)
    assert "artifact release checklist item is incomplete" in str(exc_info.value)


def test_build_submission_package_accepts_final_upload_with_filled_metadata(tmp_path) -> None:
    """验证投稿包生成器接受完整正式上传元数据。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)
    _write_final_upload_cover_letter(manuscript_root)

    summary = module.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)
    manifest = json.loads((output_dir / "submission_manifest.json").read_text(encoding="utf-8"))

    assert summary["file_count"] == 11
    assert manifest["submission_stage"] == "final_journal_upload_preflight"
    assert manifest["anonymization"]["author_status"] == "provided_for_final_upload"
    assert manifest["journal_template"]["target_journal_bound"] is True
    assert "artifact release linked" in manifest["journal_template"]["final_upload_requirements"]


def test_build_submission_package_autofills_final_upload_repository_reference(tmp_path, monkeypatch) -> None:
    """验证正式上传包会自动写入 Git 仓库 URL、提交号和分支。"""

    module = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)
    _blank_final_upload_repository_reference(manuscript_root)
    _write_final_upload_cover_letter(manuscript_root)
    monkeypatch.setattr(module, "collect_source_control_state", lambda _: _clean_source_control_state())
    monkeypatch.setattr(module, "collect_repository_url", lambda _: "https://example.org/iad-sieve.git")

    module.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)

    source_metadata_text = (manuscript_root / "submission_metadata.yml").read_text(encoding="utf-8")
    package_metadata_text = (output_dir / "submission_metadata.yml").read_text(encoding="utf-8")
    assert 'repository_url: ""' in source_metadata_text
    assert 'repository_commit: ""' in source_metadata_text
    assert 'repository_url: "https://example.org/iad-sieve.git"' in package_metadata_text
    assert 'repository_commit: "abcdef1234567890"' in package_metadata_text
    assert 'repository_branch: "main"' in package_metadata_text
    assert "https://example.org/iad-sieve.git commit abcdef1234567890" in package_metadata_text
    assert validator.validate_submission_package(output_dir, zip_path, final_upload=True) == []


def test_normalize_repository_url_converts_github_ssh_remote() -> None:
    """验证 GitHub SSH remote 会转成投稿元数据可用的 HTTPS URL。"""

    module = _load_submission_package_module()

    assert module.normalize_repository_url("git@github.com:bujiuzhi/iad-sieve.git") == "https://github.com/bujiuzhi/iad-sieve.git"
    assert module.normalize_repository_url("ssh://git@github.com/bujiuzhi/iad-sieve.git") == "https://github.com/bujiuzhi/iad-sieve.git"


def test_build_submission_package_records_clean_source_control_state(tmp_path, monkeypatch) -> None:
    """验证投稿包 manifest 记录可复核的 Git 提交锚点。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    monkeypatch.setattr(module, "collect_source_control_state", lambda _: _clean_source_control_state())

    module.build_submission_package(manuscript_root, output_dir, zip_path)
    manifest = json.loads((output_dir / "submission_manifest.json").read_text(encoding="utf-8"))

    assert manifest["source_control"]["available"] is True
    assert manifest["source_control"]["repository_commit"] == "abcdef1234567890"
    assert manifest["source_control"]["repository_branch"] == "main"
    assert manifest["source_control"]["worktree_dirty"] is False
    assert manifest["source_control"]["tracked_state"] == "clean"


def test_build_submission_package_rejects_dke_final_upload_without_elsevier_files(tmp_path) -> None:
    """验证 DKE 正式上传包必须包含 Elsevier/DKE 源文件。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_dke_final_upload_metadata(manuscript_root)
    _write_dke_final_upload_cover_letter(manuscript_root)

    with pytest.raises(ValueError) as exc_info:
        module.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)

    assert "DKE/Elsevier final upload requires DKE/Elsevier source and PDF files" in str(exc_info.value)


def test_build_submission_package_rejects_generic_final_upload_cover_letter(tmp_path) -> None:
    """验证正式上传构建器拒绝通用占位投稿信。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)

    with pytest.raises(ValueError) as exc_info:
        module.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)

    message = str(exc_info.value)
    assert "cover letter missing target journal" in message
    assert "cover letter missing artifact release boundary" in message


def test_build_submission_package_rejects_malformed_final_upload_metadata(tmp_path) -> None:
    """验证投稿包生成器拒绝结构不完整的正式上传元数据。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_malformed_final_upload_metadata(manuscript_root)

    with pytest.raises(ValueError) as exc_info:
        module.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)

    message = str(exc_info.value)
    assert "author row 1 email is missing" in message
    assert "corresponding author email is invalid" in message
    assert "artifact release URL or DOI is required" in message


def test_build_submission_package_writes_dke_preflight_package(tmp_path) -> None:
    """验证DKE预投稿包包含Elsevier源文件和PDF但仍保持匿名预投稿状态。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "dke_preflight_package"
    zip_path = tmp_path / "dke_preflight_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_dke_preflight_files(manuscript_root)

    summary = module.build_submission_package(manuscript_root, output_dir, zip_path, dke_preflight=True)

    manifest = json.loads((output_dir / "submission_manifest.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(zip_path) as archive:
        zip_names = archive.namelist()

    assert summary["file_count"] == 13
    assert summary["dke_preflight"] is True
    assert manifest["submission_stage"] == "dke_elsevier_anonymous_preflight"
    assert manifest["journal_template"]["dke_elsevier_preflight_included"] is True
    assert any(row["role"] == "dke_elsevier_latex_source" for row in manifest["files"])
    assert any(row["role"] == "dke_elsevier_pdf" for row in manifest["files"])
    assert "dke_preflight_package/iad-risk-manuscript-elsevier.tex" in zip_names
    assert "dke_preflight_package/iad-risk-manuscript-elsevier.pdf" in zip_names


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


def test_validate_submission_package_rejects_stale_main_pdf_against_references(tmp_path) -> None:
    """验证主稿 PDF 早于包内参考文献时投稿包被拒绝。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    pdf_mtime = 1_700_000_000
    source_mtime = pdf_mtime + 10
    os.utime(output_dir / "iad-risk-manuscript-latex.pdf", (pdf_mtime, pdf_mtime))
    os.utime(output_dir / "references.bib", (source_mtime, source_mtime))
    errors = validator.validate_package_directory(output_dir)

    assert any("iad-risk-manuscript-latex.pdf is older than references.bib" in error for error in errors)


def test_validate_submission_package_rejects_stale_dke_pdf_against_elsevier_source(tmp_path) -> None:
    """验证 DKE PDF 早于包内 Elsevier 源文件时投稿包被拒绝。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "dke_preflight_package"
    zip_path = tmp_path / "dke_preflight_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_dke_preflight_files(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path, dke_preflight=True)
    pdf_mtime = 1_700_000_000
    source_mtime = pdf_mtime + 10
    os.utime(output_dir / "iad-risk-manuscript-elsevier.pdf", (pdf_mtime, pdf_mtime))
    os.utime(output_dir / "iad-risk-manuscript-elsevier.tex", (source_mtime, source_mtime))
    errors = validator.validate_package_directory(output_dir, dke_preflight=True)

    assert any(
        "iad-risk-manuscript-elsevier.pdf is older than iad-risk-manuscript-elsevier.tex" in error
        for error in errors
    )


def test_validate_submission_package_rejects_directory_text_hygiene_leaks(tmp_path) -> None:
    """验证投稿包目录文本中出现本机路径和过程痕迹时会被拒绝。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    local_path_example = "/" + "Users" + "/reviewer/work/code/python/iad-sieve"
    _write_file(
        output_dir / "cover_letter.md",
        f"Draft copied from {local_path_example}.\nCodex work record.\n",
    )
    builder.write_checksums(output_dir)
    errors = validator.validate_package_directory(output_dir)

    assert any("local macOS absolute path" in error for error in errors)
    assert any("AI/tool trace" in error for error in errors)


def test_validate_submission_package_rejects_anonymous_identity_leaks_in_zip(tmp_path) -> None:
    """验证匿名投稿 zip 内出现邮箱、ORCID 和个人账号时会被拒绝。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    _write_file(
        output_dir / "submission_metadata.yml",
        "\n".join(
            [
                'corresponding_author_email: "author@example.edu"',
                'orcid: "0000-0000-0000-0000"',
                'repository: "https://github.com/bujiuzhi/iad-sieve"',
            ]
        )
        + "\n",
    )
    builder.write_checksums(output_dir)
    builder.create_zip_archive(output_dir, zip_path)
    errors = validator.validate_zip_archive(zip_path)

    assert any("email address in anonymous package" in error for error in errors)
    assert any("ORCID in anonymous package" in error for error in errors)
    assert any("personal repository URL in anonymous package" in error for error in errors)


def test_validate_submission_package_accepts_dke_preflight_package(tmp_path) -> None:
    """验证投稿包校验器接受DKE预投稿包。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "dke_preflight_package"
    zip_path = tmp_path / "dke_preflight_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_dke_preflight_files(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path, dke_preflight=True)
    errors = validator.validate_submission_package(output_dir, zip_path, dke_preflight=True)

    assert errors == []


def test_validate_submission_package_rejects_dke_package_without_profile(tmp_path) -> None:
    """验证DKE预投稿包必须用DKE profile 校验。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "dke_preflight_package"
    zip_path = tmp_path / "dke_preflight_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_dke_preflight_files(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path, dke_preflight=True)
    errors = validator.validate_submission_package(output_dir, zip_path)

    assert any("unexpected files" in error for error in errors)
    assert any("submission_stage must be template_independent_anonymous_pre_submission" in error for error in errors)


def test_validate_submission_package_rejects_final_upload_with_unresolved_metadata(tmp_path) -> None:
    """验证投稿包校验器在正式上传模式下拒绝未填写元数据。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_unresolved_submission_metadata(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True)

    assert any("target journal is empty" in error for error in errors)
    assert any("corresponding author email is empty" in error for error in errors)
    assert any("artifact release checklist item is incomplete" in error for error in errors)


def test_validate_submission_package_accepts_final_upload_with_filled_metadata(tmp_path) -> None:
    """验证投稿包校验器接受完整正式上传元数据。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)
    _write_final_upload_cover_letter(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True)

    assert errors == []


def test_validate_submission_package_accepts_matching_final_upload_artifact_manifest(tmp_path) -> None:
    """验证正式上传包可与同提交号 artifact manifest 绑定。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    artifact_dir = tmp_path / "artifact_release"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)
    _write_final_upload_cover_letter(manuscript_root)
    _write_artifact_release_manifest(artifact_dir)

    builder.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True, artifact_dir=artifact_dir)

    assert errors == []


def test_validate_submission_package_rejects_manifest_without_source_control(tmp_path) -> None:
    """验证投稿包 manifest 缺少 source_control 字段时会被拒绝。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    manifest_path = output_dir / "submission_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("source_control")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    errors = validator.validate_package_directory(output_dir)

    assert any("source_control" in error for error in errors)


def test_validate_submission_package_rejects_final_upload_commit_mismatch(tmp_path, monkeypatch) -> None:
    """验证正式上传包的 Git 提交号必须匹配投稿元数据。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)
    _write_final_upload_cover_letter(manuscript_root)
    monkeypatch.setattr(builder, "collect_source_control_state", lambda _: _clean_source_control_state("bbbbbbbbbbbbbbbb"))

    builder.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True)

    assert any("source_control commit bbbbbbbbbbbbbbbb" in error for error in errors)
    assert any("repository_commit abcdef1234567890" in error for error in errors)


def test_validate_submission_package_rejects_final_upload_artifact_commit_mismatch(tmp_path) -> None:
    """验证正式上传包和 artifact manifest 必须记录同一个提交号。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    artifact_dir = tmp_path / "artifact_release"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)
    _write_final_upload_cover_letter(manuscript_root)
    _write_artifact_release_manifest(artifact_dir, "bbbbbbbbbbbbbbbb")

    builder.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True, artifact_dir=artifact_dir)

    assert any("submission_metadata.yml repository_commit" in error for error in errors)
    assert any("artifact manifest repository.commit" in error for error in errors)


def test_validate_submission_package_rejects_final_upload_dirty_source_control(tmp_path, monkeypatch) -> None:
    """验证正式上传包不能来自 dirty 工作区。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)
    _write_final_upload_cover_letter(manuscript_root)
    dirty_state = _clean_source_control_state()
    dirty_state["worktree_dirty"] = True
    dirty_state["tracked_state"] = "dirty"
    monkeypatch.setattr(builder, "collect_source_control_state", lambda _: dirty_state)

    builder.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True)

    assert any("source_control worktree_dirty must be false" in error for error in errors)


def test_validate_submission_package_rejects_dke_final_upload_without_elsevier_profile(tmp_path) -> None:
    """验证 DKE 正式上传校验拒绝缺少 DKE/Elsevier profile 的包。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_dke_final_upload_metadata(manuscript_root)
    _write_dke_final_upload_cover_letter(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True)

    assert any("DKE/Elsevier final upload requires DKE/Elsevier source and PDF files" in error for error in errors)


def test_validate_submission_package_rejects_final_upload_manifest_with_anonymous_stage(tmp_path) -> None:
    """验证正式上传校验器拒绝仍标记为匿名预投稿状态的 manifest。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)
    _write_final_upload_cover_letter(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)
    manifest_path = output_dir / "submission_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["submission_stage"] = "template_independent_anonymous_pre_submission"
    manifest["anonymization"]["author_status"] = "anonymous_placeholder"
    manifest["journal_template"]["target_journal_bound"] = False
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    builder.write_checksums(output_dir)
    builder.create_zip_archive(output_dir, zip_path)

    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True)

    assert any("submission_stage must be final_journal_upload_preflight" in error for error in errors)
    assert any("must record final-upload author metadata status" in error for error in errors)
    assert any("must record that target journal template is bound" in error for error in errors)


def test_validate_submission_package_rejects_generic_final_upload_cover_letter(tmp_path) -> None:
    """验证正式上传校验器拒绝通用占位投稿信。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True)

    assert any("cover letter missing target journal" in error for error in errors)
    assert any("cover letter missing artifact release boundary" in error for error in errors)


def test_validate_submission_package_rejects_malformed_final_upload_metadata(tmp_path) -> None:
    """验证投稿包校验器拒绝结构不完整的正式上传元数据。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_malformed_final_upload_metadata(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True)

    assert any("author row 1 email is missing" in error for error in errors)
    assert any("corresponding author ORCID is invalid" in error for error in errors)
    assert any("artifact release URL or DOI is required" in error for error in errors)


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
