"""测试投稿包生成脚本。"""

from __future__ import annotations

import hashlib
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


def _sha256_file(path: Path) -> str:
    """计算文件 SHA256。

    参数:
        path: 文件路径。

    返回:
        str: SHA256 十六进制摘要。
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _clean_source_control_state(commit: str = "abcdef1234567890", branch: str = "main") -> dict:
    """构造测试用 Git 源状态。

    参数:
        commit: 仓库提交号。
        branch: 仓库分支名。

    返回:
        dict: 投稿包 manifest 使用的 source_control 字段。
    """
    return {
        "available": True,
        "repository_commit": commit,
        "repository_branch": branch,
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
                "target_preparation:",
                '  selected_author_guide_source: "official journal guide for authors"',
                '  selected_author_guide_source_url: "https://journal-source.org/author-guide"',
                '  selected_author_guide_rechecked_date: "2026-06-19"',
                "  selected_template_requirements_confirmed: true",
                "  ranking_confirmation_required_before_final_upload: true",
                "  ranking_confirmation_completed: true",
                '  ranking_confirmation_source: "institutional ranking system"',
                '  ranking_confirmation_source_url: "https://ranking-source.org/journal-category"',
                '  ranking_confirmation_checked_date: "2026-06-19"',
                "  selected_target_requires_author_confirmation: true",
                "  selected_target_author_confirmed: true",
                "",
                "authors:",
                '  - name: "Example Author"',
                '    affiliation: "Example University"',
                '    email: "author@example.edu"',
                '    orcid: "0000-0002-1825-0097"',
                "",
                "author_identity_materials:",
                "  author_biography_and_photo_required_before_upload: false",
                "  biography_files: []",
                "  photograph_files: []",
                "  author_identity_materials_verified: true",
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
                '  data_code_availability: "Source code and fixtures are available at https://github.com/bujiuzhi/iad-sieve.git commit abcdef1234567890; full result artifacts are available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
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
                '  repository_url: "https://github.com/bujiuzhi/iad-sieve.git"',
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
                "upload_preparation:",
                "  live_submission_system_verified: true",
                "  final_upload_package_verified_against_system: true",
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
    metadata_text = metadata_text.replace('  repository_url: "https://github.com/bujiuzhi/iad-sieve.git"', '  repository_url: ""')
    metadata_text = metadata_text.replace('  repository_commit: "abcdef1234567890"', '  repository_commit: ""')
    metadata_text = metadata_text.replace('  repository_branch: "main"', '  repository_branch: ""')
    metadata_text = metadata_text.replace(
        '  data_code_availability: "Source code and fixtures are available at https://github.com/bujiuzhi/iad-sieve.git commit abcdef1234567890; full result artifacts are available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
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


def _write_preflight_wording_final_upload_cover_letter(manuscript_root: Path) -> None:
    """写入残留匿名预投稿语义的正式上传投稿信。

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
                "This anonymous draft cover letter records only submission-planning boundaries.",
                "The scope-fit note is preparatory and must be replaced after author confirmation.",
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
                "target_preparation:",
                '  selected_author_guide_source: "official journal guide for authors"',
                '  selected_author_guide_source_url: "https://journal-source.org/author-guide"',
                '  selected_author_guide_rechecked_date: "2026-06-19"',
                "  selected_template_requirements_confirmed: true",
                "  ranking_confirmation_required_before_final_upload: true",
                "  ranking_confirmation_completed: true",
                '  ranking_confirmation_source: "institutional ranking system"',
                '  ranking_confirmation_source_url: "https://ranking-source.org/journal-category"',
                '  ranking_confirmation_checked_date: "2026-06-19"',
                "  selected_target_requires_author_confirmation: true",
                "  selected_target_author_confirmed: true",
                "",
                "authors:",
                '  - name: "Example Author"',
                '    affiliation: "Example University"',
                '    email: "author@example.edu"',
                '    orcid: "0000-0002-1825-0097"',
                "",
                "author_identity_materials:",
                "  author_biography_and_photo_required_before_upload: true",
                '  biography_files: ["author-materials/example-author-biography.md"]',
                '  photograph_files: ["author-materials/example-author-photo.jpg"]',
                "  author_identity_materials_verified: true",
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
                '  data_code_availability: "Source code and fixtures are available at https://github.com/bujiuzhi/iad-sieve.git commit abcdef1234567890; full result artifacts are available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
                '  research_data_statement: "Source code and small fixtures are available in the repository; the full result artifact is available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
                "",
                "publisher_declaration_files:",
                "  elsevier_declarations_tool_required_before_upload: true",
                '  competing_interest_declaration_file: "author-materials/competing-interest-declaration.docx"',
                "  competing_interest_declaration_file_verified: true",
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
                '  repository_url: "https://github.com/bujiuzhi/iad-sieve.git"',
                '  repository_commit: "abcdef1234567890"',
                '  repository_branch: "main"',
                "",
                "artifact_boundary:",
                '  artifact_release_url: "https://doi.org/10.0000/example"',
                '  artifact_release_doi: "10.0000/example"',
                "",
                "upload_preparation:",
                "  live_submission_system_verified: true",
                "  final_upload_package_verified_against_system: true",
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


