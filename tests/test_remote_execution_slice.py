"""测试远程执行切片。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_remote_execution_slice
from iad_sieve.evaluation.remote_execution_slice import build_remote_execution_slice_rows, write_remote_execution_slice_outputs
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


def test_build_remote_execution_slice_rows_prioritizes_inputs_and_primary_track() -> None:
    """验证远程执行切片先阻塞输入，再执行主轨道强模型。"""
    action_rows = [
        {
            "action_id": "close_advanced_track:open_v3_scholarly_balanced_gold",
            "action_type": "advanced_evidence_track_gap",
            "priority": 150,
            "status": "blocked_remote_required",
            "evaluation_track": "open_v3_scholarly_balanced_gold",
            "source_task_ids": ["run_main", "run_roberta", "run_scincl"],
            "mapped_task_count": 3,
            "execution_stages": ["0"],
            "missing_outputs": ["outputs/main/summary.jsonl", "outputs/roberta/summary.jsonl"],
            "unmapped_systems": [],
            "next_action": "运行主轨道强模型。",
            "acceptance_evidence": "主轨道证据闭环。",
            "paper_claim_boundary": "未完成前不能写 SOTA。",
        },
        {
            "action_id": "close_advanced_track:open_v2",
            "action_type": "advanced_evidence_track_gap",
            "priority": 157,
            "status": "blocked_remote_required",
            "evaluation_track": "open_v2",
            "source_task_ids": ["run_open_v2"],
            "mapped_task_count": 1,
            "execution_stages": ["0"],
            "missing_outputs": ["outputs/open_v2/summary.jsonl"],
            "unmapped_systems": [],
        },
    ]
    connection_rows = [
        {
            "item_id": "stage_command:0",
            "item_type": "stage_command",
            "execution_stage": 0,
            "task_ids": ["run_main", "run_roberta", "run_scincl", "run_open_v2"],
            "requires_secret_names": ["OPENAI_API_KEY"],
        },
        {
            "item_id": "stage_command:3",
            "item_type": "stage_command",
            "execution_stage": 3,
            "task_ids": ["rebuild_package"],
        },
    ]
    remote_input_rows = [
        {
            "request_id": "connection:remote_host",
            "request_type": "connection_field",
            "field_name": "remote_host",
            "status": "waiting_for_user",
        },
        {
            "request_id": "secret:OPENAI_API_KEY",
            "request_type": "secret_configuration",
            "field_name": "OPENAI_API_KEY",
            "status": "waiting_for_secure_configuration",
        },
    ]

    rows = build_remote_execution_slice_rows(action_rows, connection_rows, remote_input_rows)
    by_id = {row["slice_id"]: row for row in rows}
    primary = by_id["track:open_v3_scholarly_balanced_gold"]

    assert rows[0]["slice_id"] == "remote_inputs"
    assert by_id["remote_inputs"]["status"] == "blocked_until_remote_inputs_ready"
    assert by_id["remote_inputs"]["required_connection_fields"] == ["remote_host"]
    assert by_id["remote_inputs"]["required_secret_names"] == ["OPENAI_API_KEY"]
    assert primary["status"] == "blocked_until_remote_inputs_ready"
    assert primary["source_task_ids"] == ["run_main", "run_roberta", "run_scincl"]
    assert primary["mapped_task_count"] == 3
    assert primary["stage_command_ids"] == ["stage_command:0"]
    assert primary["required_stage_scripts"] == ["outputs/experiment_execution_pack_fixture/run_stage_00.sh"]
    assert primary["required_secret_names"] == ["OPENAI_API_KEY"]
    assert primary["missing_output_count"] == 2
    assert by_id["post_remote_validation_and_rebuild"]["required_stage_scripts"] == ["outputs/experiment_execution_pack_fixture/run_stage_03.sh"]


def test_build_remote_execution_slice_rows_prefers_task_level_secrets() -> None:
    """验证提供远程蓝图时按 root task 计算密钥需求。"""
    action_rows = [
        {
            "action_id": "close_advanced_track:open_v3_scholarly_balanced_gold",
            "action_type": "advanced_evidence_track_gap",
            "priority": 150,
            "evaluation_track": "open_v3_scholarly_balanced_gold",
            "source_task_ids": ["run_scincl", "run_roberta", "run_iad_risk"],
            "mapped_task_count": 3,
            "execution_stages": ["0"],
            "missing_outputs": ["outputs/main/summary.jsonl"],
        },
        {
            "action_id": "close_advanced_track:open_v2",
            "action_type": "advanced_evidence_track_gap",
            "priority": 157,
            "evaluation_track": "open_v2",
            "source_task_ids": ["run_llm"],
            "mapped_task_count": 1,
            "execution_stages": ["0"],
            "missing_outputs": ["outputs/llm/summary.jsonl"],
        },
    ]
    connection_rows = [
        {
            "item_id": "stage_command:0",
            "item_type": "stage_command",
            "execution_stage": 0,
            "task_ids": ["run_scincl", "run_roberta", "run_iad_risk", "run_llm"],
            "requires_secret_names": ["OPENAI_API_KEY"],
        }
    ]
    remote_input_rows = [
        {
            "request_id": "connection:remote_host",
            "request_type": "connection_field",
            "field_name": "remote_host",
            "status": "provided",
        }
    ]
    blueprint_rows = [
        {"blueprint_item_type": "root_execution_task", "task_id": "run_scincl", "requires_secret": ""},
        {"blueprint_item_type": "root_execution_task", "task_id": "run_roberta", "requires_secret": ""},
        {"blueprint_item_type": "root_execution_task", "task_id": "run_iad_risk", "requires_secret": ""},
        {"blueprint_item_type": "root_execution_task", "task_id": "run_llm", "requires_secret": "OPENAI_API_KEY"},
    ]

    rows = build_remote_execution_slice_rows(action_rows, connection_rows, remote_input_rows, remote_blueprint_rows=blueprint_rows)
    by_id = {row["slice_id"]: row for row in rows}

    assert by_id["track:open_v3_scholarly_balanced_gold"]["required_secret_names"] == []
    assert by_id["track:open_v2"]["required_secret_names"] == ["OPENAI_API_KEY"]


def test_build_remote_execution_slice_rows_allows_primary_when_only_deferred_secret_missing() -> None:
    """验证后续 API 密钥缺失不阻塞无密钥主轨道。"""
    action_rows = [
        {
            "action_id": "close_advanced_track:open_v3_scholarly_balanced_gold",
            "action_type": "advanced_evidence_track_gap",
            "priority": 150,
            "evaluation_track": "open_v3_scholarly_balanced_gold",
            "source_task_ids": ["run_scincl", "run_roberta", "run_iad_risk"],
            "mapped_task_count": 3,
            "execution_stages": ["0"],
            "missing_outputs": ["outputs/main/summary.jsonl"],
        },
        {
            "action_id": "close_advanced_track:open_v2",
            "action_type": "advanced_evidence_track_gap",
            "priority": 157,
            "evaluation_track": "open_v2",
            "source_task_ids": ["run_llm"],
            "mapped_task_count": 1,
            "execution_stages": ["0"],
            "missing_outputs": ["outputs/llm/summary.jsonl"],
        },
    ]
    connection_rows = [
        {
            "item_id": "stage_command:0",
            "item_type": "stage_command",
            "execution_stage": 0,
            "task_ids": ["run_scincl", "run_roberta", "run_iad_risk", "run_llm"],
            "requires_secret_names": ["OPENAI_API_KEY"],
        }
    ]
    remote_input_rows = [
        {
            "request_id": "connection:remote_host",
            "request_type": "connection_field",
            "field_name": "remote_host",
            "status": "provided",
        },
        {
            "request_id": "secret:OPENAI_API_KEY",
            "request_type": "secret_configuration",
            "field_name": "OPENAI_API_KEY",
            "status": "waiting_for_secure_configuration",
        },
    ]
    blueprint_rows = [
        {"blueprint_item_type": "root_execution_task", "task_id": "run_scincl", "requires_secret": ""},
        {"blueprint_item_type": "root_execution_task", "task_id": "run_roberta", "requires_secret": ""},
        {"blueprint_item_type": "root_execution_task", "task_id": "run_iad_risk", "requires_secret": ""},
        {"blueprint_item_type": "root_execution_task", "task_id": "run_llm", "requires_secret": "OPENAI_API_KEY"},
    ]

    rows = build_remote_execution_slice_rows(action_rows, connection_rows, remote_input_rows, remote_blueprint_rows=blueprint_rows)
    by_id = {row["slice_id"]: row for row in rows}

    assert by_id["remote_inputs"]["status"] == "ready_for_primary_track_blocked_for_deferred_secrets"
    assert by_id["remote_inputs"]["deferred_secret_names"] == ["OPENAI_API_KEY"]
    assert "具体可执行任务以 advanced_track_execution 切片状态为准" in by_id["remote_inputs"]["next_action"]
    assert by_id["track:open_v3_scholarly_balanced_gold"]["status"] == "ready_to_execute_remote_tasks"
    assert by_id["track:open_v3_scholarly_balanced_gold"]["required_secret_names"] == []
    assert by_id["track:open_v2"]["status"] == "blocked_until_required_secret_configuration"
    assert by_id["track:open_v2"]["required_secret_names"] == ["OPENAI_API_KEY"]


def test_build_remote_execution_slice_rows_blocks_when_model_artifact_missing() -> None:
    """验证本地模型目录缺失会阻塞远程输入与主轨道执行。"""
    action_rows = [
        {
            "action_id": "close_advanced_track:open_v3_scholarly_balanced_gold_source_heldout",
            "action_type": "advanced_evidence_track_gap",
            "priority": 150,
            "evaluation_track": "open_v3_scholarly_balanced_gold_source_heldout",
            "source_task_ids": ["run_gpt"],
            "mapped_task_count": 1,
            "execution_stages": ["0"],
            "missing_outputs": ["outputs/gpt.jsonl"],
        }
    ]
    connection_rows = [
        {
            "item_id": "stage_command:0",
            "item_type": "stage_command",
            "execution_stage": 0,
            "task_ids": ["run_gpt"],
            "requires_secret_names": [],
        }
    ]
    remote_input_rows = [
        {
            "request_id": "connection:remote_host",
            "request_type": "connection_field",
            "field_name": "remote_host",
            "status": "provided",
        },
        {
            "request_id": "model_artifact:outputs/models/local_llm_judge",
            "request_type": "model_artifact",
            "field_name": "outputs/models/local_llm_judge",
            "status": "waiting_for_user",
            "required": True,
        },
    ]

    rows = build_remote_execution_slice_rows(action_rows, connection_rows, remote_input_rows)
    by_id = {row["slice_id"]: row for row in rows}

    assert by_id["remote_inputs"]["status"] == "blocked_until_model_artifact"
    assert by_id["remote_inputs"]["required_model_artifacts"] == ["outputs/models/local_llm_judge"]
    assert "outputs/models/local_llm_judge" in by_id["remote_inputs"]["next_action"]
    assert by_id["track:open_v3_scholarly_balanced_gold_source_heldout"]["status"] == "blocked_until_remote_inputs_ready"


def test_build_remote_execution_slice_rows_blocks_when_primary_secret_missing() -> None:
    """验证主轨道需要密钥时 remote_inputs 不把密钥误归为 deferred。"""
    action_rows = [
        {
            "action_id": "close_advanced_track:open_v3_scholarly_balanced_gold_source_heldout",
            "action_type": "advanced_evidence_track_gap",
            "priority": 150,
            "evaluation_track": "open_v3_scholarly_balanced_gold_source_heldout",
            "source_task_ids": ["run_ditto", "run_gpt"],
            "mapped_task_count": 2,
            "execution_stages": ["0"],
            "missing_outputs": ["outputs/ditto.jsonl", "outputs/gpt.jsonl"],
        }
    ]
    connection_rows = [
        {
            "item_id": "stage_command:0",
            "item_type": "stage_command",
            "execution_stage": 0,
            "task_ids": ["run_ditto", "run_gpt"],
            "requires_secret_names": ["OPENAI_API_KEY"],
        }
    ]
    remote_input_rows = [
        {
            "request_id": "connection:remote_host",
            "request_type": "connection_field",
            "field_name": "remote_host",
            "status": "provided",
        },
        {
            "request_id": "secret:OPENAI_API_KEY",
            "request_type": "secret_configuration",
            "field_name": "OPENAI_API_KEY",
            "status": "waiting_for_secure_configuration",
        },
    ]
    blueprint_rows = [
        {"blueprint_item_type": "root_execution_task", "task_id": "run_ditto", "requires_secret": ""},
        {"blueprint_item_type": "root_execution_task", "task_id": "run_gpt", "requires_secret": "OPENAI_API_KEY"},
    ]

    rows = build_remote_execution_slice_rows(action_rows, connection_rows, remote_input_rows, remote_blueprint_rows=blueprint_rows)
    by_id = {row["slice_id"]: row for row in rows}

    assert by_id["remote_inputs"]["status"] == "blocked_until_primary_secret_configuration"
    assert by_id["remote_inputs"]["deferred_secret_names"] == []
    assert "主轨道密钥" in by_id["remote_inputs"]["next_action"]
    assert by_id["track:open_v3_scholarly_balanced_gold_source_heldout"]["status"] == "blocked_until_required_secret_configuration"
    assert by_id["track:open_v3_scholarly_balanced_gold_source_heldout"]["required_secret_names"] == ["OPENAI_API_KEY"]


def test_build_remote_execution_slice_rows_marks_unmapped_track() -> None:
    """验证未映射 system 会阻塞轨道切片。"""
    action_rows = [
        {
            "action_id": "close_advanced_track:open_v3",
            "action_type": "advanced_evidence_track_gap",
            "priority": 150,
            "evaluation_track": "open_v3",
            "source_task_ids": [],
            "mapped_task_count": 0,
            "execution_stages": [],
            "missing_outputs": [],
            "unmapped_systems": ["missing_system"],
        }
    ]
    remote_input_rows = [{"request_id": "connection:remote_host", "request_type": "connection_field", "field_name": "remote_host", "status": "provided"}]

    rows = build_remote_execution_slice_rows(action_rows, [], remote_input_rows)
    by_id = {row["slice_id"]: row for row in rows}

    assert by_id["remote_inputs"]["status"] == "ready"
    assert by_id["track:open_v3"]["status"] == "blocked_unmapped_remote_task"
    assert by_id["track:open_v3"]["unmapped_systems"] == ["missing_system"]
    assert "补齐实验队列任务或单独执行方案" in by_id["track:open_v3"]["next_action"]
    assert "不要重复执行已验收" in by_id["track:open_v3"]["next_action"]


def test_write_remote_execution_slice_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证远程执行切片写出 JSONL、CSV、Markdown 和摘要。"""
    rows = [
        {
            "slice_id": "remote_inputs",
            "slice_type": "remote_input_gate",
            "priority": -10,
            "status": "ready",
            "evaluation_track": "",
            "source_action_ids": [],
            "source_request_ids": [],
            "source_task_ids": [],
            "mapped_task_count": 0,
            "execution_stages": [],
            "stage_command_ids": [],
            "required_stage_scripts": [],
            "required_connection_fields": [],
            "required_secret_names": [],
            "missing_output_count": 0,
            "missing_outputs": [],
            "unmapped_systems": [],
            "next_action": "执行远程任务。",
        },
        {
            "slice_id": "track:open_v3",
            "slice_type": "advanced_track_execution",
            "priority": 150,
            "status": "ready_to_execute_remote_tasks",
            "evaluation_track": "open_v3",
            "mapped_task_count": 2,
            "missing_output_count": 3,
            "missing_outputs": ["a", "b", "c"],
            "unmapped_systems": [],
            "next_action": "执行主轨道。",
        },
    ]
    output_dir = tmp_path / "remote_execution_slice"

    write_remote_execution_slice_outputs(rows, output_dir)

    assert read_records(output_dir / "remote_execution_slice.jsonl")[0]["slice_id"] == "remote_inputs"
    assert (output_dir / "remote_execution_slice.csv").exists()
    assert "# Remote Execution Slice" in (output_dir / "remote_execution_slice.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "remote_execution_slice_summary.jsonl")[0]
    assert summary["slice_count"] == 2
    assert summary["track_slice_count"] == 1
    assert summary["blocked_slice_count"] == 0
    assert summary["primary_track"] == "open_v3"
    assert summary["primary_track_task_count"] == 2
    assert summary["primary_track_missing_output_count"] == 3
    assert summary["q2b_remote_execution_slice_ready"] is True


def test_build_remote_execution_slice_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出远程执行切片。"""
    action_board = tmp_path / "q2b_action_board.jsonl"
    connection_pack = tmp_path / "remote_connection_pack.jsonl"
    input_request = tmp_path / "remote_input_request.jsonl"
    execution_blueprint = tmp_path / "remote_execution_blueprint.jsonl"
    output_dir = tmp_path / "remote_execution_slice"
    _write_jsonl(
        action_board,
        [
            {
                "action_id": "close_advanced_track:open_v3",
                "action_type": "advanced_evidence_track_gap",
                "priority": 150,
                "evaluation_track": "open_v3",
                "source_task_ids": ["run_open_v3"],
                "mapped_task_count": 1,
                "execution_stages": ["0"],
                "missing_outputs": ["outputs/open_v3/summary.jsonl"],
            }
        ],
    )
    _write_jsonl(connection_pack, [{"item_id": "stage_command:0", "item_type": "stage_command", "execution_stage": 0, "task_ids": ["run_open_v3"]}])
    _write_jsonl(input_request, [{"request_id": "connection:remote_host", "request_type": "connection_field", "field_name": "remote_host", "status": "provided"}])
    _write_jsonl(execution_blueprint, [{"blueprint_item_type": "root_execution_task", "task_id": "run_open_v3", "requires_secret": ""}])

    command_build_remote_execution_slice(
        Namespace(
            q2b_action_board=str(action_board),
            remote_connection_pack=str(connection_pack),
            remote_input_request=str(input_request),
            remote_execution_blueprint=str(execution_blueprint),
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "remote_execution_slice_summary.jsonl").exists()
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-remote-execution-slice",
            "--q2b-action-board",
            str(action_board),
            "--remote-connection-pack",
            str(connection_pack),
            "--remote-input-request",
            str(input_request),
            "--remote-execution-blueprint",
            str(execution_blueprint),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_remote_execution_slice
