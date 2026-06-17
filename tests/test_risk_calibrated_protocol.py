"""测试风险校准选择性实体匹配协议。"""

from __future__ import annotations

import csv

from iad_sieve.cli import build_parser
from iad_sieve.evaluation.risk_calibrated_protocol import (
    assign_selective_decision,
    run_risk_calibrated_protocol,
    write_risk_calibrated_protocol_outputs,
)


def test_run_risk_calibrated_protocol_selects_threshold_under_fpr_and_fdr_budgets() -> None:
    """验证协议在 FPR/FDR 双重预算下选择最大安全合并召回阈值。"""
    relations = [
        {"expected_label": 1, "identity_score": 0.95, "conflict_score": 0.10, "uncertainty_score": 0.05},
        {"expected_label": 1, "identity_score": 0.86, "conflict_score": 0.10, "uncertainty_score": 0.05},
        {
            "expected_label": 0,
            "identity_score": 0.88,
            "conflict_score": 0.10,
            "uncertainty_score": 0.05,
            "relation_label": "agenda_non_identity",
        },
        {
            "expected_label": 0,
            "identity_score": 0.93,
            "conflict_score": 0.80,
            "uncertainty_score": 0.05,
            "relation_label": "agenda_non_identity",
        },
    ]

    rows = run_risk_calibrated_protocol(
        relations,
        identity_thresholds=[0.85, 0.90],
        conflict_thresholds=[0.30],
        uncertainty_thresholds=[0.30],
        version_risk_thresholds=[0.50],
        fpr_budgets=[0.10],
        fdr_budgets=[0.10],
    )

    selected = [row for row in rows if row["is_selected"] == 1]

    assert len(selected) == 1
    assert selected[0]["identity_threshold"] == 0.90
    assert selected[0]["safe_merge_precision"] == 1.0
    assert selected[0]["safe_merge_recall"] == 0.5
    assert selected[0]["negative_false_merge_rate"] == 0.0
    assert selected[0]["merge_contamination_fdr"] == 0.0
    assert selected[0]["review_rate"] == 0.25
    assert selected[0]["hard_negative_false_merge_rate"] == 0.0


def test_assign_selective_decision_separates_safe_merge_reject_and_manual_review() -> None:
    """验证三态决策可区分安全合并、拒绝合并和人工复核。"""
    thresholds = {
        "identity_threshold": 0.90,
        "conflict_threshold": 0.30,
        "uncertainty_threshold": 0.30,
        "version_risk_threshold": 0.50,
    }

    assert assign_selective_decision({"identity_score": 0.95, "conflict_score": 0.10}, **thresholds)["decision"] == "safe_merge"
    assert assign_selective_decision({"identity_score": 0.95, "conflict_score": 0.80}, **thresholds)["decision"] == "manual_review"
    assert assign_selective_decision({"identity_score": 0.95, "version_risk_score": 0.90}, **thresholds)["decision"] == "manual_review"
    assert assign_selective_decision({"identity_score": 0.95, "uncertainty_score": 0.90}, **thresholds)["decision"] == "manual_review"
    assert assign_selective_decision({"identity_score": 0.20, "conflict_score": 0.10}, **thresholds)["decision"] == "reject"


def test_assign_selective_decision_applies_explicit_veto_fields() -> None:
    """验证显式 veto 字段优先把高风险合并转入人工复核。"""
    decision = assign_selective_decision(
        {"identity_score": 0.99, "conflict_score": 0.01, "identifier_conflict": True},
        identity_threshold=0.90,
        conflict_threshold=0.30,
        uncertainty_threshold=0.30,
        version_risk_threshold=0.50,
        veto_fields=["identifier_conflict"],
    )

    assert decision["decision"] == "manual_review"
    assert decision["decision_reason"] == "veto_field_triggered:identifier_conflict"
    assert decision["veto_triggered"] == 1
    assert decision["veto_field"] == "identifier_conflict"


def test_run_risk_calibrated_protocol_counts_vetoed_safe_merges() -> None:
    """验证风险协议统计被 veto 转入人工复核的自动合并候选。"""
    rows = run_risk_calibrated_protocol(
        [
            {"expected_label": 1, "identity_score": 0.95, "conflict_score": 0.10},
            {
                "expected_label": 0,
                "identity_score": 0.99,
                "conflict_score": 0.01,
                "identifier_conflict": True,
                "relation_label": "agenda_non_identity",
            },
        ],
        identity_thresholds=[0.90],
        conflict_thresholds=[0.30],
        uncertainty_thresholds=[0.30],
        version_risk_thresholds=[0.50],
        fpr_budgets=[0.01],
        fdr_budgets=[0.01],
        veto_fields=["identifier_conflict"],
    )

    row = rows[0]
    assert row["veto_fields"] == "identifier_conflict"
    assert row["vetoed_merge_count"] == 1
    assert row["manual_review_count"] == 1
    assert row["false_positive"] == 0
    assert row["hard_negative_false_merge_count"] == 0
    assert row["is_selected"] == 1


