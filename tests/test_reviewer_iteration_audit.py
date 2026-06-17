"""测试审稿人迭代审核。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_reviewer_iteration_audit
from iad_sieve.evaluation.reviewer_iteration_audit import build_reviewer_iteration_audit_rows, write_reviewer_iteration_audit_outputs
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


def test_build_reviewer_iteration_audit_rows_flags_major_review_risks() -> None:
    """验证审稿迭代审核能识别主要审稿风险。"""
    roadmap_rows = [
        {
            "phase_id": "p0_remote_connection_and_secret",
            "status": "blocked",
            "current_blockers": ["remote_connection_profile"],
            "required_actions": "补齐远程连接。",
            "acceptance_evidence": "all_remote_run_inputs_ready=true。",
            "paper_claim_boundary": "远程输出未验收前不能写强模型完成。",
        },
        {
            "phase_id": "p3_model_superiority_and_innovation",
            "status": "blocked",
            "current_blockers": ["missing_strong_comparison"],
            "required_actions": "补齐强 baseline。",
        },
        {
            "phase_id": "p4_claim_and_submission_lockdown",
            "status": "blocked",
            "current_blockers": ["must_not_claim"],
        },
    ]
    completion_rows = [
        {
            "criterion_id": "remote_execution_readiness",
            "status": "blocked",
            "blocking_reasons": ["remote_connection_profile"],
        },
        {
            "criterion_id": "iad_risk_split_evaluation_readiness",
            "status": "conditional",
            "blocking_reasons": ["stratified_blend_diagnostic_only"],
        },
        {
            "criterion_id": "q2b_final_goal",
            "status": "blocked",
            "blocking_reasons": ["q2_b_ready"],
        },
    ]
    model_superiority_rows = [
        {
            "comparison_id": "missing:specter2",
            "status": "not_supported",
            "support_summary": "SPECTER2 missing。",
            "blocking_reasons": ["missing_strong_comparison"],
        }
    ]
    innovation_rows = [
        {
            "stress_id": "strong_baseline_depth",
            "status": "blocked",
            "innovation_dimension": "strong_baseline_comparison",
            "blocking_reasons": ["missing_strong_comparison"],
        }
    ]
    public_data_rows = [
        {
            "dimension_id": "silver_topic_concentration",
            "audit_status": "high_risk",
            "top_silver_topic_ratio": 1.0,
        }
    ]
    feature_guard_rows = [
        {
            "model_path": "model.json",
            "audit_status": "high_risk",
            "violation_count": 2,
            "paper_claim_boundary": "不得声称 provenance-blind。",
        }
    ]
    reviewer_response_rows = [
        {
            "concern_id": "baseline_strength",
            "response_status": "do_not_answer_as_claim",
            "must_not_claim": True,
            "missing_evidence": ["specter2_adapter_actual_model"],
        }
    ]

    rows = build_reviewer_iteration_audit_rows(
        roadmap_rows=roadmap_rows,
        completion_rows=completion_rows,
        model_superiority_rows=model_superiority_rows,
        innovation_depth_rows=innovation_rows,
        public_data_rows=public_data_rows,
        feature_guard_rows=feature_guard_rows,
        reviewer_response_rows=reviewer_response_rows,
    )
    by_id = {row["iteration_id"]: row for row in rows}

    assert len(rows) == 7
    assert by_id["r0_remote_reproducibility"]["status"] == "major_revision_required"
    assert by_id["r1_strong_baseline_and_sota"]["status"] == "major_revision_required"
    assert by_id["r3_model_depth_and_leakage"]["status"] == "major_revision_required"
    assert by_id["r4_data_validity_and_gold_boundary"]["status"] == "major_revision_required"
    assert by_id["r5_generalization_and_split"]["status"] == "minor_revision_required"
    assert by_id["r6_claim_safety_and_submission"]["severity"] == "critical"
    assert "不能写" in by_id["r0_remote_reproducibility"]["paper_claim_boundary"]


def test_build_reviewer_iteration_audit_rows_clears_ready_generalization_actions() -> None:
    """验证泛化证据 defensible 时不保留旧补实验动作。"""
    roadmap_rows = [
        {
            "phase_id": "p2_source_heldout_and_leakage",
            "status": "ready",
            "current_blockers": [],
            "required_actions": "在论文中分开报告 random、source-held-out、topic-held-out 和 leakage guard，并保留 limited source-heldout 边界。",
            "acceptance_evidence": "source_heldout_full_iad_ready=true。",
        }
    ]
    completion_rows = [
        {
            "criterion_id": "iad_risk_split_evaluation_readiness",
            "status": "ready",
            "blocking_reasons": [],
            "next_action": "执行真正 source-held-out 的强模型/IAD-Risk Transformer 实验，并重建 split 评估审计。",
            "acceptance_evidence": "source_heldout_full_iad_ready=true 且 limited_source_heldout_count>0。",
        }
    ]

    rows = build_reviewer_iteration_audit_rows(roadmap_rows=roadmap_rows, completion_rows=completion_rows)
    by_id = {row["iteration_id"]: row for row in rows}
    generalization_row = by_id["r5_generalization_and_split"]

    assert generalization_row["status"] == "defensible"
    assert generalization_row["blocking_reasons"] == []
    assert "执行真正 source-held-out" not in generalization_row["optimization_actions"]
    assert "保留 limited source-heldout 边界" in generalization_row["optimization_actions"]


def test_build_reviewer_iteration_audit_rows_accepts_limited_superiority_and_no_annotation_boundaries() -> None:
    """验证受限优势和 no-annotation 边界闭环时审稿视角可 ready。"""
    roadmap_rows = [
        {"phase_id": "p0_remote_connection_and_secret", "status": "ready"},
        {"phase_id": "p1_strong_model_remote_execution", "status": "ready"},
        {"phase_id": "p2_source_heldout_and_leakage", "status": "ready"},
        {"phase_id": "p3_model_superiority_and_innovation", "status": "ready"},
        {"phase_id": "p4_claim_and_submission_lockdown", "status": "ready"},
    ]
    completion_rows = [
        {"criterion_id": "remote_execution_readiness", "status": "ready"},
        {"criterion_id": "remote_result_acceptance_closure", "status": "ready"},
        {"criterion_id": "advanced_model_closure", "status": "ready"},
        {"criterion_id": "innovation_depth_closure", "status": "ready"},
        {"criterion_id": "reviewer_response_safety", "status": "ready"},
        {"criterion_id": "final_submission_gate", "status": "ready"},
        {"criterion_id": "q2b_final_goal", "status": "ready"},
        {"criterion_id": "generalization_split_readiness", "status": "ready"},
        {"criterion_id": "iad_risk_split_evaluation_readiness", "status": "ready"},
        {"criterion_id": "model_training_input_readiness", "status": "ready"},
    ]
    model_superiority_rows = [
        {"comparison_id": "constrained:main_vs_roberta", "status": "supports_constrained_risk_advantage"},
        {"comparison_id": "main_vs_deberta", "status": "not_supported"},
    ]
    public_data_rows = [
        {"dimension_id": "silver_topic_concentration", "audit_status": "high_risk", "paper_claim_boundary": "仅作为限制。"},
        {"dimension_id": "human_audit_absence", "audit_status": "deferred_enhancement", "paper_claim_boundary": "人工 gold 作为后续增强。"},
    ]
    reviewer_response_rows = [
        {"concern_id": "baseline_strength", "response_status": "ready_to_answer", "must_not_claim": False},
        {"concern_id": "duplicate_work", "response_status": "ready_to_answer", "must_not_claim": False},
        {"concern_id": "weak_label_noise", "response_status": "limited_answer", "must_not_claim": True},
        {"concern_id": "label_provenance", "response_status": "limited_answer", "must_not_claim": False},
        {"concern_id": "human_audit_deferral", "response_status": "limited_answer", "must_not_claim": True},
    ]

    rows = build_reviewer_iteration_audit_rows(
        roadmap_rows=roadmap_rows,
        completion_rows=completion_rows,
        model_superiority_rows=model_superiority_rows,
        public_data_rows=public_data_rows,
        reviewer_response_rows=reviewer_response_rows,
    )
    by_id = {row["iteration_id"]: row for row in rows}

    assert by_id["r1_strong_baseline_and_sota"]["status"] == "defensible"
    assert by_id["r4_data_validity_and_gold_boundary"]["status"] == "defensible"
    assert by_id["r6_claim_safety_and_submission"]["status"] == "defensible"
    assert all(row["status"] == "defensible" for row in rows)


def test_write_reviewer_iteration_audit_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证审稿迭代审核写出 JSONL、CSV、Markdown 和摘要。"""
    rows = [
        {
            "iteration_id": "r0_remote_reproducibility",
            "review_dimension": "远程可复现性",
            "severity": "critical",
            "status": "major_revision_required",
            "reviewer_critique": "远程未闭环。",
            "evidence_snapshot": "status=blocked",
            "blocking_reasons": ["remote_connection_profile"],
            "optimization_actions": "补齐远程连接。",
            "acceptance_evidence": "all_remote_run_inputs_ready=true。",
            "paper_claim_boundary": "不能写强模型完成。",
            "source_phase_ids": ["p0_remote_connection_and_secret"],
            "source_criterion_ids": ["remote_execution_readiness"],
            "source_evidence_ids": [],
        }
    ]
    output_dir = tmp_path / "reviewer_iteration_audit"

    write_reviewer_iteration_audit_outputs(rows, output_dir)

    assert read_records(output_dir / "reviewer_iteration_audit.jsonl")[0]["iteration_id"] == "r0_remote_reproducibility"
    assert (output_dir / "reviewer_iteration_audit.csv").exists()
    assert "# Reviewer Iteration Audit" in (output_dir / "reviewer_iteration_audit.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "reviewer_iteration_audit_summary.jsonl")[0]
    assert summary["review_item_count"] == 1
    assert summary["critical_count"] == 1
    assert summary["major_revision_required_count"] == 1
    assert summary["q2_b_ready_from_reviewer_view"] is False
    assert summary["highest_risk_iteration_id"] == "r0_remote_reproducibility"


def test_build_reviewer_iteration_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出审稿人迭代审核。"""
    roadmap = tmp_path / "q2b_upgrade_roadmap.jsonl"
    completion = tmp_path / "q2b_completion_audit.jsonl"
    output_dir = tmp_path / "reviewer_iteration_audit"
    _write_jsonl(roadmap, [{"phase_id": "p0_remote_connection_and_secret", "status": "blocked"}])
    _write_jsonl(completion, [{"criterion_id": "remote_execution_readiness", "status": "blocked"}])

    command_build_reviewer_iteration_audit(
        Namespace(
            q2b_roadmap=str(roadmap),
            q2b_completion_audit=str(completion),
            model_superiority_audit=None,
            innovation_depth=None,
            public_data_validity=None,
            feature_guard=None,
            reviewer_response=None,
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "reviewer_iteration_audit_summary.jsonl").exists()
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-reviewer-iteration-audit",
            "--q2b-roadmap",
            str(roadmap),
            "--q2b-completion-audit",
            str(completion),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_reviewer_iteration_audit
