"""测试稿件证据矩阵。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_manuscript_evidence_matrix
from iad_sieve.evaluation.manuscript_evidence_matrix import build_manuscript_evidence_rows, write_manuscript_evidence_outputs
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


def test_build_manuscript_evidence_rows_maps_supported_and_forbidden_claims() -> None:
    """验证稿件证据矩阵能区分可写主张和禁止主张。"""
    claim_rows = [
        {
            "claim_id": "identity_agenda_risk_modeling",
            "claim_status": "supported",
            "allowed_wording_level": "main_claim",
            "safe_wording": "可写为：本文提出 identity-agenda 分离的风险建模框架。",
            "available_evidence": ["same_work_gold", "iad_ablation"],
        },
        {
            "claim_id": "state_of_the_art_superiority",
            "claim_status": "forbidden",
            "allowed_wording_level": "do_not_claim",
            "safe_wording": "当前只能写强 baseline 框架已接入。",
            "missing_evidence": ["llm_api_model"],
        },
    ]
    depth_rows = [{"dimension_id": "advanced_baseline", "depth_status": "not_ready", "reviewer_risk_level": "high"}]
    submission_rows = [{"submission_gate_id": "overall_submission_gate", "decision": "blocked", "blocking_reasons": ["advanced_baseline"]}]

    rows = build_manuscript_evidence_rows(claim_rows, depth_rows, submission_rows)
    by_claim = {row["claim_id"]: row for row in rows}

    assert by_claim["identity_agenda_risk_modeling"]["manuscript_section"] == "Introduction/Method"
    assert by_claim["identity_agenda_risk_modeling"]["writing_action"] == "write_as_main_claim"
    assert by_claim["identity_agenda_risk_modeling"]["evidence_strength"] == "strong"
    assert by_claim["state_of_the_art_superiority"]["writing_action"] == "do_not_write"
    assert "advanced_baseline" in by_claim["state_of_the_art_superiority"]["blocking_reasons"]


def test_write_manuscript_evidence_outputs_writes_jsonl_csv_markdown_and_summary(tmp_path) -> None:
    """验证稿件证据矩阵写出 JSONL、CSV、Markdown 和 summary。"""
    rows = [
        {
            "claim_id": "identity_agenda_risk_modeling",
            "manuscript_section": "Introduction/Method",
            "writing_action": "write_as_main_claim",
            "evidence_strength": "strong",
            "safe_wording": "可写为：提出风险建模框架。",
            "blocking_reasons": [],
        },
        {
            "claim_id": "q2_b_ready",
            "manuscript_section": "Conclusion",
            "writing_action": "do_not_write",
            "evidence_strength": "blocked",
            "safe_wording": "不能写已达到二区。",
            "blocking_reasons": ["overall_submission_gate"],
        },
    ]
    output_dir = tmp_path / "manuscript_evidence"

    write_manuscript_evidence_outputs(rows, output_dir)

    assert read_records(output_dir / "manuscript_evidence_matrix.jsonl")[0]["claim_id"] == "identity_agenda_risk_modeling"
    assert (output_dir / "manuscript_evidence_matrix.csv").exists()
    assert "# Manuscript Evidence Matrix" in (output_dir / "manuscript_evidence_matrix.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "manuscript_evidence_summary.jsonl")[0]
    assert summary["write_as_main_claim_count"] == 1
    assert summary["do_not_write_count"] == 1


def test_build_manuscript_evidence_matrix_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出稿件证据矩阵。"""
    claim = tmp_path / "paper_claim_audit.jsonl"
    depth = tmp_path / "research_depth_audit.jsonl"
    submission = tmp_path / "submission_gate_audit.jsonl"
    output_dir = tmp_path / "manuscript_evidence"
    _write_jsonl(claim, [{"claim_id": "q2_b_ready", "claim_status": "forbidden", "allowed_wording_level": "do_not_claim", "safe_wording": "不能写已达到二区。"}])
    _write_jsonl(depth, [{"dimension_id": "advanced_baseline", "depth_status": "not_ready", "reviewer_risk_level": "high"}])
    _write_jsonl(submission, [{"submission_gate_id": "overall_submission_gate", "decision": "blocked", "blocking_reasons": ["q2_b_ready"]}])

    command_build_manuscript_evidence_matrix(
        Namespace(
            claim_audits=[str(claim)],
            research_depth_audits=[str(depth)],
            submission_gate_audits=[str(submission)],
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "manuscript_evidence_matrix.jsonl")[0]["writing_action"] == "do_not_write"
    assert (output_dir / "manuscript_evidence_matrix.md").exists()


def test_cli_includes_build_manuscript_evidence_matrix_command() -> None:
    """验证 CLI 暴露 build-manuscript-evidence-matrix 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-manuscript-evidence-matrix",
            "--claim-audits",
            "outputs/paper_claim_audit_fixture/paper_claim_audit.jsonl",
            "--research-depth-audits",
            "outputs/research_depth_audit_fixture/research_depth_audit.jsonl",
            "--submission-gate-audits",
            "outputs/submission_gate_audit_fixture/submission_gate_audit.jsonl",
            "--output-dir",
            "outputs/manuscript_evidence_matrix_fixture",
        ]
    )

    assert args.command == "build-manuscript-evidence-matrix"
    assert args.submission_gate_audits == ["outputs/submission_gate_audit_fixture/submission_gate_audit.jsonl"]
