"""测试 IAD-Risk Transformer 双空间风险模型。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_train_iad_risk_transformer_model
from iad_sieve.evaluation.iad_risk_transformer_model import (
    build_transformer_pair_features,
    predict_with_iad_risk_transformer_model,
    train_iad_risk_transformer_model,
    write_iad_risk_transformer_outputs,
)
from iad_sieve.utils.io_utils import read_records


def _document(document_id: str, title: str, authors: list[str], year: int, topics: list[str]) -> dict:
    """构造测试文献。

    参数:
        document_id: 文献 ID。
        title: 标题。
        authors: 作者列表。
        year: 出版年份。
        topics: 主题列表。

    返回:
        文献记录。
    """
    return {
        "document_id": document_id,
        "title": title,
        "abstract": title,
        "authors": authors,
        "venue": "SIGMOD",
        "year": year,
        "topics": topics,
        "references": topics,
        "doi": "",
        "arxiv_id": "",
        "openalex_work_id": "",
        "source_dataset": "fixture",
    }


def _pair(source_id: str, target_id: str, same_work: int, same_agenda: int, split: str) -> dict:
    """构造测试 pair。

    参数:
        source_id: 源文献 ID。
        target_id: 目标文献 ID。
        same_work: same_work 标签。
        same_agenda: same_agenda 标签。
        split: 数据 split。

    返回:
        pair 记录。
    """
    relation_label = "same_work" if same_work else "agenda_non_identity" if same_agenda else "unrelated"
    return {
        "pair_id": f"{source_id}-{target_id}",
        "source_document_id": source_id,
        "target_document_id": target_id,
        "expected_label": same_work,
        "expected_agenda_label": same_agenda,
        "relation_label": relation_label,
        "label_strength": "gold" if same_work else "silver",
        "label_source": "fixture",
        "hard_negative_level": "high" if same_agenda and not same_work else "none",
        "split": split,
    }


def _documents() -> list[dict]:
    """构造测试文献集合。

    参数:
        无。

    返回:
        文献列表。
    """
    return [
        _document("d1", "Aurora data stream management system", ["Alice Smith"], 2003, ["stream"]),
        _document("d2", "Aurora data stream management system", ["Alice Smith"], 2003, ["stream"]),
        _document("d3", "Aurora stream query processing architecture", ["Bob Chen"], 2004, ["stream"]),
        _document("d4", "Graph neural clustering for proteins", ["Carol Lee"], 2020, ["graph"]),
        _document("d5", "Fast join processing in databases", ["Diane King"], 2001, ["join"]),
        _document("d6", "Fast join processing in databases", ["Diane King"], 2001, ["join"]),
        _document("d7", "Join ordering for database query plans", ["Evan Lu"], 2002, ["join"]),
    ]


def _pairs() -> list[dict]:
    """构造测试 pair 集合。

    参数:
        无。

    返回:
        pair 列表。
    """
    return [
        _pair("d1", "d2", 1, 1, "train"),
        _pair("d5", "d6", 1, 1, "train"),
        _pair("d1", "d3", 0, 1, "train"),
        _pair("d5", "d7", 0, 1, "train"),
        _pair("d1", "d4", 0, 0, "train"),
        _pair("d5", "d4", 0, 0, "train"),
        _pair("d2", "d3", 0, 1, "test"),
        _pair("d6", "d7", 0, 1, "test"),
    ]


def _write_jsonl(path, records: list[dict]) -> None:
    """写入 JSONL 文件。

    参数:
        path: 输出路径。
        records: 记录列表。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def test_build_transformer_pair_features_uses_document_features_without_label_provenance() -> None:
    """验证 Transformer pair 特征来自文档和 embedding，而非标签来源。"""
    augmented_relations, metadata = build_transformer_pair_features(
        documents=_documents(),
        relations=_pairs(),
        embedding_model="hashing-fallback",
        model_backend="hashing",
    )

    first_relation = augmented_relations[0]
    assert metadata["embedding_version"] == "deterministic-hash-v1"
    assert metadata["pair_count"] == len(_pairs())
    assert "transformer_cosine" in first_relation
    assert "title_similarity" in first_relation
    assert "same_source_dataset" not in first_relation
    assert "label_provenance" not in first_relation or "shared_reference_count" not in first_relation


