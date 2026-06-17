"""测试 IAD-Risk gold/silver 训练混合输入构建。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_iad_training_blend
from iad_sieve.evaluation.iad_training_blend_builder import (
    build_iad_training_blend,
    build_iad_training_blend_from_paths,
    write_iad_training_blend_outputs,
)
from iad_sieve.evaluation.iad_training_input_audit import build_iad_training_input_audit_rows, build_iad_training_input_audit_summary
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


def _relation(pair_id: str, relation_label: str, identity_score: float, agenda_score: float, label_strength: str) -> dict:
    """构造带 IAD 特征的训练候选关系。

    参数:
        pair_id: pair ID。
        relation_label: 关系标签。
        identity_score: identity 空间分数。
        agenda_score: agenda 空间分数。
        label_strength: 标签强度。

    返回:
        关系记录。
    """
    expected_label = 1 if relation_label == "same_work" else 0
    expected_agenda_label = 1 if relation_label in {"same_work", "agenda_non_identity"} else 0
    false_merge_risk = max(0.0, agenda_score - identity_score)
    return {
        "pair_id": pair_id,
        "source_document_id": f"s-{pair_id}",
        "target_document_id": f"t-{pair_id}",
        "relation_label": relation_label,
        "label_strength": label_strength,
        "label_source": "deepmatcher" if label_strength == "gold" else "openalex",
        "expected_label": expected_label,
        "expected_agenda_label": expected_agenda_label,
        "identity_score": identity_score,
        "duplicate_score": identity_score,
        "title_similarity": identity_score,
        "author_overlap": identity_score / 2,
        "first_author_match": 1.0 if identity_score >= 0.8 else 0.0,
        "identifier_score": 1.0 if identity_score >= 0.95 else 0.0,
        "year_score": identity_score,
        "conflict_score": 0.0,
        "agenda_score": agenda_score,
        "topic_score": agenda_score,
        "full_similarity": agenda_score,
        "method_similarity": agenda_score,
        "object_similarity": agenda_score,
        "problem_similarity": agenda_score,
        "keyphrase_similarity": agenda_score,
        "category_overlap": agenda_score / 2,
        "agenda_non_identity_score": false_merge_risk,
        "false_merge_risk": false_merge_risk,
        "contribution_score": agenda_score,
    }


def test_build_iad_training_blend_balances_gold_and_silver_relations() -> None:
    """验证 gold/silver 训练混合输入按关系标签配平并保留证据边界。"""
    relations = [
        _relation("same-1", "same_work", 0.95, 0.88, "gold"),
        _relation("same-2", "same_work", 0.90, 0.84, "gold"),
        _relation("unrelated-1", "unrelated", 0.10, 0.12, "gold"),
        _relation("unrelated-2", "unrelated", 0.20, 0.18, "gold"),
        _relation("agenda-1", "agenda_non_identity", 0.20, 0.90, "silver"),
        _relation("agenda-2", "agenda_non_identity", 0.25, 0.86, "silver"),
        {"pair_id": "raw", "relation_label": "agenda_non_identity", "expected_label": 0, "expected_agenda_label": 1},
    ]

    training_rows, summary = build_iad_training_blend(relations, seed=7)
    audit_summary = build_iad_training_input_audit_summary(build_iad_training_input_audit_rows(training_rows))

    assert summary["training_blend_ready"] is True
    assert summary["selected_pair_count"] == 6
    assert summary["skipped_missing_feature_count"] == 1
    assert summary["relation_label_counts"] == {"agenda_non_identity": 2, "same_work": 2, "unrelated": 2}
    assert summary["label_strength_counts"] == {"gold": 4, "silver": 2}
    assert {row["training_evidence_scope"] for row in training_rows} == {"gold_silver_training_blend"}
    assert audit_summary["training_input_ready"] is True


def test_build_iad_training_blend_from_paths(tmp_path) -> None:
    """验证训练混合输入可从多个 JSONL 文件读取。"""
    gold_path = tmp_path / "gold.jsonl"
    silver_path = tmp_path / "silver.jsonl"
    _write_jsonl(gold_path, [_relation("same-1", "same_work", 0.95, 0.88, "gold"), _relation("unrelated-1", "unrelated", 0.10, 0.12, "gold")])
    _write_jsonl(silver_path, [_relation("agenda-1", "agenda_non_identity", 0.20, 0.90, "silver")])

    training_rows, summary = build_iad_training_blend_from_paths([gold_path, silver_path], seed=3)

    assert len(training_rows) == 3
    assert summary["input_path_count"] == 2
    assert summary["training_blend_ready"] is True


def test_write_iad_training_blend_outputs(tmp_path) -> None:
    """验证训练混合输入写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "iad_training_blend"
    training_rows, summary = build_iad_training_blend(
        [
            _relation("same-1", "same_work", 0.95, 0.88, "gold"),
            _relation("unrelated-1", "unrelated", 0.10, 0.12, "gold"),
            _relation("agenda-1", "agenda_non_identity", 0.20, 0.90, "silver"),
        ]
    )

    write_iad_training_blend_outputs(training_rows, summary, output_dir)

    assert read_records(output_dir / "iad_training_relations.jsonl")
    assert read_records(output_dir / "iad_training_blend_summary.jsonl")
    assert (output_dir / "iad_training_blend.csv").exists()
    assert "# IAD-Risk Training Blend" in (output_dir / "iad_training_blend.md").read_text(encoding="utf-8")


def test_build_iad_training_blend_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出训练混合输入。"""
    relations_path = tmp_path / "relations.jsonl"
    output_dir = tmp_path / "iad_training_blend"
    _write_jsonl(
        relations_path,
        [
            _relation("same-1", "same_work", 0.95, 0.88, "gold"),
            _relation("unrelated-1", "unrelated", 0.10, 0.12, "gold"),
            _relation("agenda-1", "agenda_non_identity", 0.20, 0.90, "silver"),
        ],
    )

    command_build_iad_training_blend(
        Namespace(
            relations=[str(relations_path)],
            output_dir=str(output_dir),
            relation_labels="same_work,unrelated,agenda_non_identity",
            max_per_relation=None,
            train_ratio=0.8,
            dev_ratio=0.1,
            seed=7,
        )
    )

    assert read_records(output_dir / "iad_training_relations.jsonl")
    assert read_records(output_dir / "iad_training_blend_summary.jsonl")


def test_cli_includes_build_iad_training_blend_command() -> None:
    """验证 CLI 暴露 build-iad-training-blend 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-iad-training-blend",
            "--relations",
            "outputs/iad_bench_open_v3_balanced_gold_source_heldout/scored_relations.jsonl",
            "outputs/openalex_api_v1/scored_relations.jsonl",
            "--output-dir",
            "outputs/iad_training_blend_open_v3_gold_silver",
        ]
    )

    assert args.command == "build-iad-training-blend"
    assert args.relations[-1].endswith("openalex_api_v1/scored_relations.jsonl")
