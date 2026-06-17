"""测试相关工作新颖性审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_prior_art_novelty_audit
from iad_sieve.evaluation.prior_art_novelty_audit import (
    build_prior_art_novelty_rows,
    build_prior_art_novelty_rows_from_paths,
    write_prior_art_novelty_outputs,
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


def _novelty_rows() -> list[dict]:
    """构造创新可证伪矩阵测试记录。

    参数:
        无。

    返回:
        测试记录列表。
    """
    return [
        {"contribution_id": "risk_decomposition_vs_single_space", "status": "ready"},
        {"contribution_id": "strong_model_superiority_control", "status": "conditional"},
        {"contribution_id": "encoder_and_provenance_validity", "status": "blocked"},
        {"contribution_id": "source_heldout_generalization_boundary", "status": "blocked"},
        {"contribution_id": "no_annotation_claim_boundary", "status": "ready"},
    ]


def test_build_prior_art_novelty_rows_blocks_unresolved_strong_prior_art() -> None:
    """验证强相关工作未闭环时不能声称创新充分。"""
    rows = build_prior_art_novelty_rows(
        novelty_rows=_novelty_rows(),
        advanced_model_summary={"missing_required_count": 10, "ready_api_model_count": 0},
        snapshot_date="2026-06-13",
    )
    by_id = {row["prior_art_family_id"]: row for row in rows}

    assert by_id["scientific_document_representation"]["status"] == "blocked"
    assert by_id["plm_entity_matching"]["status"] == "blocked"
    assert by_id["llm_entity_matching"]["status"] == "blocked"
    assert by_id["open_bibliographic_graph"]["status"] == "conditional"
    assert by_id["iad_problem_formulation"]["status"] == "ready"
    assert by_id["scientific_document_representation"]["duplicate_work_found"] is False
    assert "SPECTER2" in by_id["scientific_document_representation"]["must_compare_against"]
    assert "Topic Is Not Agenda embedding audit" in by_id["scientific_document_representation"]["must_compare_against"]
    assert "https://arxiv.org/abs/2605.07158" in by_id["scientific_document_representation"]["external_sources"]
    assert "ComEM interaction-aware LLM EM" in by_id["llm_entity_matching"]["must_compare_against"]
    assert "https://arxiv.org/abs/2405.16884" in by_id["llm_entity_matching"]["external_sources"]
    assert "https://arxiv.org/abs/2409.08185" in by_id["llm_entity_matching"]["external_sources"]
    assert "DBLPLink / DBLPLink 2.0 scholarly KG entity linking" in by_id["open_bibliographic_graph"]["must_compare_against"]
    assert "https://arxiv.org/abs/2507.22811" in by_id["open_bibliographic_graph"]["external_sources"]
    assert "不能写成没有相似工作" in by_id["iad_problem_formulation"]["paper_claim_boundary"]


def test_build_prior_art_novelty_rows_uses_ready_actions_for_ready_scientific_representation() -> None:
    """验证科学文献表示证据 ready 时不再要求补齐已完成控制。"""
    novelty_rows = [
        {"contribution_id": "risk_decomposition_vs_single_space", "status": "ready"},
        {"contribution_id": "strong_model_superiority_control", "status": "blocked"},
        {"contribution_id": "encoder_and_provenance_validity", "status": "ready"},
        {"contribution_id": "no_annotation_claim_boundary", "status": "ready"},
    ]

    rows = build_prior_art_novelty_rows(
        novelty_rows=novelty_rows,
        advanced_model_summary={"missing_required_count": 2, "ready_api_model_count": 0},
        snapshot_date="2026-06-13",
    )
    by_id = {row["prior_art_family_id"]: row for row in rows}
    scientific_row = by_id["scientific_document_representation"]

    assert scientific_row["status"] == "ready"
    assert "补齐 SPECTER2" not in scientific_row["required_action"]
    assert "未通过前" not in scientific_row["paper_claim_boundary"]


def test_build_prior_art_novelty_rows_does_not_block_plm_family_on_llm_only_gap() -> None:
    """验证 LLM 缺口不误伤已完成的 PLM entity matching 相关工作边界。"""
    novelty_rows = [
        {"contribution_id": "risk_decomposition_vs_single_space", "status": "ready"},
        {"contribution_id": "strong_model_superiority_control", "status": "conditional"},
        {"contribution_id": "encoder_and_provenance_validity", "status": "ready"},
        {"contribution_id": "no_annotation_claim_boundary", "status": "ready"},
    ]

    rows = build_prior_art_novelty_rows(
        novelty_rows=novelty_rows,
        advanced_model_summary={
            "missing_required_count": 2,
            "missing_plm_required_count": 0,
            "ready_plm_model_count": 3,
            "missing_llm_required_count": 2,
            "ready_api_model_count": 0,
        },
        snapshot_date="2026-06-13",
    )
    by_id = {row["prior_art_family_id"]: row for row in rows}

    assert by_id["plm_entity_matching"]["status"] == "ready"
    assert by_id["llm_entity_matching"]["status"] == "blocked"
    assert "missing_plm_required_count=0" in by_id["plm_entity_matching"]["current_evidence"]


def test_build_prior_art_novelty_rows_accepts_local_llm_actual_model() -> None:
    """验证本地 LLM actual_model 可关闭 LLM entity matching 相关工作边界。"""
    novelty_rows = [
        {"contribution_id": "risk_decomposition_vs_single_space", "status": "ready"},
        {"contribution_id": "strong_model_superiority_control", "status": "ready"},
        {"contribution_id": "encoder_and_provenance_validity", "status": "ready"},
        {"contribution_id": "no_annotation_claim_boundary", "status": "ready"},
    ]

    rows = build_prior_art_novelty_rows(
        novelty_rows=novelty_rows,
        advanced_model_summary={
            "missing_required_count": 0,
            "missing_llm_required_count": 0,
            "ready_api_model_count": 0,
            "ready_llm_model_count": 1,
            "missing_plm_required_count": 0,
            "ready_plm_model_count": 3,
        },
        snapshot_date="2026-06-13",
    )
    by_id = {row["prior_art_family_id"]: row for row in rows}

    assert by_id["llm_entity_matching"]["status"] == "ready"
    assert "ready_llm_model_count=1" in by_id["llm_entity_matching"]["current_evidence"]


def test_write_prior_art_novelty_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证相关工作新颖性审计写出 JSONL、CSV、Markdown 和摘要。"""
    rows = build_prior_art_novelty_rows(
        novelty_rows=_novelty_rows(),
        advanced_model_summary={"missing_required_count": 10, "ready_api_model_count": 0},
        snapshot_date="2026-06-13",
    )
    output_dir = tmp_path / "prior_art_novelty_audit"

    write_prior_art_novelty_outputs(rows, output_dir)

    assert read_records(output_dir / "prior_art_novelty_audit.jsonl")
    assert (output_dir / "prior_art_novelty_audit.csv").exists()
    assert "# Prior Art Novelty Audit" in (output_dir / "prior_art_novelty_audit.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "prior_art_novelty_audit_summary.jsonl")[0]
    assert summary["prior_art_family_count"] == 5
    assert summary["duplicate_work_found"] is False
    assert summary["blocked_prior_art_family_count"] == 3
    assert summary["q2b_prior_art_position_defensible"] is False
    assert summary["highest_priority_blocker"] == "scientific_document_representation"


def test_build_prior_art_novelty_from_paths_and_cli_write_outputs(tmp_path) -> None:
    """验证文件输入和 CLI 均可生成相关工作新颖性审计。"""
    novelty = tmp_path / "novelty_falsification_matrix.jsonl"
    advanced_model = tmp_path / "advanced_model_evidence_summary.jsonl"
    output_dir = tmp_path / "prior_art_novelty_audit"
    _write_jsonl(novelty, _novelty_rows())
    _write_jsonl(advanced_model, [{"missing_required_count": 10, "ready_api_model_count": 0}])

    rows = build_prior_art_novelty_rows_from_paths(
        novelty_matrix_paths=[novelty],
        advanced_model_summary_path=advanced_model,
        snapshot_date="2026-06-13",
    )
    assert len(rows) == 5

    command_build_prior_art_novelty_audit(
        Namespace(
            novelty_matrices=[str(novelty)],
            advanced_model_summary=str(advanced_model),
            snapshot_date="2026-06-13",
            output_dir=str(output_dir),
        )
    )
    assert read_records(output_dir / "prior_art_novelty_audit_summary.jsonl")[0]["blocked_prior_art_family_count"] == 3

    parser = build_parser()
    args = parser.parse_args(
        [
            "build-prior-art-novelty-audit",
            "--novelty-matrices",
            str(novelty),
            "--advanced-model-summary",
            str(advanced_model),
            "--snapshot-date",
            "2026-06-13",
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_prior_art_novelty_audit
