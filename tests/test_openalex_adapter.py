"""测试 OpenAlex/OpenCitations 弱监督数据适配。"""

from __future__ import annotations

from argparse import Namespace

from iad_sieve.cli import command_prepare_openalex_weak_labels
from iad_sieve.evaluation.eval_set_builder import score_evaluation_pairs, summarize_scored_eval_pairs
from iad_sieve.evaluation.openalex_adapter import (
    prepare_openalex_weak_label_evaluation_set,
    read_openalex_works,
)
from iad_sieve.utils.io_utils import read_records


def _write_fixture(path, content: str) -> None:
    """写入测试文件。

    参数:
        path: 输出路径。
        content: 文件内容。

    返回:
        无。
    """
    path.write_text(content.strip() + "\n", encoding="utf-8")


def test_read_openalex_works_converts_work_records(tmp_path) -> None:
    """验证 OpenAlex Works 转换为标准文献记录。"""
    works_path = tmp_path / "works.jsonl"
    _write_fixture(
        works_path,
        """
{"id":"https://openalex.org/W1","doi":"https://doi.org/10.1000/a","display_name":"Neural Retrieval","abstract_inverted_index":{"A":[0],"retrieval":[1],"paper":[2]},"publication_year":2024,"authorships":[{"author":{"display_name":"Alice Smith"}}],"primary_topic":{"id":"https://openalex.org/T1","display_name":"Information Retrieval"},"referenced_works":["https://openalex.org/W3"]}
""",
    )

    records = read_openalex_works(works_path, "openalex_sample")

    assert len(records) == 1
    assert records[0]["document_id"] == "openalex:openalex_sample:W1"
    assert records[0]["doi"] == "10.1000/a"
    assert records[0]["title_normalized"] == "neural retrieval"
    assert records[0]["abstract_normalized"] == "a retrieval paper"
    assert records[0]["authors"] == ["Alice Smith"]
    assert records[0]["primary_category"] == "openalex:T1"


def test_prepare_openalex_weak_label_evaluation_set_builds_agenda_non_identity_pairs(tmp_path) -> None:
    """验证同 topic 且引用相邻的不同 DOI 文献被构造为 hard negative。"""
    works_path = tmp_path / "works.jsonl"
    _write_fixture(
        works_path,
        """
{"id":"https://openalex.org/W1","doi":"https://doi.org/10.1000/a","title":"Neural Retrieval","publication_year":2024,"authorships":[{"author":{"display_name":"Alice"}}],"primary_topic":{"id":"https://openalex.org/T1","display_name":"Information Retrieval"},"referenced_works":["https://openalex.org/W3"]}
{"id":"https://openalex.org/W2","doi":"https://doi.org/10.1000/b","title":"Dense Retrieval Models","publication_year":2024,"authorships":[{"author":{"display_name":"Bob"}}],"primary_topic":{"id":"https://openalex.org/T1","display_name":"Information Retrieval"},"referenced_works":["https://openalex.org/W3"]}
{"id":"https://openalex.org/W4","doi":"https://doi.org/10.1000/d","title":"Graph Databases","publication_year":2020,"authorships":[{"author":{"display_name":"Carol"}}],"primary_topic":{"id":"https://openalex.org/T2","display_name":"Databases"}}
""",
    )

    documents, pairs, summary = prepare_openalex_weak_label_evaluation_set(
        works_path,
        dataset_name="openalex_sample",
        min_shared_references=1,
        max_pairs_per_topic=5,
    )

    assert len(documents) == 2
    assert len(pairs) == 1
    assert pairs[0]["expected_label"] == 0
    assert pairs[0]["expected_agenda_label"] == 1
    assert pairs[0]["label_type"] == "openalex_agenda_non_identity_weak"
    assert summary["agenda_non_identity_pair_count"] == 1
    assert summary["label_type"] == "same_agenda_weak_as_non_duplicate"


def test_prepare_openalex_weak_label_evaluation_set_uses_opencitations_csv(tmp_path) -> None:
    """验证 OpenCitations DOI-to-DOI CSV 可补充共享引用证据。"""
    works_path = tmp_path / "works.jsonl"
    citations_path = tmp_path / "coci.csv"
    _write_fixture(
        works_path,
        """
{"id":"https://openalex.org/W1","doi":"https://doi.org/10.1000/a","title":"Neural Retrieval","publication_year":2024,"authorships":[{"author":{"display_name":"Alice"}}],"primary_topic":{"id":"https://openalex.org/T1"}}
{"id":"https://openalex.org/W2","doi":"https://doi.org/10.1000/b","title":"Dense Retrieval","publication_year":2024,"authorships":[{"author":{"display_name":"Bob"}}],"primary_topic":{"id":"https://openalex.org/T1"}}
""",
    )
    _write_fixture(
        citations_path,
        """
citing,cited
10.1000/a,10.1000/shared
10.1000/b,10.1000/shared
""",
    )

    documents, pairs, summary = prepare_openalex_weak_label_evaluation_set(
        works_path,
        dataset_name="openalex_sample",
        citations_path=citations_path,
        min_shared_references=1,
    )

    assert len(documents) == 2
    assert len(pairs) == 1
    assert pairs[0]["candidate_sources"] == ["openalex_topic", "opencitations_shared_citation"]
    assert summary["citation_edge_count"] == 2


