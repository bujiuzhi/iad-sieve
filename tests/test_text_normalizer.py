"""测试标题、摘要和 DOI 标准化行为。"""

from iad_sieve.preprocessing.identifier_normalizer import normalize_doi
from iad_sieve.preprocessing.text_normalizer import (
    build_title_fingerprint,
    normalize_abstract,
    normalize_title,
)


def test_normalize_title_preserves_method_tokens_and_cleans_latex():
    normalized = normalize_title("  A \\textbf{BGE-M3}--Based   RAG\\nMethod for $x^2$  ")

    assert normalized == "a bge-m3-based rag method for <math>"


def test_normalize_abstract_removes_prefix_and_collapses_space():
    normalized = normalize_abstract("Abstract:  We propose a method.\\n\\n Results show gains.")

    assert normalized == "we propose a method. results show gains."


def test_build_title_fingerprint_removes_stop_punctuation():
    fingerprint = build_title_fingerprint("A Method: for Scientific-Paper Deduplication!")

    assert fingerprint == "a_method_for_scientific_paper_deduplication"


def test_normalize_doi_removes_url_prefix_and_lowercases():
    assert normalize_doi("https://doi.org/10.48550/ARXIV.2301.00001 ") == "10.48550/arxiv.2301.00001"
