"""测试 IAD-Sieve 轻量关系分类器。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_train_iad_classifier
from iad_sieve.evaluation.iad_classifier import (
    predict_with_iad_model,
    train_iad_relation_model,
    write_iad_model_json,
)
from iad_sieve.utils.io_utils import read_records


def _relation(identity_score: float, agenda_score: float, expected_label: int, expected_agenda_label: int | None = None) -> dict:
    """构造测试关系记录。

    参数:
        identity_score: identity 分数。
        agenda_score: agenda 分数。
        expected_label: same_work 标签。
        expected_agenda_label: 可选 same_agenda 标签。

    返回:
        关系记录。
    """
    record = {
        "identity_score": identity_score,
        "duplicate_score": identity_score,
        "agenda_score": agenda_score,
        "topic_score": agenda_score,
        "agenda_non_identity_score": max(0.0, agenda_score - identity_score),
        "false_merge_risk": max(0.0, agenda_score - identity_score),
        "title_similarity": identity_score,
        "full_similarity": agenda_score,
        "author_overlap": identity_score,
        "first_author_match": 1.0 if identity_score >= 0.8 else 0.0,
        "year_score": 1.0,
        "identifier_score": 1.0 if identity_score >= 0.95 else 0.0,
        "category_overlap": 1.0,
        "method_similarity": agenda_score,
        "object_similarity": agenda_score,
        "result_similarity": agenda_score,
        "problem_similarity": agenda_score,
        "keyphrase_similarity": agenda_score,
        "contribution_score": agenda_score,
        "conflict_score": 0.0,
        "expected_label": expected_label,
    }
    if expected_agenda_label is not None:
        record["expected_agenda_label"] = expected_agenda_label
    return record


def test_train_iad_relation_model_trains_same_work_classifier() -> None:
    """验证 same_work 轻量分类器可以训练并预测。"""
    relations = [
        _relation(0.95, 0.80, 1),
        _relation(0.90, 0.70, 1),
        _relation(0.20, 0.80, 0),
        _relation(0.30, 0.60, 0),
    ]

    model = train_iad_relation_model(relations, target="same_work", random_seed=7)

    assert model["trained"] is True
    assert model["target"] == "same_work"
    assert model["training_metrics"]["weak_label_count"] == 4
    assert model["training_metrics"]["f1"] >= 0.9
    assert predict_with_iad_model(model, _relation(0.93, 0.75, 1)) >= 0.5


def test_train_iad_relation_model_skips_single_class_target() -> None:
    """验证单类标签不会训练伪模型。"""
    relations = [
        _relation(0.20, 0.80, 0),
        _relation(0.30, 0.70, 0),
    ]

    model = train_iad_relation_model(relations, target="same_work")

    assert model["trained"] is False
    assert model["skip_reason"] == "single_class_or_missing_label"


def test_train_iad_relation_model_trains_agenda_non_identity_target() -> None:
    """验证 agenda_non_identity 目标可由 expected_label 与 expected_agenda_label 构造。"""
    relations = [
        _relation(0.20, 0.90, 0, expected_agenda_label=1),
        _relation(0.25, 0.85, 0, expected_agenda_label=1),
        _relation(0.92, 0.90, 1, expected_agenda_label=1),
        _relation(0.20, 0.20, 0, expected_agenda_label=0),
    ]

    model = train_iad_relation_model(relations, target="agenda_non_identity", random_seed=7)

    assert model["trained"] is True
    assert model["target"] == "agenda_non_identity"
    assert predict_with_iad_model(model, _relation(0.20, 0.88, 0, expected_agenda_label=1)) >= 0.5


def test_write_iad_model_json_writes_transparent_coefficients(tmp_path) -> None:
    """验证模型 JSON 包含可解释系数。"""
    model = train_iad_relation_model(
        [
            _relation(0.95, 0.80, 1),
            _relation(0.20, 0.80, 0),
        ],
        target="same_work",
    )
    output_path = tmp_path / "same_work_model.json"

    write_iad_model_json(model, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "feature_fields" in content
    assert "coefficients" in content


def test_cli_includes_train_iad_classifier_command() -> None:
    """验证 CLI 暴露 train-iad-classifier 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "train-iad-classifier",
            "--relations",
            "scored_a.jsonl",
            "scored_b.jsonl",
            "--output-dir",
            "models/iad",
            "--targets",
            "same_work,same_agenda",
        ]
    )

    assert args.command == "train-iad-classifier"
    assert args.relations == ["scored_a.jsonl", "scored_b.jsonl"]


def test_train_iad_classifier_cli_writes_models_and_summary(tmp_path) -> None:
    """验证训练 CLI 写出模型和摘要文件。"""
    relations_path = tmp_path / "scored_relations.jsonl"
    output_dir = tmp_path / "iad_classifier"
    records = [
        _relation(0.95, 0.80, 1, expected_agenda_label=1),
        _relation(0.90, 0.70, 1, expected_agenda_label=1),
        _relation(0.20, 0.90, 0, expected_agenda_label=1),
        _relation(0.30, 0.20, 0, expected_agenda_label=0),
    ]
    relations_path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")

    command_train_iad_classifier(
        Namespace(
            relations=[str(relations_path)],
            output_dir=str(output_dir),
            targets="same_work,same_agenda,agenda_non_identity",
            seed=7,
            limit=None,
        )
    )

    summary = read_records(output_dir / "training_summary.jsonl")

    assert (output_dir / "same_work_model.json").exists()
    assert any(row["target"] == "same_work" and row["trained"] is True for row in summary)
