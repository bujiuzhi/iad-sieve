"""测试稿件包验证脚本。"""

from __future__ import annotations

import importlib.util
import json
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
            "The authors declare no competing interests.",
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
    assert any("no competing interests" in error for error in errors)


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
            "python manuscript/scripts/validate_submission_package.py --final-upload",
            "Primary `submission_metadata.yml` target",
            "Additional file or system target",
            "`submission`, `target_preparation`, `final_upload_checklist.target_journal_selected`",
            "`authors`, `author_contributions.roles`, `final_upload_checklist.author_metadata_completed`",
            "`corresponding_author`, `final_upload_checklist.corresponding_author_completed`",
            "`funding`, `statements`, `final_upload_checklist.funding_statement_text_ready`",
            "`author_contributions`, `final_upload_checklist.contribution_statement_complete`",
            "`permissions`, `final_upload_checklist.permissions_statement_complete`",
            "`repository_reference`, `artifact_boundary`, `statements.research_data_statement`",
            "`artifact_boundary`, `final_upload_checklist.artifact_release_prepared_or_linked`",
            "`final_upload_checklist.manuscript_pdf_rebuilt_after_template`",
            "Target journal",
            "Article type",
            "Review mode",
            "Author list",
            "Author order",
            "Corresponding author",
            "Funding statement",
            "Author contribution statement",
            "Permissions statement",
            "Competing interests",
            "Ethics statement",
            "Data and code availability statement",
            "Artifact release URL or DOI",
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

    errors = module.check_final_upload_information_request(request_text)

    assert any("Submission metadata mapping" in error for error in errors)
    assert any("Primary `submission_metadata.yml` target" in error for error in errors)
    assert any("statements.research_data_statement" in error for error in errors)


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
    request_text = request_text.replace("artifact_release_prepared_or_linked", "artifact_release_public")

    errors = module.check_final_upload_information_request(request_text)

    assert any("target_journal_template_applied" in error for error in errors)
    assert any("author_metadata_completed" in error for error in errors)
    assert any("corresponding_author_completed" in error for error in errors)
    assert any("manuscript_pdf_rebuilt_after_template" in error for error in errors)
    assert any("submission_system_files_verified" in error for error in errors)
    assert any("artifact_release_prepared_or_linked" in error for error in errors)


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
            r"\label{tab:data-code-availability-boundary}",
            "The repository includes Source code and CLI entry points.",
            "The repository includes Small public fixtures and schema contracts.",
            "The repository excludes Raw third-party source files.",
            "The repository excludes Full prediction files and model checkpoints.",
            "The external artifact release should contain Derived evaluation artifacts.",
            "The external artifact release should contain prediction files, threshold logs, manifests, checksums, and commit identifiers.",
            "The statement distinguishes L0/L1 code-level reproduction from L2/L3 result-level audit.",
            "The statement says raw third-party data remain governed by original provider licenses.",
            "The statement says full numerical reproduction requires public-source rebuilds or released artifacts.",
        ]
    )

    errors = module.check_data_code_availability_boundary(manuscript_text)

    assert errors == []


def test_check_data_code_availability_boundary_rejects_missing_artifact_boundary() -> None:
    """验证数据可用性声明缺少 artifact 边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\section*{Data and Code Availability} Data are available on request."

    errors = module.check_data_code_availability_boundary(manuscript_text)

    assert any("data-code-availability-boundary" in error for error in errors)
    assert any("Full prediction files and model checkpoints" in error for error in errors)


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
            "- Open-v2 scope-bounded evidence reports IAD-Risk HNFMR=0.000.",
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
            "- Open-v2 scope-bounded evidence reports IAD-Risk HNFMR=0.000.",
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
        "false-merge risk; provenance-aware evaluation; scientific document representation"
    )

    errors = module.check_keywords(keywords_text)

    assert errors == []


def test_check_keywords_rejects_too_many_terms() -> None:
    """验证关键词数量超过候选期刊上限会被拒绝。"""

    module = _load_validate_manuscript_module()
    keywords_text = "# Keywords\n\n" + "; ".join(f"keyword {index}" for index in range(8))

    errors = module.check_keywords(keywords_text)

    assert any("expected 1 to 7" in error for error in errors)


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
            r"\label{tab:claim-evidence-boundary-main}",
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
            "Each row uses a prediction or score file, metric summary, and checksum or manifest.",
            "Each row records per-row denominator counts.",
            "Each row records the per-row threshold source.",
            "Each row records the scope label used in the main table.",
            "The evidence does not support a broad method-ranking claim.",
            r"\label{tab:openv2-results}",
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
            "The result includes same-work F1=0.980 and HNFMR=0.000.",
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
            r"\label{tab:iad-bench-document-schema}",
            r"\texttt{document\_id}",
            r"\texttt{source\_dataset}",
            r"\texttt{title}",
            r"\texttt{abstract}",
            r"\texttt{authors}",
            r"\texttt{year}",
            r"\texttt{venue}",
            r"\texttt{doi}",
            r"\texttt{arxiv\_id}",
            r"\texttt{openalex\_work\_id}",
            r"\texttt{topics}",
            r"\texttt{references}",
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

    assert any("iad-bench-document-schema" in error for error in errors)
    assert any("openalex\\_work\\_id" in error for error in errors)
    assert any("raw third-party files" in error for error in errors)


def test_check_iad_bench_pair_schema_contract_accepts_complete_contract() -> None:
    """验证 IAD-Bench pair schema 字段契约完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Pair Schema Contract}",
            r"\label{tab:iad-bench-pair-schema}",
            r"\texttt{pair\_id}",
            r"\texttt{source\_document\_id}",
            r"\texttt{target\_document\_id}",
            r"\texttt{relation\_label}",
            r"\texttt{expected\_label}",
            r"\texttt{expected\_agenda\_label}",
            r"\texttt{label\_source}",
            r"\texttt{label\_strength}",
            r"\texttt{label\_provenance}",
            r"\texttt{split}",
            r"\texttt{hard\_negative\_level}",
            "Separates same-work identity from agenda relatedness.",
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

    assert any("iad-bench-pair-schema" in error for error in errors)
    assert any("label\\_provenance" in error for error in errors)
    assert any("hard\\_negative\\_level" in error for error in errors)


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


