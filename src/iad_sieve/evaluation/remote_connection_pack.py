"""远程连接准备包生成模块。"""

from __future__ import annotations

import csv
import json
import logging
import re
import shlex
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
ALLOWED_PROFILE_FIELDS = {
    "remote_host",
    "remote_port",
    "remote_user",
    "ssh_key_path",
    "remote_workspace",
    "conda_env",
    "remote_conda_path",
    "configured_secrets",
    "provided_model_artifacts",
    "secret_configuration_note",
}
REQUIRED_CONNECTION_FIELDS = [
    ("remote_host", "REMOTE_HOST", "远程服务器地址"),
    ("remote_port", "REMOTE_PORT", "SSH 端口"),
    ("remote_user", "REMOTE_USER", "SSH 用户"),
    ("ssh_key_path", "SSH_KEY_PATH", "SSH 私钥路径"),
    ("remote_workspace", "REMOTE_WORKSPACE", "远程项目目录"),
    ("conda_env", "CONDA_ENV", "远程 conda 环境"),
]
PREFERRED_FIELDS = [
    "item_id",
    "item_type",
    "field_name",
    "environment_name",
    "required",
    "safe_to_store",
    "status",
    "value_present",
    "value_policy",
    "execution_stage",
    "task_count",
    "task_ids",
    "required_outputs",
    "requires_secret_names",
    "template_path",
    "template_role",
    "command_template",
    "reviewer_risk_level",
    "next_action",
    "paper_claim_boundary",
]


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _as_bool(value: object) -> bool:
    """转换宽松布尔值。

    参数:
        value: 原始值。

    返回:
        布尔结果。
    """
    if isinstance(value, bool):
        return value
    return _clean(value).lower() in {"1", "true", "yes", "y"}


def _list_value(value: object) -> list[str]:
    """把列表或分号分隔字符串转为字符串列表。

    参数:
        value: 原始字段值。

    返回:
        字符串列表。
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    return [item.strip() for item in str(value).split(";") if item.strip()]


def _execution_stage(value: object) -> int:
    """解析执行阶段。

    参数:
        value: 原始阶段值。

    返回:
        整数阶段。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_profile_value(profile: dict, field_name: str) -> bool:
    """判断连接 profile 字段是否已通过外部方式提供。

    参数:
        profile: 连接 profile。
        field_name: 字段名。

    返回:
        字段存在且非空返回 True。
    """
    return bool(_clean(profile.get(field_name)))


def _looks_like_secret_value(value: object) -> bool:
    """判断字段值是否疑似密钥或私钥内容。

    参数:
        value: 待检查值。

    返回:
        疑似敏感值返回 True。
    """
    text = _clean(value)
    if not text:
        return False
    lowered = text.lower()
    return text.startswith("sk-") or "begin openssh" in lowered or "private key" in lowered or "bearer " in lowered


def _validate_profile_policy(profile: dict, path: Path | None = None) -> None:
    """校验远程连接 profile 不包含密钥字段或密钥值。

    参数:
        profile: 远程连接 profile。
        path: profile 路径，仅用于错误提示。

    返回:
        无。
    """
    source = f": {path}" if path else ""
    for key, value in profile.items():
        key_text = _clean(key)
        lowered = key_text.lower()
        allowed = key_text in ALLOWED_PROFILE_FIELDS
        sensitive_key = any(marker in lowered for marker in ["api_key", "token", "password", "secret"]) or lowered.endswith("_key")
        if sensitive_key and not allowed:
            raise ValueError(f"远程连接 profile 不得包含密钥字段或密钥值{source}: {key_text}")
        if key_text == "configured_secrets":
            if not isinstance(value, list) or any(_looks_like_secret_value(item) for item in value):
                raise ValueError(f"远程连接 profile 不得包含密钥字段或密钥值{source}: configured_secrets")
            continue
        if _looks_like_secret_value(value):
            raise ValueError(f"远程连接 profile 不得包含密钥字段或密钥值{source}: {key_text}")


def build_remote_connection_profile(
    remote_host: str | None = None,
    remote_port: str | None = None,
    remote_user: str | None = None,
    ssh_key_path: str | None = None,
    remote_workspace: str | None = None,
    conda_env: str | None = None,
    remote_conda_path: str | None = None,
    configured_secrets: list[str] | None = None,
    provided_model_artifacts: list[str] | None = None,
    environment: dict[str, str] | None = None,
) -> dict:
    """构建本地远程连接 profile。

    参数:
        remote_host: 远程服务器地址；为空时读取 REMOTE_HOST。
        remote_port: SSH 端口；为空时读取 REMOTE_PORT。
        remote_user: SSH 用户；为空时读取 REMOTE_USER。
        ssh_key_path: 本机 SSH 私钥路径；为空时读取 SSH_KEY_PATH。
        remote_workspace: 远程项目目录；为空时读取 REMOTE_WORKSPACE。
        conda_env: 远程 conda 环境名；为空时读取 CONDA_ENV。
        remote_conda_path: 远程 conda 可执行文件路径；为空时读取 REMOTE_CONDA_PATH，运行模板默认回退到 conda。
        configured_secrets: 已在远程环境安全配置的密钥变量名列表，不允许传入密钥值。
        provided_model_artifacts: 已在远程项目目录预置并通过预检的模型相对路径列表。
        environment: 可选环境变量映射；用于测试或显式传入。

    返回:
        可写入本地的安全 profile。
    """
    env = environment or {}
    profile = {
        "remote_host": _clean(remote_host) or _clean(env.get("REMOTE_HOST")),
        "remote_port": _clean(remote_port) or _clean(env.get("REMOTE_PORT")),
        "remote_user": _clean(remote_user) or _clean(env.get("REMOTE_USER")),
        "ssh_key_path": _clean(ssh_key_path) or _clean(env.get("SSH_KEY_PATH")),
        "remote_workspace": _clean(remote_workspace) or _clean(env.get("REMOTE_WORKSPACE")),
        "conda_env": _clean(conda_env) or _clean(env.get("CONDA_ENV")),
        "remote_conda_path": _clean(remote_conda_path) or _clean(env.get("REMOTE_CONDA_PATH")),
        "configured_secrets": _list_value(configured_secrets or []),
        "provided_model_artifacts": _list_value(provided_model_artifacts or []),
        "secret_configuration_note": "仅在远程环境已安全配置后，才把密钥变量名加入 configured_secrets。",
    }
    _validate_profile_policy(profile)
    return profile


