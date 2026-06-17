"""测试远程连接准备包。"""

from __future__ import annotations

import json
import importlib.util
import sys
import types
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_remote_connection_pack, command_build_remote_connection_profile
from iad_sieve.evaluation.remote_connection_pack import (
    build_remote_connection_profile,
    build_remote_connection_pack_rows_from_paths,
    build_remote_connection_pack_rows,
    _remote_preflight_python,
    write_remote_connection_profile,
    write_remote_connection_pack_outputs,
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


def test_build_remote_connection_pack_rows_marks_missing_connection_fields_and_keeps_secret_safe() -> None:
    """验证连接准备包标记缺失连接字段且不保存密钥值。"""
    execution_rows = [
        {
            "task_id": "run_scincl",
            "execution_stage": 0,
            "status": "blocked_remote_required",
            "requires_remote": True,
            "requires_secret": "",
            "command": "python -m iad_sieve.cli run-representation-baseline",
            "expected_outputs": ["outputs/strong/scincl_summary.jsonl"],
        },
        {
            "task_id": "run_llm",
            "execution_stage": 0,
            "status": "blocked_missing_input",
            "requires_remote": True,
            "requires_secret": "",
            "command": (
                "python -m iad_sieve.cli run-llm-judge-baseline "
                "--model-name outputs/models/local_llm_judge"
            ),
            "expected_outputs": ["outputs/llm/summary.jsonl"],
        },
        {
            "task_id": "train_ditto",
            "execution_stage": 0,
            "status": "blocked_remote_required",
            "requires_remote": True,
            "requires_secret": "",
            "command": "python -m iad_sieve.cli train-entity-matching-baseline --output-dir outputs/models/ditto_style_em",
            "expected_outputs": ["outputs/models/ditto_style_em"],
        },
        {
            "task_id": "run_ditto",
            "execution_stage": 0,
            "status": "blocked_missing_input",
            "requires_remote": True,
            "requires_secret": "",
            "command": (
                "python -m iad_sieve.cli run-entity-matching-baseline "
                "--model-name outputs/models/ditto_style_em"
            ),
            "expected_outputs": ["outputs/ditto/summary.jsonl"],
        },
    ]
    blueprint_rows = [
        {
            "blueprint_item_id": "root_task:run_scincl",
            "blueprint_item_type": "root_execution_task",
            "task_id": "run_scincl",
            "reviewer_risk_level": "high",
        }
    ]
    profile = {
        "remote_host": "gpu.example.com",
        "remote_user": "research",
        "remote_workspace": "/srv/iad-sieve",
        "conda_env": "iad-sieve",
    }

    rows = build_remote_connection_pack_rows(execution_rows, blueprint_rows, profile)
    by_id = {row["item_id"]: row for row in rows}

    assert by_id["connection_field:remote_port"]["status"] == "blocked_external_input"
    assert by_id["connection_field:ssh_key_path"]["status"] == "blocked_external_input"
    assert "secret_field:OPENAI_API_KEY" not in by_id
    assert by_id["model_artifact:outputs/models/local_llm_judge"]["status"] == "blocked_external_input"
    assert by_id["model_artifact:outputs/models/local_llm_judge"]["value_policy"] == "remote_project_path"
    assert "outputs/models/local_llm_judge" in by_id["model_artifact:outputs/models/local_llm_judge"]["next_action"]
    assert "model_artifact:outputs/models/ditto_style_em" not in by_id
    assert by_id["stage_command:0"]["status"] == "blocked_until_connection_ready"
    assert "ssh -p ${REMOTE_PORT}" in by_id["stage_command:0"]["command_template"]
    assert "run_stage_00.sh" in by_id["stage_command:0"]["command_template"]
    assert by_id["stage_command:0"]["required_outputs"] == [
        "outputs/strong/scincl_summary.jsonl",
        "outputs/llm/summary.jsonl",
        "outputs/models/ditto_style_em",
        "outputs/ditto/summary.jsonl",
    ]
    assert by_id["stage_command:0"]["requires_secret_names"] == []
    assert "OPENAI_API_KEY=" not in by_id["stage_command:0"]["command_template"]
    assert by_id["script_template:remote_sync_and_run"]["item_type"] == "script_template"
    assert by_id["script_template:remote_sync_and_run"]["status"] == "ready_template"
    assert by_id["script_template:remote_sync_and_run"]["template_path"] == "remote_sync_and_run.template.sh"
    assert by_id["script_template:remote_preflight"]["template_path"] == "remote_preflight.template.sh"
    assert by_id["script_template:remote_preflight"]["template_role"] == "preflight_only"
    assert by_id["script_template:remote_pull_outputs"]["template_path"] == "remote_pull_outputs.template.sh"
    assert by_id["reviewer_checkpoint:remote_connection"]["reviewer_risk_level"] == "high"


def test_write_remote_connection_pack_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证连接准备包写出报告、env 模板、profile 模板和汇总。"""
    rows = [
        {
            "item_id": "connection_field:remote_host",
            "item_type": "connection_field",
            "field_name": "remote_host",
            "status": "provided",
            "required": True,
            "safe_to_store": False,
            "reviewer_risk_level": "low",
            "next_action": "",
        },
        {
            "item_id": "connection_field:ssh_key_path",
            "item_type": "connection_field",
            "field_name": "ssh_key_path",
            "status": "blocked_external_input",
            "required": True,
            "safe_to_store": False,
            "reviewer_risk_level": "high",
            "next_action": "补充 SSH 私钥路径。",
        },
        {
            "item_id": "model_artifact:outputs/models/local_llm_judge",
            "item_type": "model_artifact",
            "field_name": "outputs/models/local_llm_judge",
            "status": "blocked_external_input",
            "required": True,
            "safe_to_store": True,
            "value_policy": "remote_project_path",
            "reviewer_risk_level": "high",
            "next_action": "预置 outputs/models/local_llm_judge。",
        },
        {
            "item_id": "stage_command:0",
            "item_type": "stage_command",
            "execution_stage": 0,
            "task_ids": ["run_scincl", "run_llm"],
            "required_outputs": ["outputs/strong/scincl_summary.jsonl", "outputs/llm/summary.jsonl"],
            "requires_secret_names": [],
            "status": "blocked_until_connection_ready",
            "command_template": "ssh -p ${REMOTE_PORT} ${REMOTE_USER}@${REMOTE_HOST} 'cd ${REMOTE_WORKSPACE} && bash outputs/experiment_execution_pack_fixture/run_stage_00.sh'",
            "reviewer_risk_level": "high",
            "next_action": "连接字段齐全后执行。",
        },
    ]
    output_dir = tmp_path / "remote_connection_pack"

    write_remote_connection_pack_outputs(rows, output_dir)

    assert read_records(output_dir / "remote_connection_pack.jsonl")[0]["item_type"] == "connection_field"
    assert (output_dir / "remote_connection_pack.csv").exists()
    markdown = (output_dir / "remote_connection_pack.md").read_text(encoding="utf-8")
    assert "# Remote Connection Pack" in markdown
    assert "blocked_external_input" in markdown
    assert "build-remote-connection-profile" in markdown
    assert "## 阶段运行手册" in markdown
    assert "run_scincl; run_llm" in markdown
    assert "outputs/strong/scincl_summary.jsonl; outputs/llm/summary.jsonl" in markdown
    assert "outputs/models/local_llm_judge" in markdown
    env_template = (output_dir / "remote_connection.env.example").read_text(encoding="utf-8")
    assert "REMOTE_HOST=" in env_template
    assert "OPENAI_API_KEY=" not in env_template
    profile_template = json.loads((output_dir / "remote_connection_profile.template.json").read_text(encoding="utf-8"))
    assert profile_template["remote_host"] == ""
    assert profile_template["remote_port"] == ""
    assert profile_template["configured_secrets"] == []
    assert profile_template["provided_model_artifacts"] == []
    assert profile_template["secret_configuration_note"] == "仅在远程环境已安全配置后，才把密钥变量名加入 configured_secrets。"
    assert "OPENAI_API_KEY" not in profile_template
    assert "api_key" not in profile_template
    sync_template = (output_dir / "remote_sync_and_run.template.sh").read_text(encoding="utf-8")
    assert "rsync" in sync_template
    assert "ssh" in sync_template
    assert "REMOTE_HOST" in sync_template
    assert "REMOTE_PORT" in sync_template
    assert "REMOTE_USER" in sync_template
    assert "SSH_KEY_PATH" in sync_template
    assert "REMOTE_WORKSPACE" in sync_template
    assert "CONDA_ENV" in sync_template
    assert 'REMOTE_CONDA_PATH="${REMOTE_CONDA_PATH:-conda}"' in sync_template
    assert 'REMOTE_CONDA_COMMAND="${REMOTE_CONDA_PATH} run -n ${CONDA_ENV}"' in sync_template
    assert "run_stage_00.sh" in sync_template
    assert "python scripts/check_cuda.py" in sync_template
    assert '&& ${REMOTE_CONDA_COMMAND} python scripts/check_cuda.py' in sync_template
    assert "remote_preflight_missing=" in sync_template
    assert "sentence_transformers" in sync_template
    assert "transformers" in sync_template
    assert "adapters" in sync_template
    assert "cuda_available" in sync_template
    assert 'os.environ.get(\\"OPENAI_API_KEY\\")' not in sync_template
    assert "outputs/models/local_llm_judge" in sync_template
    assert "config.json" in sync_template
    assert "not_causal_lm" in sync_template
    assert '--exclude "remote_connection.env"' in sync_template
    assert '--exclude "remote_connection.env.*"' in sync_template
    assert '--exclude "outputs/remote_connection_profile.local.json"' in sync_template
    assert sync_template.index("mkdir -p") < sync_template.index("rsync")
    assert sync_template.index("remote_preflight_missing=") < sync_template.index("run_stage_00.sh")
    assert "conda run -n" not in sync_template
    assert "OPENAI_API_KEY=" not in sync_template
    assert "sk-" not in sync_template
    assert "gpu.example.com" not in sync_template
    preflight_template = (output_dir / "remote_preflight.template.sh").read_text(encoding="utf-8")
    assert "rsync" not in preflight_template
    assert "run_stage_00.sh" not in preflight_template
    assert "remote_preflight_missing=" in preflight_template
    assert 'REMOTE_CONDA_PATH="${REMOTE_CONDA_PATH:-conda}"' in preflight_template
    assert 'REMOTE_CONDA_COMMAND="${REMOTE_CONDA_PATH} run -n ${CONDA_ENV}"' in preflight_template
    assert "sentence_transformers" in preflight_template
    assert "cuda_available" in preflight_template
    assert 'os.environ.get("OPENAI_API_KEY")' not in preflight_template
    assert "outputs/models/local_llm_judge" in preflight_template
    assert "config.json" in preflight_template
    assert "not_causal_lm" in preflight_template
    assert '\\"sentence_transformers\\"' in preflight_template
    assert "OPENAI_API_KEY=" not in preflight_template
    assert "conda run -n" not in preflight_template
    assert "sk-" not in preflight_template
    pull_template = (output_dir / "remote_pull_outputs.template.sh").read_text(encoding="utf-8")
    assert "rsync" in pull_template
    assert "outputs/" in pull_template
    assert "validate-remote-outputs" in pull_template
    assert "remote_output_manifest.jsonl" in pull_template
    assert "build-remote-result-acceptance" in pull_template
    assert "experiment_execution_plan.jsonl" in pull_template
    assert "remote_result_acceptance_fixture" in pull_template
    assert "run_stage_03.sh" in pull_template
    assert pull_template.index("validate-remote-outputs") < pull_template.index("build-remote-result-acceptance")
    assert pull_template.index("build-remote-result-acceptance") < pull_template.index("run_stage_03.sh")
    assert "OPENAI_API_KEY=" not in pull_template
    assert "sk-" not in pull_template
    assert "gpu.example.com" not in pull_template
    runbook = (output_dir / "remote_execution_runbook.md").read_text(encoding="utf-8")
    assert "# Remote Execution Runbook" in runbook
    assert "## 连接信息填写清单" in runbook
    assert "build-remote-connection-profile" in runbook
    assert "## 阶段 0" in runbook
    assert "run_scincl" in runbook
    assert "run_llm" in runbook
    assert "outputs/strong/scincl_summary.jsonl" in runbook
    assert "outputs/models/local_llm_judge" in runbook
    assert "ssh -p ${REMOTE_PORT}" in runbook
    assert "OPENAI_API_KEY=" not in runbook
    assert "sk-" not in runbook
    assert "gpu.example.com" not in runbook
    summary = read_records(output_dir / "remote_connection_pack_summary.jsonl")[0]
    assert summary["all_connection_fields_ready"] is False
    assert summary["missing_required_field_count"] == 1
    assert summary["missing_model_artifact_count"] == 1
    assert summary["all_remote_run_inputs_ready"] is False
    assert summary["stage_command_count"] == 1
    assert summary["script_template_count"] == 3


def test_build_remote_connection_pack_marks_provided_model_artifact_ready() -> None:
    """验证 profile 声明已预置模型工件时远程输入门禁不再阻塞该模型。"""
    execution_rows = [
        {
            "task_id": "run_llm",
            "execution_stage": 0,
            "requires_remote": True,
            "requires_secret": "",
            "command": "python -m iad_sieve.cli run-llm-judge-baseline --model-name outputs/models/local_llm_judge",
        }
    ]
    profile = {
        "remote_host": "gpu.example.com",
        "remote_port": "22",
        "remote_user": "research",
        "ssh_key_path": "~/.ssh/id_iad_sieve",
        "remote_workspace": "/srv/iad-sieve",
        "conda_env": "iad-sieve",
        "provided_model_artifacts": ["outputs/models/local_llm_judge"],
    }

    rows = build_remote_connection_pack_rows(execution_rows, [], profile)
    by_id = {row["item_id"]: row for row in rows}

    assert by_id["model_artifact:outputs/models/local_llm_judge"]["status"] == "provided_out_of_band"
    assert by_id["model_artifact:outputs/models/local_llm_judge"]["value_present"] is True
    assert by_id["model_artifact:outputs/models/local_llm_judge"]["next_action"] == ""
    assert all(row["status"] == "provided" for row in rows if row.get("item_type") == "connection_field")



def test_remote_preflight_python_rejects_sequence_classifier_model_artifact(tmp_path, monkeypatch, capsys) -> None:
    """验证远程预检脚本拒绝把分类器目录误当成本地 LLM judge。"""
    classifier_model = tmp_path / "classifier_model"
    classifier_model.mkdir()
    (classifier_model / "config.json").write_text(
        json.dumps({"architectures": ["RobertaForSequenceClassification"], "model_type": "roberta"}),
        encoding="utf-8",
    )
    causal_model = tmp_path / "causal_model"
    causal_model.mkdir()
    (causal_model / "config.json").write_text(
        json.dumps({"architectures": ["Qwen2ForCausalLM"], "model_type": "qwen2"}),
        encoding="utf-8",
    )
    real_find_spec = importlib.util.find_spec

    def fake_find_spec(module_name: str):
        """为远程预检脚本模拟已安装依赖。

        参数:
            module_name: 模块名。

        返回:
            模拟的模块 spec 或真实查询结果。
        """
        if module_name in {"sentence_transformers", "torch", "transformers", "adapters"}:
            return object()
        return real_find_spec(module_name)

    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = types.SimpleNamespace(is_available=lambda: True)
    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    script = _remote_preflight_python([], [str(classifier_model), str(causal_model)])

    try:
        exec(script, {})
    except SystemExit as exc:
        assert exc.code == 1

    output = capsys.readouterr().out
    assert f"{classifier_model}:not_causal_lm" in output
    assert f"{causal_model}:not_causal_lm" not in output


def test_build_remote_connection_pack_rejects_profile_with_secret_values(tmp_path) -> None:
    """验证 profile 中出现密钥值或敏感字段时拒绝读取。"""
    execution_plan = tmp_path / "experiment_execution_plan.jsonl"
    remote_blueprint = tmp_path / "remote_execution_blueprint.jsonl"
    profile = tmp_path / "remote_profile.json"
    _write_jsonl(
        execution_plan,
        [
            {
                "task_id": "run_llm",
                "execution_stage": 0,
                "requires_secret": "OPENAI_API_KEY",
                "command": "python -m iad_sieve.cli run-llm-judge-baseline",
            }
        ],
    )
    _write_jsonl(remote_blueprint, [{"blueprint_item_id": "root_task:run_llm", "blueprint_item_type": "root_execution_task"}])
    profile.write_text(
        json.dumps(
            {
                "remote_host": "gpu.example.com",
                "OPENAI_API_KEY": "sk-should-not-be-here",
                "configured_secrets": {"OPENAI_API_KEY": "sk-should-not-be-here"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    try:
        build_remote_connection_pack_rows_from_paths(execution_plan, remote_blueprint, profile)
    except ValueError as exc:
        assert "不得包含密钥字段或密钥值" in str(exc)
    else:
        raise AssertionError("profile 包含密钥字段时应拒绝读取")


def test_build_remote_connection_profile_uses_environment_without_secret_values() -> None:
    """验证本地 profile 可从环境变量构建且只保存密钥变量名。"""
    profile = build_remote_connection_profile(
        environment={
            "REMOTE_HOST": "gpu.example.com",
            "REMOTE_PORT": "22",
            "REMOTE_USER": "research",
            "SSH_KEY_PATH": "~/.ssh/id_iad_sieve",
            "REMOTE_WORKSPACE": "/srv/iad-sieve",
            "CONDA_ENV": "iad-sieve",
            "REMOTE_CONDA_PATH": "/opt/conda/bin/conda",
        },
        configured_secrets=["OPENAI_API_KEY"],
        provided_model_artifacts=["outputs/models/local_llm_judge"],
    )

    assert profile["remote_host"] == "gpu.example.com"
    assert profile["remote_port"] == "22"
    assert profile["remote_user"] == "research"
    assert profile["ssh_key_path"] == "~/.ssh/id_iad_sieve"
    assert profile["remote_workspace"] == "/srv/iad-sieve"
    assert profile["conda_env"] == "iad-sieve"
    assert profile["remote_conda_path"] == "/opt/conda/bin/conda"
    assert profile["configured_secrets"] == ["OPENAI_API_KEY"]
    assert profile["provided_model_artifacts"] == ["outputs/models/local_llm_judge"]
    assert "sk-" not in json.dumps(profile, ensure_ascii=False)
    assert "should-not-be-here" not in json.dumps(profile, ensure_ascii=False)


def test_build_remote_connection_profile_rejects_secret_values() -> None:
    """验证本地 profile 构建拒绝密钥值和私钥内容。"""
    try:
        build_remote_connection_profile(remote_host="gpu.example.com", configured_secrets=["sk-should-not-be-here"])
    except ValueError as exc:
        assert "不得包含密钥字段或密钥值" in str(exc)
    else:
        raise AssertionError("configured_secrets 包含密钥值时应拒绝")

    try:
        build_remote_connection_profile(ssh_key_path="-----BEGIN OPENSSH PRIVATE KEY-----")
    except ValueError as exc:
        assert "不得包含密钥字段或密钥值" in str(exc)
    else:
        raise AssertionError("ssh_key_path 包含私钥内容时应拒绝")


def test_build_remote_connection_profile_cli_writes_local_profile(tmp_path) -> None:
    """验证 CLI 写出本地远程连接 profile。"""
    output_path = tmp_path / "remote_connection_profile.local.json"

    command_build_remote_connection_profile(
        Namespace(
            remote_host="gpu.example.com",
            remote_port="22",
            remote_user="research",
            ssh_key_path="~/.ssh/id_iad_sieve",
            remote_workspace="/srv/iad-sieve",
            conda_env="iad-sieve",
            remote_conda_path="/opt/conda/bin/conda",
            configured_secrets=["OPENAI_API_KEY"],
            provided_model_artifacts=["outputs/models/local_llm_judge"],
            output_path=str(output_path),
        )
    )

    profile = json.loads(output_path.read_text(encoding="utf-8"))
    assert profile["remote_host"] == "gpu.example.com"
    assert profile["remote_conda_path"] == "/opt/conda/bin/conda"
    assert profile["configured_secrets"] == ["OPENAI_API_KEY"]
    assert profile["provided_model_artifacts"] == ["outputs/models/local_llm_judge"]
    assert "sk-" not in output_path.read_text(encoding="utf-8")


def test_build_remote_connection_pack_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出远程连接准备包。"""
    execution_plan = tmp_path / "experiment_execution_plan.jsonl"
    remote_blueprint = tmp_path / "remote_execution_blueprint.jsonl"
    profile = tmp_path / "remote_profile.json"
    output_dir = tmp_path / "remote_connection_pack"
    _write_jsonl(
        execution_plan,
        [
            {
                "task_id": "run_scincl",
                "execution_stage": 0,
                "requires_remote": True,
                "requires_secret": "",
                "command": "python -m iad_sieve.cli run-representation-baseline",
            }
        ],
    )
    _write_jsonl(
        remote_blueprint,
        [{"blueprint_item_id": "root_task:run_scincl", "blueprint_item_type": "root_execution_task", "task_id": "run_scincl"}],
    )
    profile.write_text(json.dumps({"remote_host": "gpu.example.com"}, ensure_ascii=False), encoding="utf-8")

    command_build_remote_connection_pack(
        Namespace(
            execution_plan=str(execution_plan),
            remote_blueprint=str(remote_blueprint),
            profile=str(profile),
            output_dir=str(output_dir),
        )
    )

    rows = read_records(output_dir / "remote_connection_pack.jsonl")
    assert any(row["item_id"] == "connection_field:remote_host" for row in rows)
    assert (output_dir / "remote_connection.env.example").exists()
    assert (output_dir / "remote_connection_profile.template.json").exists()
    assert (output_dir / "remote_preflight.template.sh").exists()
    assert (output_dir / "remote_sync_and_run.template.sh").exists()
    assert (output_dir / "remote_pull_outputs.template.sh").exists()
    assert (output_dir / "remote_execution_runbook.md").exists()


def test_cli_includes_build_remote_connection_pack_command() -> None:
    """验证 CLI 暴露 build-remote-connection-pack 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-remote-connection-pack",
            "--execution-plan",
            "outputs/experiment_execution_pack_fixture/experiment_execution_plan.jsonl",
            "--remote-blueprint",
            "outputs/remote_execution_blueprint_fixture/remote_execution_blueprint.jsonl",
            "--profile",
            "outputs/remote_connection_profile.local.json",
            "--output-dir",
            "outputs/remote_connection_pack_fixture",
        ]
    )

    assert args.command == "build-remote-connection-pack"
    assert args.output_dir == "outputs/remote_connection_pack_fixture"

    profile_args = parser.parse_args(
        [
            "build-remote-connection-profile",
            "--remote-host",
            "gpu.example.com",
            "--remote-port",
            "22",
            "--remote-user",
            "research",
            "--ssh-key-path",
            "~/.ssh/id_iad_sieve",
            "--remote-workspace",
            "/srv/iad-sieve",
            "--conda-env",
            "iad-sieve",
            "--remote-conda-path",
            "/opt/conda/bin/conda",
            "--configured-secret",
            "OPENAI_API_KEY",
            "--output-path",
            "outputs/remote_connection_profile.local.json",
        ]
    )
    assert profile_args.command == "build-remote-connection-profile"
    assert profile_args.remote_conda_path == "/opt/conda/bin/conda"
    assert profile_args.output_path == "outputs/remote_connection_profile.local.json"
