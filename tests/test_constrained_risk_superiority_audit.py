"""测试 constrained-risk 模型优势审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_model_superiority_audit
from iad_sieve.evaluation.model_superiority_audit import (
    build_constrained_risk_superiority_rows,
    build_model_superiority_audit_rows_from_paths,
    write_model_superiority_audit_outputs,
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


def test_constrained_risk_superiority_supports_safe_merge_recall_under_same_budget() -> None:
    """验证同一 FPR/FDR 预算下 safe_merge recall 优势可被单独审计。"""
    rows = build_constrained_risk_superiority_rows(
        risk_protocol_rows=[
            {
                "system": "risk_method",
                "evaluation_track": "open_v3_multitopic_silver_patch",
                "is_selected": 1,
                "fpr_budget": 0.03,
                "fdr_budget": 0.10,
                "safe_merge_recall": 0.42,
                "safe_merge_coverage": 0.20,
                "negative_false_merge_rate": 0.02,
                "merge_contamination_fdr": 0.08,
                "hard_negative_false_merge_rate": 0.01,
                "review_rate": 0.30,
            },
            {
                "system": "scincl_baseline",
                "evaluation_track": "open_v3_multitopic_silver_patch",
                "is_selected": 1,
                "fpr_budget": 0.03,
                "fdr_budget": 0.10,
                "safe_merge_recall": 0.25,
                "safe_merge_coverage": 0.12,
                "negative_false_merge_rate": 0.03,
                "merge_contamination_fdr": 0.10,
                "hard_negative_false_merge_rate": 0.18,
                "review_rate": 0.25,
            },
        ],
        main_system="risk_method",
        required_baselines=["scincl_baseline"],
    )

    row = rows[0]

    assert row["comparison_metric"] == "safe_merge_recall_at_fpr_fdr_budget"
    assert row["status"] == "supports_constrained_risk_advantage"
    assert row["claim_status"] == "supported"
    assert row["safe_merge_recall_delta"] == 0.17
    assert row["hard_negative_false_merge_rate_reduction"] == 0.17
    assert row["fpr_budget"] == 0.03
    assert row["fdr_budget"] == 0.10


def test_constrained_risk_superiority_uses_budget_feasibility_not_lower_risk_than_baseline() -> None:
    """验证预算内 recall 优势不要求风险数值低于 baseline。"""
    rows = build_constrained_risk_superiority_rows(
        risk_protocol_rows=[
            {
                "system": "risk_method",
                "evaluation_track": "open_v3_scholarly_balanced_gold_source_heldout",
                "is_selected": 1,
                "fpr_budget": 0.03,
                "fdr_budget": 0.03,
                "safe_merge_recall": 0.98,
                "safe_merge_coverage": 0.50,
                "negative_false_merge_rate": 0.027,
                "merge_contamination_fdr": 0.026,
                "hard_negative_false_merge_rate": 0.0,
                "review_rate": 0.0,
            },
            {
                "system": "roberta_baseline",
                "evaluation_track": "open_v3_scholarly_balanced_gold_source_heldout",
                "is_selected": 1,
                "fpr_budget": 0.03,
                "fdr_budget": 0.03,
                "safe_merge_recall": 0.64,
                "safe_merge_coverage": 0.33,
                "negative_false_merge_rate": 0.016,
                "merge_contamination_fdr": 0.025,
                "hard_negative_false_merge_rate": 0.0,
                "review_rate": 0.0,
            },
        ],
        main_system="risk_method",
        required_baselines=["roberta_baseline"],
    )

    row = rows[0]

    assert row["status"] == "supports_constrained_risk_advantage"
    assert row["claim_status"] == "supported"
    assert row["safe_merge_recall_delta"] == 0.34
    assert row["negative_false_merge_rate_reduction"] == -0.011
    assert row["merge_contamination_fdr_reduction"] == -0.001


def test_constrained_risk_superiority_infers_track_from_system_when_missing() -> None:
    """验证 risk protocol 未写 track 时从 system 名称推断评估轨道。"""
    rows = build_constrained_risk_superiority_rows(
        risk_protocol_rows=[
            {
                "system": "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout",
                "is_selected": 1,
                "fpr_budget": 0.03,
                "fdr_budget": 0.03,
                "safe_merge_recall": 0.98,
                "safe_merge_coverage": 0.50,
                "negative_false_merge_rate": 0.027,
                "merge_contamination_fdr": 0.026,
                "hard_negative_false_merge_rate": 0.0,
            },
            {
                "system": "roberta_pair_open_v3_scholarly_balanced_gold_source_heldout",
                "is_selected": 1,
                "fpr_budget": 0.03,
                "fdr_budget": 0.03,
                "safe_merge_recall": 0.64,
                "safe_merge_coverage": 0.33,
                "negative_false_merge_rate": 0.016,
                "merge_contamination_fdr": 0.025,
                "hard_negative_false_merge_rate": 0.0,
            },
        ],
        main_system="iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout",
        required_baselines=["roberta_pair_open_v3_scholarly_balanced_gold_source_heldout"],
    )

    assert rows[0]["evaluation_track"] == "open_v3_scholarly_balanced_gold_source_heldout"


def test_constrained_risk_superiority_blocks_when_protocol_rows_are_missing() -> None:
    """验证缺少 constrained-risk 协议时禁止使用 best-F1 替代主比较。"""
    rows = build_constrained_risk_superiority_rows(
        risk_protocol_rows=[],
        main_system="risk_method",
        required_baselines=["scincl_baseline"],
        evaluation_track="open_v3_multitopic_silver_patch",
    )

    assert rows[0]["comparison_metric"] == "safe_merge_recall_at_fpr_fdr_budget"
    assert rows[0]["status"] == "blocked_missing_constrained_risk_protocol"
    assert rows[0]["claim_status"] != "supported"
    assert "不得用 best F1 替代" in rows[0]["paper_claim_boundary"]


def test_constrained_risk_superiority_supports_when_baseline_has_no_feasible_selected_row() -> None:
    """验证 baseline 协议已运行但无可行阈值时记录为风险预算可行性优势。"""
    rows = build_constrained_risk_superiority_rows(
        risk_protocol_rows=[
            {
                "system": "risk_method",
                "evaluation_track": "open_v3_multitopic_silver_patch",
                "is_selected": 1,
                "fpr_budget": 0.03,
                "fdr_budget": 0.10,
                "safe_merge_recall": 0.42,
                "safe_merge_coverage": 0.20,
                "negative_false_merge_rate": 0.02,
                "merge_contamination_fdr": 0.08,
            },
            {
                "system": "scincl_baseline",
                "evaluation_track": "open_v3_multitopic_silver_patch",
                "is_selected": 0,
                "fpr_budget": 0.03,
                "fdr_budget": 0.10,
                "safe_merge_recall": 0.50,
                "safe_merge_coverage": 0.30,
                "negative_false_merge_rate": 0.08,
                "merge_contamination_fdr": 0.30,
            },
        ],
        main_system="risk_method",
        required_baselines=["scincl_baseline"],
    )

    assert rows[0]["status"] == "supports_constrained_risk_advantage"
    assert rows[0]["claim_status"] == "supported"
    assert rows[0]["safe_merge_recall_delta"] == 0.42
    assert rows[0]["fpr_budget"] == 0.03
    assert rows[0]["fdr_budget"] == 0.10
    assert "无可行 selected 阈值" in rows[0]["support_summary"]


def test_model_superiority_from_paths_appends_constrained_risk_rows(tmp_path) -> None:
    """验证模型优势审计可从 risk protocol 文件追加 constrained-risk 行。"""
    advanced = tmp_path / "advanced.jsonl"
    risk_protocol = tmp_path / "risk_protocol.jsonl"
    _write_jsonl(
        advanced,
        [
            {
                "system": "risk_method",
                "evidence_type": "main_method_transformer",
                "evidence_status": "ready_actual_model",
                "evaluation_track": "open_v3_multitopic_silver_patch",
                "same_work_f1": 0.70,
                "false_merge_rate": 0.02,
                "hard_negative_false_merge_rate_mean": 0.01,
            },
            {
                "system": "scincl_baseline",
                "evidence_type": "representation",
                "evidence_status": "ready_actual_model",
                "evaluation_track": "open_v3_multitopic_silver_patch",
                "same_work_f1": 0.80,
                "false_merge_rate": 0.30,
                "hard_negative_false_merge_rate_mean": 0.18,
            },
        ],
    )
    _write_jsonl(
        risk_protocol,
        [
            {
                "system": "risk_method",
                "evaluation_track": "open_v3_multitopic_silver_patch",
                "is_selected": 1,
                "fpr_budget": 0.03,
                "fdr_budget": 0.10,
                "safe_merge_recall": 0.42,
                "safe_merge_coverage": 0.20,
                "negative_false_merge_rate": 0.02,
                "merge_contamination_fdr": 0.08,
                "hard_negative_false_merge_rate": 0.01,
                "review_rate": 0.30,
            },
            {
                "system": "scincl_baseline",
                "evaluation_track": "open_v3_multitopic_silver_patch",
                "is_selected": 1,
                "fpr_budget": 0.03,
                "fdr_budget": 0.10,
                "safe_merge_recall": 0.25,
                "safe_merge_coverage": 0.12,
                "negative_false_merge_rate": 0.03,
                "merge_contamination_fdr": 0.10,
                "hard_negative_false_merge_rate": 0.18,
                "review_rate": 0.25,
            },
        ],
    )

    rows = build_model_superiority_audit_rows_from_paths(
        advanced_model_evidence_paths=[advanced],
        model_innovation_blueprint_paths=[],
        risk_protocol_paths=[risk_protocol],
        main_system="risk_method",
    )

    assert any(row.get("comparison_metric") == "safe_merge_recall_at_fpr_fdr_budget" for row in rows)


def test_model_superiority_from_paths_ignores_transformer_variant_in_constrained_baselines(tmp_path) -> None:
    """验证同族 Transformer 变体不被当作必须优于的 constrained-risk baseline。"""
    advanced = tmp_path / "advanced.jsonl"
    risk_protocol = tmp_path / "risk_protocol.jsonl"
    _write_jsonl(
        advanced,
        [
            {
                "system": "iad_risk_transformer_scincl_track",
                "evidence_type": "main_method_transformer",
                "evidence_status": "ready_actual_model",
                "evaluation_track": "track",
            },
            {
                "system": "iad_risk_transformer_specter2_track",
                "evidence_type": "main_method_transformer",
                "evidence_status": "ready_actual_model",
                "evaluation_track": "track",
            },
            {
                "system": "roberta_pair_track",
                "evidence_type": "pair_classifier",
                "evidence_status": "ready_actual_model",
                "evaluation_track": "track",
            },
        ],
    )
    _write_jsonl(
        risk_protocol,
        [
            {"system": "iad_risk_transformer_scincl_track", "is_selected": 1, "fpr_budget": 0.03, "fdr_budget": 0.10, "safe_merge_recall": 0.42},
            {"system": "iad_risk_transformer_specter2_track", "is_selected": 1, "fpr_budget": 0.03, "fdr_budget": 0.10, "safe_merge_recall": 0.42},
            {"system": "roberta_pair_track", "is_selected": 1, "fpr_budget": 0.03, "fdr_budget": 0.10, "safe_merge_recall": 0.20},
        ],
    )

    rows = build_model_superiority_audit_rows_from_paths(
        advanced_model_evidence_paths=[advanced],
        model_innovation_blueprint_paths=[],
        risk_protocol_paths=[risk_protocol],
        main_system="iad_risk_transformer_scincl_track",
    )

    constrained_rows = [row for row in rows if row.get("comparison_family") == "constrained_risk"]

    assert [row["baseline_system"] for row in constrained_rows] == ["roberta_pair_track"]
    assert constrained_rows[0]["status"] == "supports_constrained_risk_advantage"


def test_model_superiority_from_paths_ignores_unclassified_iad_risk_variant_in_constrained_baselines(tmp_path) -> None:
    """验证缺少 advanced evidence 的 IAD-Risk 变体不进入 constrained-risk baseline。"""
    advanced = tmp_path / "advanced.jsonl"
    risk_protocol = tmp_path / "risk_protocol.jsonl"
    _write_jsonl(
        advanced,
        [
            {
                "system": "iad_risk_transformer_scincl_track",
                "evidence_type": "main_method_transformer",
                "evidence_status": "ready_actual_model",
                "evaluation_track": "track",
            },
            {
                "system": "roberta_pair_track",
                "evidence_type": "pair_classifier",
                "evidence_status": "ready_actual_model",
                "evaluation_track": "track",
            },
        ],
    )
    _write_jsonl(
        risk_protocol,
        [
            {"system": "iad_risk_transformer_scincl_track", "is_selected": 1, "fpr_budget": 0.03, "fdr_budget": 0.10, "safe_merge_recall": 0.42},
            {"system": "iad_risk_transformer_specter2_track", "is_selected": 1, "fpr_budget": 0.03, "fdr_budget": 0.10, "safe_merge_recall": 0.42},
            {"system": "roberta_pair_track", "is_selected": 1, "fpr_budget": 0.03, "fdr_budget": 0.10, "safe_merge_recall": 0.20},
        ],
    )

    rows = build_model_superiority_audit_rows_from_paths(
        advanced_model_evidence_paths=[advanced],
        model_innovation_blueprint_paths=[],
        risk_protocol_paths=[risk_protocol],
        main_system="iad_risk_transformer_scincl_track",
    )

    constrained_rows = [row for row in rows if row.get("comparison_family") == "constrained_risk"]

    assert [row["baseline_system"] for row in constrained_rows] == ["roberta_pair_track"]
    assert constrained_rows[0]["status"] == "supports_constrained_risk_advantage"


def test_write_model_superiority_summary_counts_constrained_risk_rows(tmp_path) -> None:
    """验证 summary 统计 constrained-risk 支持项。"""
    output_dir = tmp_path / "superiority"
    rows = build_constrained_risk_superiority_rows(
        risk_protocol_rows=[
            {"system": "risk_method", "is_selected": 1, "fpr_budget": 0.03, "fdr_budget": 0.10, "safe_merge_recall": 0.42},
            {"system": "baseline", "is_selected": 1, "fpr_budget": 0.03, "fdr_budget": 0.10, "safe_merge_recall": 0.20},
        ],
        main_system="risk_method",
        required_baselines=["baseline"],
    )

    write_model_superiority_audit_outputs(rows, output_dir)

    summary = read_records(output_dir / "model_superiority_audit_summary.jsonl")[0]
    assert summary["constrained_risk_advantage_count"] == 1
    assert summary["overall_superiority_status"] == "limited"


def test_build_model_superiority_audit_cli_accepts_risk_protocols(tmp_path) -> None:
    """验证 CLI 接受 risk protocol 输入。"""
    advanced = tmp_path / "advanced.jsonl"
    risk_protocol = tmp_path / "risk_protocol.jsonl"
    output_dir = tmp_path / "superiority"
    _write_jsonl(
        advanced,
        [
            {"system": "risk_method", "evidence_type": "main_method_transformer", "evidence_status": "ready_actual_model", "evaluation_track": "track"},
            {"system": "baseline", "evidence_type": "representation", "evidence_status": "ready_actual_model", "evaluation_track": "track"},
        ],
    )
    _write_jsonl(
        risk_protocol,
        [
            {"system": "risk_method", "is_selected": 1, "fpr_budget": 0.03, "fdr_budget": 0.10, "safe_merge_recall": 0.42},
            {"system": "baseline", "is_selected": 1, "fpr_budget": 0.03, "fdr_budget": 0.10, "safe_merge_recall": 0.20},
        ],
    )

    command_build_model_superiority_audit(
        Namespace(
            advanced_model_evidence=[str(advanced)],
            model_innovation_blueprints=[],
            risk_protocols=[str(risk_protocol)],
            main_system="risk_method",
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "model_superiority_audit.jsonl")
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-model-superiority-audit",
            "--advanced-model-evidence",
            str(advanced),
            "--risk-protocols",
            str(risk_protocol),
            "--main-system",
            "risk_method",
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.risk_protocols == [str(risk_protocol)]
