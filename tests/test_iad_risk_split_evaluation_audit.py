"""测试 IAD-Risk split 评估审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_iad_risk_split_evaluation_audit
from iad_sieve.evaluation.iad_risk_split_evaluation_audit import (
    build_iad_risk_split_evaluation_audit_rows,
    build_iad_risk_split_evaluation_audit_rows_from_paths,
    build_iad_risk_split_evaluation_summary,
    write_iad_risk_split_evaluation_audit_outputs,
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


def _write_json(path, record: dict) -> None:
    """写入 JSON 测试文件。

    参数:
        path: 输出路径。
        record: JSON 对象。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _summary_row(trained: bool = False, eval_split: str = "test", eval_pair_count: int = 100) -> dict:
    """构造 IAD-Risk summary 测试记录。

    参数:
        trained: 完整模型是否训练完成。
        eval_split: 评估 split。
        eval_pair_count: 评估样本数。

    返回:
        summary 记录。
    """
    return {
        "system": "iad_risk_dual_space",
        "train_split": "train",
        "train_pair_count": 400,
        "eval_split": eval_split,
        "evaluation_split_strategy": "source_held_out",
        "eval_pair_count": eval_pair_count,
        "trained": trained,
        "trained_head_count": 2 if not trained else 3,
        "required_head_count": 2,
        "same_work_f1": 0.72,
        "same_agenda_f1": 0.68,
        "agenda_non_identity_f1": 0.0 if not trained else 0.61,
        "f1": 0.0 if not trained else 0.59,
        "false_merge_rate": 0.0 if not trained else 0.08,
    }


def _model(trained: bool = False) -> dict:
    """构造 IAD-Risk 模型测试记录。

    参数:
        trained: 完整模型是否训练完成。

    返回:
        模型 JSON 对象。
    """
    return {
        "trained": trained,
        "required_head_count": 2,
        "heads": {
            "same_work": {"trained": True, "training_metrics": {"positive_label_count": 20, "negative_label_count": 20}},
            "same_agenda": {"trained": True, "training_metrics": {"positive_label_count": 20, "negative_label_count": 20}},
            "agenda_non_identity": {
                "trained": trained,
                "skip_reason": "" if trained else "single_class_or_missing_label",
                "training_metrics": {
                    "positive_label_count": 12 if trained else 0,
                    "negative_label_count": 28,
                },
            },
        },
    }


def test_build_iad_risk_split_evaluation_audit_blocks_missing_required_head() -> None:
    """验证必要 head 未训练时阻断完整 source-held-out 声明。"""
    rows = build_iad_risk_split_evaluation_audit_rows(summary_rows=[_summary_row(trained=False)], model=_model(trained=False))
    summary = build_iad_risk_split_evaluation_summary(rows)

    assert rows[0]["audit_status"] == "blocked_full_iad_risk_generalization"
    assert "agenda_non_identity_head_not_trained" in rows[0]["required_head_blockers"]
    assert rows[0]["paper_claim_boundary"] == "same_work_or_negative_pilot_only"
    assert summary["source_heldout_full_iad_ready"] is False


def test_build_iad_risk_split_evaluation_audit_allows_limited_ready_test_split() -> None:
    """验证必要 head 和 test split 均可用时允许有限 source-held-out 证据。"""
    rows = build_iad_risk_split_evaluation_audit_rows(summary_rows=[_summary_row(trained=True)], model=_model(trained=True))
    summary = build_iad_risk_split_evaluation_summary(rows)

    assert rows[0]["audit_status"] == "limited_source_heldout_evidence"
    assert rows[0]["reviewer_risk_level"] == "medium"
    assert summary["source_heldout_full_iad_ready"] is True


def test_build_iad_risk_split_evaluation_audit_blocks_missing_test_label_coverage() -> None:
    """验证 source-held-out test 缺少必要标签覆盖时阻断完整 IAD 泛化。"""
    summary_row = _summary_row(trained=True)
    summary_row["same_work_positive_count"] = 50
    summary_row["same_work_negative_count"] = 50
    summary_row["agenda_non_identity_positive_count"] = 0
    summary_row["agenda_non_identity_negative_count"] = 100

    rows = build_iad_risk_split_evaluation_audit_rows(summary_rows=[summary_row], model=_model(trained=True))
    summary = build_iad_risk_split_evaluation_summary(rows)

    assert rows[0]["audit_status"] == "blocked_eval_label_coverage"
    assert "agenda_non_identity_missing_positive_eval_label" in rows[0]["eval_label_blockers"]
    assert rows[0]["paper_claim_boundary"] == "source_heldout_identity_only"
    assert summary["source_heldout_full_iad_ready"] is False


