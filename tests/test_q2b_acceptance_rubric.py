"""测试 Q2/B 接收判定 rubric。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_q2b_acceptance_rubric
from iad_sieve.evaluation.q2b_acceptance_rubric import build_q2b_acceptance_rubric_rows, write_q2b_acceptance_rubric_outputs
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


def test_build_q2b_acceptance_rubric_rows_blocks_missing_remote_and_strong_models() -> None:
    """验证远程输出和强模型缺失时最终 gate 保持 blocked。"""
    rows = build_q2b_acceptance_rubric_rows(
        remote_output_summary={"all_outputs_valid": False, "missing_output_count": 47},
        remote_result_acceptance_summary={"all_claim_gates_accepted": False},
        advanced_model_summary={
            "missing_required_count": 10,
            "ready_model_count": 4,
            "ready_api_model_count": 0,
            "highest_priority_missing_track": "open_v3_scholarly_balanced_gold",
            "blocked_evaluation_track_count": 5,
        },
        model_superiority_summary={"overall_superiority_status": "blocked", "blocked_missing_comparison_count": 10},
        innovation_depth_summary={"q2_b_innovation_claim_allowed": False, "blocked_count": 4, "overall_innovation_depth_status": "blocked"},
        no_annotation_summary={"no_annotation_stage_allowed": True, "blocked_annotation_count": 0, "human_annotation_required_now": False},
        novelty_summary={"q2b_novelty_defensible": False, "blocked_contribution_count": 2, "conditional_contribution_count": 1},
        prior_art_summary={"q2b_prior_art_position_defensible": False, "unresolved_high_risk_family_count": 3, "duplicate_work_found": False},
        q2b_completion_summary={
            "q2_b_goal_ready": False,
            "overall_completion_status": "blocked",
            "blocking_reasons": ["remote_secret_configuration", "remote_result_missing_outputs"],
        },
        reviewer_iteration_summary={"q2_b_ready_from_reviewer_view": False, "critical_count": 3},
    )
    by_id = {row["gate_id"]: row for row in rows}

    assert by_id["remote_reproducibility_acceptance"]["status"] == "blocked"
    assert by_id["strong_model_matrix_acceptance"]["status"] == "blocked"
    assert by_id["no_annotation_strategy_acceptance"]["status"] == "ready"
    assert by_id["novelty_falsification_acceptance"]["status"] == "blocked"
    assert by_id["prior_art_novelty_acceptance"]["status"] == "blocked"
    assert by_id["final_q2b_acceptance"]["status"] == "blocked"
    assert "highest_priority_missing_track=open_v3_scholarly_balanced_gold" in by_id["strong_model_matrix_acceptance"]["current_evidence"]
    assert "不得写强模型实验完成" in by_id["remote_reproducibility_acceptance"]["paper_claim_boundary"]
    assert "outputs/models/local_llm_judge" in by_id["remote_reproducibility_acceptance"]["required_action"]
    assert "OPENAI_API_KEY" not in by_id["remote_reproducibility_acceptance"]["required_action"]
    assert "补齐远程连接" not in by_id["remote_reproducibility_acceptance"]["required_action"]
    assert "不得写完整创新闭环" in by_id["novelty_falsification_acceptance"]["paper_claim_boundary"]
    assert "不得写没有相似工作" in by_id["prior_art_novelty_acceptance"]["paper_claim_boundary"]


def test_build_q2b_acceptance_rubric_rows_accepts_limited_constrained_risk_superiority() -> None:
    """验证风险约束重构后 limited 模型优势可通过模型优势门。"""
    rows = build_q2b_acceptance_rubric_rows(
        remote_output_summary={"all_outputs_valid": True, "missing_output_count": 0},
        remote_result_acceptance_summary={"all_claim_gates_accepted": True},
        advanced_model_summary={
            "missing_required_count": 0,
            "ready_model_count": 4,
            "ready_api_model_count": 1,
            "highest_priority_missing_track": "",
            "blocked_evaluation_track_count": 0,
        },
        model_superiority_summary={
            "overall_superiority_status": "limited",
            "supported_limited_superiority_count": 0,
            "constrained_risk_advantage_count": 2,
            "constrained_risk_not_supported_count": 0,
            "not_supported_count": 2,
            "blocked_missing_comparison_count": 0,
            "sota_claim_allowed": False,
        },
        innovation_depth_summary={"q2_b_innovation_claim_allowed": True, "blocked_count": 0, "overall_innovation_depth_status": "ready"},
        no_annotation_summary={"no_annotation_stage_allowed": True, "blocked_annotation_count": 0, "human_annotation_required_now": False},
        novelty_summary={
            "q2b_novelty_defensible": True,
            "ready_contribution_count": 5,
            "blocked_contribution_count": 0,
            "conditional_contribution_count": 0,
        },
        prior_art_summary={"q2b_prior_art_position_defensible": True, "unresolved_high_risk_family_count": 0, "duplicate_work_found": False},
        q2b_completion_summary={"q2_b_goal_ready": True, "overall_completion_status": "ready"},
        reviewer_iteration_summary={"q2_b_ready_from_reviewer_view": True, "critical_count": 0},
    )
    by_id = {row["gate_id"]: row for row in rows}

    assert by_id["model_superiority_acceptance"]["status"] == "ready"
    assert "constrained_risk_advantage_count=2" in by_id["model_superiority_acceptance"]["current_evidence"]
    assert "全面 SOTA" in by_id["model_superiority_acceptance"]["paper_claim_boundary"]
    assert by_id["final_q2b_acceptance"]["status"] == "ready"


def test_write_q2b_acceptance_rubric_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证 Q2/B rubric 写出 JSONL、CSV、Markdown 和摘要。"""
    rows = [
        {
            "gate_id": "remote_reproducibility_acceptance",
            "gate_name": "远程复现",
            "priority": 0,
            "status": "blocked",
            "reviewer_risk_level": "high",
            "required_threshold": "all_outputs_valid=true",
            "current_evidence": "all_outputs_valid=False",
            "reviewer_failure_mode": "缺远程输出。",
            "required_action": "补齐远程输出。",
            "acceptance_evidence": "全部输出验收。",
            "paper_claim_boundary": "不得写完成。",
        },
        {
            "gate_id": "final_q2b_acceptance",
            "gate_name": "最终判定",
            "priority": 6,
            "status": "blocked",
            "reviewer_risk_level": "high",
            "required_threshold": "全部 ready",
            "current_evidence": "ready_gate_count=0",
            "reviewer_failure_mode": "证据不足。",
            "required_action": "关闭 blocker。",
            "acceptance_evidence": "全部 ready。",
            "paper_claim_boundary": "不得标记完成。",
        },
    ]
    output_dir = tmp_path / "q2b_acceptance_rubric"

    write_q2b_acceptance_rubric_outputs(rows, output_dir)

    assert read_records(output_dir / "q2b_acceptance_rubric.jsonl")[0]["gate_id"] == "remote_reproducibility_acceptance"
    assert (output_dir / "q2b_acceptance_rubric.csv").exists()
    assert "# Q2/B Acceptance Rubric" in (output_dir / "q2b_acceptance_rubric.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "q2b_acceptance_rubric_summary.jsonl")[0]
    assert summary["gate_count"] == 2
    assert summary["blocked_gate_count"] == 2
    assert summary["highest_priority_blocker"] == "remote_reproducibility_acceptance"
    assert summary["q2b_acceptance_ready"] is False


def test_build_q2b_acceptance_rubric_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 Q2/B 接收判定 rubric。"""
    remote_output = tmp_path / "remote_output_validation_summary.jsonl"
    remote_acceptance = tmp_path / "remote_result_acceptance_summary.jsonl"
    advanced_model = tmp_path / "advanced_model_evidence_summary.jsonl"
    model_superiority = tmp_path / "model_superiority_audit_summary.jsonl"
    innovation = tmp_path / "innovation_depth_stress_test_summary.jsonl"
    no_annotation = tmp_path / "no_annotation_protocol_summary.jsonl"
    novelty = tmp_path / "novelty_falsification_matrix_summary.jsonl"
    prior_art = tmp_path / "prior_art_novelty_audit_summary.jsonl"
    completion = tmp_path / "q2b_completion_audit_summary.jsonl"
    reviewer = tmp_path / "reviewer_iteration_audit_summary.jsonl"
    output_dir = tmp_path / "q2b_acceptance_rubric"
    _write_jsonl(remote_output, [{"all_outputs_valid": True, "missing_output_count": 0}])
    _write_jsonl(remote_acceptance, [{"all_claim_gates_accepted": True}])
    _write_jsonl(advanced_model, [{"missing_required_count": 0, "ready_model_count": 4, "ready_api_model_count": 1}])
    _write_jsonl(model_superiority, [{"overall_superiority_status": "ready", "blocked_missing_comparison_count": 0}])
    _write_jsonl(innovation, [{"q2_b_innovation_claim_allowed": True, "blocked_count": 0, "overall_innovation_depth_status": "ready"}])
    _write_jsonl(no_annotation, [{"no_annotation_stage_allowed": True, "blocked_annotation_count": 0, "human_annotation_required_now": False}])
    _write_jsonl(novelty, [{"q2b_novelty_defensible": True, "blocked_contribution_count": 0, "conditional_contribution_count": 0}])
    _write_jsonl(prior_art, [{"q2b_prior_art_position_defensible": True, "unresolved_high_risk_family_count": 0, "duplicate_work_found": False}])
    _write_jsonl(completion, [{"q2_b_goal_ready": True, "overall_completion_status": "ready"}])
    _write_jsonl(reviewer, [{"q2_b_ready_from_reviewer_view": True, "critical_count": 0}])

    command_build_q2b_acceptance_rubric(
        Namespace(
            remote_output_summary=str(remote_output),
            remote_result_acceptance_summary=str(remote_acceptance),
            advanced_model_summary=str(advanced_model),
            model_superiority_summary=str(model_superiority),
            innovation_depth_summary=str(innovation),
            no_annotation_summary=str(no_annotation),
            novelty_summary=str(novelty),
            prior_art_summary=str(prior_art),
            q2b_completion_summary=str(completion),
            reviewer_iteration_summary=str(reviewer),
            output_dir=str(output_dir),
        )
    )

    summary = read_records(output_dir / "q2b_acceptance_rubric_summary.jsonl")[0]
    assert summary["q2b_acceptance_ready"] is True
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-q2b-acceptance-rubric",
            "--remote-output-summary",
            str(remote_output),
            "--remote-result-acceptance-summary",
            str(remote_acceptance),
            "--advanced-model-summary",
            str(advanced_model),
            "--model-superiority-summary",
            str(model_superiority),
            "--innovation-depth-summary",
            str(innovation),
            "--no-annotation-summary",
            str(no_annotation),
            "--novelty-summary",
            str(novelty),
            "--prior-art-summary",
            str(prior_art),
            "--q2b-completion-summary",
            str(completion),
            "--reviewer-iteration-summary",
            str(reviewer),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_q2b_acceptance_rubric
