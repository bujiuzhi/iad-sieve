"""测试实验队列 preflight 检查。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_check_experiment_queue
from iad_sieve.evaluation.experiment_preflight import (
    build_experiment_preflight_rows,
    write_experiment_preflight_outputs,
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


def _write_text(path, content: str = "ok\n") -> None:
    """写入文本测试文件。

    参数:
        path: 输出路径。
        content: 文件内容。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_experiment_preflight_rows_blocks_missing_input(tmp_path) -> None:
    """验证输入文件缺失时任务被标记为 missing_input。"""
    rows = build_experiment_preflight_rows(
        [
            {
                "task_id": "run_missing_input",
                "priority": 1,
                "requires_remote": False,
                "requires_secret": "",
                "command": (
                    "python -m iad_sieve.cli run-representation-baseline "
                    "--documents outputs/docs.jsonl "
                    "--pairs outputs/pairs.jsonl "
                    "--output outputs/scores.jsonl"
                ),
                "expected_outputs": "outputs/scores.jsonl",
            }
        ],
        workspace_dir=tmp_path,
        remote_available=False,
        environment={},
    )

    assert rows[0]["status"] == "blocked_missing_input"
    assert rows[0]["missing_input_count"] == 2
    assert "outputs/docs.jsonl" in rows[0]["missing_inputs"]
    assert rows[0]["next_action"] == "补齐缺失输入文件后重跑 preflight。"


def test_build_experiment_preflight_rows_redacts_secret_value(tmp_path) -> None:
    """验证密钥只报告是否存在，不泄露环境变量值。"""
    _write_text(tmp_path / "outputs" / "docs.jsonl")
    _write_text(tmp_path / "outputs" / "pairs.jsonl")

    rows = build_experiment_preflight_rows(
        [
            {
                "task_id": "run_llm_pair_judge",
                "priority": 1,
                "requires_remote": False,
                "requires_secret": "OPENAI_API_KEY",
                "command": (
                    "python -m iad_sieve.cli run-llm-judge-baseline "
                    "--documents outputs/docs.jsonl "
                    "--pairs outputs/pairs.jsonl "
                    "--output outputs/gpt_scores.jsonl"
                ),
                "expected_outputs": "outputs/gpt_scores.jsonl",
            }
        ],
        workspace_dir=tmp_path,
        remote_available=False,
        environment={},
    )

    serialized = json.dumps(rows, ensure_ascii=False)
    assert rows[0]["status"] == "blocked_missing_secret"
    assert rows[0]["secret_status"] == "missing"
    assert ("OPENAI_API_KEY" + "=") not in serialized


def test_build_experiment_preflight_rows_blocks_remote_required_task(tmp_path) -> None:
    """验证远程资源未就绪时 GPU 任务被标记为 remote_required。"""
    _write_text(tmp_path / "outputs" / "docs.jsonl")
    _write_text(tmp_path / "outputs" / "pairs.jsonl")

    rows = build_experiment_preflight_rows(
        [
            {
                "task_id": "run_specter2_adapter",
                "priority": 1,
                "requires_remote": True,
                "requires_secret": "",
                "command": (
                    "python -m iad_sieve.cli run-representation-baseline "
                    "--documents outputs/docs.jsonl "
                    "--pairs outputs/pairs.jsonl "
                    "--output outputs/specter2_scores.jsonl"
                ),
                "expected_outputs": "outputs/specter2_scores.jsonl",
            }
        ],
        workspace_dir=tmp_path,
        remote_available=False,
        environment={},
    )

    assert rows[0]["status"] == "blocked_remote_required"
    assert rows[0]["remote_status"] == "required_missing"
    assert rows[0]["next_action"] == "准备远程/GPU 环境后执行该任务。"


