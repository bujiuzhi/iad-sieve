"""测试 IAD-Bench 数据契约构建器。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_iad_bench
from iad_sieve.evaluation.iad_bench_builder import build_iad_bench
from iad_sieve.utils.io_utils import read_records


def _write_jsonl(path, records: list[dict]) -> None:
    """写入 JSONL 测试文件。

    参数:
        path: 输出路径。
        records: 记录列表。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def _write_eval_dir(base_dir, documents: list[dict], pairs: list[dict], summary: dict) -> None:
    """写入评估目录 fixture。

    参数:
        base_dir: 评估目录。
        documents: eval_documents 记录。
        pairs: eval_pairs 记录。
        summary: dataset_summary 记录。

    返回:
        无。
    """
    _write_jsonl(base_dir / "eval_documents.jsonl", documents)
    _write_jsonl(base_dir / "eval_pairs.jsonl", pairs)
    _write_jsonl(base_dir / "dataset_summary.jsonl", [summary])


def _document(document_id: str, title: str, dataset: str, doi: str = "", arxiv_id: str = "") -> dict:
    """构造测试文献。

    参数:
        document_id: 文献 ID。
        title: 标题。
        dataset: 来源数据集。
        doi: DOI。
        arxiv_id: arXiv ID。

    返回:
        文献记录。
    """
    return {
        "document_id": document_id,
        "title": title,
        "abstract": f"{title} abstract",
        "authors": ["Alice Smith"],
        "publication_year": 2024,
        "journal_ref": "SIGIR",
        "doi": doi,
        "arxiv_id": arxiv_id,
        "categories": ["information_retrieval"],
        "primary_category": "information_retrieval",
        "source_dataset": dataset,
        "metadata_json": {"referenced_work_ids": ["W0"]},
    }