def _artifact_jsonl_row(row: dict) -> str:
    """序列化 artifact release 测试 JSONL 行。

    参数:
        row: 测试记录。

    返回:
        str: JSONL 文本行。
    """
    return json.dumps(row, sort_keys=True) + "\n"


def _required_artifact_content(artifact_id: str) -> str:
    """生成满足 artifact release schema 的测试文件内容。

    参数:
        artifact_id: Artifact 标识。

    返回:
        str: Artifact 文件内容。
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
        return _artifact_jsonl_row(
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
        return _artifact_jsonl_row(
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
        return _artifact_jsonl_row(
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
        return _artifact_jsonl_row(
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
        return _artifact_jsonl_row(
            {
                "stage": "prepare-openalex-weak-labels",
                "command_line": "python -m iad_sieve.cli prepare-openalex-weak-labels",
                "code_commit": "abcdef1234567890",
                "environment_summary": "python=3.11",
                "random_seed": 42,
                "started_at": "2026-06-19T00:00:00Z",
                "finished_at": "2026-06-19T00:01:00Z",
                "input_manifest_reference": "configs/source_input_manifest.json",
                "output_path": "reports/iad_bench_split_summary.jsonl",
                "exit_status": 0,
            }
        )
    return _artifact_jsonl_row({"artifact_id": artifact_id, "status": "present"})


def _write_artifact_release_manifest(artifact_dir: Path, repository_commit: str = "abcdef1234567890") -> None:
    """写入测试用完整外部 artifact release。

    参数:
        artifact_dir: Artifact release 目录。
        repository_commit: Artifact manifest 记录的源码提交号。

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
    _write_file(
        artifact_dir / "README.md",
        "\n".join(
            [
                "# IAD-Risk Artifact Release",
                "",
                "Do not include raw third-party data.",
                "Required files include README.md, manifest.json, and checksums.sha256.",
                "Run sha256sum -c checksums.sha256 before manuscript validation.",
                "Run python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release.",
                "Run python -m iad_sieve.cli --help to verify installable CLI discovery.",
                f"Repository commit: {repository_commit}.",
                "## Claim Boundaries",
                "Full numerical audit requires external artifacts.",
                "source_input_manifest records the public input boundary.",
                "processing_run_log records the processing command boundary.",
                "## Reproduction Levels",
                "L3 result audit checks released tables, predictions, logs, manifests, checksums, and commit identifiers.",
                "",
            ]
        )
        + "\n",
    )
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
        "release_status": "release_candidate",
        "manuscript_title": "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement",
        "repository": {
            "url": "https://github.com/bujiuzhi/iad-sieve.git",
            "commit": repository_commit,
            "branch": "main",
            "source_tree_clean": True,
        },
        "publication": {
            "artifact_release_url": "https://doi.org/10.0000/example",
            "artifact_release_doi": "10.0000/example",
            "public_access_status": "publicly_accessible",
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


def _refresh_artifact_release_checksums(artifact_dir: Path) -> None:
    """刷新测试 artifact release 的 checksums.sha256。

    参数:
        artifact_dir: Artifact release 目录。

    返回:
        无。
    """
    checksum_lines = []
    for path in sorted(artifact_dir.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            relative_path = path.relative_to(artifact_dir).as_posix()
            checksum_lines.append(f"{_sha256_file(path)}  {relative_path}")
    _write_file(artifact_dir / "checksums.sha256", "\n".join(checksum_lines) + "\n")


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
    artifact_dir = tmp_path / "artifact_release"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)
    _blank_final_upload_repository_reference(manuscript_root)
    _write_final_upload_cover_letter(manuscript_root)
    _write_artifact_release_manifest(artifact_dir)
    monkeypatch.setattr(module, "collect_source_control_state", lambda _: _clean_source_control_state())
    monkeypatch.setattr(module, "collect_repository_url", lambda _: "https://github.com/bujiuzhi/iad-sieve.git")

    module.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)

    source_metadata_text = (manuscript_root / "submission_metadata.yml").read_text(encoding="utf-8")
    package_metadata_text = (output_dir / "submission_metadata.yml").read_text(encoding="utf-8")
    assert 'repository_url: ""' in source_metadata_text
    assert 'repository_commit: ""' in source_metadata_text
    assert 'repository_url: "https://github.com/bujiuzhi/iad-sieve.git"' in package_metadata_text
    assert 'repository_commit: "abcdef1234567890"' in package_metadata_text
    assert 'repository_branch: "main"' in package_metadata_text
    assert "https://github.com/bujiuzhi/iad-sieve.git commit abcdef1234567890" in package_metadata_text
    assert validator.validate_submission_package(output_dir, zip_path, final_upload=True, artifact_dir=artifact_dir) == []


