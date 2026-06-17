"""测试远程切片运行包。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_remote_slice_run_pack
from iad_sieve.evaluation.remote_slice_run_pack import (
    build_remote_slice_run_pack_rows,
    write_remote_slice_run_pack_outputs,
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


def test_build_remote_slice_run_pack_rows_maps_primary_track_without_openai_secret() -> None:
    """验证主轨道切片只映射自身任务且不继承无关 API 密钥。"""
    remote_slice_rows = [
        {
            "slice_id": "track:open_v3_scholarly_balanced_gold",
            "slice_type": "advanced_track_execution",
            "priority": 150,
            "status": "blocked_until_remote_inputs_ready",
            "evaluation_track": "open_v3_scholarly_balanced_gold",
            "source_task_ids": ["run_scincl", "run_roberta", "run_iad_risk"],
            "required_secret_names": [],
            "missing_outputs": ["outputs/main/summary.jsonl"],
            "paper_claim_boundary": "主轨道未闭环前不能声称强模型先进性。",
        },
        {
            "slice_id": "track:open_v2",
            "slice_type": "advanced_track_execution",
            "priority": 157,
            "status": "blocked_until_remote_inputs_ready",
            "evaluation_track": "open_v2",
            "source_task_ids": ["run_llm"],
            "required_secret_names": ["OPENAI_API_KEY"],
            "missing_outputs": ["outputs/llm/summary.jsonl"],
        },
    ]
    execution_rows = [
        {
            "task_id": "run_llm",
            "execution_stage": 0,
            "priority": 1,
            "pre_run_checks": ["check_secret:OPENAI_API_KEY"],
            "command": "python -m iad_sieve.cli run-llm-judge-baseline --api-key-env OPENAI_API_KEY",
        },
        {
            "task_id": "run_scincl",
            "execution_stage": 0,
            "priority": 2,
            "pre_run_checks": ["check_cuda"],
            "command": "python -m iad_sieve.cli run-representation-baseline --system-name scincl",
        },
        {
            "task_id": "run_roberta",
            "execution_stage": 0,
            "priority": 3,
            "pre_run_checks": ["check_cuda"],
            "command": "python -m iad_sieve.cli run-entity-matching-baseline --system-name roberta",
        },
        {
            "task_id": "run_iad_risk",
            "execution_stage": 0,
            "priority": 4,
            "pre_run_checks": ["check_cuda"],
            "command": "python -m iad_sieve.cli train-iad-risk-transformer-model --system-name iad_risk",
        },
    ]

    rows = build_remote_slice_run_pack_rows(remote_slice_rows, execution_rows)
    by_script = {row["slice_id"]: row for row in rows if row["item_type"] == "slice_script"}
    primary = by_script["track:open_v3_scholarly_balanced_gold"]
    primary_tasks = [
        row["task_id"]
        for row in rows
        if row["item_type"] == "slice_task_command" and row["slice_id"] == "track:open_v3_scholarly_balanced_gold"
    ]

    assert primary["command_count"] == 3
    assert primary["required_secret_names"] == []
    assert primary["missing_task_ids"] == []
    assert primary["template_path"] == "run_remote_slice_open_v3_scholarly_balanced_gold.template.sh"
    assert primary_tasks == ["run_scincl", "run_roberta", "run_iad_risk"]
    assert by_script["track:open_v2"]["required_secret_names"] == ["OPENAI_API_KEY"]


def test_write_remote_slice_run_pack_outputs_writes_secret_scoped_templates(tmp_path) -> None:
    """验证切片脚本只检查当前切片所需密钥。"""
    rows = [
        {
            "item_id": "slice_script:open_v3",
            "item_type": "slice_script",
            "slice_id": "track:open_v3_scholarly_balanced_gold",
            "slice_type": "advanced_track_execution",
            "evaluation_track": "open_v3_scholarly_balanced_gold",
            "priority": 150,
            "template_path": "run_remote_slice_open_v3_scholarly_balanced_gold.template.sh",
            "task_ids": ["run_scincl", "run_roberta", "run_iad_risk"],
            "required_secret_names": [],
            "missing_task_ids": [],
            "command_count": 3,
            "status": "blocked_until_remote_inputs_ready",
            "paper_claim_boundary": "主轨道未闭环前不能声称强模型先进性。",
        },
        {
            "item_id": "slice_task:open_v3:run_scincl",
            "item_type": "slice_task_command",
            "slice_id": "track:open_v3_scholarly_balanced_gold",
            "task_id": "run_scincl",
            "task_order": 1,
            "pre_run_checks": ["check_cuda"],
            "command": "python -m iad_sieve.cli run-representation-baseline --system-name scincl",
        },
        {
            "item_id": "slice_task:open_v3:run_roberta",
            "item_type": "slice_task_command",
            "slice_id": "track:open_v3_scholarly_balanced_gold",
            "task_id": "run_roberta",
            "task_order": 2,
            "pre_run_checks": ["check_cuda"],
            "command": "python -m iad_sieve.cli run-entity-matching-baseline --system-name roberta",
        },
        {
            "item_id": "slice_task:open_v3:run_iad_risk",
            "item_type": "slice_task_command",
            "slice_id": "track:open_v3_scholarly_balanced_gold",
            "task_id": "run_iad_risk",
            "task_order": 3,
            "pre_run_checks": ["check_cuda"],
            "command": "python -m iad_sieve.cli train-iad-risk-transformer-model --system-name iad_risk",
        },
        {
            "item_id": "slice_script:open_v2",
            "item_type": "slice_script",
            "slice_id": "track:open_v2",
            "slice_type": "advanced_track_execution",
            "evaluation_track": "open_v2",
            "priority": 157,
            "template_path": "run_remote_slice_open_v2.template.sh",
            "task_ids": ["run_llm"],
            "required_secret_names": ["OPENAI_API_KEY"],
            "missing_task_ids": [],
            "command_count": 1,
            "status": "blocked_until_remote_inputs_ready",
        },
        {
            "item_id": "slice_task:open_v2:run_llm",
            "item_type": "slice_task_command",
            "slice_id": "track:open_v2",
            "task_id": "run_llm",
            "task_order": 1,
            "pre_run_checks": ["check_secret:OPENAI_API_KEY"],
            "command": "python -m iad_sieve.cli run-llm-judge-baseline --api-key-env OPENAI_API_KEY",
        },
    ]
    output_dir = tmp_path / "remote_slice_run_pack"

    write_remote_slice_run_pack_outputs(rows, output_dir)

    assert read_records(output_dir / "remote_slice_run_pack.jsonl")[0]["item_type"] == "slice_script"
    assert (output_dir / "remote_slice_run_pack.csv").exists()
    assert "# Remote Slice Run Pack" in (output_dir / "remote_slice_run_pack.md").read_text(encoding="utf-8")
    primary_template = (output_dir / "run_remote_slice_open_v3_scholarly_balanced_gold.template.sh").read_text(encoding="utf-8")
    assert "run_scincl" in primary_template
    assert "run_roberta" in primary_template
    assert "run_iad_risk" in primary_template
    assert "run_llm" not in primary_template
    assert "OPENAI_API_KEY" not in primary_template
    assert "adapters" not in primary_template
    open_v2_template = (output_dir / "run_remote_slice_open_v2.template.sh").read_text(encoding="utf-8")
    assert "run_llm" in open_v2_template
    assert "OPENAI_API_KEY" in open_v2_template
    summary = read_records(output_dir / "remote_slice_run_pack_summary.jsonl")[0]
    assert summary["slice_script_count"] == 2
    assert summary["primary_track"] == "open_v3_scholarly_balanced_gold"
    assert summary["primary_track_required_secret_count"] == 0


def test_write_remote_slice_run_pack_outputs_checks_adapters_only_for_adapter_tasks(tmp_path) -> None:
    """验证 SPECTER2 adapter 任务才触发 adapters 依赖预检。"""
    rows = [
        {
            "item_id": "slice_script:open_v3",
            "item_type": "slice_script",
            "slice_id": "track:open_v3_scholarly_balanced_gold",
            "slice_type": "advanced_track_execution",
            "evaluation_track": "open_v3_scholarly_balanced_gold",
            "priority": 150,
            "template_path": "run_remote_slice_open_v3_scholarly_balanced_gold.template.sh",
            "task_ids": ["run_scincl"],
            "required_secret_names": [],
            "missing_task_ids": [],
            "command_count": 1,
            "status": "blocked_until_remote_inputs_ready",
        },
        {
            "item_id": "slice_task:open_v3:run_scincl",
            "item_type": "slice_task_command",
            "slice_id": "track:open_v3_scholarly_balanced_gold",
            "task_id": "run_scincl",
            "task_order": 1,
            "pre_run_checks": ["check_cuda"],
            "command": "python -m iad_sieve.cli run-representation-baseline --model-backend sentence-transformers --system-name scincl",
        },
        {
            "item_id": "slice_script:specter2",
            "item_type": "slice_script",
            "slice_id": "track:open_v2",
            "slice_type": "advanced_track_execution",
            "evaluation_track": "open_v2",
            "priority": 157,
            "template_path": "run_remote_slice_open_v2.template.sh",
            "task_ids": ["run_specter2"],
            "required_secret_names": [],
            "missing_task_ids": [],
            "command_count": 1,
            "status": "blocked_until_remote_inputs_ready",
        },
        {
            "item_id": "slice_task:specter2:run_specter2",
            "item_type": "slice_task_command",
            "slice_id": "track:open_v2",
            "task_id": "run_specter2",
            "task_order": 1,
            "pre_run_checks": ["check_cuda"],
            "command": "python -m iad_sieve.cli run-representation-baseline --model-backend specter2-adapter --adapter-model allenai/specter2",
        },
    ]
    output_dir = tmp_path / "remote_slice_run_pack"

    write_remote_slice_run_pack_outputs(rows, output_dir)

    primary_template = (output_dir / "run_remote_slice_open_v3_scholarly_balanced_gold.template.sh").read_text(encoding="utf-8")
    adapter_template = (output_dir / "run_remote_slice_open_v2.template.sh").read_text(encoding="utf-8")
    assert "sentence_transformers" in primary_template
    assert "adapters" not in primary_template
    assert "adapters" in adapter_template


def test_build_remote_slice_run_pack_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出远程切片运行包。"""
    remote_slice = tmp_path / "remote_execution_slice.jsonl"
    execution_plan = tmp_path / "experiment_execution_plan.jsonl"
    output_dir = tmp_path / "remote_slice_run_pack"
    _write_jsonl(
        remote_slice,
        [
            {
                "slice_id": "track:open_v3",
                "slice_type": "advanced_track_execution",
                "priority": 150,
                "evaluation_track": "open_v3",
                "source_task_ids": ["run_open_v3"],
                "required_secret_names": [],
            }
        ],
    )
    _write_jsonl(
        execution_plan,
        [
            {
                "task_id": "run_open_v3",
                "execution_stage": 0,
                "priority": 1,
                "pre_run_checks": ["check_cuda"],
                "command": "python -m iad_sieve.cli run-representation-baseline --system-name open_v3",
            }
        ],
    )

    command_build_remote_slice_run_pack(
        Namespace(
            remote_execution_slice=str(remote_slice),
            execution_plan=str(execution_plan),
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "remote_slice_run_pack_summary.jsonl").exists()
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-remote-slice-run-pack",
            "--remote-execution-slice",
            str(remote_slice),
            "--execution-plan",
            str(execution_plan),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_remote_slice_run_pack
