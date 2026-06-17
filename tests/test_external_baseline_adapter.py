"""测试外部强基线分数评估适配。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_evaluate_external_baseline
from iad_sieve.evaluation.external_baseline_adapter import (
    attach_external_baseline_scores,
    evaluate_external_baseline,
    read_external_baseline_scores,
)
from iad_sieve.utils.io_utils import read_records


def _relation(source_id: str, target_id: str, expected_label: int, expected_agenda_label: int | None = None) -> dict:
    """构造测试关系。

    参数:
        source_id: 源文献 ID。
        target_id: 目标文献 ID。
        expected_label: same_work 标签。
        expected_agenda_label: 可选 same_agenda 标签。

    返回:
        关系记录。
    """
    record = {
        "source_document_id": source_id,
        "target_document_id": target_id,
        "expected_label": expected_label,
    }
    if expected_agenda_label is not None:
        record["expected_agenda_label"] = expected_agenda_label
    return record


def test_read_external_baseline_scores_reads_csv_by_unordered_pair(tmp_path) -> None:
    """验证外部 CSV 分数按无向 pair 读取。"""
    baseline_path = tmp_path / "specter2_scores.csv"
    baseline_path.write_text(
        "source_document_id,target_document_id,score\nb,a,0.91\nc,d,0.20\n",
        encoding="utf-8",
    )

    scores = read_external_baseline_scores(baseline_path, score_field="score")

    assert scores[("a", "b")] == 0.91
    assert scores[("c", "d")] == 0.20


def test_attach_external_baseline_scores_keeps_unmatched_relations() -> None:
    """验证缺失外部分数时关系仍保留。"""
    relations = [_relation("a", "b", 1), _relation("c", "d", 0)]
    scores = {("a", "b"): 0.91}

    attached = attach_external_baseline_scores(relations, scores, output_score_field="specter2_score")

    assert attached[0]["specter2_score"] == 0.91
    assert "specter2_score" not in attached[1]


def test_evaluate_external_baseline_reports_same_work_metrics() -> None:
    """验证外部 same_work baseline 输出二分类指标。"""
    relations = [
        {**_relation("a", "b", 1), "specter2_score": 0.91},
        {**_relation("c", "d", 0), "specter2_score": 0.70},
        {**_relation("e", "f", 0), "specter2_score": 0.20},
    ]

    rows = evaluate_external_baseline(
        relations,
        system_name="specter2_cosine",
        score_field="specter2_score",
        thresholds=[0.5, 0.9],
        metric_target="same_work",
        baseline_family="representation",
        execution_mode="actual_model",
    )

    assert rows[0]["system"] == "specter2_cosine"
    assert rows[0]["baseline_family"] == "representation"
    assert rows[0]["execution_mode"] == "actual_model"
    assert rows[0]["threshold"] == 0.5
    assert rows[0]["false_positive"] == 1
    assert rows[1]["threshold"] == 0.9
    assert rows[1]["false_positive"] == 0


def test_evaluate_external_baseline_reports_same_agenda_metrics() -> None:
    """验证外部 same_agenda baseline 可评估 proxy 标签。"""
    relations = [
        {**_relation("a", "b", 0, expected_agenda_label=1), "llm_agenda_score": 0.85},
        {**_relation("c", "d", 0, expected_agenda_label=0), "llm_agenda_score": 0.30},
    ]

    rows = evaluate_external_baseline(
        relations,
        system_name="llm_agenda_judge",
        score_field="llm_agenda_score",
        thresholds=[0.5],
        metric_target="same_agenda",
    )

    assert rows[0]["metric_target"] == "same_agenda"
    assert rows[0]["f1"] == 1.0


def test_evaluate_external_baseline_filters_requested_eval_split() -> None:
    """验证外部 baseline 可按指定 split 输出泛化指标。"""
    relations = [
        {**_relation("a", "b", 1), "split": "train", "specter2_score": 0.95},
        {**_relation("c", "d", 0), "split": "test", "specter2_score": 0.80},
        {**_relation("e", "f", 1), "split": "test", "specter2_score": 0.90},
    ]

    rows = evaluate_external_baseline(
        relations,
        system_name="specter2_cosine",
        score_field="specter2_score",
        thresholds=[0.85],
        metric_target="same_work",
        baseline_family="representation",
        execution_mode="actual_model",
        split_field="split",
        eval_splits=["test"],
    )

    assert len(rows) == 1
    assert rows[0]["eval_split"] == "test"
    assert rows[0]["split_field"] == "split"
    assert rows[0]["false_positive"] == 0
    assert rows[0]["true_positive"] == 1


def test_external_baseline_cli_writes_scored_relations_and_summary(tmp_path) -> None:
    """验证 CLI 写出外部分数合并结果和指标摘要。"""
    relations_path = tmp_path / "relations.jsonl"
    baseline_path = tmp_path / "ditto_scores.jsonl"
    output_path = tmp_path / "relations_with_ditto.jsonl"
    summary_path = tmp_path / "ditto_summary.jsonl"
    relations = [_relation("a", "b", 1), _relation("c", "d", 0)]
    baseline_rows = [
        {"source_document_id": "a", "target_document_id": "b", "probability": 0.93},
        {"source_document_id": "c", "target_document_id": "d", "probability": 0.20},
    ]
    relations_path.write_text("\n".join(json.dumps(row) for row in relations) + "\n", encoding="utf-8")
    baseline_path.write_text("\n".join(json.dumps(row) for row in baseline_rows) + "\n", encoding="utf-8")

    command_evaluate_external_baseline(
        Namespace(
            relations=str(relations_path),
            baseline=str(baseline_path),
            output=str(output_path),
            summary_output=str(summary_path),
            system_name="ditto_probability",
            score_field="probability",
            output_score_field="ditto_probability",
            thresholds="0.5,0.9",
            metric_target="same_work",
            baseline_family="entity_matching",
            execution_mode="actual_model",
            split_field="",
            eval_splits="",
            limit=None,
        )
    )

    scored_rows = read_records(output_path)
    summary_rows = read_records(summary_path)

    assert scored_rows[0]["ditto_probability"] == 0.93
    assert any(row["system"] == "ditto_probability" and row["threshold"] == 0.5 for row in summary_rows)
    assert summary_rows[0]["baseline_family"] == "entity_matching"
    assert summary_rows[0]["execution_mode"] == "actual_model"


def test_external_baseline_cli_writes_split_summary(tmp_path) -> None:
    """验证 CLI 支持按 split 写出外部 baseline 指标。"""
    relations_path = tmp_path / "relations.jsonl"
    baseline_path = tmp_path / "scores.jsonl"
    output_path = tmp_path / "relations_with_scores.jsonl"
    summary_path = tmp_path / "summary.jsonl"
    relations = [
        {**_relation("a", "b", 1), "split": "train"},
        {**_relation("c", "d", 0), "split": "test"},
        {**_relation("e", "f", 1), "split": "test"},
    ]
    baseline_rows = [
        {"source_document_id": "a", "target_document_id": "b", "score": 0.95},
        {"source_document_id": "c", "target_document_id": "d", "score": 0.80},
        {"source_document_id": "e", "target_document_id": "f", "score": 0.90},
    ]
    relations_path.write_text("\n".join(json.dumps(row) for row in relations) + "\n", encoding="utf-8")
    baseline_path.write_text("\n".join(json.dumps(row) for row in baseline_rows) + "\n", encoding="utf-8")

    command_evaluate_external_baseline(
        Namespace(
            relations=str(relations_path),
            baseline=str(baseline_path),
            output=str(output_path),
            summary_output=str(summary_path),
            system_name="specter2_cosine",
            score_field="score",
            output_score_field="specter2_score",
            thresholds="0.85",
            metric_target="same_work",
            baseline_family="representation",
            execution_mode="actual_model",
            split_field="split",
            eval_splits="test",
            limit=None,
        )
    )

    summary_rows = read_records(summary_path)

    assert len(summary_rows) == 1
    assert summary_rows[0]["eval_split"] == "test"


def test_cli_includes_evaluate_external_baseline_command() -> None:
    """验证 CLI 暴露 evaluate-external-baseline 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "evaluate-external-baseline",
            "--relations",
            "scored_relations.jsonl",
            "--baseline",
            "specter2_scores.csv",
            "--output",
            "relations_with_specter2.jsonl",
            "--summary-output",
            "specter2_summary.jsonl",
            "--system-name",
            "specter2_cosine",
            "--score-field",
            "score",
            "--output-score-field",
            "specter2_score",
            "--thresholds",
            "0.8,0.9",
            "--metric-target",
            "same_work",
            "--baseline-family",
            "representation",
            "--execution-mode",
            "actual_model",
        ]
    )

    assert args.command == "evaluate-external-baseline"
    assert args.system_name == "specter2_cosine"
    assert args.baseline_family == "representation"
    assert args.execution_mode == "actual_model"
