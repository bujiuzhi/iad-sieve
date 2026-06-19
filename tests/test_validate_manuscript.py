"""测试稿件包验证脚本。"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path


def _load_validate_manuscript_module():
    """加载稿件验证脚本模块。

    参数:
        无。

    返回:
        已加载的 Python 模块。
    """

    script_path = Path(__file__).resolve().parents[1] / "manuscript" / "scripts" / "validate_manuscript.py"
    spec = importlib.util.spec_from_file_location("validate_manuscript", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载稿件验证脚本: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_declaration_statements_accepts_complete_declarations() -> None:
    """验证数据可用性、伦理和利益冲突声明内容完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\section*{Data and Code Availability}",
            "The source code, benchmark construction scripts, schema contracts, fixture tests,",
            "and artifact-release guidance are available for audit.",
            "Raw third-party data are not redistributed in Git.",
            "The release records data-processing commands, manifests, checksums, and commit identifiers.",
            r"\section*{Ethics Statement}",
            "This study uses public scholarly metadata and does not involve human participants,",
            "clinical records, private user behavior, or sensitive personal information.",
            r"\section*{Competing Interests}",
            "The competing-interest declaration is not finalized in this anonymous preflight manuscript.",
            "Before final upload, the listed authors must confirm the competing-interest status",
            r"and synchronize the final statement with \path{submission_metadata.yml} and the live submission system.",
        ]
    )

    errors = module.check_declaration_statements(manuscript_text)

    assert errors == []


def test_check_declaration_statements_rejects_vague_declarations() -> None:
    """验证空泛声明缺少数据边界、伦理范围或利益冲突表述时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\section*{Data and Code Availability}",
            "Data are available on request.",
            r"\section*{Ethics Statement}",
            "No ethics approval was needed.",
            r"\section*{Competing Interests}",
            "None.",
        ]
    )

    errors = module.check_declaration_statements(manuscript_text)

    assert any("artifact-release" in error for error in errors)
    assert any("human participants" in error for error in errors)
    assert any("not finalized in this anonymous preflight manuscript" in error for error in errors)
    assert any("live submission system" in error for error in errors)


def test_check_final_upload_information_request_rejects_missing_required_fields() -> None:
    """验证最终上传信息收集表必须覆盖所有外部输入字段。"""

    module = _load_validate_manuscript_module()
    request_text = "# Final Upload Information Request\nTarget journal\n"

    errors = module.check_final_upload_information_request(request_text)

    assert any("Author list" in error for error in errors)
    assert any("Corresponding author" in error for error in errors)
    assert any("Funding statement" in error for error in errors)
    assert any("Author contribution statement" in error for error in errors)
    assert any("Permissions statement" in error for error in errors)
    assert any("Artifact release URL or DOI" in error for error in errors)
    assert any("Live submission-system fields" in error for error in errors)
    assert any("Submission text consistency" in error for error in errors)
    assert any("Submission metadata mapping" in error for error in errors)


def test_check_final_upload_information_request_rejects_missing_credit_roles() -> None:
    """验证最终上传信息收集表必须覆盖 CRediT 作者贡献角色。"""

    module = _load_validate_manuscript_module()
    request_text = "\n".join(
        [
            "# Final Upload Information Request",
            "Submission metadata mapping",
            "After the authors complete this form",
            "`submission_metadata.yml`, `cover_letter.md`, and the live submission system",
            "python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release",
            "Primary `submission_metadata.yml` target",
            "Additional file or system target",
            "`submission`, `target_preparation`, `target_journal_template_bound`, `final_upload_checklist.target_journal_selected`",
            "`authors`, `author_contributions.roles`, `final_upload_checklist.author_metadata_completed`",
            "`author_identity_materials`, `final_upload_checklist.author_biographies_and_photos_ready`",
            "`corresponding_author`, `final_upload_checklist.corresponding_author_completed`",
            "`funding`, `statements`, `final_upload_checklist.funding_statement_text_ready`",
            "`author_contributions`, `final_upload_checklist.contribution_statement_complete`",
            "`permissions`, `final_upload_checklist.permissions_statement_complete`",
            "`generative_ai`, `final_upload_checklist.generative_ai_declaration_complete`",
            "`repository_reference`, `artifact_boundary`, `statements.research_data_statement`",
            "`artifact_boundary`, `final_upload_checklist.artifact_release_prepared_or_linked`",
            "`final_upload_checklist.manuscript_pdf_rebuilt_after_template`",
            "Target journal",
            "Article type",
            "Review mode",
            "Author list",
            "Author order",
            "Author biographies and photographs",
            "author_identity_materials",
            "author_biography_and_photo_required_before_upload",
            "biography_files",
            "photograph_files",
            "author_identity_materials_verified",
            "Biography file path",
            "Photograph file path",
            "Author identity materials verified",
            "Corresponding author",
            "Funding statement",
            "Author contribution statement",
            "Permissions statement",
            "Generative AI declaration",
            "AI tools used in manuscript preparation",
            "Author review and responsibility confirmed",
            "AI tool not listed as author or co-author",
            "Machine-generated figures, images, or artwork included",
            "Competing interests",
            "Ethics statement",
            "Data and code availability statement",
            "Artifact release URL or DOI",
            "Source artifact directory path for preflight",
            "Source artifact preflight command passed",
            "Artifact release directory path for final validation",
            "Artifact release manifest",
            "Live submission-system fields",
            "Final title page",
            "Final-upload checklist",
        ]
    )

    errors = module.check_final_upload_information_request(request_text)

    assert any("CRediT author contribution statement" in error for error in errors)
    assert any("Conceptualization" in error for error in errors)
    assert any("Data curation" in error for error in errors)
    assert any("Writing - original draft" in error for error in errors)
    assert any("Writing - review and editing" in error for error in errors)


def test_check_final_upload_information_request_accepts_complete_request() -> None:
    """验证最终上传信息收集表覆盖所有外部输入字段时可通过检查。"""

    module = _load_validate_manuscript_module()
    request_text = Path("manuscript/final_upload_information_request.md").read_text(encoding="utf-8")

    errors = module.check_final_upload_information_request(request_text)

    assert errors == []


def test_check_final_upload_information_request_rejects_missing_metadata_mapping() -> None:
    """验证最终上传信息表必须说明外部输入如何同步到元数据文件。"""

    module = _load_validate_manuscript_module()
    request_text = Path("manuscript/final_upload_information_request.md").read_text(encoding="utf-8")
    request_text = request_text.replace("## Submission metadata mapping", "## Removed mapping")
    request_text = request_text.replace("Primary `submission_metadata.yml` target", "Primary metadata target")
    request_text = request_text.replace(
        "`repository_reference`, `artifact_boundary`, `statements.research_data_statement`",
        "`repository_reference`",
    )
    request_text = request_text.replace("target_journal_template_bound", "target_journal_template")

    errors = module.check_final_upload_information_request(request_text)

    assert any("Submission metadata mapping" in error for error in errors)
    assert any("Primary `submission_metadata.yml` target" in error for error in errors)
    assert any("statements.research_data_statement" in error for error in errors)
    assert any("target_journal_template_bound" in error for error in errors)


def test_check_final_upload_information_request_rejects_legacy_checklist_names() -> None:
    """验证最终上传信息表不得使用与机器门禁不一致的旧字段名。"""

    module = _load_validate_manuscript_module()
    request_text = Path("manuscript/final_upload_information_request.md").read_text(encoding="utf-8")
    request_text = request_text.replace("target_journal_template_applied", "journal_template_applied")
    request_text = request_text.replace("author_metadata_completed", "author_metadata_complete")
    request_text = request_text.replace("corresponding_author_completed", "corresponding_author_complete")
    request_text = request_text.replace("manuscript_pdf_rebuilt_after_template", "manuscript_pdf_rebuilt_after_metadata")
    request_text = request_text.replace("supplementary_pdf_rebuilt_after_template", "supplementary_pdf_rebuilt_after_metadata")
    request_text = request_text.replace("submission_system_files_verified", "submission_system_fields_reviewed")
    request_text = request_text.replace("first_screen_claim_lockdown_confirmed", "first_screen_claims_reviewed")
    request_text = request_text.replace("artifact_release_prepared_or_linked", "artifact_release_public")

    errors = module.check_final_upload_information_request(request_text)

    assert any("target_journal_template_applied" in error for error in errors)
    assert any("author_metadata_completed" in error for error in errors)
    assert any("corresponding_author_completed" in error for error in errors)
    assert any("manuscript_pdf_rebuilt_after_template" in error for error in errors)
    assert any("submission_system_files_verified" in error for error in errors)
    assert any("first_screen_claim_lockdown_confirmed" in error for error in errors)
    assert any("artifact_release_prepared_or_linked" in error for error in errors)


def test_check_final_upload_information_request_rejects_missing_artifact_dir_validation() -> None:
    """验证最终上传信息表必须要求 artifact release 路径参与最终包校验。"""

    module = _load_validate_manuscript_module()
    request_text = Path("manuscript/final_upload_information_request.md").read_text(encoding="utf-8")
    request_text = request_text.replace(
        "python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release",
        "python manuscript/scripts/validate_submission_package.py --final-upload",
    )
    request_text = request_text.replace("Artifact release directory path for final validation", "Artifact release path")

    errors = module.check_final_upload_information_request(request_text)

    assert any("validate_submission_package.py --final-upload --artifact-dir" in error for error in errors)
    assert any("Artifact release directory path for final validation" in error for error in errors)


def test_check_final_upload_information_request_rejects_missing_source_artifact_preflight() -> None:
    """验证最终上传信息表必须记录 source artifact 预检查路径与结果。"""

    module = _load_validate_manuscript_module()
    request_text = Path("manuscript/final_upload_information_request.md").read_text(encoding="utf-8")
    for marker in [
        "Source artifact directory path for preflight",
        "Source artifact preflight command passed",
    ]:
        request_text = request_text.replace(marker, "")

    errors = module.check_final_upload_information_request(request_text)

    assert any("Source artifact directory path for preflight" in error for error in errors)
    assert any("Source artifact preflight command passed" in error for error in errors)


def test_check_final_upload_information_request_rejects_missing_text_consistency() -> None:
    """验证最终上传信息表必须要求投稿系统首屏文本与源文件一致。"""

    module = _load_validate_manuscript_module()
    request_text = Path("manuscript/final_upload_information_request.md").read_text(encoding="utf-8")
    request_text = request_text.replace("Submission text consistency", "Removed text checks")
    request_text = request_text.replace("Title source checked against `main.tex`", "Title source checked")
    request_text = request_text.replace("Keywords copied exactly from `keywords.md`", "Keywords copied")
    request_text = request_text.replace("Highlights copied exactly from `highlights.md`", "Highlights copied")

    errors = module.check_final_upload_information_request(request_text)

    assert any("Submission text consistency" in error for error in errors)
    assert any("Title source checked against `main.tex`" in error for error in errors)
    assert any("Keywords copied exactly from `keywords.md`" in error for error in errors)
    assert any("Highlights copied exactly from `highlights.md`" in error for error in errors)


def test_final_upload_request_checklist_fields_track_metadata_true_fields() -> None:
    """验证最终上传信息表字段从元数据最终上传门禁派生。"""

    module = _load_validate_manuscript_module()

    expected_fields = [
        field_name
        for field_name in module.FINAL_UPLOAD_TRUE_FIELDS
        if field_name not in module.FINAL_UPLOAD_REQUEST_EXCLUDED_TRUE_FIELDS
    ]

    assert module.FINAL_UPLOAD_REQUEST_CHECKLIST_FIELDS == expected_fields
    assert "target_journal_template_bound" not in module.FINAL_UPLOAD_REQUEST_CHECKLIST_FIELDS


def test_check_data_code_availability_boundary_accepts_complete_boundary() -> None:
    """验证数据与代码可用性边界完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\section*{Data and Code Availability}",
            r"The source lives under \path{src/iad_sieve}.",
            r"The package is configured in \path{pyproject.toml}.",
            r"The package exposes \texttt{iad-sieve = iad\_sieve.cli:main}.",
            r"Reviewers can run \texttt{python -m iad\_sieve.cli --help}.",
            "The help command verifies command discovery.",
            "The full data and code availability boundary table is reported in the supplementary material.",
            "The repository includes source code and CLI entry points.",
            "The repository includes small public fixtures.",
            "The repository includes schema contracts.",
            "The repository includes data-processing commands.",
            "These files are version-controlled in Git.",
            "The repository excludes raw third-party source files.",
            "The repository excludes full prediction files.",
            "The repository excludes model checkpoints.",
            "The repository excludes derived evaluation artifacts.",
            "These files remain outside Git.",
            "They require an external artifact package.",
            r"The external artifact release uses \path{manuscript/scripts/populate_artifact_release.py}.",
            r"Reviewers can run \texttt{--artifact-dir} \path{/path/to/release}.",
            r"Reviewers can run \texttt{--source-dir} \path{/path/to/source-artifacts}.",
            r"Reviewers can run \texttt{--preflight-only}.",
            "The source preflight can detect missing tables, predictions, reports, configurations, or logs early.",
            "The statement says it is not itself result evidence.",
            r"The external artifact release should include \path{source_input_manifest}.",
            r"The external artifact release should include \path{processing_run_log}.",
            "The statement distinguishes L0/L1 code-level reproduction from L2/L3 result-level audit.",
            "The statement names the data-processing path.",
            "The statement says raw data or full experiment outputs are not redistributed.",
            "The statement says full numerical reproduction requires public-source rebuilds or released artifacts.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Data and Code Availability Boundary}",
            r"\label{tab:data-code-availability-boundary}",
            "Data and code availability boundary.",
            "Source code and CLI entry points",
            "Small public fixtures and schema contracts",
            "Raw third-party source files",
            "Full prediction files and model checkpoints",
            "Derived evaluation artifacts",
            "L0/L1 code-level reproduction",
            "L2/L3 result-level audit",
            "source input manifests",
            "processing run logs",
            "prediction files, threshold logs, manifests, checksums, and commit identifiers",
            "raw third-party data remain governed by original provider licenses",
            "full numerical reproduction requires public-source rebuilds or released artifacts",
        ]
    )

    errors = module.check_data_code_availability_boundary(manuscript_text, supplementary_text)

    assert errors == []


def test_check_cli_entrypoint_contract_accepts_source_contract() -> None:
    """验证可安装 CLI 入口在 pyproject 和源码中一致时可通过检查。"""

    module = _load_validate_manuscript_module()
    pyproject_text = "\n".join(
        [
            "[project.scripts]",
            'iad-sieve = "iad_sieve.cli:main"',
            "[tool.setuptools.packages.find]",
            'where = ["src"]',
        ]
    )
    cli_text = "\n".join(
        [
            "import argparse",
            "def build_parser() -> argparse.ArgumentParser:",
            '    return argparse.ArgumentParser(prog="python -m iad_sieve.cli")',
            "def main(argv: list[str] | None = None) -> int:",
            "    args = parser.parse_args(argv)",
            "    args.func(args)",
        ]
    )

    errors = module.check_cli_entrypoint_contract(pyproject_text, cli_text)

    assert errors == []


def test_check_cli_entrypoint_contract_rejects_missing_console_script() -> None:
    """验证缺少 console script 或 CLI main 入口时会被拒绝。"""

    module = _load_validate_manuscript_module()
    pyproject_text = "[tool.setuptools.packages.find]\n"
    cli_text = "import argparse\n"

    errors = module.check_cli_entrypoint_contract(pyproject_text, cli_text)

    assert any("[project.scripts]" in error for error in errors)
    assert any("iad-sieve" in error for error in errors)
    assert any("def main" in error for error in errors)


def test_check_data_code_availability_boundary_rejects_missing_artifact_boundary() -> None:
    """验证数据可用性声明缺少 artifact 边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\section*{Data and Code Availability} Data are available on request."

    errors = module.check_data_code_availability_boundary(manuscript_text)

    assert any("data-code-availability-boundary" in error for error in errors)
    assert any("pyproject.toml" in error for error in errors)
    assert any("Full prediction files and model checkpoints" in error for error in errors)


def test_check_reproduction_levels_boundary_accepts_supplementary_table() -> None:
    """验证复现层级表迁入补充材料后仍可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Artifact Reproduction Protocol}",
            "The full reproduction-level table is reported in the supplementary material.",
            "L0 code check and L1 fixture rebuild verify executable contracts.",
            "These checks do not reproduce the Open-v2 numerical table.",
            "L2 public-source rebuild requires independently obtained public raw files.",
            r"The release includes \path{source_input_manifest}.",
            r"The release includes \path{processing_run_log}.",
            "L3 result audit requires released tables, predictions, logs, manifests, checksums, and commit identifiers.",
            "A reviewer who has only the Git repository cannot verify model predictions, threshold choices, or row-level Open-v2 numbers from Git alone.",
            "The L2/L3 artifact chain is required.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Reproduction Levels}",
            r"\label{tab:reproduction-levels}",
            "Reproduction levels for auditing the repository and the reported evidence.",
            "L0/L1 levels verify executable code and fixture contracts.",
            "L2/L3 levels are required for result-level numerical audit.",
            "L0 code check",
            "L1 fixture rebuild",
            "L2 public-source rebuild",
            "L3 result audit",
            "Source tree, package environment, and manuscript scripts",
            r"\texttt{tests/fixtures}",
            r"\path{source_input_manifest}",
            r"\path{processing_run_log}",
            "Released tables, predictions, logs, manifests, checksums, and commit identifiers",
        ]
    )

    errors = module.check_reproduction_levels_boundary(manuscript_text, supplementary_text)

    assert errors == []


def test_check_reproduction_levels_boundary_rejects_missing_supplementary_table() -> None:
    """验证缺少补充材料复现层级表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Artifact Reproduction Protocol}",
            "The full reproduction-level table is reported in the supplementary material.",
            "L0 code check and L1 fixture rebuild verify executable contracts.",
            "These checks do not reproduce the Open-v2 numerical table.",
            "L2 public-source rebuild requires independently obtained public raw files.",
            r"The release includes \path{source_input_manifest}.",
            r"The release includes \path{processing_run_log}.",
            "L3 result audit requires released tables, predictions, logs, manifests, checksums, and commit identifiers.",
            "A reviewer who has only the Git repository cannot verify model predictions, threshold choices, or row-level Open-v2 numbers from Git alone.",
            "The L2/L3 artifact chain is required.",
        ]
    )

    errors = module.check_reproduction_levels_boundary(manuscript_text, "")

    assert any("tab:reproduction-levels" in error for error in errors)
    assert any("Reproduction levels for auditing" in error for error in errors)


def test_check_evaluation_protocol_boundary_accepts_supplementary_table() -> None:
    """验证 evaluation protocol 表迁入补充材料后仍可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Experimental Questions}",
            "The full evaluation-protocol table is reported in the supplementary material.",
            "RQ1 tests whether IAD-Risk preserves same-work matching performance on gold identity pairs.",
            "RQ2 tests whether it reduces false merges on silver hard negatives with HNFMR.",
            "RQ3 examines whether the observed behavior is consistent with the proposed risk mechanism through FMR and HNFMR.",
            "RQ4 tests whether results remain interpretable under gold, proxy, and silver label strata through split metrics.",
            "The evidence strength is tied to the label stratum behind each question.",
            "gold, proxy, and silver evidence are not mixed into one undifferentiated score.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Evaluation Protocol Boundary}",
            r"\label{tab:evaluation-protocol}",
            "Evaluation protocol. Each question is tied to a label stratum and a metric.",
            "RQ",
            "Evidence layer",
            "Metric",
            "Interpretation",
            "RQ1",
            "Gold identity pairs",
            "Same-work F1",
            "Duplicate matching ability",
            "RQ2",
            "Silver hard negatives",
            "HNFMR",
            "False-merge safety",
            "RQ3",
            "Mechanism analysis",
            "FMR and HNFMR",
            "Role of risk signals",
            "RQ4",
            "Gold/proxy/silver strata",
            "Split metrics",
            "Provenance-aware robustness",
        ]
    )

    errors = module.check_evaluation_protocol_boundary(manuscript_text, supplementary_text)

    assert errors == []


def test_check_evaluation_protocol_boundary_rejects_missing_supplementary_table() -> None:
    """验证缺少补充材料 evaluation protocol 表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Experimental Questions}",
            "The full evaluation-protocol table is reported in the supplementary material.",
            "RQ1 tests whether IAD-Risk preserves same-work matching performance on gold identity pairs.",
            "RQ2 tests whether it reduces false merges on silver hard negatives with HNFMR.",
            "RQ3 examines whether the observed behavior is consistent with the proposed risk mechanism through FMR and HNFMR.",
            "RQ4 tests whether results remain interpretable under gold, proxy, and silver label strata through split metrics.",
            "The evidence strength is tied to the label stratum behind each question.",
            "gold, proxy, and silver evidence are not mixed into one undifferentiated score.",
        ]
    )

    errors = module.check_evaluation_protocol_boundary(manuscript_text, "")

    assert any("tab:evaluation-protocol" in error for error in errors)
    assert any("Evaluation Protocol Boundary" in error for error in errors)


def test_check_highlights_accepts_five_concise_bullets() -> None:
    """验证 5 条简洁投稿 highlights 可通过检查。"""

    module = _load_validate_manuscript_module()
    highlights_text = "\n".join(
        [
            "# Highlights",
            "",
            "- Identity-agenda confusion causes risky scholarly work merges.",
            "- IAD-Risk separates identity, agenda, and ANI evidence.",
            "- IAD-Bench keeps gold, proxy, and silver labels separate.",
            "- Open-v2 scope-bounded evidence reports zero observed IAD-Risk HNFMR.",
            "- Cluster-level claims require artifact-backed audits.",
        ]
    )

    errors = module.check_highlights(highlights_text)

    assert errors == []


def test_check_highlights_rejects_too_many_bullets() -> None:
    """验证 highlights 数量过多会被拒绝。"""

    module = _load_validate_manuscript_module()
    highlights_text = "\n".join(f"- Highlight {index}" for index in range(7))

    errors = module.check_highlights(highlights_text)

    assert any("expected 3 to 5" in error for error in errors)


def test_check_highlights_rejects_long_bullet() -> None:
    """验证过长的 highlight 会被拒绝。"""

    module = _load_validate_manuscript_module()
    long_bullet = (
        "- This highlight is intentionally too long because it keeps adding extra words beyond "
        "the concise submission limit enforced by the validation script and continues with "
        "additional unnecessary explanatory wording."
    )

    errors = module.check_highlights(long_bullet)

    assert any("highlight is too long" in error for error in errors)
    assert any("exceeds 85 characters" in error for error in errors)


def test_check_highlights_rejects_unscoped_hnfmr_numbers() -> None:
    """验证含 HNFMR 数字的 highlight 必须说明证据范围。"""

    module = _load_validate_manuscript_module()
    highlights_text = "\n".join(
        [
            "# Highlights",
            "",
            "- Identity-agenda confusion causes risky scholarly work merges.",
            "- IAD-Risk separates identity, agenda, and ANI evidence.",
            "- IAD-Bench keeps gold, proxy, and silver labels separate.",
            "- Baselines show HNFMR 0.790--0.999; IAD-Risk HNFMR=0.000.",
            "- Fixtures and artifact rules support reproducible review.",
        ]
    )

    errors = module.check_highlights(highlights_text)

    assert any("HNFMR highlight must mention Open-v2" in error for error in errors)
    assert any("scope" in error for error in errors)


def test_check_highlights_rejects_missing_cluster_artifact_boundary() -> None:
    """验证 highlights 必须包含 cluster-level artifact 边界。"""

    module = _load_validate_manuscript_module()
    highlights_text = "\n".join(
        [
            "# Highlights",
            "",
            "- Identity-agenda confusion causes risky scholarly work merges.",
            "- IAD-Risk separates identity, agenda, and ANI evidence.",
            "- IAD-Bench keeps gold, proxy, and silver labels separate.",
            "- Open-v2 scope-bounded evidence reports zero observed IAD-Risk HNFMR.",
            "- Fixtures and artifact rules support reproducible review.",
        ]
    )

    errors = module.check_highlights(highlights_text)

    assert any("cluster-level claims" in error for error in errors)
    assert any("artifact-backed audits" in error for error in errors)


def test_check_keywords_accepts_semicolon_separated_terms() -> None:
    """验证 1 到 7 个分号分隔关键词可通过检查。"""

    module = _load_validate_manuscript_module()
    keywords_text = (
        "# Keywords\n\n"
        "scholarly entity matching; work deduplication; identity-agenda disentanglement; "
        "hard-negative false-merge rate; false-merge risk; provenance-aware evaluation; "
        "scientific document representation"
    )

    errors = module.check_keywords(keywords_text)

    assert errors == []


def test_check_keywords_rejects_too_many_terms() -> None:
    """验证关键词数量超过候选期刊上限会被拒绝。"""

    module = _load_validate_manuscript_module()
    keywords_text = "# Keywords\n\n" + "; ".join(f"keyword {index}" for index in range(8))

    errors = module.check_keywords(keywords_text)

    assert any("expected 1 to 7" in error for error in errors)


def test_check_keywords_rejects_missing_hard_negative_metric() -> None:
    """验证关键词必须包含核心 HNFMR 指标名称。"""

    module = _load_validate_manuscript_module()
    keywords_text = (
        "# Keywords\n\n"
        "scholarly entity matching; work deduplication; identity-agenda disentanglement; "
        "false-merge risk; provenance-aware evaluation; scientific document representation"
    )

    errors = module.check_keywords(keywords_text)

    assert any("hard-negative false-merge rate" in error for error in errors)


def test_check_keywords_rejects_long_keyword() -> None:
    """验证过长关键词会被拒绝。"""

    module = _load_validate_manuscript_module()
    keywords_text = (
        "# Keywords\n\n"
        "scholarly entity matching; work deduplication; identity agenda disentanglement for scholarly records; "
        "false-merge risk; provenance-aware evaluation"
    )

    errors = module.check_keywords(keywords_text)

    assert any("keyword is too long" in error for error in errors)


def test_check_elsevier_draft_source_accepts_current_generated_text() -> None:
    """验证Elsevier预转换源与主稿和关键词一致时可通过。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"""
\documentclass[11pt]{article}
\title{IAD-Risk: Test Title}
\author{Anonymous Authors}
\begin{document}
\maketitle
\begin{abstract}
This abstract states the bounded evidence.
\end{abstract}
\section{Introduction}
The body starts here.
\bibliographystyle{plainnat}
\bibliography{references}
\end{document}
"""
    keywords_text = "# Keywords\n\nentity matching; risk gating\n"
    builder = module.load_elsevier_draft_builder()
    generated_text = builder.build_elsevier_latex(manuscript_text, ["entity matching", "risk gating"])

    errors = module.check_elsevier_draft_source(manuscript_text, keywords_text, generated_text)

    assert errors == []


def test_check_elsevier_draft_source_rejects_stale_text() -> None:
    """验证Elsevier预转换源与当前主稿不一致时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"""
\title{IAD-Risk}
\begin{abstract}
Abstract text.
\end{abstract}
\section{Introduction}
Body.
\bibliographystyle{plainnat}
\bibliography{references}
"""
    keywords_text = "# Keywords\n\nentity matching\n"

    errors = module.check_elsevier_draft_source(manuscript_text, keywords_text, "stale source")

    assert any("stale" in error for error in errors)


def test_check_abstract_length_accepts_abstract_within_limit() -> None:
    """验证摘要不超过 250 词时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\begin{abstract}" + " ".join(["evidence"] * 250) + r"\end{abstract}"

    errors = module.check_abstract_length(manuscript_text)

    assert errors == []


def test_check_abstract_length_rejects_over_limit_abstract() -> None:
    """验证摘要超过 250 词时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\begin{abstract}" + " ".join(["evidence"] * 251) + r"\end{abstract}"

    errors = module.check_abstract_length(manuscript_text)

    assert any("expected at most 250" in error for error in errors)


def test_check_abstract_cluster_overclaim_accepts_pair_stage_boundary() -> None:
    """验证摘要中的 pair-stage 聚类前边界表述可通过检查。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_abstract_cluster_overclaim", None)
    assert callable(checker)
    manuscript_text = (
        r"\begin{abstract}"
        "IAD-Risk uses false-merge risk gating to block risky automatic pair merges before clustering. "
        "The manuscript keeps pair-level quality claims separated from cluster-level quality claims. "
        "Cluster-level quality claims remain conditional on cluster artifacts."
        r"\end{abstract}"
    )

    errors = checker(manuscript_text)

    assert errors == []


def test_check_abstract_cluster_overclaim_rejects_cluster_prevention_claim() -> None:
    """验证摘要不得把 pair-level 风险控制写成 cluster-level 防止声明。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_abstract_cluster_overclaim", None)
    assert callable(checker)
    manuscript_text = (
        r"\begin{abstract}"
        "False-merge risk gating prevents agenda-level hard negatives from entering automatic merge clusters."
        r"\end{abstract}"
    )

    errors = checker(manuscript_text)

    assert any("unsupported abstract cluster-level claim" in error for error in errors)
    assert any("automatic merge clusters" in error for error in errors)


def test_check_abstract_cluster_overclaim_rejects_missing_pair_level_boundary() -> None:
    """验证摘要结论必须说明 pair-level 与 cluster artifact 边界。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_abstract_cluster_overclaim", None)
    assert callable(checker)
    manuscript_text = (
        r"\begin{abstract}"
        "IAD-Risk uses false-merge risk gating to block risky automatic pair merges before clustering. "
        "The results support a conservative conclusion: identity-agenda disentanglement is a practical "
        "mechanism for safer scholarly deduplication."
        r"\end{abstract}"
    )

    errors = checker(manuscript_text)

    assert any("abstract missing pair-level claim boundary" in error for error in errors)
    assert any("cluster artifacts" in error for error in errors)


def test_check_result_claim_boundary_accepts_audited_result_table() -> None:
    """验证主结果表具备审计边界时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Claim-Evidence Boundary for Result Interpretation}",
            r"\subsection{Result Audit Trail}",
            "The full claim-evidence boundary table is reported in the supplementary material.",
            "The identity-agenda confusion is supported only as a false-merge pathway.",
            "IAD-Risk support is bounded to the reported Open-v2 setting.",
            "IAD-Bench is a provenance-aware evaluation contract.",
            "The repository-level reproduction does not by itself prove full numerical results.",
            "The complete row-family artifact crosswalk is reported in the supplementary material.",
            r"\path{open_v2_main_results}",
            r"\path{iad_bench_split_summary}",
            r"\path{representation_baseline_scores}",
            r"\path{supervised_baseline_predictions}",
            r"\path{iad_risk_predictions}",
            r"\path{threshold_selection_logs}",
            r"\path{source_input_manifest}",
            r"\path{processing_run_log}",
            r"\path{bootstrap_intervals}",
            r"\path{ablation_suite}",
            r"\path{manual_validation_slice}",
            r"\path{threshold_sensitivity_grid}",
            "Each row uses a prediction or score file, metric summary, and checksum or manifest.",
            "Each row records per-row denominator counts.",
            "Each row records the per-row threshold source.",
            "Each row records the scope label used in the main table.",
            "Each row records automatic merge count.",
            "Each row records block count.",
            "Each row records defer count.",
            "Each row records automatic merge coverage.",
            "Each row records defer rate.",
            "Each row records capacity-normalized review load.",
            "Prediction JSONL artifacts expose pair/document IDs.",
            "Prediction JSONL artifacts expose score or probability fields.",
            "Threshold logs expose threshold name.",
            "Threshold logs expose selection split.",
            "Threshold logs expose selection metric.",
            "Rebuild provenance exposes public input provenance.",
            "Rebuild provenance exposes code commits.",
            "Rebuild provenance exposes output paths.",
            "Rebuild provenance exposes exit status.",
            "External artifacts require artifact-level and manuscript-package validation.",
            "The source artifact directory contains the files required by the release manifest.",
            "The preflight returns without writing release files.",
            "The preflight is not itself result evidence.",
            r"\path{manuscript/scripts/validate_artifact_release.py}",
            r"\path{manuscript/scripts/validate_submission_package.py}",
            r"\texttt{--final-upload --artifact-dir /path/to/release}",
            "The release and manuscript package refer to the same source commit.",
            "The release should not be used to support the Open-v2 numerical table when validation fails.",
            "The evidence does not support a broad method-ranking claim.",
            r"\label{tab:openv2-results}",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Artifact Package Requirements}",
            r"\section{Claim-Evidence Matrix}",
            r"\label{tab:claim-evidence-boundary-main}",
            "Claim-evidence boundary used to interpret the reported results.",
            "Identity-agenda confusion is a concrete false-merge pathway.",
            "IAD-Risk reduces risky automatic merges in the reported setting.",
            "IAD-Bench supports provenance-aware evaluation.",
            "Repository-level reproduction is possible without committing raw data.",
            r"\label{tab:result-artifact-crosswalk}",
            "Result artifact crosswalk for the Open-v2 evidence snapshot.",
            "The released artifact package includes checksums.sha256.",
            "Reviewers can run python manuscript/scripts/build_artifact_release_skeleton.py.",
            "Reviewers can run with --preflight-only.",
            r"The preflight does not write \path{artifact_population_log.jsonl}.",
            "The source artifact directory is structurally ready for population.",
            "The preflight does not prove row-level schemas.",
            "Reviewers can run python manuscript/scripts/populate_artifact_release.py.",
            "Reviewers can run python manuscript/scripts/finalize_artifact_release.py.",
            "Reviewers can run python manuscript/scripts/validate_artifact_release.py.",
            "The validator checks required result identifiers.",
            "The validator checks conditional claim artifacts.",
            r"The package documents \path{open_v2_main_results}.",
            r"The package documents \path{iad_bench_split_summary}.",
            r"The package documents \path{representation_baseline_scores}.",
            r"The package documents \path{supervised_baseline_predictions}.",
            r"The package documents \path{iad_risk_predictions}.",
            r"The package documents \path{threshold_selection_logs}.",
            r"The package documents \path{bootstrap_intervals}.",
            r"The package documents \path{ablation_suite}.",
            r"The package documents \path{manual_validation_slice}.",
            "The artifact package records per-row denominator counts.",
            "The artifact package records the per-row threshold source.",
            "The artifact package records the scope label used in the main table.",
            "The artifact package records automatic merge count.",
            "The artifact package records block count.",
            "The artifact package records defer count.",
            "The artifact package records automatic merge coverage.",
            "The artifact package records defer rate.",
            "The artifact package records capacity-normalized review load.",
            "Prediction and threshold artifacts are row-auditable.",
            "Prediction artifacts include pair_id.",
            "Representation artifacts include normalized score.",
            "Supervised artifacts include match_probability.",
            "Threshold logs include selection_rule.",
            r"The package documents \path{threshold_sensitivity_grid}.",
            r"The package documents \path{cluster_metric_summary}.",
            r"The package documents \path{cannot_link_audit}.",
            "The package states that cluster-level quality claims require cluster assignments.",
            "The package states that cluster-level quality claims require cannot-link coverage.",
            "The package states that cluster-level quality claims require cluster contamination rate.",
            "The validator checks exclusion of raw third-party data.",
        ]
    )

    errors = module.check_result_claim_boundary(manuscript_text, supplementary_text)

    assert errors == []


def test_check_result_claim_boundary_rejects_result_table_without_audit_trail() -> None:
    """验证主结果表缺少审计边界会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\label{tab:openv2-results}"
    supplementary_text = ""

    errors = module.check_result_claim_boundary(manuscript_text, supplementary_text)

    assert any("Result Audit Trail" in error for error in errors)
    assert any("result-artifact-crosswalk" in error for error in errors)
    assert any("Artifact Package Requirements" in error for error in errors)


def test_check_result_claim_boundary_rejects_missing_row_level_audit_binding() -> None:
    """验证主结果表审计必须绑定每行 denominator、threshold 和 scope。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\label{tab:openv2-results}",
            r"\subsection{Claim-Evidence Boundary for Result Interpretation}",
            r"\subsection{Result Audit Trail}",
            r"\label{tab:result-artifact-crosswalk}",
            r"\path{open_v2_main_results}",
            r"\path{iad_bench_split_summary}",
            r"\path{representation_baseline_scores}",
            r"\path{supervised_baseline_predictions}",
            r"\path{iad_risk_predictions}",
            r"\path{threshold_selection_logs}",
            r"\path{bootstrap_intervals}",
            r"\path{ablation_suite}",
            r"\path{manual_validation_slice}",
            r"\path{threshold_sensitivity_grid}",
            r"\label{tab:claim-evidence-boundary-main}",
            "Each row needs a prediction or score file, metric summary, and checksum or manifest.",
            "The result does not support a broad method-ranking claim.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Artifact Package Requirements}",
            r"\section{Claim-Evidence Matrix}",
            "The released artifact package includes checksums.sha256.",
            "Reviewers can run python manuscript/scripts/build_artifact_release_skeleton.py.",
            "Reviewers can run python manuscript/scripts/populate_artifact_release.py.",
            "Reviewers can run python manuscript/scripts/finalize_artifact_release.py.",
            "Reviewers can run python manuscript/scripts/validate_artifact_release.py.",
            "The validator checks required result identifiers.",
            "The validator checks conditional claim artifacts.",
            r"The package documents \path{threshold_sensitivity_grid}.",
            r"The package documents \path{cluster_metric_summary}.",
            r"The package documents \path{cannot_link_audit}.",
            "The package states that cluster-level quality claims require cluster assignments.",
            "The package states that cluster-level quality claims require cannot-link coverage.",
            "The package states that cluster-level quality claims require cluster contamination rate.",
            "The validator checks exclusion of raw third-party data.",
        ]
    )

    errors = module.check_result_claim_boundary(manuscript_text, supplementary_text)

    assert any("per-row denominator counts" in error for error in errors)
    assert any("per-row threshold source" in error for error in errors)
    assert any("scope label used in the main table" in error for error in errors)
    assert any("automatic merge coverage" in error for error in errors)
    assert any("defer rate" in error for error in errors)
    assert any("capacity-normalized review load" in error for error in errors)


def test_check_result_claim_boundary_rejects_missing_supplementary_row_schema() -> None:
    """验证补充材料必须说明 Open-v2 主结果表行级 schema。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\label{tab:openv2-results}",
            r"\subsection{Claim-Evidence Boundary for Result Interpretation}",
            r"\subsection{Result Audit Trail}",
            r"\label{tab:result-artifact-crosswalk}",
            r"\label{tab:claim-evidence-boundary-main}",
            r"\path{open_v2_main_results}",
            r"\path{iad_bench_split_summary}",
            r"\path{representation_baseline_scores}",
            r"\path{supervised_baseline_predictions}",
            r"\path{iad_risk_predictions}",
            r"\path{threshold_selection_logs}",
            r"\path{bootstrap_intervals}",
            r"\path{ablation_suite}",
            r"\path{manual_validation_slice}",
            r"\path{threshold_sensitivity_grid}",
            "Each row uses a prediction or score file, metric summary, and checksum or manifest.",
            "Each row records per-row denominator counts.",
            "Each row records the per-row threshold source.",
            "Each row records the scope label used in the main table.",
            "Each row records automatic merge count.",
            "Each row records block count.",
            "Each row records defer count.",
            "Each row records automatic merge coverage.",
            "Each row records defer rate.",
            "Each row records capacity-normalized review load.",
            "The evidence does not support a broad method-ranking claim.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Artifact Package Requirements}",
            r"\section{Claim-Evidence Matrix}",
            "The released artifact package includes checksums.sha256.",
            "Reviewers can run python manuscript/scripts/build_artifact_release_skeleton.py.",
            "Reviewers can run python manuscript/scripts/populate_artifact_release.py.",
            "Reviewers can run python manuscript/scripts/finalize_artifact_release.py.",
            "Reviewers can run python manuscript/scripts/validate_artifact_release.py.",
            "The validator checks required result identifiers.",
            "The validator checks conditional claim artifacts.",
            r"The package documents \path{threshold_sensitivity_grid}.",
            r"The package documents \path{cluster_metric_summary}.",
            r"The package documents \path{cannot_link_audit}.",
            "The package states that cluster-level quality claims require cluster assignments.",
            "The package states that cluster-level quality claims require cannot-link coverage.",
            "The package states that cluster-level quality claims require cluster contamination rate.",
            "The validator checks exclusion of raw third-party data.",
        ]
    )

    errors = module.check_result_claim_boundary(manuscript_text, supplementary_text)

    assert any("open_v2_main_results" in error for error in errors)
    assert any("per-row denominator counts" in error for error in errors)
    assert any("per-row threshold source" in error for error in errors)
    assert any("scope label used in the main table" in error for error in errors)
    assert any("automatic merge coverage" in error for error in errors)
    assert any("defer rate" in error for error in errors)
    assert any("capacity-normalized review load" in error for error in errors)


def test_check_result_claim_boundary_rejects_missing_manuscript_artifact_validation_binding() -> None:
    """验证主稿必须说明 artifact release 与最终投稿包绑定校验。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\label{tab:openv2-results}",
            r"\subsection{Claim-Evidence Boundary for Result Interpretation}",
            r"\subsection{Result Audit Trail}",
            r"\label{tab:result-artifact-crosswalk}",
            r"\path{open_v2_main_results}",
            r"\path{iad_bench_split_summary}",
            r"\path{representation_baseline_scores}",
            r"\path{supervised_baseline_predictions}",
            r"\path{iad_risk_predictions}",
            r"\path{threshold_selection_logs}",
            r"\path{bootstrap_intervals}",
            r"\path{ablation_suite}",
            r"\path{manual_validation_slice}",
            r"\path{threshold_sensitivity_grid}",
            r"\label{tab:claim-evidence-boundary-main}",
            "Each row uses a prediction or score file, metric summary, and checksum or manifest.",
            "Each row records per-row denominator counts.",
            "Each row records the per-row threshold source.",
            "Each row records the scope label used in the main table.",
            "Each row records automatic merge count.",
            "Each row records block count.",
            "Each row records defer count.",
            "Each row records automatic merge coverage.",
            "Each row records defer rate.",
            "Each row records capacity-normalized review load.",
            "Prediction JSONL artifacts expose pair/document IDs.",
            "Prediction JSONL artifacts expose score or probability fields.",
            "Threshold logs expose threshold name.",
            "Threshold logs expose selection split.",
            "Threshold logs expose selection metric.",
            "The evidence does not support a broad method-ranking claim.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Artifact Package Requirements}",
            r"\section{Claim-Evidence Matrix}",
            "The released artifact package includes checksums.sha256.",
            "Reviewers can run python manuscript/scripts/build_artifact_release_skeleton.py.",
            "Reviewers can run python manuscript/scripts/populate_artifact_release.py.",
            "Reviewers can run python manuscript/scripts/finalize_artifact_release.py.",
            "Reviewers can run python manuscript/scripts/validate_artifact_release.py.",
            "The validator checks required result identifiers.",
            "The validator checks conditional claim artifacts.",
            r"The package documents \path{open_v2_main_results}.",
            "The artifact package records per-row denominator counts.",
            "The artifact package records the per-row threshold source.",
            "The artifact package records the scope label used in the main table.",
            "The artifact package records automatic merge count.",
            "The artifact package records block count.",
            "The artifact package records defer count.",
            "The artifact package records automatic merge coverage.",
            "The artifact package records defer rate.",
            "The artifact package records capacity-normalized review load.",
            "Prediction and threshold artifacts are row-auditable.",
            "Prediction artifacts include pair_id.",
            "Representation artifacts include normalized score.",
            "Supervised artifacts include match_probability.",
            "Threshold logs include selection_rule.",
            r"The package documents \path{threshold_sensitivity_grid}.",
            r"The package documents \path{cluster_metric_summary}.",
            r"The package documents \path{cannot_link_audit}.",
            "The package states that cluster-level quality claims require cluster assignments.",
            "The package states that cluster-level quality claims require cannot-link coverage.",
            "The package states that cluster-level quality claims require cluster contamination rate.",
            "The validator checks exclusion of raw third-party data.",
        ]
    )

    errors = module.check_result_claim_boundary(manuscript_text, supplementary_text)

    assert any("artifact-level and manuscript-package validation" in error for error in errors)
    assert any("validate_submission_package.py" in error for error in errors)
    assert any("same source commit" in error for error in errors)


def test_check_result_claim_boundary_rejects_missing_artifact_validator_command() -> None:
    """验证结果表审计边界要求补充材料列出 artifact release 校验命令。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\label{tab:openv2-results}",
            r"\subsection{Claim-Evidence Boundary for Result Interpretation}",
            r"\subsection{Result Audit Trail}",
            r"\label{tab:result-artifact-crosswalk}",
            r"\path{open_v2_main_results}",
            r"\path{iad_bench_split_summary}",
            r"\path{representation_baseline_scores}",
            r"\path{supervised_baseline_predictions}",
            r"\path{iad_risk_predictions}",
            r"\path{threshold_selection_logs}",
            r"\path{bootstrap_intervals}",
            r"\path{ablation_suite}",
            r"\path{manual_validation_slice}",
            r"\path{threshold_sensitivity_grid}",
            r"\label{tab:claim-evidence-boundary-main}",
            "Each row needs a prediction or score file, metric summary, and checksum or manifest.",
            "The result does not support a broad method-ranking claim.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Artifact Package Requirements}",
            r"\section{Claim-Evidence Matrix}",
            "The released artifact package includes checksums.sha256.",
        ]
    )

    errors = module.check_result_claim_boundary(manuscript_text, supplementary_text)

    assert any("validate_artifact_release.py" in error for error in errors)
    assert any("required result identifiers" in error for error in errors)


def test_check_result_claim_boundary_rejects_missing_cluster_artifact_boundary() -> None:
    """验证补充材料必须声明 cluster-level 主张所需的 artifact 边界。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\label{tab:openv2-results}",
            r"\subsection{Claim-Evidence Boundary for Result Interpretation}",
            r"\subsection{Result Audit Trail}",
            r"\label{tab:result-artifact-crosswalk}",
            r"\path{open_v2_main_results}",
            r"\path{iad_bench_split_summary}",
            r"\path{representation_baseline_scores}",
            r"\path{supervised_baseline_predictions}",
            r"\path{iad_risk_predictions}",
            r"\path{threshold_selection_logs}",
            r"\path{bootstrap_intervals}",
            r"\path{ablation_suite}",
            r"\path{manual_validation_slice}",
            r"\path{threshold_sensitivity_grid}",
            r"\label{tab:claim-evidence-boundary-main}",
            "Each row needs a prediction or score file, metric summary, and checksum or manifest.",
            "The result does not support a broad method-ranking claim.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Artifact Package Requirements}",
            r"\section{Claim-Evidence Matrix}",
            "The released artifact package includes checksums.sha256.",
            "Reviewers can run python manuscript/scripts/build_artifact_release_skeleton.py.",
            "Reviewers can run python manuscript/scripts/populate_artifact_release.py.",
            "Reviewers can run python manuscript/scripts/finalize_artifact_release.py.",
            "Reviewers can run python manuscript/scripts/validate_artifact_release.py.",
            "The validator checks required result identifiers.",
            "The validator checks conditional claim artifacts.",
            r"The package documents \path{threshold_sensitivity_grid}.",
            "The validator checks exclusion of raw third-party data.",
        ]
    )

    errors = module.check_result_claim_boundary(manuscript_text, supplementary_text)

    assert any("cluster_metric_summary" in error for error in errors)
    assert any("cannot_link_audit" in error for error in errors)
    assert any("cluster-level quality claims" in error for error in errors)


def test_check_contribution_evidence_summary_accepts_complete_summary() -> None:
    """验证贡献、证据和边界对齐完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\label{tab:contribution-evidence-summary}",
            "Contribution-evidence summary",
            "Identity-agenda confusion as a scholarly deduplication failure mode.",
            "IAD-Bench as a provenance-aware pair contract.",
            "IAD-Risk as a risk-aware merge mechanism.",
            "The paper reports hard-negative false-merge rate.",
            "Gold, proxy, silver, and manual-validation layers are separated.",
            "The evaluation uses a shared Open-v2 pair schema.",
            "It marks row-scope differences between full-scope baselines and held-out IAD-Risk rows.",
            "The result includes same-work F1=0.980 and zero observed HNFMR.",
            "The manuscript makes not a broad method-ranking claim.",
        ]
    )

    errors = module.check_contribution_evidence_summary(manuscript_text)

    assert errors == []


def test_check_contribution_evidence_summary_rejects_missing_boundary() -> None:
    """验证贡献表缺少证据边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\label{tab:contribution-evidence-summary}"

    errors = module.check_contribution_evidence_summary(manuscript_text)

    assert any("IAD-Risk as a risk-aware merge mechanism" in error for error in errors)
    assert any("shared Open-v2 pair schema" in error for error in errors)
    assert any("row-scope differences" in error for error in errors)
    assert any("not a broad method-ranking claim" in error for error in errors)


def test_check_motivating_failure_case_accepts_complete_example() -> None:
    """验证引言中包含具体身份-议题混淆失败案例时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Motivating Failure Case}",
            r"\label{tab:motivating-failure-case}",
            "The pair shares the same task or benchmark.",
            "The records make a different contribution.",
            "A representation model may assign high semantic similarity.",
            "The merge would be an unsafe automatic merge.",
            "A safe decision needs same-work identity evidence.",
            "The section states that agenda relatedness is not identity evidence.",
            "The table is an illustrative failure case, not a prevalence estimate.",
            "The example motivates HNFMR.",
        ]
    )

    errors = module.check_motivating_failure_case(manuscript_text)

    assert errors == []


def test_check_motivating_failure_case_rejects_missing_example_boundary() -> None:
    """验证失败案例缺少边界说明时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Motivating Failure Case}"

    errors = module.check_motivating_failure_case(manuscript_text)

    assert any("same task or benchmark" in error for error in errors)
    assert any("illustrative failure case, not a prevalence estimate" in error for error in errors)


def test_check_openv2_benchmark_composition_accepts_complete_composition() -> None:
    """验证 Open-v2 组成表包含数量、用途和边界时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\label{tab:openv2-composition}",
            "Open-v2 benchmark composition",
            "The table reports 415 gold pairs, 10,000 silver hard negatives, and 10,415 total pairs.",
            "The combined scope covers 1,737 documents.",
            "DeepMatcher gold identity Measures same-work matching ability.",
            "OpenAlex and OpenCitations silver hard negatives Stresses agenda-level false-merge behavior.",
            "The silver hard negatives are not human non-identity gold.",
            "The boundary states broader source-heldout claims require additional artifacts.",
        ]
    )

    errors = module.check_openv2_benchmark_composition(manuscript_text)

    assert errors == []


def test_check_openv2_benchmark_composition_rejects_missing_counts() -> None:
    """验证 Open-v2 组成表缺少关键数量和证据边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\label{tab:openv2-composition}"

    errors = module.check_openv2_benchmark_composition(manuscript_text)

    assert any("10,000" in error for error in errors)
    assert any("not human non-identity gold" in error for error in errors)


def test_check_iad_bench_document_schema_contract_accepts_complete_contract() -> None:
    """验证 IAD-Bench document schema 字段契约完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Document Schema Contract}",
            "The full document schema table is reported in the supplementary material.",
            r"\path{document_id}",
            r"\path{source_dataset}",
            r"\path{title}",
            r"\path{abstract}",
            r"\path{authors}",
            r"\path{year}",
            r"\path{venue}",
            r"\path{doi}",
            r"\path{arxiv_id}",
            r"\path{openalex_work_id}",
            r"\path{topics}",
            r"\path{references}",
            "Missing values are represented by empty strings, empty arrays, or null values.",
            "The schema can be audited without redistributing raw third-party files.",
        ]
    )

    errors = module.check_iad_bench_document_schema_contract(manuscript_text)

    assert errors == []


def test_check_iad_bench_document_schema_contract_rejects_missing_fields() -> None:
    """验证 IAD-Bench document schema 缺少核心字段时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Document Schema Contract}"

    errors = module.check_iad_bench_document_schema_contract(manuscript_text)

    assert any("full document schema table" in error for error in errors)
    assert any("openalex_work_id" in error for error in errors)
    assert any("raw third-party files" in error for error in errors)


def test_check_iad_bench_pair_schema_contract_accepts_complete_contract() -> None:
    """验证 IAD-Bench pair schema 字段契约完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Pair Schema Contract}",
            "The full pair schema table is reported in the supplementary material.",
            r"\path{pair_id}",
            r"\path{source_document_id}",
            r"\path{target_document_id}",
            r"\path{relation_label}",
            r"\path{expected_label}",
            r"\path{expected_agenda_label}",
            r"\path{label_source}",
            r"\path{label_strength}",
            r"\path{label_provenance}",
            r"\path{split}",
            r"\path{hard_negative_level}",
            "The schema separates the binary same-work target from agenda relatedness.",
            "The schema identifies agenda-level hard negatives for HNFMR.",
        ]
    )

    errors = module.check_iad_bench_pair_schema_contract(manuscript_text)

    assert errors == []


def test_check_iad_bench_pair_schema_contract_rejects_missing_fields() -> None:
    """验证 IAD-Bench pair schema 缺少核心审计字段时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Pair Schema Contract}"

    errors = module.check_iad_bench_pair_schema_contract(manuscript_text)

    assert any("full pair schema table" in error for error in errors)
    assert any("label_provenance" in error for error in errors)
    assert any("hard_negative_level" in error for error in errors)


def test_check_iad_bench_supplementary_schema_tables_accepts_complete_tables() -> None:
    """验证补充材料包含完整 IAD-Bench schema 表时可通过检查。"""

    module = _load_validate_manuscript_module()
    supplementary_text = "\n".join(
        [
            r"\section{IAD-Bench Schema Contracts}",
            r"\label{tab:iad-bench-document-schema}",
            r"\label{tab:iad-bench-pair-schema}",
            "Record identity, Text and authorship, Bibliographic metadata, and Agenda context are listed.",
            r"\texttt{document\_id}",
            r"\texttt{openalex\_work\_id}",
            r"\texttt{references}",
            "Pair identity, Relation targets, Evidence source, and Evaluation control are listed.",
            r"\texttt{pair\_id}",
            r"\texttt{expected\_agenda\_label}",
            r"\texttt{hard\_negative\_level}",
            "Evaluation control identifies agenda-level hard negatives for HNFMR.",
        ]
    )

    errors = module.check_iad_bench_supplementary_schema_tables(supplementary_text)

    assert errors == []


def test_check_iad_bench_supplementary_schema_tables_rejects_missing_table_labels() -> None:
    """验证补充材料缺少 IAD-Bench schema 表标签时会被拒绝。"""

    module = _load_validate_manuscript_module()
    supplementary_text = r"\section{IAD-Bench Schema Contracts}"

    errors = module.check_iad_bench_supplementary_schema_tables(supplementary_text)

    assert any("iad-bench-document-schema" in error for error in errors)
    assert any("iad-bench-pair-schema" in error for error in errors)


def test_check_citation_bibliography_alignment_accepts_matching_entries() -> None:
    """验证 LaTeX 引用 key 与 BibTeX 条目一致时可通过。"""

    module = _load_validate_manuscript_module()
    document_texts = {
        "main manuscript": r"\citep{fellegi1969record,mudgal2018deep} and \citet[see][Section 2]{li2020ditto}.",
        "supplementary material": r"\citeyearpar{cohan2020specter}",
    }
    bibliography_text = "\n".join(
        [
            "@article{fellegi1969record, title={A}, year={1969}}",
            "@inproceedings{mudgal2018deep, title={B}, year={2018}}",
            "@inproceedings{li2020ditto, title={C}, year={2020}}",
            "@inproceedings{cohan2020specter, title={D}, year={2020}}",
        ]
    )

    errors = module.check_citation_bibliography_alignment(document_texts, bibliography_text)

    assert errors == []


def test_check_citation_bibliography_alignment_rejects_missing_duplicate_and_uncited_entries() -> None:
    """验证引用与参考文献不一致时会报告缺失、重复和未引用条目。"""

    module = _load_validate_manuscript_module()
    document_texts = {"main manuscript": r"\citep{fellegi1969record,missing2026}"}
    bibliography_text = "\n".join(
        [
            "@article{fellegi1969record, title={A}, year={1969}}",
            "@article{fellegi1969record, title={Duplicate}, year={1970}}",
            "@article{uncited2024, title={Uncited}, year={2024}}",
        ]
    )

    errors = module.check_citation_bibliography_alignment(document_texts, bibliography_text)

    assert any("duplicate BibTeX keys" in error and "fellegi1969record" in error for error in errors)
    assert any("missing from references.bib" in error and "missing2026" in error for error in errors)
    assert any("uncited entries" in error and "uncited2024" in error for error in errors)


def test_check_bibliography_entry_metadata_accepts_complete_entries() -> None:
    """验证参考文献条目具备核心出版元数据时可通过。"""

    module = _load_validate_manuscript_module()
    bibliography_text = "\n".join(
        [
            "@article{fellegi1969record,",
            "  title = {A Theory for Record Linkage},",
            "  author = {Fellegi, Ivan P. and Sunter, Alan B.},",
            "  journal = {Journal of the American Statistical Association},",
            "  year = {1969}",
            "}",
            "@inproceedings{mudgal2018deep,",
            "  title = {Deep Learning for Entity Matching},",
            "  author = {Mudgal, Sidharth and Li, Han},",
            "  booktitle = {Proceedings of SIGMOD},",
            "  year = {2018}",
            "}",
        ]
    )

    errors = module.check_bibliography_entry_metadata(bibliography_text)

    assert errors == []


def test_check_bibliography_entry_metadata_rejects_missing_core_fields() -> None:
    """验证参考文献条目缺少作者、年份或出版场所时会被拒绝。"""

    module = _load_validate_manuscript_module()
    bibliography_text = "\n".join(
        [
            "@article{missing_author,",
            "  title = {A Reference Without Author},",
            "  journal = {Journal of Testing},",
            "  year = {2026}",
            "}",
            "@inproceedings{missing_year_and_venue,",
            "  title = {A Reference Without Year or Venue},",
            "  author = {Example, Author}",
            "}",
        ]
    )

    errors = module.check_bibliography_entry_metadata(bibliography_text)

    assert any("missing_author" in error and "author" in error for error in errors)
    assert any("missing_year_and_venue" in error and "year" in error for error in errors)
    assert any("missing_year_and_venue" in error and "journal or booktitle" in error for error in errors)


def test_check_latex_cross_references_accepts_defined_labels_and_refs() -> None:
    """验证 LaTeX label 和 ref 在同一源文件内一致时可通过。"""

    module = _load_validate_manuscript_module()
    document_texts = {
        "main manuscript": "\n".join(
            [
                r"Table~\ref{tab:results} and Figure~\ref{fig:pipeline}.",
                r"\label{tab:results}",
                r"\label{fig:pipeline}",
            ]
        ),
        "supplementary material": r"\label{sec:appendix}",
    }

    errors = module.check_latex_cross_references(document_texts)

    assert errors == []


def test_check_latex_cross_references_rejects_duplicate_missing_and_bad_prefixes() -> None:
    """验证重复 label、缺失 ref 目标和不规范前缀会被拒绝。"""

    module = _load_validate_manuscript_module()
    document_texts = {
        "main manuscript": "\n".join(
            [
                r"Table~\ref{tab:missing}.",
                r"\label{results}",
                r"\label{tab:duplicate}",
                r"\label{tab:duplicate}",
            ]
        )
    }

    errors = module.check_latex_cross_references(document_texts)

    assert any("duplicate LaTeX labels" in error and "tab:duplicate" in error for error in errors)
    assert any("approved prefixes" in error and "results" in error for error in errors)
    assert any("missing LaTeX labels" in error and "tab:missing" in error for error in errors)


def test_check_training_objective_masking_accepts_explicit_masked_loss() -> None:
    """验证训练目标显式包含来源掩码和归一化损失时可通过检查。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_training_objective_masking", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\subsection{Training Objective}",
            r"m^w_{ij}",
            r"m^a_{ij}",
            r"m^n_{ij}",
            r"\sum_{(i,j)}",
            r"\sum_{(i,j)}(m^w_{ij}+m^a_{ij}+m^n_{ij})",
            "valid supervision channels",
            "Missing labels therefore do not create negative examples.",
            "A mini-batch with Z=0 is skipped before the optimizer update.",
            "Each reported relation head requires positive mask coverage in the declared training split.",
            "The false-merge risk score is not directly supervised.",
        ]
    )

    errors = checker(manuscript_text)

    assert errors == []


def test_check_training_objective_masking_rejects_unmasked_loss() -> None:
    """验证训练目标缺少来源掩码时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_training_objective_masking", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\subsection{Training Objective}",
            r"\mathcal{L}_{ij} = \lambda_w CE + \lambda_a CE + \lambda_n CE",
            "The model uses provenance-aware masking.",
        ]
    )

    errors = checker(manuscript_text)

    assert any("m^w_{ij}" in error for error in errors)
    assert any("Missing labels" in error for error in errors)
    assert any("Z=0" in error for error in errors)
    assert any("positive mask coverage" in error for error in errors)
    assert any("risk score is not directly supervised" in error for error in errors)


def test_check_method_feature_contract_accepts_supplementary_table() -> None:
    """验证方法特征契约表迁入补充材料后可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Feature and Head Specification}",
            "The full feature and head specification table is reported in the supplementary material.",
            "Transformer distances and title similarity are used with author overlap.",
            "DOI/arXiv/OpenAlex identifier agreement is treated as identity evidence.",
            "The agenda head uses topic overlap and reference Jaccard similarity.",
            "The ANI risk head uses different-identifier conflicts.",
            "The relation heads use provenance-aware masking.",
            "audit metadata remains traceable but is not a training feature.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\label{tab:feature-head-specification}",
            "Feature and head specification for IAD-Risk transformer variants.",
            "Head or stage",
            "Main input fields",
            "Supervision or calculation",
            "Output role",
            "Identity head",
            "Agenda head",
            "ANI risk head",
            "Risk gate",
            "Audit metadata",
            "Transformer distances and title similarity are used with author overlap.",
            "DOI/arXiv/OpenAlex identifier agreement is treated as identity evidence.",
            "The agenda head uses topic overlap and reference Jaccard similarity.",
            "The ANI risk head uses different-identifier conflicts.",
            "The relation heads use provenance-aware masking.",
            "Audit metadata is retained, but it is not a training feature.",
        ]
    )

    errors = module.check_method_feature_contract(manuscript_text, supplementary_text)

    assert errors == []


def test_check_method_feature_contract_rejects_missing_supplementary_table() -> None:
    """验证缺少补充材料方法特征契约表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Feature and Head Specification}",
            "The full feature and head specification table is reported in the supplementary material.",
            "Transformer distances and title similarity are used with author overlap.",
            "DOI/arXiv/OpenAlex identifier agreement is treated as identity evidence.",
            "The agenda head uses topic overlap and reference Jaccard similarity.",
            "The ANI risk head uses different-identifier conflicts.",
            "The relation heads use provenance-aware masking.",
            "audit metadata remains traceable but is not a training feature.",
        ]
    )

    errors = module.check_method_feature_contract(manuscript_text, "")

    assert any("feature-head-specification" in error for error in errors)
    assert any("Feature and head specification" in error for error in errors)


def test_check_risk_score_design_rationale_accepts_supplementary_table() -> None:
    """验证风险分数设计依据表迁入补充材料后可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Risk Score Design Rationale}",
            "The full risk score design rationale table is reported in the supplementary material.",
            r"$p_{\mathrm{risk}}$ is a conservative upper-envelope risk proxy.",
            "The score increases monotonically with agenda-non-identity evidence.",
            "It also increases when agenda evidence is high and identity evidence is weak.",
            "The max operator keeps either direct ANI evidence or indirect agenda-without-identity evidence sufficient to block automatic merging.",
            "The product term is not a calibrated probability unless validated against held-out artifacts.",
            "Threshold transfer must be rechecked under new source distributions.",
            "defer rather than merge",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\label{tab:risk-score-rationale}",
            "Risk score design rationale.",
            "Design element",
            "Design rationale",
            "Boundary",
            r"$p_{\mathrm{ani}}$ term",
            r"$p_{\mathrm{agenda}}(1-p_{\mathrm{work}})$ term",
            "Max operator",
            "Threshold gate",
            "It is not a calibrated probability unless validated against held-out artifacts.",
            "Threshold transfer must be rechecked under new source distributions.",
        ]
    )

    errors = module.check_risk_score_design_rationale(manuscript_text, supplementary_text)

    assert errors == []


def test_check_risk_score_design_rationale_rejects_missing_supplementary_table() -> None:
    """验证缺少补充材料风险分数设计依据表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Risk Score Design Rationale}",
            "The full risk score design rationale table is reported in the supplementary material.",
            r"$p_{\mathrm{risk}}$ is a conservative upper-envelope risk proxy.",
            "The score increases monotonically with agenda-non-identity evidence.",
            "It also increases when agenda evidence is high and identity evidence is weak.",
            "The max operator keeps either direct ANI evidence or indirect agenda-without-identity evidence sufficient to block automatic merging.",
            "The product term is not a calibrated probability unless validated against held-out artifacts.",
            "Threshold transfer must be rechecked under new source distributions.",
            "defer rather than merge",
        ]
    )

    errors = module.check_risk_score_design_rationale(manuscript_text, "")

    assert any("risk-score-rationale" in error for error in errors)
    assert any("Risk score design rationale" in error for error in errors)


def test_check_risk_calibration_overclaims_accepts_negated_calibration_boundary() -> None:
    """验证否定式校准边界表述不会被误判为过度声明。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_risk_calibration_overclaims", None)
    assert checker is not None
    manuscript_text = (
        "The product term is not a calibrated probability unless validated against held-out artifacts. "
        "Threshold transfer must be rechecked under new source distributions."
    )

    errors = checker(manuscript_text)

    assert errors == []


def test_check_risk_calibration_overclaims_rejects_unsupported_calibration_wording() -> None:
    """验证未提供校准证据的风险校准表述会被拒绝。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_risk_calibration_overclaims", None)
    assert checker is not None
    manuscript_text = "This selective decision rule turns deduplication into a risk-calibrated safety problem."

    errors = checker(manuscript_text)

    assert any("unsupported risk calibration wording" in error for error in errors)
    assert any("risk-calibrated" in error for error in errors)


def test_check_method_cluster_overclaims_accepts_coverage_bounded_wording() -> None:
    """验证方法部分可使用受 coverage 限定的 cannot-link 聚类表述。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_method_cluster_overclaims", None)
    assert callable(checker)
    manuscript_text = (
        "The same decision interface also supports constrained union-find clustering, "
        "where cannot-link evidence can block documented conflicts when coverage is available."
    )

    errors = checker(manuscript_text)

    assert errors == []


def test_check_method_cluster_overclaims_rejects_unqualified_prevention_claim() -> None:
    """验证方法部分不得无条件声明 cannot-link 防止传递性误合并。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_method_cluster_overclaims", None)
    assert callable(checker)
    manuscript_text = (
        "The same decision interface also supports constrained union-find clustering, "
        "where cannot-link evidence prevents transitive false merges."
    )

    errors = checker(manuscript_text)

    assert any("unsupported method cluster-level claim" in error for error in errors)
    assert any("prevents transitive false merges" in error for error in errors)


def test_check_operational_net_benefit_boundary_accepts_complete_boundary() -> None:
    """验证方法复杂度和净收益边界完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Operational Complexity and Net Benefit}",
            "The full operational net-benefit matrix is reported in the supplementary material.",
            "IAD-Risk is appropriate when false merges are more costly than additional review.",
            "The additional cost comes from three relation heads and explicit threshold records.",
            "automatic merge coverage must be large enough to reduce reviewer work",
            "Low FMR or HNFMR alone is insufficient for productivity or cost-saving claims",
            "The deferral budget and manual-review capacity should be recorded before deployment.",
            "The method should be interpreted as a conservative safety filter without workload evidence.",
            "Shared thresholds should be selected on validation evidence, not tuned per pair.",
            "The framework is not a universal replacement for simple deduplication pipelines.",
            "net benefit is strongest in high-stakes scholarly indexes",
            "low-risk bulk cleanup",
        ]
    )

    errors = module.check_operational_net_benefit_boundary(manuscript_text)

    assert errors == []


def test_check_operational_net_benefit_boundary_rejects_missing_cost_boundary() -> None:
    """验证方法复杂度说明缺少成本和适用边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Operational Complexity and Net Benefit}"

    errors = module.check_operational_net_benefit_boundary(manuscript_text)

    assert any("operational net-benefit matrix" in error for error in errors)
    assert any("deferral budget" in error for error in errors)
    assert any("productivity or cost-saving claims" in error for error in errors)
    assert any("not a universal replacement" in error for error in errors)


def test_check_version_identifier_policy_accepts_complete_boundary() -> None:
    """验证版本和标识符合并边界完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Version and Identifier Boundary}",
            "The full version and identifier boundary table is reported in the supplementary material.",
            "DOI, arXiv, and OpenAlex identifiers are used as identity cues.",
            "publication-lineage evidence is still required for related records.",
            "identifier agreement supports merge eligibility",
            "identifier conflict creates cannot-link or defer evidence",
            "preprint, conference, and journal versions require explicit handling",
            "version policy must be declared before cluster-level merging",
            "not every related version is automatically the same work",
            "manual adjudication is required for ambiguous version boundaries",
        ]
    )

    errors = module.check_version_identifier_policy(manuscript_text)

    assert errors == []


def test_check_version_identifier_policy_rejects_missing_defer_boundary() -> None:
    """验证版本和标识符合并边界缺少阻断或延迟规则时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Version and Identifier Boundary}"

    errors = module.check_version_identifier_policy(manuscript_text)

    assert any("version and identifier boundary" in error for error in errors)
    assert any("identifier conflict creates cannot-link or defer evidence" in error for error in errors)
    assert any("manual adjudication" in error for error in errors)


def test_check_method_design_supplementary_boundaries_accepts_complete_tables() -> None:
    """验证补充材料保留方法设计边界表时可通过检查。"""

    module = _load_validate_manuscript_module()
    supplementary_text = "\n".join(
        [
            r"\section{Method Design Boundaries}",
            r"\label{tab:operational-net-benefit}",
            r"\label{tab:version-identifier-boundary}",
            "Operational complexity and net-benefit boundary",
            "The net benefit is strongest in high-stakes scholarly indexes.",
            "Thresholds are not tuned per pair.",
            "The table records deferral budget and manual-review capacity.",
            "The method is a conservative safety filter.",
            "It is not a universal replacement.",
            "Version and identifier boundary for merge decisions",
            "identifier agreement supports merge eligibility",
            "identifier conflict creates cannot-link or defer evidence",
            "not every related version is automatically the same work",
            "manual adjudication is required for ambiguous version boundaries",
            "version policy must be declared before cluster-level merging",
        ]
    )

    errors = module.check_method_design_supplementary_boundaries(supplementary_text)

    assert errors == []


def test_check_method_design_supplementary_boundaries_rejects_missing_tables() -> None:
    """验证补充材料缺少方法设计边界表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    supplementary_text = r"\section{Method Design Boundaries}"

    errors = module.check_method_design_supplementary_boundaries(supplementary_text)

    assert any("operational-net-benefit" in error for error in errors)
    assert any("version-identifier-boundary" in error for error in errors)


def test_check_method_pipeline_figure_accepts_complete_figure() -> None:
    """验证 IAD-Risk 方法流程图完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Overview}",
            r"Figure~\ref{fig:iad-risk-pipeline} summarizes the workflow.",
            r"\begin{figure}[H]",
            "Candidate\\\\record pair",
            "Identity and\\\\agenda evidence",
            "Work, agenda,\\\\ANI heads",
            "Risk-aware\\\\merge gate",
            "Merge, block,\\\\or defer",
            r"\caption{IAD-Risk pipeline. The framework separates identity evidence from agenda evidence.}",
            r"\label{fig:iad-risk-pipeline}",
            r"\end{figure}",
        ]
    )

    errors = module.check_method_pipeline_figure(manuscript_text)

    assert errors == []


def test_check_method_pipeline_figure_rejects_missing_visual_contract() -> None:
    """验证 IAD-Risk 方法流程图缺少关键节点时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Overview} The method is described in prose only."

    errors = module.check_method_pipeline_figure(manuscript_text)

    assert any("fig:iad-risk-pipeline" in error for error in errors)
    assert any("Risk-aware" in error for error in errors)


def test_check_scoring_merge_algorithm_accepts_complete_contract() -> None:
    """验证 IAD-Risk 评分和合并算法契约完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Training and Inference Trace}",
            "The implementation keeps training, threshold fixation, inference, and metric export in one auditable trace.",
            "The full training and inference trace table is reported in the supplementary material.",
            "The schema loading preserves pair IDs and split fields.",
            "The supervised fitting uses the masked objective.",
            "The threshold fixation records threshold source, selection split, and selection metric.",
            "The pair scoring writes scores.",
            "The decision emission records merge, block, or defer.",
            "The metric export binds denominators and checksums.",
            r"\subsection{Scoring and Merge Algorithm}",
            "The full scoring and merge algorithm table is reported in the supplementary material.",
            "The executable method follows a fixed scoring and merge order.",
            "IAD-Risk first builds identity, agenda, ANI, and audit fields.",
            "It builds feature groups without using audit metadata as predictors.",
            r"The heads output $p_{\mathrm{work}}$, $p_{\mathrm{agenda}}$, and $p_{\mathrm{ani}}$.",
            r"The derived risk score is $p_{\mathrm{risk}}=\max\{p_{\mathrm{ani}},p_{\mathrm{agenda}}(1-p_{\mathrm{work}})\}$.",
            "The gate uses a cannot-link flag and emits merge, block, or defer.",
            "The artifact rows include decision, row scope, denominators, thresholds, and checksum-bound artifact rows.",
            "The artifact supports same-work F1, FMR, HNFMR, coverage, and defer-rate audits.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\label{tab:training-inference-trace}",
            "Training and inference trace for IAD-Risk.",
            "Phase",
            "Required operation",
            "Auditable output or invariant",
            "Schema loading",
            "Supervised fitting",
            "Threshold fixation",
            "Pair scoring",
            "Decision emission",
            "Metric export",
            "Pair IDs and split fields remain unchanged.",
            "Gold, proxy, and silver labels are not silently converted.",
            "Threshold source, value, selection split, and selection metric.",
            "Prediction rows expose relation scores.",
            "cannot-link status",
            "Metric summaries and checksums bind denominators.",
            r"\label{tab:scoring-merge-algorithm}",
            "Scoring and merge algorithm for IAD-Risk.",
            "Step",
            "Operation",
            "Required inputs or outputs",
            "Audit role",
            "Load a candidate pair and schema metadata",
            "Build feature groups without using audit metadata as predictors",
            "Predict relation heads",
            "Compute derived false-merge risk",
            "Apply the merge gate and cannot-link evidence",
            "Write prediction and metric audit fields",
            "Fixes row identity before scoring",
            "Prevents provenance or split leakage",
            "Emits merge, block, or defer under a fixed operating point",
            "Supports same-work F1, FMR, HNFMR, coverage, and defer-rate audits",
        ]
    )

    errors = module.check_scoring_merge_algorithm(manuscript_text, supplementary_text)

    assert errors == []


def test_check_scoring_merge_algorithm_rejects_missing_execution_order() -> None:
    """验证算法契约缺少风险分数或三态输出时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Scoring and Merge Algorithm}"

    errors = module.check_scoring_merge_algorithm(manuscript_text)

    assert any("fixed scoring and merge order" in error for error in errors)
    assert any("training-inference-trace" in error for error in errors)
    assert any("p_{\\mathrm{risk}}" in error for error in errors)
    assert any("merge, block, or defer" in error for error in errors)


def test_check_design_alternative_boundaries_accepts_supplementary_table() -> None:
    """验证设计替代项表迁入补充材料后可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Design Alternatives and Rejected Shortcuts}",
            "The full design-alternatives table is reported in the supplementary material.",
            "Tune a representation-similarity threshold.",
            "Use one supervised pair classifier.",
            "Use provenance as a model feature.",
            "Always force a binary merge decision.",
            "Select thresholds after test results.",
            "RoBERTa remains a strong baseline.",
            "The paper states broad superiority is not claimed.",
            "Threshold stability needs a released grid and checksums.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\label{tab:design-alternatives}",
            "Design alternatives considered during method design.",
            "Alternative",
            "Why it is insufficient for this failure mode",
            "IAD-Risk design response",
            "Evidence boundary",
            "Tune a representation-similarity threshold.",
            "Use one supervised pair classifier.",
            "Use provenance as a model feature.",
            "Always force a binary merge decision.",
            "Select thresholds after test results.",
            "RoBERTa remains a strong baseline.",
            "The paper states broad superiority is not claimed.",
            "Threshold stability needs a released grid and checksums.",
        ]
    )

    errors = module.check_design_alternative_boundaries(manuscript_text, supplementary_text)

    assert errors == []


def test_check_design_alternative_boundaries_rejects_missing_supplementary_table() -> None:
    """验证缺少补充材料设计替代项表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Design Alternatives and Rejected Shortcuts}",
            "The full design-alternatives table is reported in the supplementary material.",
            "Tune a representation-similarity threshold.",
            "Use one supervised pair classifier.",
            "Use provenance as a model feature.",
            "Always force a binary merge decision.",
            "Select thresholds after test results.",
            "RoBERTa remains a strong baseline.",
            "The paper states broad superiority is not claimed.",
            "Threshold stability needs a released grid and checksums.",
        ]
    )

    errors = module.check_design_alternative_boundaries(manuscript_text, "")

    assert any("design-alternatives" in error for error in errors)
    assert any("Design alternatives considered" in error for error in errors)


def test_check_failure_control_rationale_accepts_supplementary_table() -> None:
    """验证 failure-control 表迁入补充材料后可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Failure-Control Rationale}",
            "The full failure-control rationale table is reported in the supplementary material.",
            "IAD-Risk is a failure-control framework rather than another similarity scorer.",
            "Topically close papers receive high semantic similarity.",
            "Silver metadata is treated as if it were human gold.",
            "Pairwise errors can contaminate clusters through transitivity.",
            "Thresholds can turn a classifier into an unsafe automatic merger.",
            "Proxy labels are over-interpreted.",
            "Threshold transfer should be rechecked under new source distributions.",
            "proxy rows remain non-human evidence even when reproducible.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\label{tab:failure-controls}",
            "Failure-control rationale of IAD-Risk.",
            "Failure pathway",
            "Design response",
            "Remaining boundary",
            "Topically close papers receive high semantic similarity.",
            "Silver metadata is treated as if it were human gold.",
            "Pairwise errors contaminate clusters through transitivity.",
            "Thresholds turn a classifier into an unsafe automatic merger.",
            "Proxy labels are over-interpreted.",
            "Cluster-level guarantees require complete cannot-link coverage.",
        ]
    )

    errors = module.check_failure_control_rationale(manuscript_text, supplementary_text)

    assert errors == []


def test_check_failure_control_rationale_rejects_missing_supplementary_table() -> None:
    """验证缺少补充材料 failure-control 表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Failure-Control Rationale}",
            "The full failure-control rationale table is reported in the supplementary material.",
            "IAD-Risk is a failure-control framework rather than another similarity scorer.",
            "Topically close papers receive high semantic similarity.",
            "Silver metadata is treated as if it were human gold.",
            "Pairwise errors can contaminate clusters through transitivity.",
            "Thresholds can turn a classifier into an unsafe automatic merger.",
            "Proxy labels are over-interpreted.",
            "Threshold transfer should be rechecked under new source distributions.",
            "proxy rows remain non-human evidence even when reproducible.",
        ]
    )

    errors = module.check_failure_control_rationale(manuscript_text, "")

    assert any("failure-controls" in error for error in errors)
    assert any("Failure-control rationale" in error for error in errors)


def test_check_operating_point_disclosure_accepts_supplementary_table() -> None:
    """验证运行点披露表迁入补充材料后可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Operating Point Disclosure}",
            "The full operating-point disclosure table is reported in the supplementary material.",
            "The table reports fixed operating points, not post-hoc best test thresholds.",
            "Representation cosine baselines use a fixed score threshold.",
            "RoBERTa pair classifier uses a pair probability threshold.",
            "IAD-Risk transformer variants use a risk gate.",
            r"The default $\tau_w=\tau_a=\tau_r=0.5$ applies unless overridden.",
            "A score file, metric summary, and threshold entry are required.",
            "A prediction file, metric summary, and model log are required.",
            "A prediction file, model JSON, thresholds, and checksums are required.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Operating Point Disclosure}",
            r"\label{tab:operating-point-disclosure}",
            "Operating point disclosure for the Open-v2 result table.",
            "Row family",
            "Decision field",
            "Operating point source",
            "Audit requirement",
            "Representation cosine baselines",
            "RoBERTa pair classifier",
            "IAD-Risk transformer variants",
            "Score file, metric summary, and threshold entry",
            "Prediction file, model JSON, thresholds, and checksums",
        ]
    )

    errors = module.check_operating_point_disclosure(manuscript_text, supplementary_text)

    assert errors == []


def test_check_operating_point_disclosure_rejects_missing_supplementary_table() -> None:
    """验证缺少补充材料完整运行点表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Operating Point Disclosure}",
            "The full operating-point disclosure table is reported in the supplementary material.",
            "The table reports fixed operating points, not post-hoc best test thresholds.",
            "Representation cosine baselines use a fixed score threshold.",
            "RoBERTa pair classifier uses a pair probability threshold.",
            "IAD-Risk transformer variants use a risk gate.",
            r"The default $\tau_w=\tau_a=\tau_r=0.5$ applies unless overridden.",
            "A score file, metric summary, and threshold entry are required.",
            "A prediction file, metric summary, and model log are required.",
            "A prediction file, model JSON, thresholds, and checksums are required.",
        ]
    )

    errors = module.check_operating_point_disclosure(manuscript_text, "")

    assert any("operating-point-disclosure" in error for error in errors)
    assert any("Operating Point Disclosure" in error for error in errors)


def test_check_selective_decision_coverage_boundary_accepts_supplementary_table() -> None:
    """验证选择性决策覆盖率边界表迁入补充材料后可通过检查。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_selective_decision_coverage_boundary", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\subsection{Selective Decision Coverage Boundary}",
            "The full selective-decision coverage boundary table is reported in the supplementary material.",
            "automatic merge coverage",
            "block rate",
            "defer rate",
            "review load",
            "capacity-normalized review load",
            "same prediction files",
            "A result with low FMR or HNFMR but high deferral is a conservative triage result.",
            "Results must be compared with a predeclared manual-review capacity and deferral budget.",
            "The current manuscript does not claim throughput reduction.",
            "It does not claim all-pair automatic resolution.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Selective Decision Coverage Boundary}",
            r"\label{tab:selective-decision-coverage}",
            "Selective decision coverage boundary.",
            "Quantity",
            "Required artifact source",
            "Interpretation boundary",
            "Automatic merge coverage",
            "Block rate",
            "Defer rate",
            "Review load",
            "Capacity-normalized review load",
        ]
    )

    errors = checker(manuscript_text, supplementary_text)

    assert errors == []


def test_check_selective_decision_coverage_boundary_rejects_missing_supplementary_table() -> None:
    """验证选择性决策缺少补充材料完整表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_selective_decision_coverage_boundary", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\subsection{Selective Decision Coverage Boundary}",
            "The full selective-decision coverage boundary table is reported in the supplementary material.",
            "automatic merge coverage",
            "block rate",
            "defer rate",
            "review load",
            "capacity-normalized review load",
            "same prediction files",
            "A result with low FMR or HNFMR but high deferral is a conservative triage result.",
            "Results must be compared with a predeclared manual-review capacity and deferral budget.",
            "The current manuscript does not claim throughput reduction.",
            "It does not claim all-pair automatic resolution.",
        ]
    )

    errors = checker(manuscript_text, "")

    assert any("tab:selective-decision-coverage" in error for error in errors)
    assert any("Selective Decision Coverage Boundary" in error for error in errors)


def test_check_pair_cluster_evidence_boundary_accepts_supplementary_table() -> None:
    """验证 pair-level 与 cluster-level 证据边界表迁入补充材料后可通过检查。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_pair_cluster_evidence_boundary", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\subsection{Pair-to-Cluster Evidence Boundary}",
            "The full pair-to-cluster evidence boundary table is reported in the supplementary material.",
            "pair-level metrics do not by themselves prove cluster-level deduplication quality.",
            "transitive merge propagation",
            "cannot-link violations",
            "cluster assignments",
            "pair-to-cluster trace files",
            "cluster_metric_summary",
            "cannot_link_audit",
            "cluster contamination rate",
            "does not claim cluster-level contamination is eliminated",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Pair-to-Cluster Evidence Boundary}",
            r"\label{tab:pair-cluster-evidence-boundary}",
            "Pair-to-cluster evidence boundary.",
            "Evidence item",
            "Required artifact source",
            "Interpretation boundary",
            "cluster assignments",
            "cannot-link violations",
            "Cluster metric summary",
            "Pair-to-cluster trace",
            "cluster contamination rate",
        ]
    )

    errors = checker(manuscript_text, supplementary_text)

    assert errors == []


def test_check_pair_cluster_evidence_boundary_rejects_missing_supplementary_table() -> None:
    """验证缺少补充材料完整表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_pair_cluster_evidence_boundary", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\subsection{Pair-to-Cluster Evidence Boundary}",
            "The full pair-to-cluster evidence boundary table is reported in the supplementary material.",
            "pair-level metrics do not by themselves prove cluster-level deduplication quality.",
            "transitive merge propagation",
            "cannot-link violations",
            "cluster assignments",
            "pair-to-cluster trace files",
            "cluster_metric_summary",
            "cannot_link_audit",
            "cluster contamination rate",
            "does not claim cluster-level contamination is eliminated",
        ]
    )

    errors = checker(manuscript_text, "")

    assert any("pair-cluster-evidence-boundary" in error for error in errors)
    assert any("Pair-to-Cluster Evidence Boundary" in error for error in errors)


def test_check_error_taxonomy_accepts_supplementary_table() -> None:
    """验证错误分类表迁入补充材料后仍可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\section{Mechanism and Error Analysis}",
            "The full error taxonomy table is reported in the supplementary material.",
            "The taxonomy includes same task, different contribution pairs.",
            "The taxonomy includes citation-neighborhood neighbors.",
            "The taxonomy includes version or extension boundaries.",
            "The taxonomy includes identifier conflicts.",
            "The taxonomy includes sparse metadata cases.",
            "The taxonomy is diagnostic rather than a measured error distribution.",
            "A stronger package requires per-category annotations and adjudication logs.",
            "The boundary requires human judgment beyond metadata-derived silver evidence.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Error Taxonomy Boundary}",
            r"\label{tab:error-taxonomy}",
            "Error taxonomy for identity-agenda confusion.",
            "Same task, different contribution",
            "Citation-neighborhood neighbor",
            "Version or extension boundary",
            "Identifier conflict",
            "Sparse metadata",
            "Stronger audit evidence",
        ]
    )

    errors = module.check_error_taxonomy(manuscript_text, supplementary_text)

    assert errors == []


def test_check_error_taxonomy_rejects_missing_supplementary_table() -> None:
    """验证错误分类缺少补充材料完整表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\section{Mechanism and Error Analysis}",
            "The full error taxonomy table is reported in the supplementary material.",
            "The taxonomy includes same task, different contribution pairs.",
            "The taxonomy includes citation-neighborhood neighbors.",
            "The taxonomy includes version or extension boundaries.",
            "The taxonomy includes identifier conflicts.",
            "The taxonomy includes sparse metadata cases.",
            "The taxonomy is diagnostic rather than a measured error distribution.",
            "A stronger package requires per-category annotations and adjudication logs.",
            "The boundary requires human judgment beyond metadata-derived silver evidence.",
        ]
    )

    errors = module.check_error_taxonomy(manuscript_text, "")

    assert any("tab:error-taxonomy" in error for error in errors)
    assert any("Error Taxonomy Boundary" in error for error in errors)


def test_check_mechanism_evidence_boundary_accepts_supplementary_table() -> None:
    """验证机制证据边界表迁入补充材料后仍可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\section{Mechanism and Error Analysis}",
            "The full mechanism-evidence boundary table is reported in the supplementary material.",
            "The prose states that topical relatedness creates merge risk only as a targeted claim.",
            "It states that explicit risk gating supports the reported Open-v2 contract.",
            "It states that component-causality claims require ablations.",
            "It states that cluster-level contamination claims require sufficient cannot-link coverage.",
            "It requires cluster-level artifact audits before deployment-level claims.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Mechanism Evidence Boundary}",
            r"\label{tab:mechanism-evidence}",
            "Mechanism evidence and interpretation boundary.",
            "Mechanism question",
            "Current evidence",
            "Interpretation boundary",
            "Does topical relatedness create merge risk?",
            "Does explicit risk gating suppress hard-negative merges?",
            "Is the gain caused by each IAD-Risk component?",
            "Can cluster-level contamination be eliminated?",
        ]
    )

    errors = module.check_mechanism_evidence_boundary(manuscript_text, supplementary_text)

    assert errors == []


def test_check_mechanism_evidence_boundary_rejects_missing_supplementary_table() -> None:
    """验证机制证据缺少补充材料完整表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\section{Mechanism and Error Analysis}",
            "The full mechanism-evidence boundary table is reported in the supplementary material.",
            "The prose states that topical relatedness creates merge risk only as a targeted claim.",
            "It states that explicit risk gating supports the reported Open-v2 contract.",
            "It states that component-causality claims require ablations.",
            "It states that cluster-level contamination claims require sufficient cannot-link coverage.",
            "It requires cluster-level artifact audits before deployment-level claims.",
        ]
    )

    errors = module.check_mechanism_evidence_boundary(manuscript_text, "")

    assert any("tab:mechanism-evidence" in error for error in errors)
    assert any("Mechanism Evidence Boundary" in error for error in errors)


def test_check_validity_threats_accepts_supplementary_matrix() -> None:
    """验证 validity threats 迁入补充材料后仍可通过完整检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\section{Limitations}",
            "This study has five limitations.",
            "pair-level metrics do not by themselves establish cluster-level deployment quality.",
            "The stronger claim requires cluster assignments.",
            "It also requires cannot-link coverage.",
            "It also requires cluster contamination rate.",
            r"\section{Threats to Validity}",
            "The full validity-threats matrix is reported in the supplementary material.",
            "The construct validity is bounded by label strata.",
            "The internal validity is bounded by threshold and split separation.",
            "The external validity is bounded by the current source mix.",
            "The conclusion validity is bounded by the absence of complete causal ablations.",
            "The reproducibility is bounded by source and artifact availability.",
            "The operational validity is bounded by the gap between pair-level decisions and cluster-level deployment.",
            "These safeguards do not turn proxy or silver evidence into human-adjudicated truth.",
            "The full numeric audit requires L2/L3 artifacts.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Validity Threats Boundary}",
            r"\label{tab:validity-threats}",
            "Threats to validity and claim boundaries.",
            "Construct validity",
            "Internal validity",
            "External validity",
            "Conclusion validity",
            "Reproducibility",
            "Operational validity",
            "not turn proxy or silver evidence into human-adjudicated truth",
            "Full numeric audit requires L2/L3 artifacts",
        ]
    )

    errors = module.check_validity_threats(manuscript_text, supplementary_text)

    assert errors == []


def test_check_validity_threats_rejects_limitations_without_cluster_boundary() -> None:
    """验证 Limitations 段落必须声明 pair-level 到 cluster-level 的证据限制。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\section{Limitations}",
            "This study has four limitations.",
            r"\section{Threats to Validity}",
            "The full validity-threats matrix is reported in the supplementary material.",
            "The construct validity is bounded by label strata.",
            "The internal validity is bounded by threshold and split separation.",
            "The external validity is bounded by the current source mix.",
            "The conclusion validity is bounded by the absence of complete causal ablations.",
            "The reproducibility is bounded by source and artifact availability.",
            "The operational validity is bounded by the gap between pair-level decisions and cluster-level deployment.",
            "These safeguards do not turn proxy or silver evidence into human-adjudicated truth.",
            "The full numeric audit requires L2/L3 artifacts.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Validity Threats Boundary}",
            r"\label{tab:validity-threats}",
            "Threats to validity and claim boundaries",
            "Construct validity",
            "Internal validity",
            "External validity",
            "Conclusion validity",
            "Reproducibility",
            "Operational validity",
            "not turn proxy or silver evidence into human-adjudicated truth",
            "Full numeric audit requires L2/L3 artifacts",
        ]
    )

    errors = module.check_validity_threats(manuscript_text, supplementary_text)

    assert any("Limitations" in error for error in errors)
    assert any("pair-level metrics" in error for error in errors)
    assert any("cluster-level deployment quality" in error for error in errors)


def test_check_decision_metric_mapping_accepts_supplementary_table() -> None:
    """验证选择性决策表迁入补充材料后可通过检查。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_decision_metric_mapping", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\subsection{Decision-to-Metric Mapping}",
            "full decision-to-metric mapping table is reported in the supplementary material",
            "automatic merge is the positive decision",
            "block and defer are non-merge decisions",
            "Deferred same-work pairs reduce recall",
            "FMR and HNFMR count only automatic merges among non-identity rows",
            "coverage and defer rate must be reported separately",
            "block suppresses false merges",
            "defer protects against unsafe automatic decisions",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Decision-to-Metric Mapping}",
            r"\label{tab:decision-metric-mapping}",
            "Decision-to-metric mapping for selective merge outputs",
            "Decision output",
            "Metric treatment",
            "Interpretation boundary",
            "Merge",
            "Block",
            "Defer",
        ]
    )

    errors = checker(manuscript_text, supplementary_text)

    assert errors == []


def test_check_decision_metric_mapping_rejects_missing_supplementary_table() -> None:
    """验证缺少补充材料决策映射表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_decision_metric_mapping", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\subsection{Decision-to-Metric Mapping}",
            "full decision-to-metric mapping table is reported in the supplementary material",
            "automatic merge is the positive decision",
            "block and defer are non-merge decisions",
            "Deferred same-work pairs reduce recall",
            "FMR and HNFMR count only automatic merges among non-identity rows",
            "coverage and defer rate must be reported separately",
            "block suppresses false merges",
            "defer protects against unsafe automatic decisions",
        ]
    )

    errors = checker(manuscript_text, "")

    assert any("Decision-to-Metric Mapping" in error for error in errors)
    assert any("tab:decision-metric-mapping" in error for error in errors)


def test_check_metric_formula_boundary_accepts_supplementary_table() -> None:
    """验证评价指标公式表迁入补充材料后可通过检查。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_metric_formula_boundary", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\subsection{Metric Formula Boundary}",
            "TP",
            "FP",
            "FN",
            r"$2TP/(2TP+FP+FN)$",
            "FMR denominator is all non-identity rows in the evaluated scope.",
            "HNFMR denominator is the agenda-level hard-negative subset.",
            "Rows excluded by missing labels are not silently added to denominators.",
            "FMR measures unsafe automatic merges rather than manual-review workload.",
            "HNFMR measures identity-agenda false merges.",
            "The full metric-formula boundary table is reported in the supplementary material.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Metric Formula Boundary}",
            r"\label{tab:metric-formula-boundary}",
            "Metric formula boundary.",
            "Metric",
            "Formula or denominator",
            "Boundary",
            "Same-work F1",
            "FMR",
            "HNFMR",
            "Defer and block decisions on true same-work rows enter FN",
        ]
    )

    errors = checker(manuscript_text, supplementary_text)

    assert errors == []


def test_check_metric_formula_boundary_rejects_missing_supplementary_table() -> None:
    """验证缺少补充材料完整指标公式表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_metric_formula_boundary", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\subsection{Metric Formula Boundary}",
            "TP",
            "FP",
            "FN",
            r"$2TP/(2TP+FP+FN)$",
            "FMR denominator is all non-identity rows in the evaluated scope.",
            "HNFMR denominator is the agenda-level hard-negative subset.",
            "Rows excluded by missing labels are not silently added to denominators.",
            "FMR measures unsafe automatic merges rather than manual-review workload.",
            "HNFMR measures identity-agenda false merges.",
            "The full metric-formula boundary table is reported in the supplementary material.",
        ]
    )

    errors = checker(manuscript_text, "")

    assert any("tab:metric-formula-boundary" in error for error in errors)
    assert any("Metric Formula Boundary" in error for error in errors)


def test_check_threshold_sensitivity_status_accepts_supplementary_table() -> None:
    """验证阈值敏感性状态表迁入补充材料后可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Threshold Sensitivity Evidence Status}",
            "The full threshold-sensitivity evidence status table is reported in the supplementary material.",
            "Threshold stability is treated as an audit requirement.",
            "It is not as an unsupported robustness claim.",
            "A stronger claim requires the same prediction files.",
            "It also requires predefined threshold ranges.",
            "The threshold grid is not reported as primary evidence.",
            "The package needs per-threshold F1, FMR, HNFMR.",
            "The package needs random seeds.",
            "The package needs command logs.",
            "The package needs a manifest.",
            "The package needs checksums.",
            "The manuscript supports fixed-threshold control, not threshold-stable ranking across all operating points.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Threshold Sensitivity Evidence Status}",
            r"\label{tab:threshold-sensitivity-status}",
            "Threshold sensitivity evidence status.",
            "Audit item",
            "Current manuscript status",
            "Required artifact before stronger claim",
            "Fixed operating point",
            "Threshold grid",
            "Metric stability",
            "Artifact manifest",
            "Interpretation boundary",
        ]
    )

    errors = module.check_threshold_sensitivity_status(manuscript_text, supplementary_text)

    assert errors == []


def test_check_threshold_sensitivity_status_rejects_missing_supplementary_table() -> None:
    """验证缺少补充材料完整阈值敏感性表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Threshold Sensitivity Evidence Status}",
            "The full threshold-sensitivity evidence status table is reported in the supplementary material.",
            "Threshold stability is treated as an audit requirement.",
            "It is not as an unsupported robustness claim.",
            "A stronger claim requires the same prediction files.",
            "It also requires predefined threshold ranges.",
            "The threshold grid is not reported as primary evidence.",
            "The package needs per-threshold F1, FMR, HNFMR.",
            "The package needs random seeds.",
            "The package needs command logs.",
            "The package needs a manifest.",
            "The package needs checksums.",
            "The manuscript supports fixed-threshold control, not threshold-stable ranking across all operating points.",
        ]
    )

    errors = module.check_threshold_sensitivity_status(manuscript_text, "")

    assert any("tab:threshold-sensitivity-status" in error for error in errors)
    assert any("Threshold Sensitivity Evidence Status" in error for error in errors)


def test_check_threshold_uncertainty_reporting_accepts_complete_boundary() -> None:
    """验证主稿阈值与不确定性边界完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Threshold Selection and Uncertainty Reporting}",
            "The full threshold and uncertainty reporting protocol is reported in the supplementary material.",
            "The reported system follows a fixed selection protocol and does not choose the best test threshold.",
            "Thresholds are selected from validation evidence.",
            "The default implementation threshold is used as a fixed operating point.",
            "The test split is then used only for final metric reporting.",
            "FMR and HNFMR are reported together.",
            "Stronger claims require prediction files and resampling logs.",
            "The required ablations include no-risk-gate, no-ANI-head, single-space, no-cannot-link, and post-hoc-threshold variants.",
            "Artifacts bind predictions, configs, logs, checksums, and commit identifiers.",
        ]
    )

    errors = module.check_threshold_uncertainty_reporting(manuscript_text)

    assert errors == []


def test_check_threshold_uncertainty_reporting_rejects_missing_artifact_boundary() -> None:
    """验证缺少 artifact 约束时阈值与不确定性边界会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Threshold Selection and Uncertainty Reporting}"

    errors = module.check_threshold_uncertainty_reporting(manuscript_text)

    assert any("prediction files and resampling logs" in error for error in errors)
    assert any("no-risk-gate" in error for error in errors)
    assert any("checksums" in error for error in errors)


def test_check_statistical_interpretation_boundary_accepts_bounded_point_estimates() -> None:
    """验证统计解释边界完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Statistical Interpretation Boundary}",
            "The full statistical interpretation table is reported in the supplementary material.",
            "The reported numbers are point estimates for a fixed evidence snapshot.",
            "They are not statistical superiority estimates.",
            "Confidence intervals, significance tests, and model-ranking statements are intentionally withheld.",
            "The stronger claim needs exact prediction files, resampling logs, random seeds, and checksums.",
            "An HNFMR value states no hard-negative false merge was observed.",
            "It should not be read as proof of zero risk.",
            r"\path{bootstrap_intervals}",
            "Predefined tests, multiplicity handling, input artifacts, and reproducible analysis logs are required.",
            "Same-scope predictions, interval estimates, ablations, and manual-validation slice are required.",
        ]
    )

    errors = module.check_statistical_interpretation_boundary(manuscript_text)

    assert errors == []


def test_check_statistical_interpretation_boundary_rejects_missing_significance_boundary() -> None:
    """验证缺少置信区间和显著性边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Statistical Interpretation Boundary}"

    errors = module.check_statistical_interpretation_boundary(manuscript_text)

    assert any("statistical superiority estimates" in error for error in errors)
    assert any("bootstrap_intervals" in error for error in errors)
    assert any("zero risk" in error for error in errors)


def test_check_ablation_acceptance_boundary_accepts_protocol() -> None:
    """验证主文包含消融验收边界时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Ablation Acceptance Boundary}",
            "The variants use the same pair scope, split field, metric implementation, and predeclared operating-point rule.",
            "The variants are no-risk-gate, no-ANI-head, single-space, no-cannot-link, and post-hoc-threshold.",
            r"The executable summary exposes \texttt{protocol\_variant}.",
            "Each output releases prediction rows, threshold logs, denominator records.",
            "The denominator records cover same-work F1, FMR, and HNFMR.",
            "The release includes checksum-bound configuration files.",
            "Otherwise the result is exploratory diagnostic evidence rather than an accepted ablation.",
            "The post-hoc-threshold row is a diagnostic threshold-sweep control.",
            "It cannot by itself support a component-causality claim.",
        ]
    )

    errors = module.check_ablation_acceptance_boundary(manuscript_text)

    assert errors == []


def test_check_ablation_acceptance_boundary_rejects_missing_protocol() -> None:
    """验证缺少消融验收边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Ablation Acceptance Boundary}"

    errors = module.check_ablation_acceptance_boundary(manuscript_text)

    assert any("no-risk-gate" in error for error in errors)
    assert any("checksum-bound configuration files" in error for error in errors)
    assert any("exploratory diagnostic evidence" in error for error in errors)
    assert any("protocol" in error for error in errors)


def test_check_experiment_reporting_supplementary_boundaries_accepts_complete_tables() -> None:
    """验证补充材料包含迁移后的实验报告边界表时可通过检查。"""

    module = _load_validate_manuscript_module()
    supplementary_text = "\n".join(
        [
            r"\section{Uncertainty and Ablation Requirements}",
            r"\label{tab:threshold-uncertainty-protocol}",
            r"\label{tab:ablation-acceptance-protocol}",
            r"\label{tab:statistical-interpretation-boundary}",
            "Threshold and uncertainty reporting protocol.",
            "Ablation acceptance protocol.",
            "Merge thresholds.",
            "Metric uncertainty.",
            "Risk metrics.",
            "Ablation claims.",
            "Artifact audit.",
            "Required variants.",
            "no-risk-gate, no-ANI-head, single-space, no-cannot-link, and post-hoc-threshold.",
            r"\texttt{protocol\_variant}.",
            "Scope parity.",
            "same pair scope, split field, label stratum, and metric implementation.",
            "Decision trace.",
            "prediction rows, threshold logs, same-work F1/FMR/HNFMR denominators.",
            "Artifact binding.",
            "configuration, command log, random seed when applicable, code commit, manifest entry, and checksum.",
            "Interpretation rule.",
            "changed pair universe, threshold-selection source, prediction schema, or post-hoc threshold selection.",
            "The post-hoc-threshold row is retained as a threshold-overfitting diagnostic.",
            "Statistical interpretation boundary.",
            "Point estimates.",
            "Confidence intervals.",
            "Statistical significance.",
            "Zero HNFMR rows.",
            "Model ranking.",
            r"\path{bootstrap_intervals}",
            "Predefined tests, multiplicity handling, input artifacts, and reproducible analysis logs.",
            "Same-scope predictions, interval estimates, ablations, and manual-validation slice.",
        ]
    )

    errors = module.check_experiment_reporting_supplementary_boundaries(supplementary_text)

    assert errors == []


def test_check_experiment_reporting_supplementary_boundaries_rejects_missing_tables() -> None:
    """验证缺少补充材料实验报告边界表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    supplementary_text = r"\section{Uncertainty and Ablation Requirements}"

    errors = module.check_experiment_reporting_supplementary_boundaries(supplementary_text)

    assert any("threshold-uncertainty-protocol" in error for error in errors)
    assert any("ablation-acceptance-protocol" in error for error in errors)
    assert any("statistical-interpretation-boundary" in error for error in errors)
    assert any("bootstrap_intervals" in error for error in errors)


def test_check_baseline_scope_alignment_accepts_reported_result_scope() -> None:
    """验证 baseline 描述与主结果表范围一致时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Baselines}",
            "The main table reports two scientific representation cosine baselines.",
            "SciNCL cosine and SPECTER2 adapter cosine are representation rows.",
            "RoBERTa pair classification is the supervised pair-classifier baseline.",
            "Other repository baseline utilities are not used as primary manuscript evidence.",
            "They require metric summaries, prediction files, thresholds, and checksums.",
            r"\label{tab:openv2-results}",
        ]
    )

    errors = module.check_baseline_scope_alignment(manuscript_text)

    assert errors == []


def test_check_baseline_scope_alignment_rejects_unreported_primary_baselines() -> None:
    """验证未进入主结果表的 baseline 不得写成已完成主证据。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Baselines}",
            "The completed actual-model baselines include rule-based matching.",
            "The completed set also includes single-space union baselines.",
            r"\label{tab:openv2-results}",
        ]
    )

    errors = module.check_baseline_scope_alignment(manuscript_text)

    assert any("rule-based matching" in error for error in errors)
    assert any("single-space union baselines" in error for error in errors)


def test_check_baseline_inclusion_rationale_accepts_complete_rationale() -> None:
    """验证 baseline 纳入和排除理由完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Baseline Inclusion Rationale}",
            "The complete inclusion matrix is reported in the supplementary material.",
            "The table discusses exact identifier matching.",
            "It also discusses title-normalization rules.",
            "Traditional entity-resolution systems require the same artifacts.",
            "Scientific representation baselines are included as primary evidence.",
            "RoBERTa pair classification is included as a supervised comparator.",
            "Included as primary evidence only when metric summaries, prediction files, threshold records, and checksums are available.",
            "Excluded from primary result table when only utility code or fixture-level checks are available.",
            "The omission is not a claim that omitted baselines were outperformed.",
            "A same-scope baseline matrix is required before broad ranking claims.",
        ]
    )

    errors = module.check_baseline_inclusion_rationale(manuscript_text)

    assert errors == []


def test_check_baseline_inclusion_rationale_rejects_missing_omitted_baseline_boundary() -> None:
    """验证 baseline 纳入理由缺少排除边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Baseline Inclusion Rationale}"

    errors = module.check_baseline_inclusion_rationale(manuscript_text)

    assert any("exact identifier matching" in error for error in errors)
    assert any("supplementary material" in error for error in errors)
    assert any("not a claim that omitted baselines were outperformed" in error for error in errors)


def test_check_baseline_fairness_controls_accepts_complete_controls() -> None:
    """验证 baseline 公平比较控制完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Baseline Fairness Controls}",
            "The full fairness-control matrix is in the supplementary material.",
            "All baselines consume the same IAD-Bench pair records.",
            "Each row uses the same train/dev/test split field when training is required.",
            "Threshold-sensitive rows use validation-selected operating points.",
            "All systems report same-work F1, FMR, and HNFMR from the same metric implementation.",
            "Label source, provenance, and split identifiers are audit fields, not predictive features.",
            "A stricter ranking requires same-scope released prediction files.",
            "The table should not be read as a single comparative ranking.",
        ]
    )

    errors = module.check_baseline_fairness_controls(manuscript_text)

    assert errors == []


def test_check_baseline_fairness_controls_rejects_missing_protocol_markers() -> None:
    """验证 baseline 公平比较缺少关键协议时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Baseline Fairness Controls}"

    errors = module.check_baseline_fairness_controls(manuscript_text)

    assert any("fairness-control matrix" in error for error in errors)
    assert any("same IAD-Bench pair records" in error for error in errors)
    assert any("not predictive features" in error for error in errors)


def test_check_baseline_supplementary_tables_accepts_complete_tables() -> None:
    """验证补充材料包含完整 baseline 审计矩阵时可通过检查。"""

    module = _load_validate_manuscript_module()
    supplementary_text = "\n".join(
        [
            r"\section{Baseline Audit Boundary}",
            r"\label{tab:baseline-inclusion-rationale}",
            r"\label{tab:baseline-fairness-controls}",
            "Exact identifier matching and Title-normalization rules are documented.",
            "Traditional entity-resolution systems require comparable artifacts.",
            "Scientific representation baselines and RoBERTa pair classification are included.",
            "Included as primary evidence only when metric summaries, prediction files, threshold records, and checksums are available.",
            "Excluded from primary result table when only utility code or fixture-level checks are available.",
            "Baselines use the same IAD-Bench pair records.",
            "Rows use the same train/dev/test split field.",
            "Rows use validation-selected operating points.",
            "A stricter ranking requires same-scope released prediction files.",
            "Different scopes should not be read as a single comparative ranking.",
        ]
    )

    errors = module.check_baseline_supplementary_tables(supplementary_text)

    assert errors == []


def test_check_baseline_supplementary_tables_rejects_missing_tables() -> None:
    """验证补充材料缺少 baseline 表格标签时会被拒绝。"""

    module = _load_validate_manuscript_module()
    supplementary_text = r"\section{Baseline Audit Boundary}"

    errors = module.check_baseline_supplementary_tables(supplementary_text)

    assert any("baseline-inclusion-rationale" in error for error in errors)
    assert any("baseline-fairness-controls" in error for error in errors)


def test_check_split_leakage_controls_accepts_supplementary_table() -> None:
    """验证 split 与泄漏控制表迁入补充材料后可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Split and Leakage Controls}",
            "The full split and leakage controls table is reported in the supplementary material.",
            "Training uses only the declared training split.",
            "threshold selection uses validation evidence.",
            "Metadata fields that identify source, provenance, or split are excluded from model features.",
            "Unordered pair leakage guard.",
            "Label-stratum coverage audit.",
            "Source-heldout readiness audit.",
            "Topic-heldout readiness audit.",
            "topic-stability claims.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Split and Leakage Controls}",
            r"\label{tab:split-leakage-controls}",
            "Split and leakage controls used to interpret IAD-Bench results.",
            "Control",
            "Manuscript role",
            "Stronger evidence boundary",
            "Train/dev/test split field",
            "Unordered pair leakage guard",
            "Label-stratum coverage audit",
            "Source-heldout readiness audit",
            "Topic-heldout readiness audit",
            "Cross-topic stability should not be claimed when topic coverage is insufficient.",
        ]
    )

    errors = module.check_split_leakage_controls(manuscript_text, supplementary_text)

    assert errors == []


def test_check_split_leakage_controls_rejects_missing_supplementary_table() -> None:
    """验证缺少补充材料 split 与泄漏控制表时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Split and Leakage Controls}",
            "The full split and leakage controls table is reported in the supplementary material.",
            "Training uses only the declared training split.",
            "threshold selection uses validation evidence.",
            "Metadata fields that identify source, provenance, or split are excluded from model features.",
            "Unordered pair leakage guard.",
            "Label-stratum coverage audit.",
            "Source-heldout readiness audit.",
            "Topic-heldout readiness audit.",
            "topic-stability claims.",
        ]
    )

    errors = module.check_split_leakage_controls(manuscript_text, "")

    assert any("Split and Leakage Controls" in error for error in errors)
    assert any("tab:split-leakage-controls" in error for error in errors)


def test_check_result_interpretation_guardrails_accepts_complete_boundaries() -> None:
    """验证主结果表判读规则完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Result Interpretation Guardrails}",
            "The full result interpretation guardrails table is reported in the supplementary material.",
            "The main result table includes Scope type.",
            "It distinguishes full available Open-v2 scope.",
            "It distinguishes held-out Open-v2 test scope.",
            "Scope labels prevent ranking interpretation.",
            "The representation rows test false-merge exposure.",
            "The RoBERTa row is a strong supervised comparator.",
            "The IAD-Risk rows test split-held-out risk gating.",
            "The result is not a claim of broad method superiority.",
            "The table is not a same-scope comparative ranking.",
            "The table is not evidence of threshold stability or zero risk.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Claim-Evidence Matrix}",
            r"\label{tab:result-interpretation-guardrails}",
            "Result interpretation guardrails for the Open-v2 evidence snapshot.",
            "The table separates Directly supported reading.",
            "It also provides a mechanism-supported reading.",
            "It explicitly lists Unsupported reading.",
            "Representation baselines.",
            "RoBERTa pair classifier.",
            "IAD-Risk transformer variants.",
            "The rows are not a claim of broad method superiority.",
            "The table is not a same-scope comparative ranking.",
            "The table is not evidence of threshold stability or zero risk.",
        ]
    )

    errors = module.check_result_interpretation_guardrails(manuscript_text, supplementary_text)

    assert errors == []


def test_check_result_interpretation_guardrails_rejects_missing_unsupported_reading() -> None:
    """验证主结果表缺少禁止读法边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Result Interpretation Guardrails}"
    supplementary_text = r"\section{Claim-Evidence Matrix}"

    errors = module.check_result_interpretation_guardrails(manuscript_text, supplementary_text)

    assert any("Unsupported reading" in error for error in errors)
    assert any("not a same-scope comparative ranking" in error for error in errors)
    assert any("result-interpretation-guardrails" in error for error in errors)


def test_check_result_interpretation_guardrails_rejects_missing_scope_type_labels() -> None:
    """验证主结果表缺少 scope 类型标签时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Result Interpretation Guardrails}",
            "The full result interpretation guardrails table is reported in the supplementary material.",
            "The representation rows test false-merge exposure.",
            "The RoBERTa row is a strong supervised comparator.",
            "The IAD-Risk rows test split-held-out risk gating.",
            "The result is not a claim of broad method superiority.",
            "The table is not a same-scope comparative ranking.",
            "The table is not evidence of threshold stability or zero risk.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Claim-Evidence Matrix}",
            r"\label{tab:result-interpretation-guardrails}",
            "Result interpretation guardrails for the Open-v2 evidence snapshot.",
            "Directly supported reading.",
            "mechanism-supported reading.",
            "Unsupported reading.",
            "Representation baselines.",
            "RoBERTa pair classifier.",
            "IAD-Risk transformer variants.",
            "The result is not a claim of broad method superiority.",
            "The table is not a same-scope comparative ranking.",
            "The table is not evidence of threshold stability or zero risk.",
        ]
    )

    errors = module.check_result_interpretation_guardrails(manuscript_text, supplementary_text)

    assert any("Scope type" in error for error in errors)
    assert any("full available Open-v2 scope" in error for error in errors)
    assert any("held-out Open-v2 test scope" in error for error in errors)


def test_check_openv2_result_table_scope_labels_accepts_scoped_rows() -> None:
    """验证 Open-v2 主结果表每一行含有正确 scope 类型时可通过。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_openv2_result_table_scope_labels", None)
    assert callable(checker)
    manuscript_text = r"""
\begin{table}[H]
\caption{Open-v2 evidence snapshot. The Denom. audit column means that same-work F1, FMR, and HNFMR denominators must be present in the corresponding \texttt{open\_v2\_main\_results} artifact row before numerical audit.}
\label{tab:openv2-results}
\centering
\begin{tabular}{lllllll}
\toprule
System & Scope type & Pairs & Denom. audit & F1 $\uparrow$ & FMR $\downarrow$ & HNFMR $\downarrow$ \\
\midrule
SciNCL cosine & Full Open-v2 & 10415 & Artifact row & 0.054 & 0.785 & 0.790 \\
SPECTER2 adapter cosine & Full Open-v2 & 10415 & Artifact row & 0.044 & 0.999 & 0.999 \\
RoBERTa pair classifier & Full Open-v2 & 10415 & Artifact row & 0.825 & 0.001 & 0.0001 \\
IAD-Risk (SciNCL) & Held-out test & 1042 & Artifact row & 0.980 & 0.001 & 0.000 \\
IAD-Risk (SPECTER2) & Held-out test & 1042 & Artifact row & 0.980 & 0.001 & 0.000 \\
\bottomrule
\end{tabular}
\end{table}
"""

    errors = checker(manuscript_text)

    assert errors == []


def test_check_openv2_result_table_scope_labels_rejects_missing_scope_column() -> None:
    """验证 Open-v2 主结果表缺少 Scope type 第二列时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_openv2_result_table_scope_labels", None)
    assert callable(checker)
    manuscript_text = r"""
\begin{table}[H]
\caption{Open-v2 evidence snapshot.}
\label{tab:openv2-results}
\centering
\begin{tabular}{lllll}
\toprule
System & Pairs & F1 $\uparrow$ & FMR $\downarrow$ & HNFMR $\downarrow$ \\
\midrule
SciNCL cosine & 10415 & 0.054 & 0.785 & 0.790 \\
SPECTER2 adapter cosine & 10415 & 0.044 & 0.999 & 0.999 \\
RoBERTa pair classifier & 10415 & 0.825 & 0.001 & 0.0001 \\
IAD-Risk (SciNCL) & 1042 & 0.980 & 0.001 & 0.000 \\
IAD-Risk (SPECTER2) & 1042 & 0.980 & 0.001 & 0.000 \\
\bottomrule
\end{tabular}
\end{table}
"""

    errors = checker(manuscript_text)

    assert any("Scope type as the second column" in error for error in errors)
    assert any("SciNCL cosine" in error and "Full Open-v2" in error for error in errors)
    assert any("Denom. audit" in error for error in errors)


def test_check_openv2_result_table_scope_labels_rejects_wrong_iad_scope() -> None:
    """验证 IAD-Risk 结果行误写成 full scope 时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_openv2_result_table_scope_labels", None)
    assert callable(checker)
    manuscript_text = r"""
\begin{table}[H]
\caption{Open-v2 evidence snapshot. The Denom. audit column means that same-work F1, FMR, and HNFMR denominators must be present in the corresponding \texttt{open\_v2\_main\_results} artifact row before numerical audit.}
\label{tab:openv2-results}
\centering
\begin{tabular}{lllllll}
\toprule
System & Scope type & Pairs & Denom. audit & F1 $\uparrow$ & FMR $\downarrow$ & HNFMR $\downarrow$ \\
\midrule
SciNCL cosine & Full Open-v2 & 10415 & Artifact row & 0.054 & 0.785 & 0.790 \\
SPECTER2 adapter cosine & Full Open-v2 & 10415 & Artifact row & 0.044 & 0.999 & 0.999 \\
RoBERTa pair classifier & Full Open-v2 & 10415 & Artifact row & 0.825 & 0.001 & 0.0001 \\
IAD-Risk (SciNCL) & Full Open-v2 & 1042 & Artifact row & 0.980 & 0.001 & 0.000 \\
IAD-Risk (SPECTER2) & Held-out test & 1042 & Artifact row & 0.980 & 0.001 & 0.000 \\
\bottomrule
\end{tabular}
\end{table}
"""

    errors = checker(manuscript_text)

    assert any("IAD-Risk (SciNCL)" in error and "Held-out test" in error for error in errors)


def test_check_openv2_result_table_scope_labels_rejects_missing_denominator_audit() -> None:
    """验证 Open-v2 主结果表每行必须保留 denominator artifact 审计标记。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_openv2_result_table_scope_labels", None)
    assert callable(checker)
    manuscript_text = r"""
\begin{table}[H]
\caption{Open-v2 evidence snapshot. The Denom. audit column means that same-work F1, FMR, and HNFMR denominators must be present in the corresponding \texttt{open\_v2\_main\_results} artifact row before numerical audit.}
\label{tab:openv2-results}
\centering
\begin{tabular}{lllllll}
\toprule
System & Scope type & Pairs & Denom. audit & F1 $\uparrow$ & FMR $\downarrow$ & HNFMR $\downarrow$ \\
\midrule
SciNCL cosine & Full Open-v2 & 10415 & Artifact row & 0.054 & 0.785 & 0.790 \\
SPECTER2 adapter cosine & Full Open-v2 & 10415 & Artifact row & 0.044 & 0.999 & 0.999 \\
RoBERTa pair classifier & Full Open-v2 & 10415 & Artifact row & 0.825 & 0.001 & 0.0001 \\
IAD-Risk (SciNCL) & Held-out test & 1042 & Missing & 0.980 & 0.001 & 0.000 \\
IAD-Risk (SPECTER2) & Held-out test & 1042 & Artifact row & 0.980 & 0.001 & 0.000 \\
\bottomrule
\end{tabular}
\end{table}
"""

    errors = checker(manuscript_text)

    assert any("IAD-Risk (SciNCL)" in error and "Artifact row" in error for error in errors)


def test_check_manual_validation_boundary_accepts_complete_boundary() -> None:
    """验证主文人工验证边界完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Manual Validation Boundary}",
            "The full manual validation boundary table is reported in the supplementary material.",
            "Manual validation is not completed in the current manuscript package.",
            "Silver hard negatives are stress-test evidence.",
            "They are not human-gold non-identity labels.",
            "A 500--1,000 pair reviewed slice is required before stronger label-precision claims.",
            "The protocol needs two independent reviewers.",
            "The reviewers must be blind to model scores.",
            "The release must include an adjudication log.",
            "The release must include an agreement report.",
            "The paper does not claim complete human validation.",
        ]
    )

    errors = module.check_manual_validation_boundary(manuscript_text)

    assert errors == []


def test_check_manual_validation_boundary_rejects_missing_human_gold_boundary() -> None:
    """验证主文缺少人工 gold 边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Manual Validation Boundary}"

    errors = module.check_manual_validation_boundary(manuscript_text)

    assert any("not completed in the current manuscript package" in error for error in errors)
    assert any("not human-gold non-identity labels" in error for error in errors)


def test_check_scope_compatibility_accepts_main_boundary_and_supplementary_matrix() -> None:
    """验证主文范围边界和补充材料范围矩阵完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Scope Compatibility of the Open-v2 Table}",
            "The full scope compatibility matrix is reported in the supplementary material.",
            "The Open-v2 table is a scope-bounded evidence table.",
            "It is not a single comparative ranking.",
            "Full pair-scope representation baselines test hard-negative risk.",
            "Held-out IAD-Risk rows test risk-gated decisions.",
            "A stronger ranking requires the same released prediction scope.",
            "It also requires a manual-validation slice.",
            "A claim that this stronger comparison has already been completed is outside the evidence.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Claim-Evidence Matrix}",
            r"\label{tab:scope-compatibility}",
            "Scope compatibility for interpreting the Open-v2 evidence snapshot.",
            "Representation baselines use Full available Open-v2 pair scope.",
            "RoBERTa pair classifier is reported as a supervised comparator.",
            "IAD-Risk transformer variants use Held-out Open-v2 test scope.",
            "Future stronger comparison requires Same released prediction scope plus manual-validation slice.",
            "A claim that this stronger comparison has already been completed is not supported.",
        ]
    )

    errors = module.check_scope_compatibility(manuscript_text, supplementary_text)

    assert errors == []


def test_check_scope_compatibility_rejects_missing_supplementary_matrix() -> None:
    """验证缺少补充材料范围矩阵时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Scope Compatibility of the Open-v2 Table}",
            "The full scope compatibility matrix is reported in the supplementary material.",
            "The Open-v2 table is a scope-bounded evidence table.",
            "It is not a single comparative ranking.",
            "Full pair-scope representation baselines test hard-negative risk.",
            "Held-out IAD-Risk rows test risk-gated decisions.",
            "A stronger ranking requires the same released prediction scope.",
            "It also requires a manual-validation slice.",
            "A claim that this stronger comparison has already been completed is outside the evidence.",
        ]
    )
    supplementary_text = r"\section{Claim-Evidence Matrix}"

    errors = module.check_scope_compatibility(manuscript_text, supplementary_text)

    assert any("scope-compatibility" in error for error in errors)
    assert any("Representation baselines" in error for error in errors)
    assert any("Held-out Open-v2 test scope" in error for error in errors)


def test_check_extended_protocol_boundary_accepts_follow_up_protocol_scope() -> None:
    """验证 Open-v3/source-heldout 作为后续协议边界时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Extended Protocols and Boundaries}",
            "Open-v3 and source-heldout protocols are retained as follow-up evaluation paths.",
            "They are not as additional result evidence in the current manuscript package.",
            "The manuscript treats Open-v2 as the core mechanism demonstration.",
            "It reserves Open-v3/source-heldout conclusions for a released artifact package.",
            "That package needs matched prediction scopes, threshold logs, checksums, and manual-validation evidence.",
        ]
    )

    errors = module.check_extended_protocol_boundary(manuscript_text)

    assert errors == []


def test_check_extended_protocol_boundary_rejects_unreported_extended_results() -> None:
    """验证未报告结果不得写成当前扩展验证证据。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Extended Evidence and Boundaries}",
            "Open-v3 and source-heldout experiments provide additional stress tests.",
            "The manuscript therefore treats Open-v3 as extended validation.",
        ]
    )

    errors = module.check_extended_protocol_boundary(manuscript_text)

    assert any("additional stress tests" in error for error in errors)
    assert any("extended validation" in error for error in errors)


def test_check_claim_interpretation_boundary_accepts_complete_boundary() -> None:
    """验证 claim interpretation boundary 迁入补充材料后仍可通过检查。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_claim_interpretation_boundary", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\section{Claim Interpretation Boundary}",
            "The full claim-interpretation boundary table is reported in the supplementary material.",
            "The contribution clarity is tied to the IAD-Bench contract.",
            "The identity-agenda confusion is part of the boundary.",
            "HNFMR as a false-merge safety problem.",
            "The writing reproducibility is limited to code-level checks.",
            "The repository supports fixture rebuilds.",
            "The repository supports schema validation.",
            "The repository supports artifact-release preparation.",
            "The experimental strength is limited to the Open-v2 evidence snapshot.",
            "The evaluation completeness is limited by artifact-backed ablations.",
            "The table requires threshold grids.",
            "The table requires a manual-validation slice.",
            "The method design soundness remains bounded by source-heldout validation.",
            "The boundary requires topic-heldout checks.",
            "The boundary requires failure-case analysis.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Claim Interpretation Boundary}",
            r"\label{tab:claim-interpretation-boundary}",
            "Claim interpretation boundary.",
            "Contribution clarity",
            "Writing reproducibility",
            "Experimental strength",
            "Evaluation completeness",
            "Method design soundness",
            "Main evidence location",
            "Supported wording",
            "Boundary before stronger wording",
            "identity-agenda confusion",
            "IAD-Bench contract",
            "Open-v2 evidence snapshot",
            "artifact-backed ablations",
            "manual-validation slice",
            "source-heldout validation",
        ]
    )

    errors = checker(manuscript_text, supplementary_text)

    assert errors == []


def test_check_claim_interpretation_boundary_rejects_missing_boundaries() -> None:
    """验证主稿缺少正式 claim interpretation boundary 时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_claim_interpretation_boundary", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\section{Claim Interpretation Boundary}",
            "Contribution clarity",
            "Experimental strength",
        ]
    )

    errors = checker(manuscript_text)

    assert any("claim-interpretation-boundary" in error for error in errors)
    assert any("full claim-interpretation boundary table" in error for error in errors)
    assert any("manual-validation slice" in error for error in errors)


def test_check_claim_interpretation_boundary_rejects_reviewer_facing_title() -> None:
    """验证主稿不得继续使用内部审稿辅助式标题。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_claim_interpretation_boundary", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\section{Reviewer-Facing Claim Checklist}",
            r"\label{tab:reviewer-facing-claim-checklist}",
            "Reviewer-facing claim checklist.",
            "Contribution clarity",
            "Writing reproducibility",
            "Experimental strength",
            "Evaluation completeness",
            "Method design soundness",
            "Main evidence location",
            "Supported wording",
            "Boundary before stronger wording",
            "identity-agenda confusion",
            "IAD-Bench contract",
            "Open-v2 evidence snapshot",
            "artifact-backed ablations",
            "manual-validation slice",
            "source-heldout validation",
        ]
    )

    errors = checker(manuscript_text)

    assert any("Reviewer-Facing Claim Checklist" in error for error in errors)
    assert any("reviewer-facing-claim-checklist" in error for error in errors)


def test_check_manual_validation_protocol_accepts_complete_protocol() -> None:
    """验证补充材料包含人工验证协议时可通过检查。"""

    module = _load_validate_manuscript_module()
    supplementary_text = "\n".join(
        [
            r"\section{Manual Validation Protocol}",
            r"\label{tab:manual-validation-boundary}",
            r"\label{tab:manual-validation-protocol}",
            "Manual validation boundary for interpreting silver hard negatives.",
            "Manual validation is a future evidence layer.",
            "The protocol samples 500--1,000 pairs.",
            "A 500--1,000 pair reviewed slice is required.",
            "It uses two independent reviewers.",
            "Reviewers are blind to model scores.",
            "The release includes an adjudication log.",
            "The release includes an agreement report.",
            "The release includes pair-level notes.",
            "The artifact reports inter-annotator agreement.",
            "The manuscript does not claim that silver rows replace human-gold non-identity labels.",
            "The manuscript must not claim human gold before the files exist.",
        ]
    )

    errors = module.check_manual_validation_protocol(supplementary_text)

    assert errors == []


def test_check_manual_validation_protocol_rejects_vague_manual_review() -> None:
    """验证泛泛提到人工验证但缺少协议细节时会被拒绝。"""

    module = _load_validate_manuscript_module()
    supplementary_text = r"\section{Manual Validation Protocol}" + "\nManual validation is future work."

    errors = module.check_manual_validation_protocol(supplementary_text)

    assert any("500--1,000 pairs" in error for error in errors)
    assert any("two independent reviewers" in error for error in errors)
    assert any("inter-annotator agreement" in error for error in errors)
    assert any("manual-validation-boundary" in error for error in errors)


def test_check_environment_setup_accepts_complete_setup() -> None:
    """验证补充材料包含环境准备命令时可通过检查。"""

    module = _load_validate_manuscript_module()
    supplementary_text = "\n".join(
        [
            r"\section{Environment Setup}",
            "conda create -n iad-sieve python=3.11 -y",
            "python -m pip install -e .",
            "python -m iad_sieve.cli --help",
            "python scripts/check_public_release.py",
            "python manuscript/scripts/verify_fixture_rebuild.py",
            "The check does not download full raw datasets.",
            "Full numerical result reproduction still requires the L2/L3 data and artifact requirements.",
        ]
    )

    errors = module.check_environment_setup(supplementary_text)

    assert errors == []


def test_check_environment_setup_rejects_missing_fixture_command() -> None:
    """验证环境准备说明缺少 fixture 重建命令时会被拒绝。"""

    module = _load_validate_manuscript_module()
    supplementary_text = r"\section{Environment Setup}" + "\nconda create -n iad-sieve python=3.11 -y"

    errors = module.check_environment_setup(supplementary_text)

    assert any("verify_fixture_rebuild.py" in error for error in errors)
    assert any("does not download full raw datasets" in error for error in errors)


def test_check_public_source_rebuild_audit_boundary_accepts_complete_boundary() -> None:
    """验证补充材料必须说明 L2 公开源重建的输入、运行和输出审计边界。"""

    module = _load_validate_manuscript_module()
    supplementary_text = "\n".join(
        [
            r"\section{Public-Source Rebuild Audit Boundary}",
            r"\label{tab:public-source-rebuild-audit-boundary}",
            r"The package includes \path{source_input_manifest}.",
            r"The package includes \path{processing_run_log}.",
            "Source name and acquisition date or version are recorded.",
            "The original provider and license boundary are recorded.",
            "Each input has a SHA256 checksum.",
            "Command line, code commit, environment summary, and random seed are recorded.",
            "The release includes output summaries.",
            "The package preserves chain of custody.",
            "These files do not upgrade fixture-level reproduction into a full numerical audit.",
        ]
    )

    errors = module.check_public_source_rebuild_audit_boundary(supplementary_text)

    assert errors == []


def test_check_public_source_rebuild_audit_boundary_rejects_missing_manifest_and_log() -> None:
    """验证 L2 公开源重建说明缺少输入 manifest 或运行日志时会被拒绝。"""

    module = _load_validate_manuscript_module()
    supplementary_text = r"\section{Public-Source Rebuild Audit Boundary}" + "\nCommands are documented."

    errors = module.check_public_source_rebuild_audit_boundary(supplementary_text)

    assert any("source_input_manifest" in error for error in errors)
    assert any("processing_run_log" in error for error in errors)
    assert any("chain of custody" in error for error in errors)


def test_check_reviewer_evidence_gate_rejects_missing_artifact_gates() -> None:
    """验证补充材料审稿证据门禁必须覆盖关键 artifact 证据。"""

    module = _load_validate_manuscript_module()
    supplementary_text = r"\section{Reviewer Evidence Gate}" + "\nContribution clarity only."

    errors = module.check_reviewer_evidence_gate(supplementary_text)

    assert any("same-scope prediction files" in error for error in errors)
    assert any("bootstrap intervals" in error for error in errors)
    assert any("ablation suite" in error for error in errors)
    assert any("manual-validation slice" in error for error in errors)
    assert any("source-heldout validation" in error for error in errors)
    assert any("cluster-level artifact audits" in error for error in errors)


def test_check_reviewer_evidence_gate_accepts_complete_supplement() -> None:
    """验证实际补充材料覆盖审稿证据门禁时可通过检查。"""

    module = _load_validate_manuscript_module()
    supplementary_text = Path("manuscript/supplementary_material.tex").read_text(encoding="utf-8")

    errors = module.check_reviewer_evidence_gate(supplementary_text)

    assert errors == []


def test_check_target_journal_shortlist_accepts_complete_shortlist() -> None:
    """验证目标期刊候选清单包含候选、边界和模板要求时可通过。"""

    module = _load_validate_manuscript_module()
    shortlist_text = "\n".join(
        [
            "# Target Journal Shortlist",
            "This is not a final submission record.",
            "Rank-sensitive labels must be reconfirmed before final upload.",
            "Primary practical target: Data & Knowledge Engineering.",
            "Stretch target: Information Systems.",
            "Domain backup: Scientometrics.",
            "## Candidate Matrix",
            "## Template and File Implications",
            "## Data & Knowledge Engineering Preflight",
            "## Source-to-Decision Audit",
            "Official guide rechecked: 2026-06-19",
            "Official source snapshot date: 2026-06-19",
            "DKE guide verified: 2026-06-19",
            "Information Systems guide verified: 2026-06-19",
            "Scientometrics guide verified: 2026-06-19",
            "All publisher-page facts in this shortlist were rechecked on 2026-06-19.",
            "The official source links are listed below.",
            "JCR quartile and CCF class must be rechecked in the authors' authorized ranking systems.",
            "Status: provisional preparation only.",
            "The current anonymous author placeholder is compatible with single anonymized review preparation.",
            "The current abstract is checked against a 250-word limit.",
            "keywords.md currently contains 1--7 semicolon-separated keywords.",
            "highlights.md currently contains 3--5 highlights and is checked against the 85-character limit.",
            "Convert to Elsevier `elsarticle` only after confirmation.",
            "Add the real artifact URL or DOI before final upload.",
            "Information Systems data statement is required.",
            "CRediT author contribution statement.",
            "generative AI declaration.",
            "author biographies and photographs.",
            "AI-tool use.",
            "AI tools as authors.",
            "large-language-model use should be documented.",
            "copy-editing-only tool use.",
            "Metrics are screening signals, not ranking proof.",
            "Review model and author metadata rules determine anonymization.",
            "Data statement and artifact link requirements determine final-upload blockers.",
            "Recheck publisher pages on submission day.",
        ]
    )

    errors = module.check_target_journal_shortlist(shortlist_text)

    assert errors == []


def test_check_target_journal_shortlist_rejects_missing_boundary() -> None:
    """验证目标期刊候选清单缺少确认边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    shortlist_text = "# Target Journal Shortlist\nPrimary practical target: Data & Knowledge Engineering."

    errors = module.check_target_journal_shortlist(shortlist_text)

    assert any("Rank-sensitive labels" in error for error in errors)
    assert any("must be reconfirmed" in error for error in errors)


def test_check_target_journal_shortlist_rejects_missing_current_source_snapshot() -> None:
    """验证目标期刊候选清单必须记录官方来源快照日期。"""

    module = _load_validate_manuscript_module()
    shortlist_text = "\n".join(
        [
            "# Target Journal Shortlist",
            "This is not a final submission record.",
            "Rank-sensitive labels must be reconfirmed before final upload.",
            "Primary practical target: Data & Knowledge Engineering.",
            "Stretch target: Information Systems.",
            "Domain backup: Scientometrics.",
            "## Candidate Matrix",
            "## Template and File Implications",
            "## Data & Knowledge Engineering Preflight",
            "## Source-to-Decision Audit",
            "Official guide rechecked: 2026-06-19",
            "Status: provisional preparation only.",
            "The current anonymous author placeholder is compatible with single anonymized review preparation.",
            "The current abstract is checked against a 250-word limit.",
            "keywords.md currently contains 1--7 semicolon-separated keywords.",
            "highlights.md currently contains 3--5 highlights and is checked against the 85-character limit.",
            "Convert to Elsevier `elsarticle` only after confirmation.",
            "Add the real artifact URL or DOI before final upload.",
            "Metrics are screening signals, not ranking proof.",
            "Review model and author metadata rules determine anonymization.",
            "Data statement and artifact link requirements determine final-upload blockers.",
            "Recheck publisher pages on submission day.",
        ]
    )

    errors = module.check_target_journal_shortlist(shortlist_text)

    assert any("Official source snapshot date: 2026-06-19" in error for error in errors)
    assert any("Information Systems data statement is required" in error for error in errors)
    assert any("CRediT author contribution statement" in error for error in errors)
    assert any("generative AI declaration" in error for error in errors)


def test_check_target_journal_shortlist_rejects_missing_dke_preflight() -> None:
    """验证目标期刊候选清单缺少DKE官方预检时会被拒绝。"""

    module = _load_validate_manuscript_module()
    shortlist_text = "\n".join(
        [
            "# Target Journal Shortlist",
            "This is not a final submission record.",
            "Rank-sensitive labels must be reconfirmed before final upload.",
            "Primary practical target: Data & Knowledge Engineering.",
            "Stretch target: Information Systems.",
            "Domain backup: Scientometrics.",
            "## Candidate Matrix",
            "## Template and File Implications",
        ]
    )

    errors = module.check_target_journal_shortlist(shortlist_text)

    assert any("Data & Knowledge Engineering Preflight" in error for error in errors)
    assert any("Official guide rechecked" in error for error in errors)
    assert any("Elsevier `elsarticle`" in error for error in errors)


def test_check_target_journal_shortlist_rejects_missing_source_decision_audit() -> None:
    """验证目标期刊候选清单缺少来源到决策审计时会被拒绝。"""

    module = _load_validate_manuscript_module()
    shortlist_text = "\n".join(
        [
            "# Target Journal Shortlist",
            "This is not a final submission record.",
            "Rank-sensitive labels must be reconfirmed before final upload.",
            "Primary practical target: Data & Knowledge Engineering.",
            "Stretch target: Information Systems.",
            "Domain backup: Scientometrics.",
            "## Candidate Matrix",
            "## Template and File Implications",
            "## Data & Knowledge Engineering Preflight",
            "Official guide rechecked: 2026-06-19",
            "Status: provisional preparation only.",
            "The current anonymous author placeholder is compatible with single anonymized review preparation.",
            "The current abstract is checked against a 250-word limit.",
            "keywords.md currently contains 1--7 semicolon-separated keywords.",
            "highlights.md currently contains 3--5 highlights and is checked against the 85-character limit.",
            "Convert to Elsevier `elsarticle` only after confirmation.",
            "Add the real artifact URL or DOI before final upload.",
        ]
    )

    errors = module.check_target_journal_shortlist(shortlist_text)

    assert any("Source-to-Decision Audit" in error for error in errors)
    assert any("Metrics are screening signals" in error for error in errors)
    assert any("Recheck publisher pages on submission day" in error for error in errors)


def test_check_artifact_release_manifest_template_accepts_complete_template() -> None:
    """验证 artifact release 模板包含结果审计必要字段时可通过。"""

    module = _load_validate_manuscript_module()
    template_text = json.dumps(
        {
            "package_type": "result_artifact_release",
            "release_status": "template_pending_external_artifact",
            "data_policy": {
                "raw_third_party_data_included": False,
                "model_checkpoints_included": False,
                "personal_or_secret_material_included": False,
                "derived_evaluation_artifacts_included": True,
            },
            "required_directories": ["configs", "tables", "predictions", "reports", "logs"],
            "required_top_level_files": ["README.md", "manifest.json", "checksums.sha256"],
            "required_artifacts": [
                {
                    "artifact_id": "open_v2_main_results",
                    "claim_support": (
                        "Main Open-v2 result table with same-work F1, FMR, HNFMR, pair counts, row scopes, "
                        "per-row denominator counts, per-row threshold source, scope label used in the main table, "
                        "automatic merge count, block count, defer count, automatic merge coverage, defer rate, "
                        "and capacity-normalized review load."
                    ),
                },
                {
                    "artifact_id": "iad_risk_predictions",
                    "claim_support": (
                        "Held-out IAD-Risk rows with pair_id, source_document_id, target_document_id, "
                        "expected labels, label strength, hard-negative level, split identifiers, "
                        "relation-head scores, work_threshold, agenda_block_threshold, risk_threshold, "
                        "threshold source, and merge_prediction."
                    ),
                },
                {
                    "artifact_id": "representation_baseline_scores",
                    "claim_support": (
                        "Representation baseline rows with pair_id, source_document_id, target_document_id, "
                        "expected labels, label strength, hard-negative level, split identifiers, normalized score, "
                        "score_field, threshold_value, threshold source, and merge_prediction."
                    ),
                },
                {
                    "artifact_id": "supervised_baseline_predictions",
                    "claim_support": (
                        "Supervised baseline rows with pair_id, source_document_id, target_document_id, "
                        "expected labels, label strength, hard-negative level, split identifiers, match_probability, "
                        "threshold_value, threshold source, and merge_prediction."
                    ),
                },
                {
                    "artifact_id": "threshold_selection_logs",
                    "claim_support": (
                        "Threshold rows with threshold_name, threshold_value, selection_split, "
                        "selection_metric, selection_rule, applied_scope, and score_field."
                    ),
                },
                {"artifact_id": "iad_bench_split_summary"},
                {
                    "artifact_id": "source_input_manifest",
                    "claim_support": (
                        "L2 public-source rebuild chain of custody with source name, acquisition date or version, "
                        "original provider, local file name, record count, license boundary, and SHA256 checksum."
                    ),
                },
                {
                    "artifact_id": "processing_run_log",
                    "claim_support": (
                        "Processing-stage log with command line, code commit, environment summary, random seed, "
                        "start and finish timestamps, input manifest reference, output path, and exit status."
                    ),
                },
                {
                    "artifact_id": "bootstrap_intervals",
                    "claim_support": (
                        "Confidence intervals only if cited by the final manuscript. The CSV must include "
                        "metric_name rows for same_work_f1, fmr, and hnfmr, with system, scope_type, "
                        "prediction_artifact_id, prediction_file_sha256, bootstrap_method, resample_unit, "
                        "resample_count, confidence_level, alpha, random_seed, point_estimate, interval_lower, "
                        "interval_upper, metric_denominator, threshold_source, and command_line. Each row must "
                        "bind to the exact prediction file checksum and satisfy interval_lower <= point_estimate <= interval_upper."
                    ),
                },
                {
                    "artifact_id": "ablation_suite",
                    "claim_support": (
                        "Component-level causality only if cited by the final manuscript. The CSV must include "
                        "protocol_variant rows for no-risk-gate, no-ANI-head, single-space, no-cannot-link, "
                        "and post-hoc-threshold, with protocol_required, accepted_for_component_causality, "
                        "threshold_source, protocol_scope_rule, requires_prediction_rows, denominators, and "
                        "false-merge metrics. The post-hoc-threshold row must use threshold_source="
                        "post_hoc_labeled_sweep and must not be accepted as standalone component-causality evidence."
                    ),
                },
                {
                    "artifact_id": "manual_validation_slice",
                    "claim_support": (
                        "Human label-precision claims only if cited by the final manuscript. The CSV must contain "
                        "a 500-1000 pair reviewed slice with manual_validation_stratum coverage for "
                        "silver_hard_negative, high_score_false_merge_candidate, blocked_or_deferred, "
                        "model_disagreement, version_boundary, identifier_conflict, and sparse_metadata; "
                        "two independent reviewer codes through reviewer_1_code and reviewer_2_code; labels in "
                        "reviewer_1_label, reviewer_2_label, and adjudicated_label; blinding fields "
                        "reviewer_blinding_confirmed, model_score_hidden, and merge_decision_hidden; "
                        "adjudication_status, adjudication_rationale, pair_level_notes, and agreement_status."
                    ),
                },
                {
                    "artifact_id": "threshold_sensitivity_grid",
                    "claim_support": (
                        "Threshold-stability claims only if cited by the final manuscript. The CSV must include "
                        "at least two predefined threshold rows generated from exactly one prediction_artifact_id "
                        "and prediction_file_sha256, with system, threshold_grid_id, threshold_range_source, "
                        "threshold_source, selection_split, evaluation_split, work_threshold, "
                        "agenda_block_threshold, risk_threshold, selected_operating_point, same_work_f1, fmr, "
                        "hnfmr, denominator counts, automatic_merge_count, block_count, defer_count, "
                        "random_seed, command_line, and separate selection and evaluation splits."
                    ),
                },
                {
                    "artifact_id": "cluster_metric_summary",
                    "claim_support": (
                        "Cluster-level quality claims only if cited by the final manuscript. The CSV must include "
                        "system, cluster_run_id, merge_policy_id, prediction_artifact_id, prediction_file_sha256, "
                        "threshold_source, work_threshold, agenda_block_threshold, risk_threshold, "
                        "cluster_assignment_file, pair_to_cluster_trace_file, cluster_id, cluster_size, "
                        "accepted_link_count, cannot_link_conflict_count, unresolved_conflict_count, "
                        "cluster_contamination_rate, singleton_rate, merge_coverage, random_seed, and command_line, "
                        "with exactly one cluster_run_id, exactly one merge_policy_id, prediction_artifact_id, and prediction_file_sha256."
                    ),
                },
                {
                    "artifact_id": "cannot_link_audit",
                    "claim_support": (
                        "Cannot-link and transitive-merge safety claims only if cited by the final manuscript. "
                        "The CSV must include system, cluster_run_id, merge_policy_id, prediction_artifact_id, "
                        "prediction_file_sha256, threshold_source, work_threshold, agenda_block_threshold, "
                        "risk_threshold, cannot_link_rule_id, conflict_type, source_document_id, target_document_id, "
                        "cannot_link_flag, accepted_merge_blocked, violation_detected, unresolved_conflict, "
                        "cannot_link_coverage_rate, identifier_conflict_rule, pair_to_cluster_trace_file, "
                        "random_seed, and command_line, with exactly one cluster_run_id, exactly one merge_policy_id, "
                        "prediction_artifact_id, and prediction_file_sha256."
                    ),
                },
            ],
            "minimum_validation_commands": [
                "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
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
            "conditional_claim_artifacts": {
                "confidence_intervals_claimed": ["bootstrap_intervals"],
                "component_causality_claimed": ["ablation_suite"],
                "human_validation_claimed": ["manual_validation_slice"],
                "threshold_stability_claimed": ["threshold_sensitivity_grid"],
                "cluster_level_quality_claimed": ["cluster_metric_summary", "cannot_link_audit"],
                "broad_method_ranking_claimed": [
                    "bootstrap_intervals",
                    "manual_validation_slice",
                    "threshold_sensitivity_grid",
                ],
            },
        }
    )

    errors = module.check_artifact_release_manifest_template(template_text)

    assert errors == []


def test_check_artifact_release_manifest_template_rejects_missing_result_row_audit_claim() -> None:
    """验证 artifact release manifest 模板必须说明主结果表行级审计列。"""

    module = _load_validate_manuscript_module()
    template_path = Path(__file__).resolve().parents[1] / "manuscript" / "artifact_release_manifest.template.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))
    for artifact_row in template["required_artifacts"]:
        if artifact_row.get("artifact_id") == "open_v2_main_results":
            artifact_row["claim_support"] = "Main Open-v2 result table."
    template_text = json.dumps(template)

    errors = module.check_artifact_release_manifest_template(template_text)

    assert any("per-row denominator counts" in error for error in errors)
    assert any("per-row threshold source" in error for error in errors)
    assert any("scope label used in the main table" in error for error in errors)
    assert any("automatic merge coverage" in error for error in errors)
    assert any("defer rate" in error for error in errors)
    assert any("capacity-normalized review load" in error for error in errors)


def test_check_artifact_release_manifest_template_rejects_unsafe_data_policy() -> None:
    """验证 artifact release 模板不得允许原始数据或缺少关键预测文件。"""

    module = _load_validate_manuscript_module()
    template_text = json.dumps(
        {
            "package_type": "result_artifact_release",
            "release_status": "template_pending_external_artifact",
            "data_policy": {
                "raw_third_party_data_included": True,
                "model_checkpoints_included": False,
                "personal_or_secret_material_included": False,
                "derived_evaluation_artifacts_included": False,
            },
            "required_directories": ["tables"],
            "required_top_level_files": ["manifest.json"],
            "required_artifacts": [{"artifact_id": "open_v2_main_results"}],
            "minimum_validation_commands": [],
            "claim_boundaries": {},
        }
    )

    errors = module.check_artifact_release_manifest_template(template_text)

    assert any("raw_third_party_data_included" in error for error in errors)
    assert any("iad_risk_predictions" in error for error in errors)
    assert any("sha256sum -c checksums.sha256" in error for error in errors)
    assert any("python -m iad_sieve.cli --help" in error for error in errors)


def test_check_artifact_release_manifest_template_rejects_missing_cluster_claim_artifacts() -> None:
    """验证 artifact release 模板必须定义 cluster-level 条件 artifact。"""

    module = _load_validate_manuscript_module()
    template_text = json.dumps(
        {
            "package_type": "result_artifact_release",
            "release_status": "template_pending_external_artifact",
            "data_policy": {
                "raw_third_party_data_included": False,
                "model_checkpoints_included": False,
                "personal_or_secret_material_included": False,
                "derived_evaluation_artifacts_included": True,
            },
            "required_directories": ["configs", "tables", "predictions", "reports", "logs"],
            "required_top_level_files": ["README.md", "manifest.json", "checksums.sha256"],
            "required_artifacts": [
                {"artifact_id": "open_v2_main_results"},
                {"artifact_id": "iad_risk_predictions"},
                {"artifact_id": "representation_baseline_scores"},
                {"artifact_id": "supervised_baseline_predictions"},
                {"artifact_id": "threshold_selection_logs"},
                {"artifact_id": "iad_bench_split_summary"},
                {"artifact_id": "bootstrap_intervals"},
                {
                    "artifact_id": "ablation_suite",
                    "claim_support": (
                        "protocol_variant rows for no-risk-gate, no-ANI-head, single-space, no-cannot-link, "
                        "and post-hoc-threshold with protocol_required, accepted_for_component_causality, "
                        "threshold_source, protocol_scope_rule, requires_prediction_rows, denominators, "
                        "false-merge metrics, post_hoc_labeled_sweep, and must not be accepted as standalone "
                        "component-causality evidence."
                    ),
                },
                {"artifact_id": "manual_validation_slice"},
                {"artifact_id": "threshold_sensitivity_grid"},
            ],
            "minimum_validation_commands": [
                "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
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
            },
            "conditional_claim_artifacts": {
                "confidence_intervals_claimed": ["bootstrap_intervals"],
                "component_causality_claimed": ["ablation_suite"],
                "human_validation_claimed": ["manual_validation_slice"],
                "threshold_stability_claimed": ["threshold_sensitivity_grid"],
                "broad_method_ranking_claimed": [
                    "bootstrap_intervals",
                    "manual_validation_slice",
                    "threshold_sensitivity_grid",
                ],
            },
        }
    )

    errors = module.check_artifact_release_manifest_template(template_text)

    assert any("cluster_metric_summary" in error for error in errors)
    assert any("cannot_link_audit" in error for error in errors)
    assert any("cluster_level_quality_claimed" in error for error in errors)


def test_check_artifact_release_manifest_template_rejects_missing_conditional_claim_artifacts() -> None:
    """验证 artifact release 模板必须定义强主张条件 artifact。"""

    module = _load_validate_manuscript_module()
    template_text = json.dumps(
        {
            "package_type": "result_artifact_release",
            "release_status": "template_pending_external_artifact",
            "data_policy": {
                "raw_third_party_data_included": False,
                "model_checkpoints_included": False,
                "personal_or_secret_material_included": False,
                "derived_evaluation_artifacts_included": True,
            },
            "required_directories": ["configs", "tables", "predictions", "reports", "logs"],
            "required_top_level_files": ["README.md", "manifest.json", "checksums.sha256"],
            "required_artifacts": [
                {"artifact_id": "open_v2_main_results"},
                {"artifact_id": "iad_risk_predictions"},
                {"artifact_id": "representation_baseline_scores"},
                {"artifact_id": "supervised_baseline_predictions"},
                {"artifact_id": "threshold_selection_logs"},
                {"artifact_id": "iad_bench_split_summary"},
                {"artifact_id": "bootstrap_intervals"},
                {
                    "artifact_id": "ablation_suite",
                    "claim_support": (
                        "protocol_variant rows for no-risk-gate, no-ANI-head, single-space, no-cannot-link, "
                        "and post-hoc-threshold with protocol_required, accepted_for_component_causality, "
                        "threshold_source, protocol_scope_rule, requires_prediction_rows, denominators, "
                        "false-merge metrics, post_hoc_labeled_sweep, and must not be accepted as standalone "
                        "component-causality evidence."
                    ),
                },
                {"artifact_id": "manual_validation_slice"},
                {"artifact_id": "cluster_metric_summary"},
                {"artifact_id": "cannot_link_audit"},
            ],
            "minimum_validation_commands": [
                "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
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
    )

    errors = module.check_artifact_release_manifest_template(template_text)

    assert any("threshold_sensitivity_grid" in error for error in errors)
    assert any("conditional_claim_artifacts" in error for error in errors)


def test_check_artifact_release_readme_template_accepts_complete_template() -> None:
    """验证 artifact release README 模板覆盖审稿复现入口时可通过。"""

    module = _load_validate_manuscript_module()
    readme_text = "\n".join(
        [
            "# IAD-Risk Artifact Release README Template",
            "This template is for the external result artifact release.",
            "Do not include raw third-party data.",
            "Do not include model checkpoints.",
            "Do not include credentials, personal identifiers, or local paths.",
            "## Required Top-Level Files",
            "README.md",
            "manifest.json",
            "checksums.sha256",
            "## Required Directories",
            "configs/",
            "tables/",
            "predictions/",
            "reports/",
            "logs/",
            "## Minimum Validation Commands",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
            "checks required source artifact files before anything is copied",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release",
            "sha256sum -c checksums.sha256",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
            "python -m iad_sieve.cli --help",
            "python manuscript/scripts/validate_manuscript.py --strict-latex",
            "python manuscript/scripts/verify_fixture_rebuild.py",
            "python scripts/check_public_release.py",
            "## Required Artifact IDs",
            "open_v2_main_results",
            "per-row denominator counts",
            "per-row threshold source",
            "scope label used in the main table",
            "automatic merge count",
            "block count",
            "defer count",
            "automatic merge coverage",
            "defer rate",
            "capacity-normalized review load",
            "iad_risk_predictions",
            "relation-head scores",
            "work_threshold",
            "agenda_block_threshold",
            "risk_threshold",
            "merge_prediction",
            "representation_baseline_scores",
            "normalized score",
            "score_field",
            "threshold_value",
            "supervised_baseline_predictions",
            "match_probability",
            "threshold_selection_logs",
            "threshold_name",
            "selection_split",
            "selection_metric",
            "selection_rule",
            "applied_scope",
            "iad_bench_split_summary",
            "source_input_manifest",
            "acquisition date or version",
            "original provider",
            "license boundary",
            "processing_run_log",
            "command line",
            "code commit",
            "environment summary",
            "random seed",
            "exit status",
            "bootstrap_intervals",
            "metric_name rows for same_work_f1, fmr, and hnfmr",
            "scope_type",
            "prediction_artifact_id",
            "prediction_file_sha256",
            "bootstrap_method",
            "resample_unit",
            "resample_count",
            "confidence_level",
            "alpha",
            "point_estimate",
            "interval_lower",
            "interval_upper",
            "metric_denominator",
            "exact prediction file checksum",
            "interval_lower <= point_estimate <= interval_upper",
            "ablation_suite",
            "protocol_variant",
            "no-risk-gate",
            "no-ANI-head",
            "single-space",
            "no-cannot-link",
            "post-hoc-threshold",
            "protocol_required",
            "accepted_for_component_causality",
            "threshold_source",
            "protocol_scope_rule",
            "requires_prediction_rows",
            "denominators",
            "false-merge metrics",
            "post_hoc_labeled_sweep",
            "standalone component-causality evidence",
            "manual_validation_slice",
            "500-1000 pair reviewed slice",
            "manual_validation_stratum",
            "silver_hard_negative",
            "high_score_false_merge_candidate",
            "blocked_or_deferred",
            "model_disagreement",
            "version_boundary",
            "identifier_conflict",
            "sparse_metadata",
            "two independent reviewer codes",
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
            "threshold_sensitivity_grid",
            "at least two predefined threshold rows",
            "exactly one prediction_artifact_id",
            "prediction_file_sha256",
            "threshold_grid_id",
            "threshold_range_source",
            "evaluation_split",
            "selected_operating_point",
            "same_work_f1",
            "fmr",
            "hnfmr",
            "denominator counts",
            "automatic_merge_count",
            "block_count",
            "defer_count",
            "separate selection and evaluation splits",
            "cluster_metric_summary",
            "cannot_link_audit",
            "cluster_run_id",
            "merge_policy_id",
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
            "cannot_link_rule_id",
            "conflict_type",
            "cannot_link_flag",
            "accepted_merge_blocked",
            "violation_detected",
            "cannot_link_coverage_rate",
            "identifier_conflict_rule",
            "exactly one cluster_run_id",
            "exactly one merge_policy_id",
            "## Conditional Claim Artifacts",
            "confidence_intervals_claimed requires bootstrap_intervals.",
            "component_causality_claimed requires ablation_suite.",
            "Component-causality claims require ablation_suite with full protocol_variant coverage and post-hoc threshold diagnostics separated from causal evidence.",
            "human_validation_claimed requires manual_validation_slice.",
            "threshold_stability_claimed requires threshold_sensitivity_grid.",
            "cluster_level_quality_claimed requires cluster_metric_summary and cannot_link_audit.",
            "broad_method_ranking_claimed requires bootstrap_intervals, manual_validation_slice, and threshold_sensitivity_grid.",
            "## Claim Boundaries",
            "silver labels are not human gold.",
            "full numerical audit requires external artifacts.",
            "broad method ranking is not claimed unless conditional artifacts are complete.",
            "cluster-level quality is not claimed unless cluster artifacts are complete.",
            "## Reproduction Levels",
            "L0 code check",
            "L1 fixture rebuild",
            "L2 public-source rebuild",
            "L3 result audit",
            "## L2 Public-Source Rebuild Boundary",
            "input boundary",
            "command boundary",
            "output boundary",
            "checksum boundary",
            "## Release Metadata To Fill",
            "publication.artifact_release_url",
            "publication.artifact_release_doi",
            "publication.public_access_status",
            "final-upload `submission_metadata.yml`",
        ]
    )

    errors = module.check_artifact_release_readme_template(readme_text)

    assert errors == []


def test_check_artifact_release_readme_template_rejects_missing_result_row_audit_description() -> None:
    """验证 artifact release README 模板必须说明主结果表行级审计列。"""

    module = _load_validate_manuscript_module()
    readme_path = Path(__file__).resolve().parents[1] / "manuscript" / "artifact_release_README.template.md"
    readme_text = readme_path.read_text(encoding="utf-8")
    for marker in [
        "per-row denominator counts",
        "per-row threshold source",
        "scope label used in the main table",
        "automatic merge count",
        "block count",
        "defer count",
        "automatic merge coverage",
        "defer rate",
        "capacity-normalized review load",
    ]:
        readme_text = readme_text.replace(marker, "")

    errors = module.check_artifact_release_readme_template(readme_text)

    assert any("per-row denominator counts" in error for error in errors)
    assert any("per-row threshold source" in error for error in errors)
    assert any("scope label used in the main table" in error for error in errors)
    assert any("automatic merge coverage" in error for error in errors)
    assert any("defer rate" in error for error in errors)
    assert any("capacity-normalized review load" in error for error in errors)


def test_check_artifact_release_readme_template_rejects_missing_release_boundaries() -> None:
    """验证 artifact release README 模板缺少复现边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    readme_text = "# IAD-Risk Artifact Release README Template\nREADME.md\nmanifest.json\n"

    errors = module.check_artifact_release_readme_template(readme_text)

    assert any("raw third-party data" in error for error in errors)
    assert any("validate_artifact_release.py" in error for error in errors)
    assert any("python -m iad_sieve.cli --help" in error for error in errors)
    assert any("threshold_sensitivity_grid" in error for error in errors)
    assert any("cluster_metric_summary" in error for error in errors)


def test_check_manuscript_package_docs_accepts_result_row_schema() -> None:
    """验证稿件目录说明覆盖主结果表行级 schema 时可通过。"""

    module = _load_validate_manuscript_module()
    readme_text = Path("manuscript/README.md").read_text(encoding="utf-8")
    manifest_text = Path("manuscript/MANIFEST.md").read_text(encoding="utf-8")

    errors = module.check_manuscript_package_docs(readme_text, manifest_text)

    assert errors == []


def test_check_manuscript_package_docs_rejects_missing_result_row_schema() -> None:
    """验证稿件目录说明必须覆盖主结果表行级 schema。"""

    module = _load_validate_manuscript_module()
    readme_text = Path("manuscript/README.md").read_text(encoding="utf-8")
    manifest_text = Path("manuscript/MANIFEST.md").read_text(encoding="utf-8")
    for marker in [
        "open_v2_main_results",
        "per-row denominator counts",
        "per-row threshold source",
        "scope label used in the main table",
        "automatic merge count",
        "block count",
        "defer count",
        "automatic merge coverage",
        "defer rate",
        "capacity-normalized review load",
        "iad_risk_predictions",
        "representation_baseline_scores",
        "supervised_baseline_predictions",
        "threshold_selection_logs",
        "pair_id",
        "source_document_id",
        "target_document_id",
        "label strength",
        "hard-negative level",
        "split identifiers",
        "score_field",
        "threshold_value",
        "merge_prediction",
        "final_upload_information_request.md",
        "Author list",
        "Corresponding author",
        "Funding statement",
        "Artifact release URL or DOI",
    ]:
        readme_text = readme_text.replace(marker, "")
        manifest_text = manifest_text.replace(marker, "")

    errors = module.check_manuscript_package_docs(readme_text, manifest_text)

    assert any("open_v2_main_results" in error for error in errors)
    assert any("per-row denominator counts" in error for error in errors)
    assert any("per-row threshold source" in error for error in errors)
    assert any("scope label used in the main table" in error for error in errors)
    assert any("automatic merge coverage" in error for error in errors)
    assert any("defer rate" in error for error in errors)
    assert any("capacity-normalized review load" in error for error in errors)
    assert any("iad_risk_predictions" in error for error in errors)
    assert any("threshold_selection_logs" in error for error in errors)
    assert any("pair_id" in error for error in errors)
    assert any("score_field" in error for error in errors)
    assert any("merge_prediction" in error for error in errors)
    assert any("final_upload_information_request.md" in error for error in errors)
    assert any("Author list" in error for error in errors)
    assert any("Corresponding author" in error for error in errors)
    assert any("Funding statement" in error for error in errors)
    assert any("Artifact release URL or DOI" in error for error in errors)


def test_check_related_work_positioning_accepts_main_text_and_supplementary_matrix() -> None:
    """验证 Related Work 正文和补充材料共同保留创新边界时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\section{Related Work}",
            "The complete positioning matrix is reported in the supplementary material.",
            "End-to-end entity resolution systems",
            "Neural entity matching",
            "Scientific document representations",
            "Open scholarly metadata benchmarks",
            "false-merge risk gates",
            "gold, proxy, and silver strata",
            "The method is not a replacement for end-to-end entity resolution workflows.",
            "It is not a comparative ranking over all neural matching methods.",
            "It does not claim that OpenAlex/OpenCitations silver evidence is human gold.",
            "The evidence supports the merge-safety framing.",
            "It clarifies the decision semantics assigned to relatedness.",
            "The score can be positive, negative, or deferred.",
            "It is not as a direct merge decision.",
            "The boundary connects IAD-Bench to HNFMR.",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Closest-Work Positioning}",
            r"\label{tab:closest-work-positioning}",
            "Positioning against the closest lines of work",
            "Line of work",
            "Primary optimization target",
            "Limitation for scholarly deduplication",
            "IAD-Risk distinction",
            "End-to-end entity resolution systems",
            "Neural entity matching",
            "Scientific document representations",
            "Open scholarly metadata benchmarks",
            "false-merge risk gates",
            "gold, proxy, and silver strata",
        ]
    )

    errors = module.check_related_work_positioning(manuscript_text, supplementary_text)

    assert errors == []


def test_check_related_work_positioning_rejects_missing_novelty_boundaries() -> None:
    """验证 Related Work 必须说明最接近工作的创新边界。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\section{Related Work}",
            "The complete positioning matrix is reported in the supplementary material.",
            "End-to-end entity resolution systems",
            "Neural entity matching",
            "Scientific document representations",
            "Open scholarly metadata benchmarks",
            "false-merge risk gates",
            "gold, proxy, and silver strata",
        ]
    )
    supplementary_text = "\n".join(
        [
            r"\section{Closest-Work Positioning}",
            r"\label{tab:closest-work-positioning}",
            "Positioning against the closest lines of work",
            "Line of work",
            "Primary optimization target",
            "Limitation for scholarly deduplication",
            "IAD-Risk distinction",
            "End-to-end entity resolution systems",
            "Neural entity matching",
            "Scientific document representations",
            "Open scholarly metadata benchmarks",
            "false-merge risk gates",
            "gold, proxy, and silver strata",
        ]
    )

    errors = module.check_related_work_positioning(manuscript_text, supplementary_text)

    assert any("not a replacement for end-to-end entity resolution workflows" in error for error in errors)
    assert any("not a comparative ranking over all neural matching methods" in error for error in errors)
    assert any("OpenAlex/OpenCitations silver evidence is human gold" in error for error in errors)


def test_check_data_processing_pipeline_document_accepts_reproducible_pipeline() -> None:
    """验证数据处理文档保留无数据提交时的可复现处理入口。"""

    module = _load_validate_manuscript_module()
    document_text = "\n".join(
        [
            "# 数据处理流水线",
            "远程仓库不提交原始数据时，复现能力不能依赖口头说明。",
            "python -m iad_sieve.cli --help",
            "tests/fixtures/",
            "outputs/repro_fixture",
            "data/raw/",
            "L2 重建审计文件",
            "configs/source_input_manifest.json",
            "logs/processing_run_log.jsonl",
            "reports/iad_bench_split_summary.jsonl",
            "chain of custody",
            "prepare-deepmatcher",
            "prepare-scirepeval-proximity",
            "fetch-openalex-works",
            "prepare-openalex-weak-labels",
            "build-iad-bench",
            "Artifact release",
            "manifest",
            "checksum",
        ]
    )

    errors = module.check_data_processing_pipeline_document(document_text)

    assert errors == []


def test_check_data_processing_pipeline_document_rejects_missing_cli_and_artifact_boundary() -> None:
    """验证数据处理文档缺少 CLI 或 artifact 边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    document_text = "# 数据处理流水线\n远程仓库不提交原始数据。\n"

    errors = module.check_data_processing_pipeline_document(document_text)

    assert any("python -m iad_sieve.cli --help" in error for error in errors)
    assert any("prepare-deepmatcher" in error for error in errors)
    assert any("Artifact release" in error for error in errors)


def test_check_artifact_release_skeleton_builder_accepts_required_markers() -> None:
    """验证 artifact release 骨架生成脚本包含必要入口和安全边界。"""

    module = _load_validate_manuscript_module()
    script_text = "\n".join(
        [
            "import argparse",
            "import logging",
            "SKELETON_RELEASE_STATUS = \"skeleton_pending_artifacts\"",
            "ARTIFACT_SHA256_PLACEHOLDER = \"fill-after-artifact-export\"",
            "artifact_release_manifest.template.json",
            "artifact_release_README.template.md",
            "checksums.sha256",
            "REQUIRED_DIRECTORIES",
            "def build_artifact_release_skeleton(",
            "def write_checksums(",
            "def parse_arguments(",
            "--repository-commit",
            "--force",
        ]
    )

    errors = module.check_artifact_release_skeleton_builder(script_text)

    assert errors == []


def test_check_artifact_release_skeleton_builder_rejects_missing_force_guard() -> None:
    """验证 artifact release 骨架生成脚本缺少覆盖保护时会被拒绝。"""

    module = _load_validate_manuscript_module()
    script_text = "def build_artifact_release_skeleton():\n    pass\n"

    errors = module.check_artifact_release_skeleton_builder(script_text)

    assert any("--force" in error for error in errors)
    assert any("checksums.sha256" in error for error in errors)


def test_check_artifact_release_finalizer_accepts_required_markers() -> None:
    """验证 artifact release 定稿脚本包含刷新和最终校验入口。"""

    module = _load_validate_manuscript_module()
    script_text = "\n".join(
        [
            "import argparse",
            "import logging",
            "DEFAULT_RELEASE_STATUS = \"release_candidate\"",
            "checksums.sha256",
            "def finalize_artifact_release(",
            "def update_artifact_checksums(",
            "def write_checksums(",
            "def run_artifact_validator(",
            "--artifact-dir",
            "--release-status",
            "--skip-validate",
            "missing required artifact files",
        ]
    )

    errors = module.check_artifact_release_finalizer(script_text)

    assert errors == []


def test_check_artifact_release_finalizer_rejects_missing_validator_call() -> None:
    """验证 artifact release 定稿脚本缺少最终校验入口时会被拒绝。"""

    module = _load_validate_manuscript_module()
    script_text = "def finalize_artifact_release():\n    pass\n"

    errors = module.check_artifact_release_finalizer(script_text)

    assert any("run_artifact_validator" in error for error in errors)
    assert any("--skip-validate" in error for error in errors)


def test_check_artifact_release_populator_accepts_required_markers() -> None:
    """验证 artifact release 填充脚本包含 source 到 release 的桥接入口。"""

    module = _load_validate_manuscript_module()
    script_text = "\n".join(
        [
            "import argparse",
            "import logging",
            "POPULATION_LOG_PATH = \"logs/artifact_population_log.jsonl\"",
            "def populate_artifact_release(",
            "def preflight_source_artifacts(",
            "def build_copy_plan(",
            "def copy_planned_artifacts(",
            "def write_population_log(",
            "def finalize_release(",
            "--source-dir",
            "--mapping",
            "--preflight-only",
            "--skip-finalize",
            "without copying, logging, or finalizing",
            "missing required source artifact files",
        ]
    )

    errors = module.check_artifact_release_populator(script_text)

    assert errors == []


def test_check_artifact_release_populator_rejects_missing_mapping_entry() -> None:
    """验证 artifact release 填充脚本缺少映射入口时会被拒绝。"""

    module = _load_validate_manuscript_module()
    script_text = "def populate_artifact_release():\n    pass\n"

    errors = module.check_artifact_release_populator(script_text)

    assert any("--mapping" in error for error in errors)
    assert any("--preflight-only" in error for error in errors)
    assert any("build_copy_plan" in error for error in errors)


def test_check_submission_system_checklist_accepts_complete_checklist() -> None:
    """验证投稿系统上传清单覆盖文件、元数据和阻断项时可通过。"""

    module = _load_validate_manuscript_module()
    checklist_text = "\n".join(
        [
            "# Submission System Checklist",
            "This is not a manuscript file for journal upload.",
            "## Required Upload Files",
            "Main manuscript source",
            "Main manuscript PDF",
            "DKE/Elsevier preflight source",
            "DKE/Elsevier preflight PDF",
            "Supplementary source",
            "Supplementary PDF",
            "Bibliography",
            "Cover letter",
            "Highlights",
            "Keywords",
            "Submission metadata",
            "target_journal_template_bound",
            "target ranking/category confirmation fields",
            "Author biographies and photographs",
            "author_identity_materials",
            "biography_files",
            "photograph_files",
            "author_identity_materials_verified",
            "Artifact release manifest",
            "## Artifact Release Package Checks",
            "python manuscript/scripts/build_artifact_release_skeleton.py --output-dir /path/to/release --repository-commit",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
            "checks required source artifact files before anything is copied",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
            "python -m iad_sieve.cli --help",
            "same repository checkout named by the release manifest",
            "`manifest.json` contains a `publication` object whose `artifact_release_url`, `artifact_release_doi`, and `public_access_status` match the final-upload metadata.",
            "open_v2_main_results",
            "per-row denominator counts",
            "per-row threshold source",
            "scope label used in the main table",
            "automatic merge count",
            "block count",
            "defer count",
            "automatic merge coverage",
            "defer rate",
            "capacity-normalized review load",
            "iad_risk_predictions",
            "representation_baseline_scores",
            "supervised_baseline_predictions",
            "threshold_selection_logs",
            "pair_id",
            "source_document_id",
            "target_document_id",
            "label strength",
            "hard-negative level",
            "split identifiers",
            "score or probability fields",
            "threshold_value",
            "threshold source",
            "merge_prediction",
            "threshold_name",
            "selection_split",
            "selection_metric",
            "selection_rule",
            "applied_scope",
            "score_field",
            "## DKE/Elsevier Preflight Package Checks",
            "python manuscript/scripts/build_submission_package.py --dke-preflight",
            "python manuscript/scripts/validate_submission_package.py --dke-preflight",
            "build/iad-risk-dke-preflight-package.zip",
            "iad-risk-manuscript-elsevier.tex",
            "iad-risk-manuscript-elsevier.pdf",
            "Passing this check does not complete the final-upload gate.",
            "## Publisher Declaration Checks",
            "The declaration text matches submission_metadata.yml.",
            "No declaration placeholder remains before final upload.",
            "The funding role is stated when funding exists.",
            "Permission files are listed when third-party permission is required.",
            "The data availability statement matches artifact release status.",
            "The generative AI declaration records AI tool use status, author review and responsibility, AI authorship exclusion, and whether any machine-generated figures, images, or artwork are included.",
            "`author_identity_materials`, `biography_files`, `photograph_files`, and `author_identity_materials_verified` are completed before `author_biographies_and_photos_ready` is marked true.",
            "## Cover Letter Customization Checks",
            "The cover letter names the selected target journal.",
            "The cover letter states the final article type.",
            "The corresponding author name appears in the cover letter.",
            "The artifact URL or DOI appears in the cover letter when available.",
            "The artifact manifest publication object records the same public artifact URL or DOI as `submission_metadata.yml`.",
            "The artifact manifest `publication.public_access_status` records the public access state.",
            "The cover letter no longer uses the generic Dear Editor greeting.",
            "The cover letter no longer uses an anonymous author signature.",
            "## Source Archive Assembly Checks",
            "The source archive contains editable LaTeX sources.",
            "The source archive includes references.bib and submission text files.",
            "The source archive includes manifest and checksum files.",
            "The source archive excludes build caches and generated zip files.",
            "The source archive is rebuilt after template conversion.",
            "## Source-Control Binding Checks",
            "The tracked source `submission_metadata.yml` can keep `repository_reference` blank before final upload.",
            "python manuscript/scripts/build_submission_package.py --final-upload",
            "The builder writes `repository_url`, `repository_commit`, and `repository_branch` into the package copy of `submission_metadata.yml`.",
            "The package copy of `submission_metadata.yml` is bound to git remote origin.",
            "The package copy is bound to git rev-parse HEAD.",
            "`submission_manifest.json` records the same `repository_commit` as the package copy.",
            "python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release",
            "The external artifact release is finalized before final-upload package validation.",
            "## Live Submission Text Checks",
            "Title, abstract, keywords, and highlights are copied from the current source files.",
            "The title and abstract match `main.tex` after journal-template conversion.",
            "Keywords match `keywords.md` exactly unless the selected journal requires a documented wording change.",
            "Highlights match `highlights.md` exactly unless the selected journal does not collect highlights.",
            "The live submission system preview shows the same title, abstract, keywords, and highlights.",
            "Mark `submission_system_files_verified`, `live_submission_system_verified`, and `final_upload_package_verified_against_system` true after the final package preview.",
            "## First-Screen Claim Lockdown Checks",
            "`cover_letter.md`, `highlights.md`, `keywords.md`, the abstract, and the conclusion describe the same problem, method, Open-v2 evidence snapshot, and claim boundary.",
            "Any journal-specific edit keeps the Open-v2 numbers scope-bounded.",
            "It preserves the distinction between full pair scope and held-out test scope.",
            "No first-screen material claims broad method superiority.",
            "No first-screen material claims SOTA ranking.",
            "No first-screen material claims statistical superiority.",
            "No first-screen material claims threshold stability.",
            "No first-screen material claims human-gold validation.",
            "No first-screen material claims Q2/B completion.",
            "No first-screen material claims final-upload readiness.",
            "No first-screen material claims cluster-level deployment quality.",
            "Artifact URL or DOI insertion does not upgrade the scientific claim.",
            "The optional evidence includes bootstrap intervals, threshold grids, ablations, manual-validation slice, or cluster artifacts.",
            "After edits, rerun `python manuscript/scripts/validate_manuscript.py --strict-latex`.",
            "Then rebuild the submission package before upload.",
            "## Final Metadata Checks",
            "The selected journal template matches the final manuscript source.",
            "`selected_author_guide_source`, `selected_author_guide_rechecked_date`, and `selected_template_requirements_confirmed` are complete before final upload.",
            "`ranking_confirmation_completed`, `ranking_confirmation_source`, `ranking_confirmation_checked_date`, and `selected_target_author_confirmed` are complete before final upload.",
            "`live_submission_system_verified` and `final_upload_package_verified_against_system` are true.",
            "The funding statement is completed and matches the manuscript and submission system.",
            "The author contribution statement is completed before final upload.",
            "The permissions statement records third-party material permission status.",
            "The generative AI declaration statement is complete and matches the selected journal's live submission field.",
            "## File Hygiene Checks",
            "No `data/`, `outputs/`, cache, local connection, credential, or raw third-party file.",
            "Anonymous packages contain no author email addresses, ORCID values, personal account URLs, local absolute paths, or development process notes.",
            "## Current Blocking Items",
            "Target journal has not been author-confirmed.",
            "Artifact release URL or DOI has not been created.",
        ]
    )

    errors = module.check_submission_system_checklist(checklist_text)

    assert errors == []


def test_check_submission_system_checklist_rejects_missing_hygiene_boundary() -> None:
    """验证投稿系统上传清单缺少文件卫生边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checklist_text = "# Submission System Checklist\n## Required Upload Files\nMain manuscript source"

    errors = module.check_submission_system_checklist(checklist_text)

    assert any("File Hygiene Checks" in error for error in errors)
    assert any("raw third-party file" in error for error in errors)
    assert any("author email addresses" in error for error in errors)
    assert any("Artifact release URL or DOI" in error for error in errors)


def test_check_submission_system_checklist_rejects_missing_template_bound_field() -> None:
    """验证投稿系统清单必须显式核对目标期刊模板绑定字段。"""

    module = _load_validate_manuscript_module()
    checklist_text = Path("manuscript/submission_system_checklist.md").read_text(encoding="utf-8")
    checklist_text = checklist_text.replace("target_journal_template_bound", "target_journal_template")
    checklist_text = checklist_text.replace("selected journal template matches the final manuscript source", "template is checked")

    errors = module.check_submission_system_checklist(checklist_text)

    assert any("target_journal_template_bound" in error for error in errors)
    assert any("selected journal template matches the final manuscript source" in error for error in errors)


def test_check_submission_system_checklist_rejects_missing_live_text_checks() -> None:
    """验证投稿系统清单必须覆盖首屏文本与源文件一致性检查。"""

    module = _load_validate_manuscript_module()
    checklist_text = Path("manuscript/submission_system_checklist.md").read_text(encoding="utf-8")
    checklist_text = checklist_text.replace("## Live Submission Text Checks", "## Removed live text checks")
    checklist_text = checklist_text.replace(
        "Title, abstract, keywords, and highlights are copied from the current source files",
        "Submission text fields are reviewed",
    )
    checklist_text = checklist_text.replace("Keywords match `keywords.md` exactly", "Keywords are reviewed")
    checklist_text = checklist_text.replace("Highlights match `highlights.md` exactly", "Highlights are reviewed")

    errors = module.check_submission_system_checklist(checklist_text)

    assert any("Live Submission Text Checks" in error for error in errors)
    assert any("Title, abstract, keywords, and highlights are copied" in error for error in errors)
    assert any("Keywords match `keywords.md` exactly" in error for error in errors)
    assert any("Highlights match `highlights.md` exactly" in error for error in errors)


def test_check_submission_system_checklist_rejects_missing_first_screen_lockdown() -> None:
    """验证投稿系统清单必须覆盖首屏主张锁定。"""

    module = _load_validate_manuscript_module()
    checklist_text = Path("manuscript/submission_system_checklist.md").read_text(encoding="utf-8")
    checklist_text = checklist_text.replace("## First-Screen Claim Lockdown Checks", "## Removed claim lockdown")
    checklist_text = checklist_text.replace(
        "`cover_letter.md`, `highlights.md`, `keywords.md`, the abstract, and the conclusion",
        "submission text files",
    )
    checklist_text = checklist_text.replace("No first-screen material claims broad method superiority", "Claims are reviewed")
    checklist_text = checklist_text.replace(
        "Artifact URL or DOI insertion does not upgrade the scientific claim",
        "Artifact link is inserted",
    )

    errors = module.check_submission_system_checklist(checklist_text)

    assert any("First-Screen Claim Lockdown Checks" in error for error in errors)
    assert any("cover_letter.md" in error for error in errors)
    assert any("broad method superiority" in error for error in errors)
    assert any("Artifact URL or DOI insertion" in error for error in errors)


def test_check_submission_system_checklist_rejects_missing_publisher_declarations() -> None:
    """验证投稿系统清单缺少出版声明一致性检查时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checklist_text = "\n".join(
        [
            "# Submission System Checklist",
            "This is not a manuscript file for journal upload.",
            "## Required Upload Files",
            "Main manuscript source",
            "Main manuscript PDF",
            "DKE/Elsevier preflight source",
            "DKE/Elsevier preflight PDF",
            "Supplementary source",
            "Supplementary PDF",
            "Bibliography",
            "Cover letter",
            "Highlights",
            "Keywords",
            "Submission metadata",
            "Artifact release manifest",
            "## Artifact Release Package Checks",
            "python manuscript/scripts/build_artifact_release_skeleton.py --output-dir /path/to/release --repository-commit",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
            "checks required source artifact files before anything is copied",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
            "python -m iad_sieve.cli --help",
            "same repository checkout named by the release manifest",
            "## DKE/Elsevier Preflight Package Checks",
            "python manuscript/scripts/build_submission_package.py --dke-preflight",
            "python manuscript/scripts/validate_submission_package.py --dke-preflight",
            "build/iad-risk-dke-preflight-package.zip",
            "iad-risk-manuscript-elsevier.tex",
            "iad-risk-manuscript-elsevier.pdf",
            "Passing this check does not complete the final-upload gate.",
            "## Final Metadata Checks",
            "The funding statement is completed and matches the manuscript and submission system.",
            "The author contribution statement is completed before final upload.",
            "The permissions statement records third-party material permission status.",
            "## File Hygiene Checks",
            "No `data/`, `outputs/`, cache, local connection, credential, or raw third-party file.",
            "Anonymous packages contain no author email addresses, ORCID values, personal account URLs, local absolute paths, or development process notes.",
            "## Current Blocking Items",
            "Target journal has not been author-confirmed.",
            "Artifact release URL or DOI has not been created.",
        ]
    )

    errors = module.check_submission_system_checklist(checklist_text)

    assert any("Publisher Declaration Checks" in error for error in errors)
    assert any("declaration text matches submission_metadata.yml" in error for error in errors)
    assert any("data availability statement matches artifact release status" in error for error in errors)


def test_check_submission_system_checklist_rejects_missing_cover_letter_customization() -> None:
    """验证投稿系统清单缺少投稿信定制检查时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checklist_text = "\n".join(
        [
            "# Submission System Checklist",
            "This is not a manuscript file for journal upload.",
            "## Required Upload Files",
            "Main manuscript source",
            "Main manuscript PDF",
            "DKE/Elsevier preflight source",
            "DKE/Elsevier preflight PDF",
            "Supplementary source",
            "Supplementary PDF",
            "Bibliography",
            "Cover letter",
            "Highlights",
            "Keywords",
            "Submission metadata",
            "Artifact release manifest",
            "## Artifact Release Package Checks",
            "python manuscript/scripts/build_artifact_release_skeleton.py --output-dir /path/to/release --repository-commit",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
            "checks required source artifact files before anything is copied",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
            "python -m iad_sieve.cli --help",
            "same repository checkout named by the release manifest",
            "## DKE/Elsevier Preflight Package Checks",
            "python manuscript/scripts/build_submission_package.py --dke-preflight",
            "python manuscript/scripts/validate_submission_package.py --dke-preflight",
            "build/iad-risk-dke-preflight-package.zip",
            "iad-risk-manuscript-elsevier.tex",
            "iad-risk-manuscript-elsevier.pdf",
            "Passing this check does not complete the final-upload gate.",
            "## Publisher Declaration Checks",
            "The declaration text matches submission_metadata.yml.",
            "No declaration placeholder remains before final upload.",
            "The funding role is stated when funding exists.",
            "Permission files are listed when third-party permission is required.",
            "The data availability statement matches artifact release status.",
            "## Final Metadata Checks",
            "The funding statement is completed and matches the manuscript and submission system.",
            "The author contribution statement is completed before final upload.",
            "The permissions statement records third-party material permission status.",
            "## File Hygiene Checks",
            "No `data/`, `outputs/`, cache, local connection, credential, or raw third-party file.",
            "Anonymous packages contain no author email addresses, ORCID values, personal account URLs, local absolute paths, or development process notes.",
            "## Current Blocking Items",
            "Target journal has not been author-confirmed.",
            "Artifact release URL or DOI has not been created.",
        ]
    )

    errors = module.check_submission_system_checklist(checklist_text)

    assert any("Cover Letter Customization Checks" in error for error in errors)
    assert any("selected target journal" in error for error in errors)
    assert any("anonymous author signature" in error for error in errors)


def test_check_submission_system_checklist_rejects_missing_source_archive_checks() -> None:
    """验证投稿系统清单缺少源文件压缩包组装检查时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checklist_text = "\n".join(
        [
            "# Submission System Checklist",
            "This is not a manuscript file for journal upload.",
            "## Required Upload Files",
            "Main manuscript source",
            "Main manuscript PDF",
            "DKE/Elsevier preflight source",
            "DKE/Elsevier preflight PDF",
            "Supplementary source",
            "Supplementary PDF",
            "Bibliography",
            "Cover letter",
            "Highlights",
            "Keywords",
            "Submission metadata",
            "Artifact release manifest",
            "## Artifact Release Package Checks",
            "python manuscript/scripts/build_artifact_release_skeleton.py --output-dir /path/to/release --repository-commit",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
            "checks required source artifact files before anything is copied",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
            "python -m iad_sieve.cli --help",
            "same repository checkout named by the release manifest",
            "## DKE/Elsevier Preflight Package Checks",
            "python manuscript/scripts/build_submission_package.py --dke-preflight",
            "python manuscript/scripts/validate_submission_package.py --dke-preflight",
            "build/iad-risk-dke-preflight-package.zip",
            "iad-risk-manuscript-elsevier.tex",
            "iad-risk-manuscript-elsevier.pdf",
            "Passing this check does not complete the final-upload gate.",
            "## Publisher Declaration Checks",
            "The declaration text matches submission_metadata.yml.",
            "No declaration placeholder remains before final upload.",
            "The funding role is stated when funding exists.",
            "Permission files are listed when third-party permission is required.",
            "The data availability statement matches artifact release status.",
            "## Cover Letter Customization Checks",
            "The cover letter names the selected target journal.",
            "The cover letter states the final article type.",
            "The corresponding author name appears in the cover letter.",
            "The artifact URL or DOI appears in the cover letter when available.",
            "The cover letter no longer uses the generic Dear Editor greeting.",
            "The cover letter no longer uses an anonymous author signature.",
            "## Final Metadata Checks",
            "The funding statement is completed and matches the manuscript and submission system.",
            "The author contribution statement is completed before final upload.",
            "The permissions statement records third-party material permission status.",
            "## File Hygiene Checks",
            "No `data/`, `outputs/`, cache, local connection, credential, or raw third-party file.",
            "Anonymous packages contain no author email addresses, ORCID values, personal account URLs, local absolute paths, or development process notes.",
            "## Current Blocking Items",
            "Target journal has not been author-confirmed.",
            "Artifact release URL or DOI has not been created.",
        ]
    )

    errors = module.check_submission_system_checklist(checklist_text)

    assert any("Source Archive Assembly Checks" in error for error in errors)
    assert any("editable LaTeX sources" in error for error in errors)
    assert any("generated zip files" in error for error in errors)


def test_check_submission_system_checklist_rejects_missing_artifact_dir_final_upload_validation() -> None:
    """验证投稿系统清单必须要求最终包校验绑定 artifact release 目录。"""

    module = _load_validate_manuscript_module()
    checklist_text = Path("manuscript/submission_system_checklist.md").read_text(encoding="utf-8")
    checklist_text = checklist_text.replace(
        "python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release",
        "python manuscript/scripts/validate_submission_package.py --final-upload",
    )
    checklist_text = checklist_text.replace("external artifact release is finalized", "artifact release exists")

    errors = module.check_submission_system_checklist(checklist_text)

    assert any("validate_submission_package.py --final-upload --artifact-dir" in error for error in errors)
    assert any("external artifact release is finalized" in error for error in errors)


def test_check_submission_system_checklist_rejects_missing_artifact_release_checks() -> None:
    """验证投稿系统清单缺少 artifact release 校验命令时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checklist_text = "\n".join(
        [
            "# Submission System Checklist",
            "This is not a manuscript file for journal upload.",
            "## Required Upload Files",
            "Main manuscript source",
            "Main manuscript PDF",
            "DKE/Elsevier preflight source",
            "DKE/Elsevier preflight PDF",
            "Supplementary source",
            "Supplementary PDF",
            "Bibliography",
            "Cover letter",
            "Highlights",
            "Keywords",
            "Submission metadata",
            "Artifact release manifest",
            "## DKE/Elsevier Preflight Package Checks",
            "python manuscript/scripts/build_submission_package.py --dke-preflight",
            "python manuscript/scripts/validate_submission_package.py --dke-preflight",
            "build/iad-risk-dke-preflight-package.zip",
            "iad-risk-manuscript-elsevier.tex",
            "iad-risk-manuscript-elsevier.pdf",
            "Passing this check does not complete the final-upload gate.",
            "## Final Metadata Checks",
            "## File Hygiene Checks",
            "No `data/`, `outputs/`, cache, local connection, credential, or raw third-party file.",
            "Anonymous packages contain no author email addresses, ORCID values, personal account URLs, local absolute paths, or development process notes.",
            "## Current Blocking Items",
            "Target journal has not been author-confirmed.",
            "Artifact release URL or DOI has not been created.",
        ]
    )

    errors = module.check_submission_system_checklist(checklist_text)

    assert any("Artifact Release Package Checks" in error for error in errors)
    assert any("validate_artifact_release.py" in error for error in errors)
    assert any("python -m iad_sieve.cli --help" in error for error in errors)


def test_check_submission_system_checklist_rejects_missing_artifact_cli_discovery_command() -> None:
    """验证投稿系统清单必须同步 artifact release CLI discovery 命令。"""

    module = _load_validate_manuscript_module()
    checklist_text = Path("manuscript/submission_system_checklist.md").read_text(encoding="utf-8")
    for marker in [
        "python -m iad_sieve.cli --help",
        "same repository checkout named by the release manifest",
    ]:
        checklist_text = checklist_text.replace(marker, "")

    errors = module.check_submission_system_checklist(checklist_text)

    assert any("python -m iad_sieve.cli --help" in error for error in errors)
    assert any("same repository checkout named by the release manifest" in error for error in errors)


def test_check_submission_system_checklist_rejects_missing_artifact_row_schema_checks() -> None:
    """验证投稿系统清单必须覆盖结果表和预测 artifact 行级 schema 检查。"""

    module = _load_validate_manuscript_module()
    checklist_text = Path("manuscript/submission_system_checklist.md").read_text(encoding="utf-8")
    for marker in [
        "open_v2_main_results",
        "per-row denominator counts",
        "per-row threshold source",
        "scope label used in the main table",
        "automatic merge count",
        "block count",
        "defer count",
        "automatic merge coverage",
        "defer rate",
        "capacity-normalized review load",
        "iad_risk_predictions",
        "representation_baseline_scores",
        "supervised_baseline_predictions",
        "threshold_selection_logs",
        "pair_id",
        "source_document_id",
        "target_document_id",
        "label strength",
        "hard-negative level",
        "split identifiers",
        "score or probability fields",
        "threshold_value",
        "threshold source",
        "merge_prediction",
        "threshold_name",
        "selection_split",
        "selection_metric",
        "selection_rule",
        "applied_scope",
        "score_field",
    ]:
        checklist_text = checklist_text.replace(marker, "")

    errors = module.check_submission_system_checklist(checklist_text)

    assert any("open_v2_main_results" in error for error in errors)
    assert any("per-row denominator counts" in error for error in errors)
    assert any("per-row threshold source" in error for error in errors)
    assert any("scope label used in the main table" in error for error in errors)
    assert any("automatic merge coverage" in error for error in errors)
    assert any("defer rate" in error for error in errors)
    assert any("capacity-normalized review load" in error for error in errors)
    assert any("iad_risk_predictions" in error for error in errors)
    assert any("threshold_selection_logs" in error for error in errors)
    assert any("pair_id" in error for error in errors)
    assert any("threshold_value" in error for error in errors)
    assert any("merge_prediction" in error for error in errors)
    assert any("selection_rule" in error for error in errors)


def test_check_submission_system_checklist_rejects_missing_declaration_gate_fields() -> None:
    """验证投稿系统清单缺少正式声明门禁字段时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checklist_text = "\n".join(
        [
            "# Submission System Checklist",
            "This is not a manuscript file for journal upload.",
            "## Required Upload Files",
            "Main manuscript source",
            "Main manuscript PDF",
            "DKE/Elsevier preflight source",
            "DKE/Elsevier preflight PDF",
            "Supplementary source",
            "Supplementary PDF",
            "Bibliography",
            "Cover letter",
            "Highlights",
            "Keywords",
            "Submission metadata",
            "Artifact release manifest",
            "## Artifact Release Package Checks",
            "python manuscript/scripts/build_artifact_release_skeleton.py --output-dir /path/to/release --repository-commit",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
            "checks required source artifact files before anything is copied",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
            "python -m iad_sieve.cli --help",
            "same repository checkout named by the release manifest",
            "## DKE/Elsevier Preflight Package Checks",
            "python manuscript/scripts/build_submission_package.py --dke-preflight",
            "python manuscript/scripts/validate_submission_package.py --dke-preflight",
            "build/iad-risk-dke-preflight-package.zip",
            "iad-risk-manuscript-elsevier.tex",
            "iad-risk-manuscript-elsevier.pdf",
            "Passing this check does not complete the final-upload gate.",
            "## Final Metadata Checks",
            "The author list, order, affiliations, ORCID values, and corresponding author match the title page.",
            "The artifact release URL or DOI resolves publicly or according to the journal's access policy.",
            "## File Hygiene Checks",
            "No `data/`, `outputs/`, cache, local connection, credential, or raw third-party file.",
            "Anonymous packages contain no author email addresses, ORCID values, personal account URLs, local absolute paths, or development process notes.",
            "## Current Blocking Items",
            "Target journal has not been author-confirmed.",
            "Artifact release URL or DOI has not been created.",
        ]
    )

    errors = module.check_submission_system_checklist(checklist_text)

    assert any("funding statement" in error for error in errors)
    assert any("author contribution statement" in error for error in errors)
    assert any("permissions statement" in error for error in errors)


def test_check_submission_system_checklist_rejects_missing_dke_preflight_package() -> None:
    """验证投稿系统上传清单缺少DKE预投稿包检查时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checklist_text = "\n".join(
        [
            "# Submission System Checklist",
            "This is not a manuscript file for journal upload.",
            "## Required Upload Files",
            "Main manuscript source",
            "Main manuscript PDF",
            "Supplementary source",
            "Supplementary PDF",
            "Bibliography",
            "Cover letter",
            "Highlights",
            "Keywords",
            "Submission metadata",
            "Artifact release manifest",
            "## Final Metadata Checks",
            "## File Hygiene Checks",
            "No `data/`, `outputs/`, cache, local connection, credential, or raw third-party file.",
            "Anonymous packages contain no author email addresses, ORCID values, personal account URLs, local absolute paths, or development process notes.",
            "## Current Blocking Items",
            "Target journal has not been author-confirmed.",
            "Artifact release URL or DOI has not been created.",
        ]
    )

    errors = module.check_submission_system_checklist(checklist_text)

    assert any("DKE/Elsevier Preflight Package Checks" in error for error in errors)
    assert any("--dke-preflight" in error for error in errors)
    assert any("does not complete the final-upload gate" in error for error in errors)


def test_check_reviewer_readiness_audit_accepts_complete_audit() -> None:
    """验证审稿准备度审计覆盖维度、风险和最终门槛时可通过。"""

    module = _load_validate_manuscript_module()
    audit_text = "\n".join(
        [
            "# Reviewer Readiness Audit",
            "Current decision: conditionally ready for target-journal selection; not ready for final upload.",
            "## Audit Iteration Summary",
            "Completed audit cycles: 84.",
            "Highest current reviewer-facing risks: final-upload metadata, target-journal template binding, author-guide/template confirmation gap, target ranking confirmation gap, live final-package system verification gap, DKE author biography and photograph materials, author identity material traceability, external artifact release, artifact source directory completeness, artifact release validation bypass, final-upload artifact-dir omission bypass, artifact publication link mismatch, zero-observed HNFMR overread, L2 public-source rebuild chain-of-custody gap, selective-decision workload evidence, anonymous cover-letter declaration confirmation, preflight metadata declaration placeholders, preflight manuscript declaration boundary, introduction row-scope comparison overread, artifact release README completeness, artifact release commit validity, artifact README/manifest commit mismatch, final package/artifact commit mismatch, final-upload artifact-dir instruction drift, prediction artifact schema drift, generative AI declaration consistency, fixture/live evidence confusion, live submission-system text consistency, Git-only full-numerical audit overread, source-to-PDF package consistency, final-upload source-control package binding, final-upload artifact publication binding, and stronger evidence gates.",
            "Current stopping rule: do not claim Q2/B completion or final-upload readiness until `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release` passes, a real artifact URL or DOI is recorded, the selected target journal, author-guide source, template requirements, and ranking/category status are author-confirmed from authorized sources, the live submission system and final package preview are verified against the source package, and the artifact manifest publication object records the same URL or DOI with public access status.",
            "Non-code external inputs still required: author metadata, DKE author biography and photograph materials, target-journal confirmation, selected author-guide source and rechecked date, template requirements confirmation, ranking/category confirmation source and date, funding statement, author contribution statement, permissions statement, generative AI declaration, live submission-system fields, and artifact release URL or DOI.",
            "Next revision trigger: repeat the editorial desk check after target-journal template binding, cover-letter customization, or artifact-link insertion.",
            "## Audit Dimensions",
            "Contribution",
            "Writing clarity",
            "Experimental strength",
            "Evaluation completeness",
            "Method design soundness",
            "## Reviewer Risk Register",
            "Silver hard negatives may not be true non-identity labels.",
            "Threshold results may be sensitive.",
            "Confidence intervals and statistical significance may be overread.",
            "The current manuscript reports point estimates and reserves bootstrap intervals.",
            "No statistical significance claim is made.",
            "Live submission-system text may drift from source files.",
            "Reproducibility depends on files outside Git.",
            "## Claim-Evidence Check",
            "## Adversarial Self-Review Matrix",
            "`pass`, `needs revision`, and `needs new experiment` are strict status values.",
            "Contribution self-review",
            "Writing clarity self-review",
            "Experimental strength self-review",
            "Evaluation completeness self-review",
            "Method design soundness self-review",
            "The stronger package requires same-scope prediction files.",
            "It also requires artifact-backed ablations.",
            "## Reviewer Response Matrix",
            "This matrix anticipates likely reviewer questions.",
            "A reviewer may ask about identity-agenda confusion.",
            "The response discusses silver hard negatives.",
            "The table is a scope-bounded evidence snapshot.",
            "It presents RoBERTa as a strong baseline.",
            "The current evidence is mechanism-consistent.",
            "The repository supports fixture-level code reproduction.",
            "## Audit Cycle 1: Claim Discipline",
            "## Audit Cycle 2: Submission Readiness",
            "## Audit Cycle 3: Q2/B Acceptance Gate",
            "remote reproducibility",
            "strong model matrix",
            "model superiority",
            "innovation depth",
            "novelty and prior-art positioning",
            "claim lockdown",
            "## Audit Cycle 4: Final Package Hygiene",
            "anonymous package hygiene",
            "## Audit Cycle 5: Editorial Desk Check",
            "title, abstract, conclusion, cover letter, highlights, and keywords",
            "editorial claim alignment",
            "author email addresses, ORCID values, personal account URLs, local absolute paths, and development process notes",
            "## Audit Cycle 6: Reviewer Rebuttal Boundary",
            "ready_to_answer",
            "limited_answer",
            "do_not_answer_as_claim",
            "safe response scope",
            "must-not-claim boundary",
            "## Revision Trigger Register",
            "reviewer concern triggers a concrete manuscript revision",
            "Contribution trigger",
            "Writing clarity trigger",
            "Experimental strength trigger",
            "Evaluation completeness trigger",
            "Method design soundness trigger",
            "weaken the claim",
            "add artifact-backed evidence",
            "do not upgrade the abstract, introduction, conclusion, cover letter, or highlights",
            "## Audit Cycle 7: Journal Fit and Novelty Desk Check",
            "desk-rejection risk",
            "target-journal scope fit",
            "novelty beyond ordinary entity matching",
            "Data & Knowledge Engineering",
            "Information Systems",
            "Scientometrics",
            "## Audit Cycle 8: Pair-to-Cluster Claim Lockdown",
            "pair-level metrics",
            "cluster-level deployment quality",
            "cluster artifacts",
            "cluster_metric_summary",
            "cannot_link_audit",
            "cover letter, highlights, and conclusion",
            "artifact-backed audits",
            "## Audit Cycle 9: Artifact Row-Level Result Audit",
            "open_v2_main_results",
            "per-row denominator counts",
            "per-row threshold source",
            "scope label used in the main table",
            "automatic merge count",
            "block count",
            "defer count",
            "automatic merge coverage",
            "defer rate",
            "capacity-normalized review load",
            "validate_artifact_release.py",
            "## Audit Cycle 34: Selective Decision Workload Boundary Gate",
            "selective-decision workload wording",
            "operational throughput or cost-saving claims",
            "## Audit Cycle 35: Anonymous Cover-Letter Declaration Boundary Gate",
            "anonymous preflight cover-letter boundary",
            "author-provided metadata confirms originality",
            "competing-interest status",
            "author contribution",
            "generative AI declarations",
            "does not treat author declarations as finalized",
            "## Audit Cycle 36: Preflight Metadata Declaration Placeholder Gate",
            "tracked metadata declaration placeholders",
            "statements.originality",
            "statements.author_approval",
            "statements.competing_interests",
            "structured metadata integrity",
            "## Audit Cycle 37: Preflight Manuscript Declaration Boundary Gate",
            "anonymous preflight manuscript declaration boundary",
            "competing-interest declaration is not finalized",
            "listed authors confirm the competing-interest status",
            "submission_metadata.yml",
            "live submission system",
            "declaration authority",
            "## Audit Cycle 38: Introduction Row-Scope Comparison Boundary Gate",
            "shared Open-v2 pair schema",
            "row-scope differences between full-scope baselines and held-out IAD-Risk rows",
            "same-scope ranking implication",
            "contribution paragraph",
            "## Audit Cycle 39: Installable CLI Entry-Point Traceability Gate",
            "Git-only command discovery and source entry-point binding",
            "`src/iad_sieve`",
            "`pyproject.toml`",
            "`iad-sieve = iad_sieve.cli:main`",
            "`python -m iad_sieve.cli --help`",
            "argparse command discovery",
            "tracked source contract",
            "Git-only reviewers can discover the CLI",
            "## Audit Cycle 40: Artifact Source Preflight Gate",
            "source artifact completeness preflight coverage",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
            "checks required source artifact paths",
            "optional mapping paths",
            "without copying files",
            "artifact_population_log.jsonl",
            "source-package readiness",
            "row-level schemas",
            "validate_submission_package.py --final-upload --artifact-dir /path/to/release",
            "## Audit Cycle 10: Final Template Binding and System Metadata Gate",
            "target_journal_template_bound",
            "target_journal_template_applied",
            "source archive rebuilt after template conversion",
            "selected journal template matches the final manuscript source",
            "DKE/Elsevier preflight package",
            "## Audit Cycle 11: Live Submission Text Consistency Gate",
            "submission_system_files_verified",
            "title, abstract, keywords, and highlights",
            "`main.tex`",
            "`keywords.md`",
            "`highlights.md`",
            "live submission system preview",
            "## Audit Cycle 12: Git-Only Fixture Reproducibility Gate",
            "python manuscript/scripts/verify_fixture_rebuild.py",
            "python scripts/check_public_release.py",
            "no-network code-path evidence",
            "data adapters, CLI entry points, schema contracts, and IAD-Bench assembly path",
            "does not prove the Open-v2 numerical table",
            "## Audit Cycle 13: Submission Package Source-PDF Consistency Gate",
            "packaged PDFs",
            "source dependencies",
            "main PDF",
            "supplementary PDF",
            "DKE/Elsevier preflight PDF",
            "rebuild PDF before packaging",
            "## Audit Cycle 14: Source-Control Manifest Binding Gate",
            "source_control",
            "repository_commit",
            "repository_branch",
            "worktree_dirty",
            "tracked_state",
            "matches `submission_metadata.yml`",
            "final package is rebuilt from the submitted repository commit",
            "## Audit Cycle 15: Artifact Release Commit Validity Gate",
            "7 to 40 character hexadecimal Git commit",
            "repository.commit",
            "artifact release skeleton builder and validator",
            "same committed source revision as the final manuscript package",
            "## Audit Cycle 16: Artifact Release README Reproducibility Gate",
            "README.md",
            "manifest.json",
            "checksums.sha256",
            "raw third-party data exclusions",
            "data policy",
            "reproduction levels",
            "claim boundaries",
            "## Audit Cycle 17: Final-Upload Source-Control Package Binding Gate",
            "tracked `submission_metadata.yml`",
            "cannot reliably contain the Git commit of the commit that contains itself",
            "writes `repository_url`, `repository_commit`, `repository_branch`",
            "matching data/code availability statement",
            "final package metadata and `submission_manifest.json` agree",
            "## Audit Cycle 18: Prediction Artifact Schema Gate",
            "row-level prediction schema enforced by `validate_artifact_release.py`",
            "iad_risk_predictions",
            "representation_baseline_scores",
            "supervised_baseline_predictions",
            "threshold_selection_logs",
            "pair_id",
            "source_document_id",
            "target_document_id",
            "label strength",
            "hard-negative level",
            "split identifiers",
            "score or probability fields",
            "threshold_value",
            "threshold source",
            "merge_prediction",
            "threshold_name",
            "selection_split",
            "selection_metric",
            "selection_rule",
            "applied_scope",
            "score_field",
            "recompute row-level decisions, denominators, and fixed operating points",
            "## Audit Cycle 19: Generative AI Declaration Gate",
            "publisher-required AI-tool disclosure",
            "removable process notes",
            "AI-tool use status",
            "author review and responsibility",
            "AI tools are not listed as authors",
            "machine-generated figures, images, or artwork",
            "generative_ai_declaration_complete",
            "## Audit Cycle 20: Fixture Evidence Isolation Gate",
            "test fixtures from being mistaken for current manuscript evidence",
            "Unit-test fixtures",
            "generated fixture reports",
            "validator coverage only",
            "live outputs regenerated from the current repository commit",
            "current live artifacts",
            "current commit metadata",
            "data/",
            "outputs/",
            "## Audit Cycle 21: DKE Author Biography and Photograph Gate",
            "author-approved biography text and photograph files",
            "short biography for each author and a passport-type photograph",
            "final-upload workflow must collect them",
            "## Audit Cycle 22: Method Execution Traceability Gate",
            "method-writing clarity",
            "training and inference trace",
            "schema loading",
            "masked supervision",
            "threshold fixation",
            "pair scoring",
            "decision emission",
            "metric export",
            "relation-head predictions",
            "## Audit Cycle 23: First-Screen Claim Lockdown Gate",
            "final-upload checklist coverage",
            "first-screen upgrades",
            "SOTA ranking",
            "statistical superiority",
            "human-gold validation",
            "Q2/B completion",
            "## Audit Cycle 24: Final-Upload Claim-Lock Metadata Gate",
            "first_screen_claim_lockdown_confirmed",
            "metadata-validator coverage",
            "live system preview",
            "## Audit Cycle 25: Artifact README-Manifest Commit Consistency Gate",
            "README.md",
            "Repository commit",
            "manifest.json",
            "repository.commit",
            "commit-consistency coverage",
            "same source revision",
            "## Audit Cycle 26: Final Package-Artifact Commit Binding Gate",
            "submission-package validator coverage",
            "validate_submission_package.py --final-upload --artifact-dir",
            "artifact manifest",
            "submission_metadata.yml",
            "repository_commit",
            "## Audit Cycle 27: Final-Upload Artifact-Dir Instruction Consistency Gate",
            "final-upload instruction coverage",
            "final_upload_information_request.md",
            "submission_system_checklist.md",
            "older command without `--artifact-dir`",
            "## Audit Cycle 28: Final-Upload Artifact Release Validation Gate",
            "integrated artifact-release validation coverage",
            "required artifact IDs",
            "Open-v2 row-level audit columns",
            "prediction JSONL fields",
            "claim-dependent artifact requirements",
            "## Audit Cycle 29: Final-Upload Artifact-Dir Required Gate",
            "missing artifact-directory rejection",
            "finalized artifact release directory",
            "omit `--artifact-dir`",
            "local checksum, manifest, row-schema, prediction-schema, and package-artifact commit checks",
            "cannot bypass the external release directory",
            "## Audit Cycle 30: Main-Manuscript Artifact Validation Text Gate",
            "manuscript-level reproducibility wording",
            "Data and Code Availability section",
            "validate_artifact_release.py --artifact-dir /path/to/release",
            "validate_submission_package.py --final-upload --artifact-dir /path/to/release",
            "source-control commit",
            "main text tells reviewers",
            "should not be used to support the Open-v2 numerical table",
            "## Audit Cycle 31: Zero-Observed HNFMR Wording Gate",
            "first-screen zero-risk overread control",
            "zero observed HNFMR rather than as wording that can be read as absolute zero risk",
            "first-screen prose",
            "no hard-negative false merge was observed",
            "does not prove zero risk under all scholarly sources",
            "## Audit Cycle 32: L2 Public-Source Rebuild Traceability Gate",
            "L2 public-source rebuild traceability wording",
            "source_input_manifest",
            "processing_run_log",
            "output summaries",
            "chain of custody",
            "real public-source inputs",
            "alongside result tables, predictions, threshold logs, and split summaries",
            "## Audit Cycle 33: Main-Text L2 Provenance Alignment Gate",
            "main-text L2 provenance alignment",
            "reproduction-level table",
            "result audit trail",
            "result artifact crosswalk",
            "Data and Code Availability section now state",
            "source-to-result alignment",
            "same provenance vocabulary",
            "supplemental-only instructions",
            "## Audit Cycle 41: Main-Text Schema Density Gate",
            "main-text schema-density reduction",
            "document-schema and pair-schema tables",
            "## Audit Cycle 42: Related-Work Positioning Density Gate",
            "closest-work positioning matrix",
            "positioning matrix",
            "## Audit Cycle 43: Method Design Boundary Density Gate",
            "operational net-benefit and version-identifier matrices",
            "method-design tables",
            "## Audit Cycle 44: Experiment Reporting Boundary Density Gate",
            "Experiments table-density reduction",
            "threshold and uncertainty reporting protocol table",
            "statistical interpretation boundary table",
            "experimental interpretability without table overload",
            "## Audit Cycle 45: Result Artifact Crosswalk Density Gate",
            "result-audit table-density reduction",
            "row-level audit requirements",
            "prediction-file requirements",
            "threshold-log requirements",
            "public-source provenance requirements",
            "full result artifact crosswalk",
            "numerical-audit traceability without main-text table overload",
            "## Audit Cycle 46: Manual Validation Boundary Density Gate",
            "manual-validation table-density reduction",
            "final label-precision claims",
            "full manual validation boundary table",
            "full manual validation protocol table",
            "label-evidence clarity without main-text table overload",
            "human-gold wording limits",
            "## Audit Cycle 47: Scope Compatibility Matrix Density Gate",
            "mixed-scope comparison table-density reduction",
            "broad ranking claims",
            "full scope compatibility matrix",
            "row-family scopes",
            "mixed-scope interpretation clarity without main-text table overload",
            "explicit stronger-comparison boundary",
            "## Audit Cycle 48: Result Interpretation Guardrails Density Gate",
            "result-interpretation table-density reduction",
            "stronger result readings",
            "full result interpretation guardrails table",
            "row-family readings",
            "result-reading clarity without main-text table overload",
            "threshold-stability or zero-risk limits",
            "## Audit Cycle 49: Claim-Evidence Boundary Density Gate",
            "claim-evidence table-density reduction",
            "full claim-evidence boundary table",
            "identity-agenda confusion",
            "IAD-Risk support",
            "IAD-Bench",
            "repository-level reproduction",
            "claim-evidence clarity without main-text table overload",
            "supplementary claim-evidence boundary",
            "## Audit Cycle 50: Validity Threats Density Gate",
            "validity-threat table-density reduction",
            "full validity-threats matrix",
            "construct validity",
            "internal validity",
            "external validity",
            "conclusion validity",
            "operational validity",
            "validity-threat clarity without main-text table overload",
            "supplementary validity-threat boundary",
            "## Audit Cycle 51: Claim Interpretation Boundary Density Gate",
            "claim-interpretation table-density reduction",
            "full claim-interpretation boundary table",
            "contribution clarity",
            "writing reproducibility",
            "experimental strength",
            "evaluation completeness",
            "method design soundness",
            "claim-interpretation clarity without main-text table overload",
            "supplementary claim-interpretation boundary",
            "## Audit Cycle 52: Data and Code Availability Density Gate",
            "data/code availability table-density reduction",
            "full data and code availability boundary table",
            "L0/L1 code-level reproduction",
            "L2/L3 result-level audit",
            "data-processing commands",
            "data-processing path",
            "raw third-party source files",
            "derived evaluation artifacts",
            "data/code availability clarity without main-text table overload",
            "supplementary data/code availability boundary",
            "## Audit Cycle 53: Error Taxonomy Density Gate",
            "error-taxonomy table-density reduction",
            "full error taxonomy table",
            "same task, different contribution",
            "citation-neighborhood neighbors",
            "version or extension boundaries",
            "identifier conflicts",
            "sparse metadata cases",
            "error-taxonomy clarity without main-text table overload",
            "supplementary error taxonomy boundary",
            "## Audit Cycle 54: Mechanism Evidence Boundary Density Gate",
            "mechanism-evidence table-density reduction",
            "full mechanism-evidence boundary table",
            "topical relatedness",
            "explicit risk gating",
            "component-causality claims",
            "cluster-level contamination claims",
            "mechanism-evidence clarity without main-text table overload",
            "supplementary mechanism-evidence boundary",
            "## Audit Cycle 55: Pair-to-Cluster Evidence Boundary Density Gate",
            "pair-to-cluster table-density reduction",
            "full pair-to-cluster evidence boundary table",
            "cluster assignments",
            "cannot-link violations",
            "pair-to-cluster trace files",
            "cluster contamination rate",
            "pair-to-cluster clarity without main-text table overload",
            "supplementary pair-to-cluster evidence boundary",
            "## Audit Cycle 56: Selective Decision Coverage Boundary Density Gate",
            "selective-decision coverage table-density reduction",
            "full selective-decision coverage boundary table",
            "automatic merge coverage",
            "block rate",
            "defer rate",
            "capacity-normalized review load",
            "selective-decision coverage clarity without main-text table overload",
            "supplementary selective-decision coverage boundary",
            "## Audit Cycle 57: Threshold Sensitivity Evidence Status Density Gate",
            "threshold-sensitivity table-density reduction",
            "full threshold-sensitivity evidence status table",
            "fixed operating points",
            "threshold grid",
            "per-threshold F1",
            "threshold-stable ranking",
            "threshold-sensitivity clarity without main-text table overload",
            "supplementary threshold-sensitivity evidence boundary",
            "## Audit Cycle 58: Operating Point Disclosure Density Gate",
            "operating-point table-density reduction",
            "full operating-point disclosure table",
            "fixed operating points",
            "post-hoc best test thresholds",
            "row family decision fields",
            "default threshold contract",
            "operating-point clarity without main-text table overload",
            "supplementary operating-point disclosure",
            "## Audit Cycle 59: Metric Formula Boundary Density Gate",
            "metric-formula table-density reduction",
            "full metric-formula boundary table",
            "same-work F1 denominator",
            "FMR denominator",
            "HNFMR denominator",
            "missing-label denominator rule",
            "metric-formula clarity without main-text table overload",
            "supplementary metric-formula boundary",
            "## Audit Cycle 60: Decision-to-Metric Mapping Density Gate",
            "decision-to-metric table-density reduction",
            "full decision-to-metric mapping table",
            "automatic merge is the positive decision",
            "block and defer are non-merge decisions",
            "deferred same-work pairs reduce recall",
            "FMR/HNFMR count only automatic merges",
            "decision-to-metric clarity without main-text table overload",
            "supplementary decision-to-metric mapping",
            "## Audit Cycle 61: Split and Leakage Controls Density Gate",
            "split-control table-density reduction",
            "full split and leakage controls table",
            "Training uses only the declared training split",
            "threshold selection uses validation evidence",
            "Unordered pair leakage guard",
            "Label-stratum coverage audit",
            "Source-heldout readiness audit",
            "Topic-heldout readiness audit",
            "split-control clarity without main-text table overload",
            "supplementary split and leakage controls table",
            "## Audit Cycle 62: Feature and Head Specification Density Gate",
            "feature-head table-density reduction",
            "full feature and head specification table",
            "Transformer distances",
            "title similarity",
            "DOI/arXiv/OpenAlex identifier agreement",
            "reference Jaccard similarity",
            "different-identifier conflicts",
            "feature-head clarity without main-text table overload",
            "supplementary feature and head specification table",
            "## Audit Cycle 63: Risk Score Design Rationale Density Gate",
            "risk-score rationale table-density reduction",
            "full risk score design rationale table",
            r"$p_{\mathrm{risk}}$ is a conservative upper-envelope risk proxy",
            "increases with agenda-non-identity evidence",
            "product term is not a calibrated probability",
            "Threshold transfer must be rechecked under new source distributions",
            "risk-score clarity without main-text table overload",
            "supplementary risk score design rationale table",
            "## Audit Cycle 64: Design Alternatives Density Gate",
            "design-alternatives table-density reduction",
            "full design-alternatives table",
            "Tune a representation-similarity threshold",
            "Use one supervised pair classifier",
            "Use provenance as a model feature",
            "Always force a binary merge decision",
            "Select thresholds after test results",
            "design-alternative clarity without main-text table overload",
            "supplementary design-alternatives table",
            "## Audit Cycle 65: Failure-Control Rationale Density Gate",
            "failure-control table-density reduction",
            "full failure-control rationale table",
            "Topically close papers receive high semantic similarity",
            "Silver metadata is treated as if it were human gold",
            "Pairwise errors can contaminate clusters through transitivity",
            "Thresholds can turn a classifier into an unsafe automatic merger",
            "Proxy labels are over-interpreted",
            "failure-control clarity without main-text table overload",
            "supplementary failure-control rationale table",
            "## Audit Cycle 66: Reproduction Levels Density Gate",
            "reproduction-level table-density reduction",
            "full reproduction-level table",
            "L0 code check and L1 fixture rebuild",
            "do not reproduce the Open-v2 numerical table",
            "L2 public-source rebuild requires independently obtained public raw files",
            "L3 result audit requires released tables, predictions, logs, manifests, checksums, and commit identifiers",
            "reproduction-level clarity without main-text table overload",
            "supplementary reproduction-level table",
            "## Audit Cycle 67: Evaluation Protocol Density Gate",
            "evaluation-protocol table-density reduction",
            "full evaluation-protocol table",
            "RQ1 tests whether IAD-Risk preserves same-work matching performance",
            "RQ2 tests whether it reduces false merges on silver hard negatives",
            "RQ3 examines whether the observed behavior is consistent with the proposed risk mechanism",
            "RQ4 tests whether results remain interpretable under gold, proxy, and silver label strata",
            "evaluation-protocol clarity without main-text table overload",
            "supplementary evaluation-protocol table",
            "## Audit Cycle 68: Training and Inference Trace Density Gate",
            "training-trace table-density reduction",
            "full training and inference trace table",
            "schema loading preserves pair IDs and split fields",
            "supervised fitting uses the masked objective",
            "threshold fixation records",
            "decision emission records merge, block, or defer",
            "metric export binds denominators and checksums",
            "training-trace clarity without main-text table overload",
            "supplementary training-inference trace table",
            "## Audit Cycle 69: Scoring and Merge Algorithm Density Gate",
            "scoring-algorithm table-density reduction",
            "full scoring and merge algorithm table",
            "fixed scoring and merge order",
            "identity, agenda, ANI, and cannot-link feature groups",
            "derived risk score",
            "merge gate combines",
            "decision, row scope, denominators, thresholds, and checksum-bound artifact rows",
            "scoring-algorithm clarity without main-text table overload",
            "supplementary scoring-merge algorithm table",
            "## Audit Cycle 70: Artifact Publication Binding Gate",
            "final-upload artifact publication binding",
            "artifact manifest publication object",
            "`artifact_release_url`",
            "`artifact_release_doi`",
            "`public_access_status`",
            "submission package is rejected",
            "publication URL or DOI differs from `submission_metadata.yml`",
            "public access status remains pending",
            "artifact-publication traceability",
            "public artifact link are aligned",
            "## Audit Cycle 71: Target Ranking and Author Confirmation Gate",
            "final-upload target-ranking gate implementation",
            "`target_preparation.ranking_confirmation_completed`",
            "ranking_confirmation_source",
            "ranking_confirmation_checked_date",
            "selected_target_author_confirmed",
            "publisher metrics remain screening signals",
            "rank/category traceability",
            "## Audit Cycle 72: Live System Final Package Verification Gate",
            "final-upload live-system verification gate implementation",
            "`upload_preparation.live_submission_system_verified`",
            "`upload_preparation.final_upload_package_verified_against_system`",
            "source-file text consistency",
            "operational traceability",
            "## Audit Cycle 73: Author Guide and Template Requirement Confirmation Gate",
            "final-upload author-guide and template-requirement gate implementation",
            "`target_preparation.selected_author_guide_source`",
            "`target_preparation.selected_author_guide_rechecked_date`",
            "`target_preparation.selected_template_requirements_confirmed`",
            "formatting and submission-policy traceability",
            "## Audit Cycle 74: Author Identity Material Traceability Gate",
            "author identity material traceability gate implementation",
            "`author_identity_materials.biography_files`",
            "`author_identity_materials.photograph_files`",
            "`author_identity_materials.author_identity_materials_verified`",
            "boolean checklist item was set to true",
            "anonymous DKE/Elsevier preflight package",
            "## Audit Cycle 75: Closest-Work Decision-Semantics Gate",
            "Related Work decision-semantics clarification",
            "different decision roles to relatedness",
            "identity evidence, agenda evidence, or agenda-non-identity stress evidence",
            "not merely a new encoder or a new threshold over existing embeddings",
            "positive, negative, or deferred",
            "connects IAD-Bench to HNFMR",
            "## Audit Cycle 76: Mechanism Ablation Acceptance Protocol Gate",
            "Mechanism ablation acceptance protocol",
            "no-risk-gate, no-ANI-head, single-space, no-cannot-link, and post-hoc-threshold",
            "same pair scope, split field, label stratum, and metric implementation",
            "prediction rows, threshold logs, same-work F1/FMR/HNFMR denominators",
            "changed pair universe, threshold-selection source, or prediction schema",
            "## Audit Cycle 77: Ablation CLI Protocol-Variant Alignment Gate",
            "ablation CLI protocol-variant alignment",
            "run-iad-ablation-suite",
            "`protocol_variant`",
            "post_hoc_labeled_sweep",
            "not as standalone causal evidence",
            "## Audit Cycle 78: Ablation Artifact Release Schema Gate",
            "ablation artifact release schema validation",
            "reports/iad_ablation_suite.csv",
            "missing protocol variants",
            "post-hoc-threshold row marked as component-causality evidence",
            "## Audit Cycle 79: Manual Validation Artifact Release Schema Gate",
            "manual-validation artifact release schema validation",
            "reports/manual_validation_slice.csv",
            "500-1000 pair reviewed slice",
            "`manual_validation_stratum`",
            "`reviewer_blinding_confirmed`",
            "`adjudication_rationale`",
            "`pair_level_notes`",
            "`human_validation_claimed`",
            "missing required strata",
            "non-blinded reviewer rows",
            "## Audit Cycle 80: Threshold Sensitivity Artifact Release Schema Gate",
            "threshold-sensitivity artifact release schema validation",
            "reports/threshold_sensitivity_grid.csv",
            "`threshold_stability_claimed`",
            "at least two predefined threshold rows",
            "exactly one `prediction_artifact_id`",
            "exactly one `prediction_file_sha256`",
            "`selected_operating_point`",
            "selection/evaluation split leakage",
            "mixed prediction-file checksums",
            "fixed-threshold false-merge control",
            "## Audit Cycle 81: Cluster-Level Artifact Release Schema Gate",
            "cluster-level artifact release schema validation",
            "`cluster_level_quality_claimed`",
            "reports/cluster_metric_summary.csv",
            "reports/cannot_link_audit.csv",
            "cluster assignment and pair-to-cluster trace file references",
            "cannot-link rule IDs",
            "blocked-merge indicators",
            "coverage rate",
            "mixed cluster runs or merge policies",
            "unparseable cannot-link booleans",
            "pair-level FMR and HNFMR support false-merge control",
            "## Audit Cycle 82: Bootstrap Interval Artifact Release Schema Gate",
            "bootstrap-interval artifact release schema validation",
            "`confidence_intervals_claimed`",
            "reports/bootstrap_intervals.csv",
            "required `metric_name` rows covering same-work F1, FMR, and HNFMR",
            "bootstrap method",
            "resample unit",
            "resample count",
            "confidence level",
            "interval lower and upper bounds",
            "too few resamples",
            "intervals that do not contain the point estimate",
            "Open-v2 values remain point estimates",
            "## Audit Cycle 83: Artifact Release CLI Discovery Command Consistency Gate",
            "artifact release CLI discovery command consistency",
            "`python -m iad_sieve.cli --help`",
            "minimum_validation_commands",
            "README command block",
            "manifest command list",
            "release README validator",
            "Git-only reviewers can verify CLI discovery before artifact validation",
            "reviewer-facing boundary is command discoverability",
            "## Audit Cycle 84: Submission Checklist Artifact CLI Discovery Gate",
            "submission-system checklist alignment",
            "same repository checkout named by the release manifest",
            "manual submission workflow",
            "installable CLI discovery",
            "final-upload procedure consistency",
            "## Minimum Gate Before Final Upload",
            "The Q2/B acceptance gate is either fully ready.",
            "python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release",
        ]
    )

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert errors == []


def test_check_reviewer_readiness_audit_rejects_missing_iteration_summary() -> None:
    """验证审稿准备度审计必须记录多轮审稿摘要和剩余外部阻断项。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Iteration Summary",
        "Completed audit cycles: 84",
        "Highest current reviewer-facing risks",
        "Current stopping rule",
        "Non-code external inputs still required",
        "Next revision trigger",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Audit Iteration Summary" in error for error in errors)
    assert any("Completed audit cycles: 84" in error for error in errors)
    assert any("Highest current reviewer-facing risks" in error for error in errors)
    assert any("Non-code external inputs still required" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_pair_cluster_lockdown() -> None:
    """验证审稿准备度审计必须覆盖 pair-to-cluster 主张锁定。"""

    module = _load_validate_manuscript_module()
    audit_text = "\n".join(
        [
            "# Reviewer Readiness Audit",
            "Current decision: conditionally ready for target-journal selection; not ready for final upload.",
            "## Audit Dimensions",
            "Contribution",
            "Writing clarity",
            "Experimental strength",
            "Evaluation completeness",
            "Method design soundness",
            "## Reviewer Risk Register",
            "Silver hard negatives may not be true non-identity labels.",
            "Threshold results may be sensitive.",
            "Confidence intervals and statistical significance may be overread.",
            "The current manuscript reports point estimates and reserves bootstrap intervals.",
            "No statistical significance claim is made.",
            "Reproducibility depends on files outside Git.",
            "## Claim-Evidence Check",
            "## Adversarial Self-Review Matrix",
            "`pass`, `needs revision`, and `needs new experiment` are strict status values.",
            "Contribution self-review",
            "Writing clarity self-review",
            "Experimental strength self-review",
            "Evaluation completeness self-review",
            "Method design soundness self-review",
            "The stronger package requires same-scope prediction files.",
            "It also requires artifact-backed ablations.",
            "## Reviewer Response Matrix",
            "This matrix anticipates likely reviewer questions.",
            "A reviewer may ask about identity-agenda confusion.",
            "The response discusses silver hard negatives.",
            "The table is a scope-bounded evidence snapshot.",
            "It presents RoBERTa as a strong baseline.",
            "The current evidence is mechanism-consistent.",
            "The repository supports fixture-level code reproduction.",
            "## Audit Cycle 1: Claim Discipline",
            "## Audit Cycle 2: Submission Readiness",
            "## Audit Cycle 3: Q2/B Acceptance Gate",
            "remote reproducibility",
            "strong model matrix",
            "model superiority",
            "innovation depth",
            "novelty and prior-art positioning",
            "claim lockdown",
            "## Audit Cycle 4: Final Package Hygiene",
            "anonymous package hygiene",
            "## Audit Cycle 5: Editorial Desk Check",
            "title, abstract, conclusion, cover letter, highlights, and keywords",
            "editorial claim alignment",
            "author email addresses, ORCID values, personal account URLs, local absolute paths, and development process notes",
            "## Audit Cycle 6: Reviewer Rebuttal Boundary",
            "ready_to_answer",
            "limited_answer",
            "do_not_answer_as_claim",
            "safe response scope",
            "must-not-claim boundary",
            "## Revision Trigger Register",
            "reviewer concern triggers a concrete manuscript revision",
            "Contribution trigger",
            "Writing clarity trigger",
            "Experimental strength trigger",
            "Evaluation completeness trigger",
            "Method design soundness trigger",
            "weaken the claim",
            "add artifact-backed evidence",
            "do not upgrade the abstract, introduction, conclusion, cover letter, or highlights",
            "## Audit Cycle 7: Journal Fit and Novelty Desk Check",
            "desk-rejection risk",
            "target-journal scope fit",
            "novelty beyond ordinary entity matching",
            "Data & Knowledge Engineering",
            "Information Systems",
            "Scientometrics",
            "## Minimum Gate Before Final Upload",
            "The Q2/B acceptance gate is either fully ready.",
            "python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release",
        ]
    )

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Pair-to-Cluster Claim Lockdown" in error for error in errors)
    assert any("cluster_metric_summary" in error for error in errors)
    assert any("cannot_link_audit" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_artifact_row_level_audit() -> None:
    """验证审稿准备度审计必须覆盖 artifact 主结果表行级审计。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 9: Artifact Row-Level Result Audit",
        "open_v2_main_results",
        "per-row denominator counts",
        "per-row threshold source",
        "scope label used in the main table",
        "automatic merge count",
        "block count",
        "defer count",
        "automatic merge coverage",
        "defer rate",
        "capacity-normalized review load",
        "validate_artifact_release.py",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Artifact Row-Level Result Audit" in error for error in errors)
    assert any("open_v2_main_results" in error for error in errors)
    assert any("per-row denominator counts" in error for error in errors)
    assert any("per-row threshold source" in error for error in errors)
    assert any("scope label used in the main table" in error for error in errors)
    assert any("automatic merge coverage" in error for error in errors)
    assert any("defer rate" in error for error in errors)
    assert any("capacity-normalized review load" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_template_binding_gate() -> None:
    """验证审稿准备度审计必须覆盖最终模板绑定门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 10: Final Template Binding and System Metadata Gate",
        "target_journal_template_bound",
        "target_journal_template_applied",
        "source archive rebuilt after template conversion",
        "selected journal template matches the final manuscript source",
        "DKE/Elsevier preflight package",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Final Template Binding and System Metadata Gate" in error for error in errors)
    assert any("target_journal_template_bound" in error for error in errors)
    assert any("target_journal_template_applied" in error for error in errors)
    assert any("selected journal template matches the final manuscript source" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_live_submission_text_gate() -> None:
    """验证审稿准备度审计必须覆盖投稿系统首屏文本一致性门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 11: Live Submission Text Consistency Gate",
        "submission_system_files_verified",
        "title, abstract, keywords, and highlights",
        "`main.tex`",
        "`keywords.md`",
        "`highlights.md`",
        "live submission system preview",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Live Submission Text Consistency Gate" in error for error in errors)
    assert any("submission_system_files_verified" in error for error in errors)
    assert any("title, abstract, keywords, and highlights" in error for error in errors)
    assert any("live submission system preview" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_fixture_reproducibility_gate() -> None:
    """验证审稿准备度审计必须覆盖 Git-only fixture 复现门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 12: Git-Only Fixture Reproducibility Gate",
        "python manuscript/scripts/verify_fixture_rebuild.py",
        "python scripts/check_public_release.py",
        "no-network code-path evidence",
        "data adapters, CLI entry points, schema contracts, and IAD-Bench assembly path",
        "does not prove the Open-v2 numerical table",
        "data/",
        "outputs/",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Git-Only Fixture Reproducibility Gate" in error for error in errors)
    assert any("verify_fixture_rebuild.py" in error for error in errors)
    assert any("check_public_release.py" in error for error in errors)
    assert any("does not prove the Open-v2 numerical table" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_cli_entrypoint_traceability_gate() -> None:
    """验证审稿准备度审计必须覆盖可安装 CLI 入口可追溯门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 39: Installable CLI Entry-Point Traceability Gate",
        "Git-only command discovery and source entry-point binding",
        "`src/iad_sieve`",
        "`pyproject.toml`",
        "`iad-sieve = iad_sieve.cli:main`",
        "`python -m iad_sieve.cli --help`",
        "argparse command discovery",
        "tracked source contract",
        "Git-only reviewers can discover the CLI",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Installable CLI Entry-Point Traceability Gate" in error for error in errors)
    assert any("src/iad_sieve" in error for error in errors)
    assert any("python -m iad_sieve.cli --help" in error for error in errors)
    assert any("tracked source contract" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_artifact_source_preflight_gate() -> None:
    """验证审稿准备度审计必须覆盖 source artifact 预检查门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 40: Artifact Source Preflight Gate",
        "source artifact completeness preflight coverage",
        "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
        "checks required source artifact paths",
        "optional mapping paths",
        "without copying files",
        "artifact_population_log.jsonl",
        "source-package readiness",
        "row-level schemas",
        "validate_submission_package.py --final-upload --artifact-dir /path/to/release",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Artifact Source Preflight Gate" in error for error in errors)
    assert any("--preflight-only" in error for error in errors)
    assert any("artifact_population_log.jsonl" in error for error in errors)
    assert any("row-level schemas" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_package_pdf_freshness_gate() -> None:
    """验证审稿准备度审计必须覆盖投稿包 PDF 新鲜度门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 13: Submission Package Source-PDF Consistency Gate",
        "packaged PDFs",
        "source dependencies",
        "main PDF",
        "supplementary PDF",
        "DKE/Elsevier preflight PDF",
        "rebuild PDF before packaging",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Submission Package Source-PDF Consistency Gate" in error for error in errors)
    assert any("packaged PDFs" in error for error in errors)
    assert any("DKE/Elsevier preflight PDF" in error for error in errors)
    assert any("rebuild PDF before packaging" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_source_control_manifest_gate() -> None:
    """验证审稿准备度审计必须覆盖 source-control manifest 绑定门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 14: Source-Control Manifest Binding Gate",
        "source_control",
        "repository_commit",
        "repository_branch",
        "worktree_dirty",
        "tracked_state",
        "matches `submission_metadata.yml`",
        "final package is rebuilt from the submitted repository commit",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Source-Control Manifest Binding Gate" in error for error in errors)
    assert any("source_control" in error for error in errors)
    assert any("repository_commit" in error for error in errors)
    assert any("worktree_dirty" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_artifact_commit_validity_gate() -> None:
    """验证审稿准备度审计必须覆盖 artifact release commit 有效性门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 15: Artifact Release Commit Validity Gate",
        "7 to 40 character hexadecimal Git commit",
        "repository.commit",
        "artifact release skeleton builder and validator",
        "same committed source revision as the final manuscript package",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Artifact Release Commit Validity Gate" in error for error in errors)
    assert any("hexadecimal Git commit" in error for error in errors)
    assert any("repository.commit" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_artifact_readme_gate() -> None:
    """验证审稿准备度审计必须覆盖 artifact release README 复现说明门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 16: Artifact Release README Reproducibility Gate",
        "README.md",
        "manifest.json",
        "checksums.sha256",
        "raw third-party data exclusions",
        "data policy",
        "reproduction levels",
        "claim boundaries",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Artifact Release README Reproducibility Gate" in error for error in errors)
    assert any("README.md" in error for error in errors)
    assert any("checksums.sha256" in error for error in errors)
    assert any("raw third-party data exclusions" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_artifact_readme_manifest_commit_gate() -> None:
    """验证审稿准备度审计必须覆盖 artifact README 与 manifest 提交号一致性门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 25: Artifact README-Manifest Commit Consistency Gate",
        "Repository commit",
        "manifest.json",
        "repository.commit",
        "commit-consistency coverage",
        "same source revision",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Artifact README-Manifest Commit Consistency Gate" in error for error in errors)
    assert any("Repository commit" in error for error in errors)
    assert any("repository.commit" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_final_package_artifact_commit_gate() -> None:
    """验证审稿准备度审计必须覆盖最终投稿包与 artifact 提交号绑定门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 26: Final Package-Artifact Commit Binding Gate",
        "submission-package validator coverage",
        "validate_submission_package.py --final-upload --artifact-dir",
        "artifact manifest",
        "submission_metadata.yml",
        "repository_commit",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Final Package-Artifact Commit Binding Gate" in error for error in errors)
    assert any("validate_submission_package.py --final-upload --artifact-dir" in error for error in errors)
    assert any("submission_metadata.yml" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_artifact_dir_instruction_gate() -> None:
    """验证审稿准备度审计必须覆盖最终上传 artifact-dir 指令一致性门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 27: Final-Upload Artifact-Dir Instruction Consistency Gate",
        "final-upload instruction coverage",
        "final_upload_information_request.md",
        "submission_system_checklist.md",
        "older command without `--artifact-dir`",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Final-Upload Artifact-Dir Instruction Consistency Gate" in error for error in errors)
    assert any("final_upload_information_request.md" in error for error in errors)
    assert any("submission_system_checklist.md" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_integrated_artifact_validation_gate() -> None:
    """验证审稿准备度审计必须覆盖最终上传集成 artifact release 校验门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 28: Final-Upload Artifact Release Validation Gate",
        "integrated artifact-release validation coverage",
        "required artifact IDs",
        "Open-v2 row-level audit columns",
        "prediction JSONL fields",
        "claim-dependent artifact requirements",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Final-Upload Artifact Release Validation Gate" in error for error in errors)
    assert any("integrated artifact-release validation coverage" in error for error in errors)
    assert any("required artifact IDs" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_artifact_dir_required_gate() -> None:
    """验证审稿准备度审计必须覆盖正式上传 artifact-dir 必传门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 29: Final-Upload Artifact-Dir Required Gate",
        "missing artifact-directory rejection",
        "finalized artifact release directory",
        "omit `--artifact-dir`",
        "local checksum, manifest, row-schema, prediction-schema, and package-artifact commit checks",
        "cannot bypass the external release directory",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Final-Upload Artifact-Dir Required Gate" in error for error in errors)
    assert any("missing artifact-directory rejection" in error for error in errors)
    assert any("cannot bypass the external release directory" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_main_manuscript_artifact_validation_gate() -> None:
    """验证审稿准备度审计必须覆盖主稿 artifact 校验文本门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 30: Main-Manuscript Artifact Validation Text Gate",
        "manuscript-level reproducibility wording",
        "Data and Code Availability section",
        "validate_artifact_release.py --artifact-dir /path/to/release",
        "validate_submission_package.py --final-upload --artifact-dir /path/to/release",
        "source-control commit",
        "main text tells reviewers",
        "should not be used to support the Open-v2 numerical table",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Main-Manuscript Artifact Validation Text Gate" in error for error in errors)
    assert any("manuscript-level reproducibility wording" in error for error in errors)
    assert any("should not be used to support the Open-v2 numerical table" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_zero_observed_hnfmr_gate() -> None:
    """验证审稿准备度审计必须覆盖 zero observed HNFMR 首屏措辞门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 31: Zero-Observed HNFMR Wording Gate",
        "first-screen zero-risk overread control",
        "zero observed HNFMR rather than as wording that can be read as absolute zero risk",
        "first-screen prose",
        "no hard-negative false merge was observed",
        "does not prove zero risk under all scholarly sources",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Zero-Observed HNFMR Wording Gate" in error for error in errors)
    assert any("first-screen zero-risk overread control" in error for error in errors)
    assert any("does not prove zero risk under all scholarly sources" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_l2_traceability_gate() -> None:
    """验证审稿准备度审计必须覆盖 L2 公开源重建追踪门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 32: L2 Public-Source Rebuild Traceability Gate",
        "L2 public-source rebuild traceability wording",
        "source_input_manifest",
        "processing_run_log",
        "output summaries",
        "chain of custody",
        "real public-source inputs",
        "alongside result tables, predictions, threshold logs, and split summaries",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("L2 Public-Source Rebuild Traceability Gate" in error for error in errors)
    assert any("source_input_manifest" in error for error in errors)
    assert any("chain of custody" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_main_text_l2_alignment_gate() -> None:
    """验证审稿准备度审计必须覆盖主稿 L2 provenance 对齐门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 33: Main-Text L2 Provenance Alignment Gate",
        "main-text L2 provenance alignment",
        "reproduction-level table",
        "result audit trail",
        "result artifact crosswalk",
        "Data and Code Availability section now state",
        "source-to-result alignment",
        "same provenance vocabulary",
        "supplemental-only instructions",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Main-Text L2 Provenance Alignment Gate" in error for error in errors)
    assert any("main-text L2 provenance alignment" in error for error in errors)
    assert any("same provenance vocabulary" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_final_upload_source_control_package_gate() -> None:
    """验证审稿准备度审计必须覆盖正式上传包内 source-control 绑定门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 17: Final-Upload Source-Control Package Binding Gate",
        "tracked `submission_metadata.yml`",
        "cannot reliably contain the Git commit of the commit that contains itself",
        "writes `repository_url`, `repository_commit`, `repository_branch`",
        "matching data/code availability statement",
        "final package metadata and `submission_manifest.json` agree",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Final-Upload Source-Control Package Binding Gate" in error for error in errors)
    assert any("tracked `submission_metadata.yml`" in error for error in errors)
    assert any("matching data/code availability statement" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_prediction_artifact_schema_gate() -> None:
    """验证审稿准备度审计必须覆盖 prediction artifact 行级 schema 门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 18: Prediction Artifact Schema Gate",
        "prediction artifact schema drift",
        "row-level prediction schema enforced by `validate_artifact_release.py`",
        "iad_risk_predictions",
        "representation_baseline_scores",
        "supervised_baseline_predictions",
        "threshold_selection_logs",
        "pair_id",
        "source_document_id",
        "target_document_id",
        "threshold_value",
        "merge_prediction",
        "selection_rule",
        "score_field",
        "recompute row-level decisions, denominators, and fixed operating points",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Prediction Artifact Schema Gate" in error for error in errors)
    assert any("prediction artifact schema drift" in error for error in errors)
    assert any("iad_risk_predictions" in error for error in errors)
    assert any("threshold_selection_logs" in error for error in errors)
    assert any("merge_prediction" in error for error in errors)
    assert any("selection_rule" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_generative_ai_declaration_gate() -> None:
    """验证审稿准备度审计必须覆盖生成式 AI 声明门禁。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 19: Generative AI Declaration Gate",
        "generative AI declaration consistency",
        "publisher-required AI-tool disclosure",
        "removable process notes",
        "AI-tool use status",
        "author review and responsibility",
        "AI tools are not listed as authors",
        "machine-generated figures, images, or artwork",
        "generative_ai_declaration_complete",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Generative AI Declaration Gate" in error for error in errors)
    assert any("generative AI declaration consistency" in error for error in errors)
    assert any("AI-tool use status" in error for error in errors)
    assert any("machine-generated figures, images, or artwork" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_fixture_evidence_isolation_gate() -> None:
    """验证审稿准备度审计必须隔离测试夹具和真实投稿证据。"""

    module = _load_validate_manuscript_module()
    audit_text = Path("manuscript/reviewer_readiness_audit.md").read_text(encoding="utf-8")
    for marker in [
        "Audit Cycle 20: Fixture Evidence Isolation Gate",
        "fixture/live evidence confusion",
        "test fixtures from being mistaken for current manuscript evidence",
        "Unit-test fixtures",
        "generated fixture reports",
        "validator coverage only",
        "live outputs regenerated from the current repository commit",
        "current live artifacts",
        "current commit metadata",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Fixture Evidence Isolation Gate" in error for error in errors)
    assert any("fixture/live evidence confusion" in error for error in errors)
    assert any("Unit-test fixtures" in error for error in errors)
    assert any("live outputs regenerated from the current repository commit" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_final_gate() -> None:
    """验证审稿准备度审计缺少最终上传门槛时会被拒绝。"""

    module = _load_validate_manuscript_module()
    audit_text = "# Reviewer Readiness Audit\n## Audit Dimensions\nContribution"

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Reviewer Risk Register" in error for error in errors)
    assert any("Adversarial Self-Review Matrix" in error for error in errors)
    assert any("Reviewer Response Matrix" in error for error in errors)
    assert any("Q2/B Acceptance Gate" in error for error in errors)
    assert any("Final Package Hygiene" in error for error in errors)
    assert any("Minimum Gate Before Final Upload" in error for error in errors)
    assert any("--final-upload" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_rebuttal_boundary() -> None:
    """验证审稿准备度审计缺少反驳边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    audit_text = "\n".join(
        [
            "# Reviewer Readiness Audit",
            "Current decision: conditionally ready for target-journal selection; not ready for final upload.",
            "## Audit Dimensions",
            "Contribution",
            "Writing clarity",
            "Experimental strength",
            "Evaluation completeness",
            "Method design soundness",
            "## Reviewer Risk Register",
            "Silver hard negatives may not be true non-identity labels.",
            "Threshold results may be sensitive.",
            "Confidence intervals and statistical significance may be overread.",
            "The current manuscript reports point estimates and reserves bootstrap intervals.",
            "No statistical significance claim is made.",
            "Reproducibility depends on files outside Git.",
            "## Claim-Evidence Check",
            "## Adversarial Self-Review Matrix",
            "`pass`, `needs revision`, and `needs new experiment` are strict status values.",
            "Contribution self-review",
            "Writing clarity self-review",
            "Experimental strength self-review",
            "Evaluation completeness self-review",
            "Method design soundness self-review",
            "The stronger package requires same-scope prediction files.",
            "It also requires artifact-backed ablations.",
            "## Reviewer Response Matrix",
            "This matrix anticipates likely reviewer questions.",
            "A reviewer may ask about identity-agenda confusion.",
            "The response discusses silver hard negatives.",
            "The table is a scope-bounded evidence snapshot.",
            "It presents RoBERTa as a strong baseline.",
            "The current evidence is mechanism-consistent.",
            "The repository supports fixture-level code reproduction.",
            "## Audit Cycle 1: Claim Discipline",
            "## Audit Cycle 2: Submission Readiness",
            "## Audit Cycle 3: Q2/B Acceptance Gate",
            "remote reproducibility",
            "strong model matrix",
            "model superiority",
            "innovation depth",
            "novelty and prior-art positioning",
            "claim lockdown",
            "## Audit Cycle 4: Final Package Hygiene",
            "anonymous package hygiene",
            "## Audit Cycle 5: Editorial Desk Check",
            "title, abstract, conclusion, cover letter, highlights, and keywords",
            "editorial claim alignment",
            "author email addresses, ORCID values, personal account URLs, local absolute paths, and development process notes",
            "## Minimum Gate Before Final Upload",
            "The Q2/B acceptance gate is either fully ready.",
            "python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release",
        ]
    )

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Reviewer Rebuttal Boundary" in error for error in errors)
    assert any("ready_to_answer" in error for error in errors)
    assert any("must-not-claim boundary" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_revision_trigger_register() -> None:
    """验证审稿准备度审计缺少修稿触发器时会被拒绝。"""

    module = _load_validate_manuscript_module()
    audit_text = "\n".join(
        [
            "# Reviewer Readiness Audit",
            "Current decision: conditionally ready for target-journal selection; not ready for final upload.",
            "## Audit Dimensions",
            "Contribution",
            "Writing clarity",
            "Experimental strength",
            "Evaluation completeness",
            "Method design soundness",
            "## Reviewer Risk Register",
            "Silver hard negatives may not be true non-identity labels.",
            "Threshold results may be sensitive.",
            "Confidence intervals and statistical significance may be overread.",
            "The current manuscript reports point estimates and reserves bootstrap intervals.",
            "No statistical significance claim is made.",
            "Reproducibility depends on files outside Git.",
            "## Claim-Evidence Check",
            "## Adversarial Self-Review Matrix",
            "`pass`, `needs revision`, and `needs new experiment` are strict status values.",
            "Contribution self-review",
            "Writing clarity self-review",
            "Experimental strength self-review",
            "Evaluation completeness self-review",
            "Method design soundness self-review",
            "The stronger package requires same-scope prediction files.",
            "It also requires artifact-backed ablations.",
            "## Reviewer Response Matrix",
            "This matrix anticipates likely reviewer questions.",
            "A reviewer may ask about identity-agenda confusion.",
            "The response discusses silver hard negatives.",
            "The table is a scope-bounded evidence snapshot.",
            "It presents RoBERTa as a strong baseline.",
            "The current evidence is mechanism-consistent.",
            "The repository supports fixture-level code reproduction.",
            "## Audit Cycle 1: Claim Discipline",
            "## Audit Cycle 2: Submission Readiness",
            "## Audit Cycle 3: Q2/B Acceptance Gate",
            "remote reproducibility",
            "strong model matrix",
            "model superiority",
            "innovation depth",
            "novelty and prior-art positioning",
            "claim lockdown",
            "## Audit Cycle 4: Final Package Hygiene",
            "anonymous package hygiene",
            "## Audit Cycle 5: Editorial Desk Check",
            "title, abstract, conclusion, cover letter, highlights, and keywords",
            "editorial claim alignment",
            "author email addresses, ORCID values, personal account URLs, local absolute paths, and development process notes",
            "## Audit Cycle 6: Reviewer Rebuttal Boundary",
            "ready_to_answer",
            "limited_answer",
            "do_not_answer_as_claim",
            "safe response scope",
            "must-not-claim boundary",
            "## Audit Cycle 7: Journal Fit and Novelty Desk Check",
            "desk-rejection risk",
            "target-journal scope fit",
            "novelty beyond ordinary entity matching",
            "Data & Knowledge Engineering",
            "Information Systems",
            "Scientometrics",
            "## Minimum Gate Before Final Upload",
            "The Q2/B acceptance gate is either fully ready.",
            "python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release",
        ]
    )

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Revision Trigger Register" in error for error in errors)
    assert any("Contribution trigger" in error for error in errors)
    assert any("do not upgrade the abstract" in error for error in errors)


def test_check_reviewer_readiness_audit_rejects_missing_journal_fit_novelty_cycle() -> None:
    """验证审稿准备度审计缺少期刊适配和新颖性桌面初筛时会被拒绝。"""

    module = _load_validate_manuscript_module()
    audit_text = "\n".join(
        [
            "# Reviewer Readiness Audit",
            "Current decision: conditionally ready for target-journal selection; not ready for final upload.",
            "## Audit Dimensions",
            "Contribution",
            "Writing clarity",
            "Experimental strength",
            "Evaluation completeness",
            "Method design soundness",
            "## Reviewer Risk Register",
            "Silver hard negatives may not be true non-identity labels.",
            "Threshold results may be sensitive.",
            "Confidence intervals and statistical significance may be overread.",
            "The current manuscript reports point estimates and reserves bootstrap intervals.",
            "No statistical significance claim is made.",
            "Reproducibility depends on files outside Git.",
            "## Claim-Evidence Check",
            "## Adversarial Self-Review Matrix",
            "`pass`, `needs revision`, and `needs new experiment` are strict status values.",
            "Contribution self-review",
            "Writing clarity self-review",
            "Experimental strength self-review",
            "Evaluation completeness self-review",
            "Method design soundness self-review",
            "The stronger package requires same-scope prediction files.",
            "It also requires artifact-backed ablations.",
            "## Reviewer Response Matrix",
            "This matrix anticipates likely reviewer questions.",
            "A reviewer may ask about identity-agenda confusion.",
            "The response discusses silver hard negatives.",
            "The table is a scope-bounded evidence snapshot.",
            "It presents RoBERTa as a strong baseline.",
            "The current evidence is mechanism-consistent.",
            "The repository supports fixture-level code reproduction.",
            "## Audit Cycle 1: Claim Discipline",
            "## Audit Cycle 2: Submission Readiness",
            "## Audit Cycle 3: Q2/B Acceptance Gate",
            "remote reproducibility",
            "strong model matrix",
            "model superiority",
            "innovation depth",
            "novelty and prior-art positioning",
            "claim lockdown",
            "## Audit Cycle 4: Final Package Hygiene",
            "anonymous package hygiene",
            "## Audit Cycle 5: Editorial Desk Check",
            "title, abstract, conclusion, cover letter, highlights, and keywords",
            "editorial claim alignment",
            "author email addresses, ORCID values, personal account URLs, local absolute paths, and development process notes",
            "## Audit Cycle 6: Reviewer Rebuttal Boundary",
            "ready_to_answer",
            "limited_answer",
            "do_not_answer_as_claim",
            "safe response scope",
            "must-not-claim boundary",
            "## Minimum Gate Before Final Upload",
            "The Q2/B acceptance gate is either fully ready.",
            "python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release",
        ]
    )

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Journal Fit and Novelty Desk Check" in error for error in errors)
    assert any("desk-rejection risk" in error for error in errors)
    assert any("target-journal scope fit" in error for error in errors)


def test_check_cover_letter_accepts_preflight_declaration_boundary() -> None:
    """验证匿名预投稿信包含正式声明待确认边界时可通过检查。"""

    module = _load_validate_manuscript_module()
    cover_letter_text = "\n".join(
        [
            "Dear Editor,",
            "We submit IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication.",
            "This anonymous preflight cover letter does not treat author declarations as finalized.",
            "Before final upload, the author-provided metadata must confirm originality, author approval, "
            "competing-interest status, funding, author contribution, permission, and generative AI declarations.",
            "The repository does not redistribute raw third-party data.",
            "full experimental outputs are not redistributed in Git.",
            "The repository includes artifact-release instructions.",
            "Released artifacts should include manifests and checksums.",
            "The manuscript does not claim cluster-level deployment quality without cluster artifacts.",
        ]
    )

    errors = module.check_cover_letter(cover_letter_text)

    assert errors == []


def test_check_cover_letter_rejects_missing_preflight_declaration_boundary() -> None:
    """验证匿名预投稿信缺少声明待确认边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    cover_letter_text = "Dear Editor,\nWe submit the manuscript."

    errors = module.check_cover_letter(cover_letter_text)

    assert any("anonymous preflight cover letter" in error for error in errors)
    assert any("author-provided metadata must confirm originality" in error for error in errors)
    assert any("generative AI declarations" in error for error in errors)


def test_check_cover_letter_rejects_premature_final_declarations() -> None:
    """验证匿名预投稿信不得提前确认作者批准和利益冲突声明。"""

    module = _load_validate_manuscript_module()
    cover_letter_text = "\n".join(
        [
            "Dear Editor,",
            "We submit IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication.",
            "This anonymous preflight cover letter does not treat author declarations as finalized.",
            "Before final upload, the author-provided metadata must confirm originality, author approval, "
            "competing-interest status, funding, author contribution, permission, and generative AI declarations.",
            "All listed authors have approved the submitted version.",
            "The authors declare no competing interests.",
            "The repository does not redistribute raw third-party data.",
            "full experimental outputs are not redistributed in Git.",
            "The repository includes artifact-release instructions.",
            "Released artifacts should include manifests and checksums.",
            "The manuscript does not claim cluster-level deployment quality without cluster artifacts.",
        ]
    )

    errors = module.check_cover_letter(cover_letter_text)

    assert any("premature final declaration" in error for error in errors)
    assert any("All listed authors have approved" in error for error in errors)
    assert any("no competing interests" in error for error in errors)


def test_check_cover_letter_rejects_missing_artifact_release_boundary() -> None:
    """验证 cover letter 缺少完整实验输出和 artifact release 边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    cover_letter_text = "\n".join(
        [
            "Dear Editor,",
            "We submit IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication.",
            "This anonymous preflight cover letter does not treat author declarations as finalized.",
            "Before final upload, the author-provided metadata must confirm originality, author approval, "
            "competing-interest status, funding, author contribution, permission, and generative AI declarations.",
            "The repository does not redistribute raw third-party data.",
            "Released artifacts should include manifests and checksums.",
        ]
    )

    errors = module.check_cover_letter(cover_letter_text)

    assert any("full experimental outputs are not redistributed in Git" in error for error in errors)
    assert any("artifact-release instructions" in error for error in errors)


def test_check_cover_letter_rejects_missing_cluster_claim_boundary() -> None:
    """验证 cover letter 必须声明 cluster-level 主张的证据边界。"""

    module = _load_validate_manuscript_module()
    cover_letter_text = "\n".join(
        [
            "Dear Editor,",
            "We submit IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication.",
            "This anonymous preflight cover letter does not treat author declarations as finalized.",
            "Before final upload, the author-provided metadata must confirm originality, author approval, "
            "competing-interest status, funding, author contribution, permission, and generative AI declarations.",
            "The repository does not redistribute raw third-party data.",
            "full experimental outputs are not redistributed in Git.",
            "The repository includes artifact-release instructions.",
            "Released artifacts should include manifests and checksums.",
        ]
    )

    errors = module.check_cover_letter(cover_letter_text)

    assert any("cluster-level deployment quality" in error for error in errors)
    assert any("cluster artifacts" in error for error in errors)


def test_check_cover_letter_rejects_subjective_fit_language() -> None:
    """验证 cover letter 不应使用主观适配措辞。"""

    module = _load_validate_manuscript_module()
    cover_letter_text = "\n".join(
        [
            "Dear Editor,",
            "We submit IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication.",
            "This anonymous preflight cover letter does not treat author declarations as finalized.",
            "Before final upload, the author-provided metadata must confirm originality, author approval, "
            "competing-interest status, funding, author contribution, permission, and generative AI declarations.",
            "The repository does not redistribute raw third-party data.",
            "full experimental outputs are not redistributed in Git.",
            "The repository includes artifact-release instructions.",
            "Released artifacts should include manifests and checksums.",
            "The manuscript does not claim cluster-level deployment quality without cluster artifacts.",
            "We believe the paper is relevant to readers interested in scholarly data integration.",
        ]
    )

    errors = module.check_cover_letter(cover_letter_text)

    assert any("subjective fit language" in error for error in errors)
    assert any("We believe" in error for error in errors)


def test_check_submission_material_quantitative_summary_accepts_scoped_highlights() -> None:
    """验证投稿摘要材料接受带范围边界的 highlights 量化表述。"""

    module = _load_validate_manuscript_module()
    highlights_text = "\n".join(
        [
            "- Identity-agenda confusion causes risky scholarly work merges.",
            "- IAD-Risk separates identity, agenda, and ANI evidence.",
            "- IAD-Bench keeps gold, proxy, and silver labels separate.",
            "- Open-v2 scope-bounded evidence reports zero observed IAD-Risk HNFMR.",
            "- Cluster-level claims require artifact-backed audits.",
        ]
    )
    cover_letter_text = "\n".join(
        [
            "The manuscript reports an Open-v2 evidence snapshot.",
            "The result rows are scope-bounded mechanism evidence rather than a same-scope comparative ranking.",
            "Single-space scientific representation baselines show HNFMR 0.790--0.999 on the full pair scope.",
            "IAD-Risk reports same-work F1=0.980 and zero observed HNFMR on the held-out test scope.",
        ]
    )

    errors = module.check_submission_material_quantitative_summary(highlights_text, cover_letter_text)

    assert errors == []


def test_check_submission_material_quantitative_summary_rejects_unscoped_highlights() -> None:
    """验证投稿 highlights 的 HNFMR 数字缺少范围边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    highlights_text = "- IAD-Risk HNFMR=0.000."
    cover_letter_text = "\n".join(
        [
            "The manuscript reports an Open-v2 evidence snapshot.",
            "The result rows are scope-bounded mechanism evidence rather than a same-scope comparative ranking.",
            "Single-space scientific representation baselines show HNFMR 0.790--0.999 on the full pair scope.",
            "IAD-Risk reports same-work F1=0.980 and zero observed HNFMR on the held-out test scope.",
        ]
    )

    errors = module.check_submission_material_quantitative_summary(highlights_text, cover_letter_text)

    assert any("highlights missing scoped quantitative evidence marker" in error for error in errors)
    assert any("Open-v2 scope-bounded evidence" in error for error in errors)


def test_check_submission_material_quantitative_summary_rejects_cover_letter_without_scope_ranking_boundary() -> None:
    """验证投稿信必须说明 Open-v2 数字不是同范围比较排序。"""

    module = _load_validate_manuscript_module()
    highlights_text = "\n".join(
        [
            "- Identity-agenda confusion causes risky scholarly work merges.",
            "- IAD-Risk separates identity, agenda, and ANI evidence.",
            "- IAD-Bench keeps gold, proxy, and silver labels separate.",
            "- Open-v2 scope-bounded evidence reports zero observed IAD-Risk HNFMR.",
            "- Cluster-level claims require artifact-backed audits.",
        ]
    )
    cover_letter_text = "\n".join(
        [
            "The manuscript reports an Open-v2 evidence snapshot.",
            "Single-space scientific representation baselines show HNFMR 0.790--0.999 on the full pair scope.",
            "IAD-Risk reports same-work F1=0.980 and zero observed HNFMR on the held-out test scope.",
        ]
    )

    errors = module.check_submission_material_quantitative_summary(highlights_text, cover_letter_text)

    assert any("scope-bounded mechanism evidence" in error for error in errors)
    assert any("same-scope comparative ranking" in error for error in errors)


def test_check_editorial_claim_alignment_accepts_consistent_submission_materials() -> None:
    """验证首屏投稿材料主张一致时可通过检查。"""

    module = _load_validate_manuscript_module()
    title = "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication"
    manuscript_text = "\n".join(
        [
            rf"\title{{{title}}}",
            r"\begin{abstract}",
            "This paper studies identity-agenda confusion and proposes IAD-Risk.",
            "It evaluates IAD-Bench under an Open-v2 evidence snapshot.",
            "The result rows are scope-bounded mechanism evidence rather than a same-scope comparative ranking.",
            "The results include HNFMR 0.790--0.999 and zero observed HNFMR.",
            "The results support a conservative pair-level conclusion.",
            "Cluster-level quality claims require cluster artifacts before broad method-ranking claims.",
            r"\end{abstract}",
            r"\section{Conclusion}",
            "IAD-Risk addresses a specific failure mode by separating identity and agenda evidence.",
            "It uses false-merge risk and supports targeted false-merge suppression.",
            "The contribution includes a reproducible benchmark contract.",
            "It does not claim cluster-level deployment quality without cluster artifacts.",
            "Additional validation is needed before broad method ranking.",
        ]
    )
    cover_letter_text = "\n".join(
        [
            title,
            "The paper studies identity-agenda confusion and proposes IAD-Risk.",
            "The manuscript contributes IAD-Bench and reports an Open-v2 evidence snapshot.",
            "The result includes HNFMR 0.790--0.999 and zero observed HNFMR.",
            "The manuscript does not claim broad method superiority.",
            "raw third-party data and full experimental outputs are not redistributed in Git.",
        ]
    )
    highlights_text = "\n".join(
        [
            "- Identity-agenda confusion causes risky scholarly work merges.",
            "- IAD-Risk separates identity, agenda, and ANI evidence.",
            "- IAD-Bench keeps gold, proxy, and silver labels separate.",
            "- Open-v2 scope-bounded evidence reports zero observed IAD-Risk HNFMR.",
            "- Cluster-level claims require artifact-backed audits.",
        ]
    )
    keywords_text = (
        "scholarly entity matching; work deduplication; identity-agenda disentanglement; "
        "false-merge risk; provenance-aware evaluation"
    )
    metadata_text = "\n".join(
        [
            f'title: "{title}"',
            "broad_method_ranking_claimed: false",
            "silver_labels_claimed_as_human_gold: false",
            "artifact_release_required_before_final_upload: true",
        ]
    )

    errors = module.check_editorial_claim_alignment(
        manuscript_text,
        cover_letter_text,
        highlights_text,
        keywords_text,
        metadata_text,
    )

    assert errors == []


def test_check_editorial_claim_alignment_rejects_abstract_without_scope_ranking_boundary() -> None:
    """验证摘要必须说明 Open-v2 结果不是同范围排行榜。"""

    module = _load_validate_manuscript_module()
    title = "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication"
    manuscript_text = "\n".join(
        [
            rf"\title{{{title}}}",
            r"\begin{abstract}",
            "This paper studies identity-agenda confusion and proposes IAD-Risk.",
            "It evaluates IAD-Bench under an Open-v2 evidence snapshot.",
            "The results include HNFMR 0.790--0.999 and zero observed HNFMR.",
            "The results support a conservative pair-level conclusion.",
            "Cluster-level quality claims require cluster artifacts before broad method-ranking claims.",
            r"\end{abstract}",
            r"\section{Conclusion}",
            "IAD-Risk addresses a specific failure mode by separating identity and agenda evidence.",
            "It uses false-merge risk and supports targeted false-merge suppression.",
            "The contribution includes a reproducible benchmark contract.",
            "It does not claim cluster-level deployment quality without cluster artifacts.",
            "Additional validation is needed before broad method ranking.",
        ]
    )
    cover_letter_text = "\n".join(
        [
            title,
            "The paper studies identity-agenda confusion and proposes IAD-Risk.",
            "The manuscript contributes IAD-Bench and reports an Open-v2 evidence snapshot.",
            "The result includes HNFMR 0.790--0.999 and zero observed HNFMR.",
            "The manuscript does not claim broad method superiority.",
            "raw third-party data and full experimental outputs are not redistributed in Git.",
        ]
    )
    highlights_text = "- Open-v2 scope-bounded evidence reports zero observed IAD-Risk HNFMR."
    keywords_text = "scholarly entity matching; false-merge risk"
    metadata_text = "\n".join(
        [
            f'title: "{title}"',
            "broad_method_ranking_claimed: false",
            "silver_labels_claimed_as_human_gold: false",
            "artifact_release_required_before_final_upload: true",
        ]
    )

    errors = module.check_editorial_claim_alignment(
        manuscript_text,
        cover_letter_text,
        highlights_text,
        keywords_text,
        metadata_text,
    )

    assert any("scope-bounded mechanism evidence" in error for error in errors)
    assert any("same-scope comparative ranking" in error for error in errors)


def test_check_editorial_claim_alignment_rejects_abstract_without_pair_cluster_boundary() -> None:
    """验证首屏摘要必须同步声明 pair-level 结论与 cluster artifact 边界。"""

    module = _load_validate_manuscript_module()
    title = "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication"
    manuscript_text = "\n".join(
        [
            rf"\title{{{title}}}",
            r"\begin{abstract}",
            "This paper studies identity-agenda confusion and proposes IAD-Risk.",
            "It evaluates IAD-Bench under an Open-v2 evidence snapshot.",
            "The results include HNFMR 0.790--0.999 and zero observed HNFMR.",
            "The paper avoids broad method-ranking claims.",
            r"\end{abstract}",
            r"\section{Conclusion}",
            "IAD-Risk addresses a specific failure mode by separating identity and agenda evidence.",
            "It uses false-merge risk and supports targeted false-merge suppression.",
            "The contribution includes a reproducible benchmark contract.",
            "It does not claim cluster-level deployment quality without cluster artifacts.",
            "Additional validation is needed before broad method ranking.",
        ]
    )
    cover_letter_text = "\n".join(
        [
            title,
            "The paper studies identity-agenda confusion and proposes IAD-Risk.",
            "The manuscript contributes IAD-Bench and reports an Open-v2 evidence snapshot.",
            "The result includes HNFMR 0.790--0.999 and zero observed HNFMR.",
            "The manuscript does not claim broad method superiority.",
            "raw third-party data and full experimental outputs are not redistributed in Git.",
        ]
    )
    highlights_text = "\n".join(
        [
            "- Identity-agenda confusion causes risky scholarly work merges.",
            "- IAD-Risk separates identity, agenda, and ANI evidence.",
            "- IAD-Bench keeps gold, proxy, and silver labels separate.",
            "- Open-v2 scope-bounded evidence reports zero observed IAD-Risk HNFMR.",
            "- Cluster-level claims require artifact-backed audits.",
        ]
    )
    keywords_text = (
        "scholarly entity matching; work deduplication; identity-agenda disentanglement; "
        "false-merge risk; provenance-aware evaluation"
    )
    metadata_text = "\n".join(
        [
            f'title: "{title}"',
            "broad_method_ranking_claimed: false",
            "silver_labels_claimed_as_human_gold: false",
            "artifact_release_required_before_final_upload: true",
        ]
    )

    errors = module.check_editorial_claim_alignment(
        manuscript_text,
        cover_letter_text,
        highlights_text,
        keywords_text,
        metadata_text,
    )

    assert any("main abstract" in error for error in errors)
    assert any("pair-level conclusion" in error for error in errors)
    assert any("cluster artifacts" in error for error in errors)


def test_check_editorial_claim_alignment_rejects_conclusion_without_cluster_boundary() -> None:
    """验证结论必须同步声明 cluster-level 部署质量边界。"""

    module = _load_validate_manuscript_module()
    title = "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication"
    manuscript_text = "\n".join(
        [
            rf"\title{{{title}}}",
            r"\begin{abstract}",
            "This paper studies identity-agenda confusion and proposes IAD-Risk.",
            "It evaluates IAD-Bench under an Open-v2 evidence snapshot.",
            "The results include HNFMR 0.790--0.999 and zero observed HNFMR.",
            "The paper avoids broad method-ranking claims.",
            r"\end{abstract}",
            r"\section{Conclusion}",
            "IAD-Risk addresses a specific failure mode by separating identity and agenda evidence.",
            "It uses false-merge risk and supports targeted false-merge suppression.",
            "The contribution includes a reproducible benchmark contract.",
            "Additional validation is needed before broad method ranking.",
        ]
    )
    cover_letter_text = "\n".join(
        [
            title,
            "The paper studies identity-agenda confusion and proposes IAD-Risk.",
            "The manuscript contributes IAD-Bench and reports an Open-v2 evidence snapshot.",
            "The result includes HNFMR 0.790--0.999 and zero observed HNFMR.",
            "The manuscript does not claim broad method superiority.",
            "raw third-party data and full experimental outputs are not redistributed in Git.",
        ]
    )
    highlights_text = "\n".join(
        [
            "- Identity-agenda confusion causes risky scholarly work merges.",
            "- IAD-Risk separates identity, agenda, and ANI evidence.",
            "- IAD-Bench keeps gold, proxy, and silver labels separate.",
            "- Open-v2 scope-bounded evidence reports zero observed IAD-Risk HNFMR.",
            "- Cluster-level claims require artifact-backed audits.",
        ]
    )
    keywords_text = (
        "scholarly entity matching; work deduplication; identity-agenda disentanglement; "
        "false-merge risk; provenance-aware evaluation"
    )
    metadata_text = "\n".join(
        [
            f'title: "{title}"',
            "broad_method_ranking_claimed: false",
            "silver_labels_claimed_as_human_gold: false",
            "artifact_release_required_before_final_upload: true",
        ]
    )

    errors = module.check_editorial_claim_alignment(
        manuscript_text,
        cover_letter_text,
        highlights_text,
        keywords_text,
        metadata_text,
    )

    assert any("main conclusion" in error for error in errors)
    assert any("cluster-level deployment quality" in error for error in errors)


def test_check_editorial_claim_alignment_rejects_drifted_submission_materials() -> None:
    """验证首屏投稿材料缺少统一题名、证据和边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\title{Different Title}",
            r"\begin{abstract}",
            "This abstract says only that IAD-Risk works well.",
            r"\end{abstract}",
            r"\section{Conclusion}",
            "The method is strong.",
        ]
    )
    cover_letter_text = "This cover letter omits the bounded claim boundary."
    highlights_text = "- A short highlight."
    keywords_text = "entity matching"
    metadata_text = "broad_method_ranking_claimed: true"

    errors = module.check_editorial_claim_alignment(
        manuscript_text,
        cover_letter_text,
        highlights_text,
        keywords_text,
        metadata_text,
    )

    assert any("missing title" in error for error in errors)
    assert any("IAD-Bench" in error for error in errors)
    assert any("broad method-ranking claims" in error for error in errors)
    assert any("broad_method_ranking_claimed: false" in error for error in errors)


def test_check_auxiliary_model_evidence_absent_accepts_submission_materials() -> None:
    """验证正式投稿材料未包含辅助模型证据词时可通过检查。"""

    module = _load_validate_manuscript_module()
    document_texts = {
        "main manuscript": "Gold, proxy, and silver label strata are reported separately.",
        "supplementary material": "Artifact releases include manifests and checksums.",
    }

    errors = module.check_auxiliary_model_evidence_absent(document_texts)

    assert errors == []


def test_check_auxiliary_model_evidence_absent_rejects_unsupported_model_phrases() -> None:
    """验证正式投稿材料出现辅助模型证据词时会被拒绝。"""

    module = _load_validate_manuscript_module()
    document_texts = {
        "main manuscript": "The table includes an LLM pair-judge row.",
        "cover letter": "An OpenAI GPT baseline is included.",
    }

    errors = module.check_auxiliary_model_evidence_absent(document_texts)

    assert any("main manuscript" in error and "LLM" in error for error in errors)
    assert any("cover letter" in error and "GPT" in error for error in errors)


def test_check_auxiliary_model_evidence_absent_rejects_process_traces() -> None:
    """验证正式投稿材料出现 AI 工具或修改记录痕迹时会被拒绝。"""

    module = _load_validate_manuscript_module()
    document_texts = {
        "cover letter": "Codex work record: 本次修改 cleaned the documentation.",
        "highlights": "AI-generated submission summary.",
    }

    errors = module.check_auxiliary_model_evidence_absent(document_texts)

    assert any("cover letter" in error and "Codex" in error for error in errors)
    assert any("cover letter" in error and "本次修改" in error for error in errors)
    assert any("highlights" in error and "AI-generated" in error for error in errors)


def test_check_formal_submission_claim_lockdown_accepts_conservative_boundaries() -> None:
    """验证正式投稿材料中的保守主张边界不会被误判。"""

    module = _load_validate_manuscript_module()
    document_texts = {
        "main manuscript": "The paper does not make broad method-ranking claims.",
        "cover letter": "The claims remain bounded to the current evidence snapshot.",
    }

    errors = module.check_formal_submission_claim_lockdown(document_texts)

    assert errors == []


def test_check_formal_submission_claim_lockdown_rejects_q2b_completion_claims() -> None:
    """验证正式投稿材料中提前宣称 Q2/B 达标会被拒绝。"""

    module = _load_validate_manuscript_module()
    document_texts = {
        "abstract": "The manuscript is Q2/B-ready for submission.",
        "cover letter": "The paper meets Q2/B acceptance expectations.",
    }

    errors = module.check_formal_submission_claim_lockdown(document_texts)

    assert any("abstract" in error and "Q2/B completion claim" in error for error in errors)
    assert any("cover letter" in error and "Q2/B completion claim" in error for error in errors)


def test_check_formal_submission_claim_lockdown_rejects_chinese_completion_claims() -> None:
    """验证正式投稿材料中中文二区/B类达标措辞会被拒绝。"""

    module = _load_validate_manuscript_module()
    document_texts = {
        "cover letter": "本文已经达到二区/B类投稿标准。",
        "main manuscript": "The journal-submission-ready package is complete.",
    }

    errors = module.check_formal_submission_claim_lockdown(document_texts)

    assert any("cover letter" in error and "Q2/B completion claim" in error for error in errors)
    assert any("main manuscript" in error and "final-upload completion claim" in error for error in errors)


def test_check_formal_source_typography_hygiene_accepts_ascii_submission_text() -> None:
    """验证正式投稿材料使用 ASCII 标点和无编辑标记时可通过。"""

    module = _load_validate_manuscript_module()
    document_texts = {
        "main manuscript": "IAD-Risk uses risk-aware merge gating -- not a comparative ranking claim.",
        "cover letter": "The manuscript is complete as an anonymous pre-submission draft.",
    }

    errors = module.check_formal_source_typography_hygiene(document_texts)

    assert errors == []


def test_check_formal_source_typography_hygiene_rejects_unicode_punctuation_and_markers() -> None:
    """验证正式投稿材料中的 Unicode 标点和未完成编辑标记会被拒绝。"""

    module = _load_validate_manuscript_module()
    document_texts = {
        "main manuscript": "IAD-Risk uses risk-aware gating – not “broad superiority”.",
        "cover letter": "TODO replace this sentence and remove bad glyph �.",
    }

    errors = module.check_formal_source_typography_hygiene(document_texts)

    assert any("main manuscript" in error and "en dash" in error for error in errors)
    assert any("main manuscript" in error and "left double quotation mark" in error for error in errors)
    assert any("cover letter" in error and "unfinished edit marker TODO" in error for error in errors)
    assert any("cover letter" in error and "replacement character" in error for error in errors)


def test_check_formal_manuscript_review_language_accepts_method_review_terms() -> None:
    """验证正文方法学语义中的人工评审用语不会被误伤。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_formal_manuscript_review_language", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            "The protocol requires two independent reviewers.",
            "Human review process is specified as future validation.",
            "The manuscript reports manual-review evidence boundaries.",
        ]
    )

    errors = checker(manuscript_text)

    assert errors == []


def test_check_formal_manuscript_review_language_rejects_internal_audit_labels() -> None:
    """验证正式正文不得保留内部审稿清单式标签。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_formal_manuscript_review_language", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            "Reviewer interpretation supports fixed-threshold false-merge control.",
            "Main-table evidence & Required artifact IDs & Reviewer audit purpose.",
            "Availability class & Included location & Reviewer use.",
        ]
    )

    errors = checker(manuscript_text)

    assert any("Reviewer interpretation" in error for error in errors)
    assert any("Reviewer audit purpose" in error for error in errors)
    assert any("Reviewer use" in error for error in errors)


def test_check_submission_metadata_accepts_blank_preflight_author_declarations() -> None:
    """验证预投稿源元数据在作者未确认时保留空作者声明。"""

    module = _load_validate_manuscript_module()
    metadata_text = Path("manuscript/submission_metadata.yml").read_text(encoding="utf-8")

    errors = module.check_submission_metadata(metadata_text)

    assert errors == []


def test_check_submission_metadata_rejects_premature_preflight_author_declarations() -> None:
    """验证预投稿源元数据不得提前写入最终作者声明。"""

    module = _load_validate_manuscript_module()
    metadata_text = Path("manuscript/submission_metadata.yml").read_text(encoding="utf-8")
    metadata_text = metadata_text.replace(
        '  author_approval: ""',
        '  author_approval: "All listed authors have approved the submitted version."',
    )
    metadata_text = metadata_text.replace(
        '  competing_interests: ""',
        '  competing_interests: "The authors declare no competing interests."',
    )

    errors = module.check_submission_metadata(metadata_text)

    assert any("statements.author_approval" in error for error in errors)
    assert any("statements.competing_interests" in error for error in errors)


def _build_filled_final_upload_metadata_text(
    generative_ai_lines: list[str] | None = None,
    generative_ai_declaration_complete: bool = True,
) -> str:
    """构造用于 final-upload 门禁测试的完整投稿元数据文本。

    参数:
        generative_ai_lines: 生成式 AI 声明区的 YAML 行；None 表示使用合规默认值。
        generative_ai_declaration_complete: final-upload checklist 中生成式 AI 声明项的状态。

    返回:
        str: 可传入 check_final_upload_metadata 的 YAML 文本。
    """

    if generative_ai_lines is None:
        generative_ai_lines = [
            "generative_ai:",
            "  declaration_required_before_final_upload: true",
            '  ai_tools_used_in_manuscript_preparation: "none"',
            '  declaration_statement: "No generative AI tools were used in manuscript preparation."',
            "  author_review_and_responsibility_confirmed: true",
            "  ai_not_listed_as_author_confirmed: true",
            "  ai_generated_images_or_artwork_included: false",
        ]

    checklist_value = str(generative_ai_declaration_complete).lower()
    metadata_lines = [
        'target_journal: "Journal of Scholarly Data"',
        "target_journal_template_bound: true",
        "target_preparation:",
        '  selected_author_guide_source: "official journal guide for authors"',
        '  selected_author_guide_rechecked_date: "2026-06-19"',
        "  selected_template_requirements_confirmed: true",
        "  ranking_confirmation_required_before_final_upload: true",
        "  ranking_confirmation_completed: true",
        '  ranking_confirmation_source: "institutional ranking system"',
        '  ranking_confirmation_checked_date: "2026-06-19"',
        "  selected_target_requires_author_confirmation: true",
        "  selected_target_author_confirmed: true",
        "authors:",
        '  - name: "Example Author"',
        '    affiliation: "Example University"',
        '    email: "author@example.edu"',
        '    orcid: "0000-0002-1825-0097"',
        "author_identity_materials:",
        "  author_biography_and_photo_required_before_upload: false",
        "  biography_files: []",
        "  photograph_files: []",
        "  author_identity_materials_verified: true",
        "corresponding_author:",
        '  name: "Example Author"',
        '  affiliation: "Example University"',
        '  email: "author@example.edu"',
        '  orcid: "0000-0002-1825-0097"',
        "funding:",
        "  no_external_funding_declared: true",
        '  funding_statement: "The authors received no external funding for this work."',
        "  funding_sources: []",
        "  grant_numbers: []",
        "statements:",
        '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
        '  author_approval: "All listed authors have approved the submitted version."',
        '  competing_interests: "The authors declare no competing interests."',
        '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
        '  data_code_availability: "Source code and fixtures are available at https://example.org/iad-sieve.git commit abcdef1234567890; full result artifacts are available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
        "author_contributions:",
        "  credit_taxonomy_required_before_final_upload: true",
        '  contribution_statement: "Example Author: conceptualization, methodology, software, validation, and writing - original draft."',
        "  roles:",
        '    - author: "Example Author"',
        '      credit_roles: "Conceptualization; Methodology; Software; Validation; Writing - original draft"',
        "permissions:",
        "  no_third_party_material_requiring_permission_declared: true",
        "  third_party_material_requires_permission: false",
        '  permissions_statement: "No third-party material requiring permission is included."',
        "  permission_files: []",
        *generative_ai_lines,
        "repository_reference:",
        '  repository_url: "https://example.org/iad-sieve.git"',
        '  repository_commit: "abcdef1234567890"',
        '  repository_branch: "main"',
        "artifact_boundary:",
        '  artifact_release_url: "https://doi.org/10.0000/example"',
        '  artifact_release_doi: "10.0000/example"',
        "upload_preparation:",
        "  live_submission_system_verified: true",
        "  final_upload_package_verified_against_system: true",
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
        f"  generative_ai_declaration_complete: {checklist_value}",
        "  manuscript_pdf_rebuilt_after_template: true",
        "  supplementary_pdf_rebuilt_after_template: true",
        "  submission_system_files_verified: true",
        "  first_screen_claim_lockdown_confirmed: true",
        "  artifact_release_prepared_or_linked: true",
    ]
    return "\n".join(metadata_lines)


def test_check_final_upload_metadata_rejects_placeholders() -> None:
    """验证 final-upload 门禁会拒绝未填写的投稿元数据。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: ""',
            "target_journal_template_bound: false",
            "authors: []",
            'name: ""',
            'affiliation: ""',
            'email: ""',
            "target_journal_selected: false",
            "article_type_confirmed: false",
            "review_mode_confirmed: false",
            "target_journal_template_applied: false",
            "author_metadata_completed: false",
            "corresponding_author_completed: false",
            "funding_statement_text_ready: false",
            "contribution_statement_complete: false",
            "permissions_statement_complete: false",
            "generative_ai_declaration_complete: false",
            "manuscript_pdf_rebuilt_after_template: false",
            "supplementary_pdf_rebuilt_after_template: false",
            "submission_system_files_verified: false",
            "artifact_release_prepared_or_linked: false",
        ]
    )

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("target journal is empty" in error for error in errors)
    assert any("author list is empty" in error for error in errors)
    assert any("corresponding author email is empty" in error for error in errors)
    assert any("article type checklist item is incomplete" in error for error in errors)
    assert any("review mode checklist item is incomplete" in error for error in errors)
    assert any("funding statement text checklist item is incomplete" in error for error in errors)
    assert any("author contribution statement checklist item is incomplete" in error for error in errors)
    assert any("permissions statement checklist item is incomplete" in error for error in errors)
    assert any("generative AI declaration checklist item is incomplete" in error for error in errors)
    assert any("artifact release checklist item is incomplete" in error for error in errors)


def test_check_final_upload_metadata_accepts_filled_metadata() -> None:
    """验证 final-upload 门禁接受已填写目标期刊和作者信息的元数据。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "target_preparation:",
            '  selected_author_guide_source: "official journal guide for authors"',
            '  selected_author_guide_rechecked_date: "2026-06-19"',
            "  selected_template_requirements_confirmed: true",
            "  ranking_confirmation_required_before_final_upload: true",
            "  ranking_confirmation_completed: true",
            '  ranking_confirmation_source: "institutional ranking system"',
            '  ranking_confirmation_checked_date: "2026-06-19"',
            "  selected_target_requires_author_confirmation: true",
            "  selected_target_author_confirmed: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "author_identity_materials:",
            "  author_biography_and_photo_required_before_upload: false",
            "  biography_files: []",
            "  photograph_files: []",
            "  author_identity_materials_verified: true",
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: "The authors received no external funding for this work."',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
            '  author_approval: "All listed authors have approved the submitted version."',
            '  competing_interests: "The authors declare no competing interests."',
            '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
            '  data_code_availability: "Source code and fixtures are available at https://example.org/iad-sieve.git commit abcdef1234567890; full result artifacts are available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
            "author_contributions:",
            "  credit_taxonomy_required_before_final_upload: true",
            '  contribution_statement: "Example Author: conceptualization, methodology, software, validation, and writing - original draft."',
            "  roles:",
            '    - author: "Example Author"',
            '      credit_roles: "Conceptualization; Methodology; Software; Validation; Writing - original draft"',
            "permissions:",
            "  no_third_party_material_requiring_permission_declared: true",
            "  third_party_material_requires_permission: false",
            '  permissions_statement: "No third-party material requiring permission is included."',
            "  permission_files: []",
            "generative_ai:",
            "  declaration_required_before_final_upload: true",
            "  ai_tools_used_in_manuscript_preparation: \"none\"",
            "  declaration_statement: \"No generative AI tools were used in manuscript preparation.\"",
            "  author_review_and_responsibility_confirmed: true",
            "  ai_not_listed_as_author_confirmed: true",
            "  ai_generated_images_or_artwork_included: false",
            "repository_reference:",
            '  repository_url: "https://example.org/iad-sieve.git"',
            '  repository_commit: "abcdef1234567890"',
            '  repository_branch: "main"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
            "upload_preparation:",
            "  live_submission_system_verified: true",
            "  final_upload_package_verified_against_system: true",
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert errors == []


def test_check_final_upload_metadata_rejects_missing_author_guide_confirmation() -> None:
    """验证 final-upload 门禁拒绝缺失的作者指南和模板要求确认。"""

    module = _load_validate_manuscript_module()
    metadata_text = _build_filled_final_upload_metadata_text()
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("selected author guide source is missing" in error for error in errors)
    assert any("selected author guide rechecked date is missing" in error for error in errors)
    assert any("selected template requirements confirmation is incomplete" in error for error in errors)


def test_check_final_upload_metadata_rejects_missing_target_ranking_confirmation() -> None:
    """验证 final-upload 门禁拒绝未确认的选刊排名或类别信息。"""

    module = _load_validate_manuscript_module()
    metadata_text = _build_filled_final_upload_metadata_text()
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("ranking/category confirmation is incomplete" in error for error in errors)
    assert any("ranking/category confirmation source is missing" in error for error in errors)
    assert any("ranking/category confirmation checked date is missing" in error for error in errors)
    assert any("selected target journal author confirmation is incomplete" in error for error in errors)


def test_check_final_upload_metadata_rejects_missing_live_system_verification() -> None:
    """验证 final-upload 门禁拒绝未完成的 live system 终检记录。"""

    module = _load_validate_manuscript_module()
    metadata_text = _build_filled_final_upload_metadata_text()
    metadata_text = metadata_text.replace(
        "  live_submission_system_verified: true",
        "  live_submission_system_verified: false",
    )
    metadata_text = metadata_text.replace(
        "  final_upload_package_verified_against_system: true",
        "  final_upload_package_verified_against_system: false",
    )

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("live submission system verification is incomplete" in error for error in errors)
    assert any("final upload package verification against live system is incomplete" in error for error in errors)


def test_check_final_upload_metadata_rejects_missing_dke_author_identity_materials() -> None:
    """验证 DKE final-upload 门禁拒绝缺失的作者简历和照片材料清单。"""

    module = _load_validate_manuscript_module()
    metadata_text = _build_filled_final_upload_metadata_text()
    metadata_text = metadata_text.replace(
        'target_journal: "Journal of Scholarly Data"',
        "\n".join(
            [
                'target_journal: "Data & Knowledge Engineering"',
                'review_mode: "single_anonymized_with_final_author_identities"',
            ]
        ),
    )
    metadata_text = metadata_text.replace(
        "  author_biography_and_photo_required_before_upload: false",
        "  author_biography_and_photo_required_before_upload: true",
    )
    metadata_text = metadata_text.replace(
        "  author_identity_materials_verified: true",
        "  author_identity_materials_verified: false",
    )

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("author biography file list is missing" in error for error in errors)
    assert any("author photograph file list is missing" in error for error in errors)
    assert any("author identity materials verification is incomplete" in error for error in errors)


def test_check_final_upload_metadata_rejects_missing_generative_ai_declaration() -> None:
    """验证 final-upload 门禁拒绝缺失的生成式 AI 声明。"""

    module = _load_validate_manuscript_module()
    metadata_text = _build_filled_final_upload_metadata_text(
        generative_ai_lines=[],
        generative_ai_declaration_complete=False,
    )

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("generative AI declaration checklist item is incomplete" in error for error in errors)
    assert any("generative AI use status is missing" in error for error in errors)
    assert any("generative AI declaration statement is missing" in error for error in errors)
    assert any("generative AI author review confirmation is incomplete" in error for error in errors)
    assert any("AI authorship exclusion confirmation is incomplete" in error for error in errors)


def test_check_final_upload_metadata_rejects_ai_generated_artwork_without_clearance() -> None:
    """验证 final-upload 门禁拒绝未被选刊路线允许的 AI 生成图像或 artwork。"""

    module = _load_validate_manuscript_module()
    metadata_text = _build_filled_final_upload_metadata_text(
        generative_ai_lines=[
            "generative_ai:",
            "  declaration_required_before_final_upload: true",
            '  ai_tools_used_in_manuscript_preparation: "language editing"',
            '  declaration_statement: "The authors reviewed and take responsibility for all manuscript content."',
            "  author_review_and_responsibility_confirmed: true",
            "  ai_not_listed_as_author_confirmed: true",
            "  ai_generated_images_or_artwork_included: true",
        ],
    )

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("machine-generated figures or artwork are not cleared for the selected submission route" in error for error in errors)


def test_check_final_upload_metadata_rejects_missing_repository_reference() -> None:
    """验证 final-upload 门禁拒绝缺少仓库 URL 或提交版本的元数据。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: "The authors received no external funding for this work."',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
            '  author_approval: "All listed authors have approved the submitted version."',
            '  competing_interests: "The authors declare no competing interests."',
            '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
            '  data_code_availability: "Source code and fixtures are available at https://example.org/iad-sieve.git commit abcdef1234567890; full result artifacts are available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
            "author_contributions:",
            "  credit_taxonomy_required_before_final_upload: true",
            '  contribution_statement: "Example Author: conceptualization, methodology, software, validation, and writing - original draft."',
            "  roles:",
            '    - author: "Example Author"',
            '      credit_roles: "Conceptualization; Methodology; Software; Validation; Writing - original draft"',
            "permissions:",
            "  no_third_party_material_requiring_permission_declared: true",
            "  third_party_material_requires_permission: false",
            '  permissions_statement: "No third-party material requiring permission is included."',
            "  permission_files: []",
            "generative_ai:",
            "  declaration_required_before_final_upload: true",
            "  ai_tools_used_in_manuscript_preparation: \"none\"",
            "  declaration_statement: \"No generative AI tools were used in manuscript preparation.\"",
            "  author_review_and_responsibility_confirmed: true",
            "  ai_not_listed_as_author_confirmed: true",
            "  ai_generated_images_or_artwork_included: false",
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
            "upload_preparation:",
            "  live_submission_system_verified: true",
            "  final_upload_package_verified_against_system: true",
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("repository URL is missing" in error for error in errors)
    assert any("repository commit is missing" in error for error in errors)


def test_check_final_upload_metadata_rejects_data_code_statement_without_release_references() -> None:
    """验证 data/code availability 必须写入仓库版本和 artifact 链接。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: "The authors received no external funding for this work."',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
            '  author_approval: "All listed authors have approved the submitted version."',
            '  competing_interests: "The authors declare no competing interests."',
            '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
            '  data_code_availability: "The repository provides source code, fixtures, and artifact-release instructions."',
            "author_contributions:",
            "  credit_taxonomy_required_before_final_upload: true",
            '  contribution_statement: "Example Author: conceptualization, methodology, software, validation, and writing - original draft."',
            "  roles:",
            '    - author: "Example Author"',
            '      credit_roles: "Conceptualization; Methodology; Software; Validation; Writing - original draft"',
            "permissions:",
            "  no_third_party_material_requiring_permission_declared: true",
            "  third_party_material_requires_permission: false",
            '  permissions_statement: "No third-party material requiring permission is included."',
            "  permission_files: []",
            "generative_ai:",
            "  declaration_required_before_final_upload: true",
            "  ai_tools_used_in_manuscript_preparation: \"none\"",
            "  declaration_statement: \"No generative AI tools were used in manuscript preparation.\"",
            "  author_review_and_responsibility_confirmed: true",
            "  ai_not_listed_as_author_confirmed: true",
            "  ai_generated_images_or_artwork_included: false",
            "repository_reference:",
            '  repository_url: "https://example.org/iad-sieve.git"',
            '  repository_commit: "abcdef1234567890"',
            '  repository_branch: "main"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("data/code availability statement missing repository URL value" in error for error in errors)
    assert any("data/code availability statement missing repository commit value" in error for error in errors)
    assert any("data/code availability statement missing artifact release URL or DOI value" in error for error in errors)


def test_check_final_upload_metadata_rejects_corresponding_author_outside_author_list() -> None:
    """验证通讯作者不在作者列表中时 final-upload 门禁会拒绝。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Different Author"',
            '  affiliation: "Example University"',
            '  email: "different@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("corresponding author must match an author row by name or email" in error for error in errors)


def test_check_final_upload_metadata_rejects_missing_funding_statement() -> None:
    """验证 final-upload 门禁拒绝缺少资助或无外部资助声明的元数据。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  funding_sources: []",
            "  grant_numbers: []",
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("funding statement text is missing" in error for error in errors)


def test_check_final_upload_metadata_rejects_no_external_funding_without_statement_text() -> None:
    """验证无外部资助也必须提供正式 funding statement 文本。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: ""',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
            '  author_approval: "All listed authors have approved the submitted version."',
            '  competing_interests: "The authors declare no competing interests."',
            '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
            '  data_code_availability: "Source code and fixtures are available at https://example.org/iad-sieve.git commit abcdef1234567890; full result artifacts are available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
            "author_contributions:",
            "  credit_taxonomy_required_before_final_upload: true",
            '  contribution_statement: "Example Author: conceptualization, methodology, software, validation, and writing - original draft."',
            "  roles:",
            '    - author: "Example Author"',
            '      credit_roles: "Conceptualization; Methodology; Software; Validation; Writing - original draft"',
            "permissions:",
            "  no_third_party_material_requiring_permission_declared: true",
            "  third_party_material_requires_permission: false",
            '  permissions_statement: "No third-party material requiring permission is included."',
            "  permission_files: []",
            "generative_ai:",
            "  declaration_required_before_final_upload: true",
            "  ai_tools_used_in_manuscript_preparation: \"none\"",
            "  declaration_statement: \"No generative AI tools were used in manuscript preparation.\"",
            "  author_review_and_responsibility_confirmed: true",
            "  ai_not_listed_as_author_confirmed: true",
            "  ai_generated_images_or_artwork_included: false",
            "repository_reference:",
            '  repository_url: "https://example.org/iad-sieve.git"',
            '  repository_commit: "abcdef1234567890"',
            '  repository_branch: "main"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("funding statement text is missing" in error for error in errors)


def test_check_final_upload_metadata_rejects_missing_submission_statements() -> None:
    """验证 final-upload 门禁拒绝缺少原创性、作者批准、伦理和可用性声明。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: "The authors received no external funding for this work."',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  competing_interests: "The authors declare no competing interests."',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("originality statement is missing" in error for error in errors)
    assert any("author approval statement is missing" in error for error in errors)
    assert any("ethics statement is missing" in error for error in errors)
    assert any("data/code availability statement is missing" in error for error in errors)


def test_check_final_upload_metadata_rejects_missing_research_data_statement_for_information_systems() -> None:
    """验证 Information Systems final-upload 元数据必须包含 research data statement。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Information Systems"',
            'review_mode: "single_anonymized_with_final_author_identities"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: "The authors received no external funding for this work."',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
            '  author_approval: "All listed authors have approved the submitted version."',
            '  competing_interests: "The authors declare no competing interests."',
            '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
            '  data_code_availability: "The repository provides source code, fixtures, and artifact-release instructions."',
            "author_contributions:",
            "  credit_taxonomy_required_before_final_upload: true",
            '  contribution_statement: "Example Author: conceptualization and writing - original draft."',
            "  roles:",
            '    - author: "Example Author"',
            '      credit_roles: "Conceptualization; Writing - original draft"',
            "permissions:",
            "  no_third_party_material_requiring_permission_declared: true",
            "  third_party_material_requires_permission: false",
            '  permissions_statement: "No third-party material requiring permission is included."',
            "  permission_files: []",
            "generative_ai:",
            "  declaration_required_before_final_upload: true",
            "  ai_tools_used_in_manuscript_preparation: \"none\"",
            "  declaration_statement: \"No generative AI tools were used in manuscript preparation.\"",
            "  author_review_and_responsibility_confirmed: true",
            "  ai_not_listed_as_author_confirmed: true",
            "  ai_generated_images_or_artwork_included: false",
            "repository_reference:",
            '  repository_url: "https://example.org/iad-sieve.git"',
            '  repository_commit: "abcdef1234567890"',
            '  repository_branch: "main"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("research data statement is missing for Information Systems" in error for error in errors)


def test_check_final_upload_metadata_rejects_missing_research_data_statement_for_dke() -> None:
    """验证 DKE final-upload 元数据必须包含 research data statement。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Data & Knowledge Engineering"',
            'review_mode: "single_anonymized_with_final_author_identities"',
            "target_journal_template_bound: true",
            "target_preparation:",
            '  selected_author_guide_source: "official journal guide for authors"',
            '  selected_author_guide_rechecked_date: "2026-06-19"',
            "  selected_template_requirements_confirmed: true",
            "  ranking_confirmation_required_before_final_upload: true",
            "  ranking_confirmation_completed: true",
            '  ranking_confirmation_source: "institutional ranking system"',
            '  ranking_confirmation_checked_date: "2026-06-19"',
            "  selected_target_requires_author_confirmation: true",
            "  selected_target_author_confirmed: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: "The authors received no external funding for this work."',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
            '  author_approval: "All listed authors have approved the submitted version."',
            '  competing_interests: "The authors declare no competing interests."',
            '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
            '  data_code_availability: "The repository provides source code, fixtures, and artifact-release instructions."',
            "author_contributions:",
            "  credit_taxonomy_required_before_final_upload: true",
            '  contribution_statement: "Example Author: conceptualization and writing - original draft."',
            "  roles:",
            '    - author: "Example Author"',
            '      credit_roles: "Conceptualization; Writing - original draft"',
            "permissions:",
            "  no_third_party_material_requiring_permission_declared: true",
            "  third_party_material_requires_permission: false",
            '  permissions_statement: "No third-party material requiring permission is included."',
            "  permission_files: []",
            "generative_ai:",
            "  declaration_required_before_final_upload: true",
            "  ai_tools_used_in_manuscript_preparation: \"none\"",
            "  declaration_statement: \"No generative AI tools were used in manuscript preparation.\"",
            "  author_review_and_responsibility_confirmed: true",
            "  ai_not_listed_as_author_confirmed: true",
            "  ai_generated_images_or_artwork_included: false",
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("research data statement is missing for Data & Knowledge Engineering" in error for error in errors)


def test_check_final_upload_metadata_rejects_research_data_statement_without_artifact_link() -> None:
    """验证 DKE research data statement 必须包含 artifact URL 或 DOI。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Data & Knowledge Engineering"',
            'review_mode: "single_anonymized_with_final_author_identities"',
            "target_journal_template_bound: true",
            "target_preparation:",
            "  ranking_confirmation_required_before_final_upload: true",
            "  ranking_confirmation_completed: true",
            '  ranking_confirmation_source: "institutional ranking system"',
            '  ranking_confirmation_checked_date: "2026-06-19"',
            "  selected_target_requires_author_confirmation: true",
            "  selected_target_author_confirmed: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: "The authors received no external funding for this work."',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
            '  author_approval: "All listed authors have approved the submitted version."',
            '  competing_interests: "The authors declare no competing interests."',
            '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
            '  data_code_availability: "The repository provides source code, fixtures, and artifact-release instructions."',
            '  research_data_statement: "The research data are described in the public repository."',
            "author_contributions:",
            "  credit_taxonomy_required_before_final_upload: true",
            '  contribution_statement: "Example Author: conceptualization and writing - original draft."',
            "  roles:",
            '    - author: "Example Author"',
            '      credit_roles: "Conceptualization; Writing - original draft"',
            "permissions:",
            "  no_third_party_material_requiring_permission_declared: true",
            "  third_party_material_requires_permission: false",
            '  permissions_statement: "No third-party material requiring permission is included."',
            "  permission_files: []",
            "generative_ai:",
            "  declaration_required_before_final_upload: true",
            "  ai_tools_used_in_manuscript_preparation: \"none\"",
            "  declaration_statement: \"No generative AI tools were used in manuscript preparation.\"",
            "  author_review_and_responsibility_confirmed: true",
            "  ai_not_listed_as_author_confirmed: true",
            "  ai_generated_images_or_artwork_included: false",
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any(
        "research data statement missing artifact release URL or DOI value for Data & Knowledge Engineering" in error
        for error in errors
    )


def test_check_final_upload_metadata_accepts_dke_research_data_statement_with_artifact_link() -> None:
    """验证 DKE research data statement 包含 artifact URL 时通过元数据门禁。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Data & Knowledge Engineering"',
            'review_mode: "single_anonymized_with_final_author_identities"',
            "target_journal_template_bound: true",
            "target_preparation:",
            '  selected_author_guide_source: "official journal guide for authors"',
            '  selected_author_guide_rechecked_date: "2026-06-19"',
            "  selected_template_requirements_confirmed: true",
            "  ranking_confirmation_required_before_final_upload: true",
            "  ranking_confirmation_completed: true",
            '  ranking_confirmation_source: "institutional ranking system"',
            '  ranking_confirmation_checked_date: "2026-06-19"',
            "  selected_target_requires_author_confirmation: true",
            "  selected_target_author_confirmed: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: "The authors received no external funding for this work."',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
            '  author_approval: "All listed authors have approved the submitted version."',
            '  competing_interests: "The authors declare no competing interests."',
            '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
            '  data_code_availability: "Source code and fixtures are available at https://example.org/iad-sieve.git commit abcdef1234567890; full result artifacts are available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
            '  research_data_statement: "Source code and small fixtures are available in the repository; the full result artifact is available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
            "author_identity_materials:",
            "  author_biography_and_photo_required_before_upload: true",
            '  biography_files: ["author-materials/example-author-biography.md"]',
            '  photograph_files: ["author-materials/example-author-photo.jpg"]',
            "  author_identity_materials_verified: true",
            "author_contributions:",
            "  credit_taxonomy_required_before_final_upload: true",
            '  contribution_statement: "Example Author: conceptualization, methodology, software, validation, and writing - original draft."',
            "  roles:",
            '    - author: "Example Author"',
            '      credit_roles: "Conceptualization; Methodology; Software; Validation; Writing - original draft"',
            "permissions:",
            "  no_third_party_material_requiring_permission_declared: true",
            "  third_party_material_requires_permission: false",
            '  permissions_statement: "No third-party material requiring permission is included."',
            "  permission_files: []",
            "generative_ai:",
            "  declaration_required_before_final_upload: true",
            "  ai_tools_used_in_manuscript_preparation: \"none\"",
            "  declaration_statement: \"No generative AI tools were used in manuscript preparation.\"",
            "  author_review_and_responsibility_confirmed: true",
            "  ai_not_listed_as_author_confirmed: true",
            "  ai_generated_images_or_artwork_included: false",
            "repository_reference:",
            '  repository_url: "https://example.org/iad-sieve.git"',
            '  repository_commit: "abcdef1234567890"',
            '  repository_branch: "main"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
            "upload_preparation:",
            "  live_submission_system_verified: true",
            "  final_upload_package_verified_against_system: true",
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert errors == []


def test_check_final_upload_metadata_rejects_missing_author_contribution_statement() -> None:
    """验证 final-upload 门禁拒绝缺少作者贡献声明的元数据。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: "The authors received no external funding for this work."',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
            '  author_approval: "All listed authors have approved the submitted version."',
            '  competing_interests: "The authors declare no competing interests."',
            '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
            '  data_code_availability: "The repository provides source code, fixtures, and artifact-release instructions."',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("author contribution statement is missing" in error for error in errors)


def test_check_final_upload_metadata_rejects_missing_credit_roles_when_required() -> None:
    """验证 final-upload 门禁在需要 CRediT 时拒绝缺少标准角色的元数据。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Data & Knowledge Engineering"',
            'review_mode: "single_anonymized_with_final_author_identities"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: "The authors received no external funding for this work."',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
            '  author_approval: "All listed authors have approved the submitted version."',
            '  competing_interests: "The authors declare no competing interests."',
            '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
            '  data_code_availability: "The repository provides source code, fixtures, and artifact-release instructions."',
            "author_contributions:",
            "  credit_taxonomy_required_before_final_upload: true",
            '  contribution_statement: "Example Author completed the study."',
            "  roles: []",
            "permissions:",
            "  no_third_party_material_requiring_permission_declared: true",
            "  third_party_material_requires_permission: false",
            '  permissions_statement: "No third-party material requiring permission is included."',
            "  permission_files: []",
            "generative_ai:",
            "  declaration_required_before_final_upload: true",
            "  ai_tools_used_in_manuscript_preparation: \"none\"",
            "  declaration_statement: \"No generative AI tools were used in manuscript preparation.\"",
            "  author_review_and_responsibility_confirmed: true",
            "  ai_not_listed_as_author_confirmed: true",
            "  ai_generated_images_or_artwork_included: false",
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("CRediT author contribution roles are missing" in error for error in errors)


def test_check_final_upload_metadata_rejects_empty_credit_roles_by_default() -> None:
    """验证 final-upload 门禁默认要求 CRediT 角色，不能用空 roles 通过。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: "The authors received no external funding for this work."',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
            '  author_approval: "All listed authors have approved the submitted version."',
            '  competing_interests: "The authors declare no competing interests."',
            '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
            '  data_code_availability: "Source code and fixtures are available at https://example.org/iad-sieve.git commit abcdef1234567890; full result artifacts are available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
            "author_contributions:",
            '  contribution_statement: "Example Author: conceptualization, methodology, software, validation, and writing - original draft."',
            "  roles: []",
            "permissions:",
            "  no_third_party_material_requiring_permission_declared: true",
            "  third_party_material_requires_permission: false",
            '  permissions_statement: "No third-party material requiring permission is included."',
            "  permission_files: []",
            "generative_ai:",
            "  declaration_required_before_final_upload: true",
            "  ai_tools_used_in_manuscript_preparation: \"none\"",
            "  declaration_statement: \"No generative AI tools were used in manuscript preparation.\"",
            "  author_review_and_responsibility_confirmed: true",
            "  ai_not_listed_as_author_confirmed: true",
            "  ai_generated_images_or_artwork_included: false",
            "repository_reference:",
            '  repository_url: "https://example.org/iad-sieve.git"',
            '  repository_commit: "abcdef1234567890"',
            '  repository_branch: "main"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("CRediT author contribution roles are missing" in error for error in errors)


def test_check_final_upload_metadata_rejects_missing_credit_roles_for_each_author() -> None:
    """验证 CRediT 角色必须覆盖每一位作者。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Data & Knowledge Engineering"',
            'review_mode: "single_anonymized_with_final_author_identities"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "First Author"',
            '    affiliation: "Example University"',
            '    email: "first@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            '  - name: "Second Author"',
            '    affiliation: "Example Institute"',
            '    email: "second@example.edu"',
            '    orcid: "0000-0002-1694-233X"',
            "corresponding_author:",
            '  name: "First Author"',
            '  affiliation: "Example University"',
            '  email: "first@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: "The authors received no external funding for this work."',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
            '  author_approval: "All listed authors have approved the submitted version."',
            '  competing_interests: "The authors declare no competing interests."',
            '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
            '  data_code_availability: "Source code and fixtures are available at https://example.org/iad-sieve.git commit abcdef1234567890; full result artifacts are available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
            '  research_data_statement: "The full result artifact is available at https://doi.org/10.0000/example."',
            "author_contributions:",
            "  credit_taxonomy_required_before_final_upload: true",
            '  contribution_statement: "First Author: conceptualization and writing - original draft. Second Author: validation."',
            "  roles:",
            '    - author: "First Author"',
            '      credit_roles: "Conceptualization; Writing - original draft"',
            "permissions:",
            "  no_third_party_material_requiring_permission_declared: true",
            "  third_party_material_requires_permission: false",
            '  permissions_statement: "No third-party material requiring permission is included."',
            "  permission_files: []",
            "generative_ai:",
            "  declaration_required_before_final_upload: true",
            "  ai_tools_used_in_manuscript_preparation: \"none\"",
            "  declaration_statement: \"No generative AI tools were used in manuscript preparation.\"",
            "  author_review_and_responsibility_confirmed: true",
            "  ai_not_listed_as_author_confirmed: true",
            "  ai_generated_images_or_artwork_included: false",
            "repository_reference:",
            '  repository_url: "https://example.org/iad-sieve.git"',
            '  repository_commit: "abcdef1234567890"',
            '  repository_branch: "main"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("CRediT author contribution roles missing for author: Second Author" in error for error in errors)


def test_check_final_upload_metadata_rejects_missing_permissions_statement() -> None:
    """验证 final-upload 门禁拒绝缺少第三方材料许可声明的元数据。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: "The authors received no external funding for this work."',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
            '  author_approval: "All listed authors have approved the submitted version."',
            '  competing_interests: "The authors declare no competing interests."',
            '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
            '  data_code_availability: "The repository provides source code, fixtures, and artifact-release instructions."',
            "author_contributions:",
            '  contribution_statement: "Example Author: conceptualization, methodology, software, validation, and writing - original draft."',
            "  roles: []",
            "permissions:",
            "  third_party_material_requires_permission: false",
            '  permissions_statement: ""',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("permissions statement is missing" in error for error in errors)


def test_check_final_upload_metadata_rejects_no_permission_without_statement_text() -> None:
    """验证无需第三方材料许可时仍必须提供正式 permissions statement 文本。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "funding:",
            "  no_external_funding_declared: true",
            '  funding_statement: "The authors received no external funding for this work."',
            "  funding_sources: []",
            "  grant_numbers: []",
            "statements:",
            '  originality: "The manuscript is original, has not been published previously, and is not under consideration elsewhere."',
            '  author_approval: "All listed authors have approved the submitted version."',
            '  competing_interests: "The authors declare no competing interests."',
            '  ethics: "This study uses public scholarly metadata and does not involve human participants."',
            '  data_code_availability: "Source code and fixtures are available at https://example.org/iad-sieve.git commit abcdef1234567890; full result artifacts are available at https://doi.org/10.0000/example. Raw third-party data are not redistributed in Git."',
            "author_contributions:",
            "  credit_taxonomy_required_before_final_upload: true",
            '  contribution_statement: "Example Author: conceptualization, methodology, software, validation, and writing - original draft."',
            "  roles:",
            '    - author: "Example Author"',
            '      credit_roles: "Conceptualization; Methodology; Software; Validation; Writing - original draft"',
            "permissions:",
            "  no_third_party_material_requiring_permission_declared: true",
            "  third_party_material_requires_permission: false",
            '  permissions_statement: ""',
            "  permission_files: []",
            "generative_ai:",
            "  declaration_required_before_final_upload: true",
            "  ai_tools_used_in_manuscript_preparation: \"none\"",
            "  declaration_statement: \"No generative AI tools were used in manuscript preparation.\"",
            "  author_review_and_responsibility_confirmed: true",
            "  ai_not_listed_as_author_confirmed: true",
            "  ai_generated_images_or_artwork_included: false",
            "repository_reference:",
            '  repository_url: "https://example.org/iad-sieve.git"',
            '  repository_commit: "abcdef1234567890"',
            '  repository_branch: "main"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("permissions statement is missing" in error for error in errors)


def test_check_final_upload_metadata_rejects_duplicate_author_orcid() -> None:
    """验证多个作者行使用同一 ORCID 时 final-upload 门禁会拒绝。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            '  - name: "Second Author"',
            '    affiliation: "Example Institute"',
            '    email: "second@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("duplicate author ORCID" in error for error in errors)


def test_check_final_upload_metadata_rejects_duplicate_author_email() -> None:
    """验证多个作者行使用同一邮箱时 final-upload 门禁会拒绝。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            '  - name: "Second Author"',
            '    affiliation: "Example Institute"',
            '    email: "AUTHOR@example.edu"',
            '    orcid: "0000-0003-1415-9269"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("duplicate author email" in error for error in errors)


def test_check_final_upload_metadata_rejects_malformed_author_and_artifact_fields() -> None:
    """验证 final-upload 门禁拒绝结构不完整的作者和 artifact 字段。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "not-an-email"',
            '  orcid: "bad-orcid"',
            "artifact_boundary:",
            '  artifact_release_url: ""',
            '  artifact_release_doi: ""',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("author row 1 email is missing" in error for error in errors)
    assert any("corresponding author email is invalid" in error for error in errors)
    assert any("corresponding author ORCID is invalid" in error for error in errors)
    assert any("artifact release URL or DOI is required" in error for error in errors)


def test_check_final_upload_metadata_rejects_mismatched_artifact_doi_url() -> None:
    """验证 artifact DOI 与 doi.org URL 不一致时会被拒绝。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example-a"',
            '  artifact_release_doi: "10.0000/example-b"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("artifact release URL DOI does not match artifact release DOI" in error for error in errors)


def test_check_final_upload_metadata_rejects_orcid_checksum_error() -> None:
    """验证 final-upload 门禁拒绝格式正确但校验位错误的 ORCID。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0000-0000-0000"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0000-0000-0000"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("author row 1 ORCID is invalid" in error for error in errors)
    assert any("corresponding author ORCID is invalid" in error for error in errors)


def test_check_final_upload_metadata_rejects_anonymous_review_for_dke() -> None:
    """验证 DKE final-upload 门禁拒绝匿名预审 review_mode。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'review_mode: "anonymous_review"',
            'target_journal: "Data & Knowledge Engineering"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("review mode must include final author identities for Data & Knowledge Engineering" in error for error in errors)


def test_check_final_upload_metadata_rejects_missing_review_mode_for_dke() -> None:
    """验证 DKE final-upload 门禁拒绝缺失的 review_mode。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Data & Knowledge Engineering"',
            "target_journal_template_bound: true",
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            '    orcid: "0000-0002-1825-0097"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
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

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("review mode must be recorded for Data & Knowledge Engineering" in error for error in errors)


def test_check_final_upload_metadata_rejects_missing_template_and_checklist_fields() -> None:
    """验证 final-upload 门禁拒绝缺失的模板绑定和清单布尔字段。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Journal of Scholarly Data"',
            "authors:",
            '  - name: "Example Author"',
            '    affiliation: "Example University"',
            '    email: "author@example.edu"',
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            "final_upload_checklist:",
            "  target_journal_selected: true",
            "  article_type_confirmed: true",
            "  review_mode_confirmed: true",
        ]
    )

    errors = module.check_final_upload_metadata(metadata_text)

    assert any("target journal template is not bound" in error for error in errors)
    assert any("target journal template checklist item is incomplete" in error for error in errors)
    assert any("author metadata checklist item is incomplete" in error for error in errors)
    assert any("first-screen claim lockdown checklist item is incomplete" in error for error in errors)
    assert any("artifact release checklist item is incomplete" in error for error in errors)


def test_check_final_upload_cover_letter_rejects_generic_cover_letter() -> None:
    """验证 final-upload 门禁拒绝通用匿名投稿信。"""

    module = _load_validate_manuscript_module()
    assert hasattr(module, "check_final_upload_cover_letter")
    metadata_text = 'target_journal: "Journal of Scholarly Data"\n'
    cover_letter_text = "\n".join(
        [
            "Dear Editor,",
            "The artifact release instructions are documented.",
            "Sincerely,",
            "Anonymous Authors",
        ]
    )

    errors = module.check_final_upload_cover_letter(cover_letter_text, metadata_text)

    assert any("generic editor greeting" in error for error in errors)
    assert any("anonymous author signature" in error for error in errors)


def test_check_final_upload_cover_letter_rejects_missing_artifact_link_value() -> None:
    """验证 final-upload 投稿信缺少元数据中的 artifact URL 或 DOI 时会被拒绝。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Data & Knowledge Engineering"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/iad-risk-artifact"',
            '  artifact_release_doi: "10.0000/iad-risk-artifact"',
        ]
    )
    cover_letter_text = "\n".join(
        [
            "Dear Data & Knowledge Engineering Editors,",
            "The manuscript includes an artifact release boundary for reproducibility.",
            "Sincerely,",
            "Example Author",
        ]
    )

    errors = module.check_final_upload_cover_letter(cover_letter_text, metadata_text)

    assert any("cover letter missing artifact release URL or DOI value" in error for error in errors)


def test_check_final_upload_cover_letter_rejects_article_type_mismatch() -> None:
    """验证 final-upload 投稿信文章类型与元数据不一致时会被拒绝。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Data & Knowledge Engineering"',
            'article_type: "research_article"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/iad-risk-artifact"',
            '  artifact_release_doi: "10.0000/iad-risk-artifact"',
        ]
    )
    cover_letter_text = "\n".join(
        [
            "Dear Data & Knowledge Engineering Editors,",
            "We submit the manuscript as a review article in Data & Knowledge Engineering.",
            "The artifact release is available at https://doi.org/10.0000/iad-risk-artifact.",
            "Sincerely,",
            "Example Author",
        ]
    )

    errors = module.check_final_upload_cover_letter(cover_letter_text, metadata_text)

    assert any("cover letter missing article type: research article" in error for error in errors)


def test_check_final_upload_cover_letter_rejects_missing_corresponding_author_signature() -> None:
    """验证 final-upload 投稿信缺少通讯作者姓名时会被拒绝。"""

    module = _load_validate_manuscript_module()
    metadata_text = "\n".join(
        [
            'target_journal: "Data & Knowledge Engineering"',
            'article_type: "research_article"',
            "corresponding_author:",
            '  name: "Corresponding Author"',
            '  affiliation: "Example University"',
            '  email: "corresponding@example.edu"',
            '  orcid: "0000-0002-1825-0097"',
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/iad-risk-artifact"',
            '  artifact_release_doi: "10.0000/iad-risk-artifact"',
        ]
    )
    cover_letter_text = "\n".join(
        [
            "Dear Data & Knowledge Engineering Editors,",
            "We submit the manuscript as a research article in Data & Knowledge Engineering.",
            "The artifact release is available at https://doi.org/10.0000/iad-risk-artifact.",
            "Sincerely,",
            "Different Author",
        ]
    )

    errors = module.check_final_upload_cover_letter(cover_letter_text, metadata_text)

    assert any(
        "cover letter missing corresponding author name: Corresponding Author" in error
        for error in errors
    )


def test_check_pdf_first_page_markers_accepts_expected_text() -> None:
    """验证 PDF 首页包含全部关键文本时可通过。"""

    module = _load_validate_manuscript_module()
    first_page_text = "\n".join(
        [
            "IAD-Risk: Risk-Aware Identity-Agenda",
            "Scholarly Work Deduplication",
            "Anonymous Authors",
            "Abstract",
            "Open-v2 evidence snapshot",
            "same-work F1=0.980 and zero observed HNFMR",
        ]
    )

    errors = module.check_pdf_first_page_markers(
        "main.pdf",
        first_page_text,
        ["IAD-Risk: Risk-Aware", "Scholarly Work Deduplication", "zero observed HNFMR"],
    )

    assert errors == []


def test_check_pdf_first_page_markers_accepts_wrapped_marker_text() -> None:
    """验证 PDF 抽取文本换行或断词时仍能识别关键文本。"""

    module = _load_validate_manuscript_module()
    first_page_text = "\n".join(
        [
            "IAD-Risk: Risk-Aware Identity-Agenda",
            "single-space baselines show HNFMR 0.790-0.999.",
            "IAD-Risk variants report same-",
            "work F1=0.980 and zero observed HNFMR.",
            "A later extraction may also contain same-work",
            "F1=0.980 on a new line.",
        ]
    )

    errors = module.check_pdf_first_page_markers(
        "main.pdf",
        first_page_text,
        ["same-work F1=0.980", "zero observed HNFMR"],
    )

    assert errors == []


def test_check_pdf_first_page_markers_rejects_missing_and_unresolved_text() -> None:
    """验证 PDF 首页缺少关键文本或含未解析标记时会被拒绝。"""

    module = _load_validate_manuscript_module()
    first_page_text = "IAD-Risk\nAbstract\nSee Table ?? for details."

    errors = module.check_pdf_first_page_markers(
        "main.pdf",
        first_page_text,
        ["Scholarly Work Deduplication", "zero observed HNFMR"],
    )

    assert any("Scholarly Work Deduplication" in error for error in errors)
    assert any("zero observed HNFMR" in error for error in errors)
    assert any("unresolved marker" in error and "??" in error for error in errors)


def test_check_pdf_freshness_accepts_pdf_newer_than_source(tmp_path) -> None:
    """验证 PDF 晚于源依赖文件时新鲜度检查通过。"""

    module = _load_validate_manuscript_module()
    source_path = tmp_path / "references.bib"
    pdf_path = tmp_path / "main.pdf"
    source_path.write_text("@article{a, title={A}}\n", encoding="utf-8")
    pdf_path.write_bytes(b"%PDF-1.5\n")
    source_mtime = 1_700_000_000
    pdf_mtime = source_mtime + 10

    os.utime(source_path, (source_mtime, source_mtime))
    os.utime(pdf_path, (pdf_mtime, pdf_mtime))

    errors = module.check_pdf_freshness(pdf_path, source_path)

    assert errors == []


def test_check_pdf_freshness_rejects_pdf_older_than_references(tmp_path) -> None:
    """验证 references.bib 晚于 PDF 时会要求重建。"""

    module = _load_validate_manuscript_module()
    source_path = tmp_path / "references.bib"
    pdf_path = tmp_path / "main.pdf"
    source_path.write_text("@article{a, title={A}}\n", encoding="utf-8")
    pdf_path.write_bytes(b"%PDF-1.5\n")
    pdf_mtime = 1_700_000_000
    source_mtime = pdf_mtime + 10

    os.utime(pdf_path, (pdf_mtime, pdf_mtime))
    os.utime(source_path, (source_mtime, source_mtime))

    errors = module.check_pdf_freshness(pdf_path, source_path)

    assert any("main.pdf is older than references.bib" in error for error in errors)


def test_check_pdf_full_text_markers_rejects_missing_marker(monkeypatch, tmp_path) -> None:
    """验证 PDF 全文缺少关键章节 marker 时会被拒绝。"""

    module = _load_validate_manuscript_module()
    pdf_path = tmp_path / "main.pdf"
    pdf_path.write_bytes(b"%PDF-1.5 fixture\n")

    def fake_extract_pdf_text(path):
        """返回测试用 PDF 文本。"""
        return "Abstract\nIntroduction\nConclusion\nReferences\n", []

    monkeypatch.setattr(module, "extract_pdf_text", fake_extract_pdf_text)

    errors = module.check_pdf_full_text_markers(pdf_path, ["Conclusion", "Data and Code Availability"])

    assert any("Data and Code Availability" in error for error in errors)


def test_check_pdf_full_text_markers_reports_extraction_errors(monkeypatch, tmp_path) -> None:
    """验证 PDF 全文抽取失败会被报告。"""

    module = _load_validate_manuscript_module()
    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(b"broken")

    def fake_extract_pdf_text(path):
        """返回测试用抽取错误。"""
        return "", ["cannot extract text"]

    monkeypatch.setattr(module, "extract_pdf_text", fake_extract_pdf_text)

    errors = module.check_pdf_full_text_markers(pdf_path, ["Conclusion"])

    assert any("full text is not readable" in error for error in errors)
