"""测试实验队列依赖图。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_experiment_dependency
from iad_sieve.evaluation.experiment_dependency import (
    build_experiment_dependency_rows,
    write_experiment_dependency_outputs,
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


def test_build_experiment_dependency_rows_links_missing_inputs_to_producers() -> None:
    """验证缺失输入会链接到产生该输出的上游任务。"""
    queue_rows = [
        {
            "task_id": "run_encoder",
            "priority": 1,
            "requires_remote": True,
            "expected_outputs": "outputs/scores.jsonl; outputs/run_summary.jsonl",
        },
        {
            "task_id": "evaluate_encoder",
            "priority": 2,
            "requires_remote": False,
            "expected_outputs": "outputs/metric_summary.jsonl",
        },
    ]
    preflight_rows = [
        {
            "task_id": "run_encoder",
            "status": "blocked_remote_required",
            "missing_inputs": [],
            "missing_outputs": ["outputs/scores.jsonl", "outputs/run_summary.jsonl"],
        },
        {
            "task_id": "evaluate_encoder",
            "status": "blocked_missing_input",
            "missing_inputs": ["outputs/scores.jsonl"],
            "missing_outputs": ["outputs/metric_summary.jsonl"],
        },
    ]

    rows = build_experiment_dependency_rows(queue_rows, preflight_rows)
    by_task = {row["task_id"]: row for row in rows}

    assert by_task["evaluate_encoder"]["depends_on"] == ["run_encoder"]
    assert by_task["run_encoder"]["unlocks"] == ["evaluate_encoder"]
    assert by_task["evaluate_encoder"]["root_blocker_task_ids"] == ["run_encoder"]
    assert by_task["evaluate_encoder"]["root_blocker_statuses"] == ["blocked_remote_required"]


def test_build_experiment_dependency_rows_propagates_secret_root_blocker_across_chain() -> None:
    """验证多级依赖会传播到根阻塞任务。"""
    queue_rows = [
        {"task_id": "run_llm", "priority": 1, "expected_outputs": "outputs/llm_scores.jsonl"},
        {"task_id": "evaluate_llm", "priority": 2, "expected_outputs": "outputs/llm_metric.jsonl"},
        {"task_id": "bootstrap_llm", "priority": 3, "expected_outputs": "outputs/llm_bootstrap.csv"},
    ]
    preflight_rows = [
        {"task_id": "run_llm", "status": "blocked_missing_secret", "missing_inputs": [], "missing_outputs": ["outputs/llm_scores.jsonl"]},
        {"task_id": "evaluate_llm", "status": "blocked_missing_input", "missing_inputs": ["outputs/llm_scores.jsonl"], "missing_outputs": ["outputs/llm_metric.jsonl"]},
        {"task_id": "bootstrap_llm", "status": "blocked_missing_input", "missing_inputs": ["outputs/llm_metric.jsonl"], "missing_outputs": ["outputs/llm_bootstrap.csv"]},
    ]

    rows = build_experiment_dependency_rows(queue_rows, preflight_rows)
    by_task = {row["task_id"]: row for row in rows}

    assert by_task["bootstrap_llm"]["depends_on"] == ["evaluate_llm"]
    assert by_task["bootstrap_llm"]["root_blocker_task_ids"] == ["run_llm"]
    assert by_task["bootstrap_llm"]["root_blocker_statuses"] == ["blocked_missing_secret"]
    assert by_task["run_llm"]["downstream_blocked_count"] == 2


def test_write_experiment_dependency_outputs_writes_jsonl_csv_and_markdown(tmp_path) -> None:
    """验证依赖图写出 JSONL、CSV 和 Markdown。"""
    output_dir = tmp_path / "experiment_dependency"
    rows = [
        {
            "task_id": "run_encoder",
            "priority": 1,
            "status": "blocked_remote_required",
            "depends_on": [],
            "unlocks": ["evaluate_encoder"],
            "root_blocker_task_ids": ["run_encoder"],
            "root_blocker_statuses": ["blocked_remote_required"],
            "downstream_blocked_count": 1,
            "execution_stage": 0,
            "next_action": "准备远程/GPU 环境后执行该任务。",
        }
    ]

    write_experiment_dependency_outputs(rows, output_dir)

    assert read_records(output_dir / "experiment_dependency.jsonl")[0]["task_id"] == "run_encoder"
    assert (output_dir / "experiment_dependency.csv").exists()
    assert "# Experiment Dependency Graph" in (output_dir / "experiment_dependency.md").read_text(encoding="utf-8")


def test_build_experiment_dependency_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出依赖图。"""
    queue = tmp_path / "experiment_queue.jsonl"
    preflight = tmp_path / "experiment_preflight.jsonl"
    output_dir = tmp_path / "experiment_dependency"
    _write_jsonl(queue, [{"task_id": "run_encoder", "priority": 1, "expected_outputs": "outputs/scores.jsonl"}])
    _write_jsonl(preflight, [{"task_id": "run_encoder", "status": "blocked_remote_required", "missing_inputs": [], "missing_outputs": ["outputs/scores.jsonl"]}])

    command_build_experiment_dependency(
        Namespace(
            queue=str(queue),
            preflight=str(preflight),
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "experiment_dependency.jsonl")[0]["status"] == "blocked_remote_required"
    assert (output_dir / "experiment_dependency.md").exists()


def test_cli_includes_build_experiment_dependency_command() -> None:
    """验证 CLI 暴露 build-experiment-dependency 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-experiment-dependency",
            "--queue",
            "outputs/experiment_queue_fixture/experiment_queue.jsonl",
            "--preflight",
            "outputs/experiment_preflight_fixture/experiment_preflight.jsonl",
            "--output-dir",
            "outputs/experiment_dependency_fixture",
        ]
    )

    assert args.command == "build-experiment-dependency"
    assert args.preflight == "outputs/experiment_preflight_fixture/experiment_preflight.jsonl"
