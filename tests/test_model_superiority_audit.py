"""测试模型优势审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_model_superiority_audit
from iad_sieve.evaluation.model_superiority_audit import (
    build_model_superiority_audit_rows,
    build_model_superiority_audit_rows_from_paths,
    write_model_superiority_audit_outputs,
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


def _advanced_rows() -> list[dict]:
    """构造模型证据测试记录。

    参数:
        无。

    返回:
        advanced_model_evidence 记录。
    """
    return [
        {
            "system": "iad_risk_transformer_open_v2",
            "evidence_type": "main_method_transformer",
            "evidence_status": "ready_actual_model",
            "evaluation_track": "open_v2",
            "same_work_f1": 0.955789,
            "false_merge_rate": 0.001375,
            "hard_negative_false_merge_rate_mean": 0.0,
        },
        {
            "system": "scincl_cosine_open_v2",
            "evidence_type": "representation",
            "evidence_status": "ready_actual_model",
            "evaluation_track": "open_v2",
            "same_work_f1": 0.293402,
            "false_merge_rate": 0.108111,
            "hard_negative_false_merge_rate_mean": 0.790663,
        },
        {
            "system": "distilbert_mrpc_open_v2",
            "evidence_type": "entity_matching",
            "evidence_status": "ready_actual_model",
            "evaluation_track": "open_v2",
            "same_work_f1": 0.40613,
            "false_merge_rate": 0.018166,
            "hard_negative_false_merge_rate_mean": 0.061683,
        },
        {
            "system": "roberta_pair_open_v2",
            "evidence_type": "entity_matching",
            "evidence_status": "ready_actual_model",
            "evaluation_track": "open_v2",
            "same_work_f1": 0.824691,
            "false_merge_rate": 0.000687,
            "hard_negative_false_merge_rate_mean": 0.000103,
        },
        {
            "system": "specter2_adapter_cosine_open_v2",
            "evidence_type": "required_strong_baseline",
            "evidence_status": "missing_required",
            "evaluation_track": "open_v2",
            "next_action": "运行 SPECTER2 adapter。",
        },
        {
            "system": "scincl_cosine_open_v3_balanced_gold",
            "evidence_type": "required_strong_baseline",
            "evidence_status": "missing_required",
            "evaluation_track": "open_v3_balanced_gold",
        },
    ]


def test_build_model_superiority_audit_rows_marks_supported_mixed_and_missing() -> None:
    """验证优势审计区分受限优势、混合优势和缺失强模型。"""
    rows = build_model_superiority_audit_rows(
        advanced_model_evidence_rows=_advanced_rows(),
        model_innovation_blueprint_rows=[],
    )
    by_baseline = {row["baseline_system"]: row for row in rows}

    assert by_baseline["scincl_cosine_open_v2"]["status"] == "supports_limited_superiority"
    assert by_baseline["distilbert_mrpc_open_v2"]["status"] == "supports_limited_superiority"
    assert by_baseline["roberta_pair_open_v2"]["status"] == "mixed_targeted_advantage"
    assert by_baseline["roberta_pair_open_v2"]["false_merge_rate_reduction"] < 0
    assert by_baseline["specter2_adapter_cosine_open_v2"]["status"] == "blocked_missing_baseline"
    assert "scincl_cosine_open_v3_balanced_gold" not in by_baseline
    assert "不得写成全面优于强模型" in by_baseline["specter2_adapter_cosine_open_v2"]["paper_claim_boundary"]
    assert by_baseline["scincl_cosine_open_v2"]["evaluation_track"] == "open_v2"


def test_build_model_superiority_audit_rows_keeps_comparisons_inside_main_track() -> None:
    """验证模型优势审计不跨数据轨道混合比较。"""
    rows = build_model_superiority_audit_rows(
        advanced_model_evidence_rows=[
            {
                "system": "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
                "evidence_type": "main_method_transformer",
                "evidence_status": "ready_actual_model",
                "evaluation_track": "open_v3_scholarly_balanced_gold",
                "same_work_f1": 0.9,
                "false_merge_rate": 0.01,
                "hard_negative_false_merge_rate_mean": 0.0,
            },
            {
                "system": "roberta_pair_open_v3_scholarly_balanced_gold",
                "evidence_type": "pair_classifier",
                "evidence_status": "ready_actual_model",
                "evaluation_track": "open_v3_scholarly_balanced_gold",
                "same_work_f1": 0.8,
                "false_merge_rate": 0.02,
                "hard_negative_false_merge_rate_mean": 0.1,
            },
            {
                "system": "roberta_pair_open_v2",
                "evidence_type": "pair_classifier",
                "evidence_status": "ready_actual_model",
                "evaluation_track": "open_v2",
                "same_work_f1": 0.95,
                "false_merge_rate": 0.001,
                "hard_negative_false_merge_rate_mean": 0.001,
            },
            {
                "system": "scincl_cosine_open_v3_balanced_gold",
                "evidence_type": "required_strong_baseline",
                "evidence_status": "missing_required",
                "evaluation_track": "open_v3_balanced_gold",
            },
        ],
        model_innovation_blueprint_rows=[],
        main_system="iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
    )
    by_baseline = {row["baseline_system"]: row for row in rows}

    assert "roberta_pair_open_v3_scholarly_balanced_gold" in by_baseline
    assert "roberta_pair_open_v2" not in by_baseline
    assert "scincl_cosine_open_v3_balanced_gold" not in by_baseline
    assert by_baseline["roberta_pair_open_v3_scholarly_balanced_gold"]["evaluation_track"] == "open_v3_scholarly_balanced_gold"


def test_build_model_superiority_audit_rows_filters_ready_control_actions() -> None:
    """验证优势审计不要求补齐已经 ready 的控制实验。"""
    rows = build_model_superiority_audit_rows(
        advanced_model_evidence_rows=[
            {
                "system": "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout",
                "evidence_type": "main_method_transformer",
                "evidence_status": "ready_actual_model",
                "evaluation_track": "open_v3_scholarly_balanced_gold_source_heldout",
                "same_work_f1": 0.70,
                "false_merge_rate": 0.03,
                "hard_negative_false_merge_rate_mean": "",
            },
            {
                "system": "roberta_pair_open_v3_scholarly_balanced_gold_source_heldout",
                "evidence_type": "pair_classifier",
                "evidence_status": "ready_actual_model",
                "evaluation_track": "open_v3_scholarly_balanced_gold_source_heldout",
                "same_work_f1": 0.85,
                "false_merge_rate": 0.02,
                "hard_negative_false_merge_rate_mean": "",
            },
        ],
        model_innovation_blueprint_rows=[
            {"blueprint_id": "specter2_encoder_stability", "status": "ready"},
            {"blueprint_id": "provenance_blind_model_validity", "status": "ready"},
            {"blueprint_id": "open_v3_source_heldout_generalization", "status": "ready"},
            {"blueprint_id": "llm_pair_judge_comparison", "status": "blocked"},
        ],
        main_system="iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout",
    )
    by_baseline = {row["baseline_system"]: row for row in rows}
    row = by_baseline["roberta_pair_open_v3_scholarly_balanced_gold_source_heldout"]

    assert row["status"] == "not_supported"
    assert "SPECTER2" not in row["next_action"]
    assert "provenance-blind" not in row["next_action"]
    assert "source-held-out 结果" not in row["next_action"]
    assert "LLM" in row["next_action"] or "GPT" in row["next_action"]
    assert "SPECTER2" not in row["reviewer_counterargument"]
    assert "provenance-blind" not in row["reviewer_counterargument"]
    assert "source-held-out" not in row["reviewer_counterargument"]
    assert "LLM" in row["reviewer_counterargument"] or "GPT" in row["reviewer_counterargument"]
    assert "需要补充 GPT/LLM judge 证据" in row["reviewer_counterargument"]


def test_build_model_superiority_audit_rows_blocks_when_main_method_missing() -> None:
    """验证主方法缺失时优势审计直接阻塞。"""
    rows = build_model_superiority_audit_rows(
        advanced_model_evidence_rows=[{"system": "scincl_cosine_open_v2", "evidence_status": "ready_actual_model"}],
        model_innovation_blueprint_rows=[],
    )

    assert rows[0]["status"] == "blocked_missing_main_method"
    assert rows[0]["baseline_system"] == "iad_risk_transformer_open_v2"


def test_write_model_superiority_audit_outputs_writes_files(tmp_path) -> None:
    """验证优势审计写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "model_superiority_audit"
    rows = build_model_superiority_audit_rows(_advanced_rows(), [])

    write_model_superiority_audit_outputs(rows, output_dir)

    assert read_records(output_dir / "model_superiority_audit.jsonl")
    assert (output_dir / "model_superiority_audit.csv").exists()
    assert "# Model Superiority Audit" in (output_dir / "model_superiority_audit.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "model_superiority_audit_summary.jsonl")[0]
    assert summary["supported_limited_superiority_count"] == 2
    assert summary["mixed_targeted_advantage_count"] == 1
    assert summary["blocked_missing_comparison_count"] == 1
    assert summary["sota_claim_allowed"] is False


def test_model_superiority_summary_does_not_mark_all_failed_comparisons_as_supported(tmp_path) -> None:
    """验证全部比较失败时 summary 不会误报 supported_limited。"""
    output_dir = tmp_path / "model_superiority_audit"
    rows = build_model_superiority_audit_rows(
        advanced_model_evidence_rows=[
            {
                "system": "iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout_extra_train_calibrated_fmr10",
                "evidence_type": "main_method_transformer",
                "evidence_status": "ready_actual_model",
                "evaluation_track": "open_v3_balanced_gold_source_heldout",
                "same_work_f1": 0.60,
                "false_merge_rate": 0.09,
                "hard_negative_false_merge_rate_mean": "",
            },
            {
                "system": "roberta_pair_open_v3_balanced_gold_source_heldout",
                "evidence_type": "pair_classifier",
                "evidence_status": "ready_actual_model",
                "evaluation_track": "open_v3_balanced_gold_source_heldout",
                "same_work_f1": 0.66,
                "false_merge_rate": 0.42,
                "hard_negative_false_merge_rate_mean": "",
            },
        ],
        model_innovation_blueprint_rows=[],
        main_system="iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout_extra_train_calibrated_fmr10",
    )

    write_model_superiority_audit_outputs(rows, output_dir)

    summary = read_records(output_dir / "model_superiority_audit_summary.jsonl")[0]
    assert rows[0]["status"] == "not_supported"
    assert summary["not_supported_count"] == 1
    assert summary["overall_superiority_status"] == "not_supported"


def test_build_model_superiority_audit_from_paths_skips_missing_inputs(tmp_path) -> None:
    """验证缺失输入不阻断优势审计生成。"""
    advanced = tmp_path / "advanced_model_evidence.jsonl"
    missing_blueprint = tmp_path / "missing_blueprint.jsonl"
    _write_jsonl(advanced, _advanced_rows())

    rows = build_model_superiority_audit_rows_from_paths(
        advanced_model_evidence_paths=[advanced],
        model_innovation_blueprint_paths=[missing_blueprint],
    )

    assert rows


def test_build_model_superiority_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出模型优势审计。"""
    advanced = tmp_path / "advanced_model_evidence.jsonl"
    blueprint = tmp_path / "model_innovation_blueprint.jsonl"
    output_dir = tmp_path / "model_superiority_audit"
    _write_jsonl(advanced, _advanced_rows())
    _write_jsonl(blueprint, [{"blueprint_id": "specter2_encoder_stability", "status": "blocked", "required_systems": ["specter2_adapter_cosine_open_v2"]}])

    command_build_model_superiority_audit(
        Namespace(
            advanced_model_evidence=[str(advanced)],
            model_innovation_blueprints=[str(blueprint)],
            main_system="iad_risk_transformer_open_v2",
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "model_superiority_audit.jsonl")
    assert (output_dir / "model_superiority_audit.md").exists()


def test_cli_includes_build_model_superiority_audit_command() -> None:
    """验证 CLI 暴露 build-model-superiority-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-model-superiority-audit",
            "--advanced-model-evidence",
            "outputs/advanced_model_evidence_fixture/advanced_model_evidence.jsonl",
            "--model-innovation-blueprints",
            "outputs/model_innovation_blueprint_fixture/model_innovation_blueprint.jsonl",
            "--main-system",
            "iad_risk_transformer_open_v2",
            "--output-dir",
            "outputs/model_superiority_audit_fixture",
        ]
    )

    assert args.command == "build-model-superiority-audit"
    assert args.main_system == "iad_risk_transformer_open_v2"
