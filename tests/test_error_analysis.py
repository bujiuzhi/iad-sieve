"""测试错误分析与人工标注样本导出。"""

from __future__ import annotations

import csv

from iad_sieve.cli import build_parser
from iad_sieve.evaluation.error_analysis import build_error_analysis, write_error_analysis_outputs


def _relation(
    source_id: str,
    target_id: str,
    relation_type: str,
    full_similarity: float,
    lexical_similarity: float,
    duplicate_score: float,
    title_similarity: float | None = None,
) -> dict:
    """构造错误分析测试关系记录。

    参数:
        source_id: 源文献 ID。
        target_id: 目标文献 ID。
        relation_type: 关系类型。
        full_similarity: full similarity。
        lexical_similarity: 词法相似度。
        duplicate_score: 重复分数。
        title_similarity: 标题相似度，默认复用 full_similarity。

    返回:
        关系记录。
    """
    return {
        "source_document_id": source_id,
        "target_document_id": target_id,
        "relation_type": relation_type,
        "title_similarity": full_similarity if title_similarity is None else title_similarity,
        "full_similarity": full_similarity,
        "lexical_similarity": lexical_similarity,
        "duplicate_score": duplicate_score,
        "topic_score": max(full_similarity, lexical_similarity),
        "contribution_score": 0.2,
        "conflict_score": 0.0,
        "first_author_match": 1.0,
        "identifier_score": 1.0 if relation_type == "exact_duplicate" else 0.0,
        "candidate_sources": ["dense"],
    }


def _document(document_id: str, title: str) -> dict:
    """构造人工标注样本测试文献。

    参数:
        document_id: 文献 ID。
        title: 文献标题。

    返回:
        文献记录。
    """
    return {
        "document_id": document_id,
        "title": title,
        "abstract": f"Abstract for {title}.",
        "authors": ["Alice Smith", "Bob Chen"],
        "categories": "cs.CL",
        "publication_year": 2024,
    }


def test_build_error_analysis_exports_summary_cases_and_annotation_sample() -> None:
    """验证错误分析输出摘要、错误案例和人工标注样本。"""
    relations = [
        _relation("a", "b", "exact_duplicate", 0.99, 0.95, 0.95),
        _relation("c", "d", "high_confidence_duplicate", 0.88, 0.91, 0.93),
        _relation("e", "f", "same_topic_non_duplicate", 0.92, 0.90, 0.70),
        _relation("g", "h", "same_topic_non_duplicate", 0.40, 0.30, 0.30),
    ]

    summary_rows, case_rows, annotation_rows = build_error_analysis(
        relations,
        documents=[_document("a", "Paper A"), _document("b", "Paper B")],
        systems=["dense_cosine_threshold", "rsl_sieve_conservative"],
        max_cases_per_bucket=2,
        annotation_sample_size=3,
        seed=11,
    )

    dense_summary = next(row for row in summary_rows if row["system"] == "dense_cosine_threshold")
    assert dense_summary["false_positive"] == 1
    assert dense_summary["false_negative"] == 1
    assert dense_summary["weak_label_count"] == 4
    assert {row["error_type"] for row in case_rows if row["system"] == "dense_cosine_threshold"} >= {"false_positive", "false_negative"}
    assert len(annotation_rows) == 3
    assert {"annotation_id", "source_document_id", "target_document_id", "suggested_label", "annotator_label", "annotation_notes"} <= set(annotation_rows[0])
    enriched = next(row for row in annotation_rows if row["source_document_id"] == "a")
    assert enriched["source_title"] == "Paper A"
    assert enriched["target_title"] == "Paper B"


def test_write_error_analysis_outputs_writes_csv_and_jsonl(tmp_path) -> None:
    """验证错误分析文件落盘格式。"""
    output_dir = tmp_path / "error_analysis"
    summary_rows, case_rows, annotation_rows = build_error_analysis(
        [
            _relation("a", "b", "exact_duplicate", 0.99, 0.95, 0.95),
            _relation("e", "f", "same_topic_non_duplicate", 0.92, 0.90, 0.70),
        ],
        max_cases_per_bucket=1,
        annotation_sample_size=2,
        seed=3,
    )

    write_error_analysis_outputs(summary_rows, case_rows, annotation_rows, output_dir)

    with (output_dir / "error_analysis_summary.csv").open("r", encoding="utf-8", newline="") as file:
        header = next(csv.reader(file))
    assert header[:5] == ["system", "weak_label_count", "positive_label_count", "negative_label_count", "predicted_positive_count"]
    assert {"true_positive", "false_positive", "true_negative", "false_negative"} <= set(header)
    assert (output_dir / "error_cases.jsonl").read_text(encoding="utf-8").count("\n") >= 1
    assert (output_dir / "manual_annotation_sample.jsonl").read_text(encoding="utf-8").count("\n") == 2


def test_cli_includes_export_error_analysis_command() -> None:
    """验证 CLI 暴露 export-error-analysis 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "export-error-analysis",
            "--relations",
            "pair_relations.jsonl",
            "--output-dir",
            "reports/error_analysis",
            "--annotation-sample-size",
            "20",
            "--documents",
            "normalized_documents.jsonl",
        ]
    )

    assert args.command == "export-error-analysis"
    assert args.annotation_sample_size == 20
    assert args.documents == "normalized_documents.jsonl"
