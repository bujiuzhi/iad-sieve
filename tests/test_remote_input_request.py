"""测试远程输入请求包。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_remote_input_request
from iad_sieve.evaluation.remote_input_request import build_remote_input_request_rows, write_remote_input_request_outputs
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


def test_build_remote_input_request_rows_marks_connection_and_secret_boundaries() -> None:
    """验证远程输入请求拆分连接字段、密钥配置和执行动作。"""
    connection_rows = [
        {
            "item_id": "connection_field:remote_host",
            "item_type": "connection_field",
            "field_name": "remote_host",
            "required": True,
            "status": "blocked_external_input",
            "paper_claim_boundary": "不能声称远程实验可复现。",
        },
        {
            "item_id": "connection_field:conda_env",
            "item_type": "connection_field",
            "field_name": "conda_env",
            "required": True,
            "status": "provided",
        },
        {
            "item_id": "secret_field:OPENAI_API_KEY",
            "item_type": "secret_field",
            "field_name": "OPENAI_API_KEY",
            "required": True,
            "status": "blocked_secret_configuration",
        },
        {
            "item_id": "model_artifact:outputs/models/local_llm_judge",
            "item_type": "model_artifact",
            "field_name": "outputs/models/local_llm_judge",
            "required": True,
            "status": "blocked_external_input",
        },
        {
            "item_id": "stage_command:0",
            "item_type": "stage_command",
            "task_count": 3,
        },
    ]
    roadmap_rows = [
        {
            "phase_id": "p0_remote_connection_and_secret",
            "reviewer_focus": "可复现性与 API 实验真实性",
            "required_actions": "补齐远程连接。",
            "paper_claim_boundary": "远程输入未就绪前不能写强模型完成。",
        }
    ]
    reviewer_rows = [
        {
            "iteration_id": "r0_remote_reproducibility",
            "reviewer_critique": "审稿人会质疑远程实验真实性。",
            "optimization_actions": "补齐远程连接 profile 与安全密钥配置后执行远程 stage 模板；在远程环境通过安全方式配置 OPENAI_API_KEY 后运行阶段脚本。",
            "paper_claim_boundary": "远程输出未验收前不能写强模型证据闭环。",
        }
    ]

    rows = build_remote_input_request_rows(connection_rows, roadmap_rows, reviewer_rows)
    by_id = {row["request_id"]: row for row in rows}

    assert by_id["connection:remote_host"]["status"] == "waiting_for_user"
    assert by_id["connection:remote_host"]["safe_to_store"] is True
    assert "服务器" in by_id["connection:remote_host"]["acceptable_input"]
    assert by_id["connection:conda_env"]["status"] == "provided"
    connection_next_action = by_id["connection:remote_host"]["next_action_after_provided"]
    assert "OPENAI_API_KEY" not in connection_next_action
    assert "安全密钥配置" not in connection_next_action
    assert "密钥配置" not in connection_next_action
    assert "远程连接" in connection_next_action
    assert by_id["secret:OPENAI_API_KEY"]["safe_to_store"] is False
    assert by_id["secret:OPENAI_API_KEY"]["value_policy"] == "remote_environment_only"
    assert "不要把 sk-" in by_id["secret:OPENAI_API_KEY"]["do_not_send"]
    assert "OPENAI_API_KEY" in by_id["secret:OPENAI_API_KEY"]["next_action_after_provided"]
    assert by_id["model_artifact:outputs/models/local_llm_judge"]["request_type"] == "model_artifact"
    assert by_id["model_artifact:outputs/models/local_llm_judge"]["status"] == "waiting_for_user"
    assert by_id["model_artifact:outputs/models/local_llm_judge"]["safe_to_store"] is True
    assert by_id["model_artifact:outputs/models/local_llm_judge"]["value_policy"] == "remote_project_path"
    assert "outputs/models/local_llm_judge" in by_id["model_artifact:outputs/models/local_llm_judge"]["acceptable_input"]
    assert by_id["execution:remote_stage_run"]["request_type"] == "post_input_execution"
    assert "3 个任务" in by_id["execution:remote_stage_run"]["why_needed"]


def test_write_remote_input_request_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证远程输入请求包写出 JSONL、CSV、Markdown 和摘要。"""
    rows = [
        {
            "request_id": "connection:remote_host",
            "request_type": "connection_field",
            "field_name": "remote_host",
            "required": True,
            "status": "waiting_for_user",
            "safe_to_store": True,
            "value_policy": "local_profile_or_shell_env_only",
            "acceptable_input": "远程服务器主机名或 IP。",
            "do_not_send": "不要发送密码。",
            "why_needed": "远程强模型实验需要。",
            "next_action_after_provided": "运行远程阶段脚本。",
            "paper_claim_boundary": "不能写强模型完成。",
            "source_item_ids": ["connection_field:remote_host"],
            "source_phase_ids": ["p0_remote_connection_and_secret"],
            "source_iteration_ids": ["r0_remote_reproducibility"],
        },
        {
            "request_id": "secret:OPENAI_API_KEY",
            "request_type": "secret_configuration",
            "field_name": "OPENAI_API_KEY",
            "required": True,
            "status": "waiting_for_secure_configuration",
            "safe_to_store": False,
            "value_policy": "remote_environment_only",
            "acceptable_input": "只说明已配置。",
            "do_not_send": "不要发送 sk- 密钥。",
            "why_needed": "LLM judge 需要。",
            "next_action_after_provided": "运行 API baseline。",
            "paper_claim_boundary": "不能写 API baseline 完成。",
            "source_item_ids": ["secret_field:OPENAI_API_KEY"],
            "source_phase_ids": [],
            "source_iteration_ids": [],
        },
        {
            "request_id": "model_artifact:outputs/models/local_llm_judge",
            "request_type": "model_artifact",
            "field_name": "outputs/models/local_llm_judge",
            "required": True,
            "status": "waiting_for_user",
            "safe_to_store": True,
            "value_policy": "remote_project_path",
            "acceptable_input": "远程项目目录下的模型目录 outputs/models/local_llm_judge。",
            "do_not_send": "不要发送密钥。",
            "why_needed": "本地 LLM judge 需要。",
            "next_action_after_provided": "预置模型后运行本地 LLM judge。",
            "paper_claim_boundary": "不能写 LLM judge 完成。",
            "source_item_ids": ["model_artifact:outputs/models/local_llm_judge"],
            "source_phase_ids": [],
            "source_iteration_ids": [],
        },
    ]
    output_dir = tmp_path / "remote_input_request"

    write_remote_input_request_outputs(rows, output_dir)

    assert read_records(output_dir / "remote_input_request.jsonl")[0]["request_id"] == "connection:remote_host"
    assert (output_dir / "remote_input_request.csv").exists()
    assert "# Remote Input Request" in (output_dir / "remote_input_request.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "remote_input_request_summary.jsonl")[0]
    assert summary["request_count"] == 3
    assert summary["missing_connection_field_count"] == 1
    assert summary["blocked_secret_configuration_count"] == 1
    assert summary["missing_model_artifact_count"] == 1
    assert summary["unsafe_to_store_count"] == 1
    assert summary["all_remote_inputs_ready"] is False
    assert summary["primary_track_ready_to_execute_remote_stages"] is False
    assert summary["requested_connection_fields"] == ["remote_host"]
    assert summary["requested_secret_names"] == ["OPENAI_API_KEY"]
    assert summary["requested_model_artifacts"] == ["outputs/models/local_llm_judge"]


def test_write_remote_input_request_outputs_marks_primary_track_ready_without_deferred_secret(tmp_path) -> None:
    """验证主轨道就绪状态不被后续 API 密钥增强阻塞。"""
    rows = [
        {
            "request_id": "connection:remote_host",
            "request_type": "connection_field",
            "field_name": "remote_host",
            "required": True,
            "status": "provided",
            "safe_to_store": True,
            "value_policy": "local_profile_or_shell_env_only",
            "acceptable_input": "远程服务器主机名或 IP。",
            "do_not_send": "不要发送密码。",
            "why_needed": "远程强模型实验需要。",
            "next_action_after_provided": "运行主轨道阶段脚本。",
            "paper_claim_boundary": "不能写强模型完成。",
            "source_item_ids": ["connection_field:remote_host"],
            "source_phase_ids": ["p0_remote_connection_and_secret"],
            "source_iteration_ids": ["r0_remote_reproducibility"],
        },
        {
            "request_id": "secret:OPENAI_API_KEY",
            "request_type": "secret_configuration",
            "field_name": "OPENAI_API_KEY",
            "required": True,
            "status": "waiting_for_secure_configuration",
            "safe_to_store": False,
            "value_policy": "remote_environment_only",
            "acceptable_input": "只说明已配置。",
            "do_not_send": "不要发送 sk- 密钥。",
            "why_needed": "LLM judge 需要。",
            "next_action_after_provided": "运行 API baseline。",
            "paper_claim_boundary": "不能写 API baseline 完成。",
            "source_item_ids": ["secret_field:OPENAI_API_KEY"],
            "source_phase_ids": [],
            "source_iteration_ids": [],
        },
    ]
    output_dir = tmp_path / "remote_input_request"

    write_remote_input_request_outputs(rows, output_dir)

    summary = read_records(output_dir / "remote_input_request_summary.jsonl")[0]
    assert summary["all_remote_inputs_ready"] is False
    assert summary["ready_to_execute_remote_stages"] is False
    assert summary["primary_track_ready_to_execute_remote_stages"] is True
    assert summary["deferred_secret_configuration_count"] == 1
    assert summary["primary_track_blocked_by_secret_configuration"] is False
    markdown = (output_dir / "remote_input_request.md").read_text(encoding="utf-8")
    assert "primary_track_ready_to_execute_remote_stages: True" in markdown
    assert "主轨道强模型阶段可在连接字段齐全后执行" in markdown
    assert "API/LLM 增强阶段" in markdown


def test_build_remote_input_request_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出远程输入请求包。"""
    connection_pack = tmp_path / "remote_connection_pack.jsonl"
    roadmap = tmp_path / "q2b_upgrade_roadmap.jsonl"
    output_dir = tmp_path / "remote_input_request"
    _write_jsonl(connection_pack, [{"item_id": "connection_field:remote_host", "item_type": "connection_field", "field_name": "remote_host", "status": "blocked_external_input"}])
    _write_jsonl(roadmap, [{"phase_id": "p0_remote_connection_and_secret", "status": "blocked"}])

    command_build_remote_input_request(
        Namespace(
            remote_connection_pack=str(connection_pack),
            q2b_roadmap=str(roadmap),
            reviewer_iteration=None,
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "remote_input_request_summary.jsonl").exists()
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-remote-input-request",
            "--remote-connection-pack",
            str(connection_pack),
            "--q2b-roadmap",
            str(roadmap),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_remote_input_request
