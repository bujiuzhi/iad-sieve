"""测试创新深度压力审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_innovation_depth_stress_test
from iad_sieve.evaluation.innovation_depth_stress_test import (
    build_innovation_depth_stress_rows,
    build_innovation_depth_stress_rows_from_paths,
    write_innovation_depth_stress_outputs,
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
        蓝图记录列表。
    """
    return [
        {
            "blueprint_id": "main_method_vs_single_space_representation",
            "status": "ready",
            "comparison_family": "mechanism_comparison",
            "paper_claim_boundary": "只能支撑机制性创新。",
        },
        {
            "blueprint_id": "pair_classifier_strong_baseline_comparison",
            "status": "ready",
            "comparison_family": "strong_baseline_comparison",
            "paper_claim_boundary": "只能说已完成部分强 baseline。",
        },
        {
            "blueprint_id": "provenance_blind_model_validity",
            "status": "blocked",
            "comparison_family": "leakage_guard",
            "paper_claim_boundary": "不能写成无泄漏最终模型。",
        },
        {
            "blueprint_id": "open_v3_source_heldout_generalization",
            "status": "blocked",
            "comparison_family": "generalization_split",
            "paper_claim_boundary": "不能写泛化稳定。",
        },
    ]


def _superiority_rows() -> list[dict]:
    """构造模型优势审计测试记录。

    参数:
        无。

    返回:
        模型优势审计记录列表。
    """
    return [
        {
            "baseline_system": "scincl_cosine_open_v2",
            "comparison_family": "representation",
            "status": "supports_limited_superiority",
            "hard_negative_false_merge_rate_reduction": 0.79,
        },
        {
            "baseline_system": "roberta_pair_open_v2",
            "comparison_family": "pair_classifier",
            "status": "mixed_targeted_advantage",
            "hard_negative_false_merge_rate_reduction": 0.0001,
        },
        {
            "baseline_system": "specter2_adapter_cosine_open_v2",
            "comparison_family": "representation",
            "status": "blocked_missing_baseline",
        },
    ]


def _mechanism_rows() -> list[dict]:
    """构造机制证据测试记录。

    参数:
        无。

    返回:
        机制证据记录列表。
    """
    return [
        {
            "system": "scincl_cosine_open_v2",
            "baseline_false_merge_count": 3,
            "iad_prevented_false_merge_count": 3,
            "iad_unresolved_false_merge_count": 0,
            "prevention_rate": 1.0,
            "mechanism_status": "strong_mechanism_evidence",
        }
    ]


def test_build_innovation_depth_stress_rows_separates_surviving_and_blocked_claims() -> None:
    """验证创新深度压力审计区分可保留机制主张和阻塞先进性主张。"""
    rows = build_innovation_depth_stress_rows(
        model_innovation_blueprint_rows=_blueprint_rows(),
        model_superiority_audit_rows=_superiority_rows(),
        mechanism_evidence_rows=_mechanism_rows(),
        mechanism_sensitivity_rows=[],
    )
    by_id = {row["stress_id"]: row for row in rows}

    assert by_id["mechanism_explanation_depth"]["status"] == "ready"
    assert "prevention_rate=1.0" in by_id["mechanism_explanation_depth"]["current_evidence"]
    assert "机制性创新" in by_id["mechanism_explanation_depth"]["surviving_claim"]
    assert by_id["strong_baseline_depth"]["status"] == "blocked"
    assert "missing_strong_comparison" in by_id["strong_baseline_depth"]["blocking_reasons"]
    assert by_id["leakage_guard_depth"]["status"] == "blocked"
    assert by_id["generalization_depth"]["status"] == "blocked"
    assert by_id["overall_innovation_depth"]["status"] == "blocked"


def test_build_innovation_depth_stress_rows_conditions_limited_triangulation() -> None:
    """验证三角验证不足时机制解释只能作为 conditional。"""
    rows = build_innovation_depth_stress_rows(
        model_innovation_blueprint_rows=_blueprint_rows(),
        model_superiority_audit_rows=_superiority_rows(),
        mechanism_evidence_rows=_mechanism_rows(),
        mechanism_sensitivity_rows=[],
        mechanism_triangulation_summary_rows=[
            {
                "triangulation_status": "parallel_family_mechanism_evidence",
                "q2b_mechanism_depth_ready": False,
            }
        ],
    )
    by_id = {row["stress_id"]: row for row in rows}

    assert by_id["mechanism_explanation_depth"]["status"] == "conditional"
    assert "mechanism_triangulation_limited" in by_id["mechanism_explanation_depth"]["blocking_reasons"]
    assert "mechanism_triangulation_limited" in by_id["overall_innovation_depth"]["blocking_reasons"]


