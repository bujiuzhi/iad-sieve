"""Tests for the provisional Elsevier draft builder."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "manuscript" / "scripts" / "build_elsevier_draft.py"


def _load_build_elsevier_module():
    """Load the Elsevier draft builder module for isolated tests.

    参数:
        无。

    返回:
        module: Imported build_elsevier_draft module.
    """
    spec = importlib.util.spec_from_file_location("build_elsevier_draft", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_elsevier_latex_uses_elsarticle_frontmatter() -> None:
    """验证生成的Elsevier预转换稿使用frontmatter、关键词和Elsevier参考样式。"""

    module = _load_build_elsevier_module()
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

    generated_text = module.build_elsevier_latex(manuscript_text, ["entity matching", "risk gating"])

    assert r"\documentclass[preprint,12pt]{elsarticle}" in generated_text
    assert r"\journal{Data \& Knowledge Engineering}" in generated_text
    assert r"\begin{frontmatter}" in generated_text
    assert r"\title{IAD-Risk: Test Title}" in generated_text
    assert "This abstract states the bounded evidence." in generated_text
    assert r"entity matching \sep risk gating" in generated_text
    assert r"\bibliographystyle{elsarticle-num}" in generated_text
    assert r"\bibliography{../references}" in generated_text


def test_build_elsevier_latex_rejects_missing_bibliography_boundary() -> None:
    """验证源稿缺少参考文献边界时会拒绝生成预转换稿。"""

    module = _load_build_elsevier_module()
    manuscript_text = r"""
\title{IAD-Risk}
\begin{abstract}
Abstract text.
\end{abstract}
\section{Introduction}
Body.
"""

    with pytest.raises(ValueError, match="bibliography style marker"):
        module.build_elsevier_latex(manuscript_text, ["entity matching"])


def test_load_keywords_rejects_empty_keyword_file(tmp_path: Path) -> None:
    """验证关键词文件为空时会触发Elsevier关键词数量约束。"""

    module = _load_build_elsevier_module()
    keywords_path = tmp_path / "keywords.md"
    keywords_path.write_text("# Keywords\n\n", encoding="utf-8")

    with pytest.raises(ValueError, match="expected 1 to 7 keywords"):
        module.load_keywords(keywords_path)
