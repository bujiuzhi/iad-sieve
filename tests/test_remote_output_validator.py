"""测试远程输出验收验证器。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_validate_remote_outputs
from iad_sieve.evaluation.remote_output_validator import build_remote_output_validation_rows, write_remote_output_validation_outputs
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


def _write_text(path, content: str) -> None:
    """写入文本测试文件。

    参数:
        path: 输出路径。
        content: 文件内容。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_remote_output_validation_rows_marks_missing_empty_valid_and_invalid_files(tmp_path) -> None:
    """验证输出验收能区分缺失、空文件、有效文件和格式错误文件。"""
    _write_text(tmp_path / "outputs" / "valid.jsonl", "{\"ok\": true}\n")
    _write_text(tmp_path / "outputs" / "empty.jsonl", "")
    _write_text(tmp_path / "outputs" / "broken.jsonl", "{bad json\n")
    manifest_rows = [
        {"task_id": "run_valid", "required_output": "outputs/valid.jsonl"},
        {"task_id": "run_empty", "required_output": "outputs/empty.jsonl"},
        {"task_id": "run_broken", "required_output": "outputs/broken.jsonl"},
        {"task_id": "run_missing", "required_output": "outputs/missing.jsonl"},
    ]

    rows = build_remote_output_validation_rows(manifest_rows, workspace_dir=tmp_path)
    by_task = {row["task_id"]: row for row in rows}

    assert by_task["run_valid"]["validation_status"] == "valid"
    assert by_task["run_valid"]["record_count"] == 1
    assert by_task["run_empty"]["validation_status"] == "empty"
    assert by_task["run_broken"]["validation_status"] == "invalid_format"
    assert by_task["run_missing"]["validation_status"] == "missing"


def test_write_remote_output_validation_outputs_writes_jsonl_csv_markdown_and_summary(tmp_path) -> None:
    """验证远程输出验收写出 JSONL、CSV、Markdown 和 summary。"""
    rows = [
        {"task_id": "run_valid", "required_output": "outputs/valid.jsonl", "validation_status": "valid", "record_count": 2, "file_size_bytes": 20, "format_issue": ""},
        {"task_id": "run_missing", "required_output": "outputs/missing.jsonl", "validation_status": "missing", "record_count": 0, "file_size_bytes": 0, "format_issue": "missing_file"},
    ]
    output_dir = tmp_path / "remote_validation"

    write_remote_output_validation_outputs(rows, output_dir)

    assert read_records(output_dir / "remote_output_validation.jsonl")[0]["task_id"] == "run_valid"
    assert (output_dir / "remote_output_validation.csv").exists()
    assert "# Remote Output Validation" in (output_dir / "remote_output_validation.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "remote_output_validation_summary.jsonl")[0]
    assert summary["total_output_count"] == 2
    assert summary["valid_output_count"] == 1
    assert summary["all_outputs_valid"] is False


def test_write_remote_output_validation_outputs_treats_empty_manifest_as_no_pending_outputs(tmp_path) -> None:
    """验证空 manifest 表示当前无待验收远程输出。"""
    output_dir = tmp_path / "remote_validation"

    write_remote_output_validation_outputs([], output_dir)

    summary = read_records(output_dir / "remote_output_validation_summary.jsonl")[0]
    assert summary["total_output_count"] == 0
    assert summary["missing_output_count"] == 0
    assert summary["no_required_outputs"] is True
    assert summary["all_outputs_valid"] is True


def test_validate_remote_outputs_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出远程输出验收报告。"""
    manifest = tmp_path / "remote_output_manifest.jsonl"
    output_dir = tmp_path / "remote_validation"
    _write_text(tmp_path / "outputs" / "valid.jsonl", "{\"ok\": true}\n")
    _write_jsonl(manifest, [{"task_id": "run_valid", "required_output": "outputs/valid.jsonl"}])

    command_validate_remote_outputs(
        Namespace(
            manifest=str(manifest),
            workspace_dir=str(tmp_path),
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "remote_output_validation.jsonl")[0]["validation_status"] == "valid"
    assert (output_dir / "remote_output_validation.md").exists()


def test_cli_includes_validate_remote_outputs_command() -> None:
    """验证 CLI 暴露 validate-remote-outputs 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "validate-remote-outputs",
            "--manifest",
            "outputs/experiment_execution_pack_fixture/remote_output_manifest.jsonl",
            "--workspace-dir",
            ".",
            "--output-dir",
            "outputs/remote_output_validation_fixture",
        ]
    )

    assert args.command == "validate-remote-outputs"
    assert args.manifest == "outputs/experiment_execution_pack_fixture/remote_output_manifest.jsonl"
