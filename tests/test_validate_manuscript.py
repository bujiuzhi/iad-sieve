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
