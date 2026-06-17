"""远程输出验收验证模块。"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "task_id",
    "required_output",
    "validation_status",
    "record_count",
    "file_size_bytes",
    "format_issue",
]


def _resolve_output_path(workspace_dir: str | Path, required_output: str) -> Path:
    """解析输出路径。

    参数:
        workspace_dir: 工作区目录。
        required_output: 输出路径，可以是相对路径或绝对路径。

    返回:
        解析后的 Path。
    """
    output_path = Path(required_output)
    if output_path.is_absolute():
        return output_path
    return Path(workspace_dir) / output_path


def _count_jsonl_records(path: Path) -> tuple[int, str]:
    """统计 JSONL 记录数并检查格式。

    参数:
        path: JSONL 文件路径。

    返回:
        记录数和格式问题；无问题时格式问题为空字符串。
    """
    count = 0
    try:
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                json.loads(stripped)
                count += 1
    except json.JSONDecodeError as error:
        return count, f"json_decode_error_line_{line_number}: {error.msg}"
    except OSError as error:
        return count, f"io_error: {error}"
    return count, ""


def _count_csv_records(path: Path) -> tuple[int, str]:
    """统计 CSV 数据行数并检查格式。

    参数:
        path: CSV 文件路径。

    返回:
        数据行数和格式问题；无问题时格式问题为空字符串。
    """
    try:
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.reader(file)
            rows = list(reader)
    except csv.Error as error:
        return 0, f"csv_error: {error}"
    except OSError as error:
        return 0, f"io_error: {error}"
    if not rows:
        return 0, ""
    return max(0, len(rows) - 1), ""


def _count_text_records(path: Path) -> tuple[int, str]:
    """统计普通文本非空行数。

    参数:
        path: 文本文件路径。

    返回:
        非空行数和格式问题；无问题时格式问题为空字符串。
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        return 0, f"io_error: {error}"
    return sum(1 for line in lines if line.strip()), ""


def _validate_file(path: Path) -> tuple[str, int, int, str]:
    """验证单个输出文件。

    参数:
        path: 输出文件路径。

    返回:
        validation_status、record_count、file_size_bytes 和 format_issue。
    """
    if not path.exists():
        return "missing", 0, 0, "missing_file"
    if path.is_dir():
        child_count = sum(1 for _ in path.iterdir())
        return ("valid" if child_count else "empty", child_count, 0, "" if child_count else "empty_directory")
    file_size = path.stat().st_size
    if file_size == 0:
        return "empty", 0, file_size, "empty_file"
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        record_count, issue = _count_jsonl_records(path)
    elif suffix == ".csv":
        record_count, issue = _count_csv_records(path)
    else:
        record_count, issue = _count_text_records(path)
    if issue:
        return "invalid_format", record_count, file_size, issue
    return "valid", record_count, file_size, ""


def build_remote_output_validation_rows(manifest_rows: list[dict], workspace_dir: str | Path) -> list[dict]:
    """构建远程输出验收记录。

    参数:
        manifest_rows: remote_output_manifest 记录。
        workspace_dir: 工作区目录。

    返回:
        输出验收记录列表。
    """
    rows: list[dict] = []
    try:
        for manifest_row in manifest_rows:
            required_output = str(manifest_row.get("required_output", "")).strip()
            if not required_output:
                continue
            output_path = _resolve_output_path(workspace_dir, required_output)
            status, record_count, file_size, issue = _validate_file(output_path)
            rows.append(
                {
                    "task_id": manifest_row.get("task_id", ""),
                    "execution_stage": manifest_row.get("execution_stage", ""),
                    "required_output": required_output,
                    "resolved_path": str(output_path),
                    "validation_status": status,
                    "record_count": record_count,
                    "file_size_bytes": file_size,
                    "format_issue": issue,
                    "reviewer_value": manifest_row.get("reviewer_value", ""),
                }
            )
        LOGGER.info("远程输出验收完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建远程输出验收失败")
        raise


def build_remote_output_validation_rows_from_path(manifest_path: str | Path, workspace_dir: str | Path) -> list[dict]:
    """从 manifest 文件构建远程输出验收记录。

    参数:
        manifest_path: remote_output_manifest JSONL 文件。
        workspace_dir: 工作区目录。

    返回:
        输出验收记录列表。
    """
    try:
        manifest_rows = read_records(manifest_path)
    except Exception:
        LOGGER.exception("读取远程输出 manifest 失败: %s", manifest_path)
        raise
    return build_remote_output_validation_rows(manifest_rows, workspace_dir)


def _serialize_csv_value(value: object) -> object:
    """序列化 CSV 单元格值。

    参数:
        value: 原始值。

    返回:
        可写入 CSV 的值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 验收报告。

    参数:
        path: 输出路径。
        rows: 验收记录。

    返回:
        无。
    """
    fields: list[str] = []
    for field in PREFERRED_FIELDS:
        if field not in fields:
            fields.append(field)
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
        LOGGER.exception("写出远程输出验收 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建远程输出验收汇总。

    参数:
        rows: 验收记录。

    返回:
        汇总记录。
    """
    total = len(rows)
    valid = sum(1 for row in rows if row.get("validation_status") == "valid")
    missing = sum(1 for row in rows if row.get("validation_status") == "missing")
    empty = sum(1 for row in rows if row.get("validation_status") == "empty")
    invalid = sum(1 for row in rows if row.get("validation_status") == "invalid_format")
    return {
        "total_output_count": total,
        "valid_output_count": valid,
        "missing_output_count": missing,
        "empty_output_count": empty,
        "invalid_format_count": invalid,
        "no_required_outputs": total == 0,
        "all_outputs_valid": valid == total and missing == 0 and empty == 0 and invalid == 0,
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 验收报告。

    参数:
        path: 输出路径。
        rows: 验收记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = ["task_id", "required_output", "validation_status", "record_count", "format_issue"]
    lines = [
        "# Remote Output Validation",
        "",
        "## 使用边界",
        "",
        "该报告只验证远程输出文件是否存在、非空且格式可解析，不替代指标正确性或论文结论审查。",
        "",
        "## 汇总",
        "",
        f"- total_output_count: {summary['total_output_count']}",
        f"- valid_output_count: {summary['valid_output_count']}",
        f"- missing_output_count: {summary['missing_output_count']}",
        f"- empty_output_count: {summary['empty_output_count']}",
        f"- invalid_format_count: {summary['invalid_format_count']}",
        f"- no_required_outputs: {summary['no_required_outputs']}",
        f"- all_outputs_valid: {summary['all_outputs_valid']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        values = [_serialize_csv_value(row.get(field, "")) for field in fields]
        lines.append("| " + " | ".join(str(value).replace("\n", " ").replace("|", "/") for value in values) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出远程输出验收 Markdown 失败: %s", path)
        raise


def write_remote_output_validation_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出远程输出验收 JSONL、CSV、Markdown 和汇总。

    参数:
        rows: 验收记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "remote_output_validation.jsonl")
        _write_csv(directory / "remote_output_validation.csv", rows)
        write_records([summary], directory / "remote_output_validation_summary.jsonl")
        _write_markdown(directory / "remote_output_validation.md", rows, summary)
    except Exception:
        LOGGER.exception("写出远程输出验收失败: %s", output_dir)
        raise