def test_build_experiment_preflight_rows_marks_existing_outputs_satisfied(tmp_path) -> None:
    """验证预期输出已存在时任务被标记为 already_satisfied。"""
    _write_text(tmp_path / "outputs" / "docs.jsonl")
    _write_text(tmp_path / "outputs" / "pairs.jsonl")
    _write_text(tmp_path / "outputs" / "scores.jsonl")

    rows = build_experiment_preflight_rows(
        [
            {
                "task_id": "evaluate_existing_output",
                "priority": 1,
                "requires_remote": False,
                "requires_secret": "",
                "command": (
                    "python -m iad_sieve.cli evaluate-external-baseline "
                    "--relations outputs/pairs.jsonl "
                    "--baseline outputs/docs.jsonl "
                    "--output outputs/scores.jsonl"
                ),
                "expected_outputs": "outputs/scores.jsonl",
            }
        ],
        workspace_dir=tmp_path,
        remote_available=False,
        environment={},
    )

    assert rows[0]["status"] == "already_satisfied"
    assert rows[0]["missing_output_count"] == 0
    assert rows[0]["next_action"] == "预期输出已存在，可进入下游报告重建或复核。"


def test_build_experiment_preflight_rows_prioritizes_missing_inputs_over_stale_outputs(tmp_path) -> None:
    """验证旧输出存在但新输入缺失时优先暴露 missing_input。"""
    _write_text(tmp_path / "outputs" / "paper_report")

    rows = build_experiment_preflight_rows(
        [
            {
                "task_id": "rebuild_report_after_new_baseline",
                "priority": 99,
                "requires_remote": False,
                "requires_secret": "",
                "command": (
                    "python -m iad_sieve.cli build-iad-paper-report "
                    "--external-summaries outputs/new_baseline_metric_summary.jsonl "
                    "--output-dir outputs/paper_report"
                ),
                "expected_outputs": "outputs/paper_report",
            }
        ],
        workspace_dir=tmp_path,
        remote_available=False,
        environment={},
    )

    assert rows[0]["status"] == "blocked_missing_input"
    assert rows[0]["missing_inputs"] == ["outputs/new_baseline_metric_summary.jsonl"]


def test_build_experiment_preflight_rows_checks_model_paths_inputs(tmp_path) -> None:
    """验证 model feature guard 的 --model-paths 会作为输入检查。"""
    _write_text(tmp_path / "outputs" / "existing_model.json")

    rows = build_experiment_preflight_rows(
        [
            {
                "task_id": "build_feature_guard",
                "priority": 99,
                "requires_remote": False,
                "requires_secret": "",
                "command": (
                    "python -m iad_sieve.cli build-iad-model-feature-guard "
                    "--model-paths outputs/existing_model.json outputs/missing_model.json "
                    "--output-dir outputs/feature_guard"
                ),
                "expected_outputs": "outputs/feature_guard",
            }
        ],
        workspace_dir=tmp_path,
        remote_available=False,
        environment={},
    )

    assert rows[0]["status"] == "blocked_missing_input"
    assert rows[0]["missing_inputs"] == ["outputs/missing_model.json"]


def test_build_experiment_preflight_rows_checks_local_model_name_path(tmp_path) -> None:
    """验证 --model-name 指向本地 checkpoint 时会作为输入检查。"""
    _write_text(tmp_path / "outputs" / "docs.jsonl")
    _write_text(tmp_path / "outputs" / "pairs.jsonl")

    rows = build_experiment_preflight_rows(
        [
            {
                "task_id": "run_ditto_style_em",
                "priority": 40,
                "requires_remote": True,
                "requires_secret": "",
                "command": (
                    "python -m iad_sieve.cli run-entity-matching-baseline "
                    "--documents outputs/docs.jsonl "
                    "--pairs outputs/pairs.jsonl "
                    "--model-name outputs/models/ditto_style_em_source_heldout "
                    "--output outputs/ditto_scores.jsonl"
                ),
                "expected_outputs": "outputs/ditto_scores.jsonl",
            }
        ],
        workspace_dir=tmp_path,
        remote_available=True,
        environment={},
    )

    assert rows[0]["status"] == "blocked_missing_input"
    assert rows[0]["missing_inputs"] == ["outputs/models/ditto_style_em_source_heldout"]


