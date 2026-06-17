"""测试主轨道远程就绪审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_primary_remote_readiness
from iad_sieve.evaluation.primary_remote_readiness import (
    build_primary_remote_readiness_rows,
    write_primary_remote_readiness_outputs,
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


def test_build_primary_remote_readiness_rows_separates_primary_secret_from_global_secret() -> None:
    """验证主轨道就绪审计不把全局 API key 阻塞算入主轨道。"""
    rows = build_primary_remote_readiness_rows(
        remote_input_request_rows=[
            {
                "request_id": "connection:remote_host",
                "request_type": "connection_field",
                "field_name": "remote_host",
                "status": "waiting_for_user",
                "required": True,
            },
            {
                "request_id": "secret:OPENAI_API_KEY",
                "request_type": "secret_configuration",
                "field_name": "OPENAI_API_KEY",
                "status": "waiting_for_secure_configuration",
                "required": True,
            },
        ],
        remote_execution_slice_rows=[
            {
                "slice_id": "track:open_v3_scholarly_balanced_gold",
                "slice_type": "advanced_track_execution",
                "evaluation_track": "open_v3_scholarly_balanced_gold",
                "priority": 150,
                "source_task_ids": ["run_iad", "run_roberta", "run_scincl"],
                "required_secret_names": [],
                "missing_outputs": ["outputs/main/summary.jsonl"],
            },
            {
                "slice_id": "track:open_v2",
                "slice_type": "advanced_track_execution",
                "evaluation_track": "open_v2",
                "priority": 157,
                "source_task_ids": ["run_llm"],
                "required_secret_names": ["OPENAI_API_KEY"],
            },
        ],
        remote_slice_run_pack_rows=[
            {
                "item_id": "slice_script:open_v3_scholarly_balanced_gold",
                "item_type": "slice_script",
                "slice_id": "track:open_v3_scholarly_balanced_gold",
                "evaluation_track": "open_v3_scholarly_balanced_gold",
                "template_path": "run_remote_slice_open_v3_scholarly_balanced_gold.template.sh",
                "command_count": 3,
                "required_secret_names": [],
                "missing_task_ids": [],
            },
            {
                "item_id": "slice_script:open_v2",
                "item_type": "slice_script",
                "slice_id": "track:open_v2",
                "evaluation_track": "open_v2",
                "template_path": "run_remote_slice_open_v2.template.sh",
                "command_count": 1,
                "required_secret_names": ["OPENAI_API_KEY"],
                "missing_task_ids": [],
            },
        ],
    )
    row = rows[0]

    assert row["readiness_id"] == "primary_track_remote_readiness"
    assert row["primary_track"] == "open_v3_scholarly_balanced_gold"
    assert row["primary_track_task_count"] == 3
    assert row["primary_template_path"] == "outputs/remote_slice_run_pack_fixture/run_remote_slice_open_v3_scholarly_balanced_gold.template.sh"
    assert row["missing_connection_fields"] == ["remote_host"]
    assert row["primary_required_secret_names"] == []
    assert row["missing_primary_secret_names"] == []
    assert row["deferred_global_secret_names"] == ["OPENAI_API_KEY"]
    assert row["readiness_status"] == "blocked_missing_connection"
    assert "先运行主轨道切片脚本" in row["next_action"]


def test_build_primary_remote_readiness_rows_reports_unmapped_primary_tasks() -> None:
    """验证主轨道无可执行任务映射时不误报为缺少脚本。"""
    rows = build_primary_remote_readiness_rows(
        remote_input_request_rows=[
            {
                "request_id": "connection:remote_host",
                "request_type": "connection_field",
                "field_name": "remote_host",
                "status": "provided",
                "required": True,
            }
        ],
        remote_execution_slice_rows=[
            {
                "slice_id": "track:open_v3_scholarly_balanced_gold_source_heldout",
                "slice_type": "advanced_track_execution",
                "evaluation_track": "open_v3_scholarly_balanced_gold_source_heldout",
                "priority": 151,
                "source_task_ids": [],
                "required_secret_names": [],
                "unmapped_systems": [
                    "ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
                    "gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout",
                ],
            }
        ],
        remote_slice_run_pack_rows=[],
    )
    row = rows[0]

    assert row["readiness_status"] == "blocked_unmapped_primary_tasks"
    assert row["primary_track_task_count"] == 0
    assert row["primary_template_path"] == ""
    assert row["unmapped_systems"] == [
        "ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
        "gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout",
    ]
    assert "补齐实验队列" in row["next_action"]
    assert "不要重复执行已验收" in row["next_action"]


def test_build_primary_remote_readiness_rows_reports_primary_secret_blocker() -> None:
    """验证主轨道任务需要 API key 时给出主轨道密钥阻塞动作。"""
    rows = build_primary_remote_readiness_rows(
        remote_input_request_rows=[
            {
                "request_id": "connection:remote_host",
                "request_type": "connection_field",
                "field_name": "remote_host",
                "status": "provided",
                "required": True,
            },
            {
                "request_id": "secret:OPENAI_API_KEY",
                "request_type": "secret_configuration",
                "field_name": "OPENAI_API_KEY",
                "status": "waiting_for_secure_configuration",
                "required": True,
            },
        ],
        remote_execution_slice_rows=[
            {
                "slice_id": "track:open_v3_scholarly_balanced_gold_source_heldout",
                "slice_type": "advanced_track_execution",
                "evaluation_track": "open_v3_scholarly_balanced_gold_source_heldout",
                "priority": 151,
                "source_task_ids": ["run_ditto", "run_gpt"],
                "required_secret_names": ["OPENAI_API_KEY"],
                "missing_outputs": ["outputs/ditto.jsonl", "outputs/gpt.jsonl"],
            }
        ],
        remote_slice_run_pack_rows=[
            {
                "item_id": "slice_script:open_v3_scholarly_balanced_gold_source_heldout",
                "item_type": "slice_script",
                "slice_id": "track:open_v3_scholarly_balanced_gold_source_heldout",
                "evaluation_track": "open_v3_scholarly_balanced_gold_source_heldout",
                "template_path": "run_remote_slice_open_v3_scholarly_balanced_gold_source_heldout.template.sh",
                "command_count": 2,
                "required_secret_names": ["OPENAI_API_KEY"],
                "missing_task_ids": [],
            }
        ],
    )
    row = rows[0]

    assert row["readiness_status"] == "blocked_missing_primary_secret"
    assert row["missing_connection_fields"] == []
    assert row["missing_primary_secret_names"] == ["OPENAI_API_KEY"]
    assert row["deferred_global_secret_names"] == []
    assert "主轨道密钥" in row["next_action"]
    assert "不阻塞 open_v3 scholarly 主轨道" not in row["next_action"]


def test_build_primary_remote_readiness_rows_reports_missing_model_artifact() -> None:
    """验证本地 LLM 权重目录缺失时主轨道不误报为可执行。"""
    rows = build_primary_remote_readiness_rows(
        remote_input_request_rows=[
            {
                "request_id": "connection:remote_host",
                "request_type": "connection_field",
                "field_name": "remote_host",
                "status": "provided",
                "required": True,
            },
            {
                "request_id": "model_artifact:outputs/models/local_llm_judge",
                "request_type": "model_artifact",
                "field_name": "outputs/models/local_llm_judge",
                "status": "waiting_for_user",
                "required": True,
            },
        ],
        remote_execution_slice_rows=[
            {
                "slice_id": "track:open_v3_scholarly_balanced_gold_source_heldout",
                "slice_type": "advanced_track_execution",
                "evaluation_track": "open_v3_scholarly_balanced_gold_source_heldout",
                "priority": 151,
                "source_task_ids": ["run_gpt"],
                "required_secret_names": [],
                "missing_outputs": ["outputs/gpt.jsonl"],
            }
        ],
        remote_slice_run_pack_rows=[
            {
                "item_id": "slice_script:open_v3_scholarly_balanced_gold_source_heldout",
                "item_type": "slice_script",
                "slice_id": "track:open_v3_scholarly_balanced_gold_source_heldout",
                "evaluation_track": "open_v3_scholarly_balanced_gold_source_heldout",
                "template_path": "run_remote_slice_open_v3_scholarly_balanced_gold_source_heldout.template.sh",
                "command_count": 1,
                "required_secret_names": [],
                "missing_task_ids": [],
            },
            {
                "item_id": "slice_task:open_v3_scholarly_balanced_gold_source_heldout:run_gpt",
                "item_type": "slice_task_command",
                "slice_id": "track:open_v3_scholarly_balanced_gold_source_heldout",
                "command": (
                    "python -m iad_sieve.cli run-llm-judge-baseline "
                    "--model-name outputs/models/local_llm_judge"
                ),
            },
        ],
    )
    row = rows[0]

    assert row["readiness_status"] == "blocked_missing_model_artifact"
    assert row["missing_model_artifacts"] == ["outputs/models/local_llm_judge"]
    assert "预置主轨道模型目录" in row["next_action"]
    assert "outputs/models/local_llm_judge" in row["next_action"]


def test_write_primary_remote_readiness_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证主轨道远程就绪审计写出报告和摘要。"""
    rows = [
        {
            "readiness_id": "primary_track_remote_readiness",
            "readiness_status": "blocked_missing_connection",
            "primary_track": "open_v3_scholarly_balanced_gold",
            "primary_template_path": "outputs/remote_slice_run_pack_fixture/run_remote_slice_open_v3_scholarly_balanced_gold.template.sh",
            "primary_track_task_count": 3,
            "missing_connection_fields": ["remote_host"],
            "primary_required_secret_names": [],
            "missing_primary_secret_names": [],
            "missing_model_artifacts": [],
            "deferred_global_secret_names": ["OPENAI_API_KEY"],
            "next_action": "先运行主轨道切片脚本。",
            "paper_claim_boundary": "远程输出未验收前不得写强模型完成。",
        }
    ]
    output_dir = tmp_path / "primary_remote_readiness"

    write_primary_remote_readiness_outputs(rows, output_dir)

    assert read_records(output_dir / "primary_remote_readiness.jsonl")[0]["primary_track_task_count"] == 3
    assert (output_dir / "primary_remote_readiness.csv").exists()
    markdown = (output_dir / "primary_remote_readiness.md").read_text(encoding="utf-8")
    assert "# Primary Remote Readiness" in markdown
    assert "OPENAI_API_KEY" in markdown
    summary = read_records(output_dir / "primary_remote_readiness_summary.jsonl")[0]
    assert summary["primary_track"] == "open_v3_scholarly_balanced_gold"
    assert summary["missing_connection_field_count"] == 1
    assert summary["missing_primary_secret_count"] == 0
    assert summary["missing_model_artifact_count"] == 0
    assert summary["deferred_global_secret_count"] == 1
    assert summary["primary_remote_ready"] is False


