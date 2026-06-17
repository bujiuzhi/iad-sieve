"""测试稿件包验证脚本。"""

from __future__ import annotations

import importlib.util
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


def test_check_highlights_accepts_five_concise_bullets() -> None:
    """验证 5 条简洁投稿 highlights 可通过检查。"""

    module = _load_validate_manuscript_module()
    highlights_text = "\n".join(
        [
            "# Highlights",
            "",
            "- Identifies identity-agenda confusion as a false-merge risk.",
            "- Separates identity, agenda, and agenda-non-identity evidence.",
            "- Defines provenance-aware gold, proxy, and silver label layers.",
            "- Reports targeted hard-negative false-merge suppression.",
            "- Documents fixture rebuild commands and claim boundaries.",
        ]
    )

    errors = module.check_highlights(highlights_text)

    assert errors == []


def test_check_highlights_rejects_too_many_bullets() -> None:
    """验证 highlights 数量过多会被拒绝。"""

    module = _load_validate_manuscript_module()
    highlights_text = "\n".join(f"- Highlight {index}" for index in range(7))

    errors = module.check_highlights(highlights_text)

    assert any("expected 3 to 6" in error for error in errors)


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


def test_check_keywords_accepts_semicolon_separated_terms() -> None:
    """验证 4 到 8 个分号分隔关键词可通过检查。"""

    module = _load_validate_manuscript_module()
    keywords_text = (
        "# Keywords\n\n"
        "scholarly entity matching; work deduplication; identity-agenda disentanglement; "
        "false-merge risk; provenance-aware evaluation; scientific document representation"
    )

    errors = module.check_keywords(keywords_text)

    assert errors == []


def test_check_keywords_rejects_too_few_terms() -> None:
    """验证关键词数量不足会被拒绝。"""

    module = _load_validate_manuscript_module()
    keywords_text = "# Keywords\n\nwork deduplication; false-merge risk"

    errors = module.check_keywords(keywords_text)

    assert any("expected 4 to 8" in error for error in errors)


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


def test_check_result_claim_boundary_accepts_audited_result_table() -> None:
    """验证主结果表具备审计边界时可通过检查。"""

    module = _load_validate_manuscript_module()
    manuscript_text = "\n".join(
        [
            r"\subsection{Claim-Evidence Boundary for Result Interpretation}",
            r"\label{tab:claim-evidence-boundary-main}",
            r"\subsection{Result Audit Trail}",
            "Each row uses a prediction or score file, metric summary, and checksum or manifest.",
            "The evidence does not support a broad method-ranking claim.",
            r"\label{tab:openv2-results}",
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

    assert errors == []


def test_check_result_claim_boundary_rejects_result_table_without_audit_trail() -> None:
    """验证主结果表缺少审计边界会被拒绝。"""

    module = _load_validate_manuscript_module()
    manuscript_text = r"\label{tab:openv2-results}"
    supplementary_text = ""

    errors = module.check_result_claim_boundary(manuscript_text, supplementary_text)

    assert any("Result Audit Trail" in error for error in errors)
    assert any("Artifact Package Requirements" in error for error in errors)


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
            "Released artifacts should include manifests and checksums.",
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
            "target_journal_template_applied: false",
            "author_metadata_completed: false",
            "corresponding_author_completed: false",
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
            "corresponding_author:",
            '  name: "Example Author"',
            '  affiliation: "Example University"',
            '  email: "author@example.edu"',
            "final_upload_checklist:",
            "  target_journal_selected: true",
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

    assert errors == []
