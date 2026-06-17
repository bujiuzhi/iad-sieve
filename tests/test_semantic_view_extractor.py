"""测试规则式语义视图抽取。"""

from iad_sieve.views.semantic_view_extractor import extract_semantic_view


def test_extract_semantic_view_assigns_problem_method_object_and_result():
    record = {
        "document_id": "doc-1",
        "title": "Graph neural retrieval for scientific papers",
        "abstract": (
            "We address the challenge of scientific paper recommendation. "
            "We propose a graph neural framework for document retrieval. "
            "Experiments on a benchmark dataset show improved ranking quality."
        ),
    }

    view = extract_semantic_view(record)

    assert "challenge" in view["problem_view"]
    assert "framework" in view["method_view"]
    assert "benchmark dataset" in view["object_view"]
    assert "improved ranking quality" in view["result_view"]
    assert view["conf_problem"] > 0
    assert view["conf_method"] > 0
    assert "scientific" in view["keyphrases"]
