"""测试 Q2/B 升级路线图生成。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_q2b_upgrade_roadmap
from iad_sieve.evaluation.q2b_upgrade_roadmap import build_q2b_upgrade_roadmap_rows, write_q2b_upgrade_roadmap_outputs
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


def test_build_q2b_upgrade_roadmap_rows_prioritizes_remote_connection() -> None:
    """验证路线图把远程连接和密钥作为最高优先级阻塞。"""
    completion_rows = [
        {
            "criterion_id": "remote_execution_readiness",
            "status": "blocked",
            "blocking_reasons": ["remote_connection_profile", "remote_secret_configuration"],
            "next_action": "补齐远程连接。",
            "acceptance_evidence": "all_remote_run_inputs_ready=true。",
            "paper_claim_boundary": "远程连接未就绪前不能写强模型完成。",
        },
        {
            "criterion_id": "iad_risk_split_evaluation_readiness",
            "status": "conditional",
            "blocking_reasons": ["stratified_blend_diagnostic_only"],
            "paper_claim_boundary": "gold/silver 分层诊断不能写成 source-heldout。",
        },
        {
            "criterion_id": "q2b_final_goal",
            "status": "blocked",
            "blocking_reasons": ["q2_b_ready"],
        },
    ]
    action_rows = [
        {
            "action_id": "provide_remote_connection:remote_host",
            "action_type": "remote_connection_input",
            "status": "blocked_external_input",
            "blocking_scope": "remote_connection_profile",
            "next_action": "提供 remote_host。",
            "acceptance_evidence": "remote_host 已提供。",
        },
        {
            "action_id": "review_remote_stage_template:0",
            "action_type": "remote_stage_template",
            "status": "blocked_until_connection_ready",
            "blocking_scope": "remote_stage_execution",
            "next_action": "执行 run_stage_00.sh。",
        },
    ]
    remote_output_summary_rows = [{"missing_output_count": 47}]

    rows = build_q2b_upgrade_roadmap_rows(
        completion_rows=completion_rows,
        action_rows=action_rows,
        remote_output_summary_rows=remote_output_summary_rows,
    )
    by_id = {row["phase_id"]: row for row in rows}

    assert rows[0]["phase_id"] == "p0_remote_connection_and_secret"
    assert by_id["p0_remote_connection_and_secret"]["status"] == "blocked"
    assert by_id["p0_remote_connection_and_secret"]["remote_required"] is True
    assert "remote_connection_profile" in by_id["p0_remote_connection_and_secret"]["current_blockers"]
    assert by_id["p1_strong_model_remote_execution"]["status"] == "blocked"
    assert "missing_output_count=47" in by_id["p1_strong_model_remote_execution"]["current_blockers"]
    assert by_id["p2_source_heldout_and_leakage"]["status"] == "conditional"
    assert by_id["p5_optional_human_gold_enhancement"]["status"] == "deferred"
    assert by_id["p5_optional_human_gold_enhancement"]["human_annotation_required_now"] is False


def test_build_q2b_upgrade_roadmap_rows_filters_stale_connection_action() -> None:
    """验证连接字段已齐备时路线图聚焦模型工件而不继承旧 profile 文案。"""
    completion_rows = [
        {
            "criterion_id": "remote_execution_readiness",
            "status": "blocked",
            "blocking_reasons": ["remote_run_inputs", "remote_model_artifact"],
            "next_action": "补齐远程连接 profile 与模型目录后执行远程 stage 模板。",
        }
    ]
    action_rows = [
        {
            "action_id": "provide_model_artifact:outputs/models/local_llm_judge",
            "action_type": "remote_model_artifact_input",
            "status": "blocked_external_input",
            "blocking_scope": "remote_model_artifact",
            "next_action": "在远程项目目录预置 outputs/models/local_llm_judge。",
        },
        {
            "action_id": "review_remote_handoff_template:sync_and_run",
            "action_type": "remote_handoff_template",
            "status": "ready_template",
            "blocking_scope": "remote_reproducibility_handoff",
            "next_action": "连接字段齐全后执行同步运行模板，按阶段运行远程强模型实验。",
        },
    ]

    rows = build_q2b_upgrade_roadmap_rows(completion_rows=completion_rows, action_rows=action_rows)
    connection_phase = {row["phase_id"]: row for row in rows}["p0_remote_connection_and_secret"]

    assert connection_phase["status"] == "blocked"
    assert "remote_model_artifact" in connection_phase["current_blockers"]
    assert "outputs/models/local_llm_judge" in connection_phase["required_actions"]
    assert "补齐远程连接 profile" not in connection_phase["required_actions"]


def test_build_q2b_upgrade_roadmap_rows_clears_ready_source_heldout_blockers() -> None:
    """验证 source-held-out 证据 ready 时路线图不保留旧缺口。"""
    completion_rows = [
        {
            "criterion_id": "generalization_split_readiness",
            "status": "ready",
            "blocking_reasons": [],
            "next_action": "补齐 topic-held-out 或更强泛化 split 后重建 split readiness。",
            "acceptance_evidence": "random/source-held-out/leakage guard 均 defensible。",
        },
        {
            "criterion_id": "model_training_input_readiness",
            "status": "ready",
            "blocking_reasons": [],
            "next_action": "生成特征完备的 scored relations，并补齐 agenda_non_identity 正负样本后重建训练输入审计。",
            "acceptance_evidence": "training_input_ready=true 且 blocked_count=0。",
        },
        {
            "criterion_id": "iad_risk_split_evaluation_readiness",
            "status": "ready",
            "blocking_reasons": [],
            "next_action": "执行真正 source-held-out 的强模型/IAD-Risk Transformer 实验，并重建 split 评估审计。",
            "acceptance_evidence": "source_heldout_full_iad_ready=true 且 limited_source_heldout_count>0。",
        },
    ]

    rows = build_q2b_upgrade_roadmap_rows(completion_rows=completion_rows, action_rows=[])
    source_phase = {row["phase_id"]: row for row in rows}["p2_source_heldout_and_leakage"]

    assert source_phase["status"] == "ready"
    assert source_phase["current_blockers"] == []
    assert "source_heldout_full_iad_missing" not in source_phase["current_blockers"]
    assert "执行真正 source-held-out" not in source_phase["required_actions"]
    assert "保留 limited source-heldout 边界" in source_phase["required_actions"]


def test_build_q2b_upgrade_roadmap_rows_accepts_conditional_data_validity_boundary_after_claim_lockdown() -> None:
    """验证主张锁定已 ready 时 data_validity 条件边界不阻塞 p4。"""
    completion_rows = [
        {"criterion_id": "reviewer_response_safety", "status": "ready", "acceptance_evidence": "unsafe=0"},
        {"criterion_id": "final_submission_gate", "status": "ready", "acceptance_evidence": "submission ready"},
        {"criterion_id": "q2b_action_closure", "status": "ready", "acceptance_evidence": "actions ready"},
        {"criterion_id": "q2b_final_goal", "status": "ready", "acceptance_evidence": "goal ready"},
    ]
    action_rows = [
        {
            "action_id": "close_submission_gate:data_validity_gate",
            "action_type": "submission_gate_recheck",
            "status": "conditional",
            "blocking_scope": "data_validity",
            "next_action": "当前论文不要声称已有人工 gold。",
        }
    ]

    rows = build_q2b_upgrade_roadmap_rows(completion_rows=completion_rows, action_rows=action_rows)
    manuscript_phase = {row["phase_id"]: row for row in rows}["p4_claim_and_submission_lockdown"]

    assert manuscript_phase["status"] == "ready"
    assert manuscript_phase["current_blockers"] == []
    assert "no-annotation" in manuscript_phase["required_actions"]


def test_write_q2b_upgrade_roadmap_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证路线图写出 JSONL、CSV、Markdown 和摘要。"""
    rows = [
        {
            "phase_id": "p0_remote_connection_and_secret",
            "phase_name": "远程连接与密钥准备",
            "priority": 0,
            "status": "blocked",
            "reviewer_focus": "可复现性",
            "current_blockers": ["remote_connection_profile"],
            "required_actions": "补齐远程连接。",
            "acceptance_evidence": "all_remote_run_inputs_ready=true。",
            "paper_claim_boundary": "不能写强模型完成。",
            "source_criterion_ids": ["remote_execution_readiness"],
            "source_action_ids": ["provide_remote_connection:remote_host"],
            "source_evidence_ids": [],
            "remote_required": True,
            "human_annotation_required_now": False,
        },
        {
            "phase_id": "p5_optional_human_gold_enhancement",
            "phase_name": "人工 gold 后续增强",
            "priority": 5,
            "status": "deferred",
            "reviewer_focus": "人工可信度增强",
            "current_blockers": ["annotation_coordination_deferred"],
            "required_actions": "后续双标。",
            "acceptance_evidence": "Kappa >= 0.70。",
            "paper_claim_boundary": "不能写成人工 gold。",
            "source_criterion_ids": [],
            "source_action_ids": [],
            "source_evidence_ids": [],
            "remote_required": False,
            "human_annotation_required_now": False,
        },
    ]
    output_dir = tmp_path / "q2b_upgrade_roadmap"

    write_q2b_upgrade_roadmap_outputs(rows, output_dir)

    assert read_records(output_dir / "q2b_upgrade_roadmap.jsonl")[0]["phase_id"] == "p0_remote_connection_and_secret"
    assert (output_dir / "q2b_upgrade_roadmap.csv").exists()
    assert "# Q2/B Upgrade Roadmap" in (output_dir / "q2b_upgrade_roadmap.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "q2b_upgrade_roadmap_summary.jsonl")[0]
    assert summary["phase_count"] == 2
    assert summary["blocked_phase_count"] == 1
    assert summary["deferred_phase_count"] == 1
    assert summary["remote_blocked"] is True
    assert summary["human_annotation_required_now"] is False
    assert summary["q2_b_ready"] is False
    assert summary["highest_priority_blocker"] == "p0_remote_connection_and_secret"


def test_build_q2b_upgrade_roadmap_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 Q2/B 升级路线图。"""
    completion = tmp_path / "q2b_completion_audit.jsonl"
    action_board = tmp_path / "q2b_action_board.jsonl"
    remote_output_summary = tmp_path / "remote_output_validation_summary.jsonl"
    output_dir = tmp_path / "q2b_upgrade_roadmap"
    _write_jsonl(completion, [{"criterion_id": "remote_execution_readiness", "status": "blocked"}])
    _write_jsonl(action_board, [{"action_id": "provide_remote_connection:remote_host", "action_type": "remote_connection_input", "status": "blocked_external_input"}])
    _write_jsonl(remote_output_summary, [{"missing_output_count": 47}])

    command_build_q2b_upgrade_roadmap(
        Namespace(
            completion_audit=str(completion),
            action_board=str(action_board),
            remote_acceptance=None,
            remote_output_summary=str(remote_output_summary),
            model_superiority_audit=None,
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "q2b_upgrade_roadmap_summary.jsonl").exists()
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-q2b-upgrade-roadmap",
            "--completion-audit",
            str(completion),
            "--action-board",
            str(action_board),
            "--remote-output-summary",
            str(remote_output_summary),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_q2b_upgrade_roadmap
