"""测试高级模型证据矩阵。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_advanced_model_evidence
from iad_sieve.evaluation.advanced_model_evidence_matrix import (
    build_advanced_model_evidence_rows,
    build_advanced_model_evidence_rows_from_paths,
    write_advanced_model_evidence_outputs,
)
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


def test_build_advanced_model_evidence_rows_marks_actual_missing_and_fallback() -> None:
    """验证矩阵区分 actual_model、fallback 与缺失强模型证据。"""
    baseline_metric_rows = [
        {"system": "scincl_cosine_open_v2", "execution_mode": "actual_model", "f1": 0.29, "false_merge_rate": 0.10, "threshold": 0.9},
        {"system": "llm_fallback_open_v2", "execution_mode": "fallback", "f1": 0.20, "false_merge_rate": 0.30, "threshold": 0.5},
    ]
    execution_summary_rows = [
        {"system": "scincl_cosine_open_v2", "execution_mode": "actual_model", "model_backend": "sentence-transformers"},
        {"system": "llm_fallback_open_v2", "execution_mode": "fallback", "model_backend": "rule"},
    ]
    transformer_summary_rows = [
        {
            "system": "iad_risk_transformer",
            "execution_mode": "actual_model",
            "eval_split": "test",
            "same_work_f1": 0.98,
            "agenda_non_identity_f1": 0.99,
            "false_merge_rate": 0.001,
            "model_backend": "sentence-transformers",
            "embedding_model": "malteos/scincl",
        }
    ]
    bootstrap_rows = [
        {
            "system": "iad_risk_transformer_open_v2",
            "metric_scope": "hard_negative_pairs",
            "hard_negative_false_merge_rate_mean": 0.0,
        },
        {
            "system": "scincl_cosine_open_v2",
            "metric_scope": "hard_negative_pairs",
            "hard_negative_false_merge_rate_mean": 0.79,
        },
    ]
    remote_summary_rows = [{"all_outputs_valid": False, "missing_output_count": 14}]

    rows = build_advanced_model_evidence_rows(
        baseline_metric_rows=baseline_metric_rows,
        execution_summary_rows=execution_summary_rows,
        transformer_summary_rows=transformer_summary_rows,
        bootstrap_rows=bootstrap_rows,
        remote_summary_rows=remote_summary_rows,
        required_systems=["specter2_adapter_cosine_open_v2", "gpt_pair_judge_open_v2"],
    )
    by_system = {row["system"]: row for row in rows}

    assert by_system["iad_risk_transformer_open_v2"]["evidence_status"] == "ready_actual_model"
    assert by_system["iad_risk_transformer_open_v2"]["evaluation_track"] == "open_v2"
    assert by_system["iad_risk_transformer_open_v2"]["advancedness_claim_allowed"] == "limited"
    assert by_system["scincl_cosine_open_v2"]["evidence_status"] == "ready_actual_model"
    assert by_system["scincl_cosine_open_v2"]["evaluation_track"] == "open_v2"
    assert by_system["llm_fallback_open_v2"]["evidence_status"] == "not_counted_fallback"
    assert by_system["specter2_adapter_cosine_open_v2"]["evidence_status"] == "missing_required"
    assert by_system["gpt_pair_judge_open_v2"]["evidence_status"] == "missing_required"
    assert by_system["specter2_adapter_cosine_open_v2"]["reviewer_risk"] == "high"


def test_build_advanced_model_evidence_rows_counts_api_model_as_ready() -> None:
    """验证 LLM API 模型结果可计入强模型证据。"""
    baseline_metric_rows = [
        {"system": "gpt_pair_judge_open_v2", "execution_mode": "api_model", "f1": 0.81, "false_merge_rate": 0.02, "threshold": 0.8}
    ]
    execution_summary_rows = [{"system": "gpt_pair_judge_open_v2", "execution_mode": "api_model", "model_backend": "openai"}]

    rows = build_advanced_model_evidence_rows(
        baseline_metric_rows=baseline_metric_rows,
        execution_summary_rows=execution_summary_rows,
        transformer_summary_rows=[],
        bootstrap_rows=[],
        remote_summary_rows=[],
        required_systems=["gpt_pair_judge_open_v2"],
    )
    summary_dir_rows = {row["system"]: row for row in rows}

    assert summary_dir_rows["gpt_pair_judge_open_v2"]["evidence_status"] == "ready_api_model"
    assert summary_dir_rows["gpt_pair_judge_open_v2"]["advancedness_claim_allowed"] == "limited"
    assert summary_dir_rows["gpt_pair_judge_open_v2"]["missing_reason"] == ""


def test_build_advanced_model_evidence_rows_prefers_source_heldout_test_split_transformer_metric() -> None:
    """验证 source-heldout Transformer summary 优先使用 test split 指标。"""
    transformer_summary_rows = [
        {
            "system": "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout",
            "execution_mode": "actual_model",
            "eval_split": "all",
            "same_work_f1": 0.91,
            "false_merge_rate": 0.07,
            "model_backend": "sentence-transformers",
        },
        {
            "system": "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout",
            "execution_mode": "actual_model",
            "eval_split": "test",
            "same_work_f1": 0.97,
            "false_merge_rate": 0.04,
            "model_backend": "sentence-transformers",
        },
    ]

    rows = build_advanced_model_evidence_rows(
        baseline_metric_rows=[],
        execution_summary_rows=[],
        transformer_summary_rows=transformer_summary_rows,
        bootstrap_rows=[],
        remote_summary_rows=[{"all_outputs_valid": True, "missing_output_count": 0}],
        required_systems=[],
    )
    by_system = {row["system"]: row for row in rows}

    assert by_system["iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout"]["same_work_f1"] == 0.97
    assert by_system["iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout"]["false_merge_rate"] == 0.04


def test_write_advanced_model_evidence_outputs_writes_jsonl_csv_markdown_and_summary(tmp_path) -> None:
    """验证高级模型证据矩阵写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "advanced_model_evidence"
    rows = [
        {
            "system": "specter2_adapter_cosine_open_v2",
            "evidence_id": "required:specter2_adapter_cosine_open_v2",
            "evidence_type": "required_strong_baseline",
            "evidence_status": "missing_required",
            "execution_mode": "",
            "model_backend": "",
            "evaluation_track": "open_v2",
            "threshold": "",
            "same_work_f1": "",
            "false_merge_rate": "",
            "hard_negative_false_merge_rate_mean": "",
            "advancedness_claim_allowed": "no",
            "reviewer_risk": "high",
            "missing_reason": "remote output missing",
            "next_action": "run remote experiment",
        }
    ]

    write_advanced_model_evidence_outputs(rows, output_dir)

    assert read_records(output_dir / "advanced_model_evidence.jsonl")[0]["system"] == "specter2_adapter_cosine_open_v2"
    assert (output_dir / "advanced_model_evidence.csv").exists()
    assert "# Advanced Model Evidence Matrix" in (output_dir / "advanced_model_evidence.md").read_text(encoding="utf-8")
    assert read_records(output_dir / "advanced_model_evidence_track_summary.jsonl")[0]["evaluation_track"] == "open_v2"
    assert (output_dir / "advanced_model_evidence_track_summary.csv").exists()
    summary = read_records(output_dir / "advanced_model_evidence_summary.jsonl")[0]
    assert summary["missing_required_count"] == 1
    assert summary["ready_model_count"] == 0
    assert summary["blocked_evaluation_track_count"] == 1
    assert summary["highest_priority_missing_track"] == "open_v2"


