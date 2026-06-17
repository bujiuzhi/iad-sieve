"""测试 Q2/B 实验优化器。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_q2b_experiment_optimizer
from iad_sieve.evaluation.q2b_experiment_optimizer import (
    build_q2b_experiment_optimizer_rows,
    write_q2b_experiment_optimizer_outputs,
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


def test_build_q2b_experiment_optimizer_rows_prioritizes_remote_and_primary_track() -> None:
    """验证优化器优先给出远程输入和主轨道强模型实验。"""
    rows = build_q2b_experiment_optimizer_rows(
        q2b_acceptance_rows=[
            {
                "gate_id": "remote_reproducibility_acceptance",
                "gate_name": "远程复现",
                "priority": 0,
                "status": "blocked",
                "required_action": "补齐远程连接。",
                "acceptance_evidence": "远程输出全部验收。",
                "reviewer_failure_mode": "缺远程输出。",
                "paper_claim_boundary": "不得写强模型完成。；OPENAI_API_KEY 未配置前，不能声称对应 API 模型实验已完成。",
            },
            {
                "gate_id": "strong_model_matrix_acceptance",
                "gate_name": "强模型矩阵",
                "priority": 1,
                "status": "blocked",
                "required_action": "运行缺失 actual_model/api_model。",
                "acceptance_evidence": "强模型全部有指标。",
                "reviewer_failure_mode": "baseline 太弱。",
                "paper_claim_boundary": "不得写 SOTA。",
            },
            {
                "gate_id": "no_annotation_strategy_acceptance",
                "gate_name": "无人工标注阶段策略",
                "priority": 6,
                "status": "ready",
                "required_action": "继续执行 no_annotation_protocol。",
                "acceptance_evidence": "不依赖新增人工标注。",
                "reviewer_failure_mode": "弱标签噪声。",
                "paper_claim_boundary": "不表示 Q2/B 已满足。",
            },
        ],
        reviewer_iteration_rows=[
            {
                "iteration_id": "r0_remote_reproducibility",
                "status": "major_revision_required",
                "review_dimension": "远程可复现性",
                "reviewer_critique": "远程未闭环。",
                "optimization_actions": "先跑远程预检。",
            },
            {
                "iteration_id": "r1_strong_baseline_and_sota",
                "status": "major_revision_required",
                "review_dimension": "强 baseline",
                "reviewer_critique": "强模型缺失。",
                "optimization_actions": "补齐 SPECTER2/SciNCL/RoBERTa。",
            },
        ],
        remote_input_request_rows=[
            {
                "request_id": "connection:remote_host",
                "request_type": "connection_field",
                "field_name": "remote_host",
                "status": "waiting_for_user",
                "required": True,
            },
            {
                "request_id": "secret:OPENAI_API_KEY",
                "request_type": "secret_configuration",
                "field_name": "OPENAI_API_KEY",
                "status": "waiting_for_secure_configuration",
                "required": True,
            },
        ],
        remote_execution_slice_rows=[
            {
                "slice_id": "remote_inputs",
                "slice_type": "remote_input_gate",
                "status": "blocked_until_remote_inputs_ready",
                "required_connection_fields": ["remote_host"],
                "required_secret_names": ["OPENAI_API_KEY"],
                "priority": -10,
                "next_action": "补齐远程连接字段。",
            },
            {
                "slice_id": "track:open_v3_scholarly_balanced_gold",
                "slice_type": "advanced_track_execution",
                "evaluation_track": "open_v3_scholarly_balanced_gold",
                "status": "blocked_until_remote_inputs_ready",
                "source_task_ids": ["run_scincl_baseline"],
                "required_secret_names": [],
                "missing_output_count": 7,
                "priority": 150,
                "next_action": "运行主轨道强模型。",
            },
        ],
        advanced_track_rows=[
            {
                "evaluation_track": "open_v3_scholarly_balanced_gold",
                "track_status": "blocked",
                "missing_required_count": 3,
                "missing_required_systems": ["scincl", "roberta", "iad_risk"],
            },
        ],
    )

    assert rows[0]["experiment_id"] == "exp_remote_reproducibility_acceptance"
    assert rows[0]["status"] == "blocked_external_input"
    assert rows[0]["required_connection_fields"] == ["remote_host"]
    assert rows[0]["required_secret_names"] == ["OPENAI_API_KEY"]
    assert rows[1]["experiment_id"] == "exp_strong_model_matrix_acceptance"
    assert rows[1]["status"] == "blocked_remote_execution"
    assert rows[1]["linked_remote_slice_ids"] == ["track:open_v3_scholarly_balanced_gold"]
    assert rows[1]["required_secret_names"] == []
    assert rows[1]["missing_required_systems"] == ["scincl", "roberta", "iad_risk"]
    assert "baseline 太弱" in rows[1]["reviewer_critique"]
    assert "不得写 SOTA" in rows[1]["paper_claim_boundary"]


def test_build_q2b_experiment_optimizer_rows_separates_primary_track_secrets() -> None:
    """验证主轨道无密钥需求时 OPENAI_API_KEY 被列为后续增强阻塞。"""
    rows = build_q2b_experiment_optimizer_rows(
        q2b_acceptance_rows=[
            {
                "gate_id": "remote_reproducibility_acceptance",
                "gate_name": "远程复现",
                "priority": 0,
                "status": "blocked",
                "required_action": "补齐远程连接。",
                "acceptance_evidence": "远程输出全部验收。",
                "reviewer_failure_mode": "缺远程输出。",
                "paper_claim_boundary": "不得写强模型完成。；OPENAI_API_KEY 未配置前，不能声称对应 API 模型实验已完成。",
            },
            {
                "gate_id": "strong_model_matrix_acceptance",
                "gate_name": "强模型矩阵",
                "priority": 1,
                "status": "blocked",
                "required_action": "运行缺失 actual_model/api_model。",
                "acceptance_evidence": "强模型全部有指标。",
                "reviewer_failure_mode": "baseline 太弱。",
                "paper_claim_boundary": "不得写 SOTA。",
            },
        ],
        reviewer_iteration_rows=[
            {
                "iteration_id": "r0_remote_reproducibility",
                "paper_claim_boundary": "远程连接或密钥未就绪前，不能声称强模型实验可复现。",
            }
        ],
        remote_input_request_rows=[
            {
                "request_id": "connection:remote_host",
                "request_type": "connection_field",
                "field_name": "remote_host",
                "status": "waiting_for_user",
                "required": True,
            },
            {
                "request_id": "secret:OPENAI_API_KEY",
                "request_type": "secret_configuration",
                "field_name": "OPENAI_API_KEY",
                "status": "waiting_for_secure_configuration",
                "required": True,
            },
        ],
        remote_execution_slice_rows=[
            {
                "slice_id": "remote_inputs",
                "slice_type": "remote_input_gate",
                "status": "blocked_until_remote_inputs_ready",
                "required_connection_fields": ["remote_host"],
                "required_secret_names": ["OPENAI_API_KEY"],
                "priority": -10,
                "next_action": (
                    "补齐远程输入。；在远程环境通过安全方式配置 OPENAI_API_KEY 后运行阶段脚本。；"
                    "补齐远程连接 profile 与安全密钥配置后执行远程 stage 模板。"
                ),
            },
            {
                "slice_id": "track:open_v3_scholarly_balanced_gold",
                "slice_type": "advanced_track_execution",
                "evaluation_track": "open_v3_scholarly_balanced_gold",
                "status": "blocked_until_remote_inputs_ready",
                "source_task_ids": ["run_scincl_baseline"],
                "required_secret_names": [],
                "priority": 150,
                "next_action": "运行主轨道强模型。",
            },
            {
                "slice_id": "track:open_v2",
                "slice_type": "advanced_track_execution",
                "evaluation_track": "open_v2",
                "status": "blocked_until_remote_inputs_ready",
                "source_task_ids": ["run_llm_pair_judge"],
                "required_secret_names": ["OPENAI_API_KEY"],
                "priority": 200,
                "next_action": "运行 LLM judge。",
            },
        ],
        advanced_track_rows=[
            {
                "evaluation_track": "open_v3_scholarly_balanced_gold",
                "track_status": "blocked",
                "missing_required_systems": ["scincl"],
            }
        ],
    )

    remote_row = rows[0]
    primary_row = rows[1]
    assert remote_row["primary_track"] == "open_v3_scholarly_balanced_gold"
    assert remote_row["primary_track_required_secret_names"] == []
    assert remote_row["deferred_secret_names"] == ["OPENAI_API_KEY"]
    assert remote_row["primary_track_can_start_without_deferred_secrets"] is True
    assert "只需先补齐远程连接字段" in remote_row["primary_track_next_experiment"]
    assert "只需先补齐远程连接字段" in remote_row["next_experiment"]
    assert "OPENAI_API_KEY" not in remote_row["next_experiment"]
    assert "安全密钥配置" not in remote_row["next_experiment"]
    assert "远程连接或密钥未就绪" not in remote_row["paper_claim_boundary"]
    assert "对应 API 模型实验" in remote_row["paper_claim_boundary"]
    assert primary_row["primary_track_required_secret_names"] == []
    assert primary_row["deferred_secret_names"] == ["OPENAI_API_KEY"]


def test_build_q2b_experiment_optimizer_rows_filters_stale_connection_actions_when_ready() -> None:
    """验证连接字段已齐备时不再保留补连接的通用动作。"""
    rows = build_q2b_experiment_optimizer_rows(
        q2b_acceptance_rows=[
            {
                "gate_id": "remote_reproducibility_acceptance",
                "gate_name": "远程复现",
                "priority": 0,
                "status": "blocked",
                "required_action": "补齐远程连接、运行 stage 脚本。",
                "acceptance_evidence": "远程输出全部验收。",
                "reviewer_failure_mode": "缺远程输出。",
                "paper_claim_boundary": "不得写强模型完成。",
            }
        ],
        reviewer_iteration_rows=[],
        remote_input_request_rows=[
            {
                "request_id": "connection:remote_host",
                "request_type": "connection_field",
                "field_name": "remote_host",
                "status": "provided",
                "required": True,
            },
            {
                "request_id": "secret:OPENAI_API_KEY",
                "request_type": "secret_configuration",
                "field_name": "OPENAI_API_KEY",
                "status": "waiting_for_secure_configuration",
                "required": True,
            },
        ],
        remote_execution_slice_rows=[
            {
                "slice_id": "remote_inputs",
                "slice_type": "remote_input_gate",
                "status": "ready_for_primary_track_blocked_for_deferred_secrets",
                "required_connection_fields": [],
                "required_secret_names": ["OPENAI_API_KEY"],
                "priority": -10,
                "next_action": "连接字段已齐；具体可执行任务以 advanced_track_execution 切片状态为准。",
            },
            {
                "slice_id": "track:open_v3",
                "slice_type": "advanced_track_execution",
                "evaluation_track": "open_v3",
                "status": "blocked_unmapped_remote_task",
                "source_task_ids": [],
                "required_secret_names": [],
                "priority": 150,
                "next_action": "open_v3 轨道存在未映射到远程执行计划的系统，需先补齐实验队列任务或单独执行方案。",
            },
        ],
        advanced_track_rows=[],
    )

    row = rows[0]

    assert row["required_connection_fields"] == []
    assert "补齐远程连接" not in row["next_experiment"]
    assert "未映射到远程执行计划" in row["primary_track_next_experiment"]


def test_build_q2b_experiment_optimizer_rows_blocks_on_model_artifact() -> None:
    """验证模型目录缺失会作为外部输入阻塞实验计划。"""
    rows = build_q2b_experiment_optimizer_rows(
        q2b_acceptance_rows=[
            {
                "gate_id": "remote_reproducibility_acceptance",
                "gate_name": "远程复现",
                "priority": 0,
                "status": "blocked",
                "required_action": "先预置本地 LLM 权重。",
                "acceptance_evidence": "远程输出全部验收。",
                "reviewer_failure_mode": "缺远程输出。",
                "paper_claim_boundary": "不得写强模型完成。",
            }
        ],
        reviewer_iteration_rows=[],
        remote_input_request_rows=[
            {
                "request_id": "connection:remote_host",
                "request_type": "connection_field",
                "field_name": "remote_host",
                "status": "provided",
                "required": True,
            },
            {
                "request_id": "model_artifact:outputs/models/local_llm_judge",
                "request_type": "model_artifact",
                "field_name": "outputs/models/local_llm_judge",
                "status": "waiting_for_user",
                "required": True,
            },
        ],
        remote_execution_slice_rows=[
            {
                "slice_id": "remote_inputs",
                "slice_type": "remote_input_gate",
                "status": "blocked_until_model_artifact",
                "required_connection_fields": [],
                "required_secret_names": [],
                "required_model_artifacts": ["outputs/models/local_llm_judge"],
                "priority": -10,
                "next_action": "预置 outputs/models/local_llm_judge。",
            },
            {
                "slice_id": "track:open_v3_scholarly_balanced_gold_source_heldout",
                "slice_type": "advanced_track_execution",
                "evaluation_track": "open_v3_scholarly_balanced_gold_source_heldout",
                "status": "blocked_until_remote_inputs_ready",
                "source_task_ids": ["run_gpt"],
                "required_secret_names": [],
                "priority": 150,
                "next_action": "运行主轨道 GPT judge。",
            },
        ],
        advanced_track_rows=[],
    )

    row = rows[0]

    assert row["status"] == "blocked_external_input"
    assert row["required_connection_fields"] == []
    assert row["required_secret_names"] == []
    assert row["required_model_artifacts"] == ["outputs/models/local_llm_judge"]
    assert "outputs/models/local_llm_judge" in row["primary_track_next_experiment"]
    assert "outputs/models/local_llm_judge" in row["next_experiment"]


def test_build_q2b_experiment_optimizer_rows_keeps_primary_secret_without_stale_connection() -> None:
    """验证主轨道密钥缺失时保留密钥动作但过滤补连接动作。"""
    rows = build_q2b_experiment_optimizer_rows(
        q2b_acceptance_rows=[
            {
                "gate_id": "remote_reproducibility_acceptance",
                "gate_name": "远程复现",
                "priority": 0,
                "status": "blocked",
                "required_action": "补齐远程连接、运行 stage 脚本。",
                "acceptance_evidence": "远程输出全部验收。",
                "reviewer_failure_mode": "缺远程输出。",
                "paper_claim_boundary": "不得写强模型完成。",
            }
        ],
        reviewer_iteration_rows=[],
        remote_input_request_rows=[
            {
                "request_id": "connection:remote_host",
                "request_type": "connection_field",
                "field_name": "remote_host",
                "status": "provided",
                "required": True,
            },
            {
                "request_id": "secret:OPENAI_API_KEY",
                "request_type": "secret_configuration",
                "field_name": "OPENAI_API_KEY",
                "status": "waiting_for_secure_configuration",
                "required": True,
            },
        ],
        remote_execution_slice_rows=[
            {
                "slice_id": "remote_inputs",
                "slice_type": "remote_input_gate",
                "status": "blocked_until_primary_secret_configuration",
                "required_connection_fields": [],
                "required_secret_names": ["OPENAI_API_KEY"],
                "deferred_secret_names": [],
                "priority": -10,
                "next_action": "连接字段已齐；还需在远程环境安全配置主轨道密钥: OPENAI_API_KEY。",
            },
            {
                "slice_id": "track:open_v3_scholarly_balanced_gold_source_heldout",
                "slice_type": "advanced_track_execution",
                "evaluation_track": "open_v3_scholarly_balanced_gold_source_heldout",
                "status": "blocked_until_required_secret_configuration",
                "source_task_ids": ["run_ditto", "run_gpt"],
                "required_secret_names": ["OPENAI_API_KEY"],
                "priority": 150,
                "next_action": "运行主轨道 Ditto/GPT。",
            },
        ],
        advanced_track_rows=[],
    )

    row = rows[0]

    assert row["primary_track_required_secret_names"] == ["OPENAI_API_KEY"]
    assert row["primary_track_can_start_without_deferred_secrets"] is False
    assert row["linked_remote_slice_ids"] == [
        "remote_inputs",
        "track:open_v3_scholarly_balanced_gold_source_heldout",
    ]
    assert row["source_task_ids"] == ["run_ditto", "run_gpt"]
    assert "补齐远程连接" not in row["next_experiment"]
    assert "主轨道密钥" in row["next_experiment"]
    assert "OPENAI_API_KEY" in row["next_experiment"]
    assert "回传 outputs 后重建 remote_output_validation 与 remote_result_acceptance" in row["next_experiment"]
    assert len(row["next_experiment"].split("；")) <= 4


def test_write_q2b_experiment_optimizer_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证优化器写出 JSONL、CSV、Markdown 和摘要。"""
    rows = [
        {
            "experiment_id": "exp_remote_reproducibility_acceptance",
            "gate_id": "remote_reproducibility_acceptance",
            "priority": 0,
            "status": "blocked_external_input",
            "review_dimension": "远程可复现性",
            "reviewer_critique": "远程未闭环。",
            "next_experiment": "补齐远程连接。",
            "required_connection_fields": ["remote_host"],
            "required_secret_names": ["OPENAI_API_KEY"],
            "linked_remote_slice_ids": ["remote_inputs"],
            "missing_required_systems": [],
            "acceptance_evidence": "远程输出验收。",
            "paper_claim_boundary": "不得写完成。",
        },
        {
            "experiment_id": "exp_strong_model_matrix_acceptance",
            "gate_id": "strong_model_matrix_acceptance",
            "priority": 1,
            "status": "blocked_remote_execution",
            "review_dimension": "强 baseline",
            "reviewer_critique": "强模型缺失。",
            "next_experiment": "运行主轨道强模型。",
            "required_connection_fields": [],
            "required_secret_names": [],
            "linked_remote_slice_ids": ["track:open_v3_scholarly_balanced_gold"],
            "missing_required_systems": ["scincl"],
            "acceptance_evidence": "强模型矩阵 ready。",
            "paper_claim_boundary": "不得写 SOTA。",
        },
    ]
    output_dir = tmp_path / "q2b_experiment_optimizer"

    write_q2b_experiment_optimizer_outputs(rows, output_dir)

    assert read_records(output_dir / "q2b_experiment_optimizer.jsonl")[0]["experiment_id"] == "exp_remote_reproducibility_acceptance"
    assert (output_dir / "q2b_experiment_optimizer.csv").exists()
    assert "# Q2/B Experiment Optimizer" in (output_dir / "q2b_experiment_optimizer.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "q2b_experiment_optimizer_summary.jsonl")[0]
    assert summary["experiment_count"] == 2
    assert summary["blocked_external_input_count"] == 1
    assert summary["blocked_remote_execution_count"] == 1
    assert summary["highest_priority_experiment"] == "exp_remote_reproducibility_acceptance"
    assert summary["remote_connection_required"] is True
    assert summary["q2b_experiment_plan_ready"] is False


def test_build_q2b_experiment_optimizer_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 Q2/B 实验优化器产物。"""
    q2b_acceptance = tmp_path / "q2b_acceptance_rubric.jsonl"
    reviewer_iteration = tmp_path / "reviewer_iteration_audit.jsonl"
    remote_input = tmp_path / "remote_input_request.jsonl"
    remote_slice = tmp_path / "remote_execution_slice.jsonl"
    advanced_track = tmp_path / "advanced_model_evidence_track_summary.jsonl"
    output_dir = tmp_path / "q2b_experiment_optimizer"
    _write_jsonl(q2b_acceptance, [{"gate_id": "remote_reproducibility_acceptance", "priority": 0, "status": "blocked"}])
    _write_jsonl(reviewer_iteration, [{"iteration_id": "r0_remote_reproducibility", "status": "major_revision_required"}])
    _write_jsonl(remote_input, [{"request_id": "connection:remote_host", "request_type": "connection_field", "field_name": "remote_host", "status": "waiting_for_user", "required": True}])
    _write_jsonl(remote_slice, [{"slice_id": "remote_inputs", "slice_type": "remote_input_gate", "status": "blocked_until_remote_inputs_ready", "required_connection_fields": ["remote_host"]}])
    _write_jsonl(advanced_track, [])

    command_build_q2b_experiment_optimizer(
        Namespace(
            q2b_acceptance_rubric=str(q2b_acceptance),
            reviewer_iteration=str(reviewer_iteration),
            remote_input_request=str(remote_input),
            remote_execution_slice=str(remote_slice),
            advanced_track_summary=str(advanced_track),
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "q2b_experiment_optimizer_summary.jsonl").exists()
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-q2b-experiment-optimizer",
            "--q2b-acceptance-rubric",
            str(q2b_acceptance),
            "--reviewer-iteration",
            str(reviewer_iteration),
            "--remote-input-request",
            str(remote_input),
            "--remote-execution-slice",
            str(remote_slice),
            "--advanced-track-summary",
            str(advanced_track),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_q2b_experiment_optimizer
