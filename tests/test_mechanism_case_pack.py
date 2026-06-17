"""测试机制案例包生成。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_mechanism_case_pack
from iad_sieve.evaluation.mechanism_case_pack import (
    build_mechanism_case_pack_rows,
    build_mechanism_case_pack_rows_from_paths,
    build_mechanism_case_pack_summary,
    write_mechanism_case_pack_outputs,
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


def _triangulation_rows() -> list[dict]:
    """构造三角验证测试记录。

    参数:
        无。

    返回:
        三角验证记录列表。
    """
    return [
        {
            "pair_id": "p_common",
            "triangulation_pattern": "cross_system_common_failure",
            "failing_systems": ["scincl_cosine_open_v2", "roberta_pair_open_v2"],
            "hard_negative_level": "medium",
            "iad_prevented": True,
            "iad_merge_prediction": 0,
            "source_document_id": "doc_a",
            "target_document_id": "doc_b",
        },
        {
            "pair_id": "p_scincl_only",
            "triangulation_pattern": "single_system_failure",
            "failing_systems": ["scincl_cosine_open_v2"],
            "hard_negative_level": "high",
            "iad_prevented": True,
            "iad_merge_prediction": 0,
            "source_document_id": "doc_a",
            "target_document_id": "doc_c",
        },
        {
            "pair_id": "p_roberta_only",
            "triangulation_pattern": "single_system_failure",
            "failing_systems": ["roberta_pair_open_v2"],
            "hard_negative_level": "high",
            "iad_prevented": True,
            "iad_merge_prediction": 0,
            "source_document_id": "doc_b",
            "target_document_id": "doc_c",
        },
    ]


def _documents() -> list[dict]:
    """构造文档测试记录。

    参数:
        无。

    返回:
        文档记录列表。
    """
    return [
        {"document_id": "doc_a", "title": "Identity preserving paper", "year": 2024, "source_dataset": "openalex", "topics": ["retrieval"]},
        {"document_id": "doc_b", "title": "Agenda similar but distinct work", "year": 2025, "source_dataset": "openalex", "topics": ["retrieval"]},
        {"document_id": "doc_c", "title": "Different contribution paper", "year": 2023, "source_dataset": "openalex", "topics": ["ranking"]},
    ]


def _iad_predictions() -> list[dict]:
    """构造 IAD-Risk 预测记录。

    参数:
        无。

    返回:
        预测记录列表。
    """
    return [
        {
            "pair_id": "p_common",
            "merge_prediction": 0,
            "p_same_work": 0.1,
            "p_same_agenda": 0.88,
            "p_agenda_non_identity": 0.91,
            "p_false_merge_risk": 0.94,
        },
        {"pair_id": "p_scincl_only", "merge_prediction": 0, "p_false_merge_risk": 0.9},
        {"pair_id": "p_roberta_only", "merge_prediction": 0, "p_false_merge_risk": 0.85},
    ]


def _baseline_specs() -> list[dict]:
    """构造 baseline specification。

    参数:
        无。

    返回:
        baseline specification 列表。
    """
    return [
        {
            "system": "scincl_cosine_open_v2",
            "score_field": "scincl_score",
            "threshold": 0.9,
            "rows": [
                {"pair_id": "p_common", "scincl_score": 0.97},
                {"pair_id": "p_scincl_only", "scincl_score": 0.95},
            ],
        },
        {
            "system": "roberta_pair_open_v2",
            "score_field": "roberta_pair_score",
            "threshold": 0.8,
            "rows": [
                {"pair_id": "p_common", "roberta_pair_score": 0.83},
                {"pair_id": "p_roberta_only", "roberta_pair_score": 0.86},
            ],
        },
    ]


def test_build_mechanism_case_pack_rows_enriches_cases() -> None:
    """验证案例包补全文献、baseline 分数和 IAD 风险字段。"""
    rows = build_mechanism_case_pack_rows(
        triangulation_rows=_triangulation_rows(),
        document_rows=_documents(),
        iad_prediction_rows=_iad_predictions(),
        baseline_specs=_baseline_specs(),
        max_cases_per_group=1,
    )
    by_pair = {row["pair_id"]: row for row in rows}
    summary = build_mechanism_case_pack_summary(rows)

    assert len(rows) == 3
    assert by_pair["p_common"]["case_role"] == "shared_cross_system_failure"
    assert by_pair["p_common"]["source_title"] == "Identity preserving paper"
    assert "scincl_cosine_open_v2=0.970000@0.900000" in by_pair["p_common"]["baseline_score_summary"]
    assert "roberta_pair_open_v2=0.830000@0.800000" in by_pair["p_common"]["baseline_score_summary"]
    assert by_pair["p_common"]["iad_decision"] == "blocked_merge"
    assert by_pair["p_common"]["p_false_merge_risk"] == 0.94
    assert summary["cross_system_case_count"] == 1
    assert summary["single_system_case_count"] == 2
    assert summary["case_pack_status"] == "paper_ready_limited_case_pack"


def test_build_mechanism_case_pack_rows_from_paths_reads_inputs(tmp_path) -> None:
    """验证从文件读取案例包输入。"""
    triangulation_path = tmp_path / "triangulation.jsonl"
    documents_path = tmp_path / "documents.jsonl"
    iad_path = tmp_path / "iad.jsonl"
    scincl_path = tmp_path / "scincl.jsonl"
    roberta_path = tmp_path / "roberta.jsonl"
    _write_jsonl(triangulation_path, _triangulation_rows())
    _write_jsonl(documents_path, _documents())
    _write_jsonl(iad_path, _iad_predictions())
    _write_jsonl(scincl_path, _baseline_specs()[0]["rows"])
    _write_jsonl(roberta_path, _baseline_specs()[1]["rows"])

    rows = build_mechanism_case_pack_rows_from_paths(
        triangulation_path=triangulation_path,
        documents_path=documents_path,
        iad_predictions_path=iad_path,
        baseline_spec_values=[
            f"system=scincl_cosine_open_v2,path={scincl_path},score_field=scincl_score,threshold=0.9",
            f"system=roberta_pair_open_v2,path={roberta_path},score_field=roberta_pair_score,threshold=0.8",
        ],
        max_cases_per_group=1,
    )

    assert {row["pair_id"] for row in rows} == {"p_common", "p_scincl_only", "p_roberta_only"}


def test_write_mechanism_case_pack_outputs_writes_files(tmp_path) -> None:
    """验证案例包写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "mechanism_case_pack"
    rows = build_mechanism_case_pack_rows(_triangulation_rows(), _documents(), _iad_predictions(), _baseline_specs())

    write_mechanism_case_pack_outputs(rows, output_dir)

    assert read_records(output_dir / "mechanism_case_pack.jsonl")
    assert (output_dir / "mechanism_case_pack.csv").exists()
    assert "# Mechanism Case Pack" in (output_dir / "mechanism_case_pack.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "mechanism_case_pack_summary.jsonl")[0]
    assert summary["case_pack_status"] == "paper_ready_limited_case_pack"


def test_build_mechanism_case_pack_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出机制案例包。"""
    triangulation_path = tmp_path / "triangulation.jsonl"
    documents_path = tmp_path / "documents.jsonl"
    iad_path = tmp_path / "iad.jsonl"
    scincl_path = tmp_path / "scincl.jsonl"
    roberta_path = tmp_path / "roberta.jsonl"
    output_dir = tmp_path / "mechanism_case_pack"
    _write_jsonl(triangulation_path, _triangulation_rows())
    _write_jsonl(documents_path, _documents())
    _write_jsonl(iad_path, _iad_predictions())
    _write_jsonl(scincl_path, _baseline_specs()[0]["rows"])
    _write_jsonl(roberta_path, _baseline_specs()[1]["rows"])

    command_build_mechanism_case_pack(
        Namespace(
            triangulation=str(triangulation_path),
            documents=str(documents_path),
            iad_predictions=str(iad_path),
            baseline_specs=[
                f"system=scincl_cosine_open_v2,path={scincl_path},score_field=scincl_score,threshold=0.9",
                f"system=roberta_pair_open_v2,path={roberta_path},score_field=roberta_pair_score,threshold=0.8",
            ],
            max_cases_per_group=1,
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "mechanism_case_pack.jsonl")
    assert (output_dir / "mechanism_case_pack.md").exists()


def test_cli_includes_build_mechanism_case_pack_command() -> None:
    """验证 CLI 暴露 build-mechanism-case-pack 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-mechanism-case-pack",
            "--triangulation",
            "outputs/mechanism_triangulation_audit_fixture/mechanism_triangulation_audit.jsonl",
            "--documents",
            "outputs/iad_bench_open_v2/iad_bench_documents.jsonl",
            "--iad-predictions",
            "outputs/iad_risk_transformer_open_v2/iad_risk_transformer_predictions.jsonl",
            "--baseline-specs",
            "system=scincl_cosine_open_v2,path=outputs/strong_baseline_open_v2/scincl_scored_relations.jsonl,score_field=scincl_score,threshold=0.9",
            "--max-cases-per-group",
            "2",
            "--output-dir",
            "outputs/mechanism_case_pack_fixture",
        ]
    )

    assert args.command == "build-mechanism-case-pack"
    assert args.max_cases_per_group == 2