def test_write_advanced_model_evidence_outputs_summarizes_tracks(tmp_path) -> None:
    """验证高级模型证据按 evaluation_track 汇总缺口。"""
    output_dir = tmp_path / "advanced_model_evidence"
    rows = [
        {
            "system": "iad_risk_transformer_open_v2",
            "evidence_id": "transformer:iad_risk_transformer_open_v2",
            "evidence_type": "main_method_transformer",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "model_backend": "sentence-transformers",
            "evaluation_track": "open_v2",
            "threshold": "",
            "same_work_f1": 0.95,
            "false_merge_rate": 0.001,
            "hard_negative_false_merge_rate_mean": 0.0,
            "advancedness_claim_allowed": "limited",
            "reviewer_risk": "medium",
            "missing_reason": "",
            "next_action": "",
        },
        {
            "system": "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
            "evidence_id": "required:iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
            "evidence_type": "required_strong_baseline",
            "evidence_status": "missing_required",
            "execution_mode": "",
            "model_backend": "",
            "evaluation_track": "open_v3_scholarly_balanced_gold",
            "threshold": "",
            "same_work_f1": "",
            "false_merge_rate": "",
            "hard_negative_false_merge_rate_mean": "",
            "advancedness_claim_allowed": "no",
            "reviewer_risk": "high",
            "missing_reason": "remote output missing",
            "next_action": "run remote experiment",
        },
    ]

    write_advanced_model_evidence_outputs(rows, output_dir)

    by_track = {
        row["evaluation_track"]: row
        for row in read_records(output_dir / "advanced_model_evidence_track_summary.jsonl")
    }
    summary = read_records(output_dir / "advanced_model_evidence_summary.jsonl")[0]
    markdown = (output_dir / "advanced_model_evidence.md").read_text(encoding="utf-8")

    assert by_track["open_v2"]["track_status"] == "ready"
    assert by_track["open_v3_scholarly_balanced_gold"]["track_status"] == "blocked"
    assert by_track["open_v3_scholarly_balanced_gold"]["missing_required_count"] == 1
    assert summary["evaluation_track_count"] == 2
    assert summary["blocked_evaluation_track_count"] == 1
    assert summary["highest_priority_missing_track"] == "open_v3_scholarly_balanced_gold"
    assert "## 评估轨道汇总" in markdown
    assert "open_v3_scholarly_balanced_gold" in markdown


