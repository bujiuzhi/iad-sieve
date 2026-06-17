"""测试 IAD 模型特征泄漏审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_iad_model_feature_guard
from iad_sieve.evaluation.iad_model_feature_guard import (
    build_iad_model_feature_guard_rows,
    build_iad_model_feature_guard_rows_from_paths,
    write_iad_model_feature_guard_outputs,
)
from iad_sieve.utils.io_utils import read_records


def _write_json(path, record: dict) -> None:
    """写入 JSON 测试文件。

    参数:
        path: 输出路径。
        record: JSON 记录。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_build_iad_model_feature_guard_rows_flags_provenance_features() -> None:
    """验证模型特征包含来源或标签字段时标记 high_risk。"""
    model = {
        "model_type": "fixture_model",
        "feature_groups": {"risk_space": ["title_similarity", "same_source_dataset"]},
        "heads": {
            "same_work": {"feature_fields": ["title_similarity"]},
            "agenda_non_identity": {"feature_fields": ["label_source", "transformer_cosine"]},
        },
    }

    audit_rows, violation_rows = build_iad_model_feature_guard_rows(models=[model], model_paths=["model.json"])

    assert audit_rows[0]["audit_status"] == "high_risk"
    assert audit_rows[0]["violation_count"] == 2
    assert {row["feature_field"] for row in violation_rows} == {"same_source_dataset", "label_source"}


def test_build_iad_model_feature_guard_rows_accepts_provenance_blind_model() -> None:
    """验证无泄漏字段的模型标记 defensible。"""
    model = {
        "model_type": "fixture_model",
        "feature_groups": {"risk_space": ["title_similarity", "transformer_cosine"]},
        "heads": {"same_work": {"feature_fields": ["title_similarity", "transformer_cosine"]}},
    }

    audit_rows, violation_rows = build_iad_model_feature_guard_rows(models=[model], model_paths=["model.json"])

    assert audit_rows[0]["audit_status"] == "defensible"
    assert audit_rows[0]["violation_count"] == 0
    assert violation_rows == []


def test_build_iad_model_feature_guard_rows_from_paths_reads_models(tmp_path) -> None:
    """验证模型特征泄漏审计可从 JSON 模型文件读取输入。"""
    model_path = tmp_path / "iad_risk_model.json"
    _write_json(model_path, {"feature_groups": {"risk_space": ["label_strength"]}})

    audit_rows, violation_rows = build_iad_model_feature_guard_rows_from_paths(model_paths=[model_path])

    assert audit_rows[0]["audit_status"] == "high_risk"
    assert violation_rows[0]["feature_field"] == "label_strength"


def test_build_iad_model_feature_guard_rows_from_paths_records_missing_models(tmp_path) -> None:
    """验证缺失模型文件会被记录为证据缺口而不是中断审计。"""
    model_path = tmp_path / "iad_risk_model.json"
    missing_model_path = tmp_path / "missing_transformer_model.json"
    _write_json(model_path, {"feature_groups": {"risk_space": ["title_similarity"]}})

    audit_rows, violation_rows = build_iad_model_feature_guard_rows_from_paths(model_paths=[model_path, missing_model_path])

    by_path = {row["model_path"]: row for row in audit_rows}
    assert by_path[str(model_path)]["audit_status"] == "defensible"
    assert by_path[str(missing_model_path)]["audit_status"] == "missing_model_file"
    assert by_path[str(missing_model_path)]["reviewer_risk_level"] == "high"
    assert violation_rows == []


def test_write_iad_model_feature_guard_outputs_writes_files(tmp_path) -> None:
    """验证模型特征泄漏审计写出 JSONL、CSV、Markdown 和 summary。"""
    audit_rows = [{"model_path": "model.json", "audit_status": "high_risk", "violation_count": 1}]
    violation_rows = [{"model_path": "model.json", "feature_field": "label_source", "feature_path": "heads.same_work.feature_fields"}]
    output_dir = tmp_path / "feature_guard"

    write_iad_model_feature_guard_outputs(audit_rows, violation_rows, output_dir)

    assert read_records(output_dir / "iad_model_feature_guard.jsonl")[0]["audit_status"] == "high_risk"
    assert read_records(output_dir / "iad_model_feature_guard_violations.jsonl")[0]["feature_field"] == "label_source"
    assert (output_dir / "iad_model_feature_guard.csv").exists()
    assert (output_dir / "iad_model_feature_guard_violations.csv").exists()
    assert "# IAD Model Feature Guard" in (output_dir / "iad_model_feature_guard.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "iad_model_feature_guard_summary.jsonl")[0]
    assert summary["high_risk_count"] == 1
    assert summary["violation_count"] == 1


def test_build_iad_model_feature_guard_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出模型特征泄漏审计。"""
    model_path = tmp_path / "model.json"
    output_dir = tmp_path / "feature_guard"
    _write_json(model_path, {"feature_groups": {"risk_space": ["label_source"]}})

    command_build_iad_model_feature_guard(
        Namespace(
            model_paths=[str(model_path)],
            output_dir=str(output_dir),
            denied_fields="label_source,label_strength",
        )
    )

    assert (output_dir / "iad_model_feature_guard.jsonl").exists()
    assert (output_dir / "iad_model_feature_guard_summary.jsonl").exists()


def test_cli_includes_build_iad_model_feature_guard_command() -> None:
    """验证 CLI 暴露 build-iad-model-feature-guard 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-iad-model-feature-guard",
            "--model-paths",
            "outputs/iad_risk_open_v2/iad_risk_model.json",
            "outputs/iad_risk_transformer_open_v2/iad_risk_transformer_model.json",
            "--output-dir",
            "outputs/iad_model_feature_guard_fixture",
        ]
    )

    assert args.command == "build-iad-model-feature-guard"
    assert args.model_paths == [
        "outputs/iad_risk_open_v2/iad_risk_model.json",
        "outputs/iad_risk_transformer_open_v2/iad_risk_transformer_model.json",
    ]
    assert args.denied_fields == ""
