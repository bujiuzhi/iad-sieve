"""测试 IAD-Bench 公开来源获取审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_iad_bench_source_acquisition_audit
from iad_sieve.evaluation.iad_bench_source_acquisition_audit import (
    build_iad_bench_source_acquisition_audit_rows,
    build_iad_bench_source_acquisition_audit_rows_from_paths,
    write_iad_bench_source_acquisition_audit_outputs,
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


def _write_text(path, content: str = "id,title\n") -> None:
    """写入文本测试文件。

    参数:
        path: 输出路径。
        content: 文件内容。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _deepmatcher_registry_row(source_id: str = "deepmatcher_dblp_scholar") -> dict:
    """构造 DeepMatcher registry 测试记录。

    参数:
        source_id: 来源 ID。

    返回:
        registry 记录。
    """
    return {
        "candidate_id": f"same_work_{source_id}",
        "relation_label": "same_work",
        "source_id": source_id,
        "source_name": "DeepMatcher DBLP-Scholar",
        "source_domain": "citation",
        "planned_label_strength": "gold",
        "adapter_format": "deepmatcher_like_csv",
        "existing_adapter": "prepare-deepmatcher",
        "target_pair_count": 500,
        "command_template": (
            "python -m iad_sieve.cli prepare-deepmatcher "
            f"--table-a data/raw/deepmatcher/{source_id}/tableA.csv "
            f"--table-b data/raw/deepmatcher/{source_id}/tableB.csv "
            f"--pairs data/raw/deepmatcher/{source_id}/{{split}}.csv "
            '--dataset-name "DBLP-Scholar" '
            f"--output-dir outputs/deepmatcher_open_v3/{source_id}/{{split}}"
        ),
    }


def _opencitations_registry_row() -> dict:
    """构造 OpenAlex/OpenCitations registry 测试记录。

    参数:
        无。

    返回:
        registry 记录。
    """
    return {
        "candidate_id": "agenda_non_identity_opencitations_coci_T10009",
        "relation_label": "agenda_non_identity",
        "source_id": "opencitations_coci_T10009",
        "source_name": "OpenAlex topic T10009 with OpenCitations COCI",
        "planned_label_strength": "silver",
        "adapter_format": "openalex_works_plus_opencitations_coci_csv",
        "existing_adapter": "prepare-openalex-weak-labels",
        "target_pair_count": 2500,
        "fetch_command": "python -m iad_sieve.cli fetch-openalex-works --output data/raw/openalex/source_registry_T10009_works.jsonl",
        "weak_label_command": (
            "python -m iad_sieve.cli prepare-openalex-weak-labels "
            "--works data/raw/openalex/source_registry_T10009_works.jsonl "
            "--citations data/raw/opencitations/coci_T10009.csv "
            "--dataset-name openalex_opencitations_T10009 "
            "--output-dir outputs/openalex_opencitations_source_registry/T10009"
        ),
    }


def test_build_iad_bench_source_acquisition_audit_rows_flags_missing_deepmatcher_files(tmp_path) -> None:
    """验证缺失 DeepMatcher 本地 raw 文件时输出阻塞与下载命令。"""
    rows = build_iad_bench_source_acquisition_audit_rows(
        registry_rows=[_deepmatcher_registry_row()],
        workspace_dir=tmp_path,
    )

    row = rows[0]

    assert row["local_status"] == "blocked_missing_raw_files"
    assert row["missing_required_file_count"] == 5
    assert "Structured.zip" in row["download_command"]
    assert "prepare-deepmatcher" in row["conversion_command"]
    assert "data/raw/deepmatcher/deepmatcher_dblp_scholar/tableA.csv" in row["required_files"]


def test_build_iad_bench_source_acquisition_audit_rows_marks_deepmatcher_ready(tmp_path) -> None:
    """验证 DeepMatcher raw 文件齐备时标记为 ready_to_convert。"""
    source_dir = tmp_path / "data" / "raw" / "deepmatcher" / "deepmatcher_dblp_scholar"
    for file_name in ["tableA.csv", "tableB.csv", "train.csv", "valid.csv", "test.csv"]:
        _write_text(source_dir / file_name)

    rows = build_iad_bench_source_acquisition_audit_rows(
        registry_rows=[_deepmatcher_registry_row()],
        workspace_dir=tmp_path,
    )

    assert rows[0]["local_status"] == "ready_to_convert"
    assert rows[0]["missing_required_file_count"] == 0


def test_build_iad_bench_source_acquisition_audit_rows_handles_opencitations_candidate(tmp_path) -> None:
    """验证 OpenAlex/OpenCitations 候选检查 works 与 COCI 文件。"""
    rows = build_iad_bench_source_acquisition_audit_rows(
        registry_rows=[_opencitations_registry_row()],
        workspace_dir=tmp_path,
    )

    row = rows[0]

    assert row["local_status"] == "blocked_missing_raw_files"
    assert row["missing_required_file_count"] == 2
    assert "fetch-openalex-works" in row["download_command"]
    assert "data/raw/opencitations/coci_T10009.csv" in row["required_files"]
    assert row["acquisition_blocker"] == "opencitations_subset_required"


