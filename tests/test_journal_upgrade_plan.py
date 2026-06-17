"""测试期刊升级优化计划。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_journal_upgrade_plan
from iad_sieve.evaluation.journal_upgrade_plan import build_journal_upgrade_plan_rows, write_journal_upgrade_plan_outputs
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


def test_build_journal_upgrade_plan_rows_prioritizes_non_human_blockers() -> None:
    """验证无新增人工标注阶段优先解决强 baseline、模型深度和本地 LLM 权重阻塞。"""
    submission_summary_rows = [
        {
            "submission_decision": "blocked",
            "blocking_reasons": [
                "advanced_baseline",
                "specter2_adapter_actual_model",
                "llm_pair_judge_api_model",
                "remote_output_validation",
                "q2_b_ready",
                "source_bias_shortcut",
                "provenance_balance_blocked",
                "model_feature_leakage",
            ],
        }
    ]
    research_depth_rows = [
        {"dimension_id": "advanced_baseline", "depth_status": "not_ready", "blocking_reasons": ["blocked_remote_required", "blocked_missing_secret"]},
        {"dimension_id": "model_depth", "depth_status": "conditional", "blocking_reasons": ["blocked_remote_required"]},
        {"dimension_id": "data_validity", "depth_status": "conditional", "missing_evidence": ["human_gold_available"]},
    ]
    remote_summary_rows = [{"all_outputs_valid": False, "missing_output_count": 14, "valid_output_count": 6}]
    draft_summary_rows = [{"restricted_section_count": 2, "todo_section_count": 1}]

    rows = build_journal_upgrade_plan_rows(
        submission_summary_rows=submission_summary_rows,
        research_depth_rows=research_depth_rows,
        remote_summary_rows=remote_summary_rows,
        manuscript_draft_summary_rows=draft_summary_rows,
        human_annotation_policy="defer",
    )
    by_requirement = {row["requirement_id"]: row for row in rows}

    assert by_requirement["remote_gpu_connection"]["status"] == "blocked_external_input"
    assert by_requirement["specter2_adapter_actual_model"]["dependency_type"] == "remote_gpu"
    llm_requirement = by_requirement["llm_pair_judge_api_model"]
    assert llm_requirement["dependency_type"] == "model_artifact"
    assert "outputs/models/local_llm_judge" in llm_requirement["concrete_action"]
    assert "execution_mode=actual_model" in llm_requirement["expected_evidence"]
    assert "OPENAI_API_KEY" not in llm_requirement["concrete_action"]
    assert by_requirement["human_gold_audit"]["status"] == "deferred_enhancement"
    assert by_requirement["human_gold_audit"]["priority"] > by_requirement["specter2_adapter_actual_model"]["priority"]
    assert "公开 gold/proxy/silver" in by_requirement["data_validity_no_human"]["concrete_action"]
    assert by_requirement["provenance_blind_transformer_retrain"]["status"] == "blocked_external_input"
    assert by_requirement["source_bias_data_closure"]["status"] == "todo_after_remote"
    assert by_requirement["submission_claim_guardrail"]["status"] == "ready_local"


def test_write_journal_upgrade_plan_outputs_writes_jsonl_csv_markdown_and_summary(tmp_path) -> None:
    """验证期刊升级优化计划写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "journal_upgrade_plan"
    rows = [
        {
            "requirement_id": "remote_gpu_connection",
            "priority": 1,
            "status": "blocked_external_input",
            "dependency_type": "remote_gpu",
            "concrete_action": "补充远程连接方式。",
            "expected_evidence": "远程脚本执行产物。",
            "reviewer_risk_if_missing": "无法验证强 baseline。",
            "paper_claim_boundary": "不能写强 baseline 已完成。",
        }
    ]

    write_journal_upgrade_plan_outputs(rows, output_dir)

    assert read_records(output_dir / "journal_upgrade_plan.jsonl")[0]["requirement_id"] == "remote_gpu_connection"
    assert (output_dir / "journal_upgrade_plan.csv").exists()
    assert "# Journal Upgrade Plan" in (output_dir / "journal_upgrade_plan.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "journal_upgrade_plan_summary.jsonl")[0]
    assert summary["blocked_external_input_count"] == 1


def test_build_journal_upgrade_plan_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出期刊升级优化计划。"""
    submission_summary = tmp_path / "submission_gate_audit_summary.jsonl"
    research_depth = tmp_path / "research_depth_audit.jsonl"
    remote_summary = tmp_path / "remote_output_validation_summary.jsonl"
    draft_summary = tmp_path / "manuscript_draft_skeleton_summary.jsonl"
    output_dir = tmp_path / "journal_upgrade_plan"
    _write_jsonl(submission_summary, [{"submission_decision": "blocked", "blocking_reasons": ["specter2_adapter_actual_model"]}])
    _write_jsonl(research_depth, [{"dimension_id": "advanced_baseline", "depth_status": "not_ready"}])
    _write_jsonl(remote_summary, [{"all_outputs_valid": False, "missing_output_count": 14}])
    _write_jsonl(draft_summary, [{"restricted_section_count": 2, "todo_section_count": 1}])

    command_build_journal_upgrade_plan(
        Namespace(
            submission_summaries=[str(submission_summary)],
            research_depth_audits=[str(research_depth)],
            remote_output_summaries=[str(remote_summary)],
            manuscript_draft_summaries=[str(draft_summary)],
            output_dir=str(output_dir),
            human_annotation_policy="defer",
        )
    )

    assert read_records(output_dir / "journal_upgrade_plan.jsonl")
    assert (output_dir / "journal_upgrade_plan.md").exists()


def test_cli_includes_build_journal_upgrade_plan_command() -> None:
    """验证 CLI 暴露 build-journal-upgrade-plan 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-journal-upgrade-plan",
            "--submission-summaries",
            "outputs/submission_gate_audit_fixture/submission_gate_audit_summary.jsonl",
            "--research-depth-audits",
            "outputs/research_depth_audit_fixture/research_depth_audit.jsonl",
            "--remote-output-summaries",
            "outputs/remote_output_validation_fixture/remote_output_validation_summary.jsonl",
            "--manuscript-draft-summaries",
            "outputs/manuscript_draft_skeleton_fixture/manuscript_draft_skeleton_summary.jsonl",
            "--human-annotation-policy",
            "defer",
            "--output-dir",
            "outputs/journal_upgrade_plan_fixture",
        ]
    )

    assert args.command == "build-journal-upgrade-plan"
    assert args.human_annotation_policy == "defer"
