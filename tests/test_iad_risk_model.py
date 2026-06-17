"""测试 IAD-Risk 双空间风险模型。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_train_iad_risk_model
from iad_sieve.evaluation.iad_risk_model import (
    build_iad_risk_summary,
    predict_with_iad_risk_model,
    train_iad_risk_model,
    write_iad_risk_outputs,
)
from iad_sieve.utils.io_utils import read_records


def _relation(identity_score: float, agenda_score: float, expected_label: int, expected_agenda_label: int) -> dict:
    """构造测试关系。

    参数:
        identity_score: 身份分数。
        agenda_score: 议题分数。
        expected_label: same_work 标签。
        expected_agenda_label: same_agenda 标签。

    返回:
        关系记录。
    """
    return {
        "source_document_id": f"s{identity_score}-{agenda_score}",
        "target_document_id": f"t{identity_score}-{agenda_score}",
        "identity_score": identity_score,
        "duplicate_score": identity_score,
        "title_similarity": identity_score,
        "author_overlap": identity_score,
        "first_author_match": 1.0 if identity_score >= 0.8 else 0.0,
        "identifier_score": 1.0 if identity_score >= 0.95 else 0.0,
        "agenda_score": agenda_score,
        "topic_score": agenda_score,
        "full_similarity": agenda_score,
        "method_similarity": agenda_score,
        "object_similarity": agenda_score,
        "problem_similarity": agenda_score,
        "keyphrase_similarity": agenda_score,
        "agenda_non_identity_score": max(0.0, agenda_score - identity_score),
        "false_merge_risk": max(0.0, agenda_score - identity_score),
        "contribution_score": agenda_score,
        "conflict_score": 0.0,
        "expected_label": expected_label,
        "expected_agenda_label": expected_agenda_label,
    }


def _write_jsonl(path, records: list[dict]) -> None:
    """写入 JSONL。

    参数:
        path: 输出路径。
        records: 记录列表。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def test_train_iad_risk_model_builds_dual_space_heads_and_blocks_hard_negative() -> None:
    """验证 IAD-Risk 训练三个 head 并阻断同议题非同身份样本。"""
    relations = [
        _relation(0.96, 0.90, 1, 1),
        _relation(0.92, 0.85, 1, 1),
        _relation(0.25, 0.92, 0, 1),
        _relation(0.30, 0.88, 0, 1),
        _relation(0.15, 0.20, 0, 0),
        _relation(0.20, 0.25, 0, 0),
    ]

    model = train_iad_risk_model(relations, random_seed=7)
    same_work_prediction = predict_with_iad_risk_model(model, _relation(0.94, 0.88, 1, 1))
    hard_negative_prediction = predict_with_iad_risk_model(model, _relation(0.20, 0.90, 0, 1))

    assert model["trained"] is True
    assert model["model_type"] == "iad_risk_dual_space_centroid_model"
    assert set(model["heads"]) == {"same_work", "same_agenda", "agenda_non_identity"}
    assert same_work_prediction["p_same_work"] >= 0.5
    assert same_work_prediction["merge_prediction"] == 1
    assert hard_negative_prediction["p_agenda_non_identity"] >= 0.5
    assert hard_negative_prediction["p_false_merge_risk"] >= 0.5
    assert hard_negative_prediction["merge_prediction"] == 0


def test_build_iad_risk_summary_marks_model_evidence_layer() -> None:
    """验证训练摘要写入 iad_risk_model 证据层。"""
    model = train_iad_risk_model(
        [
            _relation(0.96, 0.90, 1, 1),
            _relation(0.25, 0.92, 0, 1),
            _relation(0.20, 0.20, 0, 0),
        ],
        random_seed=7,
    )

    summary = build_iad_risk_summary(model, model_path="outputs/iad_risk_model/iad_risk_model.json")

    assert summary["evidence_layer"] == "iad_risk_model"
    assert summary["model_type"] == "iad_risk_dual_space_centroid_model"
    assert summary["trained"] is True
    assert summary["head_count"] == 3


