"""测试论文主张审计。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_paper_claim_audit
from iad_sieve.evaluation.paper_claim_audit import build_paper_claim_audit_rows, write_paper_claim_audit_outputs
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


def test_build_paper_claim_audit_rows_marks_supported_mechanism_claim() -> None:
    """验证机制性贡献在证据层齐备时可作为 supported claim。"""
    rq_rows = [
        {"evidence_layer": "same_work_gold", "rq": "RQ1"},
        {"evidence_layer": "same_agenda_proxy", "rq": "RQ2"},
        {"evidence_layer": "agenda_non_identity_weak", "rq": "RQ2"},
        {"evidence_layer": "iad_ablation", "rq": "RQ3"},
        {"evidence_layer": "iad_bootstrap_confidence", "rq": "RQ4"},
    ]
    readiness_rows = [{"gate_id": "overall_q2_b_readiness", "status": "needs_evidence"}]
    dependency_rows = []

    rows = build_paper_claim_audit_rows(rq_rows, readiness_rows, dependency_rows)
    by_claim = {row["claim_id"]: row for row in rows}

    assert by_claim["identity_agenda_risk_modeling"]["claim_status"] == "supported"
    assert by_claim["identity_agenda_risk_modeling"]["allowed_wording_level"] == "main_claim"
    assert "same_work_gold" in by_claim["identity_agenda_risk_modeling"]["available_evidence"]


def test_build_paper_claim_audit_rows_forbids_q2_completion_and_sota_when_gates_missing() -> None:
    """验证 high readiness blocker 存在时禁止声称已达二区/B类或 SOTA。"""
    rq_rows = [{"evidence_layer": "external_baseline", "rq": "RQ1", "baseline_family": "representation", "execution_mode": "actual_model", "system": "scincl"}]
    readiness_rows = [
        {"gate_id": "overall_q2_b_readiness", "severity": "high", "status": "needs_evidence"},
        {"gate_id": "specter2_adapter_actual_model", "severity": "high", "status": "needs_evidence"},
        {"gate_id": "llm_pair_judge_api_model", "severity": "high", "status": "needs_evidence"},
    ]
    dependency_rows = [
        {"task_id": "run_specter2_adapter_baseline_open_v2", "root_blocker_statuses": ["blocked_remote_required"]},
        {"task_id": "run_llm_pair_judge_api_model_open_v2", "root_blocker_statuses": ["blocked_missing_secret"]},
    ]

    rows = build_paper_claim_audit_rows(rq_rows, readiness_rows, dependency_rows)
    by_claim = {row["claim_id"]: row for row in rows}

    assert by_claim["q2_b_ready"]["claim_status"] == "forbidden"
    assert by_claim["q2_b_ready"]["allowed_wording_level"] == "do_not_claim"
    assert by_claim["state_of_the_art_superiority"]["claim_status"] == "forbidden"
    assert "specter2_adapter_actual_model" in by_claim["state_of_the_art_superiority"]["blocking_gates"]
    assert "blocked_missing_secret" in by_claim["state_of_the_art_superiority"]["root_blocker_statuses"]


def test_build_paper_claim_audit_rows_does_not_reask_completed_specter2_for_sota() -> None:
    """验证 SPECTER2 已 ready 时 SOTA 安全表述只指向剩余缺口。"""
    rq_rows = [
        {"evidence_layer": "external_baseline", "rq": "RQ1", "baseline_family": "representation", "execution_mode": "actual_model", "system": "specter2_adapter_cosine"},
        {"evidence_layer": "external_baseline", "rq": "RQ1", "baseline_family": "entity_matching", "execution_mode": "actual_model", "system": "roberta_pair"},
    ]
    readiness_rows = [
        {"gate_id": "specter2_adapter_actual_model", "severity": "high", "status": "evidence_ready"},
        {"gate_id": "llm_pair_judge_api_model", "severity": "high", "status": "needs_evidence"},
        {"gate_id": "executed_strong_baselines", "severity": "high", "status": "needs_evidence"},
    ]
    dependency_rows = [{"task_id": "run_llm_pair_judge_api_model_open_v2", "root_blocker_statuses": ["blocked_missing_secret"]}]

    rows = build_paper_claim_audit_rows(rq_rows, readiness_rows, dependency_rows)
    by_claim = {row["claim_id"]: row for row in rows}

    assert "specter2_adapter_actual_model" not in by_claim["state_of_the_art_superiority"]["blocking_gates"]
    assert "SPECTER2 adapter 与 LLM" not in by_claim["state_of_the_art_superiority"]["safe_wording"]
    assert "LLM api_model" in by_claim["state_of_the_art_superiority"]["safe_wording"]


def test_build_paper_claim_audit_rows_marks_human_gold_as_future_work_when_only_plan_exists() -> None:
    """验证只有人工计划时不能写成人工 gold 已采集。"""
    rq_rows = [{"evidence_layer": "human_audit_plan", "rq": "RQ2"}]
    readiness_rows = [{"gate_id": "human_audit_plan", "status": "evidence_ready"}]
    dependency_rows = []

    rows = build_paper_claim_audit_rows(rq_rows, readiness_rows, dependency_rows)
    by_claim = {row["claim_id"]: row for row in rows}

    assert by_claim["human_gold_available"]["claim_status"] == "forbidden"
    assert by_claim["human_audit_future_enhancement"]["claim_status"] == "supported"
    assert by_claim["human_audit_future_enhancement"]["allowed_wording_level"] == "limitation_or_future_work"


def test_write_paper_claim_audit_outputs_writes_jsonl_csv_and_markdown(tmp_path) -> None:
    """验证论文主张审计写出 JSONL、CSV 和 Markdown。"""
    rows = [
        {
            "claim_id": "q2_b_ready",
            "claim_status": "forbidden",
            "allowed_wording_level": "do_not_claim",
            "claim_text": "当前已经达到二区/B类投稿完成度。",
            "available_evidence": [],
            "missing_evidence": ["overall_q2_b_readiness"],
            "blocking_gates": ["overall_q2_b_readiness"],
            "root_blocker_statuses": ["blocked_remote_required"],
            "safe_wording": "当前仍需补齐强 baseline 证据。",
            "reviewer_risk": "过度宣称会被直接质疑。",
        }
    ]
    output_dir = tmp_path / "paper_claim_audit"

    write_paper_claim_audit_outputs(rows, output_dir)

    assert read_records(output_dir / "paper_claim_audit.jsonl")[0]["claim_id"] == "q2_b_ready"
    assert (output_dir / "paper_claim_audit.csv").exists()
    assert "# Paper Claim Audit" in (output_dir / "paper_claim_audit.md").read_text(encoding="utf-8")


def test_build_paper_claim_audit_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出论文主张审计。"""
    rq_summary = tmp_path / "rq_summary.jsonl"
    readiness = tmp_path / "journal_readiness.jsonl"
    dependency = tmp_path / "experiment_dependency.jsonl"
    output_dir = tmp_path / "paper_claim_audit"
    _write_jsonl(rq_summary, [{"evidence_layer": "human_audit_plan", "rq": "RQ2"}])
    _write_jsonl(readiness, [{"gate_id": "overall_q2_b_readiness", "severity": "high", "status": "needs_evidence"}])
    _write_jsonl(dependency, [{"task_id": "run_encoder", "root_blocker_statuses": ["blocked_remote_required"]}])

    command_build_paper_claim_audit(
        Namespace(
            rq_summaries=[str(rq_summary)],
            readiness_reports=[str(readiness)],
            dependency_reports=[str(dependency)],
            output_dir=str(output_dir),
        )
    )

    assert read_records(output_dir / "paper_claim_audit.jsonl")
    assert (output_dir / "paper_claim_audit.md").exists()


def test_cli_includes_build_paper_claim_audit_command() -> None:
    """验证 CLI 暴露 build-paper-claim-audit 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-paper-claim-audit",
            "--rq-summaries",
            "outputs/iad_paper_report_fixture/rq_summary.jsonl",
            "--readiness-reports",
            "outputs/journal_readiness_fixture/journal_readiness.jsonl",
            "--dependency-reports",
            "outputs/experiment_dependency_fixture/experiment_dependency.jsonl",
            "--output-dir",
            "outputs/paper_claim_audit_fixture",
        ]
    )

    assert args.command == "build-paper-claim-audit"
    assert args.dependency_reports == ["outputs/experiment_dependency_fixture/experiment_dependency.jsonl"]
