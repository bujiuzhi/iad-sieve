"""测试 IAD-Sieve 论文级 RQ 报告汇总。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_iad_paper_report
from iad_sieve.evaluation.iad_paper_report import build_iad_paper_report
from iad_sieve.utils.io_utils import read_records


def _write_jsonl(path, records: list[dict]) -> None:
    """写入 JSONL 测试文件。

    参数:
        path: 输出路径。
        records: 记录列表。

    返回:
        无。
    """
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def _write_text(path, content: str) -> None:
    """写入文本文件。

    参数:
        path: 输出路径。
        content: 文本内容。

    返回:
        无。
    """
    path.write_text(content, encoding="utf-8")


def test_build_iad_paper_report_aggregates_gold_proxy_weak_and_external_rows(tmp_path) -> None:
    """验证报告聚合 gold、proxy、weak、external 和 classifier 摘要。"""
    gold_summary = tmp_path / "deepmatcher_summary.jsonl"
    proxy_summary = tmp_path / "scirepeval_summary.jsonl"
    weak_summary = tmp_path / "openalex_summary.jsonl"
    external_summary = tmp_path / "specter2_summary.jsonl"
    classifier_summary = tmp_path / "training_summary.jsonl"
    ablation_summary = tmp_path / "iad_ablation_summary.jsonl"
    iad_bench_summary = tmp_path / "iad_bench_summary.jsonl"
    iad_risk_summary = tmp_path / "iad_risk_summary.jsonl"
    bootstrap_summary = tmp_path / "iad_risk_bootstrap_confidence.csv"
    openalex_ingestion_summary = tmp_path / "openalex_ingestion_summary.jsonl"
    openalex_dataset_summary = tmp_path / "openalex_dataset_summary.jsonl"
    human_audit_plan = tmp_path / "annotation_requirements.md"
    output_dir = tmp_path / "paper_report"
    _write_jsonl(
        gold_summary,
        [
            {
                "system": "iad_sieve_conservative",
                "metric_target": "same_work_false_merge",
                "weak_label_count": 4,
                "precision": 1.0,
                "recall": 0.5,
                "f1": 0.666667,
                "false_merge_rate": 0.0,
            }
        ],
    )
    _write_jsonl(
        proxy_summary,
        [
            {
                "system": "iad_agenda_score_threshold",
                "metric_target": "same_agenda_proxy",
                "weak_label_count": 3,
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
                "false_merge_rate": 0.0,
            }
        ],
    )
    _write_jsonl(
        weak_summary,
        [
            {
                "system": "iad_sieve_conservative",
                "metric_target": "same_work_false_merge",
                "weak_label_count": 1,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "false_merge_rate": 0.0,
            }
        ],
    )
    _write_jsonl(
        external_summary,
        [
            {
                "system": "specter2_cosine",
                "metric_target": "same_work",
                "threshold": 0.9,
                "weak_label_count": 2,
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
                "false_merge_rate": 0.0,
            }
        ],
    )
    _write_jsonl(
        classifier_summary,
        [
            {
                "target": "agenda_non_identity",
                "trained": True,
                "model_type": "standardized_centroid_linear_classifier",
                "weak_label_count": 3,
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
                "false_merge_rate": 0.0,
            }
        ],
    )
    _write_jsonl(
        ablation_summary,
        [
            {
                "variant": "without_agenda_non_identity",
                "protocol_variant": "no-ANI-head",
                "protocol_required": True,
                "accepted_for_component_causality": True,
                "metric_target": "same_work_false_merge",
                "threshold_source": "predeclared_cli_argument",
                "weak_label_count": 5,
                "precision": 0.5,
                "recall": 1.0,
                "f1": 0.666667,
                "false_merge_rate": 0.25,
            }
        ],
    )
    _write_jsonl(
        iad_bench_summary,
        [
            {
                "evidence_layer": "iad_bench_provenance",
                "pair_count": 4,
                "gold_pair_count": 2,
                "proxy_pair_count": 1,
                "silver_pair_count": 1,
            }
        ],
    )
    _write_jsonl(
        iad_risk_summary,
        [
            {
                "evidence_layer": "iad_risk_model",
                "trained": True,
                "model_type": "iad_risk_dual_space_centroid_model",
                "head_count": 3,
                "embedding_model": "allenai/specter2_base",
                "adapter_model": "allenai/specter2",
                "embedding_version": "specter2-adapter",
                "weak_label_count": 6,
                "f1": 1.0,
            }
        ],
    )
    _write_text(
        bootstrap_summary,
        "system,metric_scope,stratum_name,stratum_value,pair_count,precision_mean,recall_mean,f1_mean,false_merge_rate_mean,hard_negative_false_merge_rate_mean,hard_negative_false_merge_rate_ci_low,hard_negative_false_merge_rate_ci_high\n"
        "iad_risk_dual_space,hard_negative_pairs,hard_negative_level,any,10,0,0,0,0,0,0,0\n",
    )
    _write_jsonl(
        openalex_ingestion_summary,
        [
            {
                "source": "openalex_api",
                "fetched_record_count": 50,
                "cursor_page_count": 2,
                "requested_max_records": 50,
                "filter": "publication_year:2024,type:article",
                "api_key_used": False,
                "status": "completed",
            }
        ],
    )
    _write_jsonl(
        openalex_dataset_summary,
        [
            {
                "dataset_name": "openalex_api_sample",
                "source_work_count": 50,
                "document_count": 14,
                "pair_count": 9,
                "agenda_non_identity_pair_count": 9,
                "min_shared_references": 1,
            }
        ],
    )
    _write_text(human_audit_plan, "# 标注要求\n\n先抽取 50 至 100 条样本试标；正式标注 500-1,000 条 pair 作为后续人工 audit。")

    rows = build_iad_paper_report(
        output_dir=output_dir,
        gold_summaries=[gold_summary],
        proxy_summaries=[proxy_summary],
        weak_summaries=[weak_summary],
        external_summaries=[external_summary],
        classifier_summaries=[classifier_summary],
        ablation_summaries=[ablation_summary],
        iad_bench_summaries=[iad_bench_summary],
        iad_risk_summaries=[iad_risk_summary],
        bootstrap_summaries=[bootstrap_summary],
        openalex_ingestion_summaries=[openalex_ingestion_summary],
        openalex_dataset_summaries=[openalex_dataset_summary],
        human_audit_plans=[human_audit_plan],
    )

    assert any(row["rq"] == "RQ1" and row["evidence_layer"] == "same_work_gold" for row in rows)
    assert any(row["rq"] == "RQ2" and row["evidence_layer"] == "same_agenda_proxy" for row in rows)
    assert any(row["rq"] == "RQ2" and row["evidence_layer"] == "agenda_non_identity_weak" for row in rows)
    assert any(row["rq"] == "RQ1" and row["evidence_layer"] == "external_baseline" for row in rows)
    assert any(row["rq"] == "RQ2" and row["evidence_layer"] == "iad_classifier_training" for row in rows)
    assert any(row["rq"] == "RQ3" and row["evidence_layer"] == "iad_ablation" and row["system"] == "without_agenda_non_identity" for row in rows)
    assert any(
        row["rq"] == "RQ3"
        and row["evidence_layer"] == "iad_ablation"
        and row["protocol_variant"] == "no-ANI-head"
        and row["threshold_source"] == "predeclared_cli_argument"
        for row in rows
    )
    assert any(row["rq"] == "RQ1" and row["evidence_layer"] == "iad_bench_provenance" for row in rows)
    assert any(row["rq"] == "RQ2" and row["evidence_layer"] == "iad_bench_provenance" for row in rows)
    assert any(row["rq"] == "RQ3" and row["evidence_layer"] == "iad_risk_model" for row in rows)
    assert any(
        row["rq"] == "RQ3"
        and row["evidence_layer"] == "iad_risk_model"
        and row.get("adapter_model") == "allenai/specter2"
        for row in rows
    )
    assert any(row["rq"] == "RQ2" and row["evidence_layer"] == "iad_bootstrap_confidence" for row in rows)
    assert any(row["rq"] == "RQ4" and row["evidence_layer"] == "openalex_api_ingestion" and row["fetched_record_count"] == 50 for row in rows)
    assert any(row["rq"] == "RQ2" and row["evidence_layer"] == "openalex_api_weak_dataset" and row["pair_count"] == 9 for row in rows)
    assert any(
        row["rq"] == "RQ2"
        and row["evidence_layer"] == "human_audit_plan"
        and row["planned_pair_count_min"] == 500
        and row["planned_pair_count_max"] == 1000
        for row in rows
    )
    assert (output_dir / "rq_summary.jsonl").exists()
    assert (output_dir / "rq_summary.csv").exists()
    assert "# IAD-Sieve Paper Report" in (output_dir / "paper_report.md").read_text(encoding="utf-8")


def test_build_iad_paper_report_skips_missing_optional_summaries(tmp_path) -> None:
    """验证缺失的可选 summary 不阻断部分证据报告重建。"""
    external_summary = tmp_path / "specter2_summary.jsonl"
    bootstrap_summary = tmp_path / "specter2_bootstrap.csv"
    missing_external_summary = tmp_path / "gpt_pair_judge_metric_summary.jsonl"
    missing_bootstrap_summary = tmp_path / "gpt_pair_judge_bootstrap.csv"
    output_dir = tmp_path / "paper_report"
    _write_jsonl(
        external_summary,
        [
            {
                "system": "specter2_adapter_cosine_open_v2",
                "metric_target": "same_work",
                "execution_mode": "actual_model",
                "f1": 0.75,
            }
        ],
    )
    _write_text(
        bootstrap_summary,
        "system,metric_scope,stratum_name,stratum_value,pair_count,precision_mean,recall_mean,f1_mean,false_merge_rate_mean\n"
        "specter2_adapter_cosine_open_v2,all_pairs,all,all,4,0.8,0.7,0.75,0.1\n",
    )

    rows = build_iad_paper_report(
        output_dir=output_dir,
        external_summaries=[external_summary, missing_external_summary],
        bootstrap_summaries=[bootstrap_summary, missing_bootstrap_summary],
    )

    source_files = {row["source_file"] for row in rows}
    assert str(external_summary) in source_files
    assert str(bootstrap_summary) in source_files
    assert str(missing_external_summary) not in source_files
    assert str(missing_bootstrap_summary) not in source_files


def test_build_iad_paper_report_cli_writes_report_files(tmp_path) -> None:
    """验证 CLI 写出报告文件。"""
    gold_summary = tmp_path / "deepmatcher_summary.jsonl"
    output_dir = tmp_path / "paper_report"
    _write_jsonl(
        gold_summary,
        [
            {
                "system": "iad_sieve_conservative",
                "metric_target": "same_work_false_merge",
                "weak_label_count": 2,
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
                "false_merge_rate": 0.0,
            }
        ],
    )

    command_build_iad_paper_report(
        Namespace(
            output_dir=str(output_dir),
            gold_summaries=[str(gold_summary)],
            proxy_summaries=[],
            weak_summaries=[],
            external_summaries=[],
            classifier_summaries=[],
            ablation_summaries=[],
            iad_bench_summaries=[],
            iad_risk_summaries=[],
            bootstrap_summaries=[],
            openalex_ingestion_summaries=[],
            openalex_dataset_summaries=[],
        )
    )

    rows = read_records(output_dir / "rq_summary.jsonl")

    assert rows[0]["rq"] == "RQ1"
    assert (output_dir / "paper_report.md").exists()


def test_cli_includes_build_iad_paper_report_command() -> None:
    """验证 CLI 暴露 build-iad-paper-report 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-iad-paper-report",
            "--output-dir",
            "outputs/iad_paper_report",
            "--gold-summaries",
            "outputs/deepmatcher_fixture/summary.jsonl",
            "--external-summaries",
            "outputs/external_baseline_fixture/specter2_summary.jsonl",
            "--ablation-summaries",
            "outputs/iad_ablation_fixture/iad_ablation_summary.jsonl",
            "--iad-bench-summaries",
            "outputs/iad_bench_fixture/iad_bench_summary.jsonl",
            "--iad-risk-summaries",
            "outputs/iad_risk_model_fixture/iad_risk_summary.jsonl",
            "--bootstrap-summaries",
            "outputs/iad_bootstrap_fixture/iad_risk_bootstrap_confidence.csv",
            "--openalex-ingestion-summaries",
            "outputs/openalex_api_ingestion_fixture/ingestion_summary.jsonl",
            "--openalex-dataset-summaries",
            "outputs/openalex_api_fixture/dataset_summary.jsonl",
            "--human-audit-plans",
            "docs/annotation-requirements.md",
        ]
    )

    assert args.command == "build-iad-paper-report"
    assert args.gold_summaries == ["outputs/deepmatcher_fixture/summary.jsonl"]
    assert args.ablation_summaries == ["outputs/iad_ablation_fixture/iad_ablation_summary.jsonl"]
    assert args.iad_bench_summaries == ["outputs/iad_bench_fixture/iad_bench_summary.jsonl"]
    assert args.iad_risk_summaries == ["outputs/iad_risk_model_fixture/iad_risk_summary.jsonl"]
    assert args.bootstrap_summaries == ["outputs/iad_bootstrap_fixture/iad_risk_bootstrap_confidence.csv"]
    assert args.openalex_ingestion_summaries == ["outputs/openalex_api_ingestion_fixture/ingestion_summary.jsonl"]
    assert args.openalex_dataset_summaries == ["outputs/openalex_api_fixture/dataset_summary.jsonl"]
    assert args.human_audit_plans == ["docs/annotation-requirements.md"]
