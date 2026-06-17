"""测试审稿人批判清单与回应矩阵。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_reviewer_audit
from iad_sieve.evaluation.reviewer_audit import build_reviewer_audit_rows
from iad_sieve.utils.io_utils import read_records


def _write_jsonl(path, records: list[dict]) -> None:
    """写入 JSONL 测试文件。

    参数:
        path: 输出路径。
        records: 记录列表。

    返回:
        无。
    """
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def test_build_reviewer_audit_rows_cover_core_reviewer_concerns(tmp_path) -> None:
    """验证审稿矩阵覆盖核心批判点并读取 RQ 证据。"""
    rq_summary = tmp_path / "rq_summary.jsonl"
    _write_jsonl(
        rq_summary,
        [
            {"rq": "RQ1", "evidence_layer": "same_work_gold", "system": "iad_sieve_conservative", "f1": 1.0},
            {"rq": "RQ2", "evidence_layer": "same_agenda_proxy", "system": "iad_agenda_score_threshold", "f1": 0.8},
            {"rq": "RQ2", "evidence_layer": "agenda_non_identity_weak", "system": "iad_sieve_conservative", "f1": 0.0},
            {"rq": "RQ1", "evidence_layer": "external_baseline", "system": "specter2_cosine", "f1": 0.9},
            {"rq": "RQ3", "evidence_layer": "iad_ablation", "system": "without_agenda_non_identity", "f1": 0.7},
        ],
    )

    rows = build_reviewer_audit_rows([rq_summary])
    concern_ids = {row["concern_id"] for row in rows}
    innovation_row = next(row for row in rows if row["concern_id"] == "innovation_depth")

    assert {
        "innovation_depth",
        "duplicate_work",
        "weak_label_noise",
        "baseline_strength",
        "ablation_validity",
        "reproducibility",
        "model_depth",
        "executed_strong_baselines",
        "label_provenance",
        "statistical_stability",
        "human_audit_deferral",
        "venue_readiness",
    } <= concern_ids
    assert innovation_row["status"] == "evidence_ready"
    assert "RQ3" in innovation_row["current_artifacts"]


def test_build_reviewer_audit_rows_marks_missing_external_baseline() -> None:
    """验证缺少外部 baseline 时强基线风险不会被误判为已解决。"""
    rows = build_reviewer_audit_rows([])
    baseline_row = next(row for row in rows if row["concern_id"] == "baseline_strength")

    assert baseline_row["status"] == "needs_evidence"
    assert "external_baseline" in baseline_row["required_evidence"]


def test_build_reviewer_audit_rows_requires_executed_strong_baselines(tmp_path) -> None:
    """验证仅有占位外部 baseline 时，强模型执行风险仍需补证据。"""
    rq_summary = tmp_path / "rq_summary.jsonl"
    _write_jsonl(
        rq_summary,
        [
            {"rq": "RQ1", "evidence_layer": "external_baseline", "system": "specter2_cosine", "f1": 0.9},
        ],
    )

    rows = build_reviewer_audit_rows([rq_summary])
    strong_baseline_row = next(row for row in rows if row["concern_id"] == "executed_strong_baselines")

    assert strong_baseline_row["status"] == "needs_evidence"
    assert "SPECTER2/SciNCL" in strong_baseline_row["required_evidence"]


def test_build_reviewer_audit_rows_accepts_three_executed_strong_baseline_families(tmp_path) -> None:
    """验证三类真实执行强 baseline 同时出现后才判为已具备证据。"""
    rq_summary = tmp_path / "rq_summary.jsonl"
    _write_jsonl(
        rq_summary,
        [
            {
                "rq": "RQ1",
                "evidence_layer": "external_baseline",
                "system": "specter2_cosine",
                "baseline_family": "representation",
                "execution_mode": "actual_model",
                "f1": 0.9,
            },
            {
                "rq": "RQ1",
                "evidence_layer": "external_baseline",
                "system": "ditto_roberta",
                "baseline_family": "entity_matching",
                "execution_mode": "actual_model",
                "f1": 0.9,
            },
            {
                "rq": "RQ1",
                "evidence_layer": "external_baseline",
                "system": "gpt_pair_judge",
                "baseline_family": "llm_judge",
                "execution_mode": "api_model",
                "f1": 0.9,
            },
        ],
    )

    rows = build_reviewer_audit_rows([rq_summary])
    strong_baseline_row = next(row for row in rows if row["concern_id"] == "executed_strong_baselines")

    assert strong_baseline_row["status"] == "evidence_ready"


def test_build_reviewer_audit_rows_accepts_iad_risk_model_depth_evidence(tmp_path) -> None:
    """验证 IAD-Risk 模型证据可支撑模型深度风险。"""
    rq_summary = tmp_path / "rq_summary.jsonl"
    _write_jsonl(
        rq_summary,
        [
            {
                "rq": "RQ3",
                "evidence_layer": "iad_risk_model",
                "system": "iad_risk_dual_space",
                "model_type": "iad_risk_dual_space_centroid_model",
                "trained": True,
            },
        ],
    )

    rows = build_reviewer_audit_rows([rq_summary])
    model_depth_row = next(row for row in rows if row["concern_id"] == "model_depth")

    assert model_depth_row["status"] == "evidence_ready"


def test_build_reviewer_audit_rows_requires_bootstrap_confidence_for_statistical_stability(tmp_path) -> None:
    """验证统计稳定性风险需要 bootstrap confidence 证据。"""
    rq_summary = tmp_path / "rq_summary.jsonl"
    _write_jsonl(
        rq_summary,
        [
            {"rq": "RQ1", "evidence_layer": "same_work_gold", "system": "iad_sieve_conservative"},
            {"rq": "RQ2", "evidence_layer": "agenda_non_identity_weak", "system": "iad_sieve_conservative"},
        ],
    )

    rows = build_reviewer_audit_rows([rq_summary])
    stability_row = next(row for row in rows if row["concern_id"] == "statistical_stability")

    assert stability_row["status"] == "needs_evidence"
    assert "bootstrap confidence interval" in stability_row["required_evidence"]


def test_build_reviewer_audit_rows_accepts_bootstrap_confidence(tmp_path) -> None:
    """验证 RQ1/RQ2 同时具备 bootstrap 证据时统计稳定性通过。"""
    rq_summary = tmp_path / "rq_summary.jsonl"
    _write_jsonl(
        rq_summary,
        [
            {"rq": "RQ1", "evidence_layer": "iad_bootstrap_confidence", "system": "iad_risk_dual_space", "metric_target": "all_pairs"},
            {"rq": "RQ2", "evidence_layer": "iad_bootstrap_confidence", "system": "iad_risk_dual_space", "metric_target": "hard_negative_pairs"},
        ],
    )

    rows = build_reviewer_audit_rows([rq_summary])
    stability_row = next(row for row in rows if row["concern_id"] == "statistical_stability")

    assert stability_row["status"] == "evidence_ready"


def test_build_reviewer_audit_rows_keeps_venue_readiness_strict(tmp_path) -> None:
    """验证 venue readiness 不因普通证据层齐全而忽略强 baseline 和人工 audit 缺口。"""
    rq_summary = tmp_path / "rq_summary.jsonl"
    _write_jsonl(
        rq_summary,
        [
            {"rq": "RQ1", "evidence_layer": "same_work_gold", "system": "iad_sieve_conservative"},
            {"rq": "RQ2", "evidence_layer": "same_agenda_proxy", "system": "iad_agenda_score_threshold"},
            {"rq": "RQ2", "evidence_layer": "agenda_non_identity_weak", "system": "iad_sieve_conservative"},
            {"rq": "RQ1", "evidence_layer": "external_baseline", "system": "scincl_cosine", "baseline_family": "representation", "execution_mode": "actual_model"},
            {"rq": "RQ3", "evidence_layer": "iad_risk_model", "system": "iad_risk_dual_space"},
            {"rq": "RQ3", "evidence_layer": "iad_ablation", "system": "iad_full"},
            {"rq": "RQ1", "evidence_layer": "iad_bench_provenance", "system": "iad_bench"},
            {"rq": "RQ2", "evidence_layer": "iad_bench_provenance", "system": "iad_bench"},
            {"rq": "RQ1", "evidence_layer": "iad_bootstrap_confidence", "system": "iad_risk_dual_space"},
            {"rq": "RQ2", "evidence_layer": "iad_bootstrap_confidence", "system": "iad_risk_dual_space"},
            {"rq": "RQ4", "evidence_layer": "iad_bootstrap_confidence", "system": "iad_risk_dual_space"},
        ],
    )

    rows = build_reviewer_audit_rows([rq_summary])
    venue_row = next(row for row in rows if row["concern_id"] == "venue_readiness")

    assert venue_row["status"] == "needs_evidence"
    assert "强 baseline" in venue_row["required_evidence"]


def test_build_reviewer_audit_cli_writes_jsonl_csv_and_markdown(tmp_path) -> None:
    """验证 CLI 写出审稿矩阵三类产物。"""
    rq_summary = tmp_path / "rq_summary.jsonl"
    output_dir = tmp_path / "reviewer_audit"
    _write_jsonl(
        rq_summary,
        [
            {"rq": "RQ1", "evidence_layer": "same_work_gold", "system": "iad_sieve_conservative", "f1": 1.0},
            {"rq": "RQ3", "evidence_layer": "iad_ablation", "system": "iad_full", "f1": 1.0},
        ],
    )

    command_build_reviewer_audit(
        Namespace(
            rq_summaries=[str(rq_summary)],
            output_dir=str(output_dir),
        )
    )

    rows = read_records(output_dir / "reviewer_audit.jsonl")

    assert rows
    assert (output_dir / "reviewer_audit.csv").exists()
    assert "# Reviewer Audit Matrix" in (output_dir / "reviewer_audit.md").read_text(encoding="utf-8")


def test_cli_includes_build_reviewer_audit_command() -> None:
    """验证 CLI 暴露 build-reviewer-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-reviewer-audit",
            "--rq-summaries",
            "outputs/iad_paper_report_fixture/rq_summary.jsonl",
            "--output-dir",
            "outputs/reviewer_audit_fixture",
        ]
    )

    assert args.command == "build-reviewer-audit"
    assert args.rq_summaries == ["outputs/iad_paper_report_fixture/rq_summary.jsonl"]
