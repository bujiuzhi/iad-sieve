"""下一轮期刊实验队列生成模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "task_id",
    "priority",
    "resolves_gate",
    "requires_remote",
    "requires_secret",
    "command",
    "expected_outputs",
    "reviewer_value",
]
LOCAL_LLM_JUDGE_MODEL_PATH = "outputs/models/local_llm_judge"
LOCAL_LLM_JUDGE_MAX_NEW_TOKENS = 120
LOCAL_LLM_JUDGE_BATCH_SIZE = 16


def _read_readiness_rows(paths: list[str | Path]) -> list[dict]:
    """读取 readiness 报告。

    参数:
        paths: readiness JSONL 文件路径。

    返回:
        readiness 记录列表。
    """
    rows: list[dict] = []
    for path in paths:
        try:
            rows.extend(read_records(path))
        except Exception:
            LOGGER.exception("读取 readiness 报告失败: %s", path)
            raise
    return rows


def _needs_gate(rows: list[dict], gate_id: str) -> bool:
    """判断 readiness gate 是否仍需证据。

    参数:
        rows: readiness 记录。
        gate_id: gate ID。

    返回:
        需要证据返回 True。
    """
    return any(row.get("gate_id") == gate_id and row.get("status") != "evidence_ready" for row in rows)


def _task(
    task_id: str,
    priority: int,
    resolves_gate: str,
    requires_remote: bool,
    requires_secret: str,
    command: str,
    expected_outputs: str,
    reviewer_value: str,
) -> dict:
    """构造实验任务记录。

    参数:
        task_id: 任务 ID。
        priority: 优先级，数值越小越靠前。
        resolves_gate: 对应 readiness gate。
        requires_remote: 是否建议在远程/GPU 环境执行。
        requires_secret: 所需密钥环境变量；无则为空。
        command: 可执行命令。
        expected_outputs: 预期输出路径说明。
        reviewer_value: 审稿价值。

    返回:
        实验任务记录。
    """
    return {
        "task_id": task_id,
        "priority": priority,
        "resolves_gate": resolves_gate,
        "requires_remote": requires_remote,
        "requires_secret": requires_secret,
        "command": command,
        "expected_outputs": expected_outputs,
        "reviewer_value": reviewer_value,
    }


def _scholarly_balanced_gold_tasks() -> list[dict]:
    """构造 scholarly-only gold 主评估远程任务。

    参数:
        无。

    返回:
        scholarly-only gold 主评估与 source-held-out 任务列表。
    """
    return [
        _task(
            task_id="run_scincl_baseline_open_v3_scholarly_balanced_gold",
            priority=28,
            resolves_gate="executed_strong_baselines",
            requires_remote=True,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli run-representation-baseline "
                "--documents outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_documents.jsonl "
                "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
                "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_scores.jsonl "
                "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_execution_summary.jsonl "
                "--system-name scincl_cosine_open_v3_scholarly_balanced_gold "
                "--embedding-model malteos/scincl "
                "--model-backend sentence-transformers "
                "--batch-size 64 "
                "--score-field scincl_score"
            ),
            expected_outputs=(
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_scores.jsonl; "
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_execution_summary.jsonl"
            ),
            reviewer_value="在 scholarly-only 公开 gold 主评估集上补齐 SciNCL actual_model 表示 baseline。",
        ),
        _task(
            task_id="evaluate_scincl_baseline_open_v3_scholarly_balanced_gold",
            priority=29,
            resolves_gate="executed_strong_baselines",
            requires_remote=False,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli evaluate-external-baseline "
                "--relations outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
                "--baseline outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_scores.jsonl "
                "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_scored_relations.jsonl "
                "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_metric_summary.jsonl "
                "--system-name scincl_cosine_open_v3_scholarly_balanced_gold "
                "--score-field scincl_score "
                "--output-score-field scincl_score "
                "--thresholds 0.5,0.8,0.9 "
                "--metric-target same_work "
                "--baseline-family representation "
                "--execution-mode actual_model"
            ),
            expected_outputs=(
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_scored_relations.jsonl; "
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_metric_summary.jsonl"
            ),
            reviewer_value="用 same_work 统一口径评估 scholarly-only gold 上的 SciNCL baseline。",
        ),
        _task(
            task_id="bootstrap_scincl_baseline_open_v3_scholarly_balanced_gold",
            priority=30,
            resolves_gate="executed_strong_baselines",
            requires_remote=False,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli run-iad-evidence-bootstrap "
                "--records outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_scored_relations.jsonl "
                "--output outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/scincl_bootstrap_confidence.csv "
                "--system-name scincl_cosine_open_v3_scholarly_balanced_gold "
                "--score-field scincl_score "
                "--threshold 0.8 "
                "--iterations 1000 "
                "--confidence-level 0.95 "
                "--seed 42"
            ),
            expected_outputs="outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/scincl_bootstrap_confidence.csv",
            reviewer_value="为 scholarly-only gold 上的 SciNCL baseline 补充同阈值 bootstrap 置信区间。",
        ),
        _task(
            task_id="run_roberta_pair_baseline_open_v3_scholarly_balanced_gold",
            priority=30,
            resolves_gate="executed_strong_baselines",
            requires_remote=True,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli run-entity-matching-baseline "
                "--documents outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_documents.jsonl "
                "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
                "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_scores.jsonl "
                "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_execution_summary.jsonl "
                "--system-name roberta_pair_open_v3_scholarly_balanced_gold "
                "--model-name textattack/roberta-base-MRPC "
                "--model-backend transformers "
                "--batch-size 32 "
                "--score-field roberta_pair_score"
            ),
            expected_outputs=(
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_scores.jsonl; "
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_execution_summary.jsonl"
            ),
            reviewer_value="在 scholarly-only 公开 gold 主评估集上加入 cross-encoder/句对分类强 baseline。",
        ),
        _task(
            task_id="evaluate_roberta_pair_baseline_open_v3_scholarly_balanced_gold",
            priority=31,
            resolves_gate="executed_strong_baselines",
            requires_remote=False,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli evaluate-external-baseline "
                "--relations outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
                "--baseline outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_scores.jsonl "
                "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_scored_relations.jsonl "
                "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_metric_summary.jsonl "
                "--system-name roberta_pair_open_v3_scholarly_balanced_gold "
                "--score-field roberta_pair_score "
                "--output-score-field roberta_pair_score "
                "--thresholds 0.5,0.8,0.9 "
                "--metric-target same_work "
                "--baseline-family pair_classifier "
                "--execution-mode actual_model"
            ),
            expected_outputs=(
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_scored_relations.jsonl; "
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_metric_summary.jsonl"
            ),
            reviewer_value="用 same_work 统一口径评估 scholarly-only gold 上的 RoBERTa pair baseline。",
        ),
        _task(
            task_id="bootstrap_roberta_pair_baseline_open_v3_scholarly_balanced_gold",
            priority=32,
            resolves_gate="executed_strong_baselines",
            requires_remote=False,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli run-iad-evidence-bootstrap "
                "--records outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_scored_relations.jsonl "
                "--output outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/roberta_pair_bootstrap_confidence.csv "
                "--system-name roberta_pair_open_v3_scholarly_balanced_gold "
                "--score-field roberta_pair_score "
                "--threshold 0.8 "
                "--iterations 1000 "
                "--confidence-level 0.95 "
                "--seed 42"
            ),
            expected_outputs="outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/roberta_pair_bootstrap_confidence.csv",
            reviewer_value="为 scholarly-only gold 上的 RoBERTa pair baseline 补充同阈值 bootstrap 置信区间。",
        ),
        _task(
            task_id="run_scincl_provenance_blind_iad_risk_transformer_open_v3_scholarly_balanced_gold",
            priority=32,
            resolves_gate="model_depth",
            requires_remote=True,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli train-iad-risk-transformer-model "
                "--documents outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_documents.jsonl "
                "--relations outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
                "--output-dir outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold "
                "--system-name iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold "
                "--embedding-model malteos/scincl "
                "--model-backend sentence-transformers "
                "--batch-size 64 "
                "--train-split train "
                "--seed 7 "
                "--work-threshold 0.5 "
                "--agenda-block-threshold 0.5 "
                "--risk-threshold 0.5"
            ),
            expected_outputs=(
                "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold/iad_risk_transformer_summary.jsonl; "
                "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold/iad_risk_transformer_predictions.jsonl; "
                "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold/iad_risk_transformer_model.json"
            ),
            reviewer_value="把 IAD-Risk Transformer 放到 scholarly-only 公开 gold 主评估集上验证。",
        ),
        _task(
            task_id="bootstrap_scincl_provenance_blind_iad_risk_transformer_open_v3_scholarly_balanced_gold",
            priority=33,
            resolves_gate="model_depth",
            requires_remote=False,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli run-iad-evidence-bootstrap "
                "--records outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold/iad_risk_transformer_predictions.jsonl "
                "--output outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/iad_risk_transformer_scincl_bootstrap_confidence.csv "
                "--system-name iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold "
                "--prediction-field merge_prediction "
                "--iterations 1000 "
                "--confidence-level 0.95 "
                "--seed 42"
            ),
            expected_outputs="outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/iad_risk_transformer_scincl_bootstrap_confidence.csv",
            reviewer_value="为 scholarly-only gold 上的 IAD-Risk Transformer 补充分层 bootstrap 置信区间。",
        ),
        _task(
            task_id="apply_source_heldout_split_open_v3_scholarly_balanced_gold",
            priority=34,
            resolves_gate="source_held_out_generalization",
            requires_remote=False,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli apply-heldout-split-assignment "
                "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
                "--assignments outputs/open_v3_heldout_split_plan_scholarly_balanced_gold/open_v3_heldout_split_assignments.jsonl "
                "--split-strategy source_held_out "
                "--output-dir outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout"
            ),
            expected_outputs=(
                "outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl; "
                "outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/heldout_assignment_summary.jsonl"
            ),
            reviewer_value="把 scholarly-only source-held-out assignment 转成真实训练/测试 split。",
        ),
        _task(
            task_id="run_scincl_baseline_open_v3_scholarly_balanced_gold_source_heldout",
            priority=35,
            resolves_gate="source_held_out_generalization",
            requires_remote=True,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli run-representation-baseline "
                "--documents outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_documents.jsonl "
                "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_scores.jsonl "
                "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_execution_summary.jsonl "
                "--system-name scincl_cosine_open_v3_scholarly_balanced_gold_source_heldout "
                "--embedding-model malteos/scincl "
                "--model-backend sentence-transformers "
                "--batch-size 64 "
                "--score-field scincl_score"
            ),
            expected_outputs=(
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_scores.jsonl; "
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_execution_summary.jsonl"
            ),
            reviewer_value="补齐 scholarly-only source-held-out test split 上的 SciNCL actual_model baseline。",
        ),
        _task(
            task_id="evaluate_scincl_baseline_open_v3_scholarly_balanced_gold_source_heldout",
            priority=36,
            resolves_gate="source_held_out_generalization",
            requires_remote=False,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli evaluate-external-baseline "
                "--relations outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                "--baseline outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_scores.jsonl "
                "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_scored_relations.jsonl "
                "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_metric_summary.jsonl "
                "--system-name scincl_cosine_open_v3_scholarly_balanced_gold_source_heldout "
                "--score-field scincl_score "
                "--output-score-field scincl_score "
                "--thresholds 0.5,0.8,0.9 "
                "--metric-target same_work "
                "--baseline-family representation "
                "--execution-mode actual_model "
                "--split-field split --eval-splits test"
            ),
            expected_outputs=(
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_scored_relations.jsonl; "
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_metric_summary.jsonl"
            ),
            reviewer_value="只在 scholarly-only source-held-out test split 上报告 SciNCL 泛化指标。",
        ),
        _task(
            task_id="run_roberta_pair_baseline_open_v3_scholarly_balanced_gold_source_heldout",
            priority=37,
            resolves_gate="source_held_out_generalization",
            requires_remote=True,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli run-entity-matching-baseline "
                "--documents outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_documents.jsonl "
                "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_scores.jsonl "
                "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_execution_summary.jsonl "
                "--system-name roberta_pair_open_v3_scholarly_balanced_gold_source_heldout "
                "--model-name textattack/roberta-base-MRPC "
                "--model-backend transformers "
                "--batch-size 32 "
                "--score-field roberta_pair_score"
            ),
            expected_outputs=(
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_scores.jsonl; "
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_execution_summary.jsonl"
            ),
            reviewer_value="补齐 scholarly-only source-held-out test split 上的 RoBERTa pair actual_model baseline。",
        ),
        _task(
            task_id="evaluate_roberta_pair_baseline_open_v3_scholarly_balanced_gold_source_heldout",
            priority=38,
            resolves_gate="source_held_out_generalization",
            requires_remote=False,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli evaluate-external-baseline "
                "--relations outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                "--baseline outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_scores.jsonl "
                "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_scored_relations.jsonl "
                "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_metric_summary.jsonl "
                "--system-name roberta_pair_open_v3_scholarly_balanced_gold_source_heldout "
                "--score-field roberta_pair_score "
                "--output-score-field roberta_pair_score "
                "--thresholds 0.5,0.8,0.9 "
                "--metric-target same_work "
                "--baseline-family pair_classifier "
                "--execution-mode actual_model "
                "--split-field split --eval-splits test"
            ),
            expected_outputs=(
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_scored_relations.jsonl; "
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_metric_summary.jsonl"
            ),
            reviewer_value="只在 scholarly-only source-held-out test split 上报告 RoBERTa pair 泛化指标。",
        ),
        _task(
            task_id="train_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
            priority=39,
            resolves_gate="source_held_out_generalization",
            requires_remote=True,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli train-entity-matching-baseline "
                "--documents outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_documents.jsonl "
                "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                "--output-dir outputs/models/ditto_style_em_source_heldout "
                "--summary-output outputs/models/ditto_style_em_source_heldout_training_summary.jsonl "
                "--system-name ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout "
                "--base-model-name textattack/roberta-base-MRPC "
                "--train-split train "
                "--split-field split "
                "--label-field expected_label "
                "--batch-size 8 "
                "--epochs 1 "
                "--max-length 512 "
                "--seed 42"
            ),
            expected_outputs=(
                "outputs/models/ditto_style_em_source_heldout; "
                "outputs/models/ditto_style_em_source_heldout_training_summary.jsonl"
            ),
            reviewer_value="为 scholarly-only source-held-out 主轨道训练 Ditto-style EM 专用 checkpoint；未产出 checkpoint 前不得运行或报告 Ditto-style EM actual_model。",
        ),
        _task(
            task_id="run_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
            priority=40,
            resolves_gate="source_held_out_generalization",
            requires_remote=True,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli run-entity-matching-baseline "
                "--documents outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_documents.jsonl "
                "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_scores.jsonl "
                "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_execution_summary.jsonl "
                "--system-name ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout "
                "--model-name outputs/models/ditto_style_em_source_heldout "
                "--model-backend transformers "
                "--batch-size 16 "
                "--score-field ditto_match_probability"
            ),
            expected_outputs=(
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_scores.jsonl; "
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_execution_summary.jsonl"
            ),
            reviewer_value="为 scholarly-only source-held-out 主轨道接入 Ditto-style EM 专用 checkpoint 输出；未产出 actual_model 前不得写成 Ditto 已闭环。",
        ),
        _task(
            task_id="evaluate_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
            priority=41,
            resolves_gate="source_held_out_generalization",
            requires_remote=False,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli evaluate-external-baseline "
                "--relations outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                "--baseline outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_scores.jsonl "
                "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_scored_relations.jsonl "
                "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_metric_summary.jsonl "
                "--system-name ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout "
                "--score-field ditto_match_probability "
                "--output-score-field ditto_match_probability "
                "--thresholds 0.5,0.8,0.9 "
                "--metric-target same_work "
                "--baseline-family entity_matching "
                "--execution-mode actual_model "
                "--split-field split --eval-splits test"
            ),
            expected_outputs=(
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_scored_relations.jsonl; "
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_metric_summary.jsonl"
            ),
            reviewer_value="只在 scholarly-only source-held-out test split 上报告 Ditto-style EM 泛化指标。",
        ),
        _task(
            task_id="bootstrap_ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout",
            priority=42,
            resolves_gate="source_held_out_generalization",
            requires_remote=False,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli run-iad-evidence-bootstrap "
                "--records outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_scored_relations.jsonl "
                "--output outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/ditto_style_em_source_heldout_bootstrap_confidence.csv "
                "--system-name ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout "
                "--score-field ditto_match_probability "
                "--threshold 0.8 "
                "--iterations 1000 "
                "--confidence-level 0.95 "
                "--seed 42"
            ),
            expected_outputs="outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/ditto_style_em_source_heldout_bootstrap_confidence.csv",
            reviewer_value="为 scholarly-only source-held-out Ditto-style EM 补充分层 bootstrap 置信区间。",
        ),
        _task(
            task_id="run_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout",
            priority=43,
            resolves_gate="source_held_out_generalization",
            requires_remote=True,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli run-llm-judge-baseline "
                "--documents outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_documents.jsonl "
                "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_scores.jsonl "
                "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_execution_summary.jsonl "
                "--system-name gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout "
                f"--model-name {LOCAL_LLM_JUDGE_MODEL_PATH} "
                "--api-backend transformers "
                "--score-field gpt_same_work_probability "
                f"--max-new-tokens {LOCAL_LLM_JUDGE_MAX_NEW_TOKENS} "
                f"--batch-size {LOCAL_LLM_JUDGE_BATCH_SIZE} "
                "--timeout-seconds 30"
            ),
            expected_outputs=(
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_scores.jsonl; "
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_execution_summary.jsonl"
            ),
            reviewer_value="在 scholarly-only source-held-out test split 上补齐本地 Transformers LLM judge actual_model 强 baseline。",
        ),
        _task(
            task_id="evaluate_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout",
            priority=44,
            resolves_gate="source_held_out_generalization",
            requires_remote=False,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli evaluate-external-baseline "
                "--relations outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                "--baseline outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_scores.jsonl "
                "--output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_scored_relations.jsonl "
                "--summary-output outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_metric_summary.jsonl "
                "--system-name gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout "
                "--score-field gpt_same_work_probability "
                "--output-score-field gpt_same_work_probability "
                "--thresholds 0.5,0.8,0.9 "
                "--metric-target same_work "
                "--baseline-family llm_judge "
                "--execution-mode actual_model "
                "--split-field split --eval-splits test"
            ),
            expected_outputs=(
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_scored_relations.jsonl; "
                "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_metric_summary.jsonl"
            ),
            reviewer_value="只在 scholarly-only source-held-out test split 上报告 GPT/LLM judge 泛化指标。",
        ),
        _task(
            task_id="bootstrap_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout",
            priority=45,
            resolves_gate="source_held_out_generalization",
            requires_remote=False,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli run-iad-evidence-bootstrap "
                "--records outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_scored_relations.jsonl "
                "--output outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/gpt_pair_judge_source_heldout_bootstrap_confidence.csv "
                "--system-name gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout "
                "--score-field gpt_same_work_probability "
                "--threshold 0.8 "
                "--iterations 1000 "
                "--confidence-level 0.95 "
                "--seed 42"
            ),
            expected_outputs="outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/gpt_pair_judge_source_heldout_bootstrap_confidence.csv",
            reviewer_value="为 scholarly-only source-held-out GPT/LLM judge 补充分层 bootstrap 置信区间。",
        ),
        _task(
            task_id="run_scincl_iad_risk_transformer_open_v3_scholarly_balanced_gold_source_heldout",
            priority=46,
            resolves_gate="source_held_out_generalization",
            requires_remote=True,
            requires_secret="",
            command=(
                "python -m iad_sieve.cli train-iad-risk-transformer-model "
                "--documents outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_documents.jsonl "
                "--relations outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                "--output-dir outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout "
                "--system-name iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout "
                "--embedding-model malteos/scincl "
                "--model-backend sentence-transformers "
                "--batch-size 64 "
                "--train-split train "
                "--seed 7 "
                "--work-threshold 0.5 "
                "--agenda-block-threshold 0.5 "
                "--risk-threshold 0.5"
            ),
            expected_outputs=(
                "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout/iad_risk_transformer_summary.jsonl; "
                "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout/iad_risk_transformer_predictions.jsonl; "
                "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout/iad_risk_transformer_model.json"
            ),
            reviewer_value="验证 IAD-Risk Transformer 在 scholarly-only 未见公开来源上的泛化稳定性。",
        ),
    ]


def build_experiment_queue_rows(readiness_report_paths: list[str | Path]) -> list[dict]:
    """根据 readiness 报告生成下一轮实验队列。

    参数:
        readiness_report_paths: readiness JSONL 文件路径列表。

    返回:
        实验队列记录。
    """
    readiness_rows = _read_readiness_rows(readiness_report_paths)
    rows: list[dict] = []
    if _needs_gate(readiness_rows, "specter2_adapter_actual_model"):
        rows.extend(
            [
                _task(
                    task_id="run_specter2_adapter_baseline_open_v2",
                    priority=1,
                    resolves_gate="specter2_adapter_actual_model",
                    requires_remote=True,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli run-representation-baseline "
                        "--documents outputs/iad_bench_open_v2/iad_bench_documents.jsonl "
                        "--pairs outputs/iad_bench_open_v2/iad_bench_pairs.jsonl "
                        "--output outputs/strong_baseline_open_v2/specter2_adapter_scores.jsonl "
                        "--summary-output outputs/strong_baseline_open_v2/specter2_adapter_execution_summary.jsonl "
                        "--system-name specter2_adapter_cosine_open_v2 "
                        "--embedding-model allenai/specter2_base "
                        "--adapter-model allenai/specter2 "
                        "--model-backend specter2-adapter "
                        "--pooling-strategy cls "
                        "--batch-size 64 "
                        "--score-field specter2_adapter_score"
                    ),
                    expected_outputs=(
                        "outputs/strong_baseline_open_v2/specter2_adapter_scores.jsonl; "
                        "outputs/strong_baseline_open_v2/specter2_adapter_execution_summary.jsonl"
                    ),
                    reviewer_value="补齐官方 SPECTER2 adapter actual_model 表示 baseline。",
                ),
                _task(
                    task_id="evaluate_specter2_adapter_baseline_open_v2",
                    priority=2,
                    resolves_gate="specter2_adapter_actual_model",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli evaluate-external-baseline "
                        "--relations outputs/iad_bench_open_v2/iad_bench_pairs.jsonl "
                        "--baseline outputs/strong_baseline_open_v2/specter2_adapter_scores.jsonl "
                        "--output outputs/strong_baseline_open_v2/specter2_adapter_scored_relations.jsonl "
                        "--summary-output outputs/strong_baseline_open_v2/specter2_adapter_metric_summary.jsonl "
                        "--system-name specter2_adapter_cosine_open_v2 "
                        "--score-field specter2_adapter_score "
                        "--output-score-field specter2_adapter_score "
                        "--thresholds 0.5,0.8,0.9 "
                        "--metric-target same_work "
                        "--baseline-family representation "
                        "--execution-mode actual_model"
                    ),
                    expected_outputs=(
                        "outputs/strong_baseline_open_v2/specter2_adapter_scored_relations.jsonl; "
                        "outputs/strong_baseline_open_v2/specter2_adapter_metric_summary.jsonl"
                    ),
                    reviewer_value="把 SPECTER2 adapter 分数纳入统一 same_work 与 hard-negative 评价口径。",
                ),
                _task(
                    task_id="run_specter2_adapter_iad_risk_transformer_open_v2",
                    priority=4,
                    resolves_gate="specter2_adapter_actual_model",
                    requires_remote=True,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli train-iad-risk-transformer-model "
                        "--documents outputs/iad_bench_open_v2/iad_bench_documents.jsonl "
                        "--relations outputs/iad_bench_open_v2/iad_bench_pairs.jsonl "
                        "--output-dir outputs/iad_risk_transformer_specter2_open_v2 "
                        "--embedding-model allenai/specter2_base "
                        "--adapter-model allenai/specter2 "
                        "--model-backend specter2-adapter "
                        "--pooling-strategy cls "
                        "--batch-size 64 "
                        "--train-split train "
                        "--seed 7 "
                        "--work-threshold 0.5 "
                        "--agenda-block-threshold 0.5 "
                        "--risk-threshold 0.5"
                    ),
                    expected_outputs=(
                        "outputs/iad_risk_transformer_specter2_open_v2/iad_risk_transformer_summary.jsonl; "
                        "outputs/iad_risk_transformer_specter2_open_v2/iad_risk_transformer_predictions.jsonl; "
                        "outputs/iad_risk_transformer_specter2_open_v2/iad_risk_transformer_model.json"
                    ),
                    reviewer_value="验证 IAD-Risk Transformer 对不同科学文献 encoder 的稳定性。",
                ),
                _task(
                    task_id="bootstrap_specter2_adapter_baseline_open_v2",
                    priority=3,
                    resolves_gate="specter2_adapter_actual_model",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli run-iad-evidence-bootstrap "
                        "--records outputs/strong_baseline_open_v2/specter2_adapter_scored_relations.jsonl "
                        "--output outputs/iad_bootstrap_open_v2/specter2_adapter_bootstrap_confidence.csv "
                        "--system-name specter2_adapter_cosine_open_v2 "
                        "--score-field specter2_adapter_score "
                        "--threshold 0.8 "
                        "--iterations 1000 "
                        "--confidence-level 0.95 "
                        "--seed 42"
                    ),
                    expected_outputs="outputs/iad_bootstrap_open_v2/specter2_adapter_bootstrap_confidence.csv",
                    reviewer_value="为 SPECTER2 adapter baseline 补充分层 bootstrap 置信区间。",
                ),
                _task(
                    task_id="bootstrap_specter2_adapter_iad_risk_transformer_open_v2",
                    priority=5,
                    resolves_gate="specter2_adapter_actual_model",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli run-iad-evidence-bootstrap "
                        "--records outputs/iad_risk_transformer_specter2_open_v2/iad_risk_transformer_predictions.jsonl "
                        "--output outputs/iad_bootstrap_open_v2/iad_risk_transformer_specter2_bootstrap_confidence.csv "
                        "--system-name iad_risk_transformer_specter2_open_v2 "
                        "--prediction-field merge_prediction "
                        "--iterations 1000 "
                        "--confidence-level 0.95 "
                        "--seed 42"
                    ),
                    expected_outputs="outputs/iad_bootstrap_open_v2/iad_risk_transformer_specter2_bootstrap_confidence.csv",
                    reviewer_value="为 SPECTER2 adapter IAD-Risk Transformer 复核补充分层置信区间。",
                ),
            ]
        )
    if _needs_gate(readiness_rows, "llm_pair_judge_api_model"):
        rows.extend(
            [
                _task(
                    task_id="run_llm_pair_judge_api_model_open_v2",
                    priority=6,
                    resolves_gate="llm_pair_judge_api_model",
                    requires_remote=True,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli run-llm-judge-baseline "
                        "--documents outputs/iad_bench_open_v2/iad_bench_documents.jsonl "
                        "--pairs outputs/iad_bench_open_v2/iad_bench_pairs.jsonl "
                        "--output outputs/strong_baseline_open_v2/gpt_pair_judge_scores.jsonl "
                        "--summary-output outputs/strong_baseline_open_v2/gpt_pair_judge_execution_summary.jsonl "
                        "--system-name gpt_pair_judge_open_v2 "
                        f"--model-name {LOCAL_LLM_JUDGE_MODEL_PATH} "
                        "--api-backend transformers "
                        "--score-field gpt_same_work_probability "
                        f"--max-new-tokens {LOCAL_LLM_JUDGE_MAX_NEW_TOKENS} "
                        f"--batch-size {LOCAL_LLM_JUDGE_BATCH_SIZE} "
                        "--timeout-seconds 30"
                    ),
                    expected_outputs=(
                        "outputs/strong_baseline_open_v2/gpt_pair_judge_scores.jsonl; "
                        "outputs/strong_baseline_open_v2/gpt_pair_judge_execution_summary.jsonl"
                    ),
                    reviewer_value="补齐本地 Transformers LLM pair judge actual_model 强 baseline，避免只报告 fallback。",
                ),
                _task(
                    task_id="evaluate_llm_pair_judge_api_model_open_v2",
                    priority=7,
                    resolves_gate="llm_pair_judge_api_model",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli evaluate-external-baseline "
                        "--relations outputs/iad_bench_open_v2/iad_bench_pairs.jsonl "
                        "--baseline outputs/strong_baseline_open_v2/gpt_pair_judge_scores.jsonl "
                        "--output outputs/strong_baseline_open_v2/gpt_pair_judge_scored_relations.jsonl "
                        "--summary-output outputs/strong_baseline_open_v2/gpt_pair_judge_metric_summary.jsonl "
                        "--system-name gpt_pair_judge_open_v2 "
                        "--score-field gpt_same_work_probability "
                        "--output-score-field gpt_same_work_probability "
                        "--thresholds 0.5,0.8,0.9 "
                        "--metric-target same_work "
                        "--baseline-family llm_judge "
                        "--execution-mode actual_model"
                    ),
                    expected_outputs=(
                        "outputs/strong_baseline_open_v2/gpt_pair_judge_scored_relations.jsonl; "
                        "outputs/strong_baseline_open_v2/gpt_pair_judge_metric_summary.jsonl"
                    ),
                    reviewer_value="把本地 Transformers LLM actual_model 分数纳入统一 same_work 与 hard-negative 评价口径。",
                ),
                _task(
                    task_id="bootstrap_llm_pair_judge_api_model_open_v2",
                    priority=8,
                    resolves_gate="llm_pair_judge_api_model",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli run-iad-evidence-bootstrap "
                        "--records outputs/strong_baseline_open_v2/gpt_pair_judge_scored_relations.jsonl "
                        "--output outputs/iad_bootstrap_open_v2/gpt_pair_judge_bootstrap_confidence.csv "
                        "--system-name gpt_pair_judge_open_v2 "
                        "--score-field gpt_same_work_probability "
                        "--threshold 0.8 "
                        "--iterations 1000 "
                        "--confidence-level 0.95 "
                        "--seed 42"
                    ),
                    expected_outputs="outputs/iad_bootstrap_open_v2/gpt_pair_judge_bootstrap_confidence.csv",
                    reviewer_value="为本地 Transformers LLM baseline 补充分层 bootstrap 置信区间。",
                ),
            ]
        )
    if (
        _needs_gate(readiness_rows, "venue_readiness")
        or _needs_gate(readiness_rows, "executed_strong_baselines")
        or _needs_gate(readiness_rows, "overall_q2_b_readiness")
    ):
        rows.extend(
            [
                _task(
                    task_id="run_scincl_provenance_blind_iad_risk_transformer_open_v2",
                    priority=9,
                    resolves_gate="feature_guard_provenance_blind",
                    requires_remote=True,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli train-iad-risk-transformer-model "
                        "--documents outputs/iad_bench_open_v2/iad_bench_documents.jsonl "
                        "--relations outputs/iad_bench_open_v2/iad_bench_pairs.jsonl "
                        "--output-dir outputs/iad_risk_transformer_scincl_provenance_blind_open_v2 "
                        "--system-name iad_risk_transformer_scincl_provenance_blind_open_v2 "
                        "--embedding-model malteos/scincl "
                        "--model-backend sentence-transformers "
                        "--batch-size 64 "
                        "--train-split train "
                        "--seed 7 "
                        "--work-threshold 0.5 "
                        "--agenda-block-threshold 0.5 "
                        "--risk-threshold 0.5"
                    ),
                    expected_outputs=(
                        "outputs/iad_risk_transformer_scincl_provenance_blind_open_v2/iad_risk_transformer_summary.jsonl; "
                        "outputs/iad_risk_transformer_scincl_provenance_blind_open_v2/iad_risk_transformer_predictions.jsonl; "
                        "outputs/iad_risk_transformer_scincl_provenance_blind_open_v2/iad_risk_transformer_model.json"
                    ),
                    reviewer_value="重训移除 provenance shortcut 特征后的 SciNCL IAD-Risk Transformer actual_model。",
                ),
                _task(
                    task_id="bootstrap_scincl_provenance_blind_iad_risk_transformer_open_v2",
                    priority=10,
                    resolves_gate="feature_guard_provenance_blind",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli run-iad-evidence-bootstrap "
                        "--records outputs/iad_risk_transformer_scincl_provenance_blind_open_v2/iad_risk_transformer_predictions.jsonl "
                        "--output outputs/iad_bootstrap_open_v2/iad_risk_transformer_scincl_provenance_blind_bootstrap_confidence.csv "
                        "--system-name iad_risk_transformer_scincl_provenance_blind_open_v2 "
                        "--prediction-field merge_prediction "
                        "--iterations 1000 "
                        "--confidence-level 0.95 "
                        "--seed 42"
                    ),
                    expected_outputs="outputs/iad_bootstrap_open_v2/iad_risk_transformer_scincl_provenance_blind_bootstrap_confidence.csv",
                    reviewer_value="为 provenance-blind SciNCL IAD-Risk Transformer 补充分层 bootstrap 置信区间。",
                ),
                _task(
                    task_id="run_scincl_baseline_open_v3_balanced_gold",
                    priority=11,
                    resolves_gate="executed_strong_baselines",
                    requires_remote=True,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli run-representation-baseline "
                        "--documents outputs/iad_bench_open_v3_balanced_gold/iad_bench_documents.jsonl "
                        "--pairs outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl "
                        "--output outputs/strong_baseline_open_v3_balanced_gold/scincl_scores.jsonl "
                        "--summary-output outputs/strong_baseline_open_v3_balanced_gold/scincl_execution_summary.jsonl "
                        "--system-name scincl_cosine_open_v3_balanced_gold "
                        "--embedding-model malteos/scincl "
                        "--model-backend sentence-transformers "
                        "--batch-size 64 "
                        "--score-field scincl_score"
                    ),
                    expected_outputs=(
                        "outputs/strong_baseline_open_v3_balanced_gold/scincl_scores.jsonl; "
                        "outputs/strong_baseline_open_v3_balanced_gold/scincl_execution_summary.jsonl"
                    ),
                    reviewer_value="在来源平衡的公开 gold 主评估集上补齐 SciNCL actual_model 表示 baseline。",
                ),
                _task(
                    task_id="evaluate_scincl_baseline_open_v3_balanced_gold",
                    priority=12,
                    resolves_gate="executed_strong_baselines",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli evaluate-external-baseline "
                        "--relations outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl "
                        "--baseline outputs/strong_baseline_open_v3_balanced_gold/scincl_scores.jsonl "
                        "--output outputs/strong_baseline_open_v3_balanced_gold/scincl_scored_relations.jsonl "
                        "--summary-output outputs/strong_baseline_open_v3_balanced_gold/scincl_metric_summary.jsonl "
                        "--system-name scincl_cosine_open_v3_balanced_gold "
                        "--score-field scincl_score "
                        "--output-score-field scincl_score "
                        "--thresholds 0.5,0.8,0.9 "
                        "--metric-target same_work "
                        "--baseline-family representation "
                        "--execution-mode actual_model"
                    ),
                    expected_outputs=(
                        "outputs/strong_baseline_open_v3_balanced_gold/scincl_scored_relations.jsonl; "
                        "outputs/strong_baseline_open_v3_balanced_gold/scincl_metric_summary.jsonl"
                    ),
                    reviewer_value="用 same_work 统一口径评估 balanced gold 上的 SciNCL baseline。",
                ),
                _task(
                    task_id="run_roberta_pair_baseline_open_v3_balanced_gold",
                    priority=13,
                    resolves_gate="executed_strong_baselines",
                    requires_remote=True,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli run-entity-matching-baseline "
                        "--documents outputs/iad_bench_open_v3_balanced_gold/iad_bench_documents.jsonl "
                        "--pairs outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl "
                        "--output outputs/strong_baseline_open_v3_balanced_gold/roberta_pair_scores.jsonl "
                        "--summary-output outputs/strong_baseline_open_v3_balanced_gold/roberta_pair_execution_summary.jsonl "
                        "--system-name roberta_pair_open_v3_balanced_gold "
                        "--model-name textattack/roberta-base-MRPC "
                        "--model-backend transformers "
                        "--batch-size 32 "
                        "--score-field roberta_pair_score"
                    ),
                    expected_outputs=(
                        "outputs/strong_baseline_open_v3_balanced_gold/roberta_pair_scores.jsonl; "
                        "outputs/strong_baseline_open_v3_balanced_gold/roberta_pair_execution_summary.jsonl"
                    ),
                    reviewer_value="在公开 gold 主评估集上加入 cross-encoder/句对分类强 baseline。",
                ),
                _task(
                    task_id="evaluate_roberta_pair_baseline_open_v3_balanced_gold",
                    priority=14,
                    resolves_gate="executed_strong_baselines",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli evaluate-external-baseline "
                        "--relations outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl "
                        "--baseline outputs/strong_baseline_open_v3_balanced_gold/roberta_pair_scores.jsonl "
                        "--output outputs/strong_baseline_open_v3_balanced_gold/roberta_pair_scored_relations.jsonl "
                        "--summary-output outputs/strong_baseline_open_v3_balanced_gold/roberta_pair_metric_summary.jsonl "
                        "--system-name roberta_pair_open_v3_balanced_gold "
                        "--score-field roberta_pair_score "
                        "--output-score-field roberta_pair_score "
                        "--thresholds 0.5,0.8,0.9 "
                        "--metric-target same_work "
                        "--baseline-family pair_classifier "
                        "--execution-mode actual_model"
                    ),
                    expected_outputs=(
                        "outputs/strong_baseline_open_v3_balanced_gold/roberta_pair_scored_relations.jsonl; "
                        "outputs/strong_baseline_open_v3_balanced_gold/roberta_pair_metric_summary.jsonl"
                    ),
                    reviewer_value="用 same_work 统一口径评估 balanced gold 上的 RoBERTa pair baseline。",
                ),
                _task(
                    task_id="run_scincl_provenance_blind_iad_risk_transformer_open_v3_balanced_gold",
                    priority=15,
                    resolves_gate="model_depth",
                    requires_remote=True,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli train-iad-risk-transformer-model "
                        "--documents outputs/iad_bench_open_v3_balanced_gold/iad_bench_documents.jsonl "
                        "--relations outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl "
                        "--output-dir outputs/iad_risk_transformer_scincl_open_v3_balanced_gold "
                        "--system-name iad_risk_transformer_scincl_open_v3_balanced_gold "
                        "--embedding-model malteos/scincl "
                        "--model-backend sentence-transformers "
                        "--batch-size 64 "
                        "--train-split train "
                        "--seed 7 "
                        "--work-threshold 0.5 "
                        "--agenda-block-threshold 0.5 "
                        "--risk-threshold 0.5"
                    ),
                    expected_outputs=(
                        "outputs/iad_risk_transformer_scincl_open_v3_balanced_gold/iad_risk_transformer_summary.jsonl; "
                        "outputs/iad_risk_transformer_scincl_open_v3_balanced_gold/iad_risk_transformer_predictions.jsonl; "
                        "outputs/iad_risk_transformer_scincl_open_v3_balanced_gold/iad_risk_transformer_model.json"
                    ),
                    reviewer_value="把 IAD-Risk Transformer 放到公开 gold balanced 主评估集上重新验证。",
                ),
                _task(
                    task_id="bootstrap_scincl_provenance_blind_iad_risk_transformer_open_v3_balanced_gold",
                    priority=16,
                    resolves_gate="model_depth",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli run-iad-evidence-bootstrap "
                        "--records outputs/iad_risk_transformer_scincl_open_v3_balanced_gold/iad_risk_transformer_predictions.jsonl "
                        "--output outputs/iad_bootstrap_open_v3_balanced_gold/iad_risk_transformer_scincl_bootstrap_confidence.csv "
                        "--system-name iad_risk_transformer_scincl_open_v3_balanced_gold "
                        "--prediction-field merge_prediction "
                        "--iterations 1000 "
                        "--confidence-level 0.95 "
                        "--seed 42"
                    ),
                    expected_outputs="outputs/iad_bootstrap_open_v3_balanced_gold/iad_risk_transformer_scincl_bootstrap_confidence.csv",
                    reviewer_value="为 balanced gold 上的 IAD-Risk Transformer 补充分层 bootstrap 置信区间。",
                ),
                _task(
                    task_id="apply_source_heldout_split_open_v3_balanced_gold",
                    priority=17,
                    resolves_gate="source_held_out_generalization",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli apply-heldout-split-assignment "
                        "--pairs outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl "
                        "--assignments outputs/open_v3_heldout_split_plan_balanced_gold/open_v3_heldout_split_assignments.jsonl "
                        "--split-strategy source_held_out "
                        "--output-dir outputs/iad_bench_open_v3_balanced_gold_source_heldout"
                    ),
                    expected_outputs=(
                        "outputs/iad_bench_open_v3_balanced_gold_source_heldout/iad_bench_pairs.jsonl; "
                        "outputs/iad_bench_open_v3_balanced_gold_source_heldout/heldout_assignment_summary.jsonl"
                    ),
                    reviewer_value="把 source-held-out assignment 转成真实训练/测试 split，避免只停留在计划层。",
                ),
                _task(
                    task_id="score_source_heldout_gold_pairs_for_iad_training_open_v3",
                    priority=18,
                    resolves_gate="model_training_input",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli score-eval-set "
                        "--documents outputs/iad_bench_open_v3_balanced_gold/iad_bench_documents.jsonl "
                        "--pairs outputs/iad_bench_open_v3_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                        "--output outputs/iad_bench_open_v3_balanced_gold_source_heldout/scored_relations.jsonl "
                        "--summary-output outputs/iad_bench_open_v3_balanced_gold_source_heldout/scored_relation_summary.jsonl"
                    ),
                    expected_outputs=(
                        "outputs/iad_bench_open_v3_balanced_gold_source_heldout/scored_relations.jsonl; "
                        "outputs/iad_bench_open_v3_balanced_gold_source_heldout/scored_relation_summary.jsonl"
                    ),
                    reviewer_value="把 gold source-held-out pair 转为可学习 IAD 特征，避免 raw pair 直接训练。",
                ),
                _task(
                    task_id="build_gold_silver_iad_training_blend_open_v3",
                    priority=19,
                    resolves_gate="model_training_input",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli build-iad-training-blend "
                        "--relations outputs/iad_bench_open_v3_balanced_gold_source_heldout/scored_relations.jsonl "
                        "outputs/openalex_api_v1/scored_relations.jsonl "
                        "--output-dir outputs/iad_training_blend_open_v3_gold_silver "
                        "--relation-labels same_work,unrelated,agenda_non_identity "
                        "--seed 7"
                    ),
                    expected_outputs=(
                        "outputs/iad_training_blend_open_v3_gold_silver/iad_training_relations.jsonl; "
                        "outputs/iad_training_blend_open_v3_gold_silver/iad_training_blend_summary.jsonl"
                    ),
                    reviewer_value="用公开 gold 覆盖 same_work/unrelated，用 OpenAlex silver 覆盖 agenda_non_identity，形成可训练但边界清晰的 IAD-Risk 输入。",
                ),
                _task(
                    task_id="audit_gold_silver_iad_training_input_open_v3",
                    priority=20,
                    resolves_gate="model_training_input",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli build-iad-training-input-audit "
                        "--relations outputs/iad_training_blend_open_v3_gold_silver/iad_training_relations.jsonl "
                        "--output-dir outputs/iad_training_input_audit_open_v3_gold_silver"
                    ),
                    expected_outputs=(
                        "outputs/iad_training_input_audit_open_v3_gold_silver/iad_training_input_audit.jsonl; "
                        "outputs/iad_training_input_audit_open_v3_gold_silver/iad_training_input_audit_summary.jsonl"
                    ),
                    reviewer_value="证明混合训练输入包含 identity/agenda/risk 特征和必要 head 正负样本。",
                ),
                _task(
                    task_id="train_lightweight_iad_risk_open_v3_gold_silver",
                    priority=21,
                    resolves_gate="model_training_input",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli train-iad-risk-model "
                        "--relations outputs/iad_training_blend_open_v3_gold_silver/iad_training_relations.jsonl "
                        "--output-dir outputs/iad_risk_open_v3_gold_silver "
                        "--train-split train "
                        "--eval-splits all,train,test "
                        "--seed 7 "
                        "--work-threshold 0.5 "
                        "--agenda-block-threshold 0.5 "
                        "--risk-threshold 0.5"
                    ),
                    expected_outputs=(
                        "outputs/iad_risk_open_v3_gold_silver/iad_risk_model.json; "
                        "outputs/iad_risk_open_v3_gold_silver/iad_risk_summary.jsonl; "
                        "outputs/iad_risk_open_v3_gold_silver/iad_risk_predictions.jsonl"
                    ),
                    reviewer_value="先用本地轻量模型验证完整 IAD-Risk head 能训练，强模型结果仍由远程任务补齐。",
                ),
                _task(
                    task_id="audit_lightweight_iad_risk_split_open_v3_gold_silver",
                    priority=22,
                    resolves_gate="model_training_input",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli build-iad-risk-split-evaluation-audit "
                        "--iad-risk-summary outputs/iad_risk_open_v3_gold_silver/iad_risk_summary.jsonl "
                        "--iad-risk-model outputs/iad_risk_open_v3_gold_silver/iad_risk_model.json "
                        "--output-dir outputs/iad_risk_split_evaluation_audit_open_v3_gold_silver"
                    ),
                    expected_outputs=(
                        "outputs/iad_risk_split_evaluation_audit_open_v3_gold_silver/iad_risk_split_evaluation_audit.jsonl; "
                        "outputs/iad_risk_split_evaluation_audit_open_v3_gold_silver/iad_risk_split_evaluation_audit_summary.jsonl"
                    ),
                    reviewer_value="审计轻量 IAD-Risk 是否仅能作为 gold+silver split 诊断，而非最终强泛化证据。",
                ),
                _task(
                    task_id="run_scincl_baseline_open_v3_balanced_gold_source_heldout",
                    priority=23,
                    resolves_gate="source_held_out_generalization",
                    requires_remote=True,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli run-representation-baseline "
                        "--documents outputs/iad_bench_open_v3_balanced_gold/iad_bench_documents.jsonl "
                        "--pairs outputs/iad_bench_open_v3_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                        "--output outputs/strong_baseline_open_v3_balanced_gold_source_heldout/scincl_scores.jsonl "
                        "--summary-output outputs/strong_baseline_open_v3_balanced_gold_source_heldout/scincl_execution_summary.jsonl "
                        "--system-name scincl_cosine_open_v3_balanced_gold_source_heldout "
                        "--embedding-model malteos/scincl "
                        "--model-backend sentence-transformers "
                        "--batch-size 64 "
                        "--score-field scincl_score"
                    ),
                    expected_outputs=(
                        "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/scincl_scores.jsonl; "
                        "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/scincl_execution_summary.jsonl"
                    ),
                    reviewer_value="补齐 source-held-out test split 上的 SciNCL actual_model baseline。",
                ),
                _task(
                    task_id="evaluate_scincl_baseline_open_v3_balanced_gold_source_heldout",
                    priority=24,
                    resolves_gate="source_held_out_generalization",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli evaluate-external-baseline "
                        "--relations outputs/iad_bench_open_v3_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                        "--baseline outputs/strong_baseline_open_v3_balanced_gold_source_heldout/scincl_scores.jsonl "
                        "--output outputs/strong_baseline_open_v3_balanced_gold_source_heldout/scincl_scored_relations.jsonl "
                        "--summary-output outputs/strong_baseline_open_v3_balanced_gold_source_heldout/scincl_metric_summary.jsonl "
                        "--system-name scincl_cosine_open_v3_balanced_gold_source_heldout "
                        "--score-field scincl_score "
                        "--output-score-field scincl_score "
                        "--thresholds 0.5,0.8,0.9 "
                        "--metric-target same_work "
                        "--baseline-family representation "
                        "--execution-mode actual_model "
                        "--split-field split --eval-splits test"
                    ),
                    expected_outputs=(
                        "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/scincl_scored_relations.jsonl; "
                        "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/scincl_metric_summary.jsonl"
                    ),
                    reviewer_value="只在 source-held-out test split 上报告 SciNCL 泛化指标。",
                ),
                _task(
                    task_id="run_roberta_pair_baseline_open_v3_balanced_gold_source_heldout",
                    priority=25,
                    resolves_gate="source_held_out_generalization",
                    requires_remote=True,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli run-entity-matching-baseline "
                        "--documents outputs/iad_bench_open_v3_balanced_gold/iad_bench_documents.jsonl "
                        "--pairs outputs/iad_bench_open_v3_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                        "--output outputs/strong_baseline_open_v3_balanced_gold_source_heldout/roberta_pair_scores.jsonl "
                        "--summary-output outputs/strong_baseline_open_v3_balanced_gold_source_heldout/roberta_pair_execution_summary.jsonl "
                        "--system-name roberta_pair_open_v3_balanced_gold_source_heldout "
                        "--model-name textattack/roberta-base-MRPC "
                        "--model-backend transformers "
                        "--batch-size 32 "
                        "--score-field roberta_pair_score"
                    ),
                    expected_outputs=(
                        "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/roberta_pair_scores.jsonl; "
                        "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/roberta_pair_execution_summary.jsonl"
                    ),
                    reviewer_value="补齐 source-held-out test split 上的 RoBERTa pair actual_model baseline。",
                ),
                _task(
                    task_id="evaluate_roberta_pair_baseline_open_v3_balanced_gold_source_heldout",
                    priority=26,
                    resolves_gate="source_held_out_generalization",
                    requires_remote=False,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli evaluate-external-baseline "
                        "--relations outputs/iad_bench_open_v3_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                        "--baseline outputs/strong_baseline_open_v3_balanced_gold_source_heldout/roberta_pair_scores.jsonl "
                        "--output outputs/strong_baseline_open_v3_balanced_gold_source_heldout/roberta_pair_scored_relations.jsonl "
                        "--summary-output outputs/strong_baseline_open_v3_balanced_gold_source_heldout/roberta_pair_metric_summary.jsonl "
                        "--system-name roberta_pair_open_v3_balanced_gold_source_heldout "
                        "--score-field roberta_pair_score "
                        "--output-score-field roberta_pair_score "
                        "--thresholds 0.5,0.8,0.9 "
                        "--metric-target same_work "
                        "--baseline-family pair_classifier "
                        "--execution-mode actual_model "
                        "--split-field split --eval-splits test"
                    ),
                    expected_outputs=(
                        "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/roberta_pair_scored_relations.jsonl; "
                        "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/roberta_pair_metric_summary.jsonl"
                    ),
                    reviewer_value="只在 source-held-out test split 上报告 RoBERTa pair 泛化指标。",
                ),
                _task(
                    task_id="run_scincl_iad_risk_transformer_open_v3_balanced_gold_source_heldout",
                    priority=27,
                    resolves_gate="source_held_out_generalization",
                    requires_remote=True,
                    requires_secret="",
                    command=(
                        "python -m iad_sieve.cli train-iad-risk-transformer-model "
                        "--documents outputs/iad_bench_open_v3_balanced_gold/iad_bench_documents.jsonl "
                        "--relations outputs/iad_bench_open_v3_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                        "--output-dir outputs/iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout "
                        "--system-name iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout "
                        "--embedding-model malteos/scincl "
                        "--model-backend sentence-transformers "
                        "--batch-size 64 "
                        "--train-split train "
                        "--seed 7 "
                        "--work-threshold 0.5 "
                        "--agenda-block-threshold 0.5 "
                        "--risk-threshold 0.5"
                    ),
                    expected_outputs=(
                        "outputs/iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout/iad_risk_transformer_summary.jsonl; "
                        "outputs/iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout/iad_risk_transformer_predictions.jsonl; "
                        "outputs/iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout/iad_risk_transformer_model.json"
                    ),
                    reviewer_value="验证 IAD-Risk Transformer 在未见公开来源上的泛化稳定性。",
                ),
            ]
        )
        rows.extend(_scholarly_balanced_gold_tasks())
    if _needs_gate(readiness_rows, "venue_readiness") or _needs_gate(readiness_rows, "executed_strong_baselines"):
        rows.append(
            _task(
                task_id="rebuild_evidence_package_after_strong_baselines",
                priority=99,
                resolves_gate="venue_readiness",
                requires_remote=False,
                requires_secret="",
                command=(
                    "python -m iad_sieve.cli build-iad-paper-report "
                    "--output-dir outputs/iad_paper_report_fixture "
                    "--gold-summaries outputs/deepmatcher_fixture/summary.jsonl outputs/deepmatcher_public_dblp_acm/summary.jsonl "
                    "--proxy-summaries outputs/scirepeval_fixture/summary.jsonl "
                    "--weak-summaries outputs/openalex_fixture/summary.jsonl outputs/openalex_api_v1/summary.jsonl "
                    "--external-summaries outputs/external_baseline_fixture/specter2_summary.jsonl outputs/external_baseline_fixture/ditto_summary.jsonl "
                    "outputs/strong_baseline_fixture/scincl_metric_summary.jsonl outputs/strong_baseline_fixture/distilbert_mrpc_metric_summary.jsonl "
                    "outputs/strong_baseline_fixture/roberta_pair_metric_summary.jsonl outputs/strong_baseline_fixture/llm_fallback_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v2/scincl_metric_summary.jsonl outputs/strong_baseline_open_v2/distilbert_mrpc_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v2/roberta_pair_metric_summary.jsonl outputs/strong_baseline_open_v2/specter2_adapter_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v2/gpt_pair_judge_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_balanced_gold/scincl_metric_summary.jsonl outputs/strong_baseline_open_v3_balanced_gold/roberta_pair_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_metric_summary.jsonl outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/scincl_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/roberta_pair_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_metric_summary.jsonl "
                    "--classifier-summaries outputs/iad_classifier_fixture/training_summary.jsonl "
                    "--ablation-summaries outputs/iad_ablation_fixture/iad_ablation_summary.jsonl outputs/iad_ablation_openalex_v1/iad_ablation_summary.jsonl outputs/iad_ablation_open_v2/iad_ablation_summary.jsonl "
                    "--iad-bench-summaries outputs/iad_bench_fixture/iad_bench_summary.jsonl outputs/iad_bench_open_v1/iad_bench_summary.jsonl outputs/iad_bench_open_v2/iad_bench_summary.jsonl "
                    "outputs/iad_bench_open_v3/iad_bench_summary.jsonl outputs/iad_bench_open_v3_balanced_gold/iad_bench_summary.jsonl "
                    "outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_summary.jsonl "
                    "--iad-risk-summaries outputs/iad_risk_model_fixture/iad_risk_summary.jsonl outputs/iad_risk_openalex_v1/iad_risk_summary.jsonl "
                    "outputs/iad_risk_open_v2/iad_risk_summary.jsonl outputs/iad_risk_transformer_open_v2/iad_risk_transformer_summary.jsonl "
                    "outputs/iad_risk_transformer_scincl_provenance_blind_open_v2/iad_risk_transformer_summary.jsonl "
                    "outputs/iad_risk_transformer_specter2_open_v2/iad_risk_transformer_summary.jsonl "
                    "outputs/iad_risk_transformer_scincl_open_v3_balanced_gold/iad_risk_transformer_summary.jsonl "
                    "outputs/iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout/iad_risk_transformer_summary.jsonl "
                    "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold/iad_risk_transformer_summary.jsonl "
                    "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout/iad_risk_transformer_summary.jsonl "
                    "--bootstrap-summaries outputs/iad_bootstrap_fixture/iad_risk_bootstrap_confidence.csv outputs/iad_bootstrap_fixture/scincl_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_fixture/roberta_pair_bootstrap_confidence.csv outputs/iad_bootstrap_fixture/scincl_single_space_union_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_openalex_v1/iad_risk_bootstrap_confidence.csv outputs/iad_bootstrap_openalex_v1/review_inclusive_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v2/iad_risk_bootstrap_confidence.csv outputs/iad_bootstrap_open_v2/iad_risk_transformer_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v2/iad_risk_transformer_scincl_provenance_blind_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v2/iad_risk_transformer_specter2_bootstrap_confidence.csv outputs/iad_bootstrap_open_v2/scincl_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v2/distilbert_mrpc_bootstrap_confidence.csv outputs/iad_bootstrap_open_v2/roberta_pair_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v2/specter2_adapter_bootstrap_confidence.csv outputs/iad_bootstrap_open_v2/gpt_pair_judge_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v2/scincl_single_space_union_bootstrap_confidence.csv outputs/iad_bootstrap_open_v2/deepmatcher_rule_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v2/openalex_rule_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v3_balanced_gold/iad_risk_transformer_scincl_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/iad_risk_transformer_scincl_bootstrap_confidence.csv "
                    "--openalex-ingestion-summaries outputs/openalex_api_ingestion_fixture/ingestion_summary.jsonl outputs/openalex_api_ingestion_v1/ingestion_summary.jsonl "
                    "--openalex-dataset-summaries outputs/openalex_api_fixture/dataset_summary.jsonl outputs/openalex_api_v1/dataset_summary.jsonl "
                    "--human-audit-plans docs/annotation-requirements.md && "
                    "python -m iad_sieve.cli build-reviewer-audit "
                    "--rq-summaries outputs/iad_paper_report_fixture/rq_summary.jsonl "
                    "--output-dir outputs/reviewer_audit_fixture && "
                    "python -m iad_sieve.cli build-journal-readiness "
                    "--rq-summaries outputs/iad_paper_report_fixture/rq_summary.jsonl "
                    "--reviewer-audits outputs/reviewer_audit_fixture/reviewer_audit.jsonl "
                    "--output-dir outputs/journal_readiness_fixture && "
                    "python -m iad_sieve.cli build-experiment-queue "
                    "--readiness-reports outputs/journal_readiness_fixture/journal_readiness.jsonl "
                    "--output-dir outputs/experiment_queue_fixture && "
                    "python -m iad_sieve.cli check-experiment-queue "
                    "--queue outputs/experiment_queue_fixture/experiment_queue.jsonl "
                    "--output-dir outputs/experiment_preflight_fixture "
                    "--workspace-dir . && "
                    "python -m iad_sieve.cli build-experiment-dependency "
                    "--queue outputs/experiment_queue_fixture/experiment_queue.jsonl "
                    "--preflight outputs/experiment_preflight_fixture/experiment_preflight.jsonl "
                    "--output-dir outputs/experiment_dependency_fixture && "
                    "python -m iad_sieve.cli build-experiment-execution-pack "
                    "--queue outputs/experiment_queue_fixture/experiment_queue.jsonl "
                    "--preflight outputs/experiment_preflight_fixture/experiment_preflight.jsonl "
                    "--dependency outputs/experiment_dependency_fixture/experiment_dependency.jsonl "
                    "--output-dir outputs/experiment_execution_pack_fixture && "
                    "python -m iad_sieve.cli validate-remote-outputs "
                    "--manifest outputs/experiment_execution_pack_fixture/remote_output_manifest.jsonl "
                    "--workspace-dir . "
                    "--output-dir outputs/remote_output_validation_fixture && "
                    "python -m iad_sieve.cli build-remote-result-acceptance "
                    "--execution-plan outputs/experiment_execution_pack_fixture/experiment_execution_plan.jsonl "
                    "--remote-output-validation outputs/remote_output_validation_fixture/remote_output_validation.jsonl "
                    "--output-dir outputs/remote_result_acceptance_fixture && "
                    "python -m iad_sieve.cli build-remote-environment-audit "
                    "--output-dir outputs/remote_environment_audit_fixture && "
                    "python -m iad_sieve.cli build-remote-execution-blueprint "
                    "--execution-plan outputs/experiment_execution_pack_fixture/experiment_execution_plan.jsonl "
                    "--environment-audit outputs/remote_environment_audit_fixture/remote_environment_audit.jsonl "
                    "--remote-output-validation outputs/remote_output_validation_fixture/remote_output_validation.jsonl "
                    "--output-dir outputs/remote_execution_blueprint_fixture && "
                    "python -m iad_sieve.cli build-remote-connection-pack "
                    "--execution-plan outputs/experiment_execution_pack_fixture/experiment_execution_plan.jsonl "
                    "--remote-blueprint outputs/remote_execution_blueprint_fixture/remote_execution_blueprint.jsonl "
                    "--profile outputs/remote_connection_profile.local.json "
                    "--output-dir outputs/remote_connection_pack_fixture && "
                    "python -m iad_sieve.cli build-paper-claim-audit "
                    "--rq-summaries outputs/iad_paper_report_fixture/rq_summary.jsonl "
                    "--readiness-reports outputs/journal_readiness_fixture/journal_readiness.jsonl "
                    "--dependency-reports outputs/experiment_dependency_fixture/experiment_dependency.jsonl "
                    "--output-dir outputs/paper_claim_audit_fixture && "
                    "python -m iad_sieve.cli build-research-depth-audit "
                    "--reviewer-audits outputs/reviewer_audit_fixture/reviewer_audit.jsonl "
                    "--claim-audits outputs/paper_claim_audit_fixture/paper_claim_audit.jsonl "
                    "--readiness-reports outputs/journal_readiness_fixture/journal_readiness.jsonl "
                    "--dependency-reports outputs/experiment_dependency_fixture/experiment_dependency.jsonl "
                    "--output-dir outputs/research_depth_audit_fixture && "
                    "python -m iad_sieve.cli build-iad-bench-source-bias-diagnostic "
                    "--pairs outputs/iad_bench_open_v2/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_bench_source_bias_diagnostic_fixture "
                    "--train-split train "
                    "--eval-splits dev,test "
                    "--max-shortcut-accuracy 0.8 && "
                    "python -m iad_sieve.cli build-iad-bench-provenance-balance-plan "
                    "--pairs outputs/iad_bench_open_v2/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_bench_provenance_balance_plan_fixture "
                    "--min-sources-per-relation 2 "
                    "--max-dominant-source-ratio 0.8 "
                    "--target-pairs-per-new-source 500 && "
                    "python -m iad_sieve.cli build-iad-bench-source-candidate-registry "
                    "--provenance-balance-plan outputs/iad_bench_provenance_balance_plan_fixture/iad_bench_provenance_balance_plan.jsonl "
                    "--output-dir outputs/iad_bench_source_candidate_registry_fixture "
                    "--public-gold-source-ids deepmatcher_dblp_scholar deepmatcher_amazon_google "
                    "--openalex-topic-seed-ids T10009 && "
                    "python -m iad_sieve.cli build-iad-bench-source-acquisition-audit "
                    "--registry outputs/iad_bench_source_candidate_registry_fixture/iad_bench_source_candidate_registry.jsonl "
                    "--output-dir outputs/iad_bench_source_acquisition_audit_fixture "
                    "--workspace-dir . && "
                    "python -m iad_sieve.cli build-iad-bench-balanced-subset "
                    "--documents outputs/iad_bench_open_v3/iad_bench_documents.jsonl "
                    "--pairs outputs/iad_bench_open_v3/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_bench_open_v3_balanced_gold "
                    "--relation-labels same_work,unrelated "
                    "--seed 42 "
                    "--train-ratio 0.8 "
                    "--dev-ratio 0.1 && "
                    "python -m iad_sieve.cli build-public-data-validity-audit "
                    "--pairs outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl "
                    "--documents outputs/iad_bench_open_v3_balanced_gold/iad_bench_documents.jsonl "
                    "--output-dir outputs/public_data_validity_audit_open_v3_balanced_gold "
                    "--min-gold-pairs 2000 "
                    "--max-single-silver-topic-ratio 0.8 "
                    "--max-dominant-relation-label-ratio 0.8 && "
                    "python -m iad_sieve.cli build-iad-bench-stratification-audit "
                    "--pairs outputs/iad_bench_open_v3/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_bench_stratification_audit_open_v3 "
                    "--max-top-strength-ratio 0.8 "
                    "--min-sources-per-relation 2 && "
                    "python -m iad_sieve.cli build-iad-bench-stratification-audit "
                    "--pairs outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_bench_stratification_audit_open_v3_balanced_gold "
                    "--max-top-strength-ratio 0.8 "
                    "--min-sources-per-relation 2 && "
                    "python -m iad_sieve.cli build-iad-bench-source-bias-diagnostic "
                    "--pairs outputs/iad_bench_open_v3/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_bench_source_bias_diagnostic_open_v3 "
                    "--train-split train "
                    "--eval-splits dev,test "
                    "--max-shortcut-accuracy 0.8 && "
                    "python -m iad_sieve.cli build-iad-bench-source-bias-diagnostic "
                    "--pairs outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_bench_source_bias_diagnostic_open_v3_balanced_gold "
                    "--train-split train "
                    "--eval-splits dev,test "
                    "--max-shortcut-accuracy 0.8 && "
                    "python -m iad_sieve.cli build-iad-bench-provenance-balance-plan "
                    "--pairs outputs/iad_bench_open_v3/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_bench_provenance_balance_plan_open_v3 "
                    "--min-sources-per-relation 2 "
                    "--max-dominant-source-ratio 0.8 "
                    "--target-pairs-per-new-source 500 && "
                    "python -m iad_sieve.cli build-iad-bench-provenance-balance-plan "
                    "--pairs outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_bench_provenance_balance_plan_open_v3_balanced_gold "
                    "--min-sources-per-relation 2 "
                    "--max-dominant-source-ratio 0.8 "
                    "--target-pairs-per-new-source 500 && "
                    "python -m iad_sieve.cli build-open-v3-split-readiness "
                    "--pairs outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl "
                    "--output-dir outputs/open_v3_split_readiness_balanced_gold "
                    "--min-sources-per-relation 2 "
                    "--min-topics-for-topic-holdout 3 && "
                    "python -m iad_sieve.cli build-open-v3-heldout-split-plan "
                    "--pairs outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl "
                    "--output-dir outputs/open_v3_heldout_split_plan_balanced_gold "
                    "--min-sources-per-relation 2 "
                    "--min-topics-for-topic-holdout 3 "
                    "--topic-test-ratio 0.2 && "
                    "python -m iad_sieve.cli apply-heldout-split-assignment "
                    "--pairs outputs/iad_bench_open_v3_balanced_gold/iad_bench_pairs.jsonl "
                    "--assignments outputs/open_v3_heldout_split_plan_balanced_gold/open_v3_heldout_split_assignments.jsonl "
                    "--split-strategy source_held_out "
                    "--output-dir outputs/iad_bench_open_v3_balanced_gold_source_heldout && "
                    "python -m iad_sieve.cli score-eval-set "
                    "--documents outputs/iad_bench_open_v3_balanced_gold/iad_bench_documents.jsonl "
                    "--pairs outputs/iad_bench_open_v3_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                    "--output outputs/iad_bench_open_v3_balanced_gold_source_heldout/scored_relations.jsonl "
                    "--summary-output outputs/iad_bench_open_v3_balanced_gold_source_heldout/scored_relation_summary.jsonl && "
                    "python -m iad_sieve.cli build-iad-bench-balanced-subset "
                    "--documents outputs/iad_bench_open_v3/iad_bench_documents.jsonl "
                    "--pairs outputs/iad_bench_open_v3/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_bench_open_v3_scholarly_balanced_gold "
                    "--relation-labels same_work,unrelated "
                    "--include-label-sources deepmatcher_dblp_scholar,deepmatcher_py_entitymatching_dblp_acm "
                    "--seed 7 "
                    "--train-ratio 0.8 "
                    "--dev-ratio 0.1 && "
                    "python -m iad_sieve.cli build-public-data-validity-audit "
                    "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
                    "--documents outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_documents.jsonl "
                    "--output-dir outputs/public_data_validity_audit_open_v3_scholarly_balanced_gold "
                    "--min-gold-pairs 2000 "
                    "--max-single-silver-topic-ratio 0.15 "
                    "--max-dominant-relation-label-ratio 0.8 && "
                    "python -m iad_sieve.cli build-iad-bench-stratification-audit "
                    "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_bench_stratification_audit_open_v3_scholarly_balanced_gold "
                    "--max-top-strength-ratio 1.0 "
                    "--min-sources-per-relation 2 && "
                    "python -m iad_sieve.cli build-iad-bench-source-bias-diagnostic "
                    "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_bench_source_bias_diagnostic_open_v3_scholarly_balanced_gold "
                    "--train-split train "
                    "--eval-splits dev,test "
                    "--max-shortcut-accuracy 0.65 && "
                    "python -m iad_sieve.cli build-iad-bench-provenance-balance-plan "
                    "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_bench_provenance_balance_plan_open_v3_scholarly_balanced_gold "
                    "--min-sources-per-relation 2 "
                    "--max-dominant-source-ratio 0.95 "
                    "--target-pairs-per-new-source 1000 && "
                    "python -m iad_sieve.cli build-open-v3-split-readiness "
                    "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
                    "--output-dir outputs/open_v3_split_readiness_scholarly_balanced_gold "
                    "--min-sources-per-relation 2 "
                    "--min-topics-for-topic-holdout 3 && "
                    "python -m iad_sieve.cli build-open-v3-heldout-split-plan "
                    "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
                    "--output-dir outputs/open_v3_heldout_split_plan_scholarly_balanced_gold "
                    "--min-sources-per-relation 2 "
                    "--min-topics-for-topic-holdout 3 "
                    "--topic-test-ratio 0.2 && "
                    "python -m iad_sieve.cli apply-heldout-split-assignment "
                    "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold/iad_bench_pairs.jsonl "
                    "--assignments outputs/open_v3_heldout_split_plan_scholarly_balanced_gold/open_v3_heldout_split_assignments.jsonl "
                    "--split-strategy source_held_out "
                    "--output-dir outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout && "
                    "python -m iad_sieve.cli build-iad-source-heldout-coverage-audit "
                    "--pairs outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_source_heldout_coverage_audit_open_v3_scholarly_balanced_gold "
                    "--relation-labels same_work,unrelated,agenda_non_identity "
                    "--min-train-pairs 100 "
                    "--min-test-pairs 100 && "
                    "python -m iad_sieve.cli build-iad-training-blend "
                    "--relations outputs/iad_bench_open_v3_balanced_gold_source_heldout/scored_relations.jsonl "
                    "outputs/openalex_api_v1/scored_relations.jsonl "
                    "--output-dir outputs/iad_training_blend_open_v3_gold_silver "
                    "--relation-labels same_work,unrelated,agenda_non_identity "
                    "--seed 7 && "
                    "python -m iad_sieve.cli build-iad-training-input-audit "
                    "--relations outputs/iad_training_blend_open_v3_gold_silver/iad_training_relations.jsonl "
                    "--output-dir outputs/iad_training_input_audit_open_v3_gold_silver && "
                    "python -m iad_sieve.cli train-iad-risk-model "
                    "--relations outputs/iad_training_blend_open_v3_gold_silver/iad_training_relations.jsonl "
                    "--output-dir outputs/iad_risk_open_v3_gold_silver "
                    "--train-split train "
                    "--eval-splits all,train,test "
                    "--seed 7 "
                    "--work-threshold 0.5 "
                    "--agenda-block-threshold 0.5 "
                    "--risk-threshold 0.5 && "
                    "python -m iad_sieve.cli build-iad-risk-split-evaluation-audit "
                    "--iad-risk-summary outputs/iad_risk_open_v3_gold_silver/iad_risk_summary.jsonl "
                    "--iad-risk-model outputs/iad_risk_open_v3_gold_silver/iad_risk_model.json "
                    "--output-dir outputs/iad_risk_split_evaluation_audit_open_v3_gold_silver && "
                    "python -m iad_sieve.cli build-iad-model-feature-guard "
                    "--model-paths outputs/iad_risk_open_v2/iad_risk_model.json "
                    "outputs/iad_risk_transformer_open_v2/iad_risk_transformer_model.json "
                    "outputs/iad_risk_transformer_scincl_provenance_blind_open_v2/iad_risk_transformer_model.json "
                    "outputs/iad_risk_transformer_specter2_open_v2/iad_risk_transformer_model.json "
                    "--output-dir outputs/iad_model_feature_guard_fixture && "
                    "python -m iad_sieve.cli build-submission-gate-audit "
                    "--readiness-reports outputs/journal_readiness_fixture/journal_readiness.jsonl "
                    "--claim-audits outputs/paper_claim_audit_fixture/paper_claim_audit.jsonl "
                    "--research-depth-audits outputs/research_depth_audit_fixture/research_depth_audit.jsonl "
                    "--remote-output-summaries outputs/remote_output_validation_fixture/remote_output_validation_summary.jsonl "
                    "--remote-result-acceptance-summaries outputs/remote_result_acceptance_fixture/remote_result_acceptance_summary.jsonl "
                    "--remote-connection-summaries outputs/remote_connection_pack_fixture/remote_connection_pack_summary.jsonl "
                    "--source-bias-summaries outputs/iad_bench_source_bias_diagnostic_open_v3_balanced_gold/iad_bench_source_bias_diagnostic_summary.jsonl "
                    "outputs/iad_bench_source_bias_diagnostic_open_v3_scholarly_balanced_gold/iad_bench_source_bias_diagnostic_summary.jsonl "
                    "outputs/iad_bench_source_bias_diagnostic_fixture/iad_bench_source_bias_diagnostic_summary.jsonl "
                    "--feature-guard-summaries outputs/iad_model_feature_guard_fixture/iad_model_feature_guard_summary.jsonl "
                    "--provenance-balance-summaries outputs/iad_bench_provenance_balance_plan_open_v3_balanced_gold/iad_bench_provenance_balance_plan_summary.jsonl "
                    "outputs/iad_bench_provenance_balance_plan_open_v3_scholarly_balanced_gold/iad_bench_provenance_balance_plan_summary.jsonl "
                    "outputs/iad_bench_provenance_balance_plan_fixture/iad_bench_provenance_balance_plan_summary.jsonl "
                    "--training-input-summaries outputs/iad_training_input_audit_open_v3_gold_silver/iad_training_input_audit_summary.jsonl "
                    "--output-dir outputs/submission_gate_audit_fixture && "
                    "python -m iad_sieve.cli build-manuscript-evidence-matrix "
                    "--claim-audits outputs/paper_claim_audit_fixture/paper_claim_audit.jsonl "
                    "--research-depth-audits outputs/research_depth_audit_fixture/research_depth_audit.jsonl "
                    "--submission-gate-audits outputs/submission_gate_audit_fixture/submission_gate_audit.jsonl "
                    "--output-dir outputs/manuscript_evidence_matrix_fixture && "
                    "python -m iad_sieve.cli build-reviewer-response-matrix "
                    "--reviewer-audits outputs/reviewer_audit_fixture/reviewer_audit.jsonl "
                    "--research-depth-audits outputs/research_depth_audit_fixture/research_depth_audit.jsonl "
                    "--manuscript-evidence outputs/manuscript_evidence_matrix_fixture/manuscript_evidence_matrix.jsonl "
                    "--submission-gate-audits outputs/submission_gate_audit_fixture/submission_gate_audit.jsonl "
                    "--prior-art-audits outputs/prior_art_novelty_audit_fixture/prior_art_novelty_audit.jsonl "
                    "--output-dir outputs/reviewer_response_matrix_fixture && "
                    "python -m iad_sieve.cli build-manuscript-draft-skeleton "
                    "--manuscript-evidence outputs/manuscript_evidence_matrix_fixture/manuscript_evidence_matrix.jsonl "
                    "--submission-summaries outputs/submission_gate_audit_fixture/submission_gate_audit_summary.jsonl "
                    "--output-dir outputs/manuscript_draft_skeleton_fixture && "
                    "python -m iad_sieve.cli build-journal-upgrade-plan "
                    "--submission-summaries outputs/submission_gate_audit_fixture/submission_gate_audit_summary.jsonl "
                    "--research-depth-audits outputs/research_depth_audit_fixture/research_depth_audit.jsonl "
                    "--remote-output-summaries outputs/remote_output_validation_fixture/remote_output_validation_summary.jsonl "
                    "--manuscript-draft-summaries outputs/manuscript_draft_skeleton_fixture/manuscript_draft_skeleton_summary.jsonl "
                    "--human-annotation-policy defer "
                    "--output-dir outputs/journal_upgrade_plan_fixture && "
                    "python -m iad_sieve.cli build-public-data-validity-audit "
                    "--pairs outputs/iad_bench_open_v2/iad_bench_pairs.jsonl "
                    "--documents outputs/iad_bench_open_v2/iad_bench_documents.jsonl "
                    "--output-dir outputs/public_data_validity_audit_fixture "
                    "--min-gold-pairs 500 "
                    "--max-single-silver-topic-ratio 0.8 "
                    "--max-dominant-relation-label-ratio 0.8 && "
                    "python -m iad_sieve.cli build-iad-bench-stratification-audit "
                    "--pairs outputs/iad_bench_open_v2/iad_bench_pairs.jsonl "
                    "--output-dir outputs/iad_bench_stratification_audit_fixture "
                    "--max-top-strength-ratio 0.8 "
                    "--min-sources-per-relation 2 && "
                    "python -m iad_sieve.cli build-open-v3-plan-audit "
                    "--pairs outputs/iad_bench_open_v2/iad_bench_pairs.jsonl "
                    "--documents outputs/iad_bench_open_v2/iad_bench_documents.jsonl "
                    "--output-dir outputs/open_v3_plan_audit_fixture "
                    "--min-documents 20000 "
                    "--min-gold-pairs 2000 "
                    "--min-silver-pairs 50000 "
                    "--min-topics 30 "
                    "--max-top-topic-ratio 0.15 && "
                    "python -m iad_sieve.cli build-open-v3-source-plan "
                    "--pairs outputs/iad_bench_open_v2/iad_bench_pairs.jsonl "
                    "--documents outputs/iad_bench_open_v2/iad_bench_documents.jsonl "
                    "--output-dir outputs/open_v3_source_plan_fixture "
                    "--min-documents 20000 "
                    "--min-gold-pairs 2000 "
                    "--min-silver-pairs 50000 "
                    "--min-topics 30 "
                    "--target-records-per-topic 2000 "
                    "--topic-seed-ids T10009 && "
                    "python -m iad_sieve.cli build-open-v3-split-readiness "
                    "--pairs outputs/iad_bench_open_v2/iad_bench_pairs.jsonl "
                    "--output-dir outputs/open_v3_split_readiness_fixture "
                    "--min-sources-per-relation 2 "
                    "--min-topics-for-topic-holdout 30 && "
                    "python -m iad_sieve.cli build-open-v3-heldout-split-plan "
                    "--pairs outputs/iad_bench_open_v2/iad_bench_pairs.jsonl "
                    "--output-dir outputs/open_v3_heldout_split_plan_fixture "
                    "--min-sources-per-relation 2 "
                    "--min-topics-for-topic-holdout 30 "
                    "--topic-test-ratio 0.2 && "
                    "python -m iad_sieve.cli build-advanced-model-evidence "
                    "--baseline-metric-summaries outputs/strong_baseline_open_v2/scincl_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v2/distilbert_mrpc_metric_summary.jsonl outputs/strong_baseline_open_v2/roberta_pair_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v2/specter2_adapter_metric_summary.jsonl outputs/strong_baseline_open_v2/gpt_pair_judge_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_balanced_gold/scincl_metric_summary.jsonl outputs/strong_baseline_open_v3_balanced_gold/roberta_pair_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_metric_summary.jsonl outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/scincl_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/roberta_pair_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/deberta_pair_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_metric_summary.jsonl "
                    "--execution-summaries outputs/strong_baseline_open_v2/scincl_execution_summary.jsonl "
                    "outputs/strong_baseline_open_v2/distilbert_mrpc_execution_summary.jsonl outputs/strong_baseline_open_v2/roberta_pair_execution_summary.jsonl "
                    "outputs/strong_baseline_open_v2/specter2_adapter_execution_summary.jsonl outputs/strong_baseline_open_v2/gpt_pair_judge_execution_summary.jsonl "
                    "outputs/strong_baseline_open_v3_balanced_gold/scincl_execution_summary.jsonl outputs/strong_baseline_open_v3_balanced_gold/roberta_pair_execution_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_execution_summary.jsonl outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_execution_summary.jsonl "
                    "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/scincl_execution_summary.jsonl "
                    "outputs/strong_baseline_open_v3_balanced_gold_source_heldout/roberta_pair_execution_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/scincl_execution_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/roberta_pair_execution_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/deberta_pair_execution_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/ditto_style_em_execution_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout/gpt_pair_judge_execution_summary.jsonl "
                    "--transformer-summaries outputs/iad_risk_transformer_open_v2/iad_risk_transformer_summary.jsonl "
                    "outputs/iad_risk_transformer_scincl_provenance_blind_open_v2/iad_risk_transformer_summary.jsonl "
                    "outputs/iad_risk_transformer_specter2_open_v2/iad_risk_transformer_summary.jsonl "
                    "outputs/iad_risk_transformer_scincl_open_v3_balanced_gold/iad_risk_transformer_summary.jsonl "
                    "outputs/iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout/iad_risk_transformer_summary.jsonl "
                    "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold/iad_risk_transformer_summary.jsonl "
                    "outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout/iad_risk_transformer_summary.jsonl "
                    "--bootstrap-summaries outputs/iad_bootstrap_open_v2/iad_risk_transformer_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v2/iad_risk_transformer_scincl_provenance_blind_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v2/scincl_bootstrap_confidence.csv outputs/iad_bootstrap_open_v2/distilbert_mrpc_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v2/roberta_pair_bootstrap_confidence.csv outputs/iad_bootstrap_open_v2/specter2_adapter_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v2/gpt_pair_judge_bootstrap_confidence.csv outputs/iad_bootstrap_open_v2/iad_risk_transformer_specter2_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v3_balanced_gold/iad_risk_transformer_scincl_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/iad_risk_transformer_scincl_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/scincl_source_heldout_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/roberta_pair_source_heldout_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/iad_risk_transformer_scincl_source_heldout_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/ditto_style_em_source_heldout_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/gpt_pair_judge_source_heldout_bootstrap_confidence.csv "
                    "--remote-output-summaries outputs/remote_output_validation_fixture/remote_output_validation_summary.jsonl "
                    "--required-systems specter2_adapter_cosine_open_v2 gpt_pair_judge_open_v2 iad_risk_transformer_scincl_provenance_blind_open_v2 iad_risk_transformer_specter2_open_v2 "
                    "scincl_cosine_open_v3_balanced_gold roberta_pair_open_v3_balanced_gold iad_risk_transformer_scincl_open_v3_balanced_gold "
                    "scincl_cosine_open_v3_balanced_gold_source_heldout roberta_pair_open_v3_balanced_gold_source_heldout "
                    "iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout "
                    "scincl_cosine_open_v3_scholarly_balanced_gold roberta_pair_open_v3_scholarly_balanced_gold "
                    "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold "
                    "scincl_cosine_open_v3_scholarly_balanced_gold_source_heldout roberta_pair_open_v3_scholarly_balanced_gold_source_heldout "
                    "deberta_pair_open_v3_scholarly_balanced_gold_source_heldout "
                    "iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout "
                    "ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout "
                    "gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout "
                    "--output-dir outputs/advanced_model_evidence_fixture && "
                    "python -m iad_sieve.cli build-q2b-action-board "
                    "--submission-gates outputs/submission_gate_audit_fixture/submission_gate_audit.jsonl "
                    "--remote-blueprint outputs/remote_execution_blueprint_fixture/remote_execution_blueprint.jsonl "
                    "--journal-upgrade-plan outputs/journal_upgrade_plan_fixture/journal_upgrade_plan.jsonl "
                    "--advanced-model-evidence outputs/advanced_model_evidence_fixture/advanced_model_evidence.jsonl "
                    "--remote-connection-pack outputs/remote_connection_pack_fixture/remote_connection_pack.jsonl "
                    "--output-dir outputs/q2b_action_board_fixture && "
                    "python -m iad_sieve.cli build-model-innovation-blueprint "
                    "--advanced-model-evidence outputs/advanced_model_evidence_fixture/advanced_model_evidence.jsonl "
                    "--q2b-completion-audits outputs/q2b_completion_audit_fixture/q2b_completion_audit.jsonl "
                    "--split-readiness-audits outputs/open_v3_split_readiness_balanced_gold/open_v3_split_readiness.jsonl "
                    "outputs/open_v3_split_readiness_multitopic_silver_patch/open_v3_split_readiness.jsonl "
                    "outputs/open_v3_split_readiness_scholarly_balanced_gold/open_v3_split_readiness.jsonl "
                    "--output-dir outputs/model_innovation_blueprint_fixture && "
                    "python -m iad_sieve.cli build-model-superiority-audit "
                    "--advanced-model-evidence outputs/advanced_model_evidence_fixture/advanced_model_evidence.jsonl "
                    "--model-innovation-blueprints outputs/model_innovation_blueprint_fixture/model_innovation_blueprint.jsonl "
                    "--risk-protocols outputs/risk_protocol_iad_risk_open_v3_scholarly_balanced_gold_source_heldout/risk_calibrated_protocol.jsonl "
                    "outputs/risk_protocol_scincl_open_v3_scholarly_balanced_gold_source_heldout/risk_calibrated_protocol.jsonl "
                    "outputs/risk_protocol_roberta_open_v3_scholarly_balanced_gold_source_heldout/risk_calibrated_protocol.jsonl "
                    "outputs/risk_protocol_deberta_open_v3_scholarly_balanced_gold_source_heldout/risk_calibrated_protocol.jsonl "
                    "outputs/risk_protocol_specter2_adapter_open_v3_scholarly_balanced_gold_source_heldout/risk_calibrated_protocol.jsonl "
                    "outputs/risk_protocol_iad_risk_specter2_open_v3_scholarly_balanced_gold_source_heldout/risk_calibrated_protocol.jsonl "
                    "--main-system iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout "
                    "--output-dir outputs/model_superiority_audit_fixture && "
                    "python -m iad_sieve.cli build-mechanism-error-evidence "
                    "--baseline outputs/strong_baseline_open_v2/scincl_scored_relations.jsonl "
                    "--iad-predictions outputs/iad_risk_transformer_open_v2/iad_risk_transformer_predictions.jsonl "
                    "--system-name scincl_cosine_open_v2 --score-field scincl_score --threshold 0.9 "
                    "--sweep-thresholds 0.5,0.7,0.8,0.9,0.95 "
                    "--output-dir outputs/mechanism_error_evidence_fixture/scincl --max-cases 20 && "
                    "python -m iad_sieve.cli build-mechanism-error-evidence "
                    "--baseline outputs/strong_baseline_open_v2/roberta_pair_scored_relations.jsonl "
                    "--iad-predictions outputs/iad_risk_transformer_open_v2/iad_risk_transformer_predictions.jsonl "
                    "--system-name roberta_pair_open_v2 --score-field roberta_pair_score --threshold 0.8 "
                    "--sweep-thresholds 0.5,0.7,0.8,0.9,0.95 "
                    "--output-dir outputs/mechanism_error_evidence_fixture/roberta_pair --max-cases 20 && "
                    "python -m iad_sieve.cli build-mechanism-triangulation-audit "
                    "--iad-predictions outputs/iad_risk_transformer_open_v2/iad_risk_transformer_predictions.jsonl "
                    "--baseline-specs "
                    "system=scincl_cosine_open_v2,path=outputs/strong_baseline_open_v2/scincl_scored_relations.jsonl,score_field=scincl_score,threshold=0.9 "
                    "system=roberta_pair_open_v2,path=outputs/strong_baseline_open_v2/roberta_pair_scored_relations.jsonl,score_field=roberta_pair_score,threshold=0.8 "
                    "--output-dir outputs/mechanism_triangulation_audit_fixture && "
                    "python -m iad_sieve.cli build-mechanism-triangulation-sensitivity "
                    "--iad-predictions outputs/iad_risk_transformer_open_v2/iad_risk_transformer_predictions.jsonl "
                    "--baseline-specs "
                    "'system=scincl_cosine_open_v2,path=outputs/strong_baseline_open_v2/scincl_scored_relations.jsonl,score_field=scincl_score,thresholds=0.5|0.7|0.8|0.9|0.95' "
                    "'system=roberta_pair_open_v2,path=outputs/strong_baseline_open_v2/roberta_pair_scored_relations.jsonl,score_field=roberta_pair_score,thresholds=0.5|0.7|0.8|0.9|0.95' "
                    "--output-dir outputs/mechanism_triangulation_sensitivity_fixture && "
                    "python -m iad_sieve.cli build-mechanism-case-pack "
                    "--triangulation outputs/mechanism_triangulation_audit_fixture/mechanism_triangulation_audit.jsonl "
                    "--documents outputs/iad_bench_open_v2/iad_bench_documents.jsonl "
                    "--iad-predictions outputs/iad_risk_transformer_open_v2/iad_risk_transformer_predictions.jsonl "
                    "--baseline-specs "
                    "system=scincl_cosine_open_v2,path=outputs/strong_baseline_open_v2/scincl_scored_relations.jsonl,score_field=scincl_score,threshold=0.9 "
                    "system=roberta_pair_open_v2,path=outputs/strong_baseline_open_v2/roberta_pair_scored_relations.jsonl,score_field=roberta_pair_score,threshold=0.8 "
                    "--max-cases-per-group 2 "
                    "--output-dir outputs/mechanism_case_pack_fixture && "
                    "python -m iad_sieve.cli build-innovation-depth-stress-test "
                    "--model-innovation-blueprints outputs/model_innovation_blueprint_fixture/model_innovation_blueprint.jsonl "
                    "--model-superiority-audits outputs/model_superiority_audit_fixture/model_superiority_audit.jsonl "
                    "--mechanism-evidence outputs/mechanism_error_evidence_fixture/scincl/mechanism_error_evidence.jsonl "
                    "outputs/mechanism_error_evidence_fixture/roberta_pair/mechanism_error_evidence.jsonl "
                    "--mechanism-sensitivity outputs/mechanism_error_evidence_fixture/scincl/mechanism_threshold_sensitivity.jsonl "
                    "outputs/mechanism_error_evidence_fixture/roberta_pair/mechanism_threshold_sensitivity.jsonl "
                    "--mechanism-triangulation-summaries outputs/mechanism_triangulation_audit_fixture/mechanism_triangulation_summary.jsonl "
                    "--mechanism-triangulation-sensitivity-summaries outputs/mechanism_triangulation_sensitivity_fixture/mechanism_triangulation_sensitivity_summary.jsonl "
                    "--split-readiness-audits outputs/open_v3_split_readiness_balanced_gold/open_v3_split_readiness.jsonl "
                    "outputs/open_v3_split_readiness_multitopic_silver_patch/open_v3_split_readiness.jsonl "
                    "outputs/open_v3_split_readiness_scholarly_balanced_gold/open_v3_split_readiness.jsonl "
                    "--output-dir outputs/innovation_depth_stress_test_fixture && "
                    "python -m iad_sieve.cli build-q2b-completion-audit "
                    "--submission-summaries outputs/submission_gate_audit_fixture/submission_gate_audit_summary.jsonl "
                    "--q2b-summaries outputs/q2b_action_board_fixture/q2b_action_board_summary.jsonl "
                    "--reviewer-response-summaries outputs/reviewer_response_matrix_fixture/reviewer_response_summary.jsonl "
                    "--remote-connection-summaries outputs/remote_connection_pack_fixture/remote_connection_pack_summary.jsonl "
                    "--remote-result-acceptance-summaries outputs/remote_result_acceptance_fixture/remote_result_acceptance_summary.jsonl "
                    "--innovation-depth-summaries outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test_summary.jsonl "
                    "--advanced-model-summaries outputs/advanced_model_evidence_fixture/advanced_model_evidence_summary.jsonl "
                    "--split-readiness-summaries outputs/open_v3_split_readiness_balanced_gold/open_v3_split_readiness_summary.jsonl "
                    "outputs/open_v3_split_readiness_multitopic_silver_patch/open_v3_split_readiness_summary.jsonl "
                    "outputs/open_v3_split_readiness_scholarly_balanced_gold/open_v3_split_readiness_summary.jsonl "
                    "--split-readiness-audits outputs/open_v3_split_readiness_balanced_gold/open_v3_split_readiness.jsonl "
                    "outputs/open_v3_split_readiness_multitopic_silver_patch/open_v3_split_readiness.jsonl "
                    "outputs/open_v3_split_readiness_scholarly_balanced_gold/open_v3_split_readiness.jsonl "
                    "--training-input-summaries outputs/iad_training_input_audit_open_v3_gold_silver/iad_training_input_audit_summary.jsonl "
                    "--source-heldout-coverage-summaries outputs/iad_source_heldout_coverage_audit_open_v3_balanced_gold/iad_source_heldout_coverage_summary.jsonl "
                    "outputs/iad_source_heldout_coverage_audit_open_v3_scholarly_balanced_gold/iad_source_heldout_coverage_summary.jsonl "
                    "outputs/iad_source_heldout_coverage_audit_coci_source_patch/iad_source_heldout_coverage_summary.jsonl "
                    "--split-evaluation-summaries outputs/iad_risk_split_evaluation_audit_open_v3_gold_silver/iad_risk_split_evaluation_audit_summary.jsonl "
                    "outputs/iad_risk_split_evaluation_audit_source_heldout/iad_risk_split_evaluation_audit_summary.jsonl "
                    "outputs/iad_risk_split_evaluation_audit_coci_source_patch_source_heldout/iad_risk_split_evaluation_audit_summary.jsonl "
                    "--output-dir outputs/q2b_completion_audit_fixture && "
                    "python -m iad_sieve.cli build-q2b-upgrade-roadmap "
                    "--completion-audit outputs/q2b_completion_audit_fixture/q2b_completion_audit.jsonl "
                    "--action-board outputs/q2b_action_board_fixture/q2b_action_board.jsonl "
                    "--remote-acceptance outputs/remote_result_acceptance_fixture/remote_result_acceptance.jsonl "
                    "--remote-output-summary outputs/remote_output_validation_fixture/remote_output_validation_summary.jsonl "
                    "--model-superiority-audit outputs/model_superiority_audit_fixture/model_superiority_audit.jsonl "
                    "--output-dir outputs/q2b_upgrade_roadmap_fixture && "
                    "python -m iad_sieve.cli build-reviewer-iteration-audit "
                    "--q2b-roadmap outputs/q2b_upgrade_roadmap_fixture/q2b_upgrade_roadmap.jsonl "
                    "--q2b-completion-audit outputs/q2b_completion_audit_fixture/q2b_completion_audit.jsonl "
                    "--model-superiority-audit outputs/model_superiority_audit_fixture/model_superiority_audit.jsonl "
                    "--innovation-depth outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test.jsonl "
                    "--public-data-validity outputs/public_data_validity_audit_fixture/public_data_validity_audit.jsonl "
                    "--feature-guard outputs/iad_model_feature_guard_fixture/iad_model_feature_guard.jsonl "
                    "--reviewer-response outputs/reviewer_response_matrix_fixture/reviewer_response_matrix.jsonl "
                    "--output-dir outputs/reviewer_iteration_audit_fixture && "
                    "python -m iad_sieve.cli build-remote-input-request "
                    "--remote-connection-pack outputs/remote_connection_pack_fixture/remote_connection_pack.jsonl "
                    "--q2b-roadmap outputs/q2b_upgrade_roadmap_fixture/q2b_upgrade_roadmap.jsonl "
                    "--reviewer-iteration outputs/reviewer_iteration_audit_fixture/reviewer_iteration_audit.jsonl "
                    "--output-dir outputs/remote_input_request_fixture && "
                    "python -m iad_sieve.cli build-remote-execution-slice "
                    "--q2b-action-board outputs/q2b_action_board_fixture/q2b_action_board.jsonl "
                    "--remote-connection-pack outputs/remote_connection_pack_fixture/remote_connection_pack.jsonl "
                    "--remote-input-request outputs/remote_input_request_fixture/remote_input_request.jsonl "
                    "--remote-execution-blueprint outputs/remote_execution_blueprint_fixture/remote_execution_blueprint.jsonl "
                    "--output-dir outputs/remote_execution_slice_fixture && "
                    "python -m iad_sieve.cli build-remote-slice-run-pack "
                    "--remote-execution-slice outputs/remote_execution_slice_fixture/remote_execution_slice.jsonl "
                    "--execution-plan outputs/experiment_execution_pack_fixture/experiment_execution_plan.jsonl "
                    "--output-dir outputs/remote_slice_run_pack_fixture && "
                    "python -m iad_sieve.cli build-primary-remote-readiness "
                    "--remote-input-request outputs/remote_input_request_fixture/remote_input_request.jsonl "
                    "--remote-execution-slice outputs/remote_execution_slice_fixture/remote_execution_slice.jsonl "
                    "--remote-slice-run-pack outputs/remote_slice_run_pack_fixture/remote_slice_run_pack.jsonl "
                    "--output-dir outputs/primary_remote_readiness_fixture && "
                    "python -m iad_sieve.cli build-primary-remote-handoff "
                    "--primary-remote-readiness outputs/primary_remote_readiness_fixture/primary_remote_readiness.jsonl "
                    "--output-dir outputs/primary_remote_handoff_fixture && "
                    "python -m iad_sieve.cli build-no-annotation-protocol "
                    "--public-data-validity outputs/public_data_validity_audit_open_v3_balanced_gold/public_data_validity_audit.jsonl "
                    "--q2b-roadmap outputs/q2b_upgrade_roadmap_fixture/q2b_upgrade_roadmap.jsonl "
                    "--reviewer-iteration outputs/reviewer_iteration_audit_fixture/reviewer_iteration_audit.jsonl "
                    "--remote-input-request outputs/remote_input_request_fixture/remote_input_request.jsonl "
                    "--output-dir outputs/no_annotation_protocol_fixture && "
                    "python -m iad_sieve.cli build-novelty-falsification-matrix "
                    "--model-innovation-blueprints outputs/model_innovation_blueprint_fixture/model_innovation_blueprint.jsonl "
                    "--innovation-depth-audits outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test.jsonl "
                    "--model-superiority-summary outputs/model_superiority_audit_fixture/model_superiority_audit_summary.jsonl "
                    "--no-annotation-summary outputs/no_annotation_protocol_fixture/no_annotation_protocol_summary.jsonl "
                    "--output-dir outputs/novelty_falsification_matrix_fixture && "
                    "python -m iad_sieve.cli build-prior-art-novelty-audit "
                    "--novelty-matrices outputs/novelty_falsification_matrix_fixture/novelty_falsification_matrix.jsonl "
                    "--advanced-model-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_summary.jsonl "
                    "--snapshot-date 2026-06-13 "
                    "--output-dir outputs/prior_art_novelty_audit_fixture && "
                    "python -m iad_sieve.cli build-q2b-acceptance-rubric "
                    "--remote-output-summary outputs/remote_output_validation_fixture/remote_output_validation_summary.jsonl "
                    "--remote-result-acceptance-summary outputs/remote_result_acceptance_fixture/remote_result_acceptance_summary.jsonl "
                    "--advanced-model-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_summary.jsonl "
                    "--model-superiority-summary outputs/model_superiority_audit_fixture/model_superiority_audit_summary.jsonl "
                    "--innovation-depth-summary outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test_summary.jsonl "
                    "--no-annotation-summary outputs/no_annotation_protocol_fixture/no_annotation_protocol_summary.jsonl "
                    "--novelty-summary outputs/novelty_falsification_matrix_fixture/novelty_falsification_matrix_summary.jsonl "
                    "--prior-art-summary outputs/prior_art_novelty_audit_fixture/prior_art_novelty_audit_summary.jsonl "
                    "--q2b-completion-summary outputs/q2b_completion_audit_fixture/q2b_completion_audit_summary.jsonl "
                    "--reviewer-iteration-summary outputs/reviewer_iteration_audit_fixture/reviewer_iteration_audit_summary.jsonl "
                    "--output-dir outputs/q2b_acceptance_rubric_fixture && "
                    "python -m iad_sieve.cli build-primary-track-claim-gate "
                    "--primary-remote-handoff outputs/primary_remote_handoff_fixture/primary_remote_handoff.jsonl "
                    "--advanced-track-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_track_summary.jsonl "
                    "--model-superiority-summary outputs/model_superiority_audit_fixture/model_superiority_audit_summary.jsonl "
                    "--innovation-depth-summary outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test_summary.jsonl "
                    "--q2b-acceptance-summary outputs/q2b_acceptance_rubric_fixture/q2b_acceptance_rubric_summary.jsonl "
                    "--output-dir outputs/primary_track_claim_gate_fixture && "
                    "python -m iad_sieve.cli build-primary-track-superiority-protocol "
                    "--primary-track-claim-gate outputs/primary_track_claim_gate_fixture/primary_track_claim_gate.jsonl "
                    "--advanced-track-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_track_summary.jsonl "
                    "--model-superiority-summary outputs/model_superiority_audit_fixture/model_superiority_audit_summary.jsonl "
                    "--output-dir outputs/primary_track_superiority_protocol_fixture && "
                    "python -m iad_sieve.cli build-primary-track-superiority-evaluator "
                    "--primary-track-superiority-protocol outputs/primary_track_superiority_protocol_fixture/primary_track_superiority_protocol.jsonl "
                    "--metric-summaries outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold/iad_risk_transformer_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold/scincl_metric_summary.jsonl "
                    "outputs/strong_baseline_open_v3_scholarly_balanced_gold/roberta_pair_metric_summary.jsonl "
                    "--bootstrap-summaries outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/iad_risk_transformer_scincl_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/scincl_bootstrap_confidence.csv "
                    "outputs/iad_bootstrap_open_v3_scholarly_balanced_gold/roberta_pair_bootstrap_confidence.csv "
                    "--output-dir outputs/primary_track_superiority_evaluator_fixture && "
                    "python -m iad_sieve.cli build-q2b-experiment-optimizer "
                    "--q2b-acceptance-rubric outputs/q2b_acceptance_rubric_fixture/q2b_acceptance_rubric.jsonl "
                    "--reviewer-iteration outputs/reviewer_iteration_audit_fixture/reviewer_iteration_audit.jsonl "
                    "--remote-input-request outputs/remote_input_request_fixture/remote_input_request.jsonl "
                    "--remote-execution-slice outputs/remote_execution_slice_fixture/remote_execution_slice.jsonl "
                    "--advanced-track-summary outputs/advanced_model_evidence_fixture/advanced_model_evidence_track_summary.jsonl "
                    "--output-dir outputs/q2b_experiment_optimizer_fixture && "
                    "python -m iad_sieve.cli build-q2b-external-blocker-audit "
                    "--completion-audit outputs/q2b_completion_audit_fixture/q2b_completion_audit.jsonl "
                    "--action-board outputs/q2b_action_board_fixture/q2b_action_board.jsonl "
                    "--remote-result-acceptance outputs/remote_result_acceptance_fixture/remote_result_acceptance.jsonl "
                    "--advanced-model-evidence outputs/advanced_model_evidence_fixture/advanced_model_evidence.jsonl "
                    "--output-dir outputs/q2b_external_blocker_audit_fixture && "
                    "python -m iad_sieve.cli build-reviewer-threat-model "
                    "--q2b-acceptance-rubric outputs/q2b_acceptance_rubric_fixture/q2b_acceptance_rubric.jsonl "
                    "--q2b-experiment-optimizer outputs/q2b_experiment_optimizer_fixture/q2b_experiment_optimizer.jsonl "
                    "--model-innovation-blueprints outputs/model_innovation_blueprint_fixture/model_innovation_blueprint.jsonl "
                    "--innovation-depth-audits outputs/innovation_depth_stress_test_fixture/innovation_depth_stress_test.jsonl "
                    "--novelty-matrices outputs/novelty_falsification_matrix_fixture/novelty_falsification_matrix.jsonl "
                    "--prior-art-audits outputs/prior_art_novelty_audit_fixture/prior_art_novelty_audit.jsonl "
                    "--reviewer-iterations outputs/reviewer_iteration_audit_fixture/reviewer_iteration_audit.jsonl "
                    "--output-dir outputs/reviewer_threat_model_fixture && "
                    "REPORT_DIRS=() && "
                    "while IFS= read -r report_dir; do REPORT_DIRS+=(\"$report_dir\"); done < <(find outputs -path outputs/topic_package_final -prune -o -type f "
                    "\\( -name '*.jsonl' -o -name '*.csv' -o -name '*.md' -o -name '*.json' -o -name '*.sh' \\) "
                    "-print | sed 's#/[^/]*$##' | sort -u) && "
                    "python -m iad_sieve.cli export-topic-package "
                    "--workspace-dir . "
                    "--output-dir outputs/topic_package_final "
                    "--report-dirs \"${REPORT_DIRS[@]}\" "
                    "--model-dir outputs/iad_classifier_fixture"
                ),
                expected_outputs="outputs/iad_paper_report_fixture; outputs/reviewer_audit_fixture; outputs/journal_readiness_fixture; outputs/remote_output_validation_fixture; outputs/remote_result_acceptance_fixture; outputs/remote_environment_audit_fixture; outputs/remote_execution_blueprint_fixture; outputs/remote_connection_pack_fixture; outputs/remote_input_request_fixture; outputs/remote_execution_slice_fixture; outputs/remote_slice_run_pack_fixture; outputs/primary_remote_readiness_fixture; outputs/primary_remote_handoff_fixture; outputs/primary_track_claim_gate_fixture; outputs/primary_track_superiority_protocol_fixture; outputs/primary_track_superiority_evaluator_fixture; outputs/no_annotation_protocol_fixture; outputs/q2b_acceptance_rubric_fixture; outputs/q2b_experiment_optimizer_fixture; outputs/q2b_external_blocker_audit_fixture; outputs/reviewer_threat_model_fixture; outputs/novelty_falsification_matrix_fixture; outputs/prior_art_novelty_audit_fixture; outputs/research_depth_audit_fixture; outputs/submission_gate_audit_fixture; outputs/manuscript_evidence_matrix_fixture; outputs/reviewer_response_matrix_fixture; outputs/reviewer_iteration_audit_fixture; outputs/manuscript_draft_skeleton_fixture; outputs/journal_upgrade_plan_fixture; outputs/advanced_model_evidence_fixture; outputs/model_innovation_blueprint_fixture; outputs/model_superiority_audit_fixture; outputs/q2b_action_board_fixture; outputs/q2b_completion_audit_fixture; outputs/q2b_upgrade_roadmap_fixture; outputs/mechanism_case_pack_fixture; outputs/mechanism_triangulation_audit_fixture; outputs/mechanism_triangulation_sensitivity_fixture; outputs/public_data_validity_audit_fixture; outputs/iad_bench_stratification_audit_fixture; outputs/iad_bench_source_bias_diagnostic_fixture; outputs/iad_bench_provenance_balance_plan_fixture; outputs/iad_bench_source_candidate_registry_fixture; outputs/iad_bench_source_acquisition_audit_fixture; outputs/iad_model_feature_guard_fixture; outputs/open_v3_plan_audit_fixture; outputs/open_v3_source_plan_fixture; outputs/open_v3_split_readiness_fixture; outputs/open_v3_heldout_split_plan_fixture; outputs/iad_bench_open_v3_balanced_gold; outputs/public_data_validity_audit_open_v3_balanced_gold; outputs/iad_bench_stratification_audit_open_v3; outputs/iad_bench_stratification_audit_open_v3_balanced_gold; outputs/iad_bench_source_bias_diagnostic_open_v3; outputs/iad_bench_source_bias_diagnostic_open_v3_balanced_gold; outputs/iad_bench_provenance_balance_plan_open_v3; outputs/iad_bench_provenance_balance_plan_open_v3_balanced_gold; outputs/open_v3_split_readiness_balanced_gold; outputs/open_v3_heldout_split_plan_balanced_gold; outputs/iad_bench_open_v3_scholarly_balanced_gold; outputs/public_data_validity_audit_open_v3_scholarly_balanced_gold; outputs/iad_bench_stratification_audit_open_v3_scholarly_balanced_gold; outputs/iad_bench_source_bias_diagnostic_open_v3_scholarly_balanced_gold; outputs/iad_bench_provenance_balance_plan_open_v3_scholarly_balanced_gold; outputs/open_v3_split_readiness_scholarly_balanced_gold; outputs/open_v3_heldout_split_plan_scholarly_balanced_gold; outputs/iad_bench_open_v3_balanced_gold_source_heldout; outputs/iad_bench_open_v3_scholarly_balanced_gold_source_heldout; outputs/iad_source_heldout_coverage_audit_open_v3_scholarly_balanced_gold; outputs/iad_training_blend_open_v3_gold_silver; outputs/iad_training_input_audit_open_v3_gold_silver; outputs/iad_risk_open_v3_gold_silver; outputs/iad_risk_split_evaluation_audit_open_v3_gold_silver; outputs/strong_baseline_open_v3_balanced_gold; outputs/strong_baseline_open_v3_balanced_gold_source_heldout; outputs/strong_baseline_open_v3_scholarly_balanced_gold; outputs/strong_baseline_open_v3_scholarly_balanced_gold_source_heldout; outputs/iad_risk_transformer_scincl_provenance_blind_open_v2; outputs/iad_risk_transformer_scincl_open_v3_balanced_gold; outputs/iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout; outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold; outputs/iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout; outputs/iad_bootstrap_open_v3_balanced_gold; outputs/iad_bootstrap_open_v3_scholarly_balanced_gold; outputs/mechanism_error_evidence_fixture/scincl; outputs/mechanism_error_evidence_fixture/roberta_pair; outputs/topic_package_final",
                reviewer_value="强 baseline 完成后重建全部审稿证据，重新判断 venue_readiness。",
            )
        )
    rows.sort(key=lambda row: int(row["priority"]))
    LOGGER.info("实验队列生成完成: rows=%s", len(rows))
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 实验队列。

    参数:
        path: 输出路径。
        rows: 实验队列记录。

    返回:
        无。
    """
    fields: list[str] = []
    for field in PREFERRED_FIELDS:
        if field not in fields:
            fields.append(field)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, rows: list[dict]) -> None:
    """写出 Markdown 实验队列。

    参数:
        path: 输出路径。
        rows: 实验队列记录。

    返回:
        无。
    """
    fields = ["priority", "task_id", "resolves_gate", "requires_remote", "requires_secret", "command"]
    lines = [
        "# Experiment Queue",
        "",
        "## 使用边界",
        "",
        "该队列只列出下一轮实验命令，不包含远程连接信息或密钥值。执行后需重建 RQ、审稿矩阵和 readiness 报告。",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_experiment_queue_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出实验队列产物。

    参数:
        rows: 实验队列记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    resolved_output_dir = ensure_directory(output_dir)
    write_records(rows, resolved_output_dir / "experiment_queue.jsonl")
    _write_csv(resolved_output_dir / "experiment_queue.csv", rows)
    _write_markdown(resolved_output_dir / "experiment_queue.md", rows)