def test_check_method_feature_contract_accepts_complete_contract() -> None:
    """验证方法特征契约完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Feature and Head Specification}",
            r"\label{tab:feature-head-specification}",
            "Transformer distances and title similarity are used with author overlap.",
            "DOI/arXiv/OpenAlex identifier agreement is treated as identity evidence.",
            "The agenda head uses topic overlap and reference Jaccard similarity.",
            "The ANI risk head uses different-identifier conflicts.",
            "The relation heads use provenance-aware masking.",
            "Audit metadata is retained, but it is not a training feature.",
        ]
    )

    errors = module.check_method_feature_contract(manuscript_text)

    assert errors == []


def test_check_method_feature_contract_rejects_missing_feature_boundary() -> None:
    """验证方法特征契约缺少关键字段时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Feature and Head Specification}"

    errors = module.check_method_feature_contract(manuscript_text)

    assert any("feature-head-specification" in error for error in errors)
    assert any("different-identifier conflicts" in error for error in errors)


def test_check_risk_score_design_rationale_accepts_complete_rationale() -> None:
    """验证风险分数设计依据完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Risk Score Design Rationale}",
            r"\label{tab:risk-score-rationale}",
            r"$p_{\mathrm{risk}}$ is a conservative upper-envelope risk proxy.",
            "The score increases monotonically with agenda-non-identity evidence.",
            "It also increases when agenda evidence is high and identity evidence is weak.",
            "The max operator keeps either direct ANI evidence or indirect agenda-without-identity evidence sufficient to block automatic merging.",
            "The product term is not a calibrated probability unless validated against held-out artifacts.",
            "Threshold transfer must be rechecked under new source distributions.",
            "defer rather than merge",
        ]
    )

    errors = module.check_risk_score_design_rationale(manuscript_text)

    assert errors == []


def test_check_risk_score_design_rationale_rejects_missing_boundary() -> None:
    """验证风险分数设计缺少边界说明时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Risk Score Design Rationale}"

    errors = module.check_risk_score_design_rationale(manuscript_text)

    assert any("risk-score-rationale" in error for error in errors)
    assert any("max operator" in error for error in errors)
    assert any("not a calibrated probability" in error for error in errors)


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
            r"\label{tab:operational-net-benefit}",
            "IAD-Risk is appropriate when false merges are more costly than additional review.",
            "The additional cost comes from three relation heads and explicit threshold records.",
            "The deferral budget and manual-review capacity should be recorded before deployment.",
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

    assert any("operational-net-benefit" in error for error in errors)
    assert any("deferral budget" in error for error in errors)
    assert any("not a universal replacement" in error for error in errors)


def test_check_version_identifier_policy_accepts_complete_boundary() -> None:
    """验证版本和标识符合并边界完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Version and Identifier Boundary}",
            r"\label{tab:version-identifier-boundary}",
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


def test_check_design_alternative_boundaries_accepts_complete_boundaries() -> None:
    """验证设计替代项和拒绝边界完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Design Alternatives and Rejected Shortcuts}",
            r"\label{tab:design-alternatives}",
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

    errors = module.check_design_alternative_boundaries(manuscript_text)

    assert errors == []


def test_check_design_alternative_boundaries_rejects_missing_shortcut_boundaries() -> None:
    """验证方法部分缺少替代项边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Design Alternatives and Rejected Shortcuts}"

    errors = module.check_design_alternative_boundaries(manuscript_text)

    assert any("design-alternatives" in error for error in errors)
    assert any("one supervised pair classifier" in error for error in errors)
    assert any("released grid and checksums" in error for error in errors)


def test_check_operating_point_disclosure_accepts_complete_disclosure() -> None:
    """验证运行点披露完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Operating Point Disclosure}",
            r"\label{tab:operating-point-disclosure}",
            "The table reports fixed operating points, not post-hoc best test thresholds.",
            "Representation cosine baselines use a fixed score threshold.",
            "RoBERTa pair classifier uses a pair probability threshold.",
            "IAD-Risk transformer variants use a risk gate.",
            r"The default $\tau_w=\tau_a=\tau_r=0.5$ applies unless overridden.",
            "Score file, metric summary, and threshold entry are required.",
            "Prediction file, model JSON, thresholds, and checksums are required.",
        ]
    )

    errors = module.check_operating_point_disclosure(manuscript_text)

    assert errors == []


