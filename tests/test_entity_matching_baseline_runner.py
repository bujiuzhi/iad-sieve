"""测试实体匹配强 baseline 分数生成器。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_run_entity_matching_baseline
from iad_sieve.evaluation import entity_matching_baseline_runner
from iad_sieve.evaluation.entity_matching_baseline_runner import run_entity_matching_baseline
from iad_sieve.utils.io_utils import read_records


def _document(document_id: str, title: str, abstract: str) -> dict:
    """构造测试文献。

    参数:
        document_id: 文献 ID。
        title: 标题。
        abstract: 摘要。

    返回:
        文献记录。
    """
    return {
        "document_id": document_id,
        "title": title,
        "title_normalized": title.lower(),
        "abstract": abstract,
        "abstract_normalized": abstract.lower(),
    }


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


def test_run_entity_matching_baseline_scores_pairs_and_marks_fallback_mode() -> None:
    """验证实体匹配 baseline 输出 pair 分数并标记 fallback 执行模式。"""
    documents = [
        _document("d1", "Entity Matching for Citations", "Matching paper records with metadata"),
        _document("d2", "Entity Matching for Citations", "Matching paper records with metadata"),
        _document("d3", "Graph Clustering", "Community detection on citation graphs"),
    ]
    pairs = [
        {"source_document_id": "d1", "target_document_id": "d2"},
        {"source_document_id": "d1", "target_document_id": "d3"},
    ]

    rows, summary = run_entity_matching_baseline(
        documents=documents,
        pairs=pairs,
        system_name="heuristic_entity_matcher",
        model_name="heuristic-entity-matcher",
        score_field="match_probability",
        model_backend="heuristic",
    )

    assert len(rows) == 2
    assert rows[0]["system"] == "heuristic_entity_matcher"
    assert rows[0]["baseline_family"] == "entity_matching"
    assert rows[0]["execution_mode"] == "fallback"
    assert rows[0]["match_probability"] > rows[1]["match_probability"]
    assert summary["baseline_family"] == "entity_matching"
    assert summary["execution_mode"] == "fallback"
    assert summary["pair_count"] == 2


def test_run_entity_matching_baseline_marks_transformers_classifier_as_actual_model(monkeypatch) -> None:
    """验证 transformers 序列分类模型成功时标记为 actual_model。"""
    documents = [
        _document("d1", "Entity Matching for Citations", "Matching paper records with metadata"),
        _document("d2", "Entity Matching for Citations", "Matching paper records with metadata"),
    ]
    pairs = [{"source_document_id": "d1", "target_document_id": "d2"}]

    def _fake_score_pairs(text_pairs, model_name, batch_size):
        """模拟 transformers pair classifier 成功。"""
        assert model_name == "hf/entity-matching-roberta"
        assert batch_size == 4
        assert len(text_pairs) == 1
        return [0.91], {"resolved_model_name": model_name, "model_version": "transformers-sequence-classification", "device": "cuda:0"}

    monkeypatch.setattr(entity_matching_baseline_runner, "_score_pairs_with_transformers", _fake_score_pairs)

    rows, summary = run_entity_matching_baseline(
        documents=documents,
        pairs=pairs,
        system_name="roberta_entity_matcher",
        model_name="hf/entity-matching-roberta",
        score_field="match_probability",
        model_backend="transformers",
        batch_size=4,
    )

    assert rows[0]["execution_mode"] == "actual_model"
    assert rows[0]["match_probability"] == 0.91
    assert rows[0]["device"] == "cuda:0"
    assert summary["execution_mode"] == "actual_model"
    assert summary["model_version"] == "transformers-sequence-classification"
    assert summary["device"] == "cuda:0"


def test_run_entity_matching_baseline_cli_writes_scores(tmp_path) -> None:
    """验证 CLI 写出 entity matching baseline 分数。"""
    documents_path = tmp_path / "documents.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    output_path = tmp_path / "scores.jsonl"
    summary_path = tmp_path / "summary.jsonl"
    _write_jsonl(
        documents_path,
        [
            _document("d1", "Entity Matching for Citations", "Matching paper records with metadata"),
            _document("d2", "Entity Matching for Citations", "Matching paper records with metadata"),
        ],
    )
    _write_jsonl(pairs_path, [{"source_document_id": "d1", "target_document_id": "d2"}])

    command_run_entity_matching_baseline(
        Namespace(
            documents=str(documents_path),
            pairs=str(pairs_path),
            output=str(output_path),
            summary_output=str(summary_path),
            system_name="heuristic_entity_matcher",
            model_name="heuristic-entity-matcher",
            score_field="match_probability",
            model_backend="heuristic",
            batch_size=8,
            limit=None,
        )
    )

    rows = read_records(output_path)
    summary_rows = read_records(summary_path)

    assert rows[0]["match_probability"] == 1.0
    assert summary_rows[0]["execution_mode"] == "fallback"


def test_cli_includes_run_entity_matching_baseline_command() -> None:
    """验证 CLI 暴露 run-entity-matching-baseline 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-entity-matching-baseline",
            "--documents",
            "outputs/iad_bench_fixture/iad_bench_documents.jsonl",
            "--pairs",
            "outputs/iad_bench_fixture/iad_bench_pairs.jsonl",
            "--output",
            "outputs/strong_baselines/ditto_scores.jsonl",
            "--summary-output",
            "outputs/strong_baselines/ditto_execution.jsonl",
            "--system-name",
            "roberta_entity_matcher",
            "--model-name",
            "hf/entity-matching-roberta",
            "--model-backend",
            "transformers",
        ]
    )

    assert args.command == "run-entity-matching-baseline"
    assert args.system_name == "roberta_entity_matcher"
    assert args.model_backend == "transformers"
