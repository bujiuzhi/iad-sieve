"""测试实体匹配 checkpoint 训练入口。"""

from __future__ import annotations

import json
from argparse import Namespace

import pytest

from iad_sieve.cli import build_parser, command_train_entity_matching_baseline
from iad_sieve.evaluation.entity_matching_baseline_trainer import (
    build_entity_matching_training_examples,
    train_entity_matching_baseline,
)


def _document(document_id: str, title: str) -> dict:
    """构造测试文献。

    参数:
        document_id: 文献 ID。
        title: 文献标题。

    返回:
        文献记录。
    """
    return {
        "document_id": document_id,
        "title": title,
        "authors": ["Alice"],
        "venue": "TestConf",
        "year": 2024,
        "abstract": "A short abstract.",
    }


def test_build_entity_matching_training_examples_filters_train_split() -> None:
    """验证训练样本只使用目标 split 且跳过无效记录。"""
    documents = [_document("d1", "A"), _document("d2", "A revised"), _document("d3", "B")]
    pairs = [
        {"source_document_id": "d1", "target_document_id": "d2", "same_work": 1, "split": "train"},
        {"source_document_id": "d1", "target_document_id": "d3", "same_work": 0, "split": "test"},
        {"source_document_id": "d1", "target_document_id": "missing", "same_work": 1, "split": "train"},
        {"source_document_id": "d2", "target_document_id": "d3", "split": "train"},
    ]

    examples, summary = build_entity_matching_training_examples(documents, pairs)

    assert len(examples) == 1
    assert examples[0].label == 1
    assert "title: a" in examples[0].left_text
    assert summary["training_pair_count"] == 1
    assert summary["skipped_split_count"] == 1
    assert summary["missing_document_count"] == 1
    assert summary["missing_label_count"] == 1


def test_train_entity_matching_baseline_rejects_empty_training_examples(tmp_path) -> None:
    """验证训练样本为空时明确失败。"""
    with pytest.raises(ValueError, match="训练样本为空"):
        train_entity_matching_baseline(
            documents=[_document("d1", "A"), _document("d2", "B")],
            pairs=[{"source_document_id": "d1", "target_document_id": "d2", "same_work": 1, "split": "test"}],
            output_dir=tmp_path / "model",
            system_name="ditto_style_em_test",
        )


def test_train_entity_matching_baseline_cli_arguments() -> None:
    """验证 CLI 暴露实体匹配训练命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "train-entity-matching-baseline",
            "--documents",
            "documents.jsonl",
            "--pairs",
            "pairs.jsonl",
            "--output-dir",
            "outputs/models/ditto_style_em_source_heldout",
            "--summary-output",
            "outputs/models/ditto_style_em_source_heldout_training_summary.jsonl",
            "--system-name",
            "ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
            "--base-model-name",
            "textattack/roberta-base-MRPC",
            "--epochs",
            "2",
        ]
    )

    assert args.func == command_train_entity_matching_baseline
    assert args.output_dir == "outputs/models/ditto_style_em_source_heldout"
    assert args.epochs == 2
    assert args.train_split == "train"


def test_command_train_entity_matching_baseline_uses_trainer(monkeypatch, tmp_path) -> None:
    """验证 CLI command 读取输入并写出训练摘要。"""
    documents_path = tmp_path / "documents.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    summary_path = tmp_path / "summary.jsonl"
    documents_path.write_text(json.dumps(_document("d1", "A")) + "\n", encoding="utf-8")
    pairs_path.write_text(json.dumps({"source_document_id": "d1", "target_document_id": "d1", "same_work": 1, "split": "train"}) + "\n", encoding="utf-8")

    def fake_train_entity_matching_baseline(**kwargs):
        """伪造训练函数。

        参数:
            kwargs: 训练参数。

        返回:
            训练摘要。
        """
        return {"system": kwargs["system_name"], "output_dir": str(kwargs["output_dir"]), "training_pair_count": len(kwargs["pairs"])}

    monkeypatch.setattr("iad_sieve.cli.train_entity_matching_baseline", fake_train_entity_matching_baseline)

    command_train_entity_matching_baseline(
        Namespace(
            documents=str(documents_path),
            pairs=str(pairs_path),
            output_dir=str(tmp_path / "model"),
            summary_output=str(summary_path),
            system_name="ditto_style_em_test",
            base_model_name="textattack/roberta-base-MRPC",
            train_split="train",
            split_field="split",
            label_field="same_work",
            batch_size=2,
            epochs=1,
            learning_rate=2e-5,
            max_length=128,
            seed=42,
            limit=None,
        )
    )

    summary_rows = [json.loads(line) for line in summary_path.read_text(encoding="utf-8").splitlines()]
    assert summary_rows == [{"system": "ditto_style_em_test", "output_dir": str(tmp_path / "model"), "training_pair_count": 1}]