def test_build_submission_package_rejects_final_upload_from_non_main_branch(tmp_path, monkeypatch) -> None:
    """验证正式上传包必须从 main 分支生成。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)
    _blank_final_upload_repository_reference(manuscript_root)
    _write_final_upload_cover_letter(manuscript_root)
    monkeypatch.setattr(
        module,
        "collect_source_control_state",
        lambda _: _clean_source_control_state(branch="feature/final-upload"),
    )
    monkeypatch.setattr(module, "collect_repository_url", lambda _: "https://github.com/bujiuzhi/iad-sieve.git")

    with pytest.raises(ValueError) as exc_info:
        module.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)

    assert "repository branch must be main" in str(exc_info.value)


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


def test_build_submission_package_rejects_dke_final_upload_without_author_identity_materials(tmp_path) -> None:
    """验证 DKE 正式上传包拒绝缺失的作者简历和照片材料清单。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_dke_preflight_files(manuscript_root)
    _write_dke_final_upload_metadata(manuscript_root)
    _write_dke_final_upload_cover_letter(manuscript_root)
    metadata_path = manuscript_root / "submission_metadata.yml"
    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata_text = metadata_text.replace(
        '  biography_files: ["author-materials/example-author-biography.md"]',
        "  biography_files: []",
    )
    metadata_text = metadata_text.replace(
        '  photograph_files: ["author-materials/example-author-photo.jpg"]',
        "  photograph_files: []",
    )
    metadata_text = metadata_text.replace(
        "  author_identity_materials_verified: true",
        "  author_identity_materials_verified: false",
    )
    metadata_path.write_text(metadata_text, encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        module.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True, dke_preflight=True)

    message = str(exc_info.value)
    assert "author biography file list is missing" in message
    assert "author photograph file list is missing" in message
    assert "author identity materials verification is incomplete" in message


def test_build_submission_package_rejects_dke_final_upload_without_elsevier_declaration_file(tmp_path) -> None:
    """验证 DKE 正式上传包拒绝缺失的 Elsevier 声明工具文件。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_dke_preflight_files(manuscript_root)
    _write_dke_final_upload_metadata(manuscript_root)
    _write_dke_final_upload_cover_letter(manuscript_root)
    metadata_path = manuscript_root / "submission_metadata.yml"
    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata_text = metadata_text.replace(
        '  competing_interest_declaration_file: "author-materials/competing-interest-declaration.docx"',
        '  competing_interest_declaration_file: ""',
    )
    metadata_text = metadata_text.replace(
        "  competing_interest_declaration_file_verified: true",
        "  competing_interest_declaration_file_verified: false",
    )
    metadata_path.write_text(metadata_text, encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        module.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True, dke_preflight=True)

    message = str(exc_info.value)
    assert "Elsevier competing-interest declaration file is missing" in message
    assert "Elsevier competing-interest declaration file verification is incomplete" in message


def test_build_submission_package_rejects_dke_final_upload_with_pdf_author_biography_file(tmp_path) -> None:
    """验证 DKE 正式上传包拒绝 PDF 作者传记文件。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_dke_preflight_files(manuscript_root)
    _write_dke_final_upload_metadata(manuscript_root)
    _write_dke_final_upload_cover_letter(manuscript_root)
    metadata_path = manuscript_root / "submission_metadata.yml"
    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata_text = metadata_text.replace(
        '  biography_files: ["author-materials/example-author-biography.md"]',
        '  biography_files: ["author-materials/example-author-biography.pdf"]',
    )
    metadata_path.write_text(metadata_text, encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        module.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True, dke_preflight=True)

    assert "author biography file must be editable and must not be PDF" in str(exc_info.value)


