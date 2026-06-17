"""测试安全论文草稿骨架。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_manuscript_draft_skeleton
from iad_sieve.evaluation.manuscript_draft_skeleton import build_manuscript_draft_rows, write_manuscript_draft_outputs
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


def test_build_manuscript_draft_rows_blocks_overclaiming_in_abstract_and_conclusion() -> None:
    """验证 blocked 投稿门禁下摘要和结论必须禁止过度主张。"""
    evidence_rows = [
        {
            "claim_id": "identity_agenda_risk_modeling",
            "manuscript_section": "Introduction/Method",
            "writing_action": "write_as_main_claim",
            "safe_wording": "可写为：提出 identity-agenda 风险建模框架。",
        },
        {
            "claim_id": "q2_b_ready",
            "manuscript_section": "Conclusion",
            "writing_action": "do_not_write",
            "safe_wording": "不能写已达到二区。",
        },
    ]
    submission_summary_rows = [{"submission_decision": "blocked", "blocking_reasons": ["q2_b_ready"]}]

    rows = build_manuscript_draft_rows(evidence_rows, submission_summary_rows)
    by_section = {row["section_id"]: row for row in rows}

    assert by_section["abstract"]["section_status"] == "restricted"
    assert "q2_b_ready" in by_section["abstract"]["forbidden_claim_ids"]
    assert "identity-agenda" in by_section["method"]["must_include"]
    assert by_section["conclusion"]["section_status"] == "restricted"
    assert "不得写成已经达到二区/B类完成状态" in by_section["conclusion"]["writing_guardrail"]


def test_write_manuscript_draft_outputs_writes_jsonl_markdown_and_summary(tmp_path) -> None:
    """验证草稿骨架写出 JSONL、Markdown 和 summary。"""
    rows = [
        {
            "section_id": "abstract",
            "section_title": "Abstract",
            "section_status": "restricted",
            "must_include": "只写方法贡献。",
            "must_avoid": "不得写 SOTA。",
            "allowed_claim_ids": ["identity_agenda_risk_modeling"],
            "forbidden_claim_ids": ["q2_b_ready"],
            "writing_guardrail": "不得写成已经达到二区/B类完成状态。",
        }
    ]
    output_dir = tmp_path / "draft_skeleton"

    write_manuscript_draft_outputs(rows, output_dir)

    assert read_records(output_dir / "manuscript_draft_skeleton.jsonl")[0]["section_id"] == "abstract"
    assert "# Manuscript Draft Skeleton" in (output_dir / "manuscript_draft_skeleton.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "manuscript_draft_skeleton_summary.jsonl")[0]
    assert summary["restricted_section_count"] == 1


def test_build_manuscript_draft_skeleton_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出安全论文草稿骨架。"""
    evidence = tmp_path / "manuscript_evidence_matrix.jsonl"
    submission = tmp_path / "submission_gate_audit_summary.jsonl"
    output_dir = tmp_path / "draft_skeleton"
    _write_jsonl(evidence, [{"claim_id": "q2_b_ready", "writing_action": "do_not_write", "safe_wording": "不能写已达到二区。"}])
    _write_jsonl(submission, [{"submission_decision": "blocked", "blocking_reasons": ["q2_b_ready"]}])

    command_build_manuscript_draft_skeleton(
        Namespace(
            manuscript_evidence=[str(evidence)],
            submission_summaries=[str(submission)],
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "manuscript_draft_skeleton.jsonl")
    assert (output_dir / "manuscript_draft_skeleton.md").exists()


def test_cli_includes_build_manuscript_draft_skeleton_command() -> None:
    """验证 CLI 暴露 build-manuscript-draft-skeleton 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-manuscript-draft-skeleton",
            "--manuscript-evidence",
            "outputs/manuscript_evidence_matrix_fixture/manuscript_evidence_matrix.jsonl",
            "--submission-summaries",
            "outputs/submission_gate_audit_fixture/submission_gate_audit_summary.jsonl",
            "--output-dir",
            "outputs/manuscript_draft_skeleton_fixture",
        ]
    )

    assert args.command == "build-manuscript-draft-skeleton"
    assert args.manuscript_evidence == ["outputs/manuscript_evidence_matrix_fixture/manuscript_evidence_matrix.jsonl"]
