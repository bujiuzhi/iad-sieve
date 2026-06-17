"""测试主轨道远程交接包。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_primary_remote_handoff
from iad_sieve.evaluation.primary_remote_handoff import (
    build_primary_remote_handoff_rows,
    write_primary_remote_handoff_outputs,
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


def _readiness_row() -> dict:
    """构造主轨道远程就绪审计记录。

    参数:
        无。

    返回:
        readiness 记录。
    """
    return {
        "readiness_id": "primary_track_remote_readiness",
        "readiness_status": "blocked_missing_connection",
        "primary_track": "open_v3_scholarly_balanced_gold",
        "primary_template_path": "outputs/remote_slice_run_pack_fixture/run_remote_slice_open_v3_scholarly_balanced_gold.template.sh",
        "primary_track_task_count": 3,
        "missing_connection_fields": [
            "remote_host",
            "remote_port",
            "remote_user",
            "ssh_key_path",
            "remote_workspace",
            "conda_env",
        ],
        "primary_required_secret_names": [],
        "missing_primary_secret_names": [],
        "deferred_global_secret_names": ["OPENAI_API_KEY"],
        "source_task_ids": [
            "run_scincl_provenance_blind_iad_risk_transformer_open_v3_scholarly_balanced_gold",
            "run_roberta_pair_baseline_open_v3_scholarly_balanced_gold",
            "run_scincl_baseline_open_v3_scholarly_balanced_gold",
        ],
        "missing_outputs": [
            "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold/iad_risk_transformer_summary.jsonl",
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_scores.jsonl",
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_scores.jsonl",
        ],
        "paper_claim_boundary": "主轨道远程输出未回传并通过验收前，不能声称强模型闭环。",
    }


def test_build_primary_remote_handoff_rows_summarizes_connection_only_blocker() -> None:
    """验证交接包把主轨道阻塞收敛为连接字段和脚本。"""
    rows = build_primary_remote_handoff_rows([_readiness_row()])
    row = rows[0]

    assert row["handoff_id"] == "primary_track_remote_handoff"
    assert row["primary_track"] == "open_v3_scholarly_balanced_gold"
    assert row["handoff_status"] == "waiting_for_connection_fields"
    assert row["connection_field_count"] == 6
    assert row["primary_required_secret_names"] == []
    assert row["deferred_global_secret_names"] == ["OPENAI_API_KEY"]
    assert row["primary_script_path"].endswith("run_remote_slice_open_v3_scholarly_balanced_gold.template.sh")
    assert row["remote_task_order"] == [
        "run_scincl_baseline_open_v3_scholarly_balanced_gold",
        "run_roberta_pair_baseline_open_v3_scholarly_balanced_gold",
        "run_scincl_provenance_blind_iad_risk_transformer_open_v3_scholarly_balanced_gold",
    ]
    assert "OPENAI_API_KEY 不属于 open_v3 scholarly 主轨道前置条件" in row["operator_note"]
    assert "validate-remote-outputs" in row["post_run_validation"]
    assert "evaluate-external-baseline" in row["post_run_validation"]
    assert "run-iad-evidence-bootstrap" in row["post_run_validation"]
    assert "build-advanced-model-evidence" in row["post_run_validation"]
    assert "build-model-superiority-audit" in row["post_run_validation"]
    assert "build-q2b-acceptance-rubric" in row["post_run_validation"]
    assert "build-primary-track-superiority-protocol" in row["post_run_validation"]
    assert "build-primary-track-superiority-evaluator" in row["post_run_validation"]
    assert "build-q2b-experiment-optimizer" in row["post_run_validation"]
    assert "build-reviewer-threat-model" in row["post_run_validation"]
    assert "scincl_metric_summary.jsonl" in row["post_run_validation"]
    assert "roberta_pair_metric_summary.jsonl" in row["post_run_validation"]
    assert "iad_risk_transformer_scincl_bootstrap_confidence.csv" in row["post_run_validation"]
    assert "OPENAI_API_KEY" not in row["post_run_validation"]
    assert "--execution-mode actual_model --split-field split --eval-splits test" in row["post_run_validation"]
    assert "--execution-mode api_model" not in row["post_run_validation"]
    assert row["post_run_validation"].index("validate-remote-outputs") < row["post_run_validation"].index(
        "evaluate-external-baseline"
    )
    assert row["post_run_validation"].index("run-iad-evidence-bootstrap") < row["post_run_validation"].index(
        "build-primary-track-superiority-evaluator"
    )
    assert row["post_run_validation"].index("build-q2b-experiment-optimizer") < row["post_run_validation"].index(
        "build-reviewer-threat-model"
    )


def test_build_primary_remote_handoff_rows_reports_unmapped_primary_tasks() -> None:
    """验证主轨道无任务映射时交接包不提示重复运行已验收任务。"""
    readiness_row = {
        "readiness_id": "primary_track_remote_readiness",
        "readiness_status": "blocked_unmapped_primary_tasks",
        "primary_track": "open_v3_scholarly_balanced_gold_source_heldout",
        "primary_template_path": "",
        "primary_track_task_count": 0,
        "missing_connection_fields": [],
        "primary_required_secret_names": [],
        "missing_primary_secret_names": [],
        "deferred_global_secret_names": ["OPENAI_API_KEY"],
        "unmapped_systems": [
            "ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
            "gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout",
        ],
        "source_task_ids": [],
        "missing_outputs": [],
        "paper_claim_boundary": "缺失系统未闭环前不得写强模型完成。",
    }

    rows = build_primary_remote_handoff_rows([readiness_row])
    row = rows[0]

    assert row["handoff_status"] == "waiting_for_primary_task_mapping"
    assert row["primary_script_path"] == ""
    assert row["remote_task_order"] == []
    assert row["unmapped_systems"] == [
        "ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
        "gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout",
    ]
    assert "尚未映射到可执行远程 task" in row["operator_note"]
    assert "不要重复执行已验收" in row["operator_note"]
    assert "主轨道先跑 SciNCL" not in row["operator_note"]


def test_build_primary_remote_handoff_rows_reports_primary_secret_blocker() -> None:
    """验证主轨道包含 GPT judge 时交接包要求先配置主轨道密钥。"""
    readiness_row = {
        "readiness_id": "primary_track_remote_readiness",
        "readiness_status": "blocked_missing_primary_secret",
        "primary_track": "open_v3_scholarly_balanced_gold_source_heldout",
        "primary_template_path": "outputs/remote_slice_run_pack_fixture/run_remote_slice_open_v3_scholarly_balanced_gold_source_heldout.template.sh",
        "primary_track_task_count": 2,
        "missing_connection_fields": [],
        "primary_required_secret_names": ["OPENAI_API_KEY"],
        "missing_primary_secret_names": ["OPENAI_API_KEY"],
        "deferred_global_secret_names": [],
        "unmapped_systems": [],
        "source_task_ids": [
            "train_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
            "run_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
            "run_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout",
        ],
        "missing_outputs": [
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_scores.jsonl",
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_scores.jsonl",
        ],
        "paper_claim_boundary": "主轨道远程输出未回传并通过验收前，不能声称强模型闭环。",
    }

    rows = build_primary_remote_handoff_rows([readiness_row])
    row = rows[0]

    assert row["handoff_status"] == "waiting_for_primary_secret"
    assert row["primary_required_secret_names"] == ["OPENAI_API_KEY"]
    assert row["missing_primary_secret_names"] == ["OPENAI_API_KEY"]
    assert row["remote_task_order"] == [
        "train_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
        "run_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
        "run_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout",
    ]
    assert "先安全配置主轨道密钥" in row["operator_note"]
    assert "OPENAI_API_KEY 不属于 open_v3 scholarly 主轨道前置条件" not in row["operator_note"]
    assert "主轨道先跑 SciNCL" not in row["operator_note"]


def test_build_primary_remote_handoff_rows_describes_local_llm_primary_task() -> None:
    """验证本地 LLM judge 主轨道任务不会残留旧 API 密钥或 SciNCL 提示。"""
    readiness_row = {
        "readiness_id": "primary_track_remote_readiness",
        "readiness_status": "ready_to_run_primary_slice",
        "primary_track": "open_v3_scholarly_balanced_gold_source_heldout",
        "primary_template_path": "outputs/remote_slice_run_pack_fixture/run_remote_slice_open_v3_scholarly_balanced_gold_source_heldout.template.sh",
        "primary_track_task_count": 1,
        "missing_connection_fields": [],
        "primary_required_secret_names": [],
        "missing_primary_secret_names": [],
        "deferred_global_secret_names": [],
        "unmapped_systems": [],
        "source_task_ids": [
            "run_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout",
        ],
        "missing_outputs": [
            "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_scores.jsonl",
        ],
        "paper_claim_boundary": "主轨道远程输出未回传并通过验收前，不能声称强模型闭环。",
    }

    rows = build_primary_remote_handoff_rows([readiness_row])
    row = rows[0]

    assert row["handoff_status"] == "ready_to_execute_primary_script"
    assert row["remote_task_order"] == ["run_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout"]
    assert "本地 Transformers LLM judge" in row["operator_note"]
    assert "OPENAI_API_KEY" not in row["operator_note"]
    assert "主轨道先跑 SciNCL" not in row["operator_note"]


def test_write_primary_remote_handoff_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证交接包写出 JSONL、CSV、Markdown 和 summary。"""
    rows = build_primary_remote_handoff_rows([_readiness_row()])
    output_dir = tmp_path / "primary_remote_handoff"

    write_primary_remote_handoff_outputs(rows, output_dir)

    handoff_row = read_records(output_dir / "primary_remote_handoff.jsonl")[0]
    assert handoff_row["connection_field_count"] == 6
    assert (
        "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/gpt_pair_judge_source_heldout_bootstrap_confidence.csv"
        in handoff_row["post_run_validation_expected_outputs"]
    )
    assert (output_dir / "primary_remote_handoff.csv").exists()
    markdown = (output_dir / "primary_remote_handoff.md").read_text(encoding="utf-8")
    assert "# Primary Remote Handoff" in markdown
    assert "run_scincl_baseline_open_v3_scholarly_balanced_gold" in markdown
    assert "## 回传派生产物" in markdown
    post_run_script = output_dir / "run_primary_post_run_validation.sh"
    assert f"bash {post_run_script}" in markdown
    assert "bash run_primary_post_run_validation.sh" not in markdown
    assert "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_metric_summary.jsonl" in markdown
    assert "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_metric_summary.jsonl" in markdown
    assert "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_metric_summary.jsonl" in markdown
    assert "outputs/primary_track_superiority_evaluator_fixture/primary_track_superiority_evaluator_summary.jsonl" in markdown
    assert post_run_script.exists()
    script_text = post_run_script.read_text(encoding="utf-8")
    assert script_text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in script_text
    assert "evaluate-external-baseline" in script_text
    assert "build-primary-track-superiority-evaluator" in script_text
    assert "build-reviewer-threat-model" in script_text
    assert "OPENAI_API_KEY" not in script_text
    assert "specter2_adapter_cosine_open_v2" not in script_text
    assert "iad_risk_transformer_specter2_open_v2" not in script_text
    assert "ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout" in script_text
    assert "gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout" in script_text
    assert "ditto_match_probability" in script_text
    assert "gpt_same_work_probability" in script_text
    assert "--execution-mode actual_model --split-field split --eval-splits test" in script_text
    assert "--execution-mode api_model" not in script_text
    assert "ditto_style_em_metric_summary.jsonl" in script_text
    assert "gpt_pair_judge_metric_summary.jsonl" in script_text
    assert "ditto_style_em_execution_summary.jsonl" in script_text
    assert "gpt_pair_judge_execution_summary.jsonl" in script_text
    assert "ditto_style_em_source_heldout_bootstrap_confidence.csv" in script_text
    assert "gpt_pair_judge_source_heldout_bootstrap_confidence.csv" in script_text
    assert "iad_risk_transformer_scincl_source_heldout_bootstrap_confidence.csv" in script_text
    assert "scincl_source_heldout_bootstrap_confidence.csv" in script_text
    assert "outputs/iad_source_heldout_coverage_audit_coci_source_patch/iad_source_heldout_coverage_summary.jsonl" in script_text
    assert (
        "outputs/iad_risk_split_evaluation_audit_coci_source_patch_source_heldout/"
        "iad_risk_split_evaluation_audit_summary.jsonl"
    ) in script_text
    summary = read_records(output_dir / "primary_remote_handoff_summary.jsonl")[0]
    assert summary["primary_track"] == "open_v3_scholarly_balanced_gold"
    assert summary["handoff_status"] == "waiting_for_connection_fields"
    assert summary["connection_field_count"] == 6
    assert summary["primary_task_count"] == 3
    assert summary["missing_primary_secret_count"] == 0
    assert summary["post_run_validation_step_count"] >= 10
    assert summary["post_run_validation_expected_output_count"] >= 15
    assert summary["post_run_validation_script"] == "run_primary_post_run_validation.sh"
    assert summary["post_run_validation_script_path"] == str(post_run_script)


def test_build_primary_remote_handoff_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出主轨道远程交接包。"""
    readiness_path = tmp_path / "primary_remote_readiness.jsonl"
    output_dir = tmp_path / "primary_remote_handoff"
    _write_jsonl(readiness_path, [_readiness_row()])

    command_build_primary_remote_handoff(
        Namespace(
            primary_remote_readiness=str(readiness_path),
            output_dir=str(output_dir),
        )
    )

    assert (output_dir / "primary_remote_handoff_summary.jsonl").exists()
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-primary-remote-handoff",
            "--primary-remote-readiness",
            str(readiness_path),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.func == command_build_primary_remote_handoff