def test_check_operating_point_disclosure_rejects_missing_threshold_boundary() -> None:
    """验证缺少运行点边界会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Operating Point Disclosure}"

    errors = module.check_operating_point_disclosure(manuscript_text)

    assert any("operating-point-disclosure" in error for error in errors)
    assert any("post-hoc best test thresholds" in error for error in errors)


def test_check_selective_decision_coverage_boundary_accepts_complete_boundary() -> None:
    """验证选择性决策覆盖率边界完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_selective_decision_coverage_boundary", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\subsection{Selective Decision Coverage Boundary}",
            r"\label{tab:selective-decision-coverage}",
            "Automatic merge coverage",
            "Block rate",
            "defer rate",
            "Review load",
            "same prediction files",
            "The current manuscript does not claim throughput reduction.",
            "It does not claim all-pair automatic resolution.",
        ]
    )

    errors = checker(manuscript_text)

    assert errors == []


def test_check_selective_decision_coverage_boundary_rejects_missing_defer_boundary() -> None:
    """验证选择性决策缺少 defer 与吞吐边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_selective_decision_coverage_boundary", None)
    assert callable(checker)
    manuscript_text = r"\subsection{Selective Decision Coverage Boundary}"

    errors = checker(manuscript_text)

    assert any("defer rate" in error for error in errors)
    assert any("throughput reduction" in error for error in errors)
    assert any("all-pair automatic resolution" in error for error in errors)


def test_check_pair_cluster_evidence_boundary_accepts_complete_boundary() -> None:
    """验证 pair-level 与 cluster-level 证据边界完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_pair_cluster_evidence_boundary", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\subsection{Pair-to-Cluster Evidence Boundary}",
            r"\label{tab:pair-cluster-evidence-boundary}",
            "pair-level metrics do not by themselves prove cluster-level deduplication quality.",
            "transitive merge propagation",
            "cannot-link violations",
            "cluster assignments",
            "cluster_metric_summary",
            "cannot_link_audit",
            "cluster contamination rate",
            "does not claim cluster-level contamination is eliminated",
        ]
    )

    errors = checker(manuscript_text)

    assert errors == []


def test_check_pair_cluster_evidence_boundary_rejects_missing_cluster_audit() -> None:
    """验证缺少 cluster audit 边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_pair_cluster_evidence_boundary", None)
    assert callable(checker)
    manuscript_text = r"\subsection{Pair-to-Cluster Evidence Boundary} pair-level metrics are reported."

    errors = checker(manuscript_text)

    assert any("pair-cluster-evidence-boundary" in error for error in errors)
    assert any("cluster assignments" in error for error in errors)
    assert any("cannot_link_audit" in error for error in errors)


def test_check_validity_threats_rejects_limitations_without_cluster_boundary() -> None:
    """验证 Limitations 段落必须声明 pair-level 到 cluster-level 的证据限制。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\section{Limitations}",
            "This study has four limitations.",
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

    errors = module.check_validity_threats(manuscript_text)

    assert any("Limitations" in error for error in errors)
    assert any("pair-level metrics" in error for error in errors)
    assert any("cluster-level deployment quality" in error for error in errors)


def test_check_decision_metric_mapping_accepts_complete_mapping() -> None:
    """验证选择性决策到评价指标的映射完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_decision_metric_mapping", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\subsection{Decision-to-Metric Mapping}",
            r"\label{tab:decision-metric-mapping}",
            "automatic merge is the positive decision",
            "block and defer are non-merge decisions",
            "Deferred same-work pairs reduce recall",
            "FMR and HNFMR count only automatic merges among non-identity rows",
            "coverage and defer rate must be reported separately",
        ]
    )

    errors = checker(manuscript_text)

    assert errors == []


def test_check_decision_metric_mapping_rejects_missing_defer_mapping() -> None:
    """验证缺少 defer 到指标映射时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_decision_metric_mapping", None)
    assert callable(checker)
    manuscript_text = r"\subsection{Decision-to-Metric Mapping}"

    errors = checker(manuscript_text)

    assert any("block and defer are non-merge decisions" in error for error in errors)
    assert any("Deferred same-work pairs reduce recall" in error for error in errors)
    assert any("FMR and HNFMR count only automatic merges" in error for error in errors)


