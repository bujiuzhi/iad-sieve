"""测试审稿威胁模型。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_reviewer_threat_model
from iad_sieve.evaluation.reviewer_threat_model import (
    build_reviewer_threat_model_rows,
    build_reviewer_threat_model_rows_from_paths,
    write_reviewer_threat_model_outputs,
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


def _q2b_rows() -> list[dict]:
    """构造 Q2/B gate 测试记录。

    参数:
        无。

    返回:
        Q2/B gate 记录。
    """
    return [
        {
            "gate_id": "remote_reproducibility_acceptance",
            "priority": 0,
            "status": "blocked",
            "reviewer_failure_mode": "强模型只停留在计划层。",
            "required_action": "补齐远程连接并回传输出。",
            "acceptance_evidence": "远程输出通过验收。",
            "paper_claim_boundary": "不得写强模型已远程复现。",
        },
        {
            "gate_id": "innovation_depth_acceptance",
            "priority": 3,
            "status": "blocked",
            "reviewer_failure_mode": "创新像工程组合。",
            "required_action": "补齐创新深度压力测试。",
            "acceptance_evidence": "创新压力测试 ready。",
            "paper_claim_boundary": "不得写创新深度已满足。",
        },
    ]


def test_build_reviewer_threat_model_rows_prioritizes_rejection_risks() -> None:
    """验证审稿威胁模型聚合 gate、创新和相似工作阻塞证据。"""
    rows = build_reviewer_threat_model_rows(
        q2b_acceptance_rows=_q2b_rows(),
        q2b_experiment_optimizer_rows=[
            {
                "gate_id": "remote_reproducibility_acceptance",
                "next_experiment": "先运行主轨道强模型。",
                "required_connection_fields": ["remote_host"],
                "required_secret_names": ["OPENAI_API_KEY"],
                "primary_track_required_secret_names": [],
                "deferred_secret_names": ["OPENAI_API_KEY"],
                "primary_track_can_start_without_deferred_secrets": True,
            }
        ],
        model_innovation_blueprint_rows=[
            {
                "blueprint_id": "specter2_encoder_stability",
                "status": "blocked",
                "required_systems": ["specter2_adapter_cosine_open_v2"],
                "reviewer_risk_level": "high",
            }
        ],
        innovation_depth_rows=[
            {
                "stress_id": "overall_innovation_depth",
                "status": "blocked",
                "reviewer_attack": "审稿人会质疑创新是否只是工程组合。",
                "blocking_reasons": ["missing_strong_comparison"],
            }
        ],
        novelty_rows=[
            {
                "contribution_id": "encoder_and_provenance_validity",
                "status": "blocked",
                "required_controls": ["iad_model_feature_guard"],
                "reviewer_null_hypothesis": "结果依赖来源捷径。",
            }
        ],
        prior_art_rows=[
            {
                "prior_art_family_id": "scientific_document_representation",
                "status": "blocked",
                "must_compare_against": ["SPECTER2", "SciNCL"],
                "reviewer_attack": "已有科学文献表示可能覆盖该问题。",
            }
        ],
        reviewer_iteration_rows=[],
    )

    by_id = {row["threat_id"]: row for row in rows}
    assert rows[0]["threat_id"] == "threat_remote_reproducibility_acceptance"
    assert rows[0]["severity"] == "critical"
    assert "先运行主轨道强模型" in rows[0]["next_experiment"]
    assert "remote_host" in rows[0]["blocked_evidence"]
    assert "OPENAI_API_KEY" not in rows[0]["blocked_evidence"]
    assert "missing_required_secret:OPENAI_API_KEY" not in rows[0]["blocked_evidence"]
    assert rows[0]["immediate_blocker_type"] == "external_remote_connection"
    assert rows[0]["immediate_external_inputs"] == ["remote_host"]
    assert rows[0]["deferred_not_primary_blockers"] == ["OPENAI_API_KEY"]
    assert "先运行主轨道强模型" in rows[0]["first_unblocked_experiment"]
    assert by_id["threat_innovation_depth_acceptance"]["severity"] == "high"
    assert "SPECTER2" in by_id["threat_innovation_depth_acceptance"]["must_compare_against"]
    assert "missing_strong_comparison" in by_id["threat_innovation_depth_acceptance"]["blocked_evidence"]


def test_build_reviewer_threat_model_rows_deduplicates_chinese_fragments() -> None:
    """验证中文分号和换行分隔的审稿文本会被拆分去重。"""
    rows = build_reviewer_threat_model_rows(
        q2b_acceptance_rows=[
            {
                "gate_id": "innovation_depth_acceptance",
                "priority": 7,
                "status": "blocked",
                "reviewer_failure_mode": "主张越界。；主张越界。",
                "required_action": "压缩论文主张。\n压缩论文主张。；保留限制。",
                "acceptance_evidence": "边界表述通过。",
                "paper_claim_boundary": "不得写已满足二区/B类。；不得写已满足二区/B类。；只能写待验证。",
            }
        ],
        q2b_experiment_optimizer_rows=[
            {
                "gate_id": "innovation_depth_acceptance",
                "paper_claim_boundary": "只能写待验证。；不得写已满足二区/B类。",
            }
        ],
        model_innovation_blueprint_rows=[],
        innovation_depth_rows=[
            {
                "stress_id": "overall_innovation_depth",
                "status": "blocked",
                "reviewer_attack": "主张越界。；创新深度不足。",
            }
        ],
        novelty_rows=[],
        prior_art_rows=[],
        reviewer_iteration_rows=[],
    )

    row = rows[0]
    assert row["reviewer_attack"] == "主张越界。；创新深度不足。"
    assert row["next_experiment"] == "压缩论文主张。；保留限制。"
    assert row["paper_claim_boundary"] == "不得写已满足二区/B类。；只能写待验证。"


def test_build_reviewer_threat_model_rows_filters_stale_connection_actions() -> None:
    """验证连接字段已齐备时威胁模型不保留补连接动作。"""
    rows = build_reviewer_threat_model_rows(
        q2b_acceptance_rows=[
            {
                "gate_id": "remote_reproducibility_acceptance",
                "priority": 0,
                "status": "blocked",
                "reviewer_failure_mode": "强模型未闭环。",
                "required_action": "补齐远程连接、运行 stage 脚本。",
                "acceptance_evidence": "远程输出通过验收。",
                "paper_claim_boundary": "不得写强模型完成。",
            }
        ],
        q2b_experiment_optimizer_rows=[
            {
                "gate_id": "remote_reproducibility_acceptance",
                "next_experiment": "主轨道连接字段已齐备。；补齐未映射模型任务。",
                "required_connection_fields": [],
                "required_secret_names": ["OPENAI_API_KEY"],
                "primary_track_required_secret_names": [],
                "deferred_secret_names": ["OPENAI_API_KEY"],
                "primary_track_can_start_without_deferred_secrets": True,
            }
        ],
        model_innovation_blueprint_rows=[],
        innovation_depth_rows=[],
        novelty_rows=[],
        prior_art_rows=[],
        reviewer_iteration_rows=[],
    )
    row = rows[0]

    assert "补齐远程连接" not in row["next_experiment"]
    assert "补齐未映射模型任务" in row["next_experiment"]


def test_write_reviewer_threat_model_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证审稿威胁模型写出 JSONL、CSV、Markdown 和摘要。"""
    output_dir = tmp_path / "reviewer_threat_model"
    rows = build_reviewer_threat_model_rows(
        q2b_acceptance_rows=_q2b_rows(),
        q2b_experiment_optimizer_rows=[],
        model_innovation_blueprint_rows=[],
        innovation_depth_rows=[],
        novelty_rows=[],
        prior_art_rows=[],
        reviewer_iteration_rows=[],
    )

    write_reviewer_threat_model_outputs(rows, output_dir)

    assert read_records(output_dir / "reviewer_threat_model.jsonl")
    assert (output_dir / "reviewer_threat_model.csv").exists()
    assert "# Reviewer Threat Model" in (output_dir / "reviewer_threat_model.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "reviewer_threat_model_summary.jsonl")[0]
    assert summary["threat_count"] == 2
    assert summary["highest_priority_threat"] == "threat_remote_reproducibility_acceptance"
    assert summary["highest_priority_immediate_blocker_type"] == "claim_gate_closure"
    assert summary["q2b_reviewer_threats_closed"] is False


def test_build_reviewer_threat_model_from_paths_and_cli(tmp_path) -> None:
    """验证文件输入和 CLI 可生成审稿威胁模型。"""
    q2b = tmp_path / "q2b_acceptance_rubric.jsonl"
    optimizer = tmp_path / "q2b_experiment_optimizer.jsonl"
    blueprint = tmp_path / "model_innovation_blueprint.jsonl"
    innovation = tmp_path / "innovation_depth_stress_test.jsonl"
    novelty = tmp_path / "novelty_falsification_matrix.jsonl"
    prior_art = tmp_path / "prior_art_novelty_audit.jsonl"
    reviewer = tmp_path / "reviewer_iteration_audit.jsonl"
    output_dir = tmp_path / "reviewer_threat_model"
    _write_jsonl(q2b, _q2b_rows())
    _write_jsonl(optimizer, [{"gate_id": "remote_reproducibility_acceptance", "next_experiment": "补齐连接。"}])
    _write_jsonl(blueprint, [])
    _write_jsonl(innovation, [])
    _write_jsonl(novelty, [])
    _write_jsonl(prior_art, [])
    _write_jsonl(reviewer, [])

    rows = build_reviewer_threat_model_rows_from_paths(
        q2b_acceptance_path=q2b,
        q2b_experiment_optimizer_path=optimizer,
        model_innovation_blueprint_paths=[blueprint],
        innovation_depth_paths=[innovation],
        novelty_matrix_paths=[novelty],
        prior_art_paths=[prior_art],
        reviewer_iteration_paths=[reviewer],
    )
    assert len(rows) == 2

    command_build_reviewer_threat_model(
        Namespace(
            q2b_acceptance_rubric=str(q2b),
            q2b_experiment_optimizer=str(optimizer),
            model_innovation_blueprints=[str(blueprint)],
            innovation_depth_audits=[str(innovation)],
            novelty_matrices=[str(novelty)],
            prior_art_audits=[str(prior_art)],
            reviewer_iterations=[str(reviewer)],
            output_dir=str(output_dir),
        )
    )
    assert read_records(output_dir / "reviewer_threat_model_summary.jsonl")[0]["critical_threat_count"] == 1

    parser = build_parser()
    args = parser.parse_args(
        [
            "build-reviewer-threat-model",
            "--q2b-acceptance-rubric",
            str(q2b),
            "--q2b-experiment-optimizer",
            str(optimizer),
            "--model-innovation-blueprints",
            str(blueprint),
            "--innovation-depth-audits",
            str(innovation),
            "--novelty-matrices",
            str(novelty),
            "--prior-art-audits",
            str(prior_art),
            "--reviewer-iterations",
            str(reviewer),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_reviewer_threat_model
