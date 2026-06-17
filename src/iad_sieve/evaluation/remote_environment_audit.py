"""强模型远程环境依赖审计模块。"""

from __future__ import annotations

import csv
import importlib.metadata
import importlib.util
import logging
import os
from collections.abc import Callable, Mapping
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, write_records


LOGGER = logging.getLogger(__name__)
DEFAULT_REQUIRED_MODULES = [
    "sentence_transformers:sentence-transformers>=3.0:SciNCL / sentence-transformers 强 baseline",
    "torch:torch>=2.2:Transformer 与 GPU 推理训练",
    "transformers:transformers>=4:SPECTER2 / RoBERTa / Transformer 后端",
    "adapters:adapters>=1.3,<2:SPECTER2 adapter 后端",
]
DEFAULT_REQUIRED_ENV_VARS: list[str] = []
PREFERRED_FIELDS = [
    "check_id",
    "dependency_type",
    "dependency_name",
    "package_spec",
    "purpose",
    "status",
    "installed_version",
    "secret_value_present",
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


def _parse_module_spec(spec: str) -> dict:
    """解析 Python 模块依赖描述。

    参数:
        spec: `module:package_spec:purpose` 格式字符串。

    返回:
        标准化模块依赖描述。
    """
    parts = [_clean(part) for part in spec.split(":", 2)]
    module_name = parts[0] if parts else ""
    package_spec = parts[1] if len(parts) > 1 and parts[1] else module_name
    purpose = parts[2] if len(parts) > 2 else ""
    return {"module_name": module_name, "package_spec": package_spec, "purpose": purpose}


def _parse_env_spec(spec: str) -> dict:
    """解析环境变量依赖描述。

    参数:
        spec: `ENV_NAME:purpose` 格式字符串。

    返回:
        标准化环境变量依赖描述。
    """
    parts = [_clean(part) for part in spec.split(":", 1)]
    env_name = parts[0] if parts else ""
    purpose = parts[1] if len(parts) > 1 else ""
    return {"env_name": env_name, "purpose": purpose}


def _module_available(module_name: str) -> bool:
    """判断 Python 模块是否可导入。

    参数:
        module_name: 模块导入名。

    返回:
        可导入返回 True。
    """
    return importlib.util.find_spec(module_name) is not None


def _distribution_name(package_spec: str, module_name: str) -> str:
    """从 package spec 推断 distribution 名称。

    参数:
        package_spec: 依赖规格，如 `sentence-transformers>=3.0`。
        module_name: 模块名。

    返回:
        distribution 名称。
    """
    spec = _clean(package_spec)
    for separator in [">=", "==", "<=", "~=", ">", "<", "["]:
        if separator in spec:
            spec = spec.split(separator, 1)[0]
    return spec or module_name


def _installed_version(module_name: str, package_spec: str) -> str:
    """读取已安装包版本。

    参数:
        module_name: 模块名。
        package_spec: package spec。

    返回:
        版本号；未知时返回空字符串。
    """
    package_name = _distribution_name(package_spec, module_name)
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return ""


def build_remote_environment_audit_rows(
    required_modules: list[str] | None = None,
    required_env_vars: list[str] | None = None,
    module_checker: Callable[[str], bool] | None = None,
    version_resolver: Callable[[str, str], str] | None = None,
    environment: Mapping[str, str] | None = None,
) -> list[dict]:
    """构建强模型远程环境依赖审计记录。

    参数:
        required_modules: Python 模块依赖规格列表。
        required_env_vars: 环境变量依赖规格列表。
        module_checker: 可注入的模块检查函数。
        version_resolver: 可注入的版本读取函数。
        environment: 环境变量映射；为空时使用当前进程环境。

    返回:
        远程环境审计记录列表。
    """
    checker = module_checker or _module_available
    resolver = version_resolver or _installed_version
    env = os.environ if environment is None else environment
    module_specs = required_modules or DEFAULT_REQUIRED_MODULES
    env_specs = required_env_vars if required_env_vars is not None else DEFAULT_REQUIRED_ENV_VARS
    rows: list[dict] = []
    try:
        for spec in module_specs:
            parsed = _parse_module_spec(spec)
            module_name = parsed["module_name"]
            if not module_name:
                continue
            package_spec = parsed["package_spec"]
            available = checker(module_name)
            rows.append(
                {
                    "check_id": f"python_module:{module_name}",
                    "dependency_type": "python_module",
                    "dependency_name": module_name,
                    "package_spec": package_spec,
                    "purpose": parsed["purpose"],
                    "status": "ready" if available else "missing",
                    "installed_version": resolver(module_name, package_spec) if available else "",
                    "secret_value_present": "",
                    "reviewer_risk_level": "low" if available else "high",
                    "next_action": "" if available else f"在远程 conda 环境安装 {package_spec} 后重跑强模型任务。",
                    "paper_claim_boundary": "" if available else "依赖缺失时不能声称对应强模型 actual_model 已完成。",
                }
            )
        for spec in env_specs:
            parsed = _parse_env_spec(spec)
            env_name = parsed["env_name"]
            if not env_name:
                continue
            present = bool(_clean(env.get(env_name)))
            rows.append(
                {
                    "check_id": f"environment_variable:{env_name}",
                    "dependency_type": "environment_variable",
                    "dependency_name": env_name,
                    "package_spec": "",
                    "purpose": parsed["purpose"],
                    "status": "ready" if present else "missing",
                    "installed_version": "",
                    "secret_value_present": present,
                    "reviewer_risk_level": "low" if present else "high",
                    "next_action": "" if present else f"在远程环境配置 {env_name}，不要写入代码或报告明文。",
                    "paper_claim_boundary": "" if present else "密钥缺失时不能声称 LLM pair judge api_model 已完成。",
                }
            )
        LOGGER.info("远程环境依赖审计完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建远程环境依赖审计失败")
        raise


def _summary(rows: list[dict]) -> dict:
    """构建远程环境审计摘要。

    参数:
        rows: 审计记录。

    返回:
        摘要记录。
    """
    missing_count = sum(1 for row in rows if row.get("status") == "missing")
    ready_count = sum(1 for row in rows if row.get("status") == "ready")
    return {
        "check_count": len(rows),
        "ready_count": ready_count,
        "missing_count": missing_count,
        "all_required_ready": missing_count == 0,
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出远程环境审计 CSV。

    参数:
        path: 输出路径。
        rows: 审计记录。

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
            writer.writerows(rows)
    except OSError:
        LOGGER.exception("写出远程环境审计 CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出远程环境审计 Markdown。

    参数:
        path: 输出路径。
        rows: 审计记录。
        summary: 摘要记录。

    返回:
        无。
    """
    fields = ["dependency_type", "dependency_name", "status", "installed_version", "reviewer_risk_level", "next_action"]
    lines = [
        "# Remote Environment Audit",
        "",
        "## 使用边界",
        "",
        "该报告只检查强模型远程执行所需的 Python 模块和环境变量是否存在，不记录密钥明文。",
        "",
        "## 汇总",
        "",
        f"- check_count: {summary['check_count']}",
        f"- ready_count: {summary['ready_count']}",
        f"- missing_count: {summary['missing_count']}",
        f"- all_required_ready: {summary['all_required_ready']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出远程环境审计 Markdown 失败: %s", path)
        raise


def write_remote_environment_audit_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出强模型远程环境依赖审计产物。

    参数:
        rows: 审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _summary(rows)
    try:
        write_records(rows, directory / "remote_environment_audit.jsonl")
        write_records([summary], directory / "remote_environment_audit_summary.jsonl")
        _write_csv(directory / "remote_environment_audit.csv", rows)
        _write_markdown(directory / "remote_environment_audit.md", rows, summary)
    except Exception:
        LOGGER.exception("写出远程环境依赖审计产物失败: %s", output_dir)
        raise