def test_check_metric_formula_boundary_accepts_complete_formula_table() -> None:
    """验证评价指标公式和分母边界完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_metric_formula_boundary", None)
    assert callable(checker)
    manuscript_text = "\n".join(
        [
            r"\subsection{Metric Formula Boundary}",
            r"\label{tab:metric-formula-boundary}",
            "TP",
            "FP",
            "FN",
            r"$2TP/(2TP+FP+FN)$",
            "FMR denominator is all non-identity rows in the evaluated scope.",
            "HNFMR denominator is the agenda-level hard-negative subset.",
            "Rows excluded by missing labels are not silently added to denominators.",
        ]
    )

    errors = checker(manuscript_text)

    assert errors == []


def test_check_metric_formula_boundary_rejects_missing_denominators() -> None:
    """验证缺少指标分母说明时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_metric_formula_boundary", None)
    assert callable(checker)
    manuscript_text = r"\subsection{Metric Formula Boundary}"

    errors = checker(manuscript_text)

    assert any("FMR denominator" in error for error in errors)
    assert any("HNFMR denominator" in error for error in errors)
    assert any("missing labels" in error for error in errors)


def test_check_threshold_sensitivity_status_accepts_bounded_claim() -> None:
    """验证阈值敏感性边界完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Threshold Sensitivity Evidence Status}",
            r"\label{tab:threshold-sensitivity-status}",
            "Threshold stability is treated as an audit requirement.",
            "It is not as an unsupported robustness claim.",
            "A stronger claim requires the same prediction files.",
            "It also requires predefined threshold ranges.",
            "The threshold grid is not reported as primary evidence.",
            "The package needs Per-threshold F1, FMR, HNFMR.",
            "The manuscript supports fixed-threshold control, not threshold-stable ranking across all operating points.",
        ]
    )

    errors = module.check_threshold_sensitivity_status(manuscript_text)

    assert errors == []


def test_check_threshold_sensitivity_status_rejects_unbounded_claim() -> None:
    """验证缺少阈值敏感性 artifact 边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Threshold Sensitivity Evidence Status}"

    errors = module.check_threshold_sensitivity_status(manuscript_text)

    assert any("same prediction files" in error for error in errors)
    assert any("not threshold-stable ranking" in error for error in errors)


def test_check_statistical_interpretation_boundary_accepts_bounded_point_estimates() -> None:
    """验证统计解释边界完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Statistical Interpretation Boundary}",
            r"\label{tab:statistical-interpretation-boundary}",
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
            r"\label{tab:baseline-inclusion-rationale}",
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
    assert any("not a claim that omitted baselines were outperformed" in error for error in errors)


def test_check_baseline_fairness_controls_accepts_complete_controls() -> None:
    """验证 baseline 公平比较控制完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Baseline Fairness Controls}",
            r"\label{tab:baseline-fairness-controls}",
            "All baselines consume the same IAD-Bench pair records.",
            "Each row uses the same train/dev/test split field when training is required.",
            "Threshold-sensitive rows use validation-selected operating points.",
            "All systems report same-work F1, FMR, and HNFMR from the same metric implementation.",
            "Label source, provenance, and split identifiers are audit fields, not predictive features.",
            "A stricter ranking requires same-scope released prediction files.",
            "The table should not be read as a single leaderboard.",
        ]
    )

    errors = module.check_baseline_fairness_controls(manuscript_text)

    assert errors == []


def test_check_baseline_fairness_controls_rejects_missing_protocol_markers() -> None:
    """验证 baseline 公平比较缺少关键协议时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Baseline Fairness Controls}"

    errors = module.check_baseline_fairness_controls(manuscript_text)

    assert any("baseline-fairness-controls" in error for error in errors)
    assert any("same IAD-Bench pair records" in error for error in errors)
    assert any("not predictive features" in error for error in errors)


def test_check_result_interpretation_guardrails_accepts_complete_boundaries() -> None:
    """验证主结果表判读规则完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Result Interpretation Guardrails}",
            r"\label{tab:result-interpretation-guardrails}",
            "The table separates Directly supported reading.",
            "It also separates Mechanism-supported reading.",
            "It explicitly lists Unsupported reading.",
            "The main result table includes Scope type.",
            "It distinguishes full available Open-v2 scope.",
            "It distinguishes held-out Open-v2 test scope.",
            "Scope labels prevent leaderboard reading.",
            "The representation rows test false-merge exposure.",
            "The RoBERTa row is a strong supervised comparator.",
            "The IAD-Risk rows test split-held-out risk gating.",
            "The result is not a claim of broad method superiority.",
            "The table is not a same-scope leaderboard.",
            "The table is not evidence of threshold stability or zero risk.",
        ]
    )

    errors = module.check_result_interpretation_guardrails(manuscript_text)

    assert errors == []