def test_build_iad_bench_writes_contract_outputs_and_preserves_label_strength(tmp_path) -> None:
    """验证 IAD-Bench 输出字段、标签强度和 provenance。"""
    deepmatcher_dir = tmp_path / "deepmatcher"
    scirepeval_dir = tmp_path / "scirepeval"
    openalex_dir = tmp_path / "openalex"
    output_dir = tmp_path / "iad_bench"
    _write_eval_dir(
        deepmatcher_dir,
        [
            _document("deepmatcher:DBLP-ACM:tableA:a1", "Neural IR", "DBLP-ACM"),
            _document("deepmatcher:DBLP-ACM:tableB:b1", "Neural IR", "DBLP-ACM"),
            _document("deepmatcher:DBLP-ACM:tableB:b2", "Neural Ranking", "DBLP-ACM"),
        ],
        [
            {
                "source_document_id": "deepmatcher:DBLP-ACM:tableA:a1",
                "target_document_id": "deepmatcher:DBLP-ACM:tableB:b1",
                "expected_label": 1,
                "label_type": "deepmatcher_same_work_gold",
                "label_reason": "public_gold_label",
                "candidate_sources": ["deepmatcher_gold"],
                "source_pair_id": "dm-1",
            },
            {
                "source_document_id": "deepmatcher:DBLP-ACM:tableA:a1",
                "target_document_id": "deepmatcher:DBLP-ACM:tableB:b2",
                "expected_label": 0,
                "label_type": "deepmatcher_same_work_gold",
                "label_reason": "public_gold_label",
                "candidate_sources": ["deepmatcher_gold"],
                "source_pair_id": "dm-2",
            },
        ],
        {"dataset_name": "DBLP-ACM", "label_type": "same_work_gold"},
    )
    _write_eval_dir(
        scirepeval_dir,
        [
            _document("scirepeval:scidocs:p1", "Dense Retrieval", "scidocs"),
            _document("scirepeval:scidocs:p2", "Neural Retrieval", "scidocs"),
        ],
        [
            {
                "source_document_id": "scirepeval:scidocs:p1",
                "target_document_id": "scirepeval:scidocs:p2",
                "expected_label": 0,
                "expected_agenda_label": 1,
                "label_type": "scirepeval_agenda_non_identity_proxy",
                "label_reason": "proximity_relevance_proxy",
                "candidate_sources": ["scirepeval_proximity"],
                "relevance_score": 1.0,
            }
        ],
        {"dataset_name": "scidocs", "label_type": "same_agenda_proxy_as_non_duplicate"},
    )
    _write_eval_dir(
        openalex_dir,
        [
            _document("openalex:cs:W1", "Citation Retrieval", "openalex", doi="10.1/a"),
            _document("openalex:cs:W2", "Reference Retrieval", "openalex", doi="10.1/b"),
        ],
        [
            {
                "source_document_id": "openalex:cs:W1",
                "target_document_id": "openalex:cs:W2",
                "expected_label": 0,
                "expected_agenda_label": 1,
                "label_type": "openalex_agenda_non_identity_weak",
                "label_reason": "same_openalex_topic_shared_references_different_doi",
                "candidate_sources": ["openalex_topic", "opencitations_shared_citation"],
                "shared_reference_count": 2,
                "shared_references": ["W3", "doi:10.1/shared"],
                "primary_topic": "openalex:T1",
            }
        ],
        {"dataset_name": "openalex_cs", "label_type": "same_agenda_weak_as_non_duplicate"},
    )

    summary = build_iad_bench(
        source_dirs=[deepmatcher_dir, scirepeval_dir, openalex_dir],
        output_dir=output_dir,
        seed=11,
        train_ratio=0.5,
        dev_ratio=0.25,
    )

    pairs = read_records(output_dir / "iad_bench_pairs.jsonl")
    documents = read_records(output_dir / "iad_bench_documents.jsonl")
    split_rows = read_records(output_dir / "iad_bench_splits.jsonl")
    summary_rows = read_records(output_dir / "iad_bench_summary.jsonl")
    openalex_pair = next(pair for pair in pairs if pair["label_source"] == "openalex_opencitations")
    scirepeval_pair = next(pair for pair in pairs if pair["label_source"] == "scirepeval")
    deepmatcher_positive = next(pair for pair in pairs if pair["source_pair_id"] == "dm-1")

    assert summary["pair_count"] == 4
    assert summary["evidence_layer"] == "iad_bench_provenance"
    assert summary_rows[0]["evidence_layer"] == "iad_bench_provenance"
    assert len(documents) == 7
    assert {pair["label_strength"] for pair in pairs} == {"gold", "proxy", "silver"}
    assert deepmatcher_positive["label_source"] == "deepmatcher_dblp_acm"
    assert deepmatcher_positive["relation_label"] == "same_work"
    assert deepmatcher_positive["expected_label"] == 1
    assert scirepeval_pair["relation_label"] == "agenda_non_identity"
    assert scirepeval_pair["hard_negative_level"] == "medium"
    assert openalex_pair["relation_label"] == "agenda_non_identity"
    assert openalex_pair["label_strength"] == "silver"
    assert openalex_pair["hard_negative_level"] == "high"
    assert openalex_pair["label_provenance"]["shared_reference_count"] == 2
    assert openalex_pair["label_provenance"]["same_doi"] is False
    assert not any(pair["label_strength"] == "gold" and "openalex" in pair["label_source"] for pair in pairs)
    assert {row["pair_id"] for row in split_rows} == {pair["pair_id"] for pair in pairs}
    assert "IAD-Bench" in (output_dir / "dataset_card.md").read_text(encoding="utf-8")
    assert "openalex_opencitations" in (output_dir / "label_provenance_summary.csv").read_text(encoding="utf-8")


def test_build_iad_bench_distinguishes_deepmatcher_source_datasets(tmp_path) -> None:
    """验证 DeepMatcher 公开 gold 来源按数据集细分 label_source。"""
    dblp_scholar_dir = tmp_path / "dblp_scholar"
    amazon_google_dir = tmp_path / "amazon_google"
    output_dir = tmp_path / "iad_bench"
    _write_eval_dir(
        dblp_scholar_dir,
        [
            _document("deepmatcher:DBLP-Scholar:tableA:a1", "Paper One", "DBLP-Scholar"),
            _document("deepmatcher:DBLP-Scholar:tableB:b1", "Paper One", "DBLP-Scholar"),
        ],
        [
            {
                "source_document_id": "deepmatcher:DBLP-Scholar:tableA:a1",
                "target_document_id": "deepmatcher:DBLP-Scholar:tableB:b1",
                "expected_label": 1,
                "label_type": "deepmatcher_same_work_gold",
                "candidate_sources": ["deepmatcher_gold"],
            }
        ],
        {"dataset_name": "DBLP-Scholar", "label_type": "same_work_gold"},
    )
    _write_eval_dir(
        amazon_google_dir,
        [
            _document("deepmatcher:Amazon-Google:tableA:a1", "Product One", "Amazon-Google"),
            _document("deepmatcher:Amazon-Google:tableB:b1", "Product One", "Amazon-Google"),
        ],
        [
            {
                "source_document_id": "deepmatcher:Amazon-Google:tableA:a1",
                "target_document_id": "deepmatcher:Amazon-Google:tableB:b1",
                "expected_label": 0,
                "label_type": "deepmatcher_same_work_gold",
                "candidate_sources": ["deepmatcher_gold"],
            }
        ],
        {"dataset_name": "Amazon-Google", "label_type": "same_work_gold"},
    )

    build_iad_bench([dblp_scholar_dir, amazon_google_dir], output_dir, seed=5, train_ratio=0.5, dev_ratio=0.25)

    pairs = read_records(output_dir / "iad_bench_pairs.jsonl")
    label_sources = {pair["label_source"] for pair in pairs}

    assert label_sources == {"deepmatcher_dblp_scholar", "deepmatcher_amazon_google"}
    assert {pair["label_strength"] for pair in pairs} == {"gold"}


