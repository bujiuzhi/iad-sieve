"""测试 Q2/B 外部阻塞合同审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_q2b_external_blocker_audit
from iad_sieve.evaluation.q2b_external_blocker_audit import (
    build_q2b_external_blocker_rows,
    summarize_q2b_external_blockers,
    write_q2b_external_blocker_outputs,
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


def test_build_q2b_external_blocker_rows_collapses_model_artifact_and_missing_outputs() -> None:
    """验证本地 LLM 模型目录与 GPT 缺失输出会聚合为安全外部阻塞合同。"""
    completion_rows = [
        {
            "criterion_id": "q2b_final_goal",
            "status": "blocked",
            "blocking_reasons": ["remote_model_artifact", "llm_pair_judge_api_model"],
            "paper_claim_boundary": "不能声称已经达到二区/B类。",
        }
    ]
    action_rows = [
        {
            "action_id": "provide_model_artifact:outputs/models/local_llm_judge",
            "status": "blocked_external_input",
            "action_type": "remote_model_artifact_input",
            "blocking_scope": "remote_model_artifact",
            "external_input_name": "outputs/models/local_llm_judge",
            "next_action": "预置 outputs/models/local_llm_judge，不要写入密钥。",
            "paper_claim_boundary": "模型目录未预置前，不能声称本地 LLM judge actual_model 完成。",
        },
        {
            "action_id": "execute_remote_task:run_gpt_pair_judge",
            "status": "blocked_missing_input",
            "action_type": "remote_root_task",
            "source_task_ids": ["run_gpt_pair_judge"],
            "missing_outputs": ["scores.jsonl", "summary.jsonl"],
        },
    ]
    remote_acceptance_rows = [
        {
            "acceptance_id": "task:run_gpt_pair_judge",
            "acceptance_status": "blocked_outputs",
            "gate_id": "source_held_out_generalization",
            "task_id": "run_gpt_pair_judge",
            "missing_output_count": 2,
            "required_outputs": ["scores.jsonl", "summary.jsonl"],
            "paper_claim_boundary": "该门禁未接收前，不得写成 source-held-out 泛化已验证。",
        }
    ]
    advanced_rows = [
        {
            "evidence_id": "required:gpt_pair_judge_open_v3",
            "system": "gpt_pair_judge_open_v3",
            "evidence_status": "missing_required",
            "evaluation_track": "open_v3_source_heldout",
            "missing_reason": "remote output missing",
        }
    ]

    rows = build_q2b_external_blocker_rows(
        completion_rows=completion_rows,
        action_rows=action_rows,
        remote_acceptance_rows=remote_acceptance_rows,
        advanced_rows=advanced_rows,
    )
    by_id = {row["blocker_id"]: row for row in rows}

    model_blocker = by_id["external_model_artifact:outputs/models/local_llm_judge"]
    assert model_blocker["blocker_type"] == "external_model_artifact"
    assert model_blocker["status"] == "external_input_required"
    assert model_blocker["external_input_name"] == "outputs/models/local_llm_judge"
    assert "sk-" not in json.dumps(model_blocker, ensure_ascii=False)
    assert by_id["remote_missing_outputs:source_held_out_generalization"]["missing_output_count"] == 2
    assert by_id["advanced_missing:gpt_pair_judge_open_v3"]["external_input_name"] == "outputs/models/local_llm_judge"
    assert by_id["advanced_missing:gpt_pair_judge_open_v3"]["affected_systems"] == ["gpt_pair_judge_open_v3"]
    assert by_id["claim_lock:q2b_final_goal"]["status"] == "claim_locked"


def test_build_q2b_external_blocker_rows_ignores_unspecified_secret_gate_recheck() -> None:
    """验证泛化门禁复核动作不会生成 unknown_secret 阻塞。"""
    rows = build_q2b_external_blocker_rows(
        completion_rows=[
            {
                "criterion_id": "q2b_final_goal",
                "status": "blocked",
                "blocking_reasons": ["remote_secret_configuration"],
            }
        ],
        action_rows=[
            {
                "action_id": "close_submission_gate:remote_connection_gate",
                "status": "blocked",
                "blocking_scope": "remote_secret_configuration",
                "next_action": "补齐必要密钥。",
            }
        ],
        remote_acceptance_rows=[],
        advanced_rows=[],
    )

    assert "external_secret:unknown_secret" not in {row["blocker_id"] for row in rows}


def test_build_q2b_external_blocker_rows_avoids_gate_task_missing_output_double_count() -> None:
    """验证远程缺失输出优先按 task 行计数，避免 gate 汇总重复。"""
    rows = build_q2b_external_blocker_rows(
        completion_rows=[],
        action_rows=[],
        remote_acceptance_rows=[
            {
                "acceptance_id": "task:run_gpt",
                "acceptance_type": "task",
                "acceptance_status": "blocked_outputs",
                "gate_id": "llm_pair_judge_api_model",
                "task_id": "run_gpt",
                "missing_output_count": 2,
                "required_outputs": ["scores.jsonl", "summary.jsonl"],
            },
            {
                "acceptance_id": "gate:llm_pair_judge_api_model",
                "acceptance_type": "gate",
                "acceptance_status": "blocked_outputs",
                "gate_id": "llm_pair_judge_api_model",
                "missing_output_count": 2,
            },
        ],
        advanced_rows=[],
    )

    by_id = {row["blocker_id"]: row for row in rows}

    assert by_id["remote_missing_outputs:llm_pair_judge_api_model"]["missing_output_count"] == 2


def test_write_q2b_external_blocker_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证外部阻塞合同写出 JSONL、CSV、Markdown 与 summary。"""
    rows = [
        {
            "blocker_id": "external_model_artifact:outputs/models/local_llm_judge",
            "blocker_type": "external_model_artifact",
            "status": "external_input_required",
            "priority": 0,
            "external_input_name": "outputs/models/local_llm_judge",
            "source_action_ids": ["provide_model_artifact:outputs/models/local_llm_judge"],
            "source_criteria": ["q2b_final_goal"],
            "affected_systems": ["gpt_pair_judge_open_v3"],
            "missing_outputs": ["scores.jsonl"],
            "missing_output_count": 1,
            "safe_user_action": "在远程项目目录预置 outputs/models/local_llm_judge。",
            "paper_claim_boundary": "未预置前不得写 LLM actual_model 完成。",
        }
    ]
    output_dir = tmp_path / "q2b_external_blocker_audit"

    write_q2b_external_blocker_outputs(rows, output_dir)

    assert read_records(output_dir / "q2b_external_blocker_audit.jsonl")[0]["blocker_id"] == "external_model_artifact:outputs/models/local_llm_judge"
    assert (output_dir / "q2b_external_blocker_audit.csv").exists()
    assert "# Q2/B External Blocker Audit" in (output_dir / "q2b_external_blocker_audit.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "q2b_external_blocker_audit_summary.jsonl")[0]
    assert summary["external_secret_count"] == 0
    assert summary["external_model_artifact_count"] == 1
    assert summary["missing_output_count"] == 1
    assert summary["q2b_blocked_by_external_inputs"] is True


def test_summarize_q2b_external_blockers_counts_unique_missing_outputs() -> None:
    """验证 summary 中缺失输出按唯一路径计数。"""
    summary = summarize_q2b_external_blockers(
        [
            {
                "blocker_id": "external_secret:OPENAI_API_KEY",
                "blocker_type": "external_secret",
                "missing_outputs": ["scores.jsonl"],
                "missing_output_count": 1,
            },
            {
                "blocker_id": "remote_missing_outputs:gpt",
                "blocker_type": "remote_missing_outputs",
                "missing_outputs": ["scores.jsonl"],
                "missing_output_count": 1,
            },
        ]
    )

    assert summary["missing_output_count"] == 1


def test_build_q2b_external_blocker_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 可生成外部阻塞合同。"""
    completion = tmp_path / "q2b_completion_audit.jsonl"
    action_board = tmp_path / "q2b_action_board.jsonl"
    remote_acceptance = tmp_path / "remote_result_acceptance.jsonl"
    advanced = tmp_path / "advanced_model_evidence.jsonl"
    output_dir = tmp_path / "out"
    _write_jsonl(completion, [{"criterion_id": "q2b_final_goal", "status": "blocked"}])
    _write_jsonl(
        action_board,
        [
            {
                "action_id": "provide_model_artifact:outputs/models/local_llm_judge",
                "action_type": "remote_model_artifact_input",
                "status": "blocked_external_input",
                "blocking_scope": "remote_model_artifact",
                "external_input_name": "outputs/models/local_llm_judge",
            }
        ],
    )
    _write_jsonl(remote_acceptance, [{"acceptance_id": "gate:gpt", "acceptance_status": "blocked_outputs", "missing_output_count": 1}])
    _write_jsonl(advanced, [{"evidence_id": "required:gpt", "evidence_status": "missing_required", "system": "gpt"}])

    command_build_q2b_external_blocker_audit(
        Namespace(
            completion_audit=str(completion),
            action_board=str(action_board),
            remote_result_acceptance=str(remote_acceptance),
            advanced_model_evidence=str(advanced),
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "q2b_external_blocker_audit.jsonl").exists()
    assert (output_dir / "q2b_external_blocker_audit_summary.jsonl").exists()


def test_cli_includes_build_q2b_external_blocker_audit_command() -> None:
    """验证 CLI 暴露 build-q2b-external-blocker-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-q2b-external-blocker-audit",
            "--completion-audit",
            "outputs/q2b_completion_audit_fixture/q2b_completion_audit.jsonl",
            "--action-board",
            "outputs/q2b_action_board_fixture/q2b_action_board.jsonl",
            "--remote-result-acceptance",
            "outputs/remote_result_acceptance_fixture/remote_result_acceptance.jsonl",
            "--advanced-model-evidence",
            "outputs/advanced_model_evidence_fixture/advanced_model_evidence.jsonl",
            "--output-dir",
            "outputs/q2b_external_blocker_audit_fixture",
        ]
    )

    assert args.func == command_build_q2b_external_blocker_audit
    assert args.output_dir == "outputs/q2b_external_blocker_audit_fixture"
