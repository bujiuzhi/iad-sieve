"""测试模型创新实验蓝图。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_model_innovation_blueprint
from iad_sieve.evaluation.model_innovation_blueprint import (
    build_model_innovation_blueprint_rows,
    build_model_innovation_blueprint_rows_from_paths,
    write_model_innovation_blueprint_outputs,
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
    """构造高级模型证据测试记录。

    参数:
        无。

    返回:
        测试记录列表。
    """
    return [
        {
            "system": "iad_risk_transformer_open_v2",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "advancedness_claim_allowed": "limited",
            "same_work_f1": 0.95,
            "hard_negative_false_merge_rate_mean": 0.0,
        },
        {
            "system": "scincl_cosine_open_v2",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "advancedness_claim_allowed": "limited",
            "same_work_f1": 0.29,
            "hard_negative_false_merge_rate_mean": 0.79,
        },
        {
            "system": "roberta_pair_open_v2",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "advancedness_claim_allowed": "limited",
            "same_work_f1": 0.82,
            "hard_negative_false_merge_rate_mean": 0.0001,
        },
        {
            "system": "distilbert_mrpc_open_v2",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "advancedness_claim_allowed": "limited",
            "same_work_f1": 0.40,
            "hard_negative_false_merge_rate_mean": 0.06,
        },
        {
            "system": "gpt_pair_judge_open_v2",
            "evidence_status": "ready_api_model",
            "execution_mode": "api_model",
            "advancedness_claim_allowed": "limited",
            "same_work_f1": 0.81,
        },
        {
            "system": "specter2_adapter_cosine_open_v2",
            "evidence_status": "missing_required",
            "execution_mode": "",
            "advancedness_claim_allowed": "no",
        },
    ]


def _split_rows() -> list[dict]:
    """构造 split readiness 测试记录。

    参数:
        无。

    返回:
        split readiness 记录。
    """
    return [
        {"dimension_id": "source_held_out_readiness", "audit_status": "defensible"},
        {"dimension_id": "topic_held_out_readiness", "audit_status": "blocked"},
        {"dimension_id": "pair_leakage_guard", "audit_status": "defensible"},
    ]


def test_build_model_innovation_blueprint_rows_marks_ready_blocked_and_deferred_items() -> None:
    """验证蓝图区分已就绪、阻塞和后置增强实验。"""
    rows = build_model_innovation_blueprint_rows(
        advanced_model_evidence_rows=_advanced_rows(),
        q2b_completion_audit_rows=[{"criterion_id": "q2b_final_goal", "status": "blocked"}],
        split_readiness_rows=_split_rows(),
    )
    by_id = {row["blueprint_id"]: row for row in rows}

    assert by_id["main_method_vs_single_space_representation"]["status"] == "ready"
    assert by_id["pair_classifier_strong_baseline_comparison"]["status"] == "ready"
    assert by_id["llm_pair_judge_comparison"]["status"] == "ready"
    assert by_id["specter2_encoder_stability"]["status"] == "blocked"
    assert by_id["open_v3_source_heldout_generalization"]["status"] == "blocked"
    assert by_id["topic_heldout_future_extension"]["status"] == "deferred"
    assert "不能写跨主题泛化" in by_id["open_v3_source_heldout_generalization"]["paper_claim_boundary"]


def test_build_model_innovation_blueprint_rows_merges_split_readiness_sources() -> None:
    """验证多套 split readiness 可把 topic-heldout 从 deferred 推进为 conditional。"""
    rows = build_model_innovation_blueprint_rows(
        advanced_model_evidence_rows=_advanced_rows(),
        q2b_completion_audit_rows=[{"criterion_id": "q2b_final_goal", "status": "blocked"}],
        split_readiness_rows=[
            {"dimension_id": "source_held_out_readiness", "audit_status": "blocked"},
            {"dimension_id": "topic_held_out_readiness", "audit_status": "defensible"},
            {"dimension_id": "source_held_out_readiness", "audit_status": "defensible"},
            {"dimension_id": "topic_held_out_readiness", "audit_status": "blocked"},
        ],
    )
    by_id = {row["blueprint_id"]: row for row in rows}

    assert by_id["topic_heldout_future_extension"]["status"] == "conditional"
    assert "topic_held_out_readiness=defensible" in by_id["topic_heldout_future_extension"]["current_evidence"]


def test_build_model_innovation_blueprint_rows_accepts_scholarly_source_heldout_track() -> None:
    """验证 scholarly source-heldout 三系统完成后泛化蓝图可进入 ready。"""
    source_heldout_rows = [
        {
            "system": "scincl_cosine_open_v3_scholarly_balanced_gold_source_heldout",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "advancedness_claim_allowed": "limited",
        },
        {
            "system": "roberta_pair_open_v3_scholarly_balanced_gold_source_heldout",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "advancedness_claim_allowed": "limited",
        },
        {
            "system": "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "advancedness_claim_allowed": "limited",
        },
    ]

    rows = build_model_innovation_blueprint_rows(
        advanced_model_evidence_rows=_advanced_rows() + source_heldout_rows,
        q2b_completion_audit_rows=[],
        split_readiness_rows=_split_rows(),
    )
    by_id = {row["blueprint_id"]: row for row in rows}

    assert by_id["open_v3_source_heldout_generalization"]["status"] == "ready"
    assert "scholarly_balanced_gold_source_heldout" in by_id["open_v3_source_heldout_generalization"]["current_evidence"]
    assert "open_v3_balanced_gold_source_heldout" not in ";".join(by_id["open_v3_source_heldout_generalization"]["required_systems"])
    assert "应用 source-held-out assignment" not in by_id["open_v3_source_heldout_generalization"]["next_action"]
    assert "source-held-out 模型结果缺失" not in by_id["open_v3_source_heldout_generalization"]["paper_claim_boundary"]


def test_build_model_innovation_blueprint_rows_uses_ready_actions_for_ready_specter2() -> None:
    """验证 SPECTER2 控制已 ready 时不再输出远程执行类行动建议。"""
    ready_specter2_rows = [
        {
            "system": "specter2_adapter_cosine_open_v2",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "advancedness_claim_allowed": "limited",
        },
        {
            "system": "iad_risk_transformer_specter2_open_v2",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "advancedness_claim_allowed": "limited",
        },
    ]

    rows = build_model_innovation_blueprint_rows(
        advanced_model_evidence_rows=_advanced_rows() + ready_specter2_rows,
        q2b_completion_audit_rows=[],
        split_readiness_rows=_split_rows(),
    )
    by_id = {row["blueprint_id"]: row for row in rows}

    assert by_id["specter2_encoder_stability"]["status"] == "ready"
    assert "远程执行 SPECTER2" not in by_id["specter2_encoder_stability"]["next_action"]
    assert "SPECTER2 缺失时" not in by_id["specter2_encoder_stability"]["paper_claim_boundary"]


def test_build_model_innovation_blueprint_rows_uses_ready_actions_for_ready_provenance_blind() -> None:
    """验证 provenance-blind 控制已 ready 时不再输出重训类行动建议。"""
    ready_provenance_rows = [
        {
            "system": "iad_risk_transformer_scincl_provenance_blind_open_v2",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "advancedness_claim_allowed": "limited",
        },
    ]

    rows = build_model_innovation_blueprint_rows(
        advanced_model_evidence_rows=_advanced_rows() + ready_provenance_rows,
        q2b_completion_audit_rows=[],
        split_readiness_rows=_split_rows(),
    )
    by_id = {row["blueprint_id"]: row for row in rows}

    assert by_id["provenance_blind_model_validity"]["status"] == "ready"
    assert "重训 provenance-blind" not in by_id["provenance_blind_model_validity"]["next_action"]
    assert "未 ready 前" not in by_id["provenance_blind_model_validity"]["paper_claim_boundary"]


def test_build_model_innovation_blueprint_prefers_current_source_heldout_track_for_model_gaps() -> None:
    """验证主轨道证据存在时模型缺口映射到当前 source-heldout 轨道。"""
    current_track_rows = [
        {
            "system": "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "advancedness_claim_allowed": "limited",
        },
        {
            "system": "scincl_cosine_open_v3_scholarly_balanced_gold_source_heldout",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "advancedness_claim_allowed": "limited",
        },
        {
            "system": "roberta_pair_open_v3_scholarly_balanced_gold_source_heldout",
            "evidence_status": "ready_actual_model",
            "execution_mode": "actual_model",
            "advancedness_claim_allowed": "limited",
        },
        {
            "system": "deberta_pair_open_v3_scholarly_balanced_gold_source_heldout",
            "evidence_status": "missing_required",
            "execution_mode": "",
            "advancedness_claim_allowed": "no",
        },
        {
            "system": "ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
            "evidence_status": "missing_required",
            "execution_mode": "",
            "advancedness_claim_allowed": "no",
        },
        {
            "system": "specter2_adapter_cosine_open_v3_scholarly_balanced_gold_source_heldout",
            "evidence_status": "missing_required",
            "execution_mode": "",
            "advancedness_claim_allowed": "no",
        },
        {
            "system": "iad_risk_transformer_specter2_open_v3_scholarly_balanced_gold_source_heldout",
            "evidence_status": "missing_required",
            "execution_mode": "",
            "advancedness_claim_allowed": "no",
        },
        {
            "system": "gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout",
            "evidence_status": "missing_required",
            "execution_mode": "",
            "advancedness_claim_allowed": "no",
        },
    ]

    rows = build_model_innovation_blueprint_rows(
        advanced_model_evidence_rows=current_track_rows,
        q2b_completion_audit_rows=[],
        split_readiness_rows=_split_rows(),
    )
    by_id = {row["blueprint_id"]: row for row in rows}

    mechanism_systems = ";".join(by_id["main_method_vs_single_space_representation"]["required_systems"])
    pair_systems = ";".join(by_id["pair_classifier_strong_baseline_comparison"]["required_systems"])
    specter2_systems = ";".join(by_id["specter2_encoder_stability"]["required_systems"])
    llm_systems = ";".join(by_id["llm_pair_judge_comparison"]["required_systems"])

    assert "open_v3_scholarly_balanced_gold_source_heldout" in mechanism_systems
    assert "open_v2" not in mechanism_systems
    assert by_id["main_method_vs_single_space_representation"]["status"] == "ready"
    assert "deberta_pair_open_v3_scholarly_balanced_gold_source_heldout" in pair_systems
    assert "ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout" in pair_systems
    assert by_id["pair_classifier_strong_baseline_comparison"]["status"] == "blocked"
    assert "specter2_adapter_cosine_open_v3_scholarly_balanced_gold_source_heldout" in specter2_systems
    assert "gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout" in llm_systems
    assert "outputs/models/local_llm_judge" in by_id["llm_pair_judge_comparison"]["next_action"]
    assert "execution_mode=actual_model" in by_id["llm_pair_judge_comparison"]["acceptance_evidence"]
    assert "OPENAI_API_KEY" not in by_id["llm_pair_judge_comparison"]["next_action"]


def test_write_model_innovation_blueprint_outputs_writes_files(tmp_path) -> None:
    """验证蓝图写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "model_innovation_blueprint"
    rows = build_model_innovation_blueprint_rows(
        advanced_model_evidence_rows=_advanced_rows(),
        q2b_completion_audit_rows=[],
        split_readiness_rows=_split_rows(),
    )

    write_model_innovation_blueprint_outputs(rows, output_dir)

    assert read_records(output_dir / "model_innovation_blueprint.jsonl")
    assert (output_dir / "model_innovation_blueprint.csv").exists()
    assert "# Model Innovation Blueprint" in (output_dir / "model_innovation_blueprint.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "model_innovation_blueprint_summary.jsonl")[0]
    assert summary["blueprint_count"] == 7
    assert summary["overall_model_innovation_status"] == "blocked"


def test_build_model_innovation_blueprint_from_paths_skips_missing_inputs(tmp_path) -> None:
    """验证缺失输入不阻断蓝图生成。"""
    advanced = tmp_path / "advanced_model_evidence.jsonl"
    split = tmp_path / "open_v3_split_readiness.jsonl"
    missing_completion = tmp_path / "missing_q2b_completion.jsonl"
    _write_jsonl(advanced, _advanced_rows())
    _write_jsonl(split, _split_rows())

    rows = build_model_innovation_blueprint_rows_from_paths(
        advanced_model_evidence_paths=[advanced],
        q2b_completion_audit_paths=[missing_completion],
        split_readiness_paths=[split],
    )

    assert len(rows) == 7


def test_build_model_innovation_blueprint_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出模型创新实验蓝图。"""
    advanced = tmp_path / "advanced_model_evidence.jsonl"
    completion = tmp_path / "q2b_completion_audit.jsonl"
    split = tmp_path / "open_v3_split_readiness.jsonl"
    output_dir = tmp_path / "model_innovation_blueprint"
    _write_jsonl(advanced, _advanced_rows())
    _write_jsonl(completion, [{"criterion_id": "q2b_final_goal", "status": "blocked"}])
    _write_jsonl(split, _split_rows())

    command_build_model_innovation_blueprint(
        Namespace(
            advanced_model_evidence=[str(advanced)],
            q2b_completion_audits=[str(completion)],
            split_readiness_audits=[str(split)],
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "model_innovation_blueprint.jsonl")
    assert (output_dir / "model_innovation_blueprint.md").exists()


def test_cli_includes_build_model_innovation_blueprint_command() -> None:
    """验证 CLI 暴露 build-model-innovation-blueprint 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-model-innovation-blueprint",
            "--advanced-model-evidence",
            "outputs/advanced_model_evidence_fixture/advanced_model_evidence.jsonl",
            "--q2b-completion-audits",
            "outputs/q2b_completion_audit_fixture/q2b_completion_audit.jsonl",
            "--split-readiness-audits",
            "outputs/open_v3_split_readiness_balanced_gold/open_v3_split_readiness.jsonl",
            "--output-dir",
            "outputs/model_innovation_blueprint_fixture",
        ]
    )

    assert args.command == "build-model-innovation-blueprint"
    assert args.advanced_model_evidence == ["outputs/advanced_model_evidence_fixture/advanced_model_evidence.jsonl"]