def test_train_iad_risk_transformer_model_builds_required_heads() -> None:
    """验证 IAD-Risk Transformer 使用 train split 训练 required heads。"""
    model, augmented_relations = train_iad_risk_transformer_model(
        documents=_documents(),
        relations=_pairs(),
        embedding_model="hashing-fallback",
        model_backend="hashing",
        train_split="train",
        random_seed=7,
    )
    prediction = predict_with_iad_risk_transformer_model(model, augmented_relations[2])

    assert model["trained"] is True
    assert model["model_type"] == "iad_risk_transformer_frozen_encoder_centroid_model"
    assert model["system_name"] == "iad_risk_transformer"
    assert model["train_pair_count"] == 6
    assert model["encoder"]["execution_mode"] == "fallback"
    assert model["heads"]["same_work"]["trained"] is True
    assert model["heads"]["agenda_non_identity"]["trained"] is True
    assert "same_source_dataset" not in model["feature_groups"]["risk_space"]
    assert "same_source_dataset" not in model["heads"]["agenda_non_identity"]["feature_fields"]
    assert prediction["merge_prediction"] in {0, 1}


def test_train_iad_risk_transformer_model_keeps_identity_predictions_without_agenda_non_identity() -> None:
    """验证缺少 agenda_non_identity 正例时不会把已训练 identity head 整体禁用。"""
    identity_only_pairs = [
        _pair("d1", "d2", 1, 1, "train"),
        _pair("d5", "d6", 1, 1, "train"),
        _pair("d1", "d4", 0, 0, "train"),
        _pair("d5", "d4", 0, 0, "train"),
        _pair("d2", "d3", 0, 0, "test"),
    ]

    model, augmented_relations = train_iad_risk_transformer_model(
        documents=_documents(),
        relations=identity_only_pairs,
        embedding_model="hashing-fallback",
        model_backend="hashing",
        train_split="train",
        random_seed=7,
    )
    positive_prediction = predict_with_iad_risk_transformer_model(model, augmented_relations[0])

    assert model["trained"] is True
    assert model["prediction_mode"] == "identity_only"
    assert model["heads"]["same_work"]["trained"] is True
    assert model["heads"]["agenda_non_identity"]["trained"] is False
    assert positive_prediction["p_same_work"] >= 0.5
    assert positive_prediction["merge_prediction"] == 1


def test_write_iad_risk_transformer_outputs_writes_split_summaries(tmp_path) -> None:
    """验证 IAD-Risk Transformer 写出模型、预测和 split 摘要。"""
    model, augmented_relations = train_iad_risk_transformer_model(
        documents=_documents(),
        relations=_pairs(),
        embedding_model="hashing-fallback",
        model_backend="hashing",
        train_split="train",
        random_seed=7,
    )
    output_dir = tmp_path / "iad_risk_transformer"

    write_iad_risk_transformer_outputs(model, augmented_relations, output_dir)

    summary_rows = read_records(output_dir / "iad_risk_transformer_summary.jsonl")
    prediction_rows = read_records(output_dir / "iad_risk_transformer_predictions.jsonl")

    assert (output_dir / "iad_risk_transformer_model.json").exists()
    assert {row["eval_split"] for row in summary_rows} == {"all", "train", "dev", "test"}
    assert summary_rows[0]["evidence_layer"] == "iad_risk_model"
    assert prediction_rows


