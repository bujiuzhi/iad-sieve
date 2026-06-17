"""测试实验执行交接包。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_experiment_execution_pack
from iad_sieve.evaluation.experiment_execution_pack import (
    build_experiment_execution_rows,
    write_experiment_execution_pack_outputs,
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


def test_build_experiment_execution_rows_keeps_stage_order_and_requirements() -> None:
    """验证执行计划保留阶段顺序和资源需求。"""
    queue_rows = [
        {
            "task_id": "run_encoder",
            "priority": 1,
            "requires_remote": True,
            "requires_secret": "",
            "command": "python -m iad_sieve.cli run-representation-baseline --output outputs/scores.jsonl",
            "expected_outputs": "outputs/scores.jsonl; outputs/summary.jsonl",
        },
        {
            "task_id": "run_llm",
            "priority": 2,
            "requires_remote": False,
            "requires_secret": "OPENAI_API_KEY",
            "command": "python -m iad_sieve.cli run-llm-judge-baseline --output outputs/llm.jsonl",
        },
    ]
    preflight_rows = [
        {"task_id": "run_encoder", "status": "blocked_remote_required", "remote_status": "required_missing", "secret_status": "not_required"},
        {"task_id": "run_llm", "status": "blocked_missing_secret", "remote_status": "not_required", "secret_status": "missing"},
    ]
    dependency_rows = [
        {"task_id": "run_encoder", "execution_stage": 0, "depends_on": [], "root_blocker_statuses": ["blocked_remote_required"]},
        {"task_id": "run_llm", "execution_stage": 0, "depends_on": [], "root_blocker_statuses": ["blocked_missing_secret"]},
    ]

    rows = build_experiment_execution_rows(queue_rows, preflight_rows, dependency_rows)
    by_task = {row["task_id"]: row for row in rows}

    assert [row["task_id"] for row in rows] == ["run_encoder", "run_llm"]
    assert by_task["run_encoder"]["requires_remote"] is True
    assert by_task["run_encoder"]["pre_run_checks"] == ["check_cuda"]
    assert by_task["run_encoder"]["expected_outputs"] == ["outputs/scores.jsonl", "outputs/summary.jsonl"]
    assert by_task["run_encoder"]["missing_outputs"] == []
    assert by_task["run_llm"]["requires_secret"] == "OPENAI_API_KEY"
    assert by_task["run_llm"]["pre_run_checks"] == ["check_secret:OPENAI_API_KEY"]


def test_write_experiment_execution_pack_outputs_writes_stage_scripts_without_secret_values(tmp_path) -> None:
    """验证执行包写出计划、阶段脚本且不包含密钥值。"""
    rows = [
        {
            "task_id": "run_encoder",
            "priority": 1,
            "execution_stage": 0,
            "status": "blocked_remote_required",
            "requires_remote": True,
            "requires_secret": "",
            "pre_run_checks": ["check_cuda"],
            "command": "python -m iad_sieve.cli run-representation-baseline --output outputs/scores.jsonl",
            "expected_outputs": ["outputs/scores.jsonl"],
            "missing_outputs": ["outputs/scores.jsonl"],
        },
        {
            "task_id": "run_llm",
            "priority": 2,
            "execution_stage": 0,
            "status": "blocked_missing_secret",
            "requires_remote": False,
            "requires_secret": "OPENAI_API_KEY",
            "pre_run_checks": ["check_secret:OPENAI_API_KEY"],
            "command": "python -m iad_sieve.cli run-llm-judge-baseline --output outputs/llm.jsonl",
            "expected_outputs": ["outputs/llm.jsonl"],
            "missing_outputs": ["outputs/llm.jsonl"],
        },
    ]
    output_dir = tmp_path / "experiment_execution_pack"

    write_experiment_execution_pack_outputs(rows, output_dir)

    assert read_records(output_dir / "experiment_execution_plan.jsonl")[0]["task_id"] == "run_encoder"
    assert (output_dir / "experiment_execution_plan.csv").exists()
    assert "# Experiment Execution Pack" in (output_dir / "experiment_execution_plan.md").read_text(encoding="utf-8")
    stage_script = (output_dir / "run_stage_00.sh").read_text(encoding="utf-8")
    assert "python scripts/check_cuda.py" in stage_script
    assert "${OPENAI_API_KEY:?" in stage_script
    assert ("OPENAI_API_KEY" + "=") not in stage_script
    assert "run-representation-baseline" in stage_script
    assert "run-llm-judge-baseline" in stage_script
    handoff = (output_dir / "remote_handoff.md").read_text(encoding="utf-8")
    assert "# Remote Experiment Handoff" in handoff
    assert "remote_host" in handoff
    assert "run_encoder" in handoff
    assert "outputs/scores.jsonl" in handoff
    output_manifest = read_records(output_dir / "remote_output_manifest.jsonl")
    assert output_manifest[0]["task_id"] == "run_encoder"
    assert output_manifest[0]["required_output"] == "outputs/scores.jsonl"
    assert output_manifest[0]["acceptance_status"] == "missing"


def test_write_experiment_execution_pack_outputs_splits_chained_stage_commands(tmp_path) -> None:
    """验证阶段脚本不会把多条命令写成脆弱的超长单行。"""
    rows = [
        {
            "task_id": "rebuild_package",
            "priority": 99,
            "execution_stage": 3,
            "status": "ready",
            "requires_remote": False,
            "requires_secret": "",
            "pre_run_checks": [],
            "command": (
                "python -m iad_sieve.cli export-topic-package "
                "--report-dirs outputs/a outputs/b && "
                "python -m iad_sieve.cli validate-remote-outputs --output-dir outputs/c"
            ),
            "expected_outputs": ["outputs/topic_package_final"],
            "missing_outputs": [],
        },
    ]
    output_dir = tmp_path / "experiment_execution_pack"

    write_experiment_execution_pack_outputs(rows, output_dir)

    stage_script = (output_dir / "run_stage_03.sh").read_text(encoding="utf-8")
    script_lines = stage_script.splitlines()
    assert " && " not in stage_script
    assert "python -m iad_sieve.cli export-topic-package --report-dirs outputs/a outputs/b" in script_lines
    assert "python -m iad_sieve.cli validate-remote-outputs --output-dir outputs/c" in script_lines


def test_build_experiment_execution_pack_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出执行交接包。"""
    queue = tmp_path / "experiment_queue.jsonl"
    preflight = tmp_path / "experiment_preflight.jsonl"
    dependency = tmp_path / "experiment_dependency.jsonl"
    output_dir = tmp_path / "experiment_execution_pack"
    _write_jsonl(queue, [{"task_id": "run_encoder", "priority": 1, "requires_remote": True, "command": "python -m iad_sieve.cli run-representation-baseline"}])
    _write_jsonl(preflight, [{"task_id": "run_encoder", "status": "blocked_remote_required", "remote_status": "required_missing"}])
    _write_jsonl(dependency, [{"task_id": "run_encoder", "execution_stage": 0, "depends_on": [], "root_blocker_statuses": ["blocked_remote_required"]}])

    command_build_experiment_execution_pack(
        Namespace(
            queue=str(queue),
            preflight=str(preflight),
            dependency=str(dependency),
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "experiment_execution_plan.jsonl")[0]["task_id"] == "run_encoder"
    assert (output_dir / "run_stage_00.sh").exists()


def test_cli_includes_build_experiment_execution_pack_command() -> None:
    """验证 CLI 暴露 build-experiment-execution-pack 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-experiment-execution-pack",
            "--queue",
            "outputs/experiment_queue_fixture/experiment_queue.jsonl",
            "--preflight",
            "outputs/experiment_preflight_fixture/experiment_preflight.jsonl",
            "--dependency",
            "outputs/experiment_dependency_fixture/experiment_dependency.jsonl",
            "--output-dir",
            "outputs/experiment_execution_pack_fixture",
        ]
    )

    assert args.command == "build-experiment-execution-pack"
    assert args.dependency == "outputs/experiment_dependency_fixture/experiment_dependency.jsonl"