def test_write_advanced_model_evidence_outputs_summarizes_missing_families(tmp_path) -> None:
    """验证高级模型 summary 按 PLM 与 LLM 家族拆分缺失强模型。"""
    output_dir = tmp_path / "advanced_model_evidence"
    rows = [
        {
            "system": "roberta_pair_open_v3",
            "evidence_id": "baseline:roberta_pair_open_v3",
            "evidence_type": "pair_classifier",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "evaluation_track": "open_v3",
            "advancedness_claim_allowed": "limited",
        },
        {
            "system": "deberta_pair_open_v3",
            "evidence_id": "baseline:deberta_pair_open_v3",
            "evidence_type": "pair_classifier",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "evaluation_track": "open_v3",
            "advancedness_claim_allowed": "limited",
        },
        {
            "system": "gpt_pair_judge_open_v3",
            "evidence_id": "baseline:gpt_pair_judge_open_v3",
            "evidence_type": "llm_judge",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "evaluation_track": "open_v3",
            "advancedness_claim_allowed": "limited",
        },
        {
            "system": "gpt_pair_judge_open_v2",
            "evidence_id": "required:gpt_pair_judge_open_v2",
            "evidence_type": "required_strong_baseline",
            "evidence_status": "missing_required",
            "execution_mode": "",
            "evaluation_track": "open_v2",
            "advancedness_claim_allowed": "no",
        },
    ]

    write_advanced_model_evidence_outputs(rows, output_dir)

    summary = read_records(output_dir / "advanced_model_evidence_summary.jsonl")[0]
    assert summary["ready_plm_model_count"] == 2
    assert summary["missing_plm_required_count"] == 0
    assert summary["missing_llm_required_count"] == 1
    assert summary["ready_llm_model_count"] == 1


