"""测试期刊 readiness 诊断报告。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_journal_readiness
from iad_sieve.evaluation.journal_readiness import build_journal_readiness_rows, write_journal_readiness_outputs
from iad_sieve.utils.io_utils import read_records


def _write_jsonl(path, records: list[dict]) -> None:
    """写入 JSONL 测试文件。

    参数:
        path: 输出路径。
        records: 记录列表。

    返回:
        无。
    """
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def test_build_journal_readiness_rows_prioritizes_missing_strong_baselines(tmp_path) -> None:
    """验证 readiness 报告把缺失的强 baseline 排在优先实验中。"""
    rq_summary = tmp_path / "rq_summary.jsonl"
    reviewer_audit = tmp_path / "reviewer_audit.jsonl"
    _write_jsonl(
        rq_summary,
        [
            {"rq": "RQ1", "evidence_layer": "external_baseline", "system": "scincl_cosine_open_v2", "baseline_family": "representation", "execution_mode": "actual_model"},
            {"rq": "RQ1", "evidence_layer": "external_baseline", "system": "roberta_pair_open_v2", "baseline_family": "entity_matching", "execution_mode": "actual_model"},
            {"rq": "RQ1", "evidence_layer": "external_baseline", "system": "llm_fallback_judge", "baseline_family": "llm_judge", "execution_mode": "fallback"},
            {"rq": "RQ2", "evidence_layer": "human_audit_plan", "system": "human_audit_plan", "planned_pair_count_min": 500, "planned_pair_count_max": 1000},
        ],
    )
    _write_jsonl(
        reviewer_audit,
        [
            {"concern_id": "executed_strong_baselines", "severity": "high", "status": "needs_evidence"},
            {"concern_id": "venue_readiness", "severity": "high", "status": "needs_evidence"},
            {"concern_id": "human_audit_deferral", "severity": "medium", "status": "evidence_ready"},
        ],
    )

    rows = build_journal_readiness_rows([rq_summary], [reviewer_audit])
    by_gate = {row["gate_id"]: row for row in rows}

    assert by_gate["overall_q2_b_readiness"]["status"] == "needs_evidence"
    assert by_gate["specter2_adapter_actual_model"]["status"] == "needs_evidence"
    assert by_gate["llm_pair_judge_api_model"]["status"] == "needs_evidence"
    assert by_gate["scincl_actual_model"]["status"] == "evidence_ready"
    assert by_gate["roberta_entity_matching_actual_model"]["status"] == "evidence_ready"
    assert by_gate["human_audit_plan"]["status"] == "evidence_ready"
    assert by_gate["specter2_adapter_actual_model"]["next_experiment_rank"] < by_gate["human_audit_plan"]["next_experiment_rank"]


def test_build_journal_readiness_rows_accepts_completed_strong_baselines(tmp_path) -> None:
    """验证 SPECTER2 adapter、RoBERTa 和 LLM api_model 同时存在时强基线门禁通过。"""
    rq_summary = tmp_path / "rq_summary.jsonl"
    reviewer_audit = tmp_path / "reviewer_audit.jsonl"
    _write_jsonl(
        rq_summary,
        [
            {
                "rq": "RQ1",
                "evidence_layer": "external_baseline",
                "system": "specter2_adapter_cosine_open_v2",
                "baseline_family": "representation",
                "execution_mode": "actual_model",
                "embedding_version": "specter2-adapter",
            },
            {"rq": "RQ1", "evidence_layer": "external_baseline", "system": "roberta_pair_open_v2", "baseline_family": "entity_matching", "execution_mode": "actual_model"},
            {"rq": "RQ1", "evidence_layer": "external_baseline", "system": "gpt_pair_judge", "baseline_family": "llm_judge", "execution_mode": "api_model"},
            {"rq": "RQ2", "evidence_layer": "human_audit_plan", "system": "human_audit_plan", "planned_pair_count_min": 500, "planned_pair_count_max": 1000},
        ],
    )
    _write_jsonl(
        reviewer_audit,
        [
            {"concern_id": "executed_strong_baselines", "severity": "high", "status": "evidence_ready"},
            {"concern_id": "venue_readiness", "severity": "high", "status": "evidence_ready"},
        ],
    )

    rows = build_journal_readiness_rows([rq_summary], [reviewer_audit])
    by_gate = {row["gate_id"]: row for row in rows}

    assert by_gate["specter2_adapter_actual_model"]["status"] == "evidence_ready"
    assert by_gate["llm_pair_judge_api_model"]["status"] == "evidence_ready"
    assert by_gate["executed_strong_baselines"]["status"] == "evidence_ready"
    assert by_gate["overall_q2_b_readiness"]["status"] == "evidence_ready"


def test_build_journal_readiness_rows_accepts_specter2_adapter_system_without_embedding_version(tmp_path) -> None:
    """验证 SPECTER2 adapter system 名称可补足缺失的 embedding_version 字段。"""
    rq_summary = tmp_path / "rq_summary.jsonl"
    reviewer_audit = tmp_path / "reviewer_audit.jsonl"
    _write_jsonl(
        rq_summary,
        [
            {
                "rq": "RQ1",
                "evidence_layer": "external_baseline",
                "system": "specter2_adapter_cosine_open_v3_scholarly_balanced_gold_source_heldout",
                "baseline_family": "representation",
                "execution_mode": "actual_model",
            }
        ],
    )
    _write_jsonl(reviewer_audit, [{"concern_id": "venue_readiness", "severity": "high", "status": "needs_evidence"}])

    rows = build_journal_readiness_rows([rq_summary], [reviewer_audit])
    by_gate = {row["gate_id"]: row for row in rows}

    assert by_gate["specter2_adapter_actual_model"]["status"] == "evidence_ready"


def test_build_journal_readiness_rows_does_not_reask_ready_specter2_in_strong_baseline_action(tmp_path) -> None:
    """验证 SPECTER2 已 ready 时强 baseline 下一步只聚焦剩余 LLM/EM 缺口。"""
    rq_summary = tmp_path / "rq_summary.jsonl"
    reviewer_audit = tmp_path / "reviewer_audit.jsonl"
    _write_jsonl(
        rq_summary,
        [
            {
                "rq": "RQ1",
                "evidence_layer": "external_baseline",
                "system": "specter2_adapter_cosine_open_v3_scholarly_balanced_gold_source_heldout",
                "baseline_family": "representation",
                "execution_mode": "actual_model",
            }
        ],
    )
    _write_jsonl(reviewer_audit, [{"concern_id": "executed_strong_baselines", "severity": "high", "status": "needs_evidence"}])

    rows = build_journal_readiness_rows([rq_summary], [reviewer_audit])
    by_gate = {row["gate_id"]: row for row in rows}

    assert "SPECTER2 adapter actual_model" not in by_gate["executed_strong_baselines"]["next_experiment"]
    assert "LLM api_model" in by_gate["executed_strong_baselines"]["next_experiment"]


def test_write_journal_readiness_outputs_writes_jsonl_csv_and_markdown(tmp_path) -> None:
    """验证 readiness 报告写出 JSONL、CSV 和 Markdown。"""
    output_dir = tmp_path / "journal_readiness"
    rows = [
        {
            "gate_id": "overall_q2_b_readiness",
            "category": "venue",
            "severity": "high",
            "status": "needs_evidence",
            "required_evidence": "强 baseline 与 venue readiness",
            "current_evidence": "venue_readiness=needs_evidence",
            "next_experiment": "完成 SPECTER2 adapter 与 LLM api_model",
            "next_experiment_rank": 1,
        }
    ]

    write_journal_readiness_outputs(rows, output_dir)

    assert read_records(output_dir / "journal_readiness.jsonl")[0]["gate_id"] == "overall_q2_b_readiness"
    assert (output_dir / "journal_readiness.csv").exists()
    assert "# Journal Readiness Report" in (output_dir / "journal_readiness.md").read_text(encoding="utf-8")


def test_build_journal_readiness_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 readiness 报告。"""
    rq_summary = tmp_path / "rq_summary.jsonl"
    reviewer_audit = tmp_path / "reviewer_audit.jsonl"
    output_dir = tmp_path / "journal_readiness"
    _write_jsonl(rq_summary, [{"rq": "RQ1", "evidence_layer": "external_baseline", "system": "scincl_cosine", "baseline_family": "representation", "execution_mode": "actual_model"}])
    _write_jsonl(reviewer_audit, [{"concern_id": "venue_readiness", "severity": "high", "status": "needs_evidence"}])

    command_build_journal_readiness(
        Namespace(
            rq_summaries=[str(rq_summary)],
            reviewer_audits=[str(reviewer_audit)],
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "journal_readiness.jsonl")
    assert (output_dir / "journal_readiness.md").exists()


def test_cli_includes_build_journal_readiness_command() -> None:
    """验证 CLI 暴露 build-journal-readiness 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-journal-readiness",
            "--rq-summaries",
            "outputs/iad_paper_report_fixture/rq_summary.jsonl",
            "--reviewer-audits",
            "outputs/reviewer_audit_fixture/reviewer_audit.jsonl",
            "--output-dir",
            "outputs/journal_readiness_fixture",
        ]
    )

    assert args.command == "build-journal-readiness"
    assert args.reviewer_audits == ["outputs/reviewer_audit_fixture/reviewer_audit.jsonl"]
