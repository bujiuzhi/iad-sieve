"""测试远程结果接收审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_remote_result_acceptance
from iad_sieve.evaluation.remote_result_acceptance import (
    build_remote_result_acceptance_rows,
    build_remote_result_acceptance_rows_from_paths,
    write_remote_result_acceptance_outputs,
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


def test_build_remote_result_acceptance_rows_groups_outputs_by_claim_gate() -> None:
    """验证远程结果接收审计按论文门禁聚合输出验收状态。"""
    execution_rows = [
        {
            "task_id": "run_specter2",
            "resolves_gate": "specter2_adapter_actual_model",
            "execution_stage": 0,
            "expected_outputs": ["outputs/specter2_scores.jsonl", "outputs/specter2_summary.jsonl"],
        },
        {
            "task_id": "run_llm",
            "resolves_gate": "llm_pair_judge_api_model",
            "execution_stage": 0,
            "expected_outputs": ["outputs/gpt_scores.jsonl", "outputs/gpt_summary.jsonl"],
        },
    ]
    validation_rows = [
        {"task_id": "run_specter2", "required_output": "outputs/specter2_scores.jsonl", "validation_status": "valid"},
        {"task_id": "run_specter2", "required_output": "outputs/specter2_summary.jsonl", "validation_status": "valid"},
        {"task_id": "run_llm", "required_output": "outputs/gpt_scores.jsonl", "validation_status": "missing"},
        {"task_id": "run_llm", "required_output": "outputs/gpt_summary.jsonl", "validation_status": "valid"},
    ]

    rows = build_remote_result_acceptance_rows(execution_rows, validation_rows)
    by_id = {row["acceptance_id"]: row for row in rows}

    assert by_id["task:run_specter2"]["acceptance_status"] == "accepted"
    assert by_id["task:run_llm"]["acceptance_status"] == "blocked_outputs"
    assert by_id["gate:specter2_adapter_actual_model"]["acceptance_status"] == "accepted"
    assert by_id["gate:specter2_adapter_actual_model"]["paper_claim_update"] == "可纳入 SPECTER2 actual_model 强 baseline 与 IAD-Risk 表征鲁棒性证据。"
    assert by_id["gate:llm_pair_judge_api_model"]["acceptance_status"] == "blocked_outputs"
    assert by_id["gate:llm_pair_judge_api_model"]["missing_output_count"] == 1
    assert "不得写成 LLM API baseline 已完成" in by_id["gate:llm_pair_judge_api_model"]["paper_claim_boundary"]


def test_write_remote_result_acceptance_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证远程结果接收审计写出 JSONL、CSV、Markdown 和 summary。"""
    rows = [
        {
            "acceptance_id": "gate:specter2_adapter_actual_model",
            "acceptance_type": "gate",
            "acceptance_status": "accepted",
            "task_count": 1,
            "accepted_task_count": 1,
            "blocked_task_count": 0,
            "missing_output_count": 0,
            "invalid_output_count": 0,
            "paper_claim_update": "可纳入 SPECTER2 actual_model 强 baseline 与 IAD-Risk 表征鲁棒性证据。",
            "paper_claim_boundary": "",
            "next_action": "重建 advanced model evidence、model superiority audit 和 Q2/B gates。",
        },
        {
            "acceptance_id": "gate:llm_pair_judge_api_model",
            "acceptance_type": "gate",
            "acceptance_status": "blocked_outputs",
            "task_count": 1,
            "accepted_task_count": 0,
            "blocked_task_count": 1,
            "missing_output_count": 1,
            "invalid_output_count": 0,
            "paper_claim_update": "",
            "paper_claim_boundary": "该门禁未接收前，不得写成 LLM API baseline 已完成。",
            "next_action": "补齐缺失输出并重新运行 validate-remote-outputs。",
        },
    ]
    output_dir = tmp_path / "remote_result_acceptance"

    write_remote_result_acceptance_outputs(rows, output_dir)

    assert read_records(output_dir / "remote_result_acceptance.jsonl")[0]["acceptance_type"] == "gate"
    assert (output_dir / "remote_result_acceptance.csv").exists()
    markdown = (output_dir / "remote_result_acceptance.md").read_text(encoding="utf-8")
    assert "# Remote Result Acceptance" in markdown
    assert "llm_pair_judge_api_model" in markdown
    summary = read_records(output_dir / "remote_result_acceptance_summary.jsonl")[0]
    assert summary["gate_count"] == 2
    assert summary["accepted_gate_count"] == 1
    assert summary["blocked_gate_count"] == 1
    assert summary["all_claim_gates_accepted"] is False


def test_write_remote_result_acceptance_outputs_treats_empty_plan_as_no_pending_claim_gates(tmp_path) -> None:
    """验证空执行计划表示当前无待接收远程主张门禁。"""
    output_dir = tmp_path / "remote_result_acceptance"

    write_remote_result_acceptance_outputs([], output_dir)

    summary = read_records(output_dir / "remote_result_acceptance_summary.jsonl")[0]
    assert summary["task_count"] == 0
    assert summary["gate_count"] == 0
    assert summary["blocked_gate_count"] == 0
    assert summary["no_claim_gates_pending"] is True
    assert summary["all_claim_gates_accepted"] is True


def test_build_remote_result_acceptance_from_paths_and_cli(tmp_path) -> None:
    """验证路径入口和 CLI 能生成远程结果接收审计。"""
    execution_plan = tmp_path / "experiment_execution_plan.jsonl"
    validation = tmp_path / "remote_output_validation.jsonl"
    output_dir = tmp_path / "remote_result_acceptance"
    _write_jsonl(
        execution_plan,
        [
            {
                "task_id": "run_specter2",
                "resolves_gate": "specter2_adapter_actual_model",
                "execution_stage": 0,
                "expected_outputs": ["outputs/specter2_scores.jsonl"],
            }
        ],
    )
    _write_jsonl(validation, [{"task_id": "run_specter2", "required_output": "outputs/specter2_scores.jsonl", "validation_status": "valid"}])

    rows = build_remote_result_acceptance_rows_from_paths(execution_plan, validation)

    assert any(row["acceptance_id"] == "gate:specter2_adapter_actual_model" for row in rows)

    command_build_remote_result_acceptance(
        Namespace(
            execution_plan=str(execution_plan),
            remote_output_validation=str(validation),
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "remote_result_acceptance_summary.jsonl").exists()


def test_cli_includes_build_remote_result_acceptance_command() -> None:
    """验证 CLI 暴露 build-remote-result-acceptance 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-remote-result-acceptance",
            "--execution-plan",
            "outputs/experiment_execution_pack_fixture/experiment_execution_plan.jsonl",
            "--remote-output-validation",
            "outputs/remote_output_validation_fixture/remote_output_validation.jsonl",
            "--output-dir",
            "outputs/remote_result_acceptance_fixture",
        ]
    )

    assert args.command == "build-remote-result-acceptance"
    assert args.output_dir == "outputs/remote_result_acceptance_fixture"
