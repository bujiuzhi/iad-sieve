"""测试 DeepMatcher gold label 数据适配。"""

from __future__ import annotations

from argparse import Namespace

from iad_sieve.cli import command_prepare_deepmatcher
from iad_sieve.evaluation.deepmatcher_adapter import (
    prepare_deepmatcher_evaluation_set,
    read_deepmatcher_pairs,
    read_deepmatcher_table,
)
from iad_sieve.evaluation.eval_set_builder import score_evaluation_pairs, summarize_scored_eval_pairs
from iad_sieve.utils.io_utils import read_records


def _write_fixture_csv(path, content: str) -> None:
    """写入测试 CSV 文件。

    参数:
        path: 输出路径。
        content: CSV 内容。

    返回:
        无。
    """
    path.write_text(content.strip() + "\n", encoding="utf-8")


def test_read_deepmatcher_table_converts_citation_records(tmp_path) -> None:
    """验证 DeepMatcher 表记录转换为标准文献记录。"""
    table_path = tmp_path / "tableA.csv"
    _write_fixture_csv(
        table_path,
        """
id,title,authors,venue,year
a1,Neural Information Retrieval,Alice Smith; Bob Chen,SIGIR,2024
""",
    )

    records = read_deepmatcher_table(table_path, dataset_name="DBLP-ACM", side="A")

    assert len(records) == 1
    assert records[0]["document_id"] == "deepmatcher:DBLP-ACM:tableA:a1"
    assert records[0]["title_normalized"] == "neural information retrieval"
    assert records[0]["authors"] == ["Alice Smith", "Bob Chen"]
    assert records[0]["publication_year"] == 2024
    assert records[0]["primary_category"] == "citation_matching"


def test_read_deepmatcher_pairs_converts_gold_labels(tmp_path) -> None:
    """验证 DeepMatcher pair 标签转换为 expected_label。"""
    pair_path = tmp_path / "test.csv"
    _write_fixture_csv(
        pair_path,
        """
id,ltable_id,rtable_id,label
1,a1,b1,1
2,a2,b2,0
""",
    )

    pairs = read_deepmatcher_pairs(pair_path, dataset_name="DBLP-ACM")

    assert len(pairs) == 2
    assert pairs[0]["source_document_id"] == "deepmatcher:DBLP-ACM:tableA:a1"
    assert pairs[0]["target_document_id"] == "deepmatcher:DBLP-ACM:tableB:b1"
    assert pairs[0]["expected_label"] == 1
    assert pairs[1]["expected_label"] == 0
    assert pairs[0]["label_type"] == "deepmatcher_same_work_gold"


def test_read_deepmatcher_pairs_accepts_py_entitymatching_headers(tmp_path) -> None:
    """验证 py_entitymatching DBLP-ACM dotted header 可转换为 gold pair。"""
    pair_path = tmp_path / "test.csv"
    _write_fixture_csv(
        pair_path,
        """
_id,ltable.id,rtable.id,gold
0,conf/sigmod/A,304586,1
1,conf/sigmod/B,304587,0
""",
    )

    pairs = read_deepmatcher_pairs(pair_path, dataset_name="py_entitymatching_dblp_acm")

    assert len(pairs) == 2
    assert pairs[0]["source_document_id"] == "deepmatcher:py_entitymatching_dblp_acm:tableA:conf/sigmod/A"
    assert pairs[0]["target_document_id"] == "deepmatcher:py_entitymatching_dblp_acm:tableB:304586"
    assert pairs[0]["source_pair_id"] == "0"
    assert pairs[0]["expected_label"] == 1
    assert pairs[1]["expected_label"] == 0


def test_prepare_deepmatcher_evaluation_set_outputs_needed_documents(tmp_path) -> None:
    """验证完整 DeepMatcher 评估集只输出 pair 需要的文献。"""
    table_a = tmp_path / "tableA.csv"
    table_b = tmp_path / "tableB.csv"
    pairs_file = tmp_path / "test.csv"
    _write_fixture_csv(
        table_a,
        """
id,title,authors,venue,year
a1,Neural Information Retrieval,Alice Smith,SIGIR,2024
a2,Unused Record,Unused Author,SIGIR,2024
""",
    )
    _write_fixture_csv(
        table_b,
        """
id,title,authors,venue,year
b1,Neural IR,Alice Smith,ACM SIGIR,2024
b2,Graph Databases,Carol Lee,VLDB,2020
""",
    )
    _write_fixture_csv(
        pairs_file,
        """
id,ltable_id,rtable_id,label
1,a1,b1,1
2,a1,b2,0
""",
    )

    documents, pairs, summary = prepare_deepmatcher_evaluation_set(table_a, table_b, pairs_file, "DBLP-ACM")

    assert len(documents) == 3
    assert len(pairs) == 2
    assert summary["positive_pair_count"] == 1
    assert summary["negative_pair_count"] == 1
    assert summary["missing_document_count"] == 0


def test_prepare_deepmatcher_cli_writes_project_contract_files(tmp_path) -> None:
    """验证 CLI 命令写出项目统一评估集文件。"""
    table_a = tmp_path / "tableA.csv"
    table_b = tmp_path / "tableB.csv"
    pairs_file = tmp_path / "test.csv"
    output_dir = tmp_path / "deepmatcher_eval"
    _write_fixture_csv(
        table_a,
        """
id,title,authors,venue,year
a1,Neural Information Retrieval,Alice Smith,SIGIR,2024
""",
    )
    _write_fixture_csv(
        table_b,
        """
id,title,authors,venue,year
b1,Neural Information Retrieval,Alice Smith,SIGIR,2024
""",
    )
    _write_fixture_csv(
        pairs_file,
        """
id,ltable_id,rtable_id,label
1,a1,b1,1
""",
    )

    command_prepare_deepmatcher(
        Namespace(
            table_a=str(table_a),
            table_b=str(table_b),
            pairs=str(pairs_file),
            dataset_name="DBLP-ACM",
            output_dir=str(output_dir),
        )
    )

    documents = read_records(output_dir / "eval_documents.jsonl")
    pairs = read_records(output_dir / "eval_pairs.jsonl")
    summary = read_records(output_dir / "dataset_summary.jsonl")
    assert len(documents) == 2
    assert len(pairs) == 1
    assert summary[0]["label_type"] == "same_work_gold"


def test_deepmatcher_output_can_be_scored_by_existing_eval_pipeline(tmp_path) -> None:
    """验证 DeepMatcher 输出可直接进入现有评估评分器。"""
    table_a = tmp_path / "tableA.csv"
    table_b = tmp_path / "tableB.csv"
    pairs_file = tmp_path / "test.csv"
    _write_fixture_csv(
        table_a,
        """
id,title,authors,venue,year
a1,Neural Information Retrieval,Alice Smith,SIGIR,2024
""",
    )
    _write_fixture_csv(
        table_b,
        """
id,title,authors,venue,year
b1,Neural Information Retrieval,Alice Smith,SIGIR,2024
""",
    )
    _write_fixture_csv(
        pairs_file,
        """
id,ltable_id,rtable_id,label
1,a1,b1,1
""",
    )

    documents, pairs, _ = prepare_deepmatcher_evaluation_set(table_a, table_b, pairs_file, "DBLP-ACM")
    scored_relations = score_evaluation_pairs(documents, pairs)
    summary_rows = summarize_scored_eval_pairs(scored_relations)

    assert scored_relations[0]["expected_label"] == 1
    assert "identity_score" in scored_relations[0]
    assert summary_rows
