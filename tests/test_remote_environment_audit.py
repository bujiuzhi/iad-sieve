"""测试强模型远程环境依赖审计。"""

from __future__ import annotations

from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_remote_environment_audit
from iad_sieve.evaluation.remote_environment_audit import (
    build_remote_environment_audit_rows,
    write_remote_environment_audit_outputs,
)
from iad_sieve.utils.io_utils import read_records


def test_build_remote_environment_audit_rows_marks_modules_and_secrets() -> None:
    """验证远程环境审计能区分已安装模块、缺失模块和缺失密钥。"""
    rows = build_remote_environment_audit_rows(
        required_modules=[
            "sentence_transformers:sentence-transformers>=3.0:SciNCL baseline",
            "torch:torch>=2.2:GPU inference",
        ],
        required_env_vars=["OPENAI_API_KEY:LLM pair judge"],
        module_checker=lambda module_name: module_name == "torch",
        version_resolver=lambda module_name, package_name: "2.2.0" if module_name == "torch" else "",
        environment={},
    )
    by_check = {row["check_id"]: row for row in rows}

    assert by_check["python_module:sentence_transformers"]["status"] == "missing"
    assert by_check["python_module:sentence_transformers"]["reviewer_risk_level"] == "high"
    assert by_check["python_module:torch"]["status"] == "ready"
    assert by_check["python_module:torch"]["installed_version"] == "2.2.0"
    assert by_check["environment_variable:OPENAI_API_KEY"]["status"] == "missing"
    assert by_check["environment_variable:OPENAI_API_KEY"]["secret_value_present"] is False


def test_build_remote_environment_audit_default_does_not_require_openai_key() -> None:
    """验证默认远程环境审计不再把 OpenAI 密钥作为主轨道前置条件。"""
    rows = build_remote_environment_audit_rows(
        required_modules=["transformers:transformers>=4:local LLM backend"],
        module_checker=lambda module_name: True,
        version_resolver=lambda module_name, package_name: "4.0.0",
        environment={},
    )

    assert {row["check_id"] for row in rows} == {"python_module:transformers"}
    assert all(row["dependency_name"] != "OPENAI_API_KEY" for row in rows)


def test_write_remote_environment_audit_outputs_writes_reports(tmp_path) -> None:
    """验证远程环境审计写出 JSONL、CSV、Markdown 和 summary。"""
    rows = [
        {
            "check_id": "python_module:torch",
            "dependency_type": "python_module",
            "dependency_name": "torch",
            "status": "ready",
            "reviewer_risk_level": "low",
        },
        {
            "check_id": "environment_variable:OPENAI_API_KEY",
            "dependency_type": "environment_variable",
            "dependency_name": "OPENAI_API_KEY",
            "status": "missing",
            "reviewer_risk_level": "high",
        },
    ]
    output_dir = tmp_path / "remote_environment"

    write_remote_environment_audit_outputs(rows, output_dir)

    assert read_records(output_dir / "remote_environment_audit.jsonl")[0]["dependency_name"] == "torch"
    assert (output_dir / "remote_environment_audit.csv").exists()
    assert "# Remote Environment Audit" in (output_dir / "remote_environment_audit.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "remote_environment_audit_summary.jsonl")[0]
    assert summary["check_count"] == 2
    assert summary["missing_count"] == 1
    assert summary["all_required_ready"] is False


def test_build_remote_environment_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出远程环境依赖审计产物。"""
    output_dir = tmp_path / "remote_environment"

    command_build_remote_environment_audit(
        Namespace(
            output_dir=str(output_dir),
            required_modules=["json:stdlib json:serialization smoke test"],
            required_env_vars=[],
        )
    )

    assert read_records(output_dir / "remote_environment_audit.jsonl")[0]["status"] == "ready"
    assert (output_dir / "remote_environment_audit_summary.jsonl").exists()


def test_cli_includes_build_remote_environment_audit_command() -> None:
    """验证 CLI 暴露 build-remote-environment-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-remote-environment-audit",
            "--output-dir",
            "outputs/remote_environment_audit_fixture",
            "--required-modules",
            "sentence_transformers:sentence-transformers>=3.0:SciNCL baseline",
            "torch:torch>=2.2:GPU inference",
            "--required-env-vars",
            "OPENAI_API_KEY:LLM pair judge",
        ]
    )

    assert args.command == "build-remote-environment-audit"
    assert args.output_dir == "outputs/remote_environment_audit_fixture"
    assert args.required_modules[0].startswith("sentence_transformers:")
    assert args.required_env_vars == ["OPENAI_API_KEY:LLM pair judge"]
