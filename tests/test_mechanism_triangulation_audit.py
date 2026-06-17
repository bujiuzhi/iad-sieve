"""测试机制三角验证审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_mechanism_triangulation_audit
from iad_sieve.evaluation.mechanism_triangulation_audit import (
    build_mechanism_triangulation_rows,
    build_mechanism_triangulation_rows_from_paths,
    build_mechanism_triangulation_summary,
    write_mechanism_triangulation_outputs,
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


def _pair(pair_id: str, score_field: str, score: float, hard_negative_level: str = "high") -> dict:
    """构造 baseline pair 记录。

    参数:
        pair_id: pair ID。
        score_field: 分数字段。
        score: baseline 分数。
        hard_negative_level: hard-negative 等级。

    返回:
        baseline pair 记录。
    """
    return {
        "pair_id": pair_id,
        "expected_label": 0,
        "expected_agenda_label": 1,
        "hard_negative_level": hard_negative_level,
        "source_document_id": f"source:{pair_id}",
        "target_document_id": f"target:{pair_id}",
        score_field: score,
    }


def _iad_rows(unresolved_pair_ids: set[str] | None = None) -> list[dict]:
    """构造 IAD-Risk 预测记录。

    参数:
        unresolved_pair_ids: 仍被 IAD 判为合并的 pair ID。

    返回:
        IAD 预测记录列表。
    """
    unresolved = unresolved_pair_ids or set()
    return [
        {
            "pair_id": pair_id,
            "merge_prediction": 1 if pair_id in unresolved else 0,
            "p_false_merge_risk": 0.95,
        }
        for pair_id in ["p_common", "p_scincl_only", "p_roberta_only", "p_low_score"]
    ]


def _baseline_specs(unresolved: bool = False) -> list[dict]:
    """构造 baseline specification。

    参数:
        unresolved: 是否让 RoBERTa 独有错误未被 IAD 阻断。

    返回:
        baseline specification 列表。
    """
    del unresolved
    return [
        {
            "system": "scincl_cosine_open_v2",
            "score_field": "scincl_score",
            "threshold": 0.9,
            "rows": [
                _pair("p_common", "scincl_score", 0.95),
                _pair("p_scincl_only", "scincl_score", 0.93),
                _pair("p_low_score", "scincl_score", 0.1),
            ],
        },
        {
            "system": "roberta_pair_open_v2",
            "score_field": "roberta_pair_score",
            "threshold": 0.8,
            "rows": [
                _pair("p_common", "roberta_pair_score", 0.84),
                _pair("p_roberta_only", "roberta_pair_score", 0.82),
                _pair("p_low_score", "roberta_pair_score", 0.1),
            ],
        },
    ]


def test_build_mechanism_triangulation_rows_marks_common_and_unique_failures() -> None:
    """验证三角审计识别跨模型共同失败和单模型族失败。"""
    audit_rows, system_rows = build_mechanism_triangulation_rows(
        baseline_specs=_baseline_specs(),
        iad_prediction_rows=_iad_rows(),
    )
    by_pair = {row["pair_id"]: row for row in audit_rows}
    by_system = {row["system"]: row for row in system_rows}
    summary = build_mechanism_triangulation_summary(audit_rows, system_rows)

    assert by_pair["p_common"]["triangulation_pattern"] == "cross_system_common_failure"
    assert by_pair["p_common"]["failing_system_count"] == 2
    assert by_pair["p_scincl_only"]["triangulation_pattern"] == "single_system_failure"
    assert by_system["scincl_cosine_open_v2"]["baseline_false_merge_count"] == 2
    assert by_system["roberta_pair_open_v2"]["common_failure_count"] == 1
    assert summary["cross_system_failure_pair_count"] == 1
    assert summary["triangulation_status"] == "cross_system_mechanism_evidence"
    assert summary["q2b_mechanism_depth_ready"] is True


def test_build_mechanism_triangulation_summary_limits_parallel_only_evidence() -> None:
    """验证无共同失败 pair 时只能形成平行机制证据。"""
    specs = _baseline_specs()
    specs[1]["rows"] = [_pair("p_roberta_only", "roberta_pair_score", 0.82)]

    audit_rows, system_rows = build_mechanism_triangulation_rows(specs, _iad_rows())
    summary = build_mechanism_triangulation_summary(audit_rows, system_rows)

    assert summary["cross_system_failure_pair_count"] == 0
    assert summary["triangulation_status"] == "parallel_family_mechanism_evidence"
    assert summary["q2b_mechanism_depth_ready"] is False


def test_build_mechanism_triangulation_summary_blocks_unresolved_iad_errors() -> None:
    """验证 IAD 未阻断错误时三角证据不能 ready。"""
    audit_rows, system_rows = build_mechanism_triangulation_rows(
        baseline_specs=_baseline_specs(),
        iad_prediction_rows=_iad_rows(unresolved_pair_ids={"p_roberta_only"}),
    )
    summary = build_mechanism_triangulation_summary(audit_rows, system_rows)

    assert summary["unresolved_pair_count"] == 1
    assert summary["triangulation_status"] == "partial_mechanism_evidence"
    assert summary["q2b_mechanism_depth_ready"] is False


def test_write_mechanism_triangulation_outputs_writes_files(tmp_path) -> None:
    """验证三角审计写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "mechanism_triangulation"
    audit_rows, system_rows = build_mechanism_triangulation_rows(_baseline_specs(), _iad_rows())

    write_mechanism_triangulation_outputs(audit_rows, system_rows, output_dir)

    assert read_records(output_dir / "mechanism_triangulation_audit.jsonl")
    assert read_records(output_dir / "mechanism_triangulation_systems.jsonl")
    assert (output_dir / "mechanism_triangulation_audit.csv").exists()
    assert (output_dir / "mechanism_triangulation_systems.csv").exists()
    assert "# Mechanism Triangulation Audit" in (output_dir / "mechanism_triangulation_audit.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "mechanism_triangulation_summary.jsonl")[0]
    assert summary["triangulation_status"] == "cross_system_mechanism_evidence"


def test_build_mechanism_triangulation_rows_from_paths_reads_baseline_specs(tmp_path) -> None:
    """验证从 baseline specs 文件读取三角审计输入。"""
    scincl_path = tmp_path / "scincl.jsonl"
    roberta_path = tmp_path / "roberta.jsonl"
    iad_path = tmp_path / "iad.jsonl"
    _write_jsonl(scincl_path, _baseline_specs()[0]["rows"])
    _write_jsonl(roberta_path, _baseline_specs()[1]["rows"])
    _write_jsonl(iad_path, _iad_rows())

    audit_rows, system_rows = build_mechanism_triangulation_rows_from_paths(
        iad_predictions_path=iad_path,
        baseline_spec_values=[
            f"system=scincl_cosine_open_v2,path={scincl_path},score_field=scincl_score,threshold=0.9",
            f"system=roberta_pair_open_v2,path={roberta_path},score_field=roberta_pair_score,threshold=0.8",
        ],
    )

    assert audit_rows
    assert len(system_rows) == 2


def test_build_mechanism_triangulation_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出机制三角验证审计。"""
    scincl_path = tmp_path / "scincl.jsonl"
    roberta_path = tmp_path / "roberta.jsonl"
    iad_path = tmp_path / "iad.jsonl"
    output_dir = tmp_path / "mechanism_triangulation"
    _write_jsonl(scincl_path, _baseline_specs()[0]["rows"])
    _write_jsonl(roberta_path, _baseline_specs()[1]["rows"])
    _write_jsonl(iad_path, _iad_rows())

    command_build_mechanism_triangulation_audit(
        Namespace(
            iad_predictions=str(iad_path),
            baseline_specs=[
                f"system=scincl_cosine_open_v2,path={scincl_path},score_field=scincl_score,threshold=0.9",
                f"system=roberta_pair_open_v2,path={roberta_path},score_field=roberta_pair_score,threshold=0.8",
            ],
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "mechanism_triangulation_audit.jsonl")
    assert (output_dir / "mechanism_triangulation_audit.md").exists()


def test_cli_includes_build_mechanism_triangulation_command() -> None:
    """验证 CLI 暴露 build-mechanism-triangulation-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-mechanism-triangulation-audit",
            "--iad-predictions",
            "outputs/iad_risk_transformer_open_v2/iad_risk_transformer_predictions.jsonl",
            "--baseline-specs",
            "system=scincl_cosine_open_v2,path=outputs/strong_baseline_open_v2/scincl_scored_relations.jsonl,score_field=scincl_score,threshold=0.9",
            "--output-dir",
            "outputs/mechanism_triangulation_audit_fixture",
        ]
    )

    assert args.command == "build-mechanism-triangulation-audit"
    assert args.baseline_specs[0].startswith("system=scincl_cosine_open_v2")
