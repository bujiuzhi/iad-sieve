"""测试二区/B类行动板。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_q2b_action_board
from iad_sieve.evaluation.q2b_action_board import build_q2b_action_board_rows, write_q2b_action_board_outputs
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


def test_build_q2b_action_board_rows_prioritizes_environment_task_and_gate_recheck() -> None:
    """验证行动板按审稿风险聚合环境、远程任务和门禁复核。"""
    submission_rows = [
        {
            "submission_gate_id": "advancedness_gate",
            "decision": "blocked",
            "reviewer_risk_level": "high",
            "blocking_reasons": ["advanced_baseline"],
            "next_action": "完成强 baseline。",
        },
        {
            "submission_gate_id": "source_bias_gate",
            "decision": "ready_for_draft_submission",
            "reviewer_risk_level": "low",
        },
    ]
    blueprint_rows = [
        {
            "blueprint_item_id": "environment:python_module:torch",
            "blueprint_item_type": "environment_dependency",
            "dependency_name": "torch",
            "package_spec": "torch>=2.2",
            "status": "missing",
            "reviewer_risk_level": "high",
            "next_action": "安装 torch。",
            "paper_claim_boundary": "不能声称 GPU 模型完成。",
        },
        {
            "blueprint_item_id": "root_task:run_scincl",
            "blueprint_item_type": "root_execution_task",
            "task_id": "run_scincl",
            "priority": 3,
            "status": "blocked_remote_required",
            "missing_output_count": 2,
            "missing_outputs": ["scores.jsonl", "summary.jsonl"],
            "execution_command": "python -m iad_sieve.cli run-representation-baseline",
            "next_action": "运行阶段脚本。",
            "paper_claim_boundary": "未验收前不能写 actual_model。",
        },
    ]
    upgrade_rows = [
        {
            "requirement_id": "remote_gpu_connection",
            "priority": 1,
            "status": "blocked_external_input",
            "concrete_action": "补充远程连接。",
            "expected_evidence": "远程环境可用。",
            "paper_claim_boundary": "不能写强模型完成。",
        }
    ]
    advanced_rows = [
        {
            "evidence_id": "required:scincl_cosine_open_v3",
            "system": "scincl_cosine_open_v3",
            "evidence_status": "missing_required",
            "reviewer_risk": "high",
            "next_action": "运行 actual_model。",
        }
    ]

    rows = build_q2b_action_board_rows(submission_rows, blueprint_rows, upgrade_rows, advanced_rows)
    by_id = {row["action_id"]: row for row in rows}

    assert rows[0]["action_id"] == "prepare_remote_environment"
    assert by_id["prepare_remote_environment"]["status"] == "blocked_external_input"
    assert "torch" in by_id["prepare_remote_environment"]["acceptance_evidence"]
    assert by_id["execute_remote_task:run_scincl"]["missing_outputs"] == ["scores.jsonl", "summary.jsonl"]
    assert by_id["execute_remote_task:run_scincl"]["execution_command"] == "python -m iad_sieve.cli run-representation-baseline"
    assert by_id["close_submission_gate:advancedness_gate"]["action_type"] == "submission_gate_recheck"
    assert by_id["close_submission_gate:advancedness_gate"]["reviewer_risk_level"] == "high"
    assert by_id["close_advanced_evidence:scincl_cosine_open_v3"]["status"] == "blocked_remote_required"


def test_build_q2b_action_board_environment_action_uses_current_root_tasks_over_stale_upgrade_text() -> None:
    """验证环境准备动作优先采用当前远程 root task，避免旧升级计划文案误导执行。"""
    blueprint_rows = [
        {
            "blueprint_item_id": "environment:python_module:torch",
            "blueprint_item_type": "environment_dependency",
            "dependency_name": "torch",
            "package_spec": "torch>=2.2",
            "status": "missing",
        },
        {
            "blueprint_item_id": "root_task:run_llm_pair_judge_api_model_open_v2",
            "blueprint_item_type": "root_execution_task",
            "task_id": "run_llm_pair_judge_api_model_open_v2",
            "status": "blocked_missing_secret",
            "next_action": "安全配置 OPENAI_API_KEY 后运行 LLM pair judge。",
            "paper_claim_boundary": "LLM 输出未验收前不得写成完成。",
        },
        {
            "blueprint_item_id": "root_task:run_scincl_provenance_blind_iad_risk_transformer_open_v2",
            "blueprint_item_type": "root_execution_task",
            "task_id": "run_scincl_provenance_blind_iad_risk_transformer_open_v2",
            "status": "blocked_remote_required",
            "next_action": "在 GPU 环境运行 provenance-blind Transformer。",
            "paper_claim_boundary": "provenance-blind 输出未验收前不得写成无泄漏。",
        },
    ]
    upgrade_rows = [
        {
            "requirement_id": "specter2_adapter_actual_model",
            "status": "blocked_external_input",
            "concrete_action": "执行 stage 0 SPECTER2 adapter 任务。",
            "paper_claim_boundary": "不得写 SPECTER2 adapter actual_model 已完成。",
        }
    ]

    rows = build_q2b_action_board_rows([], blueprint_rows, upgrade_rows, [])
    environment_action = {row["action_id"]: row for row in rows}["prepare_remote_environment"]

    assert "run_llm_pair_judge_api_model_open_v2" in environment_action["next_action"]
    assert "provenance-blind Transformer" in environment_action["next_action"]
    assert "SPECTER2 adapter" not in environment_action["next_action"]
    assert "SPECTER2 adapter" not in environment_action["paper_claim_boundary"]
    assert environment_action["source_task_ids"] == [
        "run_llm_pair_judge_api_model_open_v2",
        "run_scincl_provenance_blind_iad_risk_transformer_open_v2",
    ]


def test_build_q2b_action_board_skips_environment_action_without_pending_remote_work() -> None:
    """验证无待完成远程工作时不因历史环境缺失生成外部阻塞。"""
    blueprint_rows = [
        {
            "blueprint_item_id": "environment:python_module:torch",
            "blueprint_item_type": "environment_dependency",
            "dependency_name": "torch",
            "package_spec": "torch>=2.2",
            "status": "missing",
        }
    ]

    rows = build_q2b_action_board_rows([], blueprint_rows, [], [])

    assert rows == []


def test_build_q2b_action_board_rows_adds_remote_connection_actions() -> None:
    """验证行动板把远程连接字段、模型目录和密钥配置拆成具体动作。"""
    connection_rows = [
        {
            "item_id": "connection_field:remote_host",
            "item_type": "connection_field",
            "field_name": "remote_host",
            "status": "blocked_external_input",
            "reviewer_risk_level": "high",
            "next_action": "补充远程服务器地址。",
            "paper_claim_boundary": "不能声称远程实验可复现。",
        },
        {
            "item_id": "secret_field:OPENAI_API_KEY",
            "item_type": "secret_field",
            "field_name": "OPENAI_API_KEY",
            "status": "blocked_secret_configuration",
            "reviewer_risk_level": "high",
            "next_action": "安全配置 OPENAI_API_KEY。",
            "paper_claim_boundary": "不能声称 LLM baseline 已完成。",
        },
        {
            "item_id": "model_artifact:outputs/models/local_llm_judge",
            "item_type": "model_artifact",
            "field_name": "outputs/models/local_llm_judge",
            "status": "blocked_external_input",
            "reviewer_risk_level": "high",
            "next_action": "预置 outputs/models/local_llm_judge。",
            "paper_claim_boundary": "模型目录未预置前不能声称 LLM actual_model 完成。",
        },
        {
            "item_id": "stage_command:0",
            "item_type": "stage_command",
            "status": "blocked_until_connection_ready",
            "command_template": "ssh -p ${REMOTE_PORT} ... run_stage_00.sh",
        },
        {
            "item_id": "script_template:remote_sync_and_run",
            "item_type": "script_template",
            "template_path": "remote_sync_and_run.template.sh",
            "status": "ready_template",
            "reviewer_risk_level": "low",
            "next_action": "连接字段齐全后执行同步运行模板。",
            "paper_claim_boundary": "同步运行模板执行且输出验收前，不能声称强模型结果已闭环。",
        },
        {
            "item_id": "script_template:remote_pull_outputs",
            "item_type": "script_template",
            "template_path": "remote_pull_outputs.template.sh",
            "status": "ready_template",
            "reviewer_risk_level": "low",
            "next_action": "远程执行完成后拉回输出并验收。",
            "paper_claim_boundary": "输出未拉回验收前，不能写入论文证据。",
        },
    ]

    rows = build_q2b_action_board_rows([], [], [], [], connection_rows=connection_rows)
    by_id = {row["action_id"]: row for row in rows}

    assert rows[0]["action_id"] == "provide_remote_connection:remote_host"
    assert by_id["provide_remote_connection:remote_host"]["action_type"] == "remote_connection_input"
    assert by_id["provide_remote_connection:remote_host"]["status"] == "blocked_external_input"
    assert by_id["provide_model_artifact:outputs/models/local_llm_judge"]["action_type"] == "remote_model_artifact_input"
    assert by_id["provide_model_artifact:outputs/models/local_llm_judge"]["blocking_scope"] == "remote_model_artifact"
    assert by_id["configure_remote_secret:OPENAI_API_KEY"]["action_type"] == "remote_secret_input"
    assert by_id["configure_remote_secret:OPENAI_API_KEY"]["status"] == "blocked_secret_configuration"
    assert by_id["review_remote_stage_template:0"]["execution_command"] == "ssh -p ${REMOTE_PORT} ... run_stage_00.sh"
    assert by_id["review_remote_handoff_template:remote_sync_and_run"]["action_type"] == "remote_handoff_template"
    assert by_id["review_remote_handoff_template:remote_sync_and_run"]["execution_command"] == "bash outputs/remote_connection_pack_fixture/remote_sync_and_run.template.sh"
    assert by_id["review_remote_handoff_template:remote_pull_outputs"]["reviewer_risk_level"] == "low"


def test_build_q2b_action_board_rows_adds_advanced_track_gap_actions() -> None:
    """验证行动板把高级模型缺口聚合为 evaluation_track 级阻塞动作。"""
    advanced_rows = [
        {
            "evidence_id": "transformer:iad_risk_transformer_open_v2",
            "system": "iad_risk_transformer_open_v2",
            "evaluation_track": "open_v2",
            "evidence_status": "ready_actual_model",
        },
        {
            "evidence_id": "required:specter2_adapter_cosine_open_v2",
            "system": "specter2_adapter_cosine_open_v2",
            "evaluation_track": "open_v2",
            "evidence_status": "missing_required",
        },
        {
            "evidence_id": "required:iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
            "system": "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
            "evaluation_track": "open_v3_scholarly_balanced_gold",
            "evidence_status": "missing_required",
        },
        {
            "evidence_id": "required:scincl_cosine_open_v3_scholarly_balanced_gold",
            "system": "scincl_cosine_open_v3_scholarly_balanced_gold",
            "evaluation_track": "open_v3_scholarly_balanced_gold",
            "evidence_status": "missing_required",
        },
        {
            "evidence_id": "required:roberta_pair_open_v3_balanced_gold",
            "system": "roberta_pair_open_v3_balanced_gold",
            "evaluation_track": "open_v3_balanced_gold",
            "evidence_status": "missing_required",
        },
    ]

    rows = build_q2b_action_board_rows([], [], [], advanced_rows)
    by_id = {row["action_id"]: row for row in rows}
    scholarly_track = by_id["close_advanced_track:open_v3_scholarly_balanced_gold"]

    assert rows[0]["action_id"] == "close_advanced_track:open_v3_scholarly_balanced_gold"
    assert scholarly_track["action_type"] == "advanced_evidence_track_gap"
    assert scholarly_track["priority"] == 150
    assert scholarly_track["evaluation_track"] == "open_v3_scholarly_balanced_gold"
    assert scholarly_track["missing_required_count"] == 2
    assert scholarly_track["missing_systems"] == [
        "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
        "scincl_cosine_open_v3_scholarly_balanced_gold",
    ]
    assert scholarly_track["source_evidence_ids"] == [
        "required:iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
        "required:scincl_cosine_open_v3_scholarly_balanced_gold",
    ]
    assert "open_v2" in scholarly_track["paper_claim_boundary"]
    assert by_id["close_advanced_track:open_v3_balanced_gold"]["priority"] > scholarly_track["priority"]
    assert "例如 open_v3_scholarly_balanced_gold" in by_id["close_advanced_track:open_v2"]["paper_claim_boundary"]
    assert by_id["close_advanced_evidence:scincl_cosine_open_v3_scholarly_balanced_gold"]["priority"] == 200


def test_build_q2b_action_board_rows_links_advanced_tracks_to_remote_tasks() -> None:
    """验证高级模型轨道动作关联远程 root task 和缺失输出。"""
    blueprint_rows = [
        {
            "blueprint_item_id": "root_task:run_scincl_baseline_open_v3_scholarly_balanced_gold",
            "blueprint_item_type": "root_execution_task",
            "task_id": "run_scincl_baseline_open_v3_scholarly_balanced_gold",
            "execution_stage": 0,
            "execution_command": "python -m iad_sieve.cli run-representation-baseline --system-name scincl_cosine_open_v3_scholarly_balanced_gold",
            "missing_outputs": [
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_scores.jsonl",
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_execution_summary.jsonl",
            ],
            "status": "blocked_remote_required",
        },
        {
            "blueprint_item_id": "root_task:run_iad_transformer_open_v3_scholarly_balanced_gold",
            "blueprint_item_type": "root_execution_task",
            "task_id": "run_iad_transformer_open_v3_scholarly_balanced_gold",
            "execution_stage": 1,
            "execution_command": "python -m iad_sieve.cli train-iad-risk-transformer-model --output-dir outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
            "missing_outputs": [
                "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold/iad_risk_transformer_summary.jsonl",
            ],
            "status": "blocked_remote_required",
        },
        {
            "blueprint_item_id": "root_task:run_scincl_baseline_open_v3_scholarly_balanced_gold_source_heldout",
            "blueprint_item_type": "root_execution_task",
            "task_id": "run_scincl_baseline_open_v3_scholarly_balanced_gold_source_heldout",
            "execution_stage": 0,
            "execution_command": (
                "python -m iad_sieve.cli run-representation-baseline "
                "--system-name scincl_cosine_open_v3_scholarly_balanced_gold_source_heldout"
            ),
            "missing_outputs": [
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_scores.jsonl",
            ],
            "status": "blocked_remote_required",
        },
    ]
    advanced_rows = [
        {
            "evidence_id": "required:scincl_cosine_open_v3_scholarly_balanced_gold",
            "system": "scincl_cosine_open_v3_scholarly_balanced_gold",
            "evaluation_track": "open_v3_scholarly_balanced_gold",
            "evidence_status": "missing_required",
        },
        {
            "evidence_id": "required:iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
            "system": "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold",
            "evaluation_track": "open_v3_scholarly_balanced_gold",
            "evidence_status": "missing_required",
        },
        {
            "evidence_id": "required:roberta_pair_open_v3_scholarly_balanced_gold",
            "system": "roberta_pair_open_v3_scholarly_balanced_gold",
            "evaluation_track": "open_v3_scholarly_balanced_gold",
            "evidence_status": "missing_required",
        },
    ]

    rows = build_q2b_action_board_rows([], blueprint_rows, [], advanced_rows)
    by_id = {row["action_id"]: row for row in rows}
    track_row = by_id["close_advanced_track:open_v3_scholarly_balanced_gold"]

    assert track_row["source_task_ids"] == [
        "run_scincl_baseline_open_v3_scholarly_balanced_gold",
        "run_iad_transformer_open_v3_scholarly_balanced_gold",
    ]
    assert track_row["mapped_task_count"] == 2
    assert track_row["execution_stages"] == ["0", "1"]
    assert track_row["unmapped_systems"] == ["roberta_pair_open_v3_scholarly_balanced_gold"]
    assert track_row["missing_outputs"] == [
        "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_scores.jsonl",
        "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_execution_summary.jsonl",
        "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold/iad_risk_transformer_summary.jsonl",
    ]
    assert "对应远程任务" in track_row["acceptance_evidence"]
    assert track_row["execution_command"] == "见 source_task_ids 对应 root_execution_task 或远程 stage 脚本。"


def test_write_q2b_action_board_outputs_writes_reports_and_summary(tmp_path) -> None:
    """验证行动板写出 JSONL、CSV、Markdown 和摘要。"""
    rows = [
        {
            "action_id": "prepare_remote_environment",
            "action_type": "environment_setup",
            "priority": 1,
            "status": "blocked_external_input",
            "reviewer_risk_level": "high",
            "missing_outputs": [],
            "next_action": "补齐依赖。",
        },
        {
            "action_id": "execute_remote_task:run_scincl",
            "action_type": "remote_root_task",
            "priority": 2,
            "status": "blocked_remote_required",
            "reviewer_risk_level": "high",
            "missing_outputs": ["scores.jsonl"],
            "next_action": "运行远程任务。",
        },
    ]
    output_dir = tmp_path / "q2b_action_board"

    write_q2b_action_board_outputs(rows, output_dir)

    assert read_records(output_dir / "q2b_action_board.jsonl")[0]["action_id"] == "prepare_remote_environment"
    assert (output_dir / "q2b_action_board.csv").exists()
    assert "# Q2/B Action Board" in (output_dir / "q2b_action_board.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "q2b_action_board_summary.jsonl")[0]
    assert summary["action_count"] == 2
    assert summary["high_risk_action_count"] == 2
    assert summary["remote_root_task_count"] == 1
    assert summary["remote_handoff_template_count"] == 0
    assert summary["advanced_track_gap_count"] == 0
    assert summary["unmapped_advanced_track_gap_count"] == 0
    assert summary["q2_b_ready"] is False


def test_build_q2b_action_board_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出二区/B类行动板。"""
    submission = tmp_path / "submission_gate_audit.jsonl"
    blueprint = tmp_path / "remote_execution_blueprint.jsonl"
    upgrade = tmp_path / "journal_upgrade_plan.jsonl"
    advanced = tmp_path / "advanced_model_evidence.jsonl"
    connection = tmp_path / "remote_connection_pack.jsonl"
    output_dir = tmp_path / "q2b_action_board"
    _write_jsonl(submission, [{"submission_gate_id": "overall_submission_gate", "decision": "blocked", "reviewer_risk_level": "high"}])
    _write_jsonl(
        blueprint,
        [{"blueprint_item_id": "environment:python_module:torch", "blueprint_item_type": "environment_dependency", "dependency_name": "torch", "status": "missing"}],
    )
    _write_jsonl(upgrade, [{"requirement_id": "remote_gpu_connection", "status": "blocked_external_input"}])
    _write_jsonl(advanced, [{"evidence_id": "required:scincl", "system": "scincl", "evidence_status": "missing_required"}])
    _write_jsonl(connection, [{"item_id": "connection_field:remote_host", "item_type": "connection_field", "field_name": "remote_host", "status": "blocked_external_input"}])

    command_build_q2b_action_board(
        Namespace(
            submission_gates=str(submission),
            remote_blueprint=str(blueprint),
            journal_upgrade_plan=str(upgrade),
            advanced_model_evidence=str(advanced),
            remote_connection_pack=str(connection),
            output_dir=str(output_dir),
        )
    )

    rows = read_records(output_dir / "q2b_action_board.jsonl")
    assert rows
    assert any(row["action_id"] == "provide_remote_connection:remote_host" for row in rows)
    assert (output_dir / "q2b_action_board_summary.jsonl").exists()


def test_cli_includes_build_q2b_action_board_command() -> None:
    """验证 CLI 暴露 build-q2b-action-board 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-q2b-action-board",
            "--submission-gates",
            "outputs/submission_gate_audit_fixture/submission_gate_audit.jsonl",
            "--remote-blueprint",
            "outputs/remote_execution_blueprint_fixture/remote_execution_blueprint.jsonl",
            "--journal-upgrade-plan",
            "outputs/journal_upgrade_plan_fixture/journal_upgrade_plan.jsonl",
            "--advanced-model-evidence",
            "outputs/advanced_model_evidence_fixture/advanced_model_evidence.jsonl",
            "--remote-connection-pack",
            "outputs/remote_connection_pack_fixture/remote_connection_pack.jsonl",
            "--output-dir",
            "outputs/q2b_action_board_fixture",
        ]
    )

    assert args.command == "build-q2b-action-board"
    assert args.remote_connection_pack == "outputs/remote_connection_pack_fixture/remote_connection_pack.jsonl"
    assert args.output_dir == "outputs/q2b_action_board_fixture"
