"""测试远程强模型执行蓝图。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_remote_execution_blueprint
from iad_sieve.evaluation.remote_execution_blueprint import (
    build_remote_execution_blueprint_rows,
    write_remote_execution_blueprint_outputs,
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


def test_build_remote_execution_blueprint_rows_merges_environment_tasks_and_missing_outputs() -> None:
    """验证蓝图聚合环境依赖、根任务和缺失输出。"""
    execution_rows = [
        {
            "task_id": "run_scincl",
            "priority": 1,
            "execution_stage": 0,
            "status": "blocked_remote_required",
            "requires_remote": True,
            "requires_secret": "",
            "pre_run_checks": ["check_cuda"],
            "depends_on": [],
            "expected_outputs": ["outputs/strong/scincl_metric_summary.jsonl"],
            "command": "python -m iad_sieve.cli run-representation-baseline --model-backend sentence-transformers",
            "reviewer_value": "补齐强 baseline。",
        },
        {
            "task_id": "evaluate_scincl",
            "priority": 2,
            "execution_stage": 1,
            "status": "blocked_missing_input",
            "requires_remote": False,
            "requires_secret": "",
            "pre_run_checks": [],
            "depends_on": ["run_scincl"],
            "expected_outputs": ["outputs/strong/eval.jsonl"],
            "command": "python -m iad_sieve.cli evaluate-external-baseline",
        },
    ]
    environment_rows = [
        {
            "check_id": "python_module:sentence_transformers",
            "dependency_type": "python_module",
            "dependency_name": "sentence_transformers",
            "package_spec": "sentence-transformers>=3.0",
            "purpose": "SciNCL baseline",
            "status": "missing",
            "next_action": "安装 sentence-transformers。",
            "paper_claim_boundary": "不能声称 SciNCL actual_model 已完成。",
        },
        {
            "check_id": "environment_variable:OPENAI_API_KEY",
            "dependency_type": "environment_variable",
            "dependency_name": "OPENAI_API_KEY",
            "status": "ready",
            "next_action": "",
            "paper_claim_boundary": "",
        },
    ]
    validation_rows = [
        {
            "task_id": "run_scincl",
            "required_output": "outputs/strong/scincl_metric_summary.jsonl",
            "validation_status": "missing",
        },
        {
            "task_id": "evaluate_scincl",
            "required_output": "outputs/strong/eval.jsonl",
            "validation_status": "missing",
        },
    ]

    rows = build_remote_execution_blueprint_rows(execution_rows, environment_rows, validation_rows)
    by_id = {row["blueprint_item_id"]: row for row in rows}

    assert by_id["environment:python_module:sentence_transformers"]["blueprint_item_type"] == "environment_dependency"
    assert by_id["environment:python_module:sentence_transformers"]["reviewer_risk_level"] == "high"
    assert by_id["root_task:run_scincl"]["blueprint_item_type"] == "root_execution_task"
    assert by_id["root_task:run_scincl"]["missing_output_count"] == 1
    assert by_id["root_task:run_scincl"]["missing_outputs"] == ["outputs/strong/scincl_metric_summary.jsonl"]
    assert by_id["root_task:run_scincl"]["execution_command"] == execution_rows[0]["command"]
    assert "evaluate_scincl" not in by_id


def test_build_remote_execution_blueprint_rows_skips_valid_remote_root_task() -> None:
    """验证已通过输出验收的远程根任务不再进入待执行蓝图。"""
    execution_rows = [
        {
            "task_id": "run_scincl",
            "priority": 1,
            "execution_stage": 0,
            "status": "blocked_remote_required",
            "requires_remote": True,
            "requires_secret": "",
            "depends_on": [],
            "expected_outputs": ["outputs/strong/scincl_scores.jsonl"],
            "command": "python -m iad_sieve.cli run-representation-baseline",
        }
    ]
    validation_rows = [
        {
            "task_id": "run_scincl",
            "required_output": "outputs/strong/scincl_scores.jsonl",
            "validation_status": "valid",
        }
    ]

    rows = build_remote_execution_blueprint_rows(execution_rows, [], validation_rows)

    assert not any(row.get("blueprint_item_id") == "root_task:run_scincl" for row in rows)


def test_build_remote_execution_blueprint_rows_keeps_dependent_remote_tasks() -> None:
    """验证依赖型远程任务仍进入蓝图，依赖型本地任务不进入。"""
    execution_rows = [
        {
            "task_id": "train_ditto",
            "priority": 39,
            "execution_stage": 0,
            "status": "blocked_remote_required",
            "requires_remote": True,
            "requires_secret": "",
            "depends_on": [],
            "expected_outputs": ["outputs/models/ditto"],
            "command": "python -m iad_sieve.cli train-entity-matching-baseline",
        },
        {
            "task_id": "run_ditto",
            "priority": 40,
            "execution_stage": 1,
            "status": "blocked_missing_input",
            "requires_remote": True,
            "requires_secret": "",
            "depends_on": ["train_ditto"],
            "expected_outputs": ["outputs/ditto_scores.jsonl"],
            "command": "python -m iad_sieve.cli run-entity-matching-baseline",
        },
        {
            "task_id": "evaluate_ditto",
            "priority": 41,
            "execution_stage": 2,
            "status": "blocked_missing_input",
            "requires_remote": False,
            "requires_secret": "",
            "depends_on": ["run_ditto"],
            "expected_outputs": ["outputs/ditto_metric_summary.jsonl"],
            "command": "python -m iad_sieve.cli evaluate-external-baseline",
        },
    ]
    validation_rows = [
        {"task_id": "train_ditto", "required_output": "outputs/models/ditto", "validation_status": "missing"},
        {"task_id": "run_ditto", "required_output": "outputs/ditto_scores.jsonl", "validation_status": "missing"},
        {"task_id": "evaluate_ditto", "required_output": "outputs/ditto_metric_summary.jsonl", "validation_status": "missing"},
    ]

    rows = build_remote_execution_blueprint_rows(execution_rows, [], validation_rows)
    by_task = {row.get("task_id"): row for row in rows if row.get("task_id")}

    assert "train_ditto" in by_task
    assert "run_ditto" in by_task
    assert by_task["run_ditto"]["depends_on"] == ["train_ditto"]
    assert "evaluate_ditto" not in by_task


def test_write_remote_execution_blueprint_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证蓝图写出 JSONL、CSV、Markdown 和汇总。"""
    rows = [
        {
            "blueprint_item_id": "environment:python_module:torch",
            "blueprint_item_type": "environment_dependency",
            "status": "missing",
            "missing_dependency_count": 1,
            "missing_output_count": 0,
            "reviewer_risk_level": "high",
            "next_action": "安装 torch。",
        },
        {
            "blueprint_item_id": "root_task:run_scincl",
            "blueprint_item_type": "root_execution_task",
            "task_id": "run_scincl",
            "status": "blocked_remote_required",
            "missing_dependency_count": 0,
            "missing_output_count": 2,
            "missing_outputs": ["a.jsonl", "b.csv"],
            "reviewer_risk_level": "high",
            "next_action": "运行阶段脚本。",
        },
    ]
    output_dir = tmp_path / "remote_execution_blueprint"

    write_remote_execution_blueprint_outputs(rows, output_dir)

    assert read_records(output_dir / "remote_execution_blueprint.jsonl")[0]["blueprint_item_type"] == "environment_dependency"
    assert (output_dir / "remote_execution_blueprint.csv").exists()
    assert "# Remote Execution Blueprint" in (output_dir / "remote_execution_blueprint.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "remote_execution_blueprint_summary.jsonl")[0]
    assert summary["environment_missing_count"] == 1
    assert summary["root_task_count"] == 1
    assert summary["missing_output_count"] == 2
    assert summary["all_remote_prerequisites_ready"] is False


def test_build_remote_execution_blueprint_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出远程执行蓝图。"""
    execution_plan = tmp_path / "experiment_execution_plan.jsonl"
    environment_audit = tmp_path / "remote_environment_audit.jsonl"
    remote_output_validation = tmp_path / "remote_output_validation.jsonl"
    output_dir = tmp_path / "remote_execution_blueprint"
    _write_jsonl(
        execution_plan,
        [
            {
                "task_id": "run_llm",
                "priority": 1,
                "execution_stage": 0,
                "status": "blocked_missing_secret",
                "requires_secret": "OPENAI_API_KEY",
                "expected_outputs": ["outputs/llm_metric_summary.jsonl"],
                "command": "python -m iad_sieve.cli run-llm-judge-baseline",
            }
        ],
    )
    _write_jsonl(
        environment_audit,
        [
            {
                "check_id": "environment_variable:OPENAI_API_KEY",
                "dependency_type": "environment_variable",
                "dependency_name": "OPENAI_API_KEY",
                "status": "missing",
            }
        ],
    )
    _write_jsonl(
        remote_output_validation,
        [
            {
                "task_id": "run_llm",
                "required_output": "outputs/llm_metric_summary.jsonl",
                "validation_status": "missing",
            }
        ],
    )

    command_build_remote_execution_blueprint(
        Namespace(
            execution_plan=str(execution_plan),
            environment_audit=str(environment_audit),
            remote_output_validation=str(remote_output_validation),
            output_dir=str(output_dir),
        )
    )

    rows = read_records(output_dir / "remote_execution_blueprint.jsonl")
    assert rows[0]["blueprint_item_type"] == "environment_dependency"
    assert any(row.get("task_id") == "run_llm" for row in rows)


def test_cli_includes_build_remote_execution_blueprint_command() -> None:
    """验证 CLI 暴露 build-remote-execution-blueprint 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-remote-execution-blueprint",
            "--execution-plan",
            "outputs/experiment_execution_pack_fixture/experiment_execution_plan.jsonl",
            "--environment-audit",
            "outputs/remote_environment_audit_fixture/remote_environment_audit.jsonl",
            "--remote-output-validation",
            "outputs/remote_output_validation_fixture/remote_output_validation.jsonl",
            "--output-dir",
            "outputs/remote_execution_blueprint_fixture",
        ]
    )

    assert args.command == "build-remote-execution-blueprint"
    assert args.output_dir == "outputs/remote_execution_blueprint_fixture"
