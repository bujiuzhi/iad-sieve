"""测试无人工标注阶段协议。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_no_annotation_protocol
from iad_sieve.evaluation.no_annotation_protocol import build_no_annotation_protocol_rows, write_no_annotation_protocol_outputs
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


def test_build_no_annotation_protocol_rows_keeps_human_gold_deferred() -> None:
    """验证无人工标注协议将人工 gold 后置且锁定远程强模型主张。"""
    public_rows = [
        {"dimension_id": "gold_scale", "audit_status": "defensible"},
        {"dimension_id": "split_coverage", "audit_status": "defensible"},
        {"dimension_id": "human_audit_absence", "audit_status": "deferred_enhancement"},
    ]
    roadmap_rows = [
        {
            "phase_id": "p0_remote_connection_and_secret",
            "status": "blocked",
            "human_annotation_required_now": False,
            "paper_claim_boundary": "不能声称远程实验完成。",
        },
        {
            "phase_id": "p5_optional_human_gold_enhancement",
            "status": "deferred",
            "human_annotation_required_now": False,
            "required_actions": "后续 500-1,000 pair 双标。",
        },
    ]
    reviewer_rows = [{"iteration_id": "r0_remote_reproducibility", "severity": "critical"}]
    remote_rows = [
        {"request_id": "connection:remote_host", "request_type": "connection_field", "field_name": "remote_host", "status": "waiting_for_user"},
        {"request_id": "secret:OPENAI_API_KEY", "request_type": "secret_configuration", "field_name": "OPENAI_API_KEY", "status": "waiting_for_secure_configuration"},
    ]

    rows = build_no_annotation_protocol_rows(public_rows, roadmap_rows, reviewer_rows, remote_rows)
    by_id = {row["protocol_id"]: row for row in rows}

    assert by_id["public_data_label_contract"]["status"] == "defensible"
    assert by_id["human_gold_deferred_boundary"]["status"] == "deferred_enhancement"
    assert by_id["human_gold_deferred_boundary"]["human_annotation_required_now"] is False
    assert "不得声称已有人工 gold" in by_id["human_gold_deferred_boundary"]["forbidden_claim"]
    assert by_id["remote_strong_model_dependency"]["status"] == "blocked_remote_required"
    assert by_id["q2b_claim_lockdown"]["status"] == "claim_lockdown_required"
    assert "不得声称已经达到二区/B 类" in by_id["q2b_claim_lockdown"]["forbidden_claim"]


def test_write_no_annotation_protocol_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证协议产物写出 JSONL、CSV、Markdown 和摘要。"""
    rows = [
        {
            "protocol_id": "human_gold_deferred_boundary",
            "protocol_dimension": "人工 gold 后置边界",
            "status": "deferred_enhancement",
            "reviewer_risk_level": "medium",
            "current_evidence": "human_annotation_required_now=False",
            "allowed_claim": "人工 gold 是后续增强。",
            "forbidden_claim": "不得声称已有人工 gold。",
            "required_action": "后续双标。",
            "acceptance_evidence": "Kappa >= 0.70。",
            "human_annotation_required_now": False,
            "remote_required": False,
            "source_ids": ["human_audit_absence"],
        },
        {
            "protocol_id": "remote_strong_model_dependency",
            "protocol_dimension": "强模型远程依赖",
            "status": "blocked_remote_required",
            "reviewer_risk_level": "high",
            "current_evidence": "waiting_remote_inputs=2",
            "allowed_claim": "只能写计划。",
            "forbidden_claim": "不得写强模型完成。",
            "required_action": "补远程连接。",
            "acceptance_evidence": "输出验收通过。",
            "human_annotation_required_now": False,
            "remote_required": True,
            "source_ids": ["connection:remote_host"],
        },
    ]
    output_dir = tmp_path / "no_annotation_protocol"

    write_no_annotation_protocol_outputs(rows, output_dir)

    assert read_records(output_dir / "no_annotation_protocol.jsonl")[0]["protocol_id"] == "human_gold_deferred_boundary"
    assert (output_dir / "no_annotation_protocol.csv").exists()
    assert "# No Annotation Stage Protocol" in (output_dir / "no_annotation_protocol.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "no_annotation_protocol_summary.jsonl")[0]
    assert summary["protocol_item_count"] == 2
    assert summary["blocked_annotation_count"] == 0
    assert summary["blocked_remote_count"] == 1
    assert summary["human_annotation_required_now"] is False
    assert summary["no_annotation_stage_allowed"] is True
    assert summary["q2_b_ready_under_no_annotation_strategy"] is False


def test_build_no_annotation_protocol_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出无人工标注阶段协议。"""
    public_data = tmp_path / "public_data_validity_audit.jsonl"
    roadmap = tmp_path / "q2b_upgrade_roadmap.jsonl"
    output_dir = tmp_path / "no_annotation_protocol"
    _write_jsonl(public_data, [{"dimension_id": "human_audit_absence", "audit_status": "deferred_enhancement"}])
    _write_jsonl(roadmap, [{"phase_id": "p5_optional_human_gold_enhancement", "status": "deferred", "human_annotation_required_now": False}])

    command_build_no_annotation_protocol(
        Namespace(
            public_data_validity=[str(public_data)],
            q2b_roadmap=str(roadmap),
            reviewer_iteration=None,
            remote_input_request=None,
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "no_annotation_protocol_summary.jsonl").exists()
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-no-annotation-protocol",
            "--public-data-validity",
            str(public_data),
            "--q2b-roadmap",
            str(roadmap),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_no_annotation_protocol