def test_train_iad_risk_model_treats_same_work_without_agenda_label_as_not_hard_negative() -> None:
    """验证缺少 expected_agenda_label 的 same_work 不会被风险 head 误阻断。"""
    same_work_a = _relation(0.96, 0.90, 1, 1)
    same_work_b = _relation(0.92, 0.85, 1, 1)
    same_work_a.pop("expected_agenda_label")
    same_work_b.pop("expected_agenda_label")
    relations = [
        same_work_a,
        same_work_b,
        _relation(0.25, 0.92, 0, 1),
        _relation(0.30, 0.88, 0, 1),
        _relation(0.15, 0.20, 0, 0),
        _relation(0.20, 0.25, 0, 0),
    ]

    model = train_iad_risk_model(relations, random_seed=7)
    prediction = predict_with_iad_risk_model(model, _relation(0.94, 0.88, 1, 1))

    assert prediction["p_same_work"] >= 0.5
    assert prediction["p_agenda_non_identity"] < 0.5
    assert prediction["merge_prediction"] == 1


def test_train_iad_risk_model_predicts_with_required_heads_when_same_agenda_is_single_class() -> None:
    """验证 same_agenda 单类跳过时 required heads 仍可完成风险预测。"""
    same_work_a = _relation(0.96, 0.90, 1, 1)
    same_work_b = _relation(0.92, 0.85, 1, 1)
    unrelated_a = _relation(0.20, 0.20, 0, 0)
    unrelated_b = _relation(0.25, 0.25, 0, 0)
    same_work_a.pop("expected_agenda_label")
    same_work_b.pop("expected_agenda_label")
    unrelated_a.pop("expected_agenda_label")
    unrelated_b.pop("expected_agenda_label")
    relations = [
        same_work_a,
        same_work_b,
        unrelated_a,
        unrelated_b,
        _relation(0.25, 0.92, 0, 1),
        _relation(0.30, 0.88, 0, 1),
    ]

    model = train_iad_risk_model(relations, random_seed=7)
    same_work_prediction = predict_with_iad_risk_model(model, _relation(0.94, 0.88, 1, 1))
    hard_negative_prediction = predict_with_iad_risk_model(model, _relation(0.20, 0.90, 0, 1))
    summary = build_iad_risk_summary(model, model_path="outputs/iad_risk_model/iad_risk_model.json")

    assert model["trained"] is True
    assert model["heads"]["same_agenda"]["trained"] is False
    assert model["trained_head_count"] == 2
    assert same_work_prediction["merge_prediction"] == 1
    assert hard_negative_prediction["merge_prediction"] == 0
    assert summary["trained"] is True
    assert summary["trained_head_count"] == 2
    assert summary["f1"] > 0.0


def test_train_iad_risk_model_cli_writes_model_summary_and_predictions(tmp_path) -> None:
    """验证 CLI 写出 IAD-Risk 模型、摘要和预测。"""
    relations_path = tmp_path / "relations.jsonl"
    output_dir = tmp_path / "iad_risk_model"
    _write_jsonl(
        relations_path,
        [
            _relation(0.96, 0.90, 1, 1),
            _relation(0.92, 0.85, 1, 1),
            _relation(0.25, 0.92, 0, 1),
            _relation(0.30, 0.88, 0, 1),
            _relation(0.15, 0.20, 0, 0),
            _relation(0.20, 0.25, 0, 0),
        ],
    )

    command_train_iad_risk_model(
        Namespace(
            relations=[str(relations_path)],
            output_dir=str(output_dir),
            seed=7,
            limit=None,
            work_threshold=0.5,
            agenda_block_threshold=0.5,
            risk_threshold=0.5,
        )
    )

    summary_rows = read_records(output_dir / "iad_risk_summary.jsonl")
    prediction_rows = read_records(output_dir / "iad_risk_predictions.jsonl")

    assert (output_dir / "iad_risk_model.json").exists()
    assert summary_rows[0]["evidence_layer"] == "iad_risk_model"
    assert prediction_rows


