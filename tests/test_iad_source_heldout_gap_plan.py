"""测试 IAD source-held-out 缺口补齐计划。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_iad_source_heldout_gap_plan
from iad_sieve.evaluation.iad_source_heldout_gap_plan import (
    build_iad_source_heldout_gap_plan_rows,
    build_iad_source_heldout_gap_plan_rows_from_paths,
    build_iad_source_heldout_gap_plan_summary,
    write_iad_source_heldout_gap_plan_outputs,
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


def _coverage_row(relation_label: str, status: str = "blocked_missing_relation") -> dict:
    """构造覆盖审计测试记录。

    参数:
        relation_label: IAD 关系标签。
        status: 覆盖审计状态。

    返回:
        覆盖审计记录。
    """
    return {
        "relation_label": relation_label,
        "audit_status": status,
        "coverage_blockers": "missing_train_pairs; missing_test_pairs" if status.startswith("blocked") else "",
        "train_pair_count": 0 if status.startswith("blocked") else 10,
        "test_pair_count": 0 if status.startswith("blocked") else 5,
    }


def _candidate_row(relation_label: str = "agenda_non_identity") -> dict:
    """构造候选来源测试记录。

    参数:
        relation_label: IAD 关系标签。

    返回:
        候选来源记录。
    """
    return {
        "candidate_id": "agenda_non_identity_opencitations_coci_T10009",
        "relation_label": relation_label,
        "candidate_status": "requires_openalex_and_citations_download",
        "source_name": "OpenAlex topic T10009 with OpenCitations COCI",
        "planned_label_strength": "silver",
        "planned_label_source": "openalex_opencitations",
        "target_pair_count": 2500,
        "fetch_command": "python -m iad_sieve.cli fetch-openalex-works --output data/raw/openalex/T10009.jsonl",
        "weak_label_command": "python -m iad_sieve.cli prepare-openalex-weak-labels --works data/raw/openalex/T10009.jsonl",
        "paper_claim_boundary": "完成前不能写成 source-held-out 泛化。",
    }


def test_build_iad_source_heldout_gap_plan_maps_missing_relation_to_candidate_commands() -> None:
    """验证缺失关系会映射到候选来源和可执行命令。"""
    rows = build_iad_source_heldout_gap_plan_rows(
        coverage_rows=[_coverage_row("same_work", "limited_source_heldout_coverage"), _coverage_row("agenda_non_identity")],
        candidate_rows=[_candidate_row()],
    )
    summary = build_iad_source_heldout_gap_plan_summary(rows)

    assert rows[0]["relation_label"] == "agenda_non_identity"
    assert rows[0]["gap_status"] == "candidate_available"
    assert rows[0]["candidate_id"] == "agenda_non_identity_opencitations_coci_T10009"
    assert "fetch-openalex-works" in rows[0]["acquisition_commands"]
    assert "prepare-openalex-weak-labels" in rows[0]["acquisition_commands"]
    assert summary["gap_relation_count"] == 1
    assert summary["candidate_action_count"] == 1
    assert summary["highest_priority_relation"] == "agenda_non_identity"


def test_build_iad_source_heldout_gap_plan_marks_missing_candidate() -> None:
    """验证没有候选来源时输出 no_candidate_available。"""
    rows = build_iad_source_heldout_gap_plan_rows(
        coverage_rows=[_coverage_row("agenda_non_identity")],
        candidate_rows=[],
    )

    assert rows[0]["gap_status"] == "no_candidate_available"
    assert rows[0]["candidate_id"] == ""
    assert "补充公开候选来源 registry" in rows[0]["next_action"]


def test_build_iad_source_heldout_gap_plan_rows_from_paths_reads_inputs(tmp_path) -> None:
    """验证从 coverage 和 registry 文件读取输入。"""
    coverage_path = tmp_path / "coverage.jsonl"
    registry_path = tmp_path / "registry.jsonl"
    _write_jsonl(coverage_path, [_coverage_row("agenda_non_identity")])
    _write_jsonl(registry_path, [_candidate_row()])

    rows = build_iad_source_heldout_gap_plan_rows_from_paths(coverage_path, registry_path)

    assert rows[0]["candidate_id"] == "agenda_non_identity_opencitations_coci_T10009"


def test_write_iad_source_heldout_gap_plan_outputs_writes_files(tmp_path) -> None:
    """验证 gap plan 写出 JSONL、CSV、Markdown 和 summary。"""
    rows = build_iad_source_heldout_gap_plan_rows([_coverage_row("agenda_non_identity")], [_candidate_row()])
    output_dir = tmp_path / "gap_plan"

    write_iad_source_heldout_gap_plan_outputs(rows, output_dir)

    assert read_records(output_dir / "iad_source_heldout_gap_plan.jsonl")
    assert read_records(output_dir / "iad_source_heldout_gap_plan_summary.jsonl")
    assert (output_dir / "iad_source_heldout_gap_plan.csv").exists()
    assert "# IAD Source-Heldout Gap Plan" in (output_dir / "iad_source_heldout_gap_plan.md").read_text(encoding="utf-8")


def test_build_iad_source_heldout_gap_plan_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 source-held-out 缺口补齐计划。"""
    coverage_path = tmp_path / "coverage.jsonl"
    registry_path = tmp_path / "registry.jsonl"
    output_dir = tmp_path / "gap_plan"
    _write_jsonl(coverage_path, [_coverage_row("agenda_non_identity")])
    _write_jsonl(registry_path, [_candidate_row()])

    command_build_iad_source_heldout_gap_plan(
        Namespace(
            coverage_audit=str(coverage_path),
            candidate_registry=str(registry_path),
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "iad_source_heldout_gap_plan.jsonl").exists()
    assert (output_dir / "iad_source_heldout_gap_plan_summary.jsonl").exists()


def test_cli_includes_build_iad_source_heldout_gap_plan_command() -> None:
    """验证 CLI 暴露 build-iad-source-heldout-gap-plan 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-iad-source-heldout-gap-plan",
            "--coverage-audit",
            "outputs/iad_source_heldout_coverage_audit_open_v3_balanced_gold/iad_source_heldout_coverage_audit.jsonl",
            "--candidate-registry",
            "outputs/iad_bench_source_candidate_registry_fixture/iad_bench_source_candidate_registry.jsonl",
            "--output-dir",
            "outputs/iad_source_heldout_gap_plan_open_v3_balanced_gold",
        ]
    )

    assert args.command == "build-iad-source-heldout-gap-plan"