def test_build_iad_bench_split_is_deterministic_and_pair_unique(tmp_path) -> None:
    """验证 split 可复现且同一无向 pair 不跨集合泄漏。"""
    source_dir = tmp_path / "deepmatcher"
    output_dir_a = tmp_path / "iad_bench_a"
    output_dir_b = tmp_path / "iad_bench_b"
    _write_eval_dir(
        source_dir,
        [
            _document("deepmatcher:test:tableA:a1", "Paper One", "test"),
            _document("deepmatcher:test:tableB:b1", "Paper One", "test"),
            _document("deepmatcher:test:tableB:b2", "Paper Two", "test"),
        ],
        [
            {
                "source_document_id": "deepmatcher:test:tableA:a1",
                "target_document_id": "deepmatcher:test:tableB:b1",
                "expected_label": 1,
                "label_type": "deepmatcher_same_work_gold",
                "candidate_sources": ["deepmatcher_gold"],
            },
            {
                "source_document_id": "deepmatcher:test:tableB:b2",
                "target_document_id": "deepmatcher:test:tableA:a1",
                "expected_label": 0,
                "label_type": "deepmatcher_same_work_gold",
                "candidate_sources": ["deepmatcher_gold"],
            },
        ],
        {"dataset_name": "test", "label_type": "same_work_gold"},
    )

    build_iad_bench([source_dir], output_dir_a, seed=17, train_ratio=0.5, dev_ratio=0.25)
    build_iad_bench([source_dir], output_dir_b, seed=17, train_ratio=0.5, dev_ratio=0.25)

    first_pairs = read_records(output_dir_a / "iad_bench_pairs.jsonl")
    second_pairs = read_records(output_dir_b / "iad_bench_pairs.jsonl")
    canonical_pairs = {
        tuple(sorted((pair["source_document_id"], pair["target_document_id"])))
        for pair in first_pairs
    }

    assert [(pair["pair_id"], pair["split"]) for pair in first_pairs] == [(pair["pair_id"], pair["split"]) for pair in second_pairs]
    assert len({pair["pair_id"] for pair in first_pairs}) == len(first_pairs)
    assert len(canonical_pairs) == len(first_pairs)


def test_build_iad_bench_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 IAD-Bench 产物。"""
    source_dir = tmp_path / "deepmatcher"
    output_dir = tmp_path / "iad_bench"
    _write_eval_dir(
        source_dir,
        [
            _document("deepmatcher:test:tableA:a1", "Paper One", "test"),
            _document("deepmatcher:test:tableB:b1", "Paper One", "test"),
        ],
        [
            {
                "source_document_id": "deepmatcher:test:tableA:a1",
                "target_document_id": "deepmatcher:test:tableB:b1",
                "expected_label": 1,
                "label_type": "deepmatcher_same_work_gold",
                "candidate_sources": ["deepmatcher_gold"],
            }
        ],
        {"dataset_name": "test", "label_type": "same_work_gold"},
    )

    command_build_iad_bench(
        Namespace(
            source_dirs=[str(source_dir)],
            output_dir=str(output_dir),
            seed=42,
            train_ratio=0.8,
            dev_ratio=0.1,
        )
    )

    assert (output_dir / "iad_bench_documents.jsonl").exists()
    assert (output_dir / "iad_bench_pairs.jsonl").exists()
    assert (output_dir / "label_provenance_summary.csv").exists()


def test_cli_includes_build_iad_bench_command() -> None:
    """验证 CLI 暴露 build-iad-bench 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-iad-bench",
            "--source-dirs",
            "outputs/deepmatcher_fixture",
            "outputs/scirepeval_fixture",
            "outputs/openalex_fixture",
            "--output-dir",
            "outputs/iad_bench_fixture",
            "--seed",
            "11",
        ]
    )

    assert args.command == "build-iad-bench"
    assert args.source_dirs == ["outputs/deepmatcher_fixture", "outputs/scirepeval_fixture", "outputs/openalex_fixture"]