def test_build_primary_remote_readiness_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出主轨道远程就绪审计。"""
    remote_input = tmp_path / "remote_input_request.jsonl"
    remote_slice = tmp_path / "remote_execution_slice.jsonl"
    remote_run_pack = tmp_path / "remote_slice_run_pack.jsonl"
    output_dir = tmp_path / "primary_remote_readiness"
    _write_jsonl(
        remote_input,
        [
            {
                "request_id": "connection:remote_host",
                "request_type": "connection_field",
                "field_name": "remote_host",
                "status": "provided",
                "required": True,
            }
        ],
    )
    _write_jsonl(
        remote_slice,
        [
            {
                "slice_id": "track:open_v3",
                "slice_type": "advanced_track_execution",
                "evaluation_track": "open_v3",
                "priority": 150,
                "source_task_ids": ["run_open_v3"],
                "required_secret_names": [],
            }
        ],
    )
    _write_jsonl(
        remote_run_pack,
        [
            {
                "item_id": "slice_script:open_v3",
                "item_type": "slice_script",
                "slice_id": "track:open_v3",
                "evaluation_track": "open_v3",
                "template_path": "run_remote_slice_open_v3.template.sh",
                "command_count": 1,
                "required_secret_names": [],
                "missing_task_ids": [],
            }
        ],
    )

    command_build_primary_remote_readiness(
        Namespace(
            remote_input_request=str(remote_input),
            remote_execution_slice=str(remote_slice),
            remote_slice_run_pack=str(remote_run_pack),
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "primary_remote_readiness_summary.jsonl").exists()
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-primary-remote-readiness",
            "--remote-input-request",
            str(remote_input),
            "--remote-execution-slice",
            str(remote_slice),
            "--remote-slice-run-pack",
            str(remote_run_pack),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_primary_remote_readiness