def test_build_innovation_depth_stress_rows_conditions_limited_threshold_stability() -> None:
    """验证阈值稳定性不足时机制解释只能作为 conditional。"""
    rows = build_innovation_depth_stress_rows(
        model_innovation_blueprint_rows=_blueprint_rows(),
        model_superiority_audit_rows=_superiority_rows(),
        mechanism_evidence_rows=_mechanism_rows(),
        mechanism_sensitivity_rows=[],
        mechanism_triangulation_summary_rows=[
            {
                "triangulation_status": "cross_system_mechanism_evidence",
                "q2b_mechanism_depth_ready": True,
            }
        ],
        mechanism_triangulation_sensitivity_summary_rows=[
            {
                "threshold_stability_status": "threshold_limited_cross_system_evidence",
                "q2b_threshold_stability_ready": False,
            }
        ],
    )
    by_id = {row["stress_id"]: row for row in rows}

    assert by_id["mechanism_explanation_depth"]["status"] == "conditional"
    assert "mechanism_threshold_stability_limited" in by_id["mechanism_explanation_depth"]["blocking_reasons"]
    assert "threshold_stability_status=threshold_limited_cross_system_evidence" in by_id["mechanism_explanation_depth"]["current_evidence"]
    assert "mechanism_threshold_stability_limited" in by_id["overall_innovation_depth"]["blocking_reasons"]


def test_build_innovation_depth_stress_rows_uses_topic_holdout_split_evidence() -> None:
    """验证 multi-topic split 证据可解除 topic-heldout 后置阻塞。"""
    rows = build_innovation_depth_stress_rows(
        model_innovation_blueprint_rows=_blueprint_rows(),
        model_superiority_audit_rows=_superiority_rows(),
        mechanism_evidence_rows=_mechanism_rows(),
        mechanism_sensitivity_rows=[],
        split_readiness_audit_rows=[
            {"dimension_id": "source_held_out_readiness", "audit_status": "blocked"},
            {"dimension_id": "topic_held_out_readiness", "audit_status": "defensible"},
        ],
    )
    by_id = {row["stress_id"]: row for row in rows}

    assert by_id["generalization_depth"]["status"] == "blocked"
    assert by_id["generalization_depth"]["blocking_reasons"] == ["source_heldout_missing"]
    assert "topic_held_out_readiness=defensible" in by_id["generalization_depth"]["current_evidence"]
    assert "topic_heldout_deferred" not in by_id["overall_innovation_depth"]["blocking_reasons"]


def test_build_innovation_depth_stress_rows_uses_ready_actions_for_ready_controls() -> None:
    """验证已 ready 的泄漏防护与泛化控制不再输出待执行动作。"""
    ready_blueprints = [
        {**row, "status": "ready"}
        for row in _blueprint_rows()
    ]
    rows = build_innovation_depth_stress_rows(
        model_innovation_blueprint_rows=ready_blueprints,
        model_superiority_audit_rows=_superiority_rows(),
        mechanism_evidence_rows=_mechanism_rows(),
        mechanism_sensitivity_rows=[],
        split_readiness_audit_rows=[
            {"dimension_id": "source_held_out_readiness", "audit_status": "defensible"},
            {"dimension_id": "topic_held_out_readiness", "audit_status": "defensible"},
        ],
    )
    by_id = {row["stress_id"]: row for row in rows}

    assert by_id["leakage_guard_depth"]["status"] == "ready"
    assert "重训 provenance-blind" not in by_id["leakage_guard_depth"]["next_action"]
    assert "未 ready 前" not in by_id["leakage_guard_depth"]["paper_claim_boundary"]
    assert by_id["generalization_depth"]["status"] == "ready"
    assert "完成 source-held-out" not in by_id["generalization_depth"]["next_action"]
    assert "source-held-out 缺失时" not in by_id["generalization_depth"]["paper_claim_boundary"]
    assert "provenance-blind" not in by_id["overall_innovation_depth"]["next_action"]
    assert "source-held-out 阻塞" not in by_id["overall_innovation_depth"]["next_action"]