def test_check_result_interpretation_guardrails_rejects_missing_unsupported_reading() -> None:
    """验证主结果表缺少禁止读法边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\subsection{Result Interpretation Guardrails}"

    errors = module.check_result_interpretation_guardrails(manuscript_text)

    assert any("Unsupported reading" in error for error in errors)
    assert any("not a same-scope leaderboard" in error for error in errors)


def test_check_result_interpretation_guardrails_rejects_missing_scope_type_labels() -> None:
    """验证主结果表缺少 scope 类型标签时会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Result Interpretation Guardrails}",
            r"\label{tab:result-interpretation-guardrails}",
            "Directly supported reading",
            "Mechanism-supported reading",
            "Unsupported reading",
            "The representation rows test false-merge exposure.",
            "The RoBERTa row is a strong supervised comparator.",
            "The IAD-Risk rows test split-held-out risk gating.",
            "The result is not a claim of broad method superiority.",
            "The table is not a same-scope leaderboard.",
            "The table is not evidence of threshold stability or zero risk.",
        ]
    )

    errors = module.check_result_interpretation_guardrails(manuscript_text)

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
\caption{Open-v2 evidence snapshot.}
\label{tab:openv2-results}
\centering
\begin{tabular}{llllll}
\toprule
System & Scope type & Pairs & F1 $\uparrow$ & FMR $\downarrow$ & HNFMR $\downarrow$ \\
\midrule
SciNCL cosine & Full Open-v2 & 10415 & 0.054 & 0.785 & 0.790 \\
SPECTER2 adapter cosine & Full Open-v2 & 10415 & 0.044 & 0.999 & 0.999 \\
RoBERTa pair classifier & Full Open-v2 & 10415 & 0.825 & 0.001 & 0.0001 \\
IAD-Risk (SciNCL) & Held-out test & 1042 & 0.980 & 0.001 & 0.000 \\
IAD-Risk (SPECTER2) & Held-out test & 1042 & 0.980 & 0.001 & 0.000 \\
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


def test_check_openv2_result_table_scope_labels_rejects_wrong_iad_scope() -> None:
    """验证 IAD-Risk 结果行误写成 full scope 时会被拒绝。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_openv2_result_table_scope_labels", None)
    assert callable(checker)
    manuscript_text = r"""
\begin{table}[H]
\caption{Open-v2 evidence snapshot.}
\label{tab:openv2-results}
\centering
\begin{tabular}{llllll}
\toprule
System & Scope type & Pairs & F1 $\uparrow$ & FMR $\downarrow$ & HNFMR $\downarrow$ \\
\midrule
SciNCL cosine & Full Open-v2 & 10415 & 0.054 & 0.785 & 0.790 \\
SPECTER2 adapter cosine & Full Open-v2 & 10415 & 0.044 & 0.999 & 0.999 \\
RoBERTa pair classifier & Full Open-v2 & 10415 & 0.825 & 0.001 & 0.0001 \\
IAD-Risk (SciNCL) & Full Open-v2 & 1042 & 0.980 & 0.001 & 0.000 \\
IAD-Risk (SPECTER2) & Held-out test & 1042 & 0.980 & 0.001 & 0.000 \\
\bottomrule
\end{tabular}
\end{table}
"""

    errors = checker(manuscript_text)

    assert any("IAD-Risk (SciNCL)" in error and "Held-out test" in error for error in errors)


def test_check_manual_validation_boundary_accepts_complete_boundary() -> None:
    """验证主文人工验证边界完整时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Manual Validation Boundary}",
            r"\label{tab:manual-validation-boundary}",
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
    """验证主稿包含正式论文风格的 claim interpretation boundary 时可通过检查。"""

    module = _load_validate_manuscript_module()
    checker = getattr(module, "check_claim_interpretation_boundary", None)
    assert callable(checker)
    manuscript_text = "\n".join(
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

    errors = checker(manuscript_text)

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
    assert any("Boundary before stronger wording" in error for error in errors)
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
            "Manual validation is a future evidence layer.",
            "The protocol samples 500--1,000 pairs.",
            "It uses two independent reviewers.",
            "Reviewers are blind to model scores.",
            "The release includes an adjudication log.",
            "The artifact reports inter-annotator agreement.",
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
            "Official guide rechecked: 2026-06-18",
            "Official source snapshot date: 2026-06-18",
            "DKE guide verified: 2026-06-18",
            "Information Systems guide verified: 2026-06-18",
            "Scientometrics guide verified: 2026-06-18",
            "Status: provisional preparation only.",
            "The current anonymous author placeholder is compatible with single anonymized review preparation.",
            "The current abstract is checked against a 250-word limit.",
            "keywords.md currently contains 1--7 semicolon-separated keywords.",
            "highlights.md currently contains 3--5 highlights and is checked against the 85-character limit.",
            "Convert to Elsevier `elsarticle` only after confirmation.",
            "Add the real artifact URL or DOI before final upload.",
            "Information Systems data statement is required.",
            "CRediT author contribution statement.",
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
            "Official guide rechecked: 2026-06-18",
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

    assert any("Official source snapshot date: 2026-06-18" in error for error in errors)
    assert any("Information Systems data statement is required" in error for error in errors)
    assert any("CRediT author contribution statement" in error for error in errors)


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
            "Official guide rechecked: 2026-06-18",
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
                        "per-row denominator counts, per-row threshold source, and scope label used in the main table."
                    ),
                },
                {"artifact_id": "iad_risk_predictions"},
                {"artifact_id": "representation_baseline_scores"},
                {"artifact_id": "supervised_baseline_predictions"},
                {"artifact_id": "threshold_selection_logs"},
                {"artifact_id": "iad_bench_split_summary"},
                {"artifact_id": "bootstrap_intervals"},
                {"artifact_id": "ablation_suite"},
                {"artifact_id": "manual_validation_slice"},
                {"artifact_id": "threshold_sensitivity_grid"},
                {"artifact_id": "cluster_metric_summary"},
                {"artifact_id": "cannot_link_audit"},
            ],
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
                {"artifact_id": "ablation_suite"},
                {"artifact_id": "manual_validation_slice"},
                {"artifact_id": "threshold_sensitivity_grid"},
            ],
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
                {"artifact_id": "ablation_suite"},
                {"artifact_id": "manual_validation_slice"},
                {"artifact_id": "cluster_metric_summary"},
                {"artifact_id": "cannot_link_audit"},
            ],
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
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release",
            "sha256sum -c checksums.sha256",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
            "python manuscript/scripts/validate_manuscript.py --strict-latex",
            "python manuscript/scripts/verify_fixture_rebuild.py",
            "python scripts/check_public_release.py",
            "## Required Artifact IDs",
            "open_v2_main_results",
            "per-row denominator counts",
            "per-row threshold source",
            "scope label used in the main table",
            "iad_risk_predictions",
            "representation_baseline_scores",
            "supervised_baseline_predictions",
            "threshold_selection_logs",
            "iad_bench_split_summary",
            "cluster_metric_summary",
            "cannot_link_audit",
            "## Conditional Claim Artifacts",
            "confidence_intervals_claimed requires bootstrap_intervals.",
            "component_causality_claimed requires ablation_suite.",
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
    ]:
        readme_text = readme_text.replace(marker, "")

    errors = module.check_artifact_release_readme_template(readme_text)

    assert any("per-row denominator counts" in error for error in errors)
    assert any("per-row threshold source" in error for error in errors)
    assert any("scope label used in the main table" in error for error in errors)


