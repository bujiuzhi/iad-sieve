"""测试创新可证伪矩阵。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_novelty_falsification_matrix
from iad_sieve.evaluation.novelty_falsification_matrix import (
    build_novelty_falsification_rows,
    build_novelty_falsification_rows_from_paths,
    write_novelty_falsification_outputs,
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


def _blueprint_rows() -> list[dict]:
    """构造模型创新蓝图测试记录。

    参数:
        无。

    返回:
        测试记录列表。
    """
    return [
        {"blueprint_id": "main_method_vs_single_space_representation", "status": "ready"},
        {"blueprint_id": "pair_classifier_strong_baseline_comparison", "status": "ready"},
        {"blueprint_id": "specter2_encoder_stability", "status": "blocked"},
        {"blueprint_id": "provenance_blind_model_validity", "status": "blocked"},
        {"blueprint_id": "open_v3_source_heldout_generalization", "status": "blocked"},
        {"blueprint_id": "llm_pair_judge_comparison", "status": "conditional"},
    ]


def _innovation_rows() -> list[dict]:
    """构造创新深度压力审计测试记录。

    参数:
        无。

    返回:
        测试记录列表。
    """
    return [
        {"stress_id": "mechanism_explanation_depth", "status": "ready"},
        {"stress_id": "strong_baseline_depth", "status": "conditional"},
        {"stress_id": "leakage_guard_depth", "status": "blocked"},
        {"stress_id": "generalization_depth", "status": "blocked"},
    ]


def test_build_novelty_falsification_rows_links_claims_to_reviewer_null_hypotheses() -> None:
    """验证矩阵把创新主张转换为可证伪审稿门槛。"""
    rows = build_novelty_falsification_rows(
        model_innovation_blueprint_rows=_blueprint_rows(),
        innovation_depth_rows=_innovation_rows(),
        model_superiority_summary={"overall_superiority_status": "conditional", "blocked_missing_comparison_count": 2},
        no_annotation_summary={"no_annotation_stage_allowed": True, "blocked_annotation_count": 0},
    )
    by_id = {row["contribution_id"]: row for row in rows}

    assert by_id["risk_decomposition_vs_single_space"]["status"] == "ready"
    assert by_id["strong_model_superiority_control"]["status"] == "conditional"
    assert by_id["encoder_and_provenance_validity"]["status"] == "blocked"
    assert by_id["source_heldout_generalization_boundary"]["status"] == "blocked"
    assert by_id["no_annotation_claim_boundary"]["status"] == "ready"
    assert "零假设" not in by_id["risk_decomposition_vs_single_space"]["reviewer_null_hypothesis"]
    assert "SciNCL/SPECTER2" in by_id["risk_decomposition_vs_single_space"]["nearest_prior_art_family"]
    assert "不能替代人工 gold" in by_id["no_annotation_claim_boundary"]["paper_claim_boundary"]


def test_build_novelty_falsification_rows_uses_ready_actions_for_ready_evidence() -> None:
    """验证 ready 贡献项不再输出已完成实验的待执行动作。"""
    rows = build_novelty_falsification_rows(
        model_innovation_blueprint_rows=[
            {"blueprint_id": "main_method_vs_single_space_representation", "status": "ready"},
            {"blueprint_id": "pair_classifier_strong_baseline_comparison", "status": "blocked"},
            {"blueprint_id": "specter2_encoder_stability", "status": "ready"},
            {"blueprint_id": "provenance_blind_model_validity", "status": "ready"},
            {"blueprint_id": "open_v3_source_heldout_generalization", "status": "ready"},
        ],
        innovation_depth_rows=[
            {"stress_id": "mechanism_explanation_depth", "status": "ready"},
            {"stress_id": "leakage_guard_depth", "status": "ready"},
            {"stress_id": "generalization_depth", "status": "ready"},
        ],
        model_superiority_summary={"overall_superiority_status": "blocked", "blocked_missing_comparison_count": 2},
        no_annotation_summary={"no_annotation_stage_allowed": True, "blocked_annotation_count": 0},
    )
    by_id = {row["contribution_id"]: row for row in rows}

    validity_row = by_id["encoder_and_provenance_validity"]
    source_row = by_id["source_heldout_generalization_boundary"]

    assert validity_row["status"] == "ready"
    assert source_row["status"] == "ready"
    assert "远程执行 SPECTER2" not in validity_row["next_action"]
    assert "应用 source-held-out assignment" not in source_row["next_action"]
    assert "未 ready 前" not in validity_row["paper_claim_boundary"]
    assert "未 ready 前" not in source_row["paper_claim_boundary"]


def test_build_novelty_falsification_rows_accepts_limited_constrained_risk_superiority() -> None:
    """验证风险预算下 limited 优势可关闭强模型控制创新项。"""
    rows = build_novelty_falsification_rows(
        model_innovation_blueprint_rows=_blueprint_rows(),
        innovation_depth_rows=_innovation_rows(),
        model_superiority_summary={
            "overall_superiority_status": "limited",
            "blocked_missing_comparison_count": 0,
            "constrained_risk_advantage_count": 2,
            "constrained_risk_not_supported_count": 0,
        },
        no_annotation_summary={"no_annotation_stage_allowed": True, "blocked_annotation_count": 0},
    )
    by_id = {row["contribution_id"]: row for row in rows}

    row = by_id["strong_model_superiority_control"]
    assert row["status"] == "ready"
    assert row["blocked_reasons"] == []
    assert "constrained_risk_advantage_count=2" in row["current_evidence"]
    assert "不得声称全面 SOTA" in row["paper_claim_boundary"]


def test_write_novelty_falsification_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证创新可证伪矩阵写出 JSONL、CSV、Markdown 和摘要。"""
    output_dir = tmp_path / "novelty_falsification_matrix"
    rows = build_novelty_falsification_rows(
        model_innovation_blueprint_rows=_blueprint_rows(),
        innovation_depth_rows=_innovation_rows(),
        model_superiority_summary={"overall_superiority_status": "conditional", "blocked_missing_comparison_count": 2},
        no_annotation_summary={"no_annotation_stage_allowed": True, "blocked_annotation_count": 0},
    )

    write_novelty_falsification_outputs(rows, output_dir)

    assert read_records(output_dir / "novelty_falsification_matrix.jsonl")
    assert (output_dir / "novelty_falsification_matrix.csv").exists()
    assert "# Novelty Falsification Matrix" in (output_dir / "novelty_falsification_matrix.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "novelty_falsification_matrix_summary.jsonl")[0]
    assert summary["contribution_count"] == 5
    assert summary["ready_contribution_count"] == 2
    assert summary["blocked_contribution_count"] == 2
    assert summary["q2b_novelty_defensible"] is False
    assert summary["highest_priority_blocker"] == "encoder_and_provenance_validity"


def test_build_novelty_falsification_from_paths_and_cli_write_outputs(tmp_path) -> None:
    """验证文件输入和 CLI 均可生成创新可证伪矩阵。"""
    blueprint = tmp_path / "model_innovation_blueprint.jsonl"
    innovation = tmp_path / "innovation_depth_stress_test.jsonl"
    superiority = tmp_path / "model_superiority_audit_summary.jsonl"
    no_annotation = tmp_path / "no_annotation_protocol_summary.jsonl"
    output_dir = tmp_path / "novelty_falsification_matrix"
    _write_jsonl(blueprint, _blueprint_rows())
    _write_jsonl(innovation, _innovation_rows())
    _write_jsonl(superiority, [{"overall_superiority_status": "conditional", "blocked_missing_comparison_count": 2}])
    _write_jsonl(no_annotation, [{"no_annotation_stage_allowed": True, "blocked_annotation_count": 0}])

    rows = build_novelty_falsification_rows_from_paths(
        model_innovation_blueprint_paths=[blueprint],
        innovation_depth_paths=[innovation],
        model_superiority_summary_path=superiority,
        no_annotation_summary_path=no_annotation,
    )
    assert len(rows) == 5

    command_build_novelty_falsification_matrix(
        Namespace(
            model_innovation_blueprints=[str(blueprint)],
            innovation_depth_audits=[str(innovation)],
            model_superiority_summary=str(superiority),
            no_annotation_summary=str(no_annotation),
            output_dir=str(output_dir),
        )
    )
    assert read_records(output_dir / "novelty_falsification_matrix_summary.jsonl")[0]["blocked_contribution_count"] == 2

    parser = build_parser()
    args = parser.parse_args(
        [
            "build-novelty-falsification-matrix",
            "--model-innovation-blueprints",
            str(blueprint),
            "--innovation-depth-audits",
            str(innovation),
            "--model-superiority-summary",
            str(superiority),
            "--no-annotation-summary",
            str(no_annotation),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_novelty_falsification_matrix