def test_train_iad_risk_transformer_model_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 IAD-Risk Transformer 产物。"""
    documents_path = tmp_path / "documents.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    output_dir = tmp_path / "iad_risk_transformer"
    _write_jsonl(documents_path, _documents())
    _write_jsonl(pairs_path, _pairs())

    command_train_iad_risk_transformer_model(
        Namespace(
            documents=str(documents_path),
            relations=[str(pairs_path)],
            output_dir=str(output_dir),
            embedding_model="hashing-fallback",
            model_backend="hashing",
            adapter_model=None,
            system_name="iad_risk_transformer_fixture",
            batch_size=4,
            pooling_strategy="cls",
            train_split="train",
            seed=7,
            limit=None,
            work_threshold=0.5,
            agenda_block_threshold=0.5,
            risk_threshold=0.5,
        )
    )

    assert (output_dir / "iad_risk_transformer_model.json").exists()
    summary_rows = read_records(output_dir / "iad_risk_transformer_summary.jsonl")
    assert summary_rows[0]["system"] == "iad_risk_transformer_fixture"
    assert read_records(output_dir / "iad_risk_transformer_predictions.jsonl")


def test_train_iad_risk_transformer_model_cli_accepts_multiple_document_files(tmp_path) -> None:
    """验证 CLI 支持多个文献 JSONL 以训练 gold+silver 混合关系。"""
    first_documents_path = tmp_path / "documents_a.jsonl"
    second_documents_path = tmp_path / "documents_b.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    output_dir = tmp_path / "iad_risk_transformer"
    documents = _documents()
    _write_jsonl(first_documents_path, documents[:4])
    _write_jsonl(second_documents_path, documents[4:])
    _write_jsonl(pairs_path, _pairs())

    command_train_iad_risk_transformer_model(
        Namespace(
            documents=[str(first_documents_path), str(second_documents_path)],
            relations=[str(pairs_path)],
            output_dir=str(output_dir),
            embedding_model="hashing-fallback",
            model_backend="hashing",
            adapter_model=None,
            system_name="iad_risk_transformer_multi_doc_fixture",
            batch_size=4,
            pooling_strategy="cls",
            train_split="train",
            seed=7,
            limit=None,
            work_threshold=0.5,
            agenda_block_threshold=0.5,
            risk_threshold=0.5,
        )
    )

    model = json.loads((output_dir / "iad_risk_transformer_model.json").read_text(encoding="utf-8"))
    assert model["encoder"]["document_count"] == len(documents)
    assert read_records(output_dir / "iad_risk_transformer_predictions.jsonl")


def test_train_iad_risk_transformer_model_cli_uses_extra_train_relations_without_evaluating_them(tmp_path) -> None:
    """验证额外训练关系只补强模型训练，不进入评估预测输出。"""
    documents_path = tmp_path / "documents.jsonl"
    eval_pairs_path = tmp_path / "eval_pairs.jsonl"
    extra_train_pairs_path = tmp_path / "extra_train_pairs.jsonl"
    output_dir = tmp_path / "iad_risk_transformer"
    eval_pairs = [
        _pair("d1", "d2", 1, 1, "train"),
        _pair("d5", "d6", 1, 1, "train"),
        _pair("d1", "d4", 0, 0, "train"),
        _pair("d5", "d4", 0, 0, "train"),
        _pair("d2", "d3", 0, 0, "test"),
    ]
    _write_jsonl(documents_path, _documents())
    _write_jsonl(eval_pairs_path, eval_pairs)
    _write_jsonl(extra_train_pairs_path, _pairs())

    command_train_iad_risk_transformer_model(
        Namespace(
            documents=[str(documents_path)],
            relations=[str(eval_pairs_path)],
            extra_train_relations=[str(extra_train_pairs_path)],
            output_dir=str(output_dir),
            embedding_model="hashing-fallback",
            model_backend="hashing",
            adapter_model=None,
            system_name="iad_risk_transformer_extra_train_fixture",
            batch_size=4,
            pooling_strategy="cls",
            train_split="train",
            seed=7,
            limit=None,
            work_threshold=0.5,
            agenda_block_threshold=0.5,
            risk_threshold=0.5,
        )
    )

    model = json.loads((output_dir / "iad_risk_transformer_model.json").read_text(encoding="utf-8"))
    prediction_rows = read_records(output_dir / "iad_risk_transformer_predictions.jsonl")
    assert model["heads"]["agenda_non_identity"]["trained"] is True
    assert model["train_pair_count"] > 4
    assert len(prediction_rows) == len(eval_pairs)


def test_cli_includes_train_iad_risk_transformer_model_command() -> None:
    """验证 CLI 暴露 train-iad-risk-transformer-model 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "train-iad-risk-transformer-model",
            "--documents",
            "outputs/iad_bench_open_v2/iad_bench_documents.jsonl",
            "--relations",
            "outputs/iad_bench_open_v2/iad_bench_pairs.jsonl",
            "--extra-train-relations",
            "outputs/iad_training_blend_open_v3_gold_silver/iad_training_relations.jsonl",
            "--output-dir",
            "outputs/iad_risk_transformer_open_v2",
            "--embedding-model",
            "allenai/specter2_base",
            "--model-backend",
            "specter2-adapter",
            "--adapter-model",
            "allenai/specter2",
        ]
    )

    assert args.command == "train-iad-risk-transformer-model"
    assert args.documents == ["outputs/iad_bench_open_v2/iad_bench_documents.jsonl"]
    assert args.extra_train_relations == ["outputs/iad_training_blend_open_v3_gold_silver/iad_training_relations.jsonl"]
    assert args.embedding_model == "allenai/specter2_base"
    assert args.model_backend == "specter2-adapter"
    assert args.adapter_model == "allenai/specter2"
    assert args.system_name == "iad_risk_transformer"