def test_check_artifact_release_readme_template_rejects_missing_release_boundaries() -> None:
    """验证 artifact release README 模板缺少复现边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    readme_text = "# IAD-Risk Artifact Release README Template\nREADME.md\nmanifest.json\n"

    errors = module.check_artifact_release_readme_template(readme_text)

    assert any("raw third-party data" in error for error in errors)
    assert any("validate_artifact_release.py" in error for error in errors)
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
    assert any("final_upload_information_request.md" in error for error in errors)
    assert any("Author list" in error for error in errors)
    assert any("Corresponding author" in error for error in errors)
    assert any("Funding statement" in error for error in errors)
    assert any("Artifact release URL or DOI" in error for error in errors)


def test_check_related_work_positioning_rejects_missing_novelty_boundaries() -> None:
    """验证 Related Work 必须说明最接近工作的创新边界。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\label{tab:closest-work-positioning}",
            "Positioning against the closest lines of work",
            "End-to-end entity resolution systems",
            "Neural entity matching",
            "Scientific document representations",
            "Open scholarly metadata benchmarks",
            "false-merge risk gates",
            "gold, proxy, and silver strata",
        ]
    )

    errors = module.check_related_work_positioning(manuscript_text)

    assert any("not a replacement for end-to-end entity resolution workflows" in error for error in errors)
    assert any("not a leaderboard over all neural matching methods" in error for error in errors)
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
            "def build_copy_plan(",
            "def copy_planned_artifacts(",
            "def write_population_log(",
            "def finalize_release(",
            "--source-dir",
            "--mapping",
            "--skip-finalize",
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
            "Artifact release manifest",
            "## Artifact Release Package Checks",
            "python manuscript/scripts/build_artifact_release_skeleton.py --output-dir /path/to/release --repository-commit",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
            "open_v2_main_results",
            "per-row denominator counts",
            "per-row threshold source",
            "scope label used in the main table",
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
            "## Source Archive Assembly Checks",
            "The source archive contains editable LaTeX sources.",
            "The source archive includes references.bib and submission text files.",
            "The source archive includes manifest and checksum files.",
            "The source archive excludes build caches and generated zip files.",
            "The source archive is rebuilt after template conversion.",
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
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
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
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
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
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
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


