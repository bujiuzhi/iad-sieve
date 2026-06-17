"""测试 SciRepEval/SciDocs proximity 数据适配。"""

from __future__ import annotations

from argparse import Namespace

from iad_sieve.cli import command_prepare_scirepeval_proximity
from iad_sieve.evaluation.eval_set_builder import score_evaluation_pairs, summarize_scored_eval_pairs
from iad_sieve.evaluation.scirepeval_adapter import (
    prepare_scirepeval_proximity_evaluation_set,
    read_scirepeval_metadata,
    read_scirepeval_proximity_pairs,
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


def test_read_scirepeval_metadata_converts_records(tmp_path) -> None:
    """验证 metadata 转换为标准文献记录。"""
    metadata_path = tmp_path / "metadata.jsonl"
    _write_fixture(
        metadata_path,
        """
{"paper_id":"p1","title":"Neural Retrieval","abstract":"A retrieval paper.","authors":[{"name":"Alice Smith"}],"venue":"SIGIR","year":2024}
""",
    )

    records = read_scirepeval_metadata(metadata_path, "scidocs_cite")

    assert len(records) == 1
    assert records[0]["document_id"] == "scirepeval:scidocs_cite:p1"
    assert records[0]["title_normalized"] == "neural retrieval"
    assert records[0]["authors"] == ["Alice Smith"]
    assert records[0]["publication_year"] == 2024


def test_read_scirepeval_proximity_pairs_marks_agenda_proxy_as_non_duplicate(tmp_path) -> None:
    """验证相关 pair 被标记为议题相关但非重复。"""
    pairs_path = tmp_path / "pairs.csv"
    _write_fixture(
        pairs_path,
        """
query_id,candidate_id,score
p1,p2,1
p1,p3,0
""",
    )

    pairs = read_scirepeval_proximity_pairs(pairs_path, "scidocs_cite", min_relevance_score=1.0)

    assert len(pairs) == 2
    assert pairs[0]["expected_label"] == 0
    assert pairs[0]["expected_agenda_label"] == 1
    assert pairs[0]["label_type"] == "scirepeval_agenda_non_identity_proxy"
    assert pairs[1]["expected_agenda_label"] == 0


def test_prepare_scirepeval_proximity_evaluation_set_outputs_summary(tmp_path) -> None:
    """验证 SciRepEval proximity 评估集输出摘要。"""
    metadata_path = tmp_path / "metadata.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    _write_fixture(
        metadata_path,
        """
{"paper_id":"p1","title":"Neural Retrieval","abstract":"A retrieval paper.","authors":["Alice"],"year":2024}
{"paper_id":"p2","title":"Dense Retrieval","abstract":"Another retrieval paper.","authors":["Bob"],"year":2024}
{"paper_id":"p3","title":"Graph Databases","abstract":"A database paper.","authors":["Carol"],"year":2020}
""",
    )
    _write_fixture(
        pairs_path,
        """
{"query_id":"p1","candidate_id":"p2","score":1}
{"query_id":"p1","candidate_id":"p3","score":0}
""",
    )

    documents, pairs, summary = prepare_scirepeval_proximity_evaluation_set(metadata_path, pairs_path, "scidocs_cite")

    assert len(documents) == 3
    assert len(pairs) == 2
    assert summary["agenda_positive_pair_count"] == 1
    assert summary["duplicate_positive_pair_count"] == 0
    assert summary["label_type"] == "same_agenda_proxy_as_non_duplicate"


def test_prepare_scirepeval_proximity_cli_writes_project_contract_files(tmp_path) -> None:
    """验证 CLI 写出统一评估集文件。"""
    metadata_path = tmp_path / "metadata.jsonl"
    pairs_path = tmp_path / "pairs.csv"
    output_dir = tmp_path / "scirepeval_eval"
    _write_fixture(
        metadata_path,
        """
{"paper_id":"p1","title":"Neural Retrieval","abstract":"A retrieval paper.","authors":["Alice"],"year":2024}
{"paper_id":"p2","title":"Dense Retrieval","abstract":"Another retrieval paper.","authors":["Bob"],"year":2024}
""",
    )
    _write_fixture(
        pairs_path,
        """
query_id,candidate_id,score
p1,p2,1
""",
    )

    command_prepare_scirepeval_proximity(
        Namespace(
            metadata=str(metadata_path),
            pairs=str(pairs_path),
            dataset_name="scidocs_cite",
            output_dir=str(output_dir),
            min_relevance_score=1.0,
        )
    )

    documents = read_records(output_dir / "eval_documents.jsonl")
    pairs = read_records(output_dir / "eval_pairs.jsonl")
    summary = read_records(output_dir / "dataset_summary.jsonl")
    assert len(documents) == 2
    assert pairs[0]["expected_label"] == 0
    assert pairs[0]["expected_agenda_label"] == 1
    assert summary[0]["agenda_positive_pair_count"] == 1


def test_scirepeval_output_can_be_scored_for_false_merge_risk(tmp_path) -> None:
    """验证 SciRepEval 输出可进入现有去重评分器以评估误合并风险。"""
    metadata_path = tmp_path / "metadata.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    _write_fixture(
        metadata_path,
        """
{"paper_id":"p1","title":"Neural Retrieval","abstract":"A retrieval paper.","authors":["Alice"],"year":2024}
{"paper_id":"p2","title":"Neural Retrieval with Dense Models","abstract":"A related retrieval paper.","authors":["Bob"],"year":2024}
""",
    )
    _write_fixture(
        pairs_path,
        """
{"query_id":"p1","candidate_id":"p2","score":1}
""",
    )

    documents, pairs, _ = prepare_scirepeval_proximity_evaluation_set(metadata_path, pairs_path, "scidocs_cite")
    scored_relations = score_evaluation_pairs(documents, pairs)
    summary_rows = summarize_scored_eval_pairs(scored_relations)

    assert scored_relations[0]["expected_label"] == 0
    assert scored_relations[0]["expected_agenda_label"] == 1
    assert "agenda_score" in scored_relations[0]
    assert any(row["system"] == "iad_sieve_conservative" for row in summary_rows)
    assert any(row["system"] == "iad_agenda_score_threshold" and row["metric_target"] == "same_agenda_proxy" for row in summary_rows)