def write_remote_connection_profile(profile: dict, output_path: str | Path) -> None:
    """写出本地远程连接 profile。

    参数:
        profile: 远程连接 profile。
        output_path: 输出 JSON 路径。

    返回:
        无。
    """
    try:
        _validate_profile_policy(profile)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        LOGGER.exception("写出远程连接 profile 失败: %s", output_path)
        raise


def _connection_field_rows(profile: dict) -> list[dict]:
    """构建连接字段请求记录。

    参数:
        profile: 连接 profile。

    返回:
        连接字段请求记录。
    """
    rows: list[dict] = []
    for field_name, environment_name, description in REQUIRED_CONNECTION_FIELDS:
        present = _safe_profile_value(profile, field_name)
        rows.append(
            {
                "item_id": f"connection_field:{field_name}",
                "item_type": "connection_field",
                "field_name": field_name,
                "environment_name": environment_name,
                "required": True,
                "safe_to_store": False,
                "status": "provided" if present else "blocked_external_input",
                "value_present": present,
                "value_policy": "provided_out_of_band",
                "reviewer_risk_level": "low" if present else "high",
                "next_action": "" if present else f"补充{description}，只在本地安全 profile 或 shell 环境中配置。",
                "paper_claim_boundary": "" if present else "远程连接字段缺失时，不能声称强模型远程实验已经可复现执行。",
            }
        )
    return rows


def _required_secret_names(execution_rows: list[dict]) -> list[str]:
    """提取执行计划要求的密钥变量名。

    参数:
        execution_rows: 实验执行计划记录。

    返回:
        去重后的密钥变量名列表。
    """
    names: list[str] = []
    for row in execution_rows:
        name = _clean(row.get("requires_secret"))
        if name and name not in names:
            names.append(name)
    return names


def _secret_rows(execution_rows: list[dict], profile: dict) -> list[dict]:
    """构建密钥配置请求记录。

    参数:
        execution_rows: 实验执行计划记录。
        profile: 连接 profile。

    返回:
        密钥配置请求记录。
    """
    rows: list[dict] = []
    configured_secrets = set(_list_value(profile.get("configured_secrets")))
    for secret_name in _required_secret_names(execution_rows):
        configured = secret_name in configured_secrets
        rows.append(
            {
                "item_id": f"secret_field:{secret_name}",
                "item_type": "secret_field",
                "field_name": secret_name,
                "environment_name": secret_name,
                "required": True,
                "safe_to_store": False,
                "status": "provided_out_of_band" if configured else "blocked_secret_configuration",
                "value_present": configured,
                "value_policy": "environment_only",
                "reviewer_risk_level": "medium" if configured else "high",
                "next_action": "" if configured else f"在远程 shell、凭据管理系统或调度器中配置 {secret_name}，不要写入代码、JSONL 或 Markdown。",
                "paper_claim_boundary": "" if configured else f"{secret_name} 未配置前，不能声称对应 API 模型实验已完成。",
            }
        )
    return rows


def _is_path_like_model(value: str) -> bool:
    """判断模型参数是否为本地路径。

    参数:
        value: --model-name 参数值。

    返回:
        本地路径返回 True，远程模型 ID 返回 False。
    """
    if not value:
        return False
    if value.startswith((".", "/", "~", "outputs/")):
        return True
    return "/" in value and value.count("/") != 1