def test_train_iad_risk_model_cli_supports_split_aware_source_heldout(tmp_path) -> None:
    """验证 CLI 支持只用 train split 训练并输出 test split 摘要。"""
    relations_path = tmp_path / "relations.jsonl"
    output_dir = tmp_path / "iad_risk_source_heldout"
    train_rows = [
        {**_relation(0.96, 0.90, 1, 1), "pair_id": "train_same_1", "split": "train"},
        {**_relation(0.92, 0.85, 1, 1), "pair_id": "train_same_2", "split": "train"},
        {**_relation(0.25, 0.92, 0, 1), "pair_id": "train_hard_1", "split": "train"},
        {**_relation(0.20, 0.20, 0, 0), "pair_id": "train_unrelated_1", "split": "train"},
    ]
    test_rows = [
        {**_relation(0.94, 0.88, 1, 1), "pair_id": "test_same_1", "split": "test"},
        {**_relation(0.22, 0.90, 0, 1), "pair_id": "test_hard_1", "split": "test"},
        {**_relation(0.18, 0.18, 0, 0), "pair_id": "test_unrelated_1", "split": "test"},
    ]
    _write_jsonl(relations_path, [*train_rows, *test_rows])

    command_train_iad_risk_model(
        Namespace(
            relations=[str(relations_path)],
            output_dir=str(output_dir),
            seed=7,
            limit=None,
            work_threshold=0.5,
            agenda_block_threshold=0.5,
            risk_threshold=0.5,
            train_split="train",
            eval_splits="all,train,test",
        )
    )

    model = json.loads((output_dir / "iad_risk_model.json").read_text(encoding="utf-8"))
    summary_rows = read_records(output_dir / "iad_risk_summary.jsonl")
    by_split = {row["eval_split"]: row for row in summary_rows}

    assert model["train_split"] == "train"
    assert model["train_pair_count"] == 4
    assert {row["eval_split"] for row in summary_rows} == {"all", "train", "test"}
    assert by_split["test"]["eval_pair_count"] == 3
    assert by_split["test"]["train_pair_count"] == 4
    assert by_split["test"]["f1"] >= 0.0


def test_write_iad_risk_outputs_writes_all_files(tmp_path) -> None:
    """验证 IAD-Risk 输出函数写出全部产物。"""
    relations = [_relation(0.96, 0.90, 1, 1), _relation(0.25, 0.92, 0, 1), _relation(0.20, 0.20, 0, 0)]
    relations[1]["pair_id"] = "iadbench_000002"
    relations[1]["relation_label"] = "agenda_non_identity"
    relations[1]["label_strength"] = "silver"
    relations[1]["label_source"] = "openalex_opencitations"
    relations[1]["hard_negative_level"] = "high"
    model = train_iad_risk_model(relations, random_seed=7)
    output_dir = tmp_path / "iad_risk_model"

    write_iad_risk_outputs(model, relations, output_dir)

    prediction_rows = read_records(output_dir / "iad_risk_predictions.jsonl")
    silver_row = next(row for row in prediction_rows if row.get("pair_id") == "iadbench_000002")
    assert (output_dir / "iad_risk_model.json").exists()
    assert (output_dir / "iad_risk_summary.jsonl").exists()
    assert (output_dir / "iad_risk_predictions.jsonl").exists()
    assert silver_row["label_strength"] == "silver"
    assert silver_row["label_source"] == "openalex_opencitations"
    assert silver_row["hard_negative_level"] == "high"