def test_run_risk_calibrated_protocol_does_not_count_low_identity_veto_as_vetoed_merge() -> None:
    """验证低 identity reject 样本不计入 vetoed_merge_count。"""
    rows = run_risk_calibrated_protocol(
        [
            {
                "expected_label": 0,
                "identity_score": 0.20,
                "conflict_score": 0.01,
                "identifier_conflict": True,
                "relation_label": "agenda_non_identity",
            },
            {
                "expected_label": 0,
                "identity_score": 0.99,
                "conflict_score": 0.01,
                "identifier_conflict": True,
                "relation_label": "agenda_non_identity",
            },
        ],
        identity_thresholds=[0.90],
        conflict_thresholds=[0.30],
        uncertainty_thresholds=[0.30],
        version_risk_thresholds=[0.50],
        fpr_budgets=[0.01],
        fdr_budgets=[0.01],
        veto_fields=["identifier_conflict"],
    )

    row = rows[0]
    assert row["reject_count"] == 1
    assert row["manual_review_count"] == 1
    assert row["vetoed_merge_count"] == 1


def test_run_risk_calibrated_protocol_does_not_count_high_conflict_veto_as_vetoed_merge() -> None:
    """验证本会因 conflict 复核的样本不计入 vetoed_merge_count。"""
    rows = run_risk_calibrated_protocol(
        [
            {
                "expected_label": 0,
                "identity_score": 0.99,
                "conflict_score": 0.80,
                "identifier_conflict": True,
                "relation_label": "agenda_non_identity",
            },
            {
                "expected_label": 0,
                "identity_score": 0.99,
                "conflict_score": 0.01,
                "identifier_conflict": True,
                "relation_label": "agenda_non_identity",
            },
        ],
        identity_thresholds=[0.90],
        conflict_thresholds=[0.30],
        uncertainty_thresholds=[0.30],
        version_risk_thresholds=[0.50],
        fpr_budgets=[0.01],
        fdr_budgets=[0.01],
        veto_fields=["identifier_conflict"],
    )

    row = rows[0]
    assert row["manual_review_count"] == 2
    assert row["vetoed_merge_count"] == 1


def test_run_risk_calibrated_protocol_can_filter_evaluation_split() -> None:
    """验证协议可只评估指定 split，避免训练集混入主评价。"""
    rows = run_risk_calibrated_protocol(
        [
            {"expected_label": 1, "identity_score": 0.95, "conflict_score": 0.10, "split": "test"},
            {"expected_label": 0, "identity_score": 0.20, "conflict_score": 0.10, "split": "test"},
            {"expected_label": 0, "identity_score": 0.95, "conflict_score": 0.10, "split": "train"},
        ],
        identity_thresholds=[0.90],
        conflict_thresholds=[0.30],
        uncertainty_thresholds=[0.30],
        version_risk_thresholds=[0.50],
        fpr_budgets=[0.01],
        fdr_budgets=[0.01],
        eval_split="test",
    )

    assert rows[0]["pair_count"] == 2
    assert rows[0]["negative_false_merge_rate"] == 0.0


def test_run_risk_calibrated_protocol_accepts_explicit_system_name() -> None:
    """验证协议可给单文件输入显式指定 system 名称。"""
    rows = run_risk_calibrated_protocol(
        [
            {"expected_label": 1, "identity_score": 0.95, "conflict_score": 0.10},
            {"expected_label": 0, "identity_score": 0.20, "conflict_score": 0.10},
        ],
        identity_thresholds=[0.90],
        conflict_thresholds=[0.30],
        uncertainty_thresholds=[0.30],
        version_risk_thresholds=[0.50],
        fpr_budgets=[0.01],
        fdr_budgets=[0.01],
        system_name="explicit_system",
    )

    assert rows[0]["system"] == "explicit_system"


def test_write_risk_calibrated_protocol_outputs_writes_summary_and_table(tmp_path) -> None:
    """验证风险校准协议输出 CSV、JSONL 和 Markdown 摘要。"""
    rows = run_risk_calibrated_protocol(
        [
            {"expected_label": 1, "identity_score": 0.95, "conflict_score": 0.10},
            {"expected_label": 0, "identity_score": 0.20, "conflict_score": 0.10},
        ],
        identity_thresholds=[0.90],
        conflict_thresholds=[0.30],
        uncertainty_thresholds=[0.30],
        version_risk_thresholds=[0.50],
        fpr_budgets=[0.01],
        fdr_budgets=[0.01],
    )

    write_risk_calibrated_protocol_outputs(rows, tmp_path)

    csv_path = tmp_path / "risk_calibrated_protocol.csv"
    summary_path = tmp_path / "risk_calibrated_protocol_summary.jsonl"
    markdown_path = tmp_path / "risk_calibrated_protocol.md"

    assert csv_path.exists()
    assert summary_path.exists()
    assert markdown_path.exists()
    with csv_path.open("r", encoding="utf-8", newline="") as file:
        written_rows = list(csv.DictReader(file))
    assert written_rows[0]["evaluation_protocol"] == "risk_calibrated_selective_entity_matching"
    assert written_rows[0]["is_selected"] == "1"


def test_cli_includes_run_risk_calibrated_protocol_command() -> None:
    """验证 CLI 暴露 run-risk-calibrated-protocol 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-risk-calibrated-protocol",
            "--relations",
            "scored_relations.jsonl",
            "--output-dir",
            "outputs/risk_protocol",
            "--identity-thresholds",
            "0.85,0.90",
            "--fpr-budgets",
            "0.01,0.05",
            "--fdr-budgets",
            "0.01,0.05",
            "--system-name",
            "scincl_baseline",
            "--veto-fields",
            "identifier_conflict",
        ]
    )

    assert args.command == "run-risk-calibrated-protocol"
    assert args.identity_thresholds == "0.85,0.90"
    assert args.fpr_budgets == "0.01,0.05"
    assert args.system_name == "scincl_baseline"
    assert args.veto_fields == "identifier_conflict"
