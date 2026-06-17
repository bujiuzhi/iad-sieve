"""测试研究深度审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_research_depth_audit
from iad_sieve.evaluation.research_depth_audit import build_research_depth_audit_rows, write_research_depth_audit_outputs
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


def test_build_research_depth_audit_rows_marks_problem_innovation_defensible() -> None:
    """验证机制主张和创新审稿项同时 ready 时创新问题可辩护。"""
    reviewer_rows = [{"concern_id": "innovation_depth", "status": "evidence_ready"}]
    claim_rows = [{"claim_id": "identity_agenda_risk_modeling", "claim_status": "supported"}]
    readiness_rows = []
    dependency_rows = []

    rows = build_research_depth_audit_rows(reviewer_rows, claim_rows, readiness_rows, dependency_rows)
    by_dimension = {row["dimension_id"]: row for row in rows}

    assert by_dimension["problem_innovation"]["depth_status"] == "defensible"
    assert by_dimension["problem_innovation"]["reviewer_risk_level"] == "medium"
    assert "identity-agenda" in by_dimension["problem_innovation"]["defensible_position"]


def test_build_research_depth_audit_rows_marks_advanced_baseline_not_ready() -> None:
    """验证 SOTA 主张禁止且强 baseline gate 缺失时先进性不足。"""
    reviewer_rows = [{"concern_id": "executed_strong_baselines", "status": "needs_evidence"}]
    claim_rows = [{"claim_id": "state_of_the_art_superiority", "claim_status": "forbidden"}]
    readiness_rows = [
        {"gate_id": "specter2_adapter_actual_model", "status": "needs_evidence"},
        {"gate_id": "llm_pair_judge_api_model", "status": "needs_evidence"},
    ]
    dependency_rows = [{"root_blocker_statuses": ["blocked_remote_required", "blocked_missing_secret"]}]

    rows = build_research_depth_audit_rows(reviewer_rows, claim_rows, readiness_rows, dependency_rows)
    by_dimension = {row["dimension_id"]: row for row in rows}

    assert by_dimension["advanced_baseline"]["depth_status"] == "not_ready"
    assert by_dimension["advanced_baseline"]["reviewer_risk_level"] == "high"
    assert "SPECTER2 adapter" in by_dimension["advanced_baseline"]["next_optimization"]
    assert "blocked_missing_secret" in by_dimension["advanced_baseline"]["blocking_reasons"]


def test_build_research_depth_audit_rows_does_not_reask_completed_specter2_baseline() -> None:
    """验证 SPECTER2 已完成时先进性下一步不再要求补跑 SPECTER2。"""
    reviewer_rows = [{"concern_id": "executed_strong_baselines", "status": "needs_evidence"}]
    claim_rows = [{"claim_id": "state_of_the_art_superiority", "claim_status": "forbidden"}]
    readiness_rows = [
        {"gate_id": "specter2_adapter_actual_model", "status": "evidence_ready"},
        {"gate_id": "llm_pair_judge_api_model", "status": "needs_evidence"},
    ]
    dependency_rows = [{"root_blocker_statuses": ["blocked_missing_secret"]}]

    rows = build_research_depth_audit_rows(reviewer_rows, claim_rows, readiness_rows, dependency_rows)
    by_dimension = {row["dimension_id"]: row for row in rows}

    assert "specter2_adapter_actual_model" in by_dimension["advanced_baseline"]["available_evidence"]
    assert "SPECTER2 adapter actual_model" not in by_dimension["advanced_baseline"]["next_optimization"]
    assert "LLM API baseline" in by_dimension["advanced_baseline"]["next_optimization"]


def test_build_research_depth_audit_rows_marks_model_depth_conditional_until_encoder_validation() -> None:
    """验证模型深度已有证据但 SPECTER2 复核未完成时仍为 conditional。"""
    reviewer_rows = [{"concern_id": "model_depth", "status": "evidence_ready"}]
    claim_rows = []
    readiness_rows = [{"gate_id": "specter2_adapter_actual_model", "status": "needs_evidence"}]
    dependency_rows = [{"task_id": "run_specter2_adapter_iad_risk_transformer_open_v2", "root_blocker_statuses": ["blocked_remote_required"]}]

    rows = build_research_depth_audit_rows(reviewer_rows, claim_rows, readiness_rows, dependency_rows)
    by_dimension = {row["dimension_id"]: row for row in rows}

    assert by_dimension["model_depth"]["depth_status"] == "conditional"
    assert by_dimension["model_depth"]["reviewer_risk_level"] == "medium"
    assert "SPECTER2" in by_dimension["model_depth"]["next_optimization"]


def test_build_research_depth_audit_rows_does_not_reask_completed_encoder_validation() -> None:
    """验证模型深度已通过 SPECTER2 复核时不再要求重跑 SPECTER2。"""
    reviewer_rows = [{"concern_id": "model_depth", "status": "evidence_ready"}]
    claim_rows = []
    readiness_rows = [{"gate_id": "specter2_adapter_actual_model", "status": "evidence_ready"}]
    dependency_rows = []

    rows = build_research_depth_audit_rows(reviewer_rows, claim_rows, readiness_rows, dependency_rows)
    by_dimension = {row["dimension_id"]: row for row in rows}

    assert by_dimension["model_depth"]["depth_status"] == "defensible"
    assert "SPECTER2 adapter 重跑" not in by_dimension["model_depth"]["next_optimization"]
    assert "失败案例" in by_dimension["model_depth"]["next_optimization"]


def test_build_research_depth_audit_rows_marks_data_validity_conditional_without_human_gold() -> None:
    """验证只有人工计划时数据可信度为 conditional，不是 fully defensible。"""
    reviewer_rows = [{"concern_id": "weak_label_noise", "status": "evidence_ready"}]
    claim_rows = [
        {"claim_id": "human_gold_available", "claim_status": "forbidden"},
        {"claim_id": "human_audit_future_enhancement", "claim_status": "supported"},
    ]
    readiness_rows = [{"gate_id": "human_audit_plan", "status": "evidence_ready"}]
    dependency_rows = []

    rows = build_research_depth_audit_rows(reviewer_rows, claim_rows, readiness_rows, dependency_rows)
    by_dimension = {row["dimension_id"]: row for row in rows}

    assert by_dimension["data_validity"]["depth_status"] == "conditional"
    assert by_dimension["data_validity"]["reviewer_risk_level"] == "medium"
    assert "人工 gold" in by_dimension["data_validity"]["next_optimization"]


def test_write_research_depth_audit_outputs_writes_jsonl_csv_and_markdown(tmp_path) -> None:
    """验证研究深度审计写出 JSONL、CSV 和 Markdown。"""
    rows = [
        {
            "dimension_id": "advanced_baseline",
            "depth_status": "not_ready",
            "reviewer_risk_level": "high",
            "defensible_position": "不能声称 SOTA。",
            "blocking_reasons": ["blocked_missing_secret"],
            "next_optimization": "完成 LLM api_model。",
        }
    ]
    output_dir = tmp_path / "research_depth_audit"

    write_research_depth_audit_outputs(rows, output_dir)

    assert read_records(output_dir / "research_depth_audit.jsonl")[0]["dimension_id"] == "advanced_baseline"
    assert (output_dir / "research_depth_audit.csv").exists()
    assert "# Research Depth Audit" in (output_dir / "research_depth_audit.md").read_text(encoding="utf-8")


def test_build_research_depth_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出研究深度审计。"""
    reviewer = tmp_path / "reviewer_audit.jsonl"
    claim = tmp_path / "paper_claim_audit.jsonl"
    readiness = tmp_path / "journal_readiness.jsonl"
    dependency = tmp_path / "experiment_dependency.jsonl"
    output_dir = tmp_path / "research_depth_audit"
    _write_jsonl(reviewer, [{"concern_id": "innovation_depth", "status": "evidence_ready"}])
    _write_jsonl(claim, [{"claim_id": "identity_agenda_risk_modeling", "claim_status": "supported"}])
    _write_jsonl(readiness, [])
    _write_jsonl(dependency, [])

    command_build_research_depth_audit(
        Namespace(
            reviewer_audits=[str(reviewer)],
            claim_audits=[str(claim)],
            readiness_reports=[str(readiness)],
            dependency_reports=[str(dependency)],
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "research_depth_audit.jsonl")
    assert (output_dir / "research_depth_audit.md").exists()


def test_cli_includes_build_research_depth_audit_command() -> None:
    """验证 CLI 暴露 build-research-depth-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-research-depth-audit",
            "--reviewer-audits",
            "outputs/reviewer_audit_fixture/reviewer_audit.jsonl",
            "--claim-audits",
            "outputs/paper_claim_audit_fixture/paper_claim_audit.jsonl",
            "--readiness-reports",
            "outputs/journal_readiness_fixture/journal_readiness.jsonl",
            "--dependency-reports",
            "outputs/experiment_dependency_fixture/experiment_dependency.jsonl",
            "--output-dir",
            "outputs/research_depth_audit_fixture",
        ]
    )

    assert args.command == "build-research-depth-audit"
    assert args.claim_audits == ["outputs/paper_claim_audit_fixture/paper_claim_audit.jsonl"]
