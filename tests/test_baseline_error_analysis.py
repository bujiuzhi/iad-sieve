"""测试 IAD 强 baseline hard-negative 错误分析。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_baseline_error_analysis
from iad_sieve.evaluation.baseline_error_analysis import build_baseline_error_analysis, write_baseline_error_analysis_outputs
from iad_sieve.utils.io_utils import read_records


def _relation(
    source_id: str,
    target_id: str,
    expected_label: int,
    expected_agenda_label: int,
    hard_negative_level: str,
    score: float,
) -> dict:
    """构造测试关系。

    参数:
        source_id: 源文献 ID。
        target_id: 目标文献 ID。
        expected_label: same_work 标签。
        expected_agenda_label: same_agenda 标签。
        hard_negative_level: hard negative 等级。
        score: baseline 分数。

    返回:
        关系记录。
    """
    return {
        "source_document_id": source_id,
        "target_document_id": target_id,
        "expected_label": expected_label,
        "expected_agenda_label": expected_agenda_label,
        "hard_negative_level": hard_negative_level,
        "label_strength": "proxy" if hard_negative_level != "none" else "gold",
        "relation_label": "agenda_non_identity" if hard_negative_level != "none" else "same_work",
        "baseline_score": score,
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


def test_build_baseline_error_analysis_reports_hard_negative_false_merge_rate() -> None:
    """验证错误分析输出 hard-negative 分层误合并率。"""
    relations = [
        _relation("a", "b", 1, 1, "none", 0.91),
        _relation("c", "d", 0, 1, "high", 0.89),
        _relation("e", "f", 0, 1, "medium", 0.40),
        _relation("g", "h", 0, 0, "none", 0.20),
    ]

    summary_rows, case_rows = build_baseline_error_analysis(
        relations=relations,
        system_name="scincl_cosine",
        score_field="baseline_score",
        thresholds=[0.5],
        baseline_family="representation",
        execution_mode="actual_model",
    )

    summary = summary_rows[0]
    assert summary["system"] == "scincl_cosine"
    assert summary["baseline_family"] == "representation"
    assert summary["execution_mode"] == "actual_model"
    assert summary["hard_negative_pair_count"] == 2
    assert summary["hard_negative_false_merge_count"] == 1
    assert summary["hard_negative_false_merge_rate"] == 0.5
    assert summary["false_positive"] == 1
    assert case_rows[0]["error_type"] == "hard_negative_false_merge"
    assert case_rows[0]["hard_negative_level"] == "high"


def test_write_baseline_error_analysis_outputs_writes_report_files(tmp_path) -> None:
    """验证错误分析输出 JSONL、CSV 和 Markdown。"""
    output_dir = tmp_path / "baseline_error_analysis"
    summary_rows, case_rows = build_baseline_error_analysis(
        relations=[
            _relation("a", "b", 1, 1, "none", 0.91),
            _relation("c", "d", 0, 1, "high", 0.89),
        ],
        system_name="roberta_pair_entity_matcher",
        score_field="baseline_score",
        thresholds=[0.5, 0.9],
        baseline_family="entity_matching",
        execution_mode="actual_model",
    )

    write_baseline_error_analysis_outputs(summary_rows, case_rows, output_dir)

    assert len(read_records(output_dir / "baseline_error_summary.jsonl")) == 2
    assert len(read_records(output_dir / "baseline_error_cases.jsonl")) == 1
    assert "hard_negative_false_merge_rate" in (output_dir / "baseline_error_report.md").read_text(encoding="utf-8")
    assert (output_dir / "baseline_error_summary.csv").exists()


def test_build_baseline_error_analysis_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 baseline 错误分析产物。"""
    relations_path = tmp_path / "relations.jsonl"
    output_dir = tmp_path / "baseline_error_analysis"
    _write_jsonl(
        relations_path,
        [
            _relation("a", "b", 1, 1, "none", 0.91),
            _relation("c", "d", 0, 1, "high", 0.89),
        ],
    )

    command_build_baseline_error_analysis(
        Namespace(
            relations=str(relations_path),
            output_dir=str(output_dir),
            system_name="scincl_cosine",
            score_field="baseline_score",
            thresholds="0.5,0.9",
            baseline_family="representation",
            execution_mode="actual_model",
            limit=None,
        )
    )

    assert read_records(output_dir / "baseline_error_summary.jsonl")[0]["system"] == "scincl_cosine"


def test_cli_includes_build_baseline_error_analysis_command() -> None:
    """验证 CLI 暴露 build-baseline-error-analysis 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-baseline-error-analysis",
            "--relations",
            "outputs/strong_baseline_fixture/scincl_scored_relations.jsonl",
            "--output-dir",
            "outputs/baseline_error_analysis_fixture",
            "--system-name",
            "scincl_cosine",
            "--score-field",
            "scincl_score",
            "--thresholds",
            "0.5,0.8",
            "--baseline-family",
            "representation",
            "--execution-mode",
            "actual_model",
        ]
    )

    assert args.command == "build-baseline-error-analysis"
    assert args.system_name == "scincl_cosine"
    assert args.score_field == "scincl_score"