def _extract_model_name_paths(command: str) -> list[str]:
    """从命令中提取本地 --model-name 路径。

    参数:
        command: 实验执行命令。

    返回:
        本地模型路径列表。
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        LOGGER.warning("解析远程模型路径失败，跳过命令: %s", command)
        return []
    paths: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("--model-name="):
            value = token.split("=", 1)[1]
            if _is_path_like_model(value):
                paths.append(value)
            index += 1
            continue
        if token == "--model-name" and index + 1 < len(tokens):
            value = tokens[index + 1]
            if _is_path_like_model(value):
                paths.append(value)
            index += 2
            continue
        index += 1
    return paths


def _is_produced_path(model_path: str, produced_paths: set[str]) -> bool:
    """判断模型路径是否由执行计划内任务产出。

    参数:
        model_path: 模型路径。
        produced_paths: 执行计划预期输出路径集合。

    返回:
        已由任务产出返回 True。
    """
    return any(model_path == produced_path or model_path.startswith(f"{produced_path}/") for produced_path in produced_paths)


def _model_artifact_rows(execution_rows: list[dict], profile: dict | None = None) -> list[dict]:
    """构建需预置的本地模型工件请求记录。

    参数:
        execution_rows: 实验执行计划记录。
        profile: 连接 profile；用于读取已预置模型工件路径。

    返回:
        模型工件请求记录。
    """
    produced_paths = {
        output_path
        for row in execution_rows
        for output_path in _list_value(row.get("expected_outputs"))
        if output_path
    }
    model_paths: list[str] = []
    for row in execution_rows:
        for model_path in _extract_model_name_paths(_clean(row.get("command"))):
            if model_path not in model_paths and not _is_produced_path(model_path, produced_paths):
                model_paths.append(model_path)
    rows: list[dict] = []
    provided_model_artifacts = set(_list_value((profile or {}).get("provided_model_artifacts")))
    for model_path in model_paths:
        provided = model_path in provided_model_artifacts
        rows.append(
            {
                "item_id": f"model_artifact:{model_path}",
                "item_type": "model_artifact",
                "field_name": model_path,
                "environment_name": "",
                "required": True,
                "safe_to_store": True,
                "status": "provided_out_of_band" if provided else "blocked_external_input",
                "value_present": provided,
                "value_policy": "remote_project_path",
                "reviewer_risk_level": "low" if provided else "high",
                "next_action": (
                    ""
                    if provided
                    else (
                        f"在远程项目目录预置模型目录 {model_path}；可使用离线权重、rsync 或远程已有缓存，"
                        "目录需包含 config.json 且模型架构应为可执行 text-generation 的 CausalLM；"
                        "不要把 API key 或私钥写入模型目录。"
                    )
                ),
                "paper_claim_boundary": "" if provided else f"{model_path} 未预置前，不能声称本地 LLM judge actual_model 已可复现运行。",
            }
        )
    return rows


def _stage_rows(execution_rows: list[dict], connection_ready: bool) -> list[dict]:
    """构建远程阶段运行命令模板。

    参数:
        execution_rows: 实验执行计划记录。
        connection_ready: 必要连接字段是否齐全。

    返回:
        阶段命令模板记录。
    """
    stage_map: dict[int, list[dict]] = {}
    for row in execution_rows:
        if not (_as_bool(row.get("requires_remote")) or _clean(row.get("requires_secret")) or _clean(row.get("command"))):
            continue
        stage_map.setdefault(_execution_stage(row.get("execution_stage")), []).append(row)
    rows: list[dict] = []
    for stage, stage_task_rows in sorted(stage_map.items()):
        task_ids = [_clean(row.get("task_id")) for row in stage_task_rows if _clean(row.get("task_id"))]
        required_outputs: list[str] = []
        requires_secret_names: list[str] = []
        for row in stage_task_rows:
            for output_path in _list_value(row.get("expected_outputs")):
                if output_path not in required_outputs:
                    required_outputs.append(output_path)
            secret_name = _clean(row.get("requires_secret"))
            if secret_name and secret_name not in requires_secret_names:
                requires_secret_names.append(secret_name)
        command_template = (
            "ssh -p ${REMOTE_PORT} -i ${SSH_KEY_PATH} ${REMOTE_USER}@${REMOTE_HOST} "
            f"'cd ${{REMOTE_WORKSPACE}} && ${{REMOTE_CONDA_PATH:-conda}} run -n ${{CONDA_ENV}} bash outputs/experiment_execution_pack_fixture/run_stage_{stage:02d}.sh'"
        )
        rows.append(
            {
                "item_id": f"stage_command:{stage}",
                "item_type": "stage_command",
                "execution_stage": stage,
                "task_count": len(task_ids),
                "task_ids": task_ids,
                "required_outputs": required_outputs,
                "requires_secret_names": requires_secret_names,
                "required": True,
                "safe_to_store": True,
                "status": "ready_template" if connection_ready else "blocked_until_connection_ready",
                "value_policy": "template_only",
                "command_template": command_template,
                "reviewer_risk_level": "medium" if connection_ready else "high",
                "next_action": "执行该阶段命令并回传输出验收清单。" if connection_ready else "补齐连接字段后再执行该阶段命令。",
                "paper_claim_boundary": "阶段脚本输出未回传并验收前，不能声称强模型证据已闭环。",
            }
        )
    return rows


def _script_template_rows() -> list[dict]:
    """构建远程交接脚本模板记录。

    参数:
        无。

    返回:
        脚本模板记录列表。
    """
    return [
        {
            "item_id": "script_template:remote_sync_and_run",
            "item_type": "script_template",
            "template_path": "remote_sync_and_run.template.sh",
            "template_role": "sync_and_run",
            "required": True,
            "safe_to_store": True,
            "status": "ready_template",
            "value_policy": "template_only",
            "reviewer_risk_level": "low",
            "next_action": "连接字段齐全后执行同步运行模板，按阶段运行远程强模型实验。",
            "paper_claim_boundary": "同步运行模板执行且输出验收前，不能声称强模型结果已闭环。",
        },
        {
            "item_id": "script_template:remote_preflight",
            "item_type": "script_template",
            "template_path": "remote_preflight.template.sh",
            "template_role": "preflight_only",
            "required": True,
            "safe_to_store": True,
            "status": "ready_template",
            "value_policy": "template_only",
            "reviewer_risk_level": "low",
            "next_action": "连接字段齐全后先执行轻量远程预检，再启动全量强模型阶段。",
            "paper_claim_boundary": "远程预检通过前，不能声称强模型运行环境已具备。",
        },
        {
            "item_id": "script_template:remote_pull_outputs",
            "item_type": "script_template",
            "template_path": "remote_pull_outputs.template.sh",
            "template_role": "pull_and_validate",
            "required": True,
            "safe_to_store": True,
            "status": "ready_template",
            "value_policy": "template_only",
            "reviewer_risk_level": "low",
            "next_action": "远程阶段执行后拉回 outputs 并运行远程输出验收。",
            "paper_claim_boundary": "输出未拉回并通过验收前，不能写入论文证据。",
        },
    ]


def _with_script_template_rows(rows: list[dict]) -> list[dict]:
    """确保记录中包含远程脚本模板元数据。

    参数:
        rows: 原始准备包记录。

    返回:
        补齐脚本模板记录后的列表。
    """
    output_rows = list(rows)
    existing_ids = {_clean(row.get("item_id")) for row in output_rows}
    for row in _script_template_rows():
        if row["item_id"] not in existing_ids:
            output_rows.append(row)
    return output_rows


def _reviewer_checkpoint_row(rows: list[dict], blueprint_rows: list[dict]) -> dict:
    """构建审稿检查点记录。

    参数:
        rows: 已生成连接准备记录。
        blueprint_rows: 远程执行蓝图记录。

    返回:
        审稿检查点记录。
    """
    blocked_count = sum(1 for row in rows if _clean(row.get("status")).startswith("blocked"))
    high_blueprint_count = sum(1 for row in blueprint_rows if row.get("reviewer_risk_level") == "high")
    high_risk = blocked_count > 0 or high_blueprint_count > 0
    return {
        "item_id": "reviewer_checkpoint:remote_connection",
        "item_type": "reviewer_checkpoint",
        "required": True,
        "safe_to_store": True,
        "status": "blocked" if high_risk else "ready",
        "value_policy": "evidence_gate",
        "reviewer_risk_level": "high" if high_risk else "low",
        "next_action": "先完成远程连接、密钥配置和根任务执行，再重建 advanced evidence、submission gates 和 topic package。" if high_risk else "远程连接准备项已齐全，可进入执行与回传验收。",
        "paper_claim_boundary": "该检查点通过前，论文只能描述远程强模型实验计划，不能写成已完成结果。",
    }


def build_remote_connection_pack_rows(execution_rows: list[dict], blueprint_rows: list[dict], profile: dict | None = None) -> list[dict]:
    """构建远程连接准备包记录。

    参数:
        execution_rows: 实验执行计划记录。
        blueprint_rows: 远程执行蓝图记录。
        profile: 外部连接 profile；只用于判断字段是否齐全，不写出真实值。

    返回:
        远程连接准备包记录。
    """
    try:
        profile_data = profile or {}
        rows = _connection_field_rows(profile_data)
        rows.extend(_secret_rows(execution_rows, profile_data))
        rows.extend(_model_artifact_rows(execution_rows, profile_data))
        connection_ready = all(row.get("status") == "provided" for row in rows if row.get("item_type") == "connection_field")
        rows.extend(_stage_rows(execution_rows, connection_ready))
        rows = _with_script_template_rows(rows)
        rows.append(_reviewer_checkpoint_row(rows, blueprint_rows))
        LOGGER.info("远程连接准备包生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建远程连接准备包失败")
        raise


def _read_profile(path: str | Path | None) -> dict:
    """读取连接 profile。

    参数:
        path: JSON profile 路径；为空或不存在时返回空字典。

    返回:
        profile 字典。
    """
    if not path:
        return {}
    profile_path = Path(path)
    if not profile_path.exists():
        LOGGER.warning("远程连接 profile 不存在，按空 profile 生成: %s", profile_path)
        return {}
    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        LOGGER.exception("读取远程连接 profile 失败: %s", profile_path)
        raise
    if not isinstance(data, dict):
        raise ValueError(f"远程连接 profile 必须是 JSON object: {profile_path}")
    _validate_profile_policy(data, profile_path)
    return data


def build_remote_connection_pack_rows_from_paths(
    execution_plan_path: str | Path,
    remote_blueprint_path: str | Path,
    profile_path: str | Path | None = None,
) -> list[dict]:
    """从文件构建远程连接准备包。

    参数:
        execution_plan_path: experiment_execution_plan JSONL 路径。
        remote_blueprint_path: remote_execution_blueprint JSONL 路径。
        profile_path: 远程连接 profile JSON 路径。

    返回:
        远程连接准备包记录。
    """
    try:
        execution_rows = read_records(execution_plan_path)
        blueprint_rows = read_records(remote_blueprint_path)
        profile = _read_profile(profile_path)
    except Exception:
        LOGGER.exception("读取远程连接准备包输入失败")
        raise
    return build_remote_connection_pack_rows(execution_rows, blueprint_rows, profile)


def _serialize_csv_value(value: object) -> object:
    """序列化 CSV 单元格值。

    参数:
        value: 原始值。

    返回:
        CSV 可写值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出远程连接准备包 CSV。

    参数:
        path: 输出路径。
        rows: 准备包记录。

    返回:
        无。
    """
    fields = list(PREFERRED_FIELDS)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_csv_value(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出远程连接准备包 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建远程连接准备包摘要。

    参数:
        rows: 准备包记录。

    返回:
        摘要记录。
    """
    connection_rows = [row for row in rows if row.get("item_type") == "connection_field"]
    secret_rows = [row for row in rows if row.get("item_type") == "secret_field"]
    model_artifact_rows = [row for row in rows if row.get("item_type") == "model_artifact"]
    stage_rows = [row for row in rows if row.get("item_type") == "stage_command"]
    script_rows = [row for row in rows if row.get("item_type") == "script_template"]
    missing_required_count = sum(1 for row in connection_rows if _clean(row.get("status")) == "blocked_external_input")
    blocked_secret_count = sum(1 for row in secret_rows if _clean(row.get("status")) == "blocked_secret_configuration")
    missing_model_artifact_count = sum(1 for row in model_artifact_rows if _clean(row.get("status")) == "blocked_external_input")
    high_risk_count = sum(1 for row in rows if row.get("reviewer_risk_level") == "high")
    return {
        "item_count": len(rows),
        "connection_field_count": len(connection_rows),
        "missing_required_field_count": missing_required_count,
        "secret_field_count": len(secret_rows),
        "blocked_secret_count": blocked_secret_count,
        "model_artifact_count": len(model_artifact_rows),
        "missing_model_artifact_count": missing_model_artifact_count,
        "stage_command_count": len(stage_rows),
        "script_template_count": len(script_rows),
        "high_risk_count": high_risk_count,
        "all_connection_fields_ready": missing_required_count == 0,
        "all_remote_run_inputs_ready": missing_required_count == 0 and blocked_secret_count == 0 and missing_model_artifact_count == 0,
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出远程连接准备包 Markdown。

    参数:
        path: 输出路径。
        rows: 准备包记录。
        summary: 摘要记录。

    返回:
        无。
    """
    fields = ["item_type", "field_name", "status", "reviewer_risk_level", "next_action"]
    lines = [
        "# Remote Connection Pack",
        "",
        "## 使用边界",
        "",
        "该准备包只保存字段状态、命令模板和审稿边界，不保存远程地址、私钥路径或 API 密钥值。",
        "",
        "## 汇总",
        "",
        f"- item_count: {summary['item_count']}",
        f"- missing_required_field_count: {summary['missing_required_field_count']}",
        f"- blocked_secret_count: {summary['blocked_secret_count']}",
        f"- model_artifact_count: {summary.get('model_artifact_count', 0)}",
        f"- missing_model_artifact_count: {summary.get('missing_model_artifact_count', 0)}",
        f"- stage_command_count: {summary['stage_command_count']}",
        f"- script_template_count: {summary['script_template_count']}",
        f"- high_risk_count: {summary['high_risk_count']}",
        f"- all_remote_run_inputs_ready: {summary['all_remote_run_inputs_ready']}",
        "",
        "## 脚本模板",
        "",
        "- `remote_preflight.template.sh`: 只检查远程 SSH、conda、CUDA、Python 模块和密钥环境，不同步项目且不启动实验。",
        "- `remote_sync_and_run.template.sh`: 将本地项目同步到远程目录，先做远程 CUDA、Python 模块和密钥环境预检，再按阶段执行 `run_stage_*.sh`。",
        "- `remote_pull_outputs.template.sh`: 将远程 `outputs/` 拉回本地，并运行远程输出验收、远程结果接收审计和 stage 03 证据包重建。",
        "",
        "## 本地 profile 生成",
        "",
        "可使用 `python -m iad_sieve.cli build-remote-connection-profile` 从命令行参数或本地环境变量生成 `outputs/remote_connection_profile.local.json`；该命令只保存连接字段和已确认配置的密钥变量名，不保存 API key、密码或私钥内容。",
        "",
        "## 阶段运行手册",
        "",
        "| execution_stage | status | task_ids | required_outputs | requires_secret_names | command_template |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if row.get("item_type") != "stage_command":
            continue
        values = [
            row.get("execution_stage", ""),
            row.get("status", ""),
            _serialize_csv_value(row.get("task_ids", "")),
            _serialize_csv_value(row.get("required_outputs", "")),
            _serialize_csv_value(row.get("requires_secret_names", "")),
            row.get("command_template", ""),
        ]
        lines.append("| " + " | ".join(str(value).replace("\n", " ").replace("|", "/") for value in values) + " |")
    lines.extend(
        [
            "",
            "## 明细",
            "",
            "| " + " | ".join(fields) + " |",
            "| " + " | ".join(["---"] * len(fields)) + " |",
        ]
    )
    for row in rows:
        values = [_serialize_csv_value(row.get(field, "")) for field in fields]
        lines.append("| " + " | ".join(str(value).replace("\n", " ").replace("|", "/") for value in values) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出远程连接准备包 Markdown 失败: %s", path)
        raise


def _write_runbook(path: Path, rows: list[dict], summary: dict) -> None:
    """写出远程实验交接运行手册。

    参数:
        path: 输出路径。
        rows: 远程连接准备包记录。
        summary: 摘要记录。

    返回:
        无。
    """
    connection_rows = [row for row in rows if row.get("item_type") == "connection_field"]
    secret_rows = [row for row in rows if row.get("item_type") == "secret_field"]
    model_artifact_rows = [row for row in rows if row.get("item_type") == "model_artifact"]
    stage_rows = [row for row in rows if row.get("item_type") == "stage_command"]
    stage_secret_names: list[str] = []
    for row in stage_rows:
        for secret_name in _list_value(row.get("requires_secret_names")):
            if secret_name not in stage_secret_names:
                stage_secret_names.append(secret_name)
    lines = [
        "# Remote Execution Runbook",
        "",
        "## 使用边界",
        "",
        "该手册用于把远程强模型实验交接给执行人员；其中只包含变量名、模板命令和验收输出，不包含真实服务器地址、私钥路径或 API 密钥值。",
        "",
        "## 当前状态",
        "",
        f"- all_remote_run_inputs_ready: {summary['all_remote_run_inputs_ready']}",
        f"- missing_required_field_count: {summary['missing_required_field_count']}",
        f"- blocked_secret_count: {summary['blocked_secret_count']}",
        f"- missing_model_artifact_count: {summary.get('missing_model_artifact_count', 0)}",
        f"- stage_command_count: {summary['stage_command_count']}",
        "",
        "## 连接信息填写清单",
        "",
        "可先运行 `python -m iad_sieve.cli build-remote-connection-profile --output-path outputs/remote_connection_profile.local.json ...` 生成本地 profile，再运行 `build-remote-connection-pack` 刷新本手册。不要把 API key、密码或私钥内容写入该命令。",
        "",
        "| field_name | environment_name | status | safe_to_store | next_action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in connection_rows:
        values = [
            row.get("field_name", ""),
            row.get("environment_name", ""),
            row.get("status", ""),
            row.get("safe_to_store", ""),
            row.get("next_action", ""),
        ]
        lines.append("| " + " | ".join(str(value).replace("\n", " ").replace("|", "/") for value in values) + " |")
    lines.extend(["", "## 模型工件预置要求", ""])
    if model_artifact_rows:
        lines.extend(["| field_name | status | value_policy | next_action |", "| --- | --- | --- | --- |"])
        for row in model_artifact_rows:
            values = [row.get("field_name", ""), row.get("status", ""), row.get("value_policy", ""), row.get("next_action", "")]
            lines.append("| " + " | ".join(str(value).replace("\n", " ").replace("|", "/") for value in values) + " |")
    else:
        lines.append("当前执行计划没有声明需预置的本地模型目录。")
    lines.extend(["", "## 密钥配置要求", ""])
    if secret_rows:
        lines.extend(["| field_name | status | value_policy | next_action |", "| --- | --- | --- | --- |"])
        for row in secret_rows:
            values = [row.get("field_name", ""), row.get("status", ""), row.get("value_policy", ""), row.get("next_action", "")]
            lines.append("| " + " | ".join(str(value).replace("\n", " ").replace("|", "/") for value in values) + " |")
        lines.append("")
        lines.append("不要把密钥值写入 profile、JSONL、Markdown 或脚本模板；只允许在远程 shell、凭据管理系统或调度器中以环境变量方式配置。")
    elif stage_secret_names:
        lines.append(f"阶段命令声明需要密钥变量: {_serialize_csv_value(stage_secret_names)}。")
        lines.append("")
        lines.append("不要把密钥值写入 profile、JSONL、Markdown 或脚本模板；只允许在远程 shell、凭据管理系统或调度器中以环境变量方式配置。")
    else:
        lines.append("当前执行计划没有声明额外密钥。")
    for row in stage_rows:
        stage = row.get("execution_stage", "")
        lines.extend(
            [
                "",
                f"## 阶段 {stage}",
                "",
                f"- status: {row.get('status', '')}",
                f"- task_count: {row.get('task_count', '')}",
                f"- task_ids: {_serialize_csv_value(row.get('task_ids', ''))}",
                f"- required_outputs: {_serialize_csv_value(row.get('required_outputs', ''))}",
                f"- requires_secret_names: {_serialize_csv_value(row.get('requires_secret_names', ''))}",
                "",
                "```bash",
                _clean(row.get("command_template")),
                "```",
            ]
        )
    lines.extend(
        [
            "",
            "## 回传验收",
            "",
            "远程阶段执行完成后，运行 `remote_pull_outputs.template.sh` 拉回 `outputs/`，再执行 `validate-remote-outputs`、`build-remote-result-acceptance` 和 stage 03 证据包重建；未通过验收前不得把强模型结果写入论文结论。",
        ]
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出远程实验运行手册失败: %s", path)
        raise


def _write_env_template(path: Path) -> None:
    """写出远程连接环境变量模板。

    参数:
        path: 输出路径。

    返回:
        无。
    """
    lines = [
        "# 仅用于本地 shell source，不要提交真实值。",
        "REMOTE_HOST=",
        "REMOTE_PORT=",
        "REMOTE_USER=",
        "SSH_KEY_PATH=",
        "REMOTE_WORKSPACE=",
        "CONDA_ENV=iad-sieve",
        "REMOTE_CONDA_PATH=",
    ]
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出远程连接环境变量模板失败: %s", path)
        raise


def _write_profile_template(path: Path) -> None:
    """写出远程连接 profile JSON 模板。

    参数:
        path: 输出路径。

    返回:
        无。
    """
    profile_template = {
        "remote_host": "",
        "remote_port": "",
        "remote_user": "",
        "ssh_key_path": "",
        "remote_workspace": "",
        "conda_env": "iad-sieve",
        "remote_conda_path": "",
        "configured_secrets": [],
        "provided_model_artifacts": [],
        "secret_configuration_note": "仅在远程环境已安全配置后，才把密钥变量名加入 configured_secrets。",
    }
    try:
        path.write_text(json.dumps(profile_template, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出远程连接 profile 模板失败: %s", path)
        raise


def _stage_script_paths(rows: list[dict]) -> list[str]:
    """提取需要远程执行的阶段脚本路径。

    参数:
        rows: 远程连接准备包记录。

    返回:
        去重后的阶段脚本路径列表。
    """
    stage_numbers: set[int] = set()
    stage_pattern = re.compile(r"run_stage_(\d+)\.sh")
    for row in rows:
        if row.get("item_type") != "stage_command":
            continue
        stage_text = _clean(row.get("execution_stage"))
        if stage_text:
            stage_numbers.add(_execution_stage(stage_text))
            continue
        item_id = _clean(row.get("item_id"))
        if item_id.startswith("stage_command:"):
            stage_numbers.add(_execution_stage(item_id.split(":", 1)[1]))
            continue
        command_template = _clean(row.get("command_template"))
        match = stage_pattern.search(command_template)
        if match:
            stage_numbers.add(_execution_stage(match.group(1)))
    return [f"outputs/experiment_execution_pack_fixture/run_stage_{stage:02d}.sh" for stage in sorted(stage_numbers)]


def _remote_env_bootstrap_lines() -> list[str]:
    """构建远程脚本模板公共环境加载片段。

    参数:
        无。

    返回:
        Bash 代码行列表。
    """
    required_variables = ["REMOTE_HOST", "REMOTE_PORT", "REMOTE_USER", "SSH_KEY_PATH", "REMOTE_WORKSPACE", "CONDA_ENV"]
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        'REMOTE_CONNECTION_ENV_PATH="${REMOTE_CONNECTION_ENV_PATH:-./remote_connection.env}"',
        'if [[ -f "${REMOTE_CONNECTION_ENV_PATH}" ]]; then',
        "  set -a",
        '  source "${REMOTE_CONNECTION_ENV_PATH}"',
        "  set +a",
        "fi",
        "",
    ]
    lines.extend(f': "${{{variable}:?请先设置 {variable}}}"' for variable in required_variables)
    lines.extend(
        [
            'SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"',
            'REMOTE_PROJECT_DIR="${REMOTE_WORKSPACE%/}"',
            'REMOTE_CONDA_PATH="${REMOTE_CONDA_PATH:-conda}"',
            'REMOTE_CONDA_COMMAND="${REMOTE_CONDA_PATH} run -n ${CONDA_ENV}"',
            'SSH_COMMAND="ssh -p ${REMOTE_PORT} -i ${SSH_KEY_PATH}"',
            "",
        ]
    )
    return lines


def _write_executable_template(path: Path, lines: list[str]) -> None:
    """写出可执行 shell 模板。

    参数:
        path: 输出路径。
        lines: shell 代码行。

    返回:
        无。
    """
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        path.chmod(0o755)
    except OSError:
        LOGGER.exception("写出远程 shell 模板失败: %s", path)
        raise


def _stage_secret_names(rows: list[dict]) -> list[str]:
    """提取阶段命令声明的密钥变量名。

    参数:
        rows: 远程连接准备包记录。

    返回:
        去重后的密钥变量名列表。
    """
    names: list[str] = []
    for row in rows:
        if row.get("item_type") != "stage_command":
            continue
        for secret_name in _list_value(row.get("requires_secret_names")):
            if secret_name not in names:
                names.append(secret_name)
    return names


def _model_artifact_paths(rows: list[dict]) -> list[str]:
    """提取需在远程项目目录预置的模型路径。

    参数:
        rows: 远程连接准备包记录。

    返回:
        去重后的相对模型路径列表。
    """
    paths: list[str] = []
    for row in rows:
        if row.get("item_type") != "model_artifact":
            continue
        path = _clean(row.get("field_name"))
        if path and path not in paths:
            paths.append(path)
    return paths


def _remote_preflight_python(secrets: list[str], model_paths: list[str], quote_escape: str = "") -> str:
    """生成远程预检 Python 单行脚本。

    参数:
        secrets: 需要在远程环境存在的密钥变量名。
        model_paths: 需要在远程项目目录存在的模型路径。
        quote_escape: 双引号转义前缀；嵌入远程双引号命令时使用反斜杠。

    返回:
        可传给 `python -c` 的单行脚本。
    """
    def quoted(values: list[str]) -> str:
        return "[" + ",".join(f'"{value}"' for value in values) + "]"

    script = (
        "import importlib.util, os, sys, json; "
        f"modules={quoted(['sentence_transformers', 'torch', 'transformers', 'adapters'])}; "
        "missing=[name for name in modules if importlib.util.find_spec(name) is None]; "
        "missing += ([] if \"torch\" in missing or __import__(\"torch\").cuda.is_available() else [\"cuda_available\"]); "
        f"secrets={quoted(secrets)}; "
        "missing += [name for name in secrets if not os.environ.get(name)]; "
        f"model_paths={quoted(model_paths)}; "
        "missing += [path for path in model_paths if not os.path.exists(path)]; "
        "existing_model_paths=[path for path in model_paths if os.path.exists(path)]; "
        "missing += [path + \":config.json\" for path in existing_model_paths if not os.path.isfile(os.path.join(path, \"config.json\"))]; "
        "causal_arch_markers=(\"ForCausalLM\", \"LMHeadModel\", \"GPT2LMHeadModel\", \"GPTNeo\", \"GPTJ\", \"GPTBigCode\", \"Llama\", \"Mistral\", \"Mixtral\", \"Qwen\", \"Gemma\", \"Phi\", \"Falcon\", \"MPTForCausalLM\", \"ChatGLM\"); "
        "generative_model_types={\"gpt2\", \"gpt_neox\", \"gptj\", \"llama\", \"mistral\", \"mixtral\", \"qwen\", \"qwen2\", \"qwen3\", \"gemma\", \"gemma2\", \"gemma3\", \"phi\", \"phi3\", \"falcon\", \"mpt\", \"chatglm\"}; "
        "model_configs=[(path, json.loads(open(os.path.join(path, \"config.json\"), encoding=\"utf-8\").read())) for path in existing_model_paths if os.path.isfile(os.path.join(path, \"config.json\"))]; "
        "missing += [path + \":not_causal_lm\" for path, config in model_configs if not (any(any(marker in str(arch) for marker in causal_arch_markers) for arch in (config.get(\"architectures\") or [])) or str(config.get(\"model_type\") or \"\").lower() in generative_model_types)]; "
        "print(\"remote_preflight_missing=\" + \",\".join(missing)); "
        "sys.exit(1 if missing else 0)"
    )
    if quote_escape:
        return script.replace('"', f'{quote_escape}"')
    return script


def _write_sync_and_run_template(path: Path, rows: list[dict]) -> None:
    """写出远程同步与阶段执行模板。

    参数:
        path: 输出路径。
        rows: 远程连接准备包记录。

    返回:
        无。
    """
    stage_scripts = _stage_script_paths(rows)
    preflight_python = _remote_preflight_python(_stage_secret_names(rows), _model_artifact_paths(rows), quote_escape="\\")
    lines = _remote_env_bootstrap_lines()
    lines.extend(
        [
            'ssh -p "${REMOTE_PORT}" -i "${SSH_KEY_PATH}" "${SSH_TARGET}" "mkdir -p \\"${REMOTE_PROJECT_DIR}\\""',
            "",
            'rsync -az --exclude ".git/" --exclude "remote_connection.env" --exclude "remote_connection.env.*" --exclude "outputs/topic_package_final/" --exclude "outputs/remote_connection_profile.local.json" -e "${SSH_COMMAND}" ./ "${SSH_TARGET}:${REMOTE_PROJECT_DIR}/"',
            "",
            'ssh -p "${REMOTE_PORT}" -i "${SSH_KEY_PATH}" "${SSH_TARGET}" "cd \\"${REMOTE_PROJECT_DIR}\\" && ${REMOTE_CONDA_COMMAND} python scripts/check_cuda.py"',
            f'ssh -p "${{REMOTE_PORT}}" -i "${{SSH_KEY_PATH}}" "${{SSH_TARGET}}" "cd \\"${{REMOTE_PROJECT_DIR}}\\" && ${{REMOTE_CONDA_COMMAND}} python -c \'{preflight_python}\'"',
            "",
        ]
    )
    if stage_scripts:
        for script_path in stage_scripts:
            lines.append(
                f'ssh -p "${{REMOTE_PORT}}" -i "${{SSH_KEY_PATH}}" "${{SSH_TARGET}}" '
                f'"cd \\"${{REMOTE_PROJECT_DIR}}\\" && ${{REMOTE_CONDA_COMMAND}} bash {script_path}"'
            )
    else:
        lines.append('echo "未发现 stage_command 记录，请先重建 remote_connection_pack。" >&2')
        lines.append("exit 1")
    _write_executable_template(path, lines)


def _write_remote_preflight_template(path: Path, rows: list[dict]) -> None:
    """写出远程轻量预检模板。

    参数:
        path: 输出路径。
        rows: 远程连接准备包记录。

    返回:
        无。
    """
    preflight_python = _remote_preflight_python(_stage_secret_names(rows), _model_artifact_paths(rows), quote_escape="\\")
    lines = _remote_env_bootstrap_lines()
    lines.extend(
        [
            'ssh -p "${REMOTE_PORT}" -i "${SSH_KEY_PATH}" "${SSH_TARGET}" "mkdir -p \\"${REMOTE_PROJECT_DIR}\\""',
            f'ssh -p "${{REMOTE_PORT}}" -i "${{SSH_KEY_PATH}}" "${{SSH_TARGET}}" "cd \\"${{REMOTE_PROJECT_DIR}}\\" && ${{REMOTE_CONDA_COMMAND}} python -c \'{preflight_python}\'"',
        ]
    )
    _write_executable_template(path, lines)


def _write_pull_outputs_template(path: Path) -> None:
    """写出远程输出回传与验收模板。

    参数:
        path: 输出路径。

    返回:
        无。
    """
    lines = _remote_env_bootstrap_lines()
    lines.extend(
        [
            "mkdir -p outputs",
            'rsync -az -e "${SSH_COMMAND}" "${SSH_TARGET}:${REMOTE_PROJECT_DIR}/outputs/" "./outputs/"',
            "",
            "python -m iad_sieve.cli validate-remote-outputs \\",
            "  --manifest outputs/experiment_execution_pack_fixture/remote_output_manifest.jsonl \\",
            "  --workspace-dir . \\",
            "  --output-dir outputs/remote_output_validation_fixture",
            "",
            "python -m iad_sieve.cli build-remote-result-acceptance \\",
            "  --execution-plan outputs/experiment_execution_pack_fixture/experiment_execution_plan.jsonl \\",
            "  --remote-output-validation outputs/remote_output_validation_fixture/remote_output_validation.jsonl \\",
            "  --output-dir outputs/remote_result_acceptance_fixture",
            "",
            'if [[ -f "outputs/experiment_execution_pack_fixture/run_stage_03.sh" ]]; then',
            "  bash outputs/experiment_execution_pack_fixture/run_stage_03.sh",
            "else",
            '  echo "未发现 stage 03 证据包重建脚本，请先重建 experiment_execution_pack。" >&2',
            "  exit 1",
            "fi",
        ]
    )
    _write_executable_template(path, lines)


def write_remote_connection_pack_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出远程连接准备包。

    参数:
        rows: 准备包记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        output_rows = _with_script_template_rows(rows)
        write_records(output_rows, directory / "remote_connection_pack.jsonl")
        _write_csv(directory / "remote_connection_pack.csv", output_rows)
        summary = _build_summary(output_rows)
        write_records([summary], directory / "remote_connection_pack_summary.jsonl")
        _write_markdown(directory / "remote_connection_pack.md", output_rows, summary)
        _write_env_template(directory / "remote_connection.env.example")
        _write_profile_template(directory / "remote_connection_profile.template.json")
        _write_remote_preflight_template(directory / "remote_preflight.template.sh", output_rows)
        _write_sync_and_run_template(directory / "remote_sync_and_run.template.sh", output_rows)
        _write_pull_outputs_template(directory / "remote_pull_outputs.template.sh")
        _write_runbook(directory / "remote_execution_runbook.md", output_rows, summary)
    except Exception:
        LOGGER.exception("写出远程连接准备包失败: %s", output_dir)
        raise
