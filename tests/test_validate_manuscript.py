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