def test_write_iad_risk_outputs_infers_provenance_from_legacy_scored_relations(tmp_path) -> None:
    """验证旧 scored_relations 缺少 label_strength 时能推断 provenance。"""
    relations = [_relation(0.96, 0.90, 1, 1), _relation(0.25, 0.92, 0, 1), _relation(0.20, 0.20, 0, 0)]
    relations[1]["label_type"] = "openalex_agenda_non_identity_weak"
    relations[1]["label_reason"] = "same_openalex_topic_shared_references_different_doi"
    relations[1]["candidate_sources"] = ["openalex_topic", "opencitations_shared_citation"]
    relations[1]["raw_similarity"] = 1.0
    model = train_iad_risk_model(relations, random_seed=7)
    output_dir = tmp_path / "iad_risk_model"

    write_iad_risk_outputs(model, relations, output_dir)

    prediction_rows = read_records(output_dir / "iad_risk_predictions.jsonl")
    silver_row = next(row for row in prediction_rows if row.get("label_source") == "openalex_opencitations")
    assert silver_row["label_strength"] == "silver"
    assert silver_row["relation_label"] == "agenda_non_identity"
    assert silver_row["hard_negative_level"] == "high"
    assert silver_row["label_provenance"]["candidate_sources"] == ["openalex_topic", "opencitations_shared_citation"]


def test_write_iad_risk_outputs_distinguishes_openalex_from_opencitations(tmp_path) -> None:
    """验证纯 OpenAlex 共享引用弱标签不会被误标为 OpenCitations。"""
    relations = [_relation(0.96, 0.90, 1, 1), _relation(0.25, 0.92, 0, 1), _relation(0.20, 0.20, 0, 0)]
    relations[1]["label_type"] = "openalex_agenda_non_identity_weak"
    relations[1]["label_reason"] = "same_openalex_topic_shared_references_different_doi"
    relations[1]["candidate_sources"] = ["openalex_topic", "openalex_shared_references"]
    relations[1]["raw_similarity"] = 1.0
    model = train_iad_risk_model(relations, random_seed=7)
    output_dir = tmp_path / "iad_risk_model"

    write_iad_risk_outputs(model, relations, output_dir)

    prediction_rows = read_records(output_dir / "iad_risk_predictions.jsonl")
    silver_row = next(row for row in prediction_rows if row.get("label_source") == "openalex")
    assert silver_row["label_strength"] == "silver"
    assert silver_row["relation_label"] == "agenda_non_identity"
    assert silver_row["label_provenance"]["candidate_sources"] == ["openalex_topic", "openalex_shared_references"]


def test_cli_includes_train_iad_risk_model_command() -> None:
    """验证 CLI 暴露 train-iad-risk-model 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "train-iad-risk-model",
            "--relations",
            "outputs/deepmatcher_fixture/scored_relations.jsonl",
            "outputs/scirepeval_fixture/scored_relations.jsonl",
            "--output-dir",
            "outputs/iad_risk_model_fixture",
        ]
    )

    assert args.command == "train-iad-risk-model"
    assert args.output_dir == "outputs/iad_risk_model_fixture"


def test_write_iad_risk_outputs_records_eval_label_coverage(tmp_path) -> None:
    """验证 split summary 写出评估标签覆盖计数。"""
    relations = [
        {**_relation(0.96, 0.90, 1, 1), "split": "train", "evaluation_split_strategy": "source_held_out"},
        {**_relation(0.25, 0.92, 0, 1), "split": "train", "evaluation_split_strategy": "source_held_out"},
        {**_relation(0.20, 0.20, 0, 0), "split": "train", "evaluation_split_strategy": "source_held_out"},
        {**_relation(0.94, 0.88, 1, 1), "split": "test", "evaluation_split_strategy": "source_held_out"},
        {**_relation(0.22, 0.24, 0, 0), "split": "test", "evaluation_split_strategy": "source_held_out"},
    ]
    model = train_iad_risk_model(relations, random_seed=7, train_split="train")
    output_dir = tmp_path / "iad_risk_model"

    write_iad_risk_outputs(model, relations, output_dir, eval_splits=["test"])

    summary = read_records(output_dir / "iad_risk_summary.jsonl")[0]
    assert summary["same_work_positive_count"] == 1
    assert summary["same_work_negative_count"] == 1
    assert summary["agenda_non_identity_positive_count"] == 0
    assert summary["agenda_non_identity_negative_count"] == 2