def test_build_iad_risk_split_evaluation_audit_marks_stratified_blend_as_diagnostic_only() -> None:
    """验证 gold/silver 分层混合测试不能冒充 source-held-out 泛化证据。"""
    summary_row = _summary_row(trained=True)
    summary_row["evaluation_split_strategy"] = "stratified_gold_silver_blend"

    rows = build_iad_risk_split_evaluation_audit_rows(summary_rows=[summary_row], model=_model(trained=True))
    summary = build_iad_risk_split_evaluation_summary(rows)

    assert rows[0]["audit_status"] == "limited_stratified_blend_evidence"
    assert rows[0]["paper_claim_boundary"] == "gold_silver_stratified_diagnostic_only"
    assert summary["limited_stratified_blend_count"] == 1
    assert summary["source_heldout_full_iad_ready"] is False
    assert summary["overall_split_evaluation_status"] == "stratified_blend_diagnostic_only"


def test_build_iad_risk_split_evaluation_audit_rows_from_paths(tmp_path) -> None:
    """验证从 summary 与 model 文件读取 split 审计输入。"""
    summary_path = tmp_path / "iad_risk_summary.jsonl"
    model_path = tmp_path / "iad_risk_model.json"
    _write_jsonl(summary_path, [_summary_row(trained=False)])
    _write_json(model_path, _model(trained=False))

    rows = build_iad_risk_split_evaluation_audit_rows_from_paths(summary_path, model_path)

    assert rows[0]["eval_split"] == "test"
    assert rows[0]["audit_status"] == "blocked_full_iad_risk_generalization"


def test_write_iad_risk_split_evaluation_audit_outputs(tmp_path) -> None:
    """验证 split 审计写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "iad_risk_split_evaluation_audit"
    rows = build_iad_risk_split_evaluation_audit_rows(summary_rows=[_summary_row(trained=False)], model=_model(trained=False))

    write_iad_risk_split_evaluation_audit_outputs(rows, output_dir)

    assert read_records(output_dir / "iad_risk_split_evaluation_audit.jsonl")
    assert read_records(output_dir / "iad_risk_split_evaluation_audit_summary.jsonl")
    assert (output_dir / "iad_risk_split_evaluation_audit.csv").exists()
    assert "# IAD-Risk Split Evaluation Audit" in (output_dir / "iad_risk_split_evaluation_audit.md").read_text(encoding="utf-8")


def test_build_iad_risk_split_evaluation_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 IAD-Risk split 审计。"""
    summary_path = tmp_path / "iad_risk_summary.jsonl"
    model_path = tmp_path / "iad_risk_model.json"
    output_dir = tmp_path / "iad_risk_split_evaluation_audit"
    _write_jsonl(summary_path, [_summary_row(trained=False)])
    _write_json(model_path, _model(trained=False))

    command_build_iad_risk_split_evaluation_audit(
        Namespace(iad_risk_summary=str(summary_path), iad_risk_model=str(model_path), output_dir=str(output_dir))
    )

    assert read_records(output_dir / "iad_risk_split_evaluation_audit.jsonl")
    assert (output_dir / "iad_risk_split_evaluation_audit.md").exists()


def test_cli_includes_build_iad_risk_split_evaluation_audit_command() -> None:
    """验证 CLI 暴露 build-iad-risk-split-evaluation-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-iad-risk-split-evaluation-audit",
            "--iad-risk-summary",
            "outputs/iad_risk_source_heldout_lightweight/iad_risk_summary.jsonl",
            "--iad-risk-model",
            "outputs/iad_risk_source_heldout_lightweight/iad_risk_model.json",
            "--output-dir",
            "outputs/iad_risk_split_evaluation_audit_source_heldout",
        ]
    )

    assert args.command == "build-iad-risk-split-evaluation-audit"
    assert args.iad_risk_model.endswith("iad_risk_model.json")