def test_build_submission_package_rejects_dke_final_upload_with_unsupported_review_mode(tmp_path) -> None:
    """验证 DKE 正式上传包拒绝不含最终作者身份语义的 review_mode。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_dke_preflight_files(manuscript_root)
    _write_dke_final_upload_metadata(manuscript_root)
    _write_dke_final_upload_cover_letter(manuscript_root)
    metadata_path = manuscript_root / "submission_metadata.yml"
    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata_text = metadata_text.replace(
        '  review_mode: "single_anonymized_author_visible_final_upload"',
        '  review_mode: "single_anonymized"',
    )
    metadata_path.write_text(metadata_text, encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        module.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True, dke_preflight=True)

    assert "review mode must include final author identities for Data & Knowledge Engineering" in str(exc_info.value)


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


def test_build_submission_package_rejects_preflight_wording_final_upload_cover_letter(tmp_path) -> None:
    """验证正式上传构建器拒绝残留匿名预投稿说明的投稿信。"""

    module = _load_submission_package_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)
    _write_preflight_wording_final_upload_cover_letter(manuscript_root)

    with pytest.raises(ValueError) as exc_info:
        module.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)

    message = str(exc_info.value)
    assert "anonymous draft" in message
    assert "submission-planning boundaries" in message
    assert "preparatory scope-fit note" in message
    assert "replacement instructions" in message


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
    errors = validator.validate_submission_package(output_dir, zip_path, source_root=manuscript_root)

    assert errors == []


def test_validate_submission_package_rejects_stale_source_file(tmp_path) -> None:
    """验证当前源文件变更后旧投稿包会被拒绝。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    _write_file(manuscript_root / "main.tex", "updated main source\n")
    errors = validator.validate_submission_package(output_dir, zip_path, source_root=manuscript_root)

    assert any("package file main.tex differs from current source main.tex" in error for error in errors)
    assert any("zip archive package file main.tex differs from current source main.tex" in error for error in errors)