def test_build_experiment_preflight_rows_ignores_remote_model_name(tmp_path) -> None:
    """验证 Hugging Face model id 不会被误判为本地输入路径。"""
    _write_text(tmp_path / "outputs" / "docs.jsonl")
    _write_text(tmp_path / "outputs" / "pairs.jsonl")

    rows = build_experiment_preflight_rows(
        [
            {
                "task_id": "run_roberta_pair",
                "priority": 37,
                "requires_remote": True,
                "requires_secret": "",
                "command": (
                    "python -m iad_sieve.cli run-entity-matching-baseline "
                    "--documents outputs/docs.jsonl "
                    "--pairs outputs/pairs.jsonl "
                    "--model-name textattack/roberta-base-MRPC "
                    "--output outputs/roberta_scores.jsonl"
                ),
                "expected_outputs": "outputs/roberta_scores.jsonl",
            }
        ],
        workspace_dir=tmp_path,
        remote_available=True,
        environment={},
    )

    assert rows[0]["status"] == "ready_to_run"
    assert rows[0]["missing_inputs"] == []


def test_write_experiment_preflight_outputs_writes_jsonl_csv_and_markdown(tmp_path) -> None:
    """验证 preflight 写出 JSONL、CSV 和 Markdown。"""
    output_dir = tmp_path / "experiment_preflight"
    rows = [
        {
            "task_id": "run_specter2_adapter",
            "priority": 1,
            "status": "blocked_remote_required",
            "missing_input_count": 0,
            "missing_output_count": 1,
            "requires_remote": True,
            "remote_status": "required_missing",
            "requires_secret": "",
            "secret_status": "not_required",
            "command_status": "valid",
            "expected_outputs": ["outputs/specter2_scores.jsonl"],
            "missing_inputs": [],
            "missing_outputs": ["outputs/specter2_scores.jsonl"],
            "next_action": "准备远程/GPU 环境后执行该任务。",
        }
    ]

    write_experiment_preflight_outputs(rows, output_dir)

    assert read_records(output_dir / "experiment_preflight.jsonl")[0]["status"] == "blocked_remote_required"
    assert (output_dir / "experiment_preflight.csv").exists()
    assert "# Experiment Preflight" in (output_dir / "experiment_preflight.md").read_text(encoding="utf-8")


def test_check_experiment_queue_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 preflight 报告。"""
    queue = tmp_path / "experiment_queue.jsonl"
    output_dir = tmp_path / "experiment_preflight"
    _write_jsonl(
        queue,
        [
            {
                "task_id": "run_missing_input",
                "priority": 1,
                "requires_remote": False,
                "requires_secret": "",
                "command": "python -m iad_sieve.cli run-representation-baseline --documents outputs/docs.jsonl --output outputs/scores.jsonl",
                "expected_outputs": "outputs/scores.jsonl",
            }
        ],
    )

    command_check_experiment_queue(
        Namespace(
            queue=str(queue),
            output_dir=str(output_dir),
            workspace_dir=str(tmp_path),
            remote_available=False,
        )
    )

    assert read_records(output_dir / "experiment_preflight.jsonl")[0]["status"] == "blocked_missing_input"
    assert (output_dir / "experiment_preflight.md").exists()


def test_cli_includes_check_experiment_queue_command() -> None:
    """验证 CLI 暴露 check-experiment-queue 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "check-experiment-queue",
            "--queue",
            "outputs/experiment_queue_fixture/experiment_queue.jsonl",
            "--output-dir",
            "outputs/experiment_preflight_fixture",
            "--workspace-dir",
            ".",
        ]
    )

    assert args.command == "check-experiment-queue"
    assert args.queue == "outputs/experiment_queue_fixture/experiment_queue.jsonl"