def test_check_submission_system_checklist_rejects_missing_artifact_row_schema_checks() -> None:
    """验证投稿系统清单必须覆盖主结果表行级 schema 检查。"""

    module = _load_validate_manuscript_module()
    checklist_text = Path("manuscript/submission_system_checklist.md").read_text(encoding="utf-8")
    for marker in [
        "open_v2_main_results",
        "per-row denominator counts",
        "per-row threshold source",
        "scope label used in the main table",
    ]:
        checklist_text = checklist_text.replace(marker, "")

    errors = module.check_submission_system_checklist(checklist_text)

    assert any("open_v2_main_results" in error for error in errors)
    assert any("per-row denominator counts" in error for error in errors)
    assert any("per-row threshold source" in error for error in errors)
    assert any("scope label used in the main table" in error for error in errors)


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
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
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
            "Completed audit cycles: 9.",
            "Highest current reviewer-facing risks: final-upload metadata, external artifact release, and stronger evidence gates.",
            "Current stopping rule: do not claim Q2/B completion or final-upload readiness until `python manuscript/scripts/validate_submission_package.py --final-upload` passes and a real artifact URL or DOI is recorded.",
            "Non-code external inputs still required: author metadata, target-journal confirmation, funding statement, author contribution statement, permissions statement, live submission-system fields, and artifact release URL or DOI.",
            "Next revision trigger: repeat the editorial desk check after template conversion, cover-letter customization, or artifact-link insertion.",
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
            "validate_artifact_release.py",
            "## Minimum Gate Before Final Upload",
            "The Q2/B acceptance gate is either fully ready.",
            "python manuscript/scripts/validate_submission_package.py --final-upload",
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
        "Completed audit cycles: 9",
        "Highest current reviewer-facing risks",
        "Current stopping rule",
        "Non-code external inputs still required",
        "Next revision trigger",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Audit Iteration Summary" in error for error in errors)
    assert any("Completed audit cycles: 9" in error for error in errors)
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
            "python manuscript/scripts/validate_submission_package.py --final-upload",
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
        "validate_artifact_release.py",
    ]:
        audit_text = audit_text.replace(marker, "")

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Artifact Row-Level Result Audit" in error for error in errors)
    assert any("open_v2_main_results" in error for error in errors)
    assert any("per-row denominator counts" in error for error in errors)
    assert any("per-row threshold source" in error for error in errors)
    assert any("scope label used in the main table" in error for error in errors)


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
            "python manuscript/scripts/validate_submission_package.py --final-upload",
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
            "python manuscript/scripts/validate_submission_package.py --final-upload",
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
            "python manuscript/scripts/validate_submission_package.py --final-upload",
        ]
    )

    errors = module.check_reviewer_readiness_audit(audit_text)

    assert any("Journal Fit and Novelty Desk Check" in error for error in errors)
    assert any("desk-rejection risk" in error for error in errors)
    assert any("target-journal scope fit" in error for error in errors)