def test_validate_submission_package_rejects_stale_source_control_metadata(tmp_path, monkeypatch) -> None:
    """验证投稿包 manifest 的提交号必须匹配当前检出状态。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    monkeypatch.setattr(builder, "collect_source_control_state", lambda _: _clean_source_control_state("aaaaaaaaaaaaaaaa"))
    monkeypatch.setattr(
        validator,
        "collect_current_source_control_state",
        lambda _: _clean_source_control_state("bbbbbbbbbbbbbbbb"),
    )

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    errors = validator.validate_submission_package(output_dir, zip_path, source_root=manuscript_root)

    assert any("source_control repository_commit aaaaaaaaaaaaaaaa" in error for error in errors)
    assert any("current repository_commit bbbbbbbbbbbbbbbb" in error for error in errors)


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
        f"Draft copied from {local_path_example}.\nCodex work record.\nAssistant draft summary.\nPrompt note.\n",
    )
    builder.write_checksums(output_dir)
    errors = validator.validate_package_directory(output_dir)

    assert any("local macOS absolute path" in error for error in errors)
    assert any("AI/tool trace" in error for error in errors)
    assert any("process-note trace" in error for error in errors)


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


def test_validate_submission_package_rejects_missing_target_ranking_confirmation(tmp_path) -> None:
    """验证正式上传包校验拒绝缺失的目标期刊排名或类别确认。"""

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
    metadata_path = manuscript_root / "submission_metadata.yml"
    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata_text = metadata_text.replace(
        "  ranking_confirmation_completed: true",
        "  ranking_confirmation_completed: false",
    )
    metadata_text = metadata_text.replace(
        '  ranking_confirmation_source: "institutional ranking system"',
        '  ranking_confirmation_source: ""',
    )
    metadata_text = metadata_text.replace(
        '  ranking_confirmation_checked_date: "2026-06-19"',
        '  ranking_confirmation_checked_date: ""',
    )
    metadata_text = metadata_text.replace(
        "  selected_target_author_confirmed: true",
        "  selected_target_author_confirmed: false",
    )
    metadata_path.write_text(metadata_text, encoding="utf-8")

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True, artifact_dir=artifact_dir)

    assert any("ranking/category confirmation is incomplete" in error for error in errors)
    assert any("ranking/category confirmation source is missing" in error for error in errors)
    assert any("ranking/category confirmation checked date is missing" in error for error in errors)
    assert any("selected target journal author confirmation is incomplete" in error for error in errors)


def test_validate_submission_package_rejects_future_target_confirmation_dates(tmp_path) -> None:
    """验证正式上传包校验拒绝未来日期的选刊确认记录。"""

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
    metadata_path = manuscript_root / "submission_metadata.yml"
    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata_text = metadata_text.replace(
        '  selected_author_guide_rechecked_date: "2026-06-19"',
        '  selected_author_guide_rechecked_date: "2099-01-01"',
    )
    metadata_text = metadata_text.replace(
        '  ranking_confirmation_checked_date: "2026-06-19"',
        '  ranking_confirmation_checked_date: "2099-01-01"',
    )
    metadata_path.write_text(metadata_text, encoding="utf-8")

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True, artifact_dir=artifact_dir)

    assert any("selected author guide rechecked date must not be in the future" in error for error in errors)
    assert any("ranking/category confirmation checked date must not be in the future" in error for error in errors)


def test_validate_submission_package_rejects_missing_author_guide_confirmation(tmp_path) -> None:
    """验证正式上传包校验拒绝缺失的作者指南和模板要求确认。"""

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
    metadata_path = manuscript_root / "submission_metadata.yml"
    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata_text = metadata_text.replace(
        '  selected_author_guide_source: "official journal guide for authors"',
        '  selected_author_guide_source: ""',
    )
    metadata_text = metadata_text.replace(
        '  selected_author_guide_rechecked_date: "2026-06-19"',
        '  selected_author_guide_rechecked_date: ""',
    )
    metadata_text = metadata_text.replace(
        "  selected_template_requirements_confirmed: true",
        "  selected_template_requirements_confirmed: false",
    )
    metadata_path.write_text(metadata_text, encoding="utf-8")

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True, artifact_dir=artifact_dir)

    assert any("selected author guide source is missing" in error for error in errors)
    assert any("selected author guide rechecked date is missing" in error for error in errors)
    assert any("selected template requirements confirmation is incomplete" in error for error in errors)


def test_validate_submission_package_rejects_missing_target_source_urls(tmp_path) -> None:
    """验证正式上传包校验拒绝缺失的目标确认来源 URL。"""

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
    metadata_path = manuscript_root / "submission_metadata.yml"
    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata_text = metadata_text.replace(
        '  selected_author_guide_source_url: "https://journal-source.org/author-guide"',
        '  selected_author_guide_source_url: ""',
    )
    metadata_text = metadata_text.replace(
        '  ranking_confirmation_source_url: "https://ranking-source.org/journal-category"',
        '  ranking_confirmation_source_url: ""',
    )
    metadata_path.write_text(metadata_text, encoding="utf-8")

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True, artifact_dir=artifact_dir)

    assert any("selected author guide source URL is missing" in error for error in errors)
    assert any("ranking/category confirmation source URL is missing" in error for error in errors)


def test_validate_submission_package_rejects_placeholder_target_source_urls(tmp_path) -> None:
    """验证正式上传包校验拒绝目标确认来源的占位 URL。"""

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
    metadata_path = manuscript_root / "submission_metadata.yml"
    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata_text = metadata_text.replace(
        '  selected_author_guide_source_url: "https://journal-source.org/author-guide"',
        '  selected_author_guide_source_url: "https://example.org/author-guide"',
    )
    metadata_text = metadata_text.replace(
        '  ranking_confirmation_source_url: "https://ranking-source.org/journal-category"',
        '  ranking_confirmation_source_url: "https://127.0.0.1/ranking"',
    )
    metadata_path.write_text(metadata_text, encoding="utf-8")

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True, artifact_dir=artifact_dir)

    assert any("selected author guide source URL must not use a placeholder URL" in error for error in errors)
    assert any("ranking/category confirmation source URL must not use a placeholder URL" in error for error in errors)


def test_validate_submission_package_rejects_missing_live_system_verification(tmp_path) -> None:
    """验证正式上传包校验拒绝缺失的 live system 终检记录。"""

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
    metadata_path = manuscript_root / "submission_metadata.yml"
    metadata_text = metadata_path.read_text(encoding="utf-8")
    metadata_text = metadata_text.replace(
        "  live_submission_system_verified: true",
        "  live_submission_system_verified: false",
    )
    metadata_text = metadata_text.replace(
        "  final_upload_package_verified_against_system: true",
        "  final_upload_package_verified_against_system: false",
    )
    metadata_path.write_text(metadata_text, encoding="utf-8")

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True, artifact_dir=artifact_dir)

    assert any("live submission system verification is incomplete" in error for error in errors)
    assert any("final upload package verification against live system is incomplete" in error for error in errors)


def test_validate_submission_package_accepts_final_upload_with_valid_artifact_release(tmp_path) -> None:
    """验证投稿包校验器接受完整正式上传元数据和有效 artifact release。"""

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


def test_validate_submission_package_rejects_final_upload_without_artifact_dir(tmp_path) -> None:
    """验证正式上传包校验必须提供外部 artifact release 目录。"""

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

    assert any("final-upload validation requires --artifact-dir" in error for error in errors)


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


def test_validate_submission_package_rejects_final_upload_branch_mismatch(tmp_path, monkeypatch) -> None:
    """验证正式上传包的 Git 分支必须为 main 且匹配投稿元数据。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)
    _write_final_upload_cover_letter(manuscript_root)
    monkeypatch.setattr(builder, "collect_source_control_state", lambda _: _clean_source_control_state())

    builder.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)
    manifest_path = output_dir / "submission_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_control"]["repository_branch"] = "feature/final-upload"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    builder.write_checksums(output_dir)
    builder.create_zip_archive(output_dir, zip_path)

    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True)

    assert any("source_control branch feature/final-upload" in error for error in errors)
    assert any("repository_branch must be main" in error for error in errors)


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


