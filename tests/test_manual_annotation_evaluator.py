"""测试人工标注结果评估。"""

from __future__ import annotations

import csv

from iad_sieve.cli import build_parser
from iad_sieve.evaluation.manual_annotation_evaluator import evaluate_manual_annotations, write_manual_annotation_outputs


def _annotation(annotation_id: str, suggested_label: int, annotator_label: str) -> dict:
    """构造人工标注记录。

    参数:
        annotation_id: 标注 ID。
        suggested_label: 弱标签建议。
        annotator_label: 人工标注值。

    返回:
        标注记录。
    """
    return {
        "annotation_id": annotation_id,
        "source_document_id": f"source-{annotation_id}",
        "target_document_id": f"target-{annotation_id}",
        "suggested_label": suggested_label,
        "annotator_label": annotator_label,
        "annotation_notes": "",
    }


def test_evaluate_manual_annotations_counts_coverage_and_agreement() -> None:
    """验证人工标注评估统计覆盖率、一致率和分歧样本。"""
    summary_rows, disagreement_rows = evaluate_manual_annotations(
        [
            _annotation("ann-1", 1, "duplicate"),
            _annotation("ann-2", 0, "not_duplicate"),
            _annotation("ann-3", 1, "not_duplicate"),
            _annotation("ann-4", 0, ""),
        ]
    )

    summary = summary_rows[0]
    assert summary["sample_count"] == 4
    assert summary["labeled_count"] == 3
    assert summary["unlabeled_count"] == 1
    assert summary["manual_positive_count"] == 1
    assert summary["manual_negative_count"] == 2
    assert summary["suggested_agreement_count"] == 2
    assert summary["suggested_disagreement_count"] == 1
    assert summary["suggested_agreement_rate"] == 0.666667
    assert summary["suggested_label_precision"] == 0.5
    assert summary["suggested_label_recall"] == 1.0
    assert len(disagreement_rows) == 1
    assert disagreement_rows[0]["annotation_id"] == "ann-3"


def test_write_manual_annotation_outputs_writes_summary_and_disagreements(tmp_path) -> None:
    """验证人工标注评估文件落盘。"""
    summary_rows, disagreement_rows = evaluate_manual_annotations(
        [
            _annotation("ann-1", 1, "1"),
            _annotation("ann-2", 0, "0"),
            _annotation("ann-3", 1, "0"),
        ]
    )
    output_dir = tmp_path / "manual_annotation"

    write_manual_annotation_outputs(summary_rows, disagreement_rows, output_dir)

    with (output_dir / "manual_annotation_summary.csv").open("r", encoding="utf-8", newline="") as file:
        header = next(csv.reader(file))
    assert header[:4] == ["sample_count", "labeled_count", "unlabeled_count", "manual_positive_count"]
    assert (output_dir / "manual_annotation_disagreements.jsonl").read_text(encoding="utf-8").count("\n") == 1


def test_cli_includes_score_manual_annotations_command() -> None:
    """验证 CLI 暴露 score-manual-annotations 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "score-manual-annotations",
            "--input",
            "manual_annotation_sample.jsonl",
            "--output-dir",
            "reports/manual_annotation",
        ]
    )

    assert args.command == "score-manual-annotations"
    assert args.input == "manual_annotation_sample.jsonl"