def test_write_innovation_depth_stress_outputs_writes_files(tmp_path) -> None:
    """验证创新深度压力审计写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "innovation_depth_stress_test"
    rows = build_innovation_depth_stress_rows(_blueprint_rows(), _superiority_rows(), _mechanism_rows(), [])

    write_innovation_depth_stress_outputs(rows, output_dir)

    assert read_records(output_dir / "innovation_depth_stress_test.jsonl")
    assert (output_dir / "innovation_depth_stress_test.csv").exists()
    assert "# Innovation Depth Stress Test" in (output_dir / "innovation_depth_stress_test.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "innovation_depth_stress_test_summary.jsonl")[0]
    assert summary["stress_count"] == 6
    assert summary["overall_innovation_depth_status"] == "blocked"
    assert summary["q2_b_innovation_claim_allowed"] is False


def test_build_innovation_depth_stress_from_paths_skips_missing_optional_inputs(tmp_path) -> None:
    """验证缺失可选输入不阻断创新深度压力审计。"""
    blueprint = tmp_path / "model_innovation_blueprint.jsonl"
    superiority = tmp_path / "model_superiority_audit.jsonl"
    mechanism = tmp_path / "mechanism_error_evidence.jsonl"
    missing_sensitivity = tmp_path / "missing_sensitivity.jsonl"
    _write_jsonl(blueprint, _blueprint_rows())
    _write_jsonl(superiority, _superiority_rows())
    _write_jsonl(mechanism, _mechanism_rows())

    rows = build_innovation_depth_stress_rows_from_paths(
        model_innovation_blueprint_paths=[blueprint],
        model_superiority_audit_paths=[superiority],
        mechanism_evidence_paths=[mechanism],
        mechanism_sensitivity_paths=[missing_sensitivity],
        mechanism_triangulation_summary_paths=[],
        mechanism_triangulation_sensitivity_summary_paths=[],
    )

    assert {row["stress_id"] for row in rows} >= {"mechanism_explanation_depth", "overall_innovation_depth"}


def test_build_innovation_depth_stress_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出创新深度压力审计。"""
    blueprint = tmp_path / "model_innovation_blueprint.jsonl"
    superiority = tmp_path / "model_superiority_audit.jsonl"
    mechanism = tmp_path / "mechanism_error_evidence.jsonl"
    output_dir = tmp_path / "innovation_depth_stress_test"
    _write_jsonl(blueprint, _blueprint_rows())
    _write_jsonl(superiority, _superiority_rows())
    _write_jsonl(mechanism, _mechanism_rows())

    command_build_innovation_depth_stress_test(
        Namespace(
            model_innovation_blueprints=[str(blueprint)],
            model_superiority_audits=[str(superiority)],
            mechanism_evidence=[str(mechanism)],
            mechanism_sensitivity=[],
            mechanism_triangulation_summaries=[],
            mechanism_triangulation_sensitivity_summaries=[],
            split_readiness_audits=[],
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "innovation_depth_stress_test.jsonl")
    assert (output_dir / "innovation_depth_stress_test.md").exists()


def test_cli_includes_build_innovation_depth_stress_test_command() -> None:
    """验证 CLI 暴露 build-innovation-depth-stress-test 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-innovation-depth-stress-test",
            "--model-innovation-blueprints",
            "outputs/model_innovation_blueprint_fixture/model_innovation_blueprint.jsonl",
            "--model-superiority-audits",
            "outputs/model_superiority_audit_fixture/model_superiority_audit.jsonl",
            "--mechanism-evidence",
            "outputs/mechanism_error_evidence_fixture/scincl/mechanism_error_evidence.jsonl",
            "--mechanism-sensitivity",
            "outputs/mechanism_error_evidence_fixture/scincl/mechanism_threshold_sensitivity.jsonl",
            "--mechanism-triangulation-summaries",
            "outputs/mechanism_triangulation_audit_fixture/mechanism_triangulation_summary.jsonl",
            "--mechanism-triangulation-sensitivity-summaries",
            "outputs/mechanism_triangulation_sensitivity_fixture/mechanism_triangulation_sensitivity_summary.jsonl",
            "--split-readiness-audits",
            "outputs/open_v3_split_readiness_multitopic_silver_patch/open_v3_split_readiness.jsonl",
            "--output-dir",
            "outputs/innovation_depth_stress_test_fixture",
        ]
    )

    assert args.command == "build-innovation-depth-stress-test"
    assert args.model_superiority_audits == ["outputs/model_superiority_audit_fixture/model_superiority_audit.jsonl"]
    assert args.mechanism_triangulation_summaries == ["outputs/mechanism_triangulation_audit_fixture/mechanism_triangulation_summary.jsonl"]
    assert args.mechanism_triangulation_sensitivity_summaries == [
        "outputs/mechanism_triangulation_sensitivity_fixture/mechanism_triangulation_sensitivity_summary.jsonl"
    ]
    assert args.split_readiness_audits == ["outputs/open_v3_split_readiness_multitopic_silver_patch/open_v3_split_readiness.jsonl"]
    assert args.func == command_build_innovation_depth_stress_test
