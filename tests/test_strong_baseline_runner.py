"""测试强 baseline 分数生成器。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_run_representation_baseline
from iad_sieve.evaluation import strong_baseline_runner
from iad_sieve.evaluation.strong_baseline_runner import run_representation_baseline, write_baseline_scores
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


def test_run_representation_baseline_scores_pairs_and_marks_fallback_mode() -> None:
    """验证表示 baseline 输出 pair 分数并标记 fallback 执行模式。"""
    documents = [
        _document("d1", "Neural Retrieval", "Dense retrieval with transformers"),
        _document("d2", "Neural Retrieval", "Dense retrieval with transformers"),
        _document("d3", "Graph Clustering", "Community detection on graphs"),
    ]
    pairs = [
        {"source_document_id": "d1", "target_document_id": "d2"},
        {"source_document_id": "d1", "target_document_id": "d3"},
    ]

    rows, summary = run_representation_baseline(
        documents=documents,
        pairs=pairs,
        system_name="hashing_representation_cosine",
        embedding_model="hashing-fallback",
        score_field="score",
    )

    assert len(rows) == 2
    assert rows[0]["system"] == "hashing_representation_cosine"
    assert rows[0]["baseline_family"] == "representation"
    assert rows[0]["execution_mode"] == "fallback"
    assert rows[0]["score"] > rows[1]["score"]
    assert summary["system"] == "hashing_representation_cosine"
    assert summary["execution_mode"] == "fallback"
    assert summary["pair_count"] == 2


def test_run_representation_baseline_marks_transformers_backend_as_actual_model(monkeypatch) -> None:
    """验证 transformers 后端成功时标记为 actual_model。"""
    documents = [
        _document("d1", "Neural Retrieval", "Dense retrieval with transformers"),
        _document("d2", "Neural Retrieval", "Dense retrieval with transformers"),
    ]
    pairs = [{"source_document_id": "d1", "target_document_id": "d2"}]

    def _fake_encode_documents(
        records,
        model_name,
        batch_size=32,
        dimension=128,
        model_backend="auto",
        pooling_strategy="cls",
        adapter_model=None,
    ):
        """模拟 transformers 编码成功。"""
        return ["d1", "d2"], [[1.0, 0.0], [1.0, 0.0]], {
            "embedding_model": model_name,
            "embedding_dim": 2,
            "embedding_version": "transformers",
            "pooling_strategy": pooling_strategy,
        }

    monkeypatch.setattr(strong_baseline_runner, "encode_documents", _fake_encode_documents)

    rows, summary = run_representation_baseline(
        documents=documents,
        pairs=pairs,
        system_name="specter2_cosine",
        embedding_model="allenai/specter2_base",
        model_backend="transformers",
        pooling_strategy="cls",
    )

    assert rows[0]["execution_mode"] == "actual_model"
    assert summary["execution_mode"] == "actual_model"
    assert summary["embedding_version"] == "transformers"


def test_run_representation_baseline_preserves_specter2_adapter_metadata(monkeypatch) -> None:
    """验证 SPECTER2 adapter baseline 保留 adapter 与 device 元数据。"""
    documents = [
        _document("d1", "Neural Retrieval", "Dense retrieval with transformers"),
        _document("d2", "Neural Retrieval", "Dense retrieval with transformers"),
    ]
    pairs = [{"source_document_id": "d1", "target_document_id": "d2"}]

    def _fake_encode_documents(
        records,
        model_name,
        batch_size=32,
        dimension=128,
        model_backend="auto",
        pooling_strategy="cls",
        adapter_model=None,
    ):
        """模拟 SPECTER2 adapter 编码成功。"""
        assert model_backend == "specter2-adapter"
        assert adapter_model == "allenai/specter2"
        return ["d1", "d2"], [[1.0, 0.0], [1.0, 0.0]], {
            "embedding_model": model_name,
            "adapter_model": adapter_model,
            "embedding_dim": 2,
            "embedding_version": "specter2-adapter",
            "pooling_strategy": pooling_strategy,
            "device": "cuda",
        }

    monkeypatch.setattr(strong_baseline_runner, "encode_documents", _fake_encode_documents)

    rows, summary = run_representation_baseline(
        documents=documents,
        pairs=pairs,
        system_name="specter2_adapter_cosine",
        embedding_model="allenai/specter2_base",
        adapter_model="allenai/specter2",
        model_backend="specter2-adapter",
        pooling_strategy="cls",
    )

    assert rows[0]["execution_mode"] == "actual_model"
    assert rows[0]["adapter_model"] == "allenai/specter2"
    assert rows[0]["device"] == "cuda"
    assert summary["execution_mode"] == "actual_model"
    assert summary["adapter_model"] == "allenai/specter2"
    assert summary["device"] == "cuda"


def test_write_baseline_scores_writes_scores_and_summary(tmp_path) -> None:
    """验证 baseline 分数与执行摘要写出。"""
    output_path = tmp_path / "scores.jsonl"
    summary_path = tmp_path / "summary.jsonl"
    rows = [{"source_document_id": "d1", "target_document_id": "d2", "score": 1.0}]
    summary = {"system": "hashing_representation_cosine", "pair_count": 1}

    write_baseline_scores(rows, summary, output_path, summary_path)

    assert read_records(output_path)[0]["score"] == 1.0
    assert read_records(summary_path)[0]["pair_count"] == 1


def test_run_representation_baseline_cli_writes_scores(tmp_path) -> None:
    """验证 CLI 写出 representation baseline 分数。"""
    documents_path = tmp_path / "documents.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    output_path = tmp_path / "scores.jsonl"
    summary_path = tmp_path / "summary.jsonl"
    _write_jsonl(
        documents_path,
        [
            _document("d1", "Neural Retrieval", "Dense retrieval with transformers"),
            _document("d2", "Neural Retrieval", "Dense retrieval with transformers"),
        ],
    )
    _write_jsonl(pairs_path, [{"source_document_id": "d1", "target_document_id": "d2"}])

    command_run_representation_baseline(
        Namespace(
            documents=str(documents_path),
            pairs=str(pairs_path),
            output=str(output_path),
            summary_output=str(summary_path),
            system_name="hashing_representation_cosine",
            embedding_model="hashing-fallback",
            score_field="score",
            batch_size=32,
            model_backend="hashing",
            adapter_model=None,
            pooling_strategy="cls",
            limit=None,
        )
    )

    rows = read_records(output_path)
    summary_rows = read_records(summary_path)

    assert rows[0]["score"] == 1.0
    assert summary_rows[0]["execution_mode"] == "fallback"


def test_cli_includes_run_representation_baseline_command() -> None:
    """验证 CLI 暴露 run-representation-baseline 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-representation-baseline",
            "--documents",
            "outputs/iad_bench_fixture/iad_bench_documents.jsonl",
            "--pairs",
            "outputs/iad_bench_fixture/iad_bench_pairs.jsonl",
            "--output",
            "outputs/strong_baselines/specter2_scores.jsonl",
            "--summary-output",
            "outputs/strong_baselines/specter2_execution.jsonl",
            "--system-name",
            "specter2_cosine",
            "--embedding-model",
            "allenai/specter2_base",
            "--model-backend",
            "specter2-adapter",
            "--adapter-model",
            "allenai/specter2",
            "--pooling-strategy",
            "cls",
        ]
    )

    assert args.command == "run-representation-baseline"
    assert args.system_name == "specter2_cosine"
    assert args.model_backend == "specter2-adapter"
    assert args.adapter_model == "allenai/specter2"
