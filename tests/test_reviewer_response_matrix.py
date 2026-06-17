"""测试审稿回应矩阵。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_reviewer_response_matrix
from iad_sieve.evaluation.reviewer_response_matrix import (
    build_reviewer_response_rows,
    build_reviewer_response_rows_from_paths,
    write_reviewer_response_outputs,
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


def test_build_reviewer_response_rows_marks_innovation_ready_to_answer() -> None:
    """验证创新问题在主张和深度证据均可辩护时可作为主回应。"""
    reviewer_rows = [
        {
            "concern_id": "innovation_depth",
            "severity": "high",
            "status": "evidence_ready",
            "likely_reviewer_question": "创新是什么？",
            "paper_response": "identity-agenda divergence 风险建模。",
            "rebuttal_strategy": "强调 hard negative 风险控制。",
        }
    ]
    depth_rows = [{"dimension_id": "problem_innovation", "depth_status": "defensible", "reviewer_risk_level": "medium"}]
    manuscript_rows = [
        {
            "claim_id": "identity_agenda_risk_modeling",
            "writing_action": "write_as_main_claim",
            "evidence_strength": "strong",
            "available_evidence": ["iad_ablation"],
        }
    ]
    submission_rows = []

    rows = build_reviewer_response_rows(reviewer_rows, depth_rows, manuscript_rows, submission_rows)

    assert rows[0]["response_status"] == "ready_to_answer"
    assert rows[0]["must_not_claim"] is False
    assert rows[0]["recommended_response_level"] == "main_response"
    assert "iad_ablation" in rows[0]["available_evidence"]


def test_build_reviewer_response_rows_blocks_sota_when_advanced_baseline_missing() -> None:
    """验证强 baseline 缺失时禁止写成 SOTA 或强模型优越回应。"""
    reviewer_rows = [
        {
            "concern_id": "executed_strong_baselines",
            "severity": "high",
            "status": "needs_evidence",
            "likely_reviewer_question": "是否比较了 SPECTER2 和 LLM？",
            "paper_response": "强 baseline 必须 actual_model。",
            "rebuttal_strategy": "缺失时不能夸大。",
        }
    ]
    depth_rows = [
        {
            "dimension_id": "advanced_baseline",
            "depth_status": "not_ready",
            "reviewer_risk_level": "high",
            "missing_evidence": ["specter2_adapter_actual_model", "llm_pair_judge_api_model"],
        }
    ]
    manuscript_rows = [
        {
            "claim_id": "state_of_the_art_superiority",
            "writing_action": "do_not_write",
            "evidence_strength": "blocked",
            "missing_evidence": ["llm_api_model"],
            "blocking_reasons": ["advanced_baseline"],
        }
    ]
    submission_rows = [{"submission_gate_id": "advancedness_gate", "decision": "blocked", "blocking_reasons": ["advanced_baseline"]}]

    rows = build_reviewer_response_rows(reviewer_rows, depth_rows, manuscript_rows, submission_rows)

    assert rows[0]["response_status"] == "do_not_answer_as_claim"
    assert rows[0]["must_not_claim"] is True
    assert rows[0]["recommended_response_level"] == "limitation_only"
    assert "advanced_baseline" in rows[0]["blocking_reasons"]
    assert "llm_api_model" in rows[0]["missing_evidence"]


def test_build_reviewer_response_rows_blocks_duplicate_work_claim_when_prior_art_unresolved() -> None:
    """验证相关工作新颖性审计未闭环时不能把重复工作质疑写成已解决。"""
    reviewer_rows = [
        {
            "concern_id": "duplicate_work",
            "severity": "high",
            "status": "evidence_ready",
            "likely_reviewer_question": "是否只是 SPECTER2 或 Ditto 的重新包装？",
            "paper_response": "强调 IAD 风险建模边界。",
            "rebuttal_strategy": "保留相似工作边界。",
        }
    ]
    depth_rows = [
        {"dimension_id": "problem_innovation", "depth_status": "defensible", "reviewer_risk_level": "medium"},
        {"dimension_id": "advanced_baseline", "depth_status": "defensible", "reviewer_risk_level": "medium"},
    ]
    manuscript_rows = [
        {
            "claim_id": "identity_agenda_risk_modeling",
            "writing_action": "write_as_main_claim",
            "evidence_strength": "strong",
            "available_evidence": ["iad_ablation"],
        },
        {
            "claim_id": "state_of_the_art_superiority",
            "writing_action": "write_with_limits",
            "evidence_strength": "limited",
            "missing_evidence": ["specter2_adapter_actual_model"],
        },
    ]
    submission_rows = []
    prior_art_rows = [
        {
            "prior_art_family_id": "scientific_document_representation",
            "status": "blocked",
            "overlap_risk_level": "high",
            "must_compare_against": ["SPECTER2", "SciNCL"],
            "required_action": "补齐 SPECTER2/SciNCL 同口径比较。",
        }
    ]

    rows = build_reviewer_response_rows(reviewer_rows, depth_rows, manuscript_rows, submission_rows, prior_art_rows)

    assert rows[0]["response_status"] == "do_not_answer_as_claim"
    assert rows[0]["must_not_claim"] is True
    assert "scientific_document_representation" in rows[0]["blocking_reasons"]
    assert "SPECTER2" in rows[0]["missing_evidence"]
    assert "prior_art_novelty_audit" in rows[0]["available_evidence"]
    assert "不得写成没有相似工作" in rows[0]["paper_claim_boundary"]


def test_build_reviewer_response_rows_limits_human_audit_deferral() -> None:
    """验证人工审查暂缓时只能限制性回应，不能写成人工 gold 已有。"""
    reviewer_rows = [
        {
            "concern_id": "human_audit_deferral",
            "severity": "medium",
            "status": "evidence_ready",
            "likely_reviewer_question": "没有人工审查怎么办？",
            "paper_response": "当前按公开分层证据限定。",
            "rebuttal_strategy": "主动降低结论强度。",
        }
    ]
    depth_rows = [{"dimension_id": "data_validity", "depth_status": "conditional", "reviewer_risk_level": "medium"}]
    manuscript_rows = [
        {
            "claim_id": "human_gold_available",
            "writing_action": "do_not_write",
            "evidence_strength": "blocked",
            "missing_evidence": ["human_audit"],
            "blocking_reasons": ["data_validity"],
        },
        {
            "claim_id": "human_audit_future_enhancement",
            "writing_action": "write_with_limits",
            "evidence_strength": "limited",
            "available_evidence": ["human_audit_plan"],
        },
    ]
    submission_rows = []

    rows = build_reviewer_response_rows(reviewer_rows, depth_rows, manuscript_rows, submission_rows)

    assert rows[0]["response_status"] == "limited_answer"
    assert rows[0]["must_not_claim"] is True
    assert rows[0]["recommended_response_level"] == "limited_response"
    assert "human_audit_plan" in rows[0]["available_evidence"]
    assert "human_audit" in rows[0]["missing_evidence"]


def test_build_reviewer_response_rows_from_paths_reads_inputs(tmp_path) -> None:
    """验证审稿回应矩阵可从路径读取输入。"""
    reviewer = tmp_path / "reviewer_audit.jsonl"
    depth = tmp_path / "research_depth_audit.jsonl"
    manuscript = tmp_path / "manuscript_evidence_matrix.jsonl"
    submission = tmp_path / "submission_gate_audit.jsonl"
    prior_art = tmp_path / "prior_art_novelty_audit.jsonl"
    _write_jsonl(reviewer, [{"concern_id": "innovation_depth", "status": "evidence_ready"}])
    _write_jsonl(depth, [{"dimension_id": "problem_innovation", "depth_status": "defensible"}])
    _write_jsonl(manuscript, [{"claim_id": "identity_agenda_risk_modeling", "writing_action": "write_as_main_claim", "evidence_strength": "strong"}])
    _write_jsonl(submission, [])
    _write_jsonl(prior_art, [{"prior_art_family_id": "iad_problem_formulation", "status": "ready"}])

    rows = build_reviewer_response_rows_from_paths([reviewer], [depth], [manuscript], [submission], [prior_art])

    assert rows[0]["concern_id"] == "innovation_depth"
    assert rows[0]["response_status"] == "ready_to_answer"


def test_build_reviewer_response_rows_from_paths_skips_missing_optional_prior_art(tmp_path) -> None:
    """验证可选 prior-art 审计缺失时不阻断审稿回应矩阵重建。"""
    reviewer = tmp_path / "reviewer_audit.jsonl"
    depth = tmp_path / "research_depth_audit.jsonl"
    manuscript = tmp_path / "manuscript_evidence_matrix.jsonl"
    submission = tmp_path / "submission_gate_audit.jsonl"
    missing_prior_art = tmp_path / "missing_prior_art.jsonl"
    _write_jsonl(reviewer, [{"concern_id": "innovation_depth", "status": "evidence_ready"}])
    _write_jsonl(depth, [{"dimension_id": "problem_innovation", "depth_status": "defensible"}])
    _write_jsonl(manuscript, [{"claim_id": "identity_agenda_risk_modeling", "writing_action": "write_as_main_claim", "evidence_strength": "strong"}])
    _write_jsonl(submission, [])

    rows = build_reviewer_response_rows_from_paths([reviewer], [depth], [manuscript], [submission], [missing_prior_art])

    assert rows[0]["concern_id"] == "innovation_depth"
    assert rows[0]["response_status"] == "ready_to_answer"


def test_write_reviewer_response_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证审稿回应矩阵写出 JSONL、CSV、Markdown 和摘要。"""
    rows = [
        {"concern_id": "innovation_depth", "response_status": "ready_to_answer", "must_not_claim": False, "reviewer_risk_level": "medium"},
        {"concern_id": "executed_strong_baselines", "response_status": "do_not_answer_as_claim", "must_not_claim": True, "reviewer_risk_level": "high"},
        {"concern_id": "human_audit_deferral", "response_status": "limited_answer", "must_not_claim": True, "reviewer_risk_level": "medium"},
    ]
    output_dir = tmp_path / "reviewer_response_matrix"

    write_reviewer_response_outputs(rows, output_dir)

    assert read_records(output_dir / "reviewer_response_matrix.jsonl")[0]["concern_id"] == "innovation_depth"
    assert (output_dir / "reviewer_response_matrix.csv").exists()
    assert "# Reviewer Response Matrix" in (output_dir / "reviewer_response_matrix.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "reviewer_response_summary.jsonl")[0]
    assert summary["ready_to_answer_count"] == 1
    assert summary["do_not_answer_as_claim_count"] == 1
    assert summary["limited_answer_count"] == 1
    assert summary["must_not_claim_count"] == 2
    assert summary["unsafe_must_not_claim_count"] == 1
    assert summary["limitation_boundary_count"] == 1


def test_build_reviewer_response_matrix_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出审稿回应矩阵。"""
    reviewer = tmp_path / "reviewer_audit.jsonl"
    depth = tmp_path / "research_depth_audit.jsonl"
    manuscript = tmp_path / "manuscript_evidence_matrix.jsonl"
    submission = tmp_path / "submission_gate_audit.jsonl"
    prior_art = tmp_path / "prior_art_novelty_audit.jsonl"
    output_dir = tmp_path / "reviewer_response_matrix"
    _write_jsonl(reviewer, [{"concern_id": "innovation_depth", "status": "evidence_ready"}])
    _write_jsonl(depth, [{"dimension_id": "problem_innovation", "depth_status": "defensible"}])
    _write_jsonl(manuscript, [{"claim_id": "identity_agenda_risk_modeling", "writing_action": "write_as_main_claim", "evidence_strength": "strong"}])
    _write_jsonl(submission, [])
    _write_jsonl(prior_art, [{"prior_art_family_id": "iad_problem_formulation", "status": "ready"}])

    command_build_reviewer_response_matrix(
        Namespace(
            reviewer_audits=[str(reviewer)],
            research_depth_audits=[str(depth)],
            manuscript_evidence=[str(manuscript)],
            submission_gate_audits=[str(submission)],
            prior_art_audits=[str(prior_art)],
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "reviewer_response_matrix.jsonl").exists()
    assert (output_dir / "reviewer_response_summary.jsonl").exists()


def test_cli_includes_build_reviewer_response_matrix_command() -> None:
    """验证 CLI 暴露 build-reviewer-response-matrix 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-reviewer-response-matrix",
            "--reviewer-audits",
            "outputs/reviewer_audit_fixture/reviewer_audit.jsonl",
            "--research-depth-audits",
            "outputs/research_depth_audit_fixture/research_depth_audit.jsonl",
            "--manuscript-evidence",
            "outputs/manuscript_evidence_matrix_fixture/manuscript_evidence_matrix.jsonl",
            "--submission-gate-audits",
            "outputs/submission_gate_audit_fixture/submission_gate_audit.jsonl",
            "--prior-art-audits",
            "outputs/prior_art_novelty_audit_fixture/prior_art_novelty_audit.jsonl",
            "--output-dir",
            "outputs/reviewer_response_matrix_fixture",
        ]
    )

    assert args.command == "build-reviewer-response-matrix"
    assert args.output_dir == "outputs/reviewer_response_matrix_fixture"
