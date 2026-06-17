"""IAD-Bench 公开来源获取审计模块。"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
DEEPMATCHER_STRUCTURED_ZIP_URL = "http://pages.cs.wisc.edu/~anhai/data1/deepmatcher_data/Structured.zip"
DEEPMATCHER_TEXTUAL_ZIP_URL = "http://pages.cs.wisc.edu/~anhai/data1/deepmatcher_data/Textual.zip"
PREFERRED_FIELDS = [
    "candidate_id",
    "relation_label",
    "local_status",
    "acquisition_blocker",
    "source_id",
    "source_name",
    "adapter_format",
    "planned_label_strength",
    "target_pair_count",
    "required_files",
    "missing_required_files",
    "missing_required_file_count",
    "invalid_required_files",
    "invalid_required_file_count",
    "valid_citation_edge_count",
    "download_url",
    "download_command",
    "conversion_command",
    "reviewer_value",
    "paper_claim_boundary",
]


def _clean(value: object) -> str:
    """清理字符串字段。

    参数:
        value: 原始值。

    返回:
        去除空白后的字符串。
    """
    return str(value or "").strip()


def _safe_suffix(value: str) -> str:
    """生成安全路径后缀。

    参数:
        value: 原始字符串。

    返回:
        只包含字母、数字和下划线的后缀。
    """
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    return cleaned.strip("_") or "source"


def _extract_option_path(command: str, option_name: str) -> str:
    """从命令字符串中提取 option 后的路径。

    参数:
        command: 命令字符串。
        option_name: 参数名，例如 --works。

    返回:
        参数值；缺失时返回空字符串。
    """
    pattern = rf"{re.escape(option_name)}\s+([^ ]+)"
    match = re.search(pattern, command)
    return match.group(1).strip('"') if match else ""


def _existing_and_missing(workspace_dir: Path, required_files: list[str]) -> tuple[list[str], list[str]]:
    """拆分已存在和缺失文件。

    参数:
        workspace_dir: 工作区目录。
        required_files: 相对工作区的必需文件路径。

    返回:
        已存在路径列表和缺失路径列表。
    """
    existing: list[str] = []
    missing: list[str] = []
    for relative_path in required_files:
        if (workspace_dir / relative_path).exists():
            existing.append(relative_path)
        else:
            missing.append(relative_path)
    return existing, missing


def _first_existing_value(row: dict[str, str], field_names: list[str]) -> str:
    """读取 CSV 行中的第一个非空字段值。

    参数:
        row: CSV 行。
        field_names: 候选字段名。

    返回:
        去除首尾空白后的字段值。
    """
    for field_name in field_names:
        value = _clean(row.get(field_name))
        if value:
            return value
    return ""


def _valid_citation_edge_count(path: Path) -> int:
    """统计 COCI 风格 CSV 中有效 DOI-to-DOI 引用边数量。

    参数:
        path: COCI 风格 CSV 文件路径。

    返回:
        同时包含 citing 与 cited DOI 的记录数量。
    """
    try:
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames:
                return 0
            count = 0
            for row in reader:
                citing = _first_existing_value(row, ["citing", "citing_doi", "source_doi", "from_doi"])
                cited = _first_existing_value(row, ["cited", "cited_doi", "target_doi", "to_doi"])
                if citing and cited:
                    count += 1
            return count
    except OSError:
        LOGGER.exception("读取 OpenCitations COCI 文件失败: %s", path)
        return 0


def _deepmatcher_download_url(row: dict) -> str:
    """根据 DeepMatcher 来源选择公开下载包。

    参数:
        row: registry 记录。

    返回:
        下载 URL。
    """
    source_id = _clean(row.get("source_id")).lower()
    source_domain = _clean(row.get("source_domain")).lower()
    if "abt_buy" in source_id or "text" in source_domain:
        return DEEPMATCHER_TEXTUAL_ZIP_URL
    return DEEPMATCHER_STRUCTURED_ZIP_URL


def _deepmatcher_required_files(row: dict) -> list[str]:
    """构造 DeepMatcher 候选所需 raw 文件。

    参数:
        row: registry 记录。

    返回:
        相对工作区的必需文件路径。
    """
    source_id = _safe_suffix(_clean(row.get("source_id")) or _clean(row.get("candidate_id")))
    source_dir = f"data/raw/deepmatcher/{source_id}"
    return [
        f"{source_dir}/tableA.csv",
        f"{source_dir}/tableB.csv",
        f"{source_dir}/train.csv",
        f"{source_dir}/valid.csv",
        f"{source_dir}/test.csv",
    ]


def _deepmatcher_conversion_command(row: dict) -> str:
    """构造 DeepMatcher 三个 split 的转换命令。

    参数:
        row: registry 记录。

    返回:
        转换命令字符串。
    """
    template = _clean(row.get("command_template"))
    if not template:
        return ""
    return " && ".join(template.replace("{split}", split) for split in ["train", "valid", "test"])


def _deepmatcher_acquisition_row(row: dict, workspace_dir: Path) -> dict:
    """构造 DeepMatcher 获取审计记录。

    参数:
        row: registry 记录。
        workspace_dir: 工作区目录。

    返回:
        acquisition audit 记录。
    """
    required_files = _deepmatcher_required_files(row)
    _, missing_files = _existing_and_missing(workspace_dir, required_files)
    download_url = _deepmatcher_download_url(row)
    local_status = "ready_to_convert" if not missing_files else "blocked_missing_raw_files"
    return {
        "candidate_id": _clean(row.get("candidate_id")),
        "relation_label": _clean(row.get("relation_label")),
        "local_status": local_status,
        "acquisition_blocker": "" if not missing_files else "deepmatcher_preprocessed_zip_required",
        "source_id": _clean(row.get("source_id")),
        "source_name": _clean(row.get("source_name")),
        "adapter_format": _clean(row.get("adapter_format")),
        "planned_label_strength": _clean(row.get("planned_label_strength")),
        "target_pair_count": row.get("target_pair_count", ""),
        "required_files": required_files,
        "missing_required_files": missing_files,
        "missing_required_file_count": len(missing_files),
        "invalid_required_files": [],
        "invalid_required_file_count": 0,
        "valid_citation_edge_count": "",
        "download_url": download_url,
        "download_command": f"curl -L -o data/raw/deepmatcher_downloads/{Path(download_url).name} {download_url}",
        "conversion_command": _deepmatcher_conversion_command(row),
        "reviewer_value": "把公开 gold 候选转成可验收的本地 raw 文件和转换命令，支撑后续 source balance。",
        "paper_claim_boundary": "local_status 不是 ready_to_convert 前，不能写成该公开来源已进入 IAD-Bench。",
    }


def _opencitations_required_files(row: dict) -> list[str]:
    """构造 OpenAlex/OpenCitations 候选所需 raw 文件。

    参数:
        row: registry 记录。

    返回:
        相对工作区的必需文件路径。
    """
    fetch_command = _clean(row.get("fetch_command"))
    weak_label_command = _clean(row.get("weak_label_command"))
    works_path = _extract_option_path(fetch_command, "--output") or _extract_option_path(weak_label_command, "--works")
    citations_path = _extract_option_path(weak_label_command, "--citations")
    return [path for path in [works_path, citations_path] if path]


def _opencitations_acquisition_row(row: dict, workspace_dir: Path) -> dict:
    """构造 OpenAlex/OpenCitations 获取审计记录。

    参数:
        row: registry 记录。
        workspace_dir: 工作区目录。

    返回:
        acquisition audit 记录。
    """
    required_files = _opencitations_required_files(row)
    _, missing_files = _existing_and_missing(workspace_dir, required_files)
    citations_path_text = _extract_option_path(_clean(row.get("weak_label_command")), "--citations")
    citations_path = workspace_dir / citations_path_text if citations_path_text else None
    valid_citation_edge_count = 0
    invalid_files: list[str] = []
    if citations_path_text and citations_path_text not in missing_files and citations_path is not None:
        valid_citation_edge_count = _valid_citation_edge_count(citations_path)
        if valid_citation_edge_count <= 0:
            invalid_files.append(citations_path_text)
    if missing_files:
        local_status = "blocked_missing_raw_files"
        acquisition_blocker = "opencitations_subset_required"
    elif invalid_files:
        local_status = "blocked_invalid_raw_files"
        acquisition_blocker = "opencitations_valid_edges_required"
    else:
        local_status = "ready_to_convert"
        acquisition_blocker = ""
    return {
        "candidate_id": _clean(row.get("candidate_id")),
        "relation_label": _clean(row.get("relation_label")),
        "local_status": local_status,
        "acquisition_blocker": acquisition_blocker,
        "source_id": _clean(row.get("source_id")),
        "source_name": _clean(row.get("source_name")),
        "adapter_format": _clean(row.get("adapter_format")),
        "planned_label_strength": _clean(row.get("planned_label_strength")),
        "target_pair_count": row.get("target_pair_count", ""),
        "required_files": required_files,
        "missing_required_files": missing_files,
        "missing_required_file_count": len(missing_files),
        "invalid_required_files": invalid_files,
        "invalid_required_file_count": len(invalid_files),
        "valid_citation_edge_count": valid_citation_edge_count,
        "download_url": "https://opencitations.net/index/coci",
        "download_command": _clean(row.get("fetch_command")),
        "conversion_command": _clean(row.get("weak_label_command")),
        "reviewer_value": "把 OpenAlex/OpenCitations silver 候选转成 works 与 COCI 子集验收条件。",
        "paper_claim_boundary": "该来源仍为 silver hard negative；未生成 works 与 COCI 子集前，不能写成来源平衡完成。",
    }


def _unsupported_acquisition_row(row: dict) -> dict:
    """构造未支持候选的获取审计记录。

    参数:
        row: registry 记录。

    返回:
        acquisition audit 记录。
    """
    return {
        "candidate_id": _clean(row.get("candidate_id")),
        "relation_label": _clean(row.get("relation_label")),
        "local_status": "blocked_unsupported_adapter",
        "acquisition_blocker": "converter_required",
        "source_id": _clean(row.get("source_id")),
        "source_name": _clean(row.get("source_name")),
        "adapter_format": _clean(row.get("adapter_format")),
        "planned_label_strength": _clean(row.get("planned_label_strength")),
        "target_pair_count": row.get("target_pair_count", ""),
        "required_files": [],
        "missing_required_files": [],
        "missing_required_file_count": 0,
        "invalid_required_files": [],
        "invalid_required_file_count": 0,
        "valid_citation_edge_count": "",
        "download_url": _clean(row.get("source_url")),
        "download_command": "",
        "conversion_command": "",
        "reviewer_value": "标出当前适配器尚不能直接承接的公开来源。",
        "paper_claim_boundary": "转换器完成前，不得把该候选写入 IAD-Bench 结果。",
    }


def build_iad_bench_source_acquisition_audit_rows(registry_rows: list[dict], workspace_dir: str | Path = ".") -> list[dict]:
    """构建 IAD-Bench 公开来源获取审计记录。

    参数:
        registry_rows: source candidate registry 记录。
        workspace_dir: 工作区目录。

    返回:
        获取审计记录。
    """
    resolved_workspace_dir = Path(workspace_dir)
    try:
        rows: list[dict] = []
        for row in registry_rows:
            adapter_format = _clean(row.get("adapter_format"))
            if adapter_format == "deepmatcher_like_csv":
                rows.append(_deepmatcher_acquisition_row(row, resolved_workspace_dir))
            elif adapter_format == "openalex_works_plus_opencitations_coci_csv":
                rows.append(_opencitations_acquisition_row(row, resolved_workspace_dir))
            else:
                rows.append(_unsupported_acquisition_row(row))
        rows.sort(key=lambda item: (item["local_status"], item["candidate_id"]))
        LOGGER.info("IAD-Bench 公开来源获取审计完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建 IAD-Bench 公开来源获取审计失败")
        raise


def build_iad_bench_source_acquisition_audit_rows_from_paths(registry_path: str | Path, workspace_dir: str | Path = ".") -> list[dict]:
    """从 registry 文件构建公开来源获取审计。

    参数:
        registry_path: source candidate registry JSONL。
        workspace_dir: 工作区目录。

    返回:
        获取审计记录。
    """
    try:
        return build_iad_bench_source_acquisition_audit_rows(read_records(registry_path), workspace_dir=workspace_dir)
    except Exception:
        LOGGER.exception("读取 IAD-Bench 公开来源获取审计输入失败: %s", registry_path)
        raise


def _serialize_cell(value: object) -> object:
    """序列化 CSV / Markdown 单元格。

    参数:
        value: 原始值。

    返回:
        可写入单元格的值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出公开来源获取审计 CSV。

    参数:
        path: 输出路径。
        rows: 审计记录。

    返回:
        无。
    """
    fields = [field for field in PREFERRED_FIELDS if any(field in row for row in rows)]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_cell(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出 IAD-Bench 公开来源获取审计 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建公开来源获取审计汇总。

    参数:
        rows: 审计记录。

    返回:
        summary 记录。
    """
    blocked_missing_count = sum(1 for row in rows if row.get("local_status") == "blocked_missing_raw_files")
    blocked_invalid_count = sum(1 for row in rows if row.get("local_status") == "blocked_invalid_raw_files")
    unsupported_count = sum(1 for row in rows if row.get("local_status") == "blocked_unsupported_adapter")
    return {
        "candidate_count": len(rows),
        "ready_to_convert_count": sum(1 for row in rows if row.get("local_status") == "ready_to_convert"),
        "blocked_missing_raw_files_count": blocked_missing_count,
        "blocked_invalid_raw_files_count": blocked_invalid_count,
        "blocked_unsupported_adapter_count": unsupported_count,
        "deepmatcher_candidate_count": sum(1 for row in rows if row.get("adapter_format") == "deepmatcher_like_csv"),
        "opencitations_candidate_count": sum(1 for row in rows if row.get("adapter_format") == "openalex_works_plus_opencitations_coci_csv"),
        "missing_raw_file_count": sum(int(row.get("missing_required_file_count", 0) or 0) for row in rows),
        "invalid_raw_file_count": sum(int(row.get("invalid_required_file_count", 0) or 0) for row in rows),
        "overall_acquisition_status": "blocked" if blocked_missing_count or blocked_invalid_count or unsupported_count else "ready",
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出公开来源获取审计 Markdown。

    参数:
        path: 输出路径。
        rows: 审计记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = ["candidate_id", "relation_label", "local_status", "missing_required_file_count", "acquisition_blocker", "download_url"]
    lines = [
        "# IAD-Bench Source Acquisition Audit",
        "",
        "## 使用边界",
        "",
        "该审计只检查公开候选来源的本地 raw 文件是否齐备，并给出下载与转换命令；它不是数据转换结果，也不能替代 source-held-out 评估。",
        "",
        "## 汇总",
        "",
        f"- candidate_count: {summary['candidate_count']}",
        f"- ready_to_convert_count: {summary['ready_to_convert_count']}",
        f"- blocked_missing_raw_files_count: {summary['blocked_missing_raw_files_count']}",
        f"- blocked_unsupported_adapter_count: {summary['blocked_unsupported_adapter_count']}",
        f"- missing_raw_file_count: {summary['missing_raw_file_count']}",
        f"- overall_acquisition_status: {summary['overall_acquisition_status']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        values = [str(_serialize_cell(row.get(field, ""))).replace("\n", " ").replace("|", "/") for field in fields]
        lines.append("| " + " | ".join(values) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 IAD-Bench 公开来源获取审计 Markdown 失败: %s", path)
        raise


def write_iad_bench_source_acquisition_audit_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出公开来源获取审计产物。

    参数:
        rows: 审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "iad_bench_source_acquisition_audit.jsonl")
        write_records([summary], directory / "iad_bench_source_acquisition_audit_summary.jsonl")
        _write_csv(directory / "iad_bench_source_acquisition_audit.csv", rows)
        _write_markdown(directory / "iad_bench_source_acquisition_audit.md", rows, summary)
    except Exception:
        LOGGER.exception("写出 IAD-Bench 公开来源获取审计失败: %s", output_dir)
        raise