def test_check_cover_letter_accepts_required_submission_statements() -> None:
    """验证 cover letter 含正式投稿声明时可通过检查。"""

    module = _load_validate_manuscript_module()
    cover_letter_text = "\n".join(
        [
            "Dear Editor,",
            "We submit IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication.",
            "The manuscript is not under consideration elsewhere.",
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

    assert errors == []


def test_check_cover_letter_rejects_missing_submission_statements() -> None:
    """验证 cover letter 缺少正式投稿声明时会被拒绝。"""

    module = _load_validate_manuscript_module()
    cover_letter_text = "Dear Editor,\nWe submit the manuscript."

    errors = module.check_cover_letter(cover_letter_text)

    assert any("not under consideration elsewhere" in error for error in errors)
    assert any("no competing interests" in error for error in errors)


def test_check_cover_letter_rejects_missing_artifact_release_boundary() -> None:
    """验证 cover letter 缺少完整实验输出和 artifact release 边界时会被拒绝。"""

    module = _load_validate_manuscript_module()
    cover_letter_text = "\n".join(
        [
            "Dear Editor,",
            "We submit IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication.",
            "The manuscript is not under consideration elsewhere.",
            "All listed authors have approved the submitted version.",
            "The authors declare no competing interests.",
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
            "The manuscript is not under consideration elsewhere.",
            "All listed authors have approved the submitted version.",
            "The authors declare no competing interests.",
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
            "The manuscript is not under consideration elsewhere.",
            "All listed authors have approved the submitted version.",
            "The authors declare no competing interests.",
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
            "- Open-v2 scope-bounded evidence reports IAD-Risk HNFMR=0.000.",
            "- Cluster-level claims require artifact-backed audits.",
        ]
    )
    cover_letter_text = "\n".join(
        [
            "The manuscript reports an Open-v2 evidence snapshot.",
            "Single-space scientific representation baselines show HNFMR 0.790--0.999 on the full pair scope.",
            "IAD-Risk reports same-work F1=0.980 and HNFMR=0.000 on the held-out test scope.",
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
            "Single-space scientific representation baselines show HNFMR 0.790--0.999 on the full pair scope.",
            "IAD-Risk reports same-work F1=0.980 and HNFMR=0.000 on the held-out test scope.",
        ]
    )

    errors = module.check_submission_material_quantitative_summary(highlights_text, cover_letter_text)

    assert any("highlights missing scoped quantitative evidence marker" in error for error in errors)
    assert any("Open-v2 scope-bounded evidence" in error for error in errors)


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
            "The results include HNFMR 0.790--0.999 and HNFMR=0.000.",
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
            "The result includes HNFMR 0.790--0.999 and HNFMR=0.000.",
            "The manuscript does not claim broad method superiority.",
            "raw third-party data and full experimental outputs are not redistributed in Git.",
        ]
    )
    highlights_text = "\n".join(
        [
            "- Identity-agenda confusion causes risky scholarly work merges.",
            "- IAD-Risk separates identity, agenda, and ANI evidence.",
            "- IAD-Bench keeps gold, proxy, and silver labels separate.",
            "- Open-v2 scope-bounded evidence reports IAD-Risk HNFMR=0.000.",
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
            "The results include HNFMR 0.790--0.999 and HNFMR=0.000.",
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
            "The result includes HNFMR 0.790--0.999 and HNFMR=0.000.",
            "The manuscript does not claim broad method superiority.",
            "raw third-party data and full experimental outputs are not redistributed in Git.",
        ]
    )
    highlights_text = "\n".join(
        [
            "- Identity-agenda confusion causes risky scholarly work merges.",
            "- IAD-Risk separates identity, agenda, and ANI evidence.",
            "- IAD-Bench keeps gold, proxy, and silver labels separate.",
            "- Open-v2 scope-bounded evidence reports IAD-Risk HNFMR=0.000.",
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
            "The results include HNFMR 0.790--0.999 and HNFMR=0.000.",
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
            "The result includes HNFMR 0.790--0.999 and HNFMR=0.000.",
            "The manuscript does not claim broad method superiority.",
            "raw third-party data and full experimental outputs are not redistributed in Git.",
        ]
    )
    highlights_text = "\n".join(
        [
            "- Identity-agenda confusion causes risky scholarly work merges.",
            "- IAD-Risk separates identity, agenda, and ANI evidence.",
            "- IAD-Bench keeps gold, proxy, and silver labels separate.",
            "- Open-v2 scope-bounded evidence reports IAD-Risk HNFMR=0.000.",
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
        "main manuscript": "IAD-Risk uses risk-aware merge gating -- not a leaderboard claim.",
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
    assert any("artifact release checklist item is incomplete" in error for error in errors)


def test_check_final_upload_metadata_accepts_filled_metadata() -> None:
    """验证 final-upload 门禁接受已填写目标期刊和作者信息的元数据。"""

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
            "  corresponding_author_completed: true",
            "  funding_statement_text_ready: true",
            "  contribution_statement_complete: true",
            "  permissions_statement_complete: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
            "  artifact_release_prepared_or_linked: true",
        ]
    )

    errors = module.check_final_upload_metadata(metadata_text)

    assert errors == []


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
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
            "final_upload_checklist:",
            "  target_journal_selected: true",
            "  article_type_confirmed: true",
            "  review_mode_confirmed: true",
            "  target_journal_template_applied: true",
            "  author_metadata_completed: true",
            "  corresponding_author_completed: true",
            "  funding_statement_text_ready: true",
            "  contribution_statement_complete: true",
            "  permissions_statement_complete: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  funding_statement_text_ready: true",
            "  contribution_statement_complete: true",
            "  permissions_statement_complete: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  funding_statement_text_ready: true",
            "  contribution_statement_complete: true",
            "  permissions_statement_complete: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
            "final_upload_checklist:",
            "  target_journal_selected: true",
            "  article_type_confirmed: true",
            "  review_mode_confirmed: true",
            "  target_journal_template_applied: true",
            "  author_metadata_completed: true",
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
            "final_upload_checklist:",
            "  target_journal_selected: true",
            "  article_type_confirmed: true",
            "  review_mode_confirmed: true",
            "  target_journal_template_applied: true",
            "  author_metadata_completed: true",
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  funding_statement_text_ready: true",
            "  contribution_statement_complete: true",
            "  permissions_statement_complete: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "artifact_boundary:",
            '  artifact_release_url: "https://doi.org/10.0000/example"',
            '  artifact_release_doi: "10.0000/example"',
            "final_upload_checklist:",
            "  target_journal_selected: true",
            "  article_type_confirmed: true",
            "  review_mode_confirmed: true",
            "  target_journal_template_applied: true",
            "  author_metadata_completed: true",
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  funding_statement_text_ready: true",
            "  contribution_statement_complete: true",
            "  permissions_statement_complete: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  funding_statement_text_ready: true",
            "  contribution_statement_complete: true",
            "  permissions_statement_complete: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "  corresponding_author_completed: true",
            "  manuscript_pdf_rebuilt_after_template: true",
            "  supplementary_pdf_rebuilt_after_template: true",
            "  submission_system_files_verified: true",
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
            "same-work F1=0.980 and HNFMR=0.000",
        ]
    )

    errors = module.check_pdf_first_page_markers(
        "main.pdf",
        first_page_text,
        ["IAD-Risk: Risk-Aware", "Scholarly Work Deduplication", "HNFMR=0.000"],
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
            "work F1=0.980 and HNFMR=0.000.",
            "A later extraction may also contain same-work",
            "F1=0.980 on a new line.",
        ]
    )

    errors = module.check_pdf_first_page_markers(
        "main.pdf",
        first_page_text,
        ["same-work F1=0.980", "HNFMR=0.000"],
    )

    assert errors == []


def test_check_pdf_first_page_markers_rejects_missing_and_unresolved_text() -> None:
    """验证 PDF 首页缺少关键文本或含未解析标记时会被拒绝。"""

    module = _load_validate_manuscript_module()
    first_page_text = "IAD-Risk\nAbstract\nSee Table ?? for details."

    errors = module.check_pdf_first_page_markers(
        "main.pdf",
        first_page_text,
        ["Scholarly Work Deduplication", "HNFMR=0.000"],
    )

    assert any("Scholarly Work Deduplication" in error for error in errors)
    assert any("HNFMR=0.000" in error for error in errors)
    assert any("unresolved marker" in error and "??" in error for error in errors)


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