def test_prepare_openalex_weak_label_evaluation_set_can_require_opencitations(tmp_path) -> None:
    """验证可只保留 OpenCitations DOI 共享引用支持的 hard negative。"""
    works_path = tmp_path / "works.jsonl"
    citations_path = tmp_path / "coci.csv"
    _write_fixture(
        works_path,
        """
{"id":"https://openalex.org/W1","doi":"https://doi.org/10.1000/a","title":"Neural Retrieval","publication_year":2024,"authorships":[{"author":{"display_name":"Alice"}}],"primary_topic":{"id":"https://openalex.org/T1"},"referenced_works":["https://openalex.org/W3"]}
{"id":"https://openalex.org/W2","doi":"https://doi.org/10.1000/b","title":"Dense Retrieval","publication_year":2024,"authorships":[{"author":{"display_name":"Bob"}}],"primary_topic":{"id":"https://openalex.org/T1"},"referenced_works":["https://openalex.org/W3"]}
{"id":"https://openalex.org/W4","doi":"https://doi.org/10.1000/d","title":"Sparse Retrieval","publication_year":2024,"authorships":[{"author":{"display_name":"Carol"}}],"primary_topic":{"id":"https://openalex.org/T1"},"referenced_works":["https://openalex.org/W3"]}
""",
    )
    _write_fixture(
        citations_path,
        """
citing,cited
10.1000/a,10.1000/shared
10.1000/b,10.1000/shared
""",
    )

    _, pairs, summary = prepare_openalex_weak_label_evaluation_set(
        works_path,
        dataset_name="openalex_sample",
        citations_path=citations_path,
        min_shared_references=1,
        require_opencitations=True,
    )

    assert len(pairs) == 1
    assert pairs[0]["candidate_sources"] == ["openalex_topic", "opencitations_shared_citation"]
    assert summary["require_opencitations"] is True


def test_prepare_openalex_weak_labels_cli_writes_project_contract_files(tmp_path) -> None:
    """验证 OpenAlex CLI 写出统一评估集文件。"""
    works_path = tmp_path / "works.jsonl"
    output_dir = tmp_path / "openalex_eval"
    _write_fixture(
        works_path,
        """
{"id":"https://openalex.org/W1","doi":"https://doi.org/10.1000/a","title":"Neural Retrieval","publication_year":2024,"authorships":[{"author":{"display_name":"Alice"}}],"primary_topic":{"id":"https://openalex.org/T1"},"referenced_works":["https://openalex.org/W3"]}
{"id":"https://openalex.org/W2","doi":"https://doi.org/10.1000/b","title":"Dense Retrieval","publication_year":2024,"authorships":[{"author":{"display_name":"Bob"}}],"primary_topic":{"id":"https://openalex.org/T1"},"referenced_works":["https://openalex.org/W3"]}
""",
    )

    command_prepare_openalex_weak_labels(
        Namespace(
            works=str(works_path),
            output_dir=str(output_dir),
            dataset_name="openalex_sample",
            min_shared_references=1,
            max_pairs_per_topic=5,
            max_pairs=100,
            limit=None,
        )
    )

    documents = read_records(output_dir / "eval_documents.jsonl")
    pairs = read_records(output_dir / "eval_pairs.jsonl")
    summary = read_records(output_dir / "dataset_summary.jsonl")

    assert len(documents) == 2
    assert len(pairs) == 1
    assert summary[0]["agenda_non_identity_pair_count"] == 1


def test_openalex_weak_label_output_can_be_scored_for_false_merge_risk(tmp_path) -> None:
    """验证 OpenAlex 弱标签输出可进入现有评分器。"""
    works_path = tmp_path / "works.jsonl"
    _write_fixture(
        works_path,
        """
{"id":"https://openalex.org/W1","doi":"https://doi.org/10.1000/a","title":"Neural Retrieval","publication_year":2024,"authorships":[{"author":{"display_name":"Alice"}}],"primary_topic":{"id":"https://openalex.org/T1"},"referenced_works":["https://openalex.org/W3"]}
{"id":"https://openalex.org/W2","doi":"https://doi.org/10.1000/b","title":"Neural Retrieval with Dense Models","publication_year":2024,"authorships":[{"author":{"display_name":"Bob"}}],"primary_topic":{"id":"https://openalex.org/T1"},"referenced_works":["https://openalex.org/W3"]}
""",
    )

    documents, pairs, _ = prepare_openalex_weak_label_evaluation_set(works_path, "openalex_sample")
    scored_relations = score_evaluation_pairs(documents, pairs)
    summary_rows = summarize_scored_eval_pairs(scored_relations)

    assert scored_relations[0]["expected_label"] == 0
    assert scored_relations[0]["expected_agenda_label"] == 1
    assert "false_merge_risk" in scored_relations[0]
    assert any(row["metric_target"] == "same_agenda_proxy" for row in summary_rows)