def test_build_advanced_model_evidence_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出高级模型证据矩阵。"""
    metric_summary = tmp_path / "metric_summary.jsonl"
    execution_summary = tmp_path / "execution_summary.jsonl"
    transformer_summary = tmp_path / "iad_risk_transformer_summary.jsonl"
    remote_summary = tmp_path / "remote_output_validation_summary.jsonl"
    bootstrap_csv = tmp_path / "bootstrap.csv"
    output_dir = tmp_path / "advanced_model_evidence"
    _write_jsonl(metric_summary, [{"system": "scincl_cosine_open_v2", "execution_mode": "actual_model", "f1": 0.29, "false_merge_rate": 0.10}])
    _write_jsonl(execution_summary, [{"system": "scincl_cosine_open_v2", "execution_mode": "actual_model"}])
    _write_jsonl(transformer_summary, [{"system": "iad_risk_transformer", "execution_mode": "actual_model", "eval_split": "test", "same_work_f1": 0.98}])
    _write_jsonl(remote_summary, [{"all_outputs_valid": False, "missing_output_count": 14}])
    bootstrap_csv.write_text("system,metric_scope,hard_negative_false_merge_rate_mean\nscincl_cosine_open_v2,hard_negative_pairs,0.79\n", encoding="utf-8")

    command_build_advanced_model_evidence(
        Namespace(
            baseline_metric_summaries=[str(metric_summary)],
            execution_summaries=[str(execution_summary)],
            transformer_summaries=[str(transformer_summary)],
            bootstrap_summaries=[str(bootstrap_csv)],
            remote_output_summaries=[str(remote_summary)],
            required_systems=["specter2_adapter_cosine_open_v2"],
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "advanced_model_evidence.jsonl")
    assert (output_dir / "advanced_model_evidence.md").exists()


def test_build_advanced_model_evidence_from_paths_skips_missing_pending_summaries(tmp_path) -> None:
    """验证缺失的待远程 summary 不阻断高级模型证据矩阵生成。"""
    metric_summary = tmp_path / "metric_summary.jsonl"
    execution_summary = tmp_path / "execution_summary.jsonl"
    remote_summary = tmp_path / "remote_output_validation_summary.jsonl"
    missing_metric_summary = tmp_path / "missing_metric_summary.jsonl"
    missing_transformer_summary = tmp_path / "missing_transformer_summary.jsonl"
    missing_bootstrap_summary = tmp_path / "missing_bootstrap.csv"
    _write_jsonl(metric_summary, [{"system": "scincl_cosine_open_v2", "execution_mode": "actual_model", "f1": 0.29, "false_merge_rate": 0.10}])
    _write_jsonl(execution_summary, [{"system": "scincl_cosine_open_v2", "execution_mode": "actual_model"}])
    _write_jsonl(remote_summary, [{"all_outputs_valid": False, "missing_output_count": 8}])

    rows = build_advanced_model_evidence_rows_from_paths(
        baseline_metric_summary_paths=[metric_summary, missing_metric_summary],
        execution_summary_paths=[execution_summary],
        transformer_summary_paths=[missing_transformer_summary],
        bootstrap_summary_paths=[missing_bootstrap_summary],
        remote_output_summary_paths=[remote_summary],
        required_systems=["scincl_cosine_open_v2", "specter2_adapter_cosine_open_v2"],
    )
    by_system = {row["system"]: row for row in rows}

    assert by_system["scincl_cosine_open_v2"]["evidence_status"] == "ready_actual_model"
    assert by_system["specter2_adapter_cosine_open_v2"]["evidence_status"] == "missing_required"
    assert by_system["specter2_adapter_cosine_open_v2"]["evaluation_track"] == "open_v2"
    assert by_system["specter2_adapter_cosine_open_v2"]["missing_reason"] == "remote output missing"


def test_cli_includes_build_advanced_model_evidence_command() -> None:
    """验证 CLI 暴露 build-advanced-model-evidence 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-advanced-model-evidence",
            "--baseline-metric-summaries",
            "outputs/strong_baseline_open_v2/scincl_metric_summary.jsonl",
            "--execution-summaries",
            "outputs/strong_baseline_open_v2/scincl_execution_summary.jsonl",
            "--transformer-summaries",
            "outputs/iad_risk_transformer_open_v2/iad_risk_transformer_summary.jsonl",
            "--bootstrap-summaries",
            "outputs/iad_bootstrap_open_v2/scincl_bootstrap_confidence.csv",
            "--remote-output-summaries",
            "outputs/remote_output_validation_fixture/remote_output_validation_summary.jsonl",
            "--required-systems",
            "specter2_adapter_cosine_open_v2",
            "gpt_pair_judge_open_v2",
            "--output-dir",
            "outputs/advanced_model_evidence_fixture",
        ]
    )

    assert args.command == "build-advanced-model-evidence"
    assert args.required_systems == ["specter2_adapter_cosine_open_v2", "gpt_pair_judge_open_v2"]