def test_validate_submission_package_rejects_missing_artifact_publication_binding(tmp_path) -> None:
    """验证正式上传包要求 artifact manifest 记录公开 release 链接。"""

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
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("publication")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _refresh_artifact_release_checksums(artifact_dir)

    builder.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True, artifact_dir=artifact_dir)

    assert any("artifact manifest missing publication object" in error for error in errors)


def test_validate_submission_package_rejects_artifact_publication_link_mismatch(tmp_path) -> None:
    """验证正式上传元数据与 artifact manifest 的公开 DOI 必须一致。"""

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
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["publication"]["artifact_release_url"] = "https://doi.org/10.0000/other"
    manifest["publication"]["artifact_release_doi"] = "10.0000/other"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _refresh_artifact_release_checksums(artifact_dir)

    builder.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True, artifact_dir=artifact_dir)

    assert any("artifact_release_url" in error and "publication.artifact_release_url" in error for error in errors)
    assert any("artifact_release_doi" in error and "publication.artifact_release_doi" in error for error in errors)


def test_validate_submission_package_rejects_placeholder_artifact_publication_url(tmp_path) -> None:
    """验证正式上传包拒绝 artifact manifest 中的占位 publication URL。"""

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
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["publication"]["artifact_release_url"] = "https://example.org/iad-risk-artifact"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _refresh_artifact_release_checksums(artifact_dir)

    builder.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True, artifact_dir=artifact_dir)

    assert any("publication.artifact_release_url must not use a placeholder URL" in error for error in errors)


def test_validate_submission_package_rejects_invalid_final_upload_artifact_release(tmp_path) -> None:
    """验证正式上传包会拒绝未通过完整校验的 artifact release。"""

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
    (artifact_dir / "checksums.sha256").unlink()

    builder.build_submission_package(manuscript_root, output_dir, zip_path, final_upload=True)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True, artifact_dir=artifact_dir)

    assert any("artifact release validation failed" in error for error in errors)
    assert any("checksums.sha256" in error for error in errors)


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


def test_validate_submission_package_rejects_preflight_wording_final_upload_cover_letter(tmp_path) -> None:
    """验证正式上传校验器拒绝残留匿名预投稿说明的投稿信。"""

    builder = _load_submission_package_module()
    validator = _load_submission_validator_module()
    manuscript_root = tmp_path / "manuscript"
    output_dir = tmp_path / "submission_package"
    zip_path = tmp_path / "submission_package.zip"
    _write_required_manuscript_files(manuscript_root)
    _write_final_upload_metadata(manuscript_root)
    _write_preflight_wording_final_upload_cover_letter(manuscript_root)

    builder.build_submission_package(manuscript_root, output_dir, zip_path)
    errors = validator.validate_submission_package(output_dir, zip_path, final_upload=True)

    assert any("anonymous draft" in error for error in errors)
    assert any("submission-planning boundaries" in error for error in errors)
    assert any("preparatory scope-fit note" in error for error in errors)
    assert any("replacement instructions" in error for error in errors)


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