def test_build_iad_bench_source_acquisition_audit_rows_blocks_invalid_coci_file(tmp_path) -> None:
    """验证空 COCI 文件不能被误判为 ready_to_convert。"""
    _write_text(tmp_path / "data/raw/openalex/source_registry_T10009_works.jsonl", "{}\n")
    _write_text(tmp_path / "data/raw/opencitations/coci_T10009.csv", "citing,cited\n")

    rows = build_iad_bench_source_acquisition_audit_rows(
        registry_rows=[_opencitations_registry_row()],
        workspace_dir=tmp_path,
    )
    row = rows[0]

    assert row["local_status"] == "blocked_invalid_raw_files"
    assert row["missing_required_file_count"] == 0
    assert row["invalid_required_file_count"] == 1
    assert row["valid_citation_edge_count"] == 0
    assert row["acquisition_blocker"] == "opencitations_valid_edges_required"


def test_build_iad_bench_source_acquisition_audit_rows_marks_valid_coci_ready(tmp_path) -> None:
    """验证 COCI 文件存在且包含有效 DOI 引用边时标记为 ready_to_convert。"""
    _write_text(tmp_path / "data/raw/openalex/source_registry_T10009_works.jsonl", "{}\n")
    _write_text(
        tmp_path / "data/raw/opencitations/coci_T10009.csv",
        "citing,cited\n10.1000/a,10.1000/c\n10.1000/b,10.1000/c\n",
    )

    rows = build_iad_bench_source_acquisition_audit_rows(
        registry_rows=[_opencitations_registry_row()],
        workspace_dir=tmp_path,
    )
    row = rows[0]

    assert row["local_status"] == "ready_to_convert"
    assert row["missing_required_file_count"] == 0
    assert row["invalid_required_file_count"] == 0
    assert row["valid_citation_edge_count"] == 2
    assert row["acquisition_blocker"] == ""


def test_build_iad_bench_source_acquisition_audit_rows_from_paths_reads_registry(tmp_path) -> None:
    """验证 acquisition audit 可从 registry 文件读取输入。"""
    registry_path = tmp_path / "registry.jsonl"
    _write_jsonl(registry_path, [_deepmatcher_registry_row()])

    rows = build_iad_bench_source_acquisition_audit_rows_from_paths(
        registry_path=registry_path,
        workspace_dir=tmp_path,
    )

    assert rows[0]["candidate_id"] == "same_work_deepmatcher_dblp_scholar"


def test_write_iad_bench_source_acquisition_audit_outputs_writes_files(tmp_path) -> None:
    """验证 acquisition audit 写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "acquisition"
    rows = build_iad_bench_source_acquisition_audit_rows(
        registry_rows=[_deepmatcher_registry_row()],
        workspace_dir=tmp_path,
    )

    write_iad_bench_source_acquisition_audit_outputs(rows, output_dir)

    assert read_records(output_dir / "iad_bench_source_acquisition_audit.jsonl")[0]["candidate_id"] == "same_work_deepmatcher_dblp_scholar"
    assert (output_dir / "iad_bench_source_acquisition_audit.csv").exists()
    assert "# IAD-Bench Source Acquisition Audit" in (output_dir / "iad_bench_source_acquisition_audit.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "iad_bench_source_acquisition_audit_summary.jsonl")[0]
    assert summary["candidate_count"] == 1
    assert summary["blocked_missing_raw_files_count"] == 1
    assert summary["overall_acquisition_status"] == "blocked"


def test_build_iad_bench_source_acquisition_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出公开来源获取审计。"""
    registry_path = tmp_path / "registry.jsonl"
    output_dir = tmp_path / "acquisition"
    _write_jsonl(registry_path, [_deepmatcher_registry_row()])

    command_build_iad_bench_source_acquisition_audit(
        Namespace(
            registry=str(registry_path),
            output_dir=str(output_dir),
            workspace_dir=str(tmp_path),
        )
    )

    assert (output_dir / "iad_bench_source_acquisition_audit.jsonl").exists()
    assert (output_dir / "iad_bench_source_acquisition_audit_summary.jsonl").exists()


def test_cli_includes_build_iad_bench_source_acquisition_audit_command() -> None:
    """验证 CLI 暴露 build-iad-bench-source-acquisition-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-iad-bench-source-acquisition-audit",
            "--registry",
            "outputs/iad_bench_source_candidate_registry_fixture/iad_bench_source_candidate_registry.jsonl",
            "--output-dir",
            "outputs/iad_bench_source_acquisition_audit_fixture",
            "--workspace-dir",
            ".",
        ]
    )

    assert args.command == "build-iad-bench-source-acquisition-audit"
    assert args.workspace_dir == "."
