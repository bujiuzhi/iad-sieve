"""iad-sieve 命令行入口。"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from collections.abc import Iterable, Iterator

from iad_sieve.candidates.candidate_merger import merge_candidate_pairs
from iad_sieve.candidates.dense_candidate_generator import generate_dense_candidates
from iad_sieve.candidates.identifier_candidate_generator import generate_identifier_candidates
from iad_sieve.candidates.lexical_candidate_generator import generate_lexical_candidates
from iad_sieve.candidates.title_candidate_generator import generate_title_candidates
from iad_sieve.clustering.clusterer import cluster_documents
from iad_sieve.clustering.topic_graph_builder import build_topic_graph_edges
from iad_sieve.data.arxiv_loader import stream_arxiv_metadata
from iad_sieve.data.sampler import prepare_sample
from iad_sieve.deduplication.dedup_pipeline import merge_duplicates
from iad_sieve.embedding.embedding_cache import load_embeddings, save_embeddings
from iad_sieve.embedding.encoder import encode_documents
from iad_sieve.embedding.vector_store import build_vector_index
from iad_sieve.evaluation.ablation_runner import run_ablation_summary
from iad_sieve.evaluation.advanced_model_evidence_matrix import build_advanced_model_evidence_rows_from_paths, write_advanced_model_evidence_outputs
from iad_sieve.evaluation.artifact_exporter import export_paper_artifacts
from iad_sieve.evaluation.baseline_error_analysis import build_baseline_error_analysis, write_baseline_error_analysis_outputs
from iad_sieve.evaluation.baseline_runner import run_baseline_summary
from iad_sieve.evaluation.bootstrap_confidence import (
    run_bootstrap_confidence,
    run_iad_evidence_bootstrap,
    write_bootstrap_csv,
    write_iad_bootstrap_csv,
)
from iad_sieve.evaluation.candidate_cap_analysis import run_candidate_cap_analysis, write_candidate_cap_csv
from iad_sieve.evaluation.clustering_evaluator import evaluate_clustering, run_cluster_contamination_bootstrap, write_cluster_bootstrap_csv
from iad_sieve.evaluation.deepmatcher_adapter import prepare_deepmatcher_evaluation_set
from iad_sieve.evaluation.dedup_evaluator import evaluate_deduplication
from iad_sieve.evaluation.error_analysis import build_error_analysis, write_error_analysis_outputs
from iad_sieve.evaluation.eval_set_builder import build_evaluation_set, score_evaluation_pairs, summarize_scored_eval_pairs
from iad_sieve.evaluation.external_baseline_adapter import (
    attach_external_baseline_scores,
    evaluate_external_baseline,
    read_external_baseline_scores,
)
from iad_sieve.evaluation.heldout_assignment_applier import apply_heldout_split_assignments_from_paths, write_heldout_split_assignment_outputs
from iad_sieve.evaluation.entity_matching_baseline_runner import run_entity_matching_baseline, write_entity_matching_scores
from iad_sieve.evaluation.entity_matching_baseline_trainer import train_entity_matching_baseline, write_entity_matching_training_summary
from iad_sieve.evaluation.experiment_dependency import build_experiment_dependency_rows_from_paths, write_experiment_dependency_outputs
from iad_sieve.evaluation.experiment_execution_pack import build_experiment_execution_rows_from_paths, write_experiment_execution_pack_outputs
from iad_sieve.evaluation.experiment_preflight import build_experiment_preflight_rows_from_paths, write_experiment_preflight_outputs
from iad_sieve.evaluation.experiment_queue import build_experiment_queue_rows, write_experiment_queue_outputs
from iad_sieve.evaluation.hard_negative_stress_builder import build_hard_negative_stress_set_from_paths, write_hard_negative_stress_outputs
from iad_sieve.evaluation.iad_ablation_suite import run_iad_ablation_suite, write_iad_ablation_outputs
from iad_sieve.evaluation.iad_bench_balanced_subset import build_iad_bench_balanced_subset_from_paths, write_iad_bench_balanced_subset_outputs
from iad_sieve.evaluation.iad_bench_builder import build_iad_bench
from iad_sieve.evaluation.iad_bench_provenance_balance_plan import build_iad_bench_provenance_balance_plan_rows_from_paths, write_iad_bench_provenance_balance_plan_outputs
from iad_sieve.evaluation.iad_bench_source_acquisition_audit import (
    build_iad_bench_source_acquisition_audit_rows_from_paths,
    write_iad_bench_source_acquisition_audit_outputs,
)
from iad_sieve.evaluation.iad_bench_source_candidate_registry import (
    build_iad_bench_source_candidate_registry_rows_from_paths,
    write_iad_bench_source_candidate_registry_outputs,
)
from iad_sieve.evaluation.iad_bench_source_bias_diagnostic import build_iad_bench_source_bias_diagnostic_rows_from_paths, write_iad_bench_source_bias_diagnostic_outputs
from iad_sieve.evaluation.iad_bench_stratification_audit import build_iad_bench_stratification_audit_rows_from_paths, write_iad_bench_stratification_audit_outputs
from iad_sieve.evaluation.iad_model_feature_guard import build_iad_model_feature_guard_rows_from_paths, write_iad_model_feature_guard_outputs
from iad_sieve.evaluation.innovation_depth_stress_test import build_innovation_depth_stress_rows_from_paths, write_innovation_depth_stress_outputs
from iad_sieve.evaluation.llm_judge_baseline_runner import run_llm_judge_baseline, write_llm_judge_scores
from iad_sieve.evaluation.manuscript_draft_skeleton import build_manuscript_draft_rows_from_paths, write_manuscript_draft_outputs
from iad_sieve.evaluation.manuscript_evidence_matrix import build_manuscript_evidence_rows_from_paths, write_manuscript_evidence_outputs
from iad_sieve.evaluation.manual_annotation_evaluator import evaluate_manual_annotations, write_manual_annotation_outputs
from iad_sieve.evaluation.mechanism_error_evidence import (
    build_mechanism_error_evidence_rows_from_paths,
    build_mechanism_threshold_sensitivity_rows,
    write_mechanism_error_evidence_outputs,
)
from iad_sieve.evaluation.mechanism_case_pack import build_mechanism_case_pack_rows_from_paths, write_mechanism_case_pack_outputs
from iad_sieve.evaluation.model_innovation_blueprint import (
    build_model_innovation_blueprint_rows_from_paths,
    write_model_innovation_blueprint_outputs,
)
from iad_sieve.evaluation.model_superiority_audit import build_model_superiority_audit_rows_from_paths, write_model_superiority_audit_outputs
from iad_sieve.evaluation.mechanism_triangulation_audit import build_mechanism_triangulation_rows_from_paths, write_mechanism_triangulation_outputs
from iad_sieve.evaluation.mechanism_triangulation_sensitivity import (
    build_mechanism_triangulation_sensitivity_rows_from_paths,
    write_mechanism_triangulation_sensitivity_outputs,
)
from iad_sieve.evaluation.no_annotation_protocol import build_no_annotation_protocol_rows_from_paths, write_no_annotation_protocol_outputs
from iad_sieve.evaluation.novelty_falsification_matrix import build_novelty_falsification_rows_from_paths, write_novelty_falsification_outputs
from iad_sieve.evaluation.openalex_adapter import prepare_openalex_weak_label_evaluation_set
from iad_sieve.evaluation.openalex_api_ingestion import fetch_openalex_works, write_openalex_ingestion_outputs
from iad_sieve.evaluation.open_v3_heldout_split_plan import build_open_v3_heldout_split_plan_rows_from_paths, write_open_v3_heldout_split_plan_outputs
from iad_sieve.evaluation.open_v3_plan_audit import build_open_v3_plan_audit_rows_from_paths, write_open_v3_plan_audit_outputs
from iad_sieve.evaluation.open_v3_split_readiness import build_open_v3_split_readiness_rows_from_paths, write_open_v3_split_readiness_outputs
from iad_sieve.evaluation.open_v3_source_plan import build_open_v3_source_plan_rows_from_paths, write_open_v3_source_plan_outputs
from iad_sieve.evaluation.paper_claim_audit import build_paper_claim_audit_rows_from_paths, write_paper_claim_audit_outputs
from iad_sieve.evaluation.primary_remote_handoff import build_primary_remote_handoff_rows_from_paths, write_primary_remote_handoff_outputs
from iad_sieve.evaluation.primary_remote_readiness import build_primary_remote_readiness_rows_from_paths, write_primary_remote_readiness_outputs
from iad_sieve.evaluation.primary_track_claim_gate import build_primary_track_claim_gate_rows_from_paths, write_primary_track_claim_gate_outputs
from iad_sieve.evaluation.primary_track_superiority_protocol import (
    build_primary_track_superiority_protocol_rows_from_paths,
    write_primary_track_superiority_protocol_outputs,
)
from iad_sieve.evaluation.primary_track_superiority_evaluator import (
    build_primary_track_superiority_evaluator_rows_from_paths,
    write_primary_track_superiority_evaluator_outputs,
)
from iad_sieve.evaluation.prior_art_novelty_audit import build_prior_art_novelty_rows_from_paths, write_prior_art_novelty_outputs
from iad_sieve.evaluation.public_data_validity_audit import build_public_data_validity_audit_rows_from_paths, write_public_data_validity_audit_outputs
from iad_sieve.evaluation.q2b_acceptance_rubric import build_q2b_acceptance_rubric_rows_from_paths, write_q2b_acceptance_rubric_outputs
from iad_sieve.evaluation.q2b_action_board import build_q2b_action_board_rows_from_paths, write_q2b_action_board_outputs
from iad_sieve.evaluation.q2b_completion_audit import build_q2b_completion_audit_rows_from_paths, write_q2b_completion_audit_outputs
from iad_sieve.evaluation.q2b_external_blocker_audit import (
    build_q2b_external_blocker_rows_from_paths,
    write_q2b_external_blocker_outputs,
)
from iad_sieve.evaluation.q2b_experiment_optimizer import build_q2b_experiment_optimizer_rows_from_paths, write_q2b_experiment_optimizer_outputs
from iad_sieve.evaluation.q2b_upgrade_roadmap import build_q2b_upgrade_roadmap_rows_from_paths, write_q2b_upgrade_roadmap_outputs
from iad_sieve.evaluation.ranking_evaluator import evaluate_ranking
from iad_sieve.evaluation.recommendation_evaluator import evaluate_recommendations
from iad_sieve.evaluation.research_depth_audit import build_research_depth_audit_rows_from_paths, write_research_depth_audit_outputs
from iad_sieve.evaluation.reviewer_response_matrix import build_reviewer_response_rows_from_paths, write_reviewer_response_outputs
from iad_sieve.evaluation.reviewer_iteration_audit import build_reviewer_iteration_audit_rows_from_paths, write_reviewer_iteration_audit_outputs
from iad_sieve.evaluation.reviewer_threat_model import build_reviewer_threat_model_rows_from_paths, write_reviewer_threat_model_outputs
from iad_sieve.evaluation.reviewer_audit import build_reviewer_audit_rows, write_reviewer_audit_outputs
from iad_sieve.evaluation.risk_calibrated_protocol import run_risk_calibrated_protocol, write_risk_calibrated_protocol_outputs
from iad_sieve.evaluation.remote_environment_audit import build_remote_environment_audit_rows, write_remote_environment_audit_outputs
from iad_sieve.evaluation.remote_connection_pack import (
    build_remote_connection_pack_rows_from_paths,
    build_remote_connection_profile,
    write_remote_connection_pack_outputs,
    write_remote_connection_profile,
)
from iad_sieve.evaluation.remote_execution_blueprint import build_remote_execution_blueprint_rows_from_paths, write_remote_execution_blueprint_outputs
from iad_sieve.evaluation.remote_execution_slice import build_remote_execution_slice_rows_from_paths, write_remote_execution_slice_outputs
from iad_sieve.evaluation.remote_input_request import build_remote_input_request_rows_from_paths, write_remote_input_request_outputs
from iad_sieve.evaluation.remote_output_validator import build_remote_output_validation_rows_from_path, write_remote_output_validation_outputs
from iad_sieve.evaluation.remote_result_acceptance import build_remote_result_acceptance_rows_from_paths, write_remote_result_acceptance_outputs
from iad_sieve.evaluation.remote_slice_run_pack import build_remote_slice_run_pack_rows_from_paths, write_remote_slice_run_pack_outputs
from iad_sieve.evaluation.sensitivity import run_parameter_sensitivity, write_sensitivity_csv
from iad_sieve.evaluation.scirepeval_adapter import prepare_scirepeval_proximity_evaluation_set
from iad_sieve.evaluation.single_space_union_baseline import run_single_space_union_baseline, write_single_space_union_outputs
from iad_sieve.evaluation.stress_cluster_contamination import (
    build_stress_cluster_contamination_audit_from_paths,
    write_stress_cluster_contamination_outputs,
)
from iad_sieve.evaluation.submission_gate_audit import build_submission_gate_audit_rows_from_paths, write_submission_gate_audit_outputs
from iad_sieve.evaluation.strong_baseline_runner import run_representation_baseline, write_baseline_scores
from iad_sieve.evaluation.threshold_calibrator import run_iad_threshold_calibration, write_iad_calibration_csv
from iad_sieve.evaluation.iad_classifier import build_training_summary, train_iad_relation_model, write_iad_model_json
from iad_sieve.evaluation.iad_paper_report import build_iad_paper_report
from iad_sieve.evaluation.iad_risk_model import train_iad_risk_model, write_iad_risk_outputs
from iad_sieve.evaluation.iad_risk_split_evaluation_audit import (
    build_iad_risk_split_evaluation_audit_rows_from_paths,
    write_iad_risk_split_evaluation_audit_outputs,
)
from iad_sieve.evaluation.iad_risk_transformer_model import train_iad_risk_transformer_model, write_iad_risk_transformer_outputs
from iad_sieve.evaluation.iad_source_heldout_coverage_audit import (
    build_iad_source_heldout_coverage_rows_from_paths,
    write_iad_source_heldout_coverage_outputs,
)
from iad_sieve.evaluation.iad_source_heldout_gap_plan import (
    build_iad_source_heldout_gap_plan_rows_from_paths,
    write_iad_source_heldout_gap_plan_outputs,
)
from iad_sieve.evaluation.iad_training_blend_builder import build_iad_training_blend_from_paths, write_iad_training_blend_outputs
from iad_sieve.evaluation.iad_training_input_audit import build_iad_training_input_audit_rows_from_paths, write_iad_training_input_audit_outputs
from iad_sieve.evaluation.journal_readiness import build_journal_readiness_rows, write_journal_readiness_outputs
from iad_sieve.evaluation.journal_upgrade_plan import build_journal_upgrade_plan_rows_from_paths, write_journal_upgrade_plan_outputs
from iad_sieve.evaluation.topic_package_exporter import export_topic_package
from iad_sieve.logging_config import configure_logging
from iad_sieve.preprocessing.preprocessor import normalize_documents
from iad_sieve.ranking.importance_ranker import rank_documents
from iad_sieve.recommendation.recommendation_ranker import rank_recommendations
from iad_sieve.relations.relation_pipeline import score_candidate_pairs, score_candidate_pairs_iter
from iad_sieve.relations.adaptive_threshold import get_default_thresholds
from iad_sieve.utils.io_utils import ensure_directory, read_jsonl, read_records, write_jsonl, write_records
from iad_sieve.utils.random_utils import set_random_seed
from iad_sieve.views.semantic_view_extractor import build_semantic_views


LOGGER = logging.getLogger(__name__)
DEFAULT_QUERIES = [
    "semantic deduplication scientific papers",
    "scientific literature clustering recommendation",
    "relation separated duplicate detection",
    "survey of literature recommendation methods",
    "benchmark dataset for paper retrieval",
]


def add_common_io_arguments(parser: argparse.ArgumentParser) -> None:
    """添加通用 IO 参数。

    参数:
        parser: argparse 子命令解析器。

    返回:
        无。
    """
    parser.add_argument("--limit", type=int, default=None, help="最多读取记录数")
    parser.add_argument("--sample-size", type=int, default=None, help="样本数量")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")


def add_relation_threshold_arguments(parser: argparse.ArgumentParser) -> None:
    """添加关系分类阈值参数。

    参数:
        parser: argparse 子命令解析器。

    返回:
        无。
    """
    parser.add_argument("--duplicate-threshold", type=float, default=None, help="自动重复合并阈值")
    parser.add_argument("--review-threshold", type=float, default=None, help="高置信复核阈值")
    parser.add_argument("--review-candidate-threshold", type=float, default=None, help="候选复核池阈值")
    parser.add_argument("--topic-threshold", type=float, default=None, help="同主题非重复阈值")
    parser.add_argument("--contribution-threshold", type=float, default=None, help="贡献差异阈值")
    parser.add_argument("--conflict-threshold", type=float, default=None, help="冲突分数阈值")


def build_relation_thresholds_from_args(args: argparse.Namespace) -> dict[str, float]:
    """从 CLI 参数构造关系分类阈值。

    参数:
        args: 命令行参数。

    返回:
        阈值字典。
    """
    thresholds = get_default_thresholds()
    arg_to_key = {
        "duplicate_threshold": "duplicate_threshold",
        "review_threshold": "review_threshold",
        "review_candidate_threshold": "review_candidate_threshold",
        "topic_threshold": "topic_threshold",
        "contribution_threshold": "contribution_threshold",
        "conflict_threshold": "conflict_threshold",
    }
    for arg_name, threshold_key in arg_to_key.items():
        value = getattr(args, arg_name, None)
        if value is not None:
            thresholds[threshold_key] = float(value)
    return thresholds


def iter_sharded_records(records: Iterable[dict], shard_count: int = 1, shard_index: int = 0) -> Iterator[dict]:
    """按记录序号取模返回指定分片。

    参数:
        records: 输入记录迭代器。
        shard_count: 总分片数。
        shard_index: 当前分片序号，从 0 开始。

    返回:
        当前分片记录迭代器。
    """
    if shard_count < 1:
        raise ValueError("shard_count 必须大于等于 1")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("shard_index 必须满足 0 <= shard_index < shard_count")
    for index, record in enumerate(records):
        if index % shard_count == shard_index:
            yield record


def command_prepare_sample(args: argparse.Namespace) -> None:
    """执行 prepare-sample 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    count = prepare_sample(args.input, args.output, args.sample_size, args.seed, args.primary_category, args.limit)
    LOGGER.info("样本准备完成: %s records -> %s", count, args.output)


def command_preprocess(args: argparse.Namespace) -> None:
    """执行 preprocess 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    records = list(stream_arxiv_metadata(args.input, limit=args.limit)) if str(args.input).endswith(".json") else read_records(args.input, limit=args.limit)
    if args.sample_size is not None:
        records = records[: args.sample_size]
    normalized = normalize_documents(records)
    write_records(normalized, args.output)
    LOGGER.info("标准化完成: %s", args.output)


def command_build_views(args: argparse.Namespace) -> None:
    """执行 build-views 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    records = read_records(args.input, limit=args.limit)
    views = build_semantic_views(records)
    write_records(views, args.output)
    LOGGER.info("语义视图完成: %s", args.output)


def command_embed(args: argparse.Namespace) -> None:
    """执行 embed 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    records = read_records(args.input, limit=args.limit)
    document_ids, embeddings, metadata = encode_documents(records, args.embedding_model, args.batch_size)
    save_embeddings(document_ids, embeddings, args.output_dir, metadata)
    build_vector_index(embeddings, args.output_dir)
    LOGGER.info("embedding 完成: %s", args.output_dir)


def _load_embedding_lookup(embedding_dir: str | None) -> tuple[list[str], list[list[float]], dict[str, list[float]]]:
    """读取 embedding 映射。

    参数:
        embedding_dir: embedding 目录。

    返回:
        ID 列表、向量列表和映射。
    """
    if not embedding_dir:
        return [], [], {}
    document_ids, embeddings = load_embeddings(embedding_dir)
    return document_ids, embeddings, dict(zip(document_ids, embeddings, strict=True))


def command_generate_candidates(args: argparse.Namespace) -> None:
    """执行 generate-candidates 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    records = read_records(args.input, limit=args.limit)
    views = read_records(args.views) if args.views else []
    document_ids, embeddings, _ = _load_embedding_lookup(args.embedding_dir)
    candidate_groups = [
        generate_identifier_candidates(records),
        generate_title_candidates(records, max_block_size=args.title_max_block_size),
        generate_lexical_candidates(
            records,
            views,
            top_k=args.lexical_top_k,
            min_shared_tokens=args.lexical_min_shared_tokens,
            max_postings_per_token=args.lexical_max_postings_per_token,
            max_neighbors_per_token=args.lexical_max_neighbors_per_token,
            max_candidate_pairs=args.lexical_max_candidate_pairs,
        ),
    ]
    if document_ids and embeddings:
        candidate_groups.append(generate_dense_candidates(document_ids, embeddings, top_k=args.dense_top_k, brute_force_limit=args.dense_brute_force_limit))
    candidates = merge_candidate_pairs(candidate_groups, max_candidate_per_document=args.max_candidate_per_document)
    write_records(candidates, args.output)
    LOGGER.info("候选对生成完成: %s", args.output)


def command_score_relations(args: argparse.Namespace) -> None:
    """执行 score-relations 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    documents = read_records(args.input, limit=args.limit)
    views = read_records(args.views) if args.views else []
    _, _, embedding_lookup = _load_embedding_lookup(args.embedding_dir)
    thresholds = build_relation_thresholds_from_args(args)
    if Path(args.output).suffix == ".jsonl":
        candidate_records = read_jsonl(args.candidates)
        candidate_records = iter_sharded_records(candidate_records, shard_count=args.shard_count, shard_index=args.shard_index)
        relations = score_candidate_pairs_iter(candidate_records, documents, views, embedding_lookup, thresholds=thresholds)
        count = write_jsonl(relations, args.output)
    else:
        candidates = read_records(args.candidates)
        relations = score_candidate_pairs(candidates, documents, views, embedding_lookup, thresholds=thresholds)
        count = write_records(relations, args.output)
    LOGGER.info("关系评分完成: %s records=%s", args.output, count)


def command_merge_duplicates(args: argparse.Namespace) -> None:
    """执行 merge-duplicates 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    documents = read_records(args.input, limit=args.limit)
    relations = read_records(args.relations)
    duplicate_groups, canonical_documents = merge_duplicates(documents, relations)
    output_dir = ensure_directory(args.output_dir)
    write_records(duplicate_groups, output_dir / "duplicate_groups.jsonl")
    write_records(canonical_documents, output_dir / "canonical_documents.jsonl")
    LOGGER.info("重复组合并完成: %s", output_dir)


def command_build_topic_graph(args: argparse.Namespace) -> None:
    """执行 build-topic-graph 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    relations = read_records(args.relations, limit=args.limit)
    edges = build_topic_graph_edges(relations)
    write_records(edges, args.output)
    LOGGER.info("主题图完成: %s", args.output)


def command_cluster(args: argparse.Namespace) -> None:
    """执行 cluster 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    documents = read_records(args.input, limit=args.limit)
    topic_edges = read_records(args.topic_graph) if args.topic_graph else []
    clusters, memberships = cluster_documents(documents, topic_edges)
    output_dir = ensure_directory(args.output_dir)
    write_records(clusters, output_dir / "clusters.jsonl")
    write_records(memberships, output_dir / "cluster_membership.jsonl")
    LOGGER.info("聚类完成: %s", output_dir)


def command_rank(args: argparse.Namespace) -> None:
    """执行 rank 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    documents = read_records(args.input, limit=args.limit)
    rankings = rank_documents(documents)
    write_records(rankings, args.output)
    LOGGER.info("排序完成: %s", args.output)


def command_recommend(args: argparse.Namespace) -> None:
    """执行 recommend 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    documents = read_records(args.input, limit=args.limit)
    rankings = read_records(args.rankings) if args.rankings else []
    recommendations = rank_recommendations(args.query, documents, rankings, limit=args.limit or 20, rank_profile=args.rank_profile)
    write_records(recommendations, args.output)
    LOGGER.info("推荐完成: %s", args.output)


def command_evaluate(args: argparse.Namespace) -> None:
    """执行 evaluate 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    output_dir = ensure_directory(args.output_dir)
    duplicate_groups = read_records(args.duplicate_groups) if args.duplicate_groups else []
    relations = read_records(args.relations) if args.relations else []
    eval_split = getattr(args, "eval_split", None)
    if eval_split:
        relations = [relation for relation in relations if str(relation.get("split", "")).strip() == eval_split]
    clusters = read_records(args.clusters) if args.clusters else []
    cluster_memberships = read_records(getattr(args, "cluster_membership", None)) if getattr(args, "cluster_membership", None) else []
    risk_protocol_rows = read_records(getattr(args, "risk_protocol", None)) if getattr(args, "risk_protocol", None) else None
    rankings = read_records(args.rankings) if args.rankings else []
    recommendations = read_records(args.recommendations) if args.recommendations else []
    summary = {
        "dedup": evaluate_deduplication(duplicate_groups, relations),
        "clustering": evaluate_clustering(
            clusters,
            relations=relations,
            memberships=cluster_memberships,
            prediction_field=getattr(args, "cluster_prediction_field", None),
            score_field=getattr(args, "cluster_score_field", None),
            score_threshold=getattr(args, "cluster_score_threshold", None),
            risk_protocol_rows=risk_protocol_rows,
            risk_system=getattr(args, "risk_system", None),
            risk_fpr_budget=getattr(args, "risk_fpr_budget", None),
            risk_fdr_budget=getattr(args, "risk_fdr_budget", None),
            identity_field=getattr(args, "identity_field", "identity_score"),
            conflict_field=getattr(args, "conflict_field", "conflict_score"),
            uncertainty_field=getattr(args, "uncertainty_field", "uncertainty_score"),
            version_risk_field=getattr(args, "version_risk_field", "version_risk_score"),
        ),
        "ranking": evaluate_ranking(rankings),
        "recommendation": evaluate_recommendations(recommendations),
        "baseline": run_baseline_summary(relations),
        "ablation": run_ablation_summary(relations, rankings=rankings, recommendations=recommendations),
    }
    report_path = output_dir / "evaluation_summary.md"
    lines = ["# Evaluation Summary", "", "## Metrics", ""]
    for section, metrics in summary.items():
        lines.append(f"### {section}")
        lines.append("")
        lines.append(f"```json\n{json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True)}\n```")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    LOGGER.info("评估报告完成: %s", report_path)


def command_run_cluster_contamination_bootstrap(args: argparse.Namespace) -> None:
    """执行 run-cluster-contamination-bootstrap 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    relations = read_records(args.relations, limit=args.limit)
    eval_split = getattr(args, "eval_split", None)
    if eval_split:
        relations = [relation for relation in relations if str(relation.get("split", "")).strip() == eval_split]
    risk_protocol_rows = read_records(getattr(args, "risk_protocol", None)) if getattr(args, "risk_protocol", None) else None
    rows = run_cluster_contamination_bootstrap(
        relations,
        system_name=args.system_name,
        iterations=args.iterations,
        seed=args.seed,
        confidence_level=args.confidence_level,
        prediction_field=getattr(args, "cluster_prediction_field", None),
        score_field=getattr(args, "cluster_score_field", None),
        score_threshold=getattr(args, "cluster_score_threshold", None),
        risk_protocol_rows=risk_protocol_rows,
        risk_system=getattr(args, "risk_system", None),
        risk_fpr_budget=getattr(args, "risk_fpr_budget", None),
        risk_fdr_budget=getattr(args, "risk_fdr_budget", None),
        identity_field=getattr(args, "identity_field", "identity_score"),
        conflict_field=getattr(args, "conflict_field", "conflict_score"),
        uncertainty_field=getattr(args, "uncertainty_field", "uncertainty_score"),
        version_risk_field=getattr(args, "version_risk_field", "version_risk_score"),
    )
    write_cluster_bootstrap_csv(rows, args.output)
    LOGGER.info("cluster contamination bootstrap 完成: %s rows=%s", args.output, len(rows))


def command_export_paper_artifacts(args: argparse.Namespace) -> None:
    """执行 export-paper-artifacts 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    export_paper_artifacts(args.input, args.output_dir)


def command_build_eval_set(args: argparse.Namespace) -> None:
    """执行 build-eval-set 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    documents = read_records(args.input, limit=args.limit)
    relations = read_records(args.relations) if args.relations else []
    eval_documents, eval_pairs = build_evaluation_set(
        documents,
        relations,
        synthetic_count=args.synthetic_count,
        hard_negative_count=args.hard_negative_count,
        seed=args.seed,
    )
    output_dir = ensure_directory(args.output_dir)
    write_records(eval_documents, output_dir / "eval_documents.jsonl")
    write_records(eval_pairs, output_dir / "eval_pairs.jsonl")
    LOGGER.info("评估集输出完成: %s documents=%s pairs=%s", output_dir, len(eval_documents), len(eval_pairs))


def command_score_eval_set(args: argparse.Namespace) -> None:
    """执行 score-eval-set 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    documents = read_records(args.documents, limit=args.limit)
    pairs = read_records(args.pairs)
    scored_relations = score_evaluation_pairs(documents, pairs)
    write_records(scored_relations, args.output)
    summary_rows = summarize_scored_eval_pairs(scored_relations)
    if args.summary_output:
        write_records(summary_rows, args.summary_output)
    LOGGER.info("评估集评分完成: output=%s pairs=%s", args.output, len(scored_relations))


def command_prepare_deepmatcher(args: argparse.Namespace) -> None:
    """执行 prepare-deepmatcher 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    documents, pairs, summary = prepare_deepmatcher_evaluation_set(args.table_a, args.table_b, args.pairs, args.dataset_name)
    output_dir = ensure_directory(args.output_dir)
    write_records(documents, output_dir / "eval_documents.jsonl")
    write_records(pairs, output_dir / "eval_pairs.jsonl")
    write_records([summary], output_dir / "dataset_summary.jsonl")
    LOGGER.info("DeepMatcher 评估集输出完成: %s documents=%s pairs=%s", output_dir, len(documents), len(pairs))


def command_prepare_scirepeval_proximity(args: argparse.Namespace) -> None:
    """执行 prepare-scirepeval-proximity 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    documents, pairs, summary = prepare_scirepeval_proximity_evaluation_set(
        args.metadata,
        args.pairs,
        args.dataset_name,
        min_relevance_score=args.min_relevance_score,
    )
    output_dir = ensure_directory(args.output_dir)
    write_records(documents, output_dir / "eval_documents.jsonl")
    write_records(pairs, output_dir / "eval_pairs.jsonl")
    write_records([summary], output_dir / "dataset_summary.jsonl")
    LOGGER.info("SciRepEval proximity 评估集输出完成: %s documents=%s pairs=%s", output_dir, len(documents), len(pairs))


def command_prepare_openalex_weak_labels(args: argparse.Namespace) -> None:
    """执行 prepare-openalex-weak-labels 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    documents, pairs, summary = prepare_openalex_weak_label_evaluation_set(
        args.works,
        args.dataset_name,
        citations_path=getattr(args, "citations", None),
        min_shared_references=args.min_shared_references,
        max_pairs_per_topic=args.max_pairs_per_topic,
        max_pairs=args.max_pairs,
        limit=args.limit,
        require_opencitations=getattr(args, "require_opencitations", False),
    )
    output_dir = ensure_directory(args.output_dir)
    write_records(documents, output_dir / "eval_documents.jsonl")
    write_records(pairs, output_dir / "eval_pairs.jsonl")
    write_records([summary], output_dir / "dataset_summary.jsonl")
    LOGGER.info("OpenAlex 弱监督评估集输出完成: %s documents=%s pairs=%s", output_dir, len(documents), len(pairs))


def command_fetch_openalex_works(args: argparse.Namespace) -> None:
    """执行 fetch-openalex-works 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    records, summary = fetch_openalex_works(
        filter_expression=args.filter,
        select_fields=args.select,
        per_page=args.per_page,
        max_records=args.max_records,
        seed=args.seed,
        sample_size=args.sample_size,
        mailto=args.mailto,
        api_key=args.api_key or os.environ.get("OPENALEX_API_KEY"),
        endpoint=args.endpoint,
        timeout=args.timeout,
    )
    write_openalex_ingestion_outputs(records, summary, args.output, args.summary_output)
    LOGGER.info("OpenAlex API Works 拉取完成: output=%s records=%s", args.output, len(records))


def _parse_float_list(raw_value: str | None) -> list[float] | None:
    """解析逗号分隔浮点列表。

    参数:
        raw_value: 原始字符串。

    返回:
        浮点列表；空值返回 None。
    """
    if not raw_value:
        return None
    return [float(value.strip()) for value in raw_value.split(",") if value.strip()]


def _parse_int_list(raw_value: str | None) -> list[int] | None:
    """解析逗号分隔整数列表。

    参数:
        raw_value: 原始字符串。

    返回:
        整数列表；空值返回 None。
    """
    if not raw_value:
        return None
    return [int(value.strip()) for value in raw_value.split(",") if value.strip()]


def _parse_str_list(raw_value: str | None) -> list[str] | None:
    """解析逗号分隔字符串列表。

    参数:
        raw_value: 原始字符串。

    返回:
        字符串列表；空值返回 None。
    """
    if not raw_value:
        return None
    return [value.strip() for value in raw_value.split(",") if value.strip()]


def command_run_sensitivity(args: argparse.Namespace) -> None:
    """执行 run-sensitivity 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    relations = read_records(args.relations, limit=args.limit)
    rows = run_parameter_sensitivity(
        relations,
        duplicate_thresholds=_parse_float_list(args.duplicate_thresholds),
        topic_thresholds=_parse_float_list(args.topic_thresholds),
        candidate_caps=_parse_int_list(args.candidate_caps),
        review_threshold=args.review_threshold,
        duplicate_threshold_for_tlnd=args.duplicate_threshold_for_tlnd,
        contribution_threshold=args.contribution_threshold,
        conflict_threshold=args.conflict_threshold,
    )
    write_sensitivity_csv(rows, args.output)
    LOGGER.info("参数敏感性分析完成: %s rows=%s", args.output, len(rows))


def command_run_iad_calibration(args: argparse.Namespace) -> None:
    """执行 run-iad-calibration 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    relations = read_records(args.relations, limit=args.limit)
    rows = run_iad_threshold_calibration(
        relations,
        identity_thresholds=_parse_float_list(args.identity_thresholds),
        agenda_thresholds=_parse_float_list(args.agenda_thresholds),
        false_merge_rate_constraint=args.false_merge_rate_constraint,
        false_merge_risk_threshold=args.false_merge_risk_threshold,
    )
    write_iad_calibration_csv(rows, args.output)
    LOGGER.info("IAD 阈值校准完成: %s rows=%s", args.output, len(rows))


def command_run_risk_calibrated_protocol(args: argparse.Namespace) -> None:
    """执行 run-risk-calibrated-protocol 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    relations = read_records(args.relations, limit=args.limit)
    rows = run_risk_calibrated_protocol(
        relations,
        identity_thresholds=_parse_float_list(args.identity_thresholds),
        conflict_thresholds=_parse_float_list(args.conflict_thresholds),
        uncertainty_thresholds=_parse_float_list(args.uncertainty_thresholds),
        version_risk_thresholds=_parse_float_list(args.version_risk_thresholds),
        fpr_budgets=_parse_float_list(args.fpr_budgets),
        fdr_budgets=_parse_float_list(args.fdr_budgets),
        identity_field=args.identity_field,
        conflict_field=args.conflict_field,
        uncertainty_field=args.uncertainty_field,
        version_risk_field=args.version_risk_field,
        system_field=args.system_field,
        system_name=args.system_name,
        eval_split=args.eval_split,
        veto_fields=args.veto_fields,
    )
    write_risk_calibrated_protocol_outputs(rows, args.output_dir)
    LOGGER.info("风险校准选择性实体匹配协议完成: %s rows=%s", args.output_dir, len(rows))


def command_build_hard_negative_stress_set(args: argparse.Namespace) -> None:
    """执行 build-hard-negative-stress-set 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_hard_negative_stress_set_from_paths(
        relation_paths=args.relations,
        limit=args.limit,
        min_title_similarity=args.min_title_similarity,
        min_embedding_similarity=args.min_embedding_similarity,
        min_shared_references=args.min_shared_references,
    )
    write_hard_negative_stress_outputs(rows, args.output_dir)
    LOGGER.info("hard-negative stress set 输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_stress_cluster_contamination_audit(args: argparse.Namespace) -> None:
    """执行 build-stress-cluster-contamination-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    row = build_stress_cluster_contamination_audit_from_paths(
        stress_relations_path=args.stress_relations,
        scored_relations_path=args.scored_relations,
        system_name=args.system_name,
        prediction_field=getattr(args, "prediction_field", None),
        score_field=getattr(args, "score_field", None),
        score_threshold=getattr(args, "score_threshold", None),
        include_version_risk=getattr(args, "include_version_risk", False),
        veto_fields=getattr(args, "veto_fields", None),
        limit=args.limit,
    )
    write_stress_cluster_contamination_outputs([row], args.output_dir)
    LOGGER.info("hard-negative stress cluster contamination 审计完成: %s system=%s", args.output_dir, args.system_name)


def command_train_iad_classifier(args: argparse.Namespace) -> None:
    """执行 train-iad-classifier 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    relations: list[dict] = []
    for relation_path in args.relations:
        remaining_limit = None if args.limit is None else max(0, args.limit - len(relations))
        if remaining_limit == 0:
            break
        relations.extend(read_records(relation_path, limit=remaining_limit))
    output_dir = ensure_directory(args.output_dir)
    targets = [target.strip() for target in args.targets.split(",") if target.strip()]
    summary_rows: list[dict] = []
    for target in targets:
        model = train_iad_relation_model(relations, target=target, random_seed=args.seed)
        model_path = output_dir / f"{target}_model.json"
        write_iad_model_json(model, model_path)
        summary_rows.append(build_training_summary(model, model_path=model_path))
    write_records(summary_rows, output_dir / "training_summary.jsonl")
    LOGGER.info("IAD 轻量分类器训练完成: %s targets=%s", output_dir, len(summary_rows))


def command_train_iad_risk_model(args: argparse.Namespace) -> None:
    """执行 train-iad-risk-model 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    relations: list[dict] = []
    for relation_path in args.relations:
        remaining_limit = None if args.limit is None else max(0, args.limit - len(relations))
        if remaining_limit == 0:
            break
        relations.extend(read_records(relation_path, limit=remaining_limit))
    model = train_iad_risk_model(
        relations,
        random_seed=args.seed,
        work_threshold=args.work_threshold,
        agenda_block_threshold=args.agenda_block_threshold,
        risk_threshold=args.risk_threshold,
        train_split=getattr(args, "train_split", None),
    )
    eval_splits = [
        split_name.strip()
        for split_name in str(getattr(args, "eval_splits", "") or "").split(",")
        if split_name.strip()
    ]
    write_iad_risk_outputs(model, relations, args.output_dir, eval_splits=eval_splits or None)
    LOGGER.info("IAD-Risk 双空间模型输出完成: %s relations=%s trained=%s", args.output_dir, len(relations), model.get("trained"))


def command_train_iad_risk_transformer_model(args: argparse.Namespace) -> None:
    """执行 train-iad-risk-transformer-model 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    document_paths = args.documents if isinstance(args.documents, list) else [args.documents]
    documents: list[dict] = []
    for document_path in document_paths:
        documents.extend(read_records(document_path))
    relations: list[dict] = []
    relation_paths = args.relations if isinstance(args.relations, list) else [args.relations]
    for relation_path in relation_paths:
        remaining_limit = None if args.limit is None else max(0, args.limit - len(relations))
        if remaining_limit == 0:
            break
        relations.extend(read_records(relation_path, limit=remaining_limit))
    extra_train_relations: list[dict] = []
    for relation_path in getattr(args, "extra_train_relations", []) or []:
        extra_train_relations.extend(read_records(relation_path))
    model, augmented_relations = train_iad_risk_transformer_model(
        documents=documents,
        relations=relations,
        extra_train_relations=extra_train_relations,
        system_name=args.system_name,
        embedding_model=args.embedding_model,
        adapter_model=args.adapter_model,
        model_backend=args.model_backend,
        batch_size=args.batch_size,
        pooling_strategy=args.pooling_strategy,
        train_split=args.train_split,
        random_seed=args.seed,
        work_threshold=args.work_threshold,
        agenda_block_threshold=args.agenda_block_threshold,
        risk_threshold=args.risk_threshold,
    )
    write_iad_risk_transformer_outputs(model, augmented_relations, args.output_dir)
    LOGGER.info(
        "IAD-Risk Transformer 模型输出完成: %s relations=%s trained=%s",
        args.output_dir,
        len(augmented_relations),
        model.get("trained"),
    )


def command_evaluate_external_baseline(args: argparse.Namespace) -> None:
    """执行 evaluate-external-baseline 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    relations = read_records(args.relations, limit=args.limit)
    scores = read_external_baseline_scores(args.baseline, score_field=args.score_field)
    attached_relations = attach_external_baseline_scores(relations, scores, output_score_field=args.output_score_field)
    summary_rows = evaluate_external_baseline(
        attached_relations,
        system_name=args.system_name,
        score_field=args.output_score_field,
        thresholds=_parse_float_list(args.thresholds) or [0.5],
        metric_target=args.metric_target,
        baseline_family=args.baseline_family,
        execution_mode=args.execution_mode,
        split_field=args.split_field,
        eval_splits=_parse_str_list(args.eval_splits),
    )
    write_records(attached_relations, args.output)
    write_records(summary_rows, args.summary_output)
    LOGGER.info("外部 baseline 评估完成: output=%s summary=%s", args.output, args.summary_output)


def command_run_representation_baseline(args: argparse.Namespace) -> None:
    """执行 run-representation-baseline 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    documents = read_records(args.documents, limit=args.limit)
    pairs = read_records(args.pairs)
    rows, summary = run_representation_baseline(
        documents=documents,
        pairs=pairs,
        system_name=args.system_name,
        embedding_model=args.embedding_model,
        score_field=args.score_field,
        batch_size=args.batch_size,
        model_backend=args.model_backend,
        pooling_strategy=args.pooling_strategy,
        adapter_model=args.adapter_model,
    )
    write_baseline_scores(rows, summary, args.output, args.summary_output)
    LOGGER.info("表示模型 baseline 输出完成: output=%s summary=%s rows=%s", args.output, args.summary_output, len(rows))


def command_run_entity_matching_baseline(args: argparse.Namespace) -> None:
    """执行 run-entity-matching-baseline 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    documents = read_records(args.documents, limit=args.limit)
    pairs = read_records(args.pairs)
    rows, summary = run_entity_matching_baseline(
        documents=documents,
        pairs=pairs,
        system_name=args.system_name,
        model_name=args.model_name,
        score_field=args.score_field,
        model_backend=args.model_backend,
        batch_size=args.batch_size,
    )
    write_entity_matching_scores(rows, summary, args.output, args.summary_output)
    LOGGER.info("实体匹配 baseline 输出完成: output=%s summary=%s rows=%s", args.output, args.summary_output, len(rows))


def command_train_entity_matching_baseline(args: argparse.Namespace) -> None:
    """执行 train-entity-matching-baseline 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    documents = read_records(args.documents, limit=args.limit)
    pairs = read_records(args.pairs)
    summary = train_entity_matching_baseline(
        documents=documents,
        pairs=pairs,
        output_dir=args.output_dir,
        system_name=args.system_name,
        base_model_name=args.base_model_name,
        train_split=args.train_split,
        split_field=args.split_field,
        label_field=args.label_field,
        batch_size=args.batch_size,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        max_length=args.max_length,
        seed=args.seed,
    )
    write_entity_matching_training_summary(summary, args.summary_output)
    LOGGER.info("实体匹配 checkpoint 训练输出完成: output_dir=%s summary=%s", args.output_dir, args.summary_output)


def command_run_llm_judge_baseline(args: argparse.Namespace) -> None:
    """执行 run-llm-judge-baseline 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    import os

    documents = read_records(args.documents, limit=args.limit)
    pairs = read_records(args.pairs)
    api_key = os.environ.get(args.api_key_env) if args.api_key_env else None
    rows, summary = run_llm_judge_baseline(
        documents=documents,
        pairs=pairs,
        system_name=args.system_name,
        model_name=args.model_name,
        score_field=args.score_field,
        api_backend=args.api_backend,
        api_key=api_key,
        timeout_seconds=args.timeout_seconds,
        max_new_tokens=getattr(args, "max_new_tokens", 80),
        batch_size=getattr(args, "batch_size", 4),
    )
    write_llm_judge_scores(rows, summary, args.output, args.summary_output)
    LOGGER.info("LLM judge baseline 输出完成: output=%s summary=%s rows=%s", args.output, args.summary_output, len(rows))


def command_build_baseline_error_analysis(args: argparse.Namespace) -> None:
    """执行 build-baseline-error-analysis 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    relations = read_records(args.relations, limit=args.limit)
    summary_rows, case_rows = build_baseline_error_analysis(
        relations=relations,
        system_name=args.system_name,
        score_field=args.score_field,
        thresholds=_parse_float_list(args.thresholds) or [0.5],
        baseline_family=args.baseline_family,
        execution_mode=args.execution_mode,
    )
    write_baseline_error_analysis_outputs(summary_rows, case_rows, args.output_dir)
    LOGGER.info("baseline 错误分析输出完成: output_dir=%s rows=%s cases=%s", args.output_dir, len(summary_rows), len(case_rows))


def command_run_single_space_union_baseline(args: argparse.Namespace) -> None:
    """执行 run-single-space-union-baseline 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    relations = read_records(args.relations, limit=args.limit)
    predictions, summary = run_single_space_union_baseline(
        relations=relations,
        system_name=args.system_name,
        score_field=args.score_field,
        threshold=args.threshold,
        baseline_family=args.baseline_family,
        execution_mode=args.execution_mode,
    )
    write_single_space_union_outputs(predictions, summary, args.output_dir)
    LOGGER.info("single-space union baseline 输出完成: output_dir=%s rows=%s", args.output_dir, len(predictions))


def command_build_iad_paper_report(args: argparse.Namespace) -> None:
    """执行 build-iad-paper-report 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_iad_paper_report(
        output_dir=args.output_dir,
        gold_summaries=args.gold_summaries,
        proxy_summaries=args.proxy_summaries,
        weak_summaries=args.weak_summaries,
        external_summaries=args.external_summaries,
        classifier_summaries=args.classifier_summaries,
        ablation_summaries=args.ablation_summaries,
        iad_bench_summaries=getattr(args, "iad_bench_summaries", []),
        iad_risk_summaries=getattr(args, "iad_risk_summaries", []),
        bootstrap_summaries=getattr(args, "bootstrap_summaries", []),
        openalex_ingestion_summaries=getattr(args, "openalex_ingestion_summaries", []),
        openalex_dataset_summaries=getattr(args, "openalex_dataset_summaries", []),
        human_audit_plans=getattr(args, "human_audit_plans", []),
    )
    LOGGER.info("IAD 论文级报告完成: %s rows=%s", args.output_dir, len(rows))


def command_build_iad_bench(args: argparse.Namespace) -> None:
    """执行 build-iad-bench 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    summary = build_iad_bench(
        source_dirs=args.source_dirs,
        output_dir=args.output_dir,
        seed=args.seed,
        train_ratio=args.train_ratio,
        dev_ratio=args.dev_ratio,
    )
    LOGGER.info("IAD-Bench 输出完成: %s pairs=%s", args.output_dir, summary["pair_count"])


def command_build_iad_bench_balanced_subset(args: argparse.Namespace) -> None:
    """执行 build-iad-bench-balanced-subset 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    documents, pairs, summary = build_iad_bench_balanced_subset_from_paths(
        documents_path=args.documents,
        pairs_path=args.pairs,
        relation_labels=args.relation_labels,
        include_label_sources=getattr(args, "include_label_sources", None),
        exclude_label_sources=getattr(args, "exclude_label_sources", None),
        seed=args.seed,
        train_ratio=args.train_ratio,
        dev_ratio=args.dev_ratio,
    )
    write_iad_bench_balanced_subset_outputs(documents, pairs, summary, args.output_dir)
    LOGGER.info("IAD-Bench 平衡子集输出完成: %s pairs=%s", args.output_dir, summary["pair_count"])


def command_build_iad_bench_stratification_audit(args: argparse.Namespace) -> None:
    """执行 build-iad-bench-stratification-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    audit_rows, distribution_rows = build_iad_bench_stratification_audit_rows_from_paths(
        pairs_path=args.pairs,
        max_top_strength_ratio=args.max_top_strength_ratio,
        min_sources_per_relation=args.min_sources_per_relation,
    )
    write_iad_bench_stratification_audit_outputs(audit_rows, distribution_rows, args.output_dir)
    LOGGER.info("IAD-Bench 分层分布审计输出完成: %s audit_rows=%s distribution_rows=%s", args.output_dir, len(audit_rows), len(distribution_rows))


def command_build_iad_bench_source_bias_diagnostic(args: argparse.Namespace) -> None:
    """执行 build-iad-bench-source-bias-diagnostic 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    eval_splits = [split.strip() for split in str(args.eval_splits or "").split(",") if split.strip()]
    diagnostic_rows, prediction_rows = build_iad_bench_source_bias_diagnostic_rows_from_paths(
        pairs_path=args.pairs,
        train_split=args.train_split,
        eval_splits=eval_splits,
        max_shortcut_accuracy=args.max_shortcut_accuracy,
    )
    write_iad_bench_source_bias_diagnostic_outputs(diagnostic_rows, prediction_rows, args.output_dir)
    LOGGER.info("IAD-Bench 来源偏置诊断输出完成: %s diagnostics=%s predictions=%s", args.output_dir, len(diagnostic_rows), len(prediction_rows))


def command_build_iad_bench_provenance_balance_plan(args: argparse.Namespace) -> None:
    """执行 build-iad-bench-provenance-balance-plan 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_iad_bench_provenance_balance_plan_rows_from_paths(
        pairs_path=args.pairs,
        min_sources_per_relation=args.min_sources_per_relation,
        max_dominant_source_ratio=args.max_dominant_source_ratio,
        target_pairs_per_new_source=args.target_pairs_per_new_source,
    )
    write_iad_bench_provenance_balance_plan_outputs(rows, args.output_dir)
    LOGGER.info("IAD-Bench provenance 平衡计划输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_iad_bench_source_candidate_registry(args: argparse.Namespace) -> None:
    """执行 build-iad-bench-source-candidate-registry 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_iad_bench_source_candidate_registry_rows_from_paths(
        provenance_balance_plan_path=args.provenance_balance_plan,
        public_gold_source_ids=args.public_gold_source_ids,
        openalex_topic_seed_ids=args.openalex_topic_seed_ids,
    )
    write_iad_bench_source_candidate_registry_outputs(rows, args.output_dir)
    LOGGER.info("IAD-Bench 公开来源候选 registry 输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_iad_bench_source_acquisition_audit(args: argparse.Namespace) -> None:
    """执行 build-iad-bench-source-acquisition-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_iad_bench_source_acquisition_audit_rows_from_paths(
        registry_path=args.registry,
        workspace_dir=args.workspace_dir,
    )
    write_iad_bench_source_acquisition_audit_outputs(rows, args.output_dir)
    LOGGER.info("IAD-Bench 公开来源获取审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_iad_model_feature_guard(args: argparse.Namespace) -> None:
    """执行 build-iad-model-feature-guard 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    audit_rows, violation_rows = build_iad_model_feature_guard_rows_from_paths(
        model_paths=args.model_paths,
        denied_fields=args.denied_fields,
    )
    write_iad_model_feature_guard_outputs(audit_rows, violation_rows, args.output_dir)
    LOGGER.info("IAD 模型特征泄漏审计输出完成: %s audits=%s violations=%s", args.output_dir, len(audit_rows), len(violation_rows))


def command_run_iad_ablation_suite(args: argparse.Namespace) -> None:
    """执行 run-iad-ablation-suite 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    relations: list[dict] = []
    relation_paths = args.relations if isinstance(args.relations, list) else [args.relations]
    for relation_path in relation_paths:
        remaining_limit = None if args.limit is None else max(0, args.limit - len(relations))
        if remaining_limit == 0:
            break
        relations.extend(read_records(relation_path, limit=remaining_limit))
    rows = run_iad_ablation_suite(
        relations,
        identity_threshold=args.identity_threshold,
        agenda_block_threshold=args.agenda_block_threshold,
        false_merge_risk_threshold=args.false_merge_risk_threshold,
        agenda_threshold=args.agenda_threshold,
        dense_threshold=args.dense_threshold,
    )
    write_iad_ablation_outputs(rows, args.output_dir)
    LOGGER.info("IAD 消融套件输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_reviewer_audit(args: argparse.Namespace) -> None:
    """执行 build-reviewer-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_reviewer_audit_rows(args.rq_summaries)
    write_reviewer_audit_outputs(rows, args.output_dir)
    LOGGER.info("审稿回应矩阵输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_journal_readiness(args: argparse.Namespace) -> None:
    """执行 build-journal-readiness 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_journal_readiness_rows(args.rq_summaries, args.reviewer_audits)
    write_journal_readiness_outputs(rows, args.output_dir)
    LOGGER.info("期刊 readiness 报告输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_experiment_queue(args: argparse.Namespace) -> None:
    """执行 build-experiment-queue 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_experiment_queue_rows(args.readiness_reports)
    write_experiment_queue_outputs(rows, args.output_dir)
    LOGGER.info("实验队列输出完成: %s rows=%s", args.output_dir, len(rows))


def command_check_experiment_queue(args: argparse.Namespace) -> None:
    """执行 check-experiment-queue 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_experiment_preflight_rows_from_paths(
        queue_paths=[args.queue],
        workspace_dir=args.workspace_dir,
        remote_available=args.remote_available,
    )
    write_experiment_preflight_outputs(rows, args.output_dir)
    LOGGER.info("实验队列 preflight 输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_experiment_dependency(args: argparse.Namespace) -> None:
    """执行 build-experiment-dependency 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_experiment_dependency_rows_from_paths(args.queue, args.preflight)
    write_experiment_dependency_outputs(rows, args.output_dir)
    LOGGER.info("实验依赖图输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_experiment_execution_pack(args: argparse.Namespace) -> None:
    """执行 build-experiment-execution-pack 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_experiment_execution_rows_from_paths(args.queue, args.preflight, args.dependency)
    write_experiment_execution_pack_outputs(rows, args.output_dir)
    LOGGER.info("实验执行交接包输出完成: %s rows=%s", args.output_dir, len(rows))


def command_validate_remote_outputs(args: argparse.Namespace) -> None:
    """执行 validate-remote-outputs 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_remote_output_validation_rows_from_path(
        manifest_path=args.manifest,
        workspace_dir=args.workspace_dir,
    )
    write_remote_output_validation_outputs(rows, args.output_dir)
    LOGGER.info("远程输出验收报告输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_remote_environment_audit(args: argparse.Namespace) -> None:
    """执行 build-remote-environment-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_remote_environment_audit_rows(
        required_modules=args.required_modules,
        required_env_vars=args.required_env_vars,
    )
    write_remote_environment_audit_outputs(rows, args.output_dir)
    LOGGER.info("远程环境依赖审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_remote_execution_blueprint(args: argparse.Namespace) -> None:
    """执行 build-remote-execution-blueprint 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_remote_execution_blueprint_rows_from_paths(
        execution_plan_path=args.execution_plan,
        environment_audit_path=args.environment_audit,
        remote_output_validation_path=args.remote_output_validation,
    )
    write_remote_execution_blueprint_outputs(rows, args.output_dir)
    LOGGER.info("远程执行蓝图输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_remote_connection_pack(args: argparse.Namespace) -> None:
    """执行 build-remote-connection-pack 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_remote_connection_pack_rows_from_paths(
        execution_plan_path=args.execution_plan,
        remote_blueprint_path=args.remote_blueprint,
        profile_path=args.profile,
    )
    write_remote_connection_pack_outputs(rows, args.output_dir)
    LOGGER.info("远程连接准备包输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_remote_connection_profile(args: argparse.Namespace) -> None:
    """执行 build-remote-connection-profile 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    profile = build_remote_connection_profile(
        remote_host=args.remote_host,
        remote_port=args.remote_port,
        remote_user=args.remote_user,
        ssh_key_path=args.ssh_key_path,
        remote_workspace=args.remote_workspace,
        conda_env=args.conda_env,
        remote_conda_path=args.remote_conda_path,
        configured_secrets=args.configured_secrets,
        provided_model_artifacts=args.provided_model_artifacts,
        environment=os.environ,
    )
    write_remote_connection_profile(profile, args.output_path)
    LOGGER.info("远程连接 profile 输出完成: %s", args.output_path)


def command_build_remote_input_request(args: argparse.Namespace) -> None:
    """执行 build-remote-input-request 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_remote_input_request_rows_from_paths(
        remote_connection_pack_path=args.remote_connection_pack,
        q2b_roadmap_path=args.q2b_roadmap,
        reviewer_iteration_path=args.reviewer_iteration,
    )
    write_remote_input_request_outputs(rows, args.output_dir)
    LOGGER.info("远程输入请求包输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_remote_execution_slice(args: argparse.Namespace) -> None:
    """执行 build-remote-execution-slice 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_remote_execution_slice_rows_from_paths(
        q2b_action_board_path=args.q2b_action_board,
        remote_connection_pack_path=args.remote_connection_pack,
        remote_input_request_path=args.remote_input_request,
        remote_execution_blueprint_path=args.remote_execution_blueprint,
    )
    write_remote_execution_slice_outputs(rows, args.output_dir)
    LOGGER.info("远程执行切片输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_remote_slice_run_pack(args: argparse.Namespace) -> None:
    """执行 build-remote-slice-run-pack 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_remote_slice_run_pack_rows_from_paths(
        remote_execution_slice_path=args.remote_execution_slice,
        execution_plan_path=args.execution_plan,
    )
    write_remote_slice_run_pack_outputs(rows, args.output_dir)
    LOGGER.info("远程切片运行包输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_primary_remote_readiness(args: argparse.Namespace) -> None:
    """执行 build-primary-remote-readiness 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_primary_remote_readiness_rows_from_paths(
        remote_input_request_path=args.remote_input_request,
        remote_execution_slice_path=args.remote_execution_slice,
        remote_slice_run_pack_path=args.remote_slice_run_pack,
    )
    write_primary_remote_readiness_outputs(rows, args.output_dir)
    LOGGER.info("主轨道远程就绪审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_primary_remote_handoff(args: argparse.Namespace) -> None:
    """执行 build-primary-remote-handoff 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_primary_remote_handoff_rows_from_paths(
        primary_remote_readiness_path=args.primary_remote_readiness,
    )
    write_primary_remote_handoff_outputs(rows, args.output_dir)
    LOGGER.info("主轨道远程交接包输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_primary_track_claim_gate(args: argparse.Namespace) -> None:
    """执行 build-primary-track-claim-gate 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_primary_track_claim_gate_rows_from_paths(
        primary_remote_handoff_path=args.primary_remote_handoff,
        advanced_track_summary_path=args.advanced_track_summary,
        model_superiority_summary_path=args.model_superiority_summary,
        innovation_depth_summary_path=args.innovation_depth_summary,
        q2b_acceptance_summary_path=args.q2b_acceptance_summary,
    )
    write_primary_track_claim_gate_outputs(rows, args.output_dir)
    LOGGER.info("主轨道论文主张门禁输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_primary_track_superiority_protocol(args: argparse.Namespace) -> None:
    """执行 build-primary-track-superiority-protocol 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_primary_track_superiority_protocol_rows_from_paths(
        primary_track_claim_gate_path=args.primary_track_claim_gate,
        advanced_track_summary_path=args.advanced_track_summary,
        model_superiority_summary_path=args.model_superiority_summary,
    )
    write_primary_track_superiority_protocol_outputs(rows, args.output_dir)
    LOGGER.info("主轨道优势判定协议输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_primary_track_superiority_evaluator(args: argparse.Namespace) -> None:
    """执行 build-primary-track-superiority-evaluator 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_primary_track_superiority_evaluator_rows_from_paths(
        primary_track_superiority_protocol_path=args.primary_track_superiority_protocol,
        metric_summary_paths=args.metric_summaries,
        bootstrap_summary_paths=args.bootstrap_summaries,
    )
    write_primary_track_superiority_evaluator_outputs(rows, args.output_dir)
    LOGGER.info("主轨道实际优势判定输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_no_annotation_protocol(args: argparse.Namespace) -> None:
    """执行 build-no-annotation-protocol 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_no_annotation_protocol_rows_from_paths(
        public_data_validity_paths=args.public_data_validity,
        q2b_roadmap_path=args.q2b_roadmap,
        reviewer_iteration_path=args.reviewer_iteration,
        remote_input_request_path=args.remote_input_request,
    )
    write_no_annotation_protocol_outputs(rows, args.output_dir)
    LOGGER.info("无人工标注阶段协议输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_remote_result_acceptance(args: argparse.Namespace) -> None:
    """执行 build-remote-result-acceptance 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_remote_result_acceptance_rows_from_paths(
        execution_plan_path=args.execution_plan,
        remote_output_validation_path=args.remote_output_validation,
    )
    write_remote_result_acceptance_outputs(rows, args.output_dir)
    LOGGER.info("远程结果接收审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_q2b_action_board(args: argparse.Namespace) -> None:
    """执行 build-q2b-action-board 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_q2b_action_board_rows_from_paths(
        submission_gates_path=args.submission_gates,
        remote_blueprint_path=args.remote_blueprint,
        journal_upgrade_plan_path=args.journal_upgrade_plan,
        advanced_model_evidence_path=args.advanced_model_evidence,
        remote_connection_pack_path=args.remote_connection_pack,
    )
    write_q2b_action_board_outputs(rows, args.output_dir)
    LOGGER.info("二区/B类行动板输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_q2b_completion_audit(args: argparse.Namespace) -> None:
    """执行 build-q2b-completion-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_q2b_completion_audit_rows_from_paths(
        submission_summary_paths=args.submission_summaries,
        q2b_summary_paths=args.q2b_summaries,
        reviewer_response_summary_paths=args.reviewer_response_summaries,
        remote_connection_summary_paths=args.remote_connection_summaries,
        remote_result_acceptance_summary_paths=args.remote_result_acceptance_summaries,
        innovation_depth_summary_paths=args.innovation_depth_summaries,
        advanced_model_summary_paths=args.advanced_model_summaries,
        split_readiness_summary_paths=args.split_readiness_summaries,
        split_readiness_audit_paths=args.split_readiness_audits,
        training_input_summary_paths=args.training_input_summaries,
        source_heldout_coverage_summary_paths=getattr(args, "source_heldout_coverage_summaries", []),
        split_evaluation_summary_paths=args.split_evaluation_summaries,
    )
    write_q2b_completion_audit_outputs(rows, args.output_dir)
    LOGGER.info("二区/B类最终目标完成度审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_q2b_external_blocker_audit(args: argparse.Namespace) -> None:
    """执行 build-q2b-external-blocker-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_q2b_external_blocker_rows_from_paths(
        completion_audit_path=args.completion_audit,
        action_board_path=args.action_board,
        remote_result_acceptance_path=args.remote_result_acceptance,
        advanced_model_evidence_path=args.advanced_model_evidence,
    )
    write_q2b_external_blocker_outputs(rows, args.output_dir)
    LOGGER.info("Q2/B 外部阻塞合同审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_q2b_acceptance_rubric(args: argparse.Namespace) -> None:
    """执行 build-q2b-acceptance-rubric 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_q2b_acceptance_rubric_rows_from_paths(
        remote_output_summary_path=args.remote_output_summary,
        remote_result_acceptance_summary_path=args.remote_result_acceptance_summary,
        advanced_model_summary_path=args.advanced_model_summary,
        model_superiority_summary_path=args.model_superiority_summary,
        innovation_depth_summary_path=args.innovation_depth_summary,
        no_annotation_summary_path=args.no_annotation_summary,
        novelty_summary_path=args.novelty_summary,
        prior_art_summary_path=args.prior_art_summary,
        q2b_completion_summary_path=args.q2b_completion_summary,
        reviewer_iteration_summary_path=args.reviewer_iteration_summary,
    )
    write_q2b_acceptance_rubric_outputs(rows, args.output_dir)
    LOGGER.info("Q2/B 接收判定 rubric 输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_q2b_experiment_optimizer(args: argparse.Namespace) -> None:
    """执行 build-q2b-experiment-optimizer 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_q2b_experiment_optimizer_rows_from_paths(
        q2b_acceptance_rubric_path=args.q2b_acceptance_rubric,
        reviewer_iteration_path=args.reviewer_iteration,
        remote_input_request_path=args.remote_input_request,
        remote_execution_slice_path=args.remote_execution_slice,
        advanced_track_summary_path=args.advanced_track_summary,
    )
    write_q2b_experiment_optimizer_outputs(rows, args.output_dir)
    LOGGER.info("Q2/B 实验优化器输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_reviewer_threat_model(args: argparse.Namespace) -> None:
    """执行 build-reviewer-threat-model 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_reviewer_threat_model_rows_from_paths(
        q2b_acceptance_path=args.q2b_acceptance_rubric,
        q2b_experiment_optimizer_path=args.q2b_experiment_optimizer,
        model_innovation_blueprint_paths=args.model_innovation_blueprints,
        innovation_depth_paths=args.innovation_depth_audits,
        novelty_matrix_paths=args.novelty_matrices,
        prior_art_paths=args.prior_art_audits,
        reviewer_iteration_paths=args.reviewer_iterations,
    )
    write_reviewer_threat_model_outputs(rows, args.output_dir)
    LOGGER.info("审稿威胁模型输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_novelty_falsification_matrix(args: argparse.Namespace) -> None:
    """执行 build-novelty-falsification-matrix 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_novelty_falsification_rows_from_paths(
        model_innovation_blueprint_paths=args.model_innovation_blueprints,
        innovation_depth_paths=args.innovation_depth_audits,
        model_superiority_summary_path=args.model_superiority_summary,
        no_annotation_summary_path=args.no_annotation_summary,
    )
    write_novelty_falsification_outputs(rows, args.output_dir)
    LOGGER.info("创新可证伪矩阵输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_prior_art_novelty_audit(args: argparse.Namespace) -> None:
    """执行 build-prior-art-novelty-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_prior_art_novelty_rows_from_paths(
        novelty_matrix_paths=args.novelty_matrices,
        advanced_model_summary_path=args.advanced_model_summary,
        snapshot_date=args.snapshot_date,
    )
    write_prior_art_novelty_outputs(rows, args.output_dir)
    LOGGER.info("相关工作新颖性审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_q2b_upgrade_roadmap(args: argparse.Namespace) -> None:
    """执行 build-q2b-upgrade-roadmap 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_q2b_upgrade_roadmap_rows_from_paths(
        completion_audit_path=args.completion_audit,
        action_board_path=args.action_board,
        remote_acceptance_path=args.remote_acceptance,
        remote_output_summary_path=args.remote_output_summary,
        model_superiority_path=args.model_superiority_audit,
    )
    write_q2b_upgrade_roadmap_outputs(rows, args.output_dir)
    LOGGER.info("Q2/B 升级路线图输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_reviewer_response_matrix(args: argparse.Namespace) -> None:
    """执行 build-reviewer-response-matrix 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_reviewer_response_rows_from_paths(
        reviewer_audit_paths=args.reviewer_audits,
        research_depth_audit_paths=args.research_depth_audits,
        manuscript_evidence_paths=args.manuscript_evidence,
        submission_gate_audit_paths=args.submission_gate_audits,
        prior_art_audit_paths=args.prior_art_audits,
    )
    write_reviewer_response_outputs(rows, args.output_dir)
    LOGGER.info("审稿回应矩阵输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_reviewer_iteration_audit(args: argparse.Namespace) -> None:
    """执行 build-reviewer-iteration-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_reviewer_iteration_audit_rows_from_paths(
        roadmap_path=args.q2b_roadmap,
        completion_audit_path=args.q2b_completion_audit,
        model_superiority_path=args.model_superiority_audit,
        innovation_depth_path=args.innovation_depth,
        public_data_path=args.public_data_validity,
        feature_guard_path=args.feature_guard,
        reviewer_response_path=args.reviewer_response,
    )
    write_reviewer_iteration_audit_outputs(rows, args.output_dir)
    LOGGER.info("审稿人迭代审核输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_paper_claim_audit(args: argparse.Namespace) -> None:
    """执行 build-paper-claim-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_paper_claim_audit_rows_from_paths(
        rq_summary_paths=args.rq_summaries,
        readiness_report_paths=args.readiness_reports,
        dependency_report_paths=args.dependency_reports,
    )
    write_paper_claim_audit_outputs(rows, args.output_dir)
    LOGGER.info("论文主张审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_research_depth_audit(args: argparse.Namespace) -> None:
    """执行 build-research-depth-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_research_depth_audit_rows_from_paths(
        reviewer_audit_paths=args.reviewer_audits,
        claim_audit_paths=args.claim_audits,
        readiness_report_paths=args.readiness_reports,
        dependency_report_paths=args.dependency_reports,
    )
    write_research_depth_audit_outputs(rows, args.output_dir)
    LOGGER.info("研究深度审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_submission_gate_audit(args: argparse.Namespace) -> None:
    """执行 build-submission-gate-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_submission_gate_audit_rows_from_paths(
        readiness_report_paths=args.readiness_reports,
        claim_audit_paths=args.claim_audits,
        research_depth_audit_paths=args.research_depth_audits,
        remote_output_summary_paths=args.remote_output_summaries,
        remote_result_acceptance_summary_paths=args.remote_result_acceptance_summaries,
        remote_connection_summary_paths=args.remote_connection_summaries,
        source_bias_summary_paths=args.source_bias_summaries,
        feature_guard_summary_paths=args.feature_guard_summaries,
        provenance_balance_summary_paths=args.provenance_balance_summaries,
        training_input_summary_paths=args.training_input_summaries,
    )
    write_submission_gate_audit_outputs(rows, args.output_dir)
    LOGGER.info("投稿门禁审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_manuscript_evidence_matrix(args: argparse.Namespace) -> None:
    """执行 build-manuscript-evidence-matrix 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_manuscript_evidence_rows_from_paths(
        claim_audit_paths=args.claim_audits,
        research_depth_audit_paths=args.research_depth_audits,
        submission_gate_audit_paths=args.submission_gate_audits,
    )
    write_manuscript_evidence_outputs(rows, args.output_dir)
    LOGGER.info("稿件证据矩阵输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_manuscript_draft_skeleton(args: argparse.Namespace) -> None:
    """执行 build-manuscript-draft-skeleton 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_manuscript_draft_rows_from_paths(
        manuscript_evidence_paths=args.manuscript_evidence,
        submission_summary_paths=args.submission_summaries,
    )
    write_manuscript_draft_outputs(rows, args.output_dir)
    LOGGER.info("安全论文草稿骨架输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_journal_upgrade_plan(args: argparse.Namespace) -> None:
    """执行 build-journal-upgrade-plan 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_journal_upgrade_plan_rows_from_paths(
        submission_summary_paths=args.submission_summaries,
        research_depth_audit_paths=args.research_depth_audits,
        remote_output_summary_paths=args.remote_output_summaries,
        manuscript_draft_summary_paths=args.manuscript_draft_summaries,
        human_annotation_policy=args.human_annotation_policy,
    )
    write_journal_upgrade_plan_outputs(rows, args.output_dir)
    LOGGER.info("期刊升级优化计划输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_advanced_model_evidence(args: argparse.Namespace) -> None:
    """执行 build-advanced-model-evidence 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_advanced_model_evidence_rows_from_paths(
        baseline_metric_summary_paths=args.baseline_metric_summaries,
        execution_summary_paths=args.execution_summaries,
        transformer_summary_paths=args.transformer_summaries,
        bootstrap_summary_paths=args.bootstrap_summaries,
        remote_output_summary_paths=args.remote_output_summaries,
        required_systems=args.required_systems,
    )
    write_advanced_model_evidence_outputs(rows, args.output_dir)
    LOGGER.info("高级模型证据矩阵输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_model_innovation_blueprint(args: argparse.Namespace) -> None:
    """执行 build-model-innovation-blueprint 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_model_innovation_blueprint_rows_from_paths(
        advanced_model_evidence_paths=args.advanced_model_evidence,
        q2b_completion_audit_paths=args.q2b_completion_audits,
        split_readiness_paths=args.split_readiness_audits,
    )
    write_model_innovation_blueprint_outputs(rows, args.output_dir)
    LOGGER.info("模型创新实验蓝图输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_model_superiority_audit(args: argparse.Namespace) -> None:
    """执行 build-model-superiority-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_model_superiority_audit_rows_from_paths(
        advanced_model_evidence_paths=args.advanced_model_evidence,
        model_innovation_blueprint_paths=args.model_innovation_blueprints,
        risk_protocol_paths=getattr(args, "risk_protocols", []),
        main_system=args.main_system,
    )
    write_model_superiority_audit_outputs(rows, args.output_dir)
    LOGGER.info("模型优势审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_innovation_depth_stress_test(args: argparse.Namespace) -> None:
    """执行 build-innovation-depth-stress-test 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_innovation_depth_stress_rows_from_paths(
        model_innovation_blueprint_paths=args.model_innovation_blueprints,
        model_superiority_audit_paths=args.model_superiority_audits,
        mechanism_evidence_paths=args.mechanism_evidence,
        mechanism_sensitivity_paths=args.mechanism_sensitivity,
        mechanism_triangulation_summary_paths=args.mechanism_triangulation_summaries,
        mechanism_triangulation_sensitivity_summary_paths=args.mechanism_triangulation_sensitivity_summaries,
        split_readiness_audit_paths=getattr(args, "split_readiness_audits", []),
    )
    write_innovation_depth_stress_outputs(rows, args.output_dir)
    LOGGER.info("创新深度压力审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_mechanism_error_evidence(args: argparse.Namespace) -> None:
    """执行 build-mechanism-error-evidence 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    evidence_rows, case_rows, stratum_rows = build_mechanism_error_evidence_rows_from_paths(
        baseline_path=args.baseline,
        iad_predictions_path=args.iad_predictions,
        system_name=args.system_name,
        score_field=args.score_field,
        threshold=args.threshold,
        max_cases=args.max_cases,
    )
    sweep_thresholds = _parse_float_list(getattr(args, "sweep_thresholds", None))
    sensitivity_rows = None
    if sweep_thresholds:
        sensitivity_rows = build_mechanism_threshold_sensitivity_rows(
            baseline_rows=read_records(args.baseline),
            iad_rows=read_records(args.iad_predictions),
            system_name=args.system_name,
            score_field=args.score_field,
            thresholds=sweep_thresholds,
        )
    write_mechanism_error_evidence_outputs(evidence_rows, case_rows, stratum_rows, args.output_dir, sensitivity_rows=sensitivity_rows)
    LOGGER.info(
        "机制性错误证据输出完成: %s rows=%s cases=%s strata=%s sensitivity=%s",
        args.output_dir,
        len(evidence_rows),
        len(case_rows),
        len(stratum_rows),
        len(sensitivity_rows or []),
    )


def command_build_mechanism_triangulation_audit(args: argparse.Namespace) -> None:
    """执行 build-mechanism-triangulation-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    audit_rows, system_rows = build_mechanism_triangulation_rows_from_paths(
        iad_predictions_path=args.iad_predictions,
        baseline_spec_values=args.baseline_specs,
    )
    write_mechanism_triangulation_outputs(audit_rows, system_rows, args.output_dir)
    LOGGER.info("机制三角验证审计输出完成: %s pairs=%s systems=%s", args.output_dir, len(audit_rows), len(system_rows))


def command_build_mechanism_triangulation_sensitivity(args: argparse.Namespace) -> None:
    """执行 build-mechanism-triangulation-sensitivity 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_mechanism_triangulation_sensitivity_rows_from_paths(
        iad_predictions_path=args.iad_predictions,
        baseline_spec_values=args.baseline_specs,
    )
    write_mechanism_triangulation_sensitivity_outputs(rows, args.output_dir)
    LOGGER.info("机制三角验证阈值敏感性输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_iad_risk_split_evaluation_audit(args: argparse.Namespace) -> None:
    """执行 build-iad-risk-split-evaluation-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_iad_risk_split_evaluation_audit_rows_from_paths(
        summary_path=args.iad_risk_summary,
        model_path=args.iad_risk_model,
    )
    write_iad_risk_split_evaluation_audit_outputs(rows, args.output_dir)
    LOGGER.info("IAD-Risk split 评估审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_iad_source_heldout_coverage_audit(args: argparse.Namespace) -> None:
    """执行 build-iad-source-heldout-coverage-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_iad_source_heldout_coverage_rows_from_paths(
        pairs_path=args.pairs,
        relation_labels=args.relation_labels,
        min_train_pairs=args.min_train_pairs,
        min_test_pairs=args.min_test_pairs,
    )
    write_iad_source_heldout_coverage_outputs(rows, args.output_dir)
    LOGGER.info("IAD source-held-out 覆盖审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_iad_source_heldout_gap_plan(args: argparse.Namespace) -> None:
    """执行 build-iad-source-heldout-gap-plan 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_iad_source_heldout_gap_plan_rows_from_paths(
        coverage_audit_path=args.coverage_audit,
        candidate_registry_path=args.candidate_registry,
    )
    write_iad_source_heldout_gap_plan_outputs(rows, args.output_dir)
    LOGGER.info("IAD source-held-out 缺口补齐计划输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_iad_training_input_audit(args: argparse.Namespace) -> None:
    """执行 build-iad-training-input-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_iad_training_input_audit_rows_from_paths(relations_path=args.relations)
    write_iad_training_input_audit_outputs(rows, args.output_dir)
    LOGGER.info("IAD-Risk 训练输入审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_iad_training_blend(args: argparse.Namespace) -> None:
    """执行 build-iad-training-blend 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows, summary = build_iad_training_blend_from_paths(
        relation_paths=args.relations,
        relation_labels=args.relation_labels,
        max_per_relation=args.max_per_relation,
        seed=args.seed,
        train_ratio=args.train_ratio,
        dev_ratio=args.dev_ratio,
    )
    write_iad_training_blend_outputs(rows, summary, args.output_dir)
    LOGGER.info("IAD-Risk 训练混合输入输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_mechanism_case_pack(args: argparse.Namespace) -> None:
    """执行 build-mechanism-case-pack 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_mechanism_case_pack_rows_from_paths(
        triangulation_path=args.triangulation,
        documents_path=args.documents,
        iad_predictions_path=args.iad_predictions,
        baseline_spec_values=args.baseline_specs,
        max_cases_per_group=args.max_cases_per_group,
    )
    write_mechanism_case_pack_outputs(rows, args.output_dir)
    LOGGER.info("机制案例包输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_public_data_validity_audit(args: argparse.Namespace) -> None:
    """执行 build-public-data-validity-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_public_data_validity_audit_rows_from_paths(
        pairs_path=args.pairs,
        documents_path=args.documents,
        min_gold_pairs=args.min_gold_pairs,
        max_single_silver_topic_ratio=args.max_single_silver_topic_ratio,
        max_dominant_relation_label_ratio=args.max_dominant_relation_label_ratio,
    )
    write_public_data_validity_audit_outputs(rows, args.output_dir)
    LOGGER.info("公开数据有效性审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_open_v3_plan_audit(args: argparse.Namespace) -> None:
    """执行 build-open-v3-plan-audit 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_open_v3_plan_audit_rows_from_paths(
        pairs_path=args.pairs,
        documents_path=args.documents,
        min_documents=args.min_documents,
        min_gold_pairs=args.min_gold_pairs,
        min_silver_pairs=args.min_silver_pairs,
        min_topics=args.min_topics,
        max_top_topic_ratio=args.max_top_topic_ratio,
    )
    write_open_v3_plan_audit_outputs(rows, args.output_dir)
    LOGGER.info("Open-v3 数据目标差距审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_open_v3_source_plan(args: argparse.Namespace) -> None:
    """执行 build-open-v3-source-plan 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    topic_seed_ids = [topic.strip() for topic in str(args.topic_seed_ids or "").split(",") if topic.strip()]
    rows = build_open_v3_source_plan_rows_from_paths(
        pairs_path=args.pairs,
        documents_path=args.documents,
        min_documents=args.min_documents,
        min_gold_pairs=args.min_gold_pairs,
        min_silver_pairs=args.min_silver_pairs,
        min_topics=args.min_topics,
        target_records_per_topic=args.target_records_per_topic,
        topic_seed_ids=topic_seed_ids,
    )
    write_open_v3_source_plan_outputs(rows, args.output_dir)
    LOGGER.info("Open-v3 数据源扩展计划输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_open_v3_split_readiness(args: argparse.Namespace) -> None:
    """执行 build-open-v3-split-readiness 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = build_open_v3_split_readiness_rows_from_paths(
        pairs_path=args.pairs,
        min_sources_per_relation=args.min_sources_per_relation,
        min_topics_for_topic_holdout=args.min_topics_for_topic_holdout,
    )
    write_open_v3_split_readiness_outputs(rows, args.output_dir)
    LOGGER.info("Open-v3 split 泛化就绪度审计输出完成: %s rows=%s", args.output_dir, len(rows))


def command_build_open_v3_heldout_split_plan(args: argparse.Namespace) -> None:
    """执行 build-open-v3-heldout-split-plan 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    plan_rows, assignment_rows = build_open_v3_heldout_split_plan_rows_from_paths(
        pairs_path=args.pairs,
        min_sources_per_relation=args.min_sources_per_relation,
        min_topics_for_topic_holdout=args.min_topics_for_topic_holdout,
        topic_test_ratio=args.topic_test_ratio,
    )
    write_open_v3_heldout_split_plan_outputs(plan_rows, assignment_rows, args.output_dir)
    LOGGER.info("Open-v3 held-out split 计划输出完成: %s plans=%s assignments=%s", args.output_dir, len(plan_rows), len(assignment_rows))


def command_apply_heldout_split_assignment(args: argparse.Namespace) -> None:
    """执行 apply-heldout-split-assignment 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    assigned_pairs, summary = apply_heldout_split_assignments_from_paths(
        pairs_path=args.pairs,
        assignments_path=args.assignments,
        split_strategy=args.split_strategy,
    )
    write_heldout_split_assignment_outputs(assigned_pairs, summary, args.output_dir)
    LOGGER.info("held-out assignment 应用输出完成: %s pairs=%s", args.output_dir, summary["pair_count"])


def command_export_topic_package(args: argparse.Namespace) -> None:
    """执行 export-topic-package 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    rows = export_topic_package(
        workspace_dir=args.workspace_dir,
        output_dir=args.output_dir,
        report_dirs=args.report_dirs,
        model_dir=args.model_dir,
    )
    LOGGER.info("最终课题包导出完成: %s rows=%s", args.output_dir, len(rows))


def command_analyze_candidate_cap(args: argparse.Namespace) -> None:
    """执行 analyze-candidate-cap 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    relations = read_records(args.relations, limit=args.limit)
    rows = run_candidate_cap_analysis(relations, candidate_caps=_parse_int_list(args.candidate_caps))
    write_candidate_cap_csv(rows, args.output)
    LOGGER.info("候选 cap 分析完成: %s rows=%s", args.output, len(rows))


def command_run_bootstrap(args: argparse.Namespace) -> None:
    """执行 run-bootstrap 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    relations = read_records(args.relations, limit=args.limit)
    rows = run_bootstrap_confidence(
        relations,
        iterations=args.iterations,
        seed=args.seed,
        confidence_level=args.confidence_level,
    )
    write_bootstrap_csv(rows, args.output)
    LOGGER.info("bootstrap 置信区间完成: %s rows=%s", args.output, len(rows))


def command_run_iad_evidence_bootstrap(args: argparse.Namespace) -> None:
    """执行 run-iad-evidence-bootstrap 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    records = read_records(args.records, limit=args.limit)
    rows = run_iad_evidence_bootstrap(
        records,
        system_name=args.system_name,
        prediction_field=args.prediction_field,
        score_field=args.score_field,
        threshold=args.threshold,
        iterations=args.iterations,
        seed=args.seed,
        confidence_level=args.confidence_level,
        split_field=args.split_field,
        eval_splits=args.eval_splits,
    )
    write_iad_bootstrap_csv(rows, args.output)
    LOGGER.info("IAD bootstrap 置信区间完成: %s rows=%s", args.output, len(rows))


def command_export_error_analysis(args: argparse.Namespace) -> None:
    """执行 export-error-analysis 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    relations = read_records(args.relations, limit=args.limit)
    documents = read_records(args.documents) if args.documents else None
    systems = [value.strip() for value in args.systems.split(",") if value.strip()] if args.systems else None
    summary_rows, case_rows, annotation_rows = build_error_analysis(
        relations,
        documents=documents,
        systems=systems,
        max_cases_per_bucket=args.max_cases_per_bucket,
        annotation_sample_size=args.annotation_sample_size,
        seed=args.seed,
    )
    write_error_analysis_outputs(summary_rows, case_rows, annotation_rows, args.output_dir)
    LOGGER.info(
        "错误分析导出完成: %s summary=%s cases=%s annotations=%s",
        args.output_dir,
        len(summary_rows),
        len(case_rows),
        len(annotation_rows),
    )


def command_score_manual_annotations(args: argparse.Namespace) -> None:
    """执行 score-manual-annotations 命令。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    annotation_records = read_records(args.input, limit=args.limit)
    summary_rows, disagreement_rows = evaluate_manual_annotations(annotation_records)
    write_manual_annotation_outputs(summary_rows, disagreement_rows, args.output_dir)
    LOGGER.info("人工标注评估完成: %s summary=%s disagreements=%s", args.output_dir, len(summary_rows), len(disagreement_rows))


def command_run_pipeline(args: argparse.Namespace) -> None:
    """执行 P0 smoke pipeline。

    参数:
        args: 命令行参数。

    返回:
        无。
    """
    set_random_seed(args.seed)
    output_dir = ensure_directory(args.output_dir)
    raw_records = list(stream_arxiv_metadata(args.input, limit=args.limit)) if str(args.input).endswith(".json") else read_records(args.input, limit=args.limit)
    if args.sample_size is not None:
        raw_records = raw_records[: args.sample_size]
    normalized = normalize_documents(raw_records)
    normalized_path = output_dir / "normalized_documents.jsonl"
    write_records(normalized, normalized_path)
    views = build_semantic_views(normalized)
    views_path = output_dir / "semantic_views.jsonl"
    write_records(views, views_path)
    document_ids, embeddings, metadata = encode_documents(normalized, args.embedding_model, args.batch_size)
    save_embeddings(document_ids, embeddings, output_dir / "embeddings", metadata)
    build_vector_index(embeddings, output_dir / "embeddings")
    candidates = merge_candidate_pairs(
        [
            generate_identifier_candidates(normalized),
            generate_title_candidates(normalized, max_block_size=args.title_max_block_size),
            generate_lexical_candidates(
                normalized,
                views,
                min_shared_tokens=args.lexical_min_shared_tokens,
                max_postings_per_token=args.lexical_max_postings_per_token,
                max_neighbors_per_token=args.lexical_max_neighbors_per_token,
                max_candidate_pairs=args.lexical_max_candidate_pairs,
            ),
            generate_dense_candidates(document_ids, embeddings, top_k=args.dense_top_k, brute_force_limit=args.dense_brute_force_limit),
        ],
        max_candidate_per_document=args.max_candidate_per_document,
    )
    candidates_path = output_dir / "candidate_pairs.jsonl"
    write_records(candidates, candidates_path)
    embedding_lookup = dict(zip(document_ids, embeddings, strict=True))
    thresholds = build_relation_thresholds_from_args(args)
    relations = score_candidate_pairs(candidates, normalized, views, embedding_lookup, thresholds=thresholds)
    relations_path = output_dir / "pair_relations.jsonl"
    write_records(relations, relations_path)
    duplicate_groups, canonical_documents = merge_duplicates(normalized, relations)
    duplicate_groups_path = output_dir / "duplicate_groups.jsonl"
    canonical_path = output_dir / "canonical_documents.jsonl"
    write_records(duplicate_groups, duplicate_groups_path)
    write_records(canonical_documents, canonical_path)
    topic_edges = build_topic_graph_edges(relations)
    topic_graph_path = output_dir / "topic_graph.jsonl"
    write_records(topic_edges, topic_graph_path)
    clusters, memberships = cluster_documents(canonical_documents, topic_edges)
    clusters_path = output_dir / "clusters.jsonl"
    memberships_path = output_dir / "cluster_membership.jsonl"
    write_records(clusters, clusters_path)
    write_records(memberships, memberships_path)
    rankings = rank_documents(canonical_documents)
    rankings_path = output_dir / "rankings.jsonl"
    write_records(rankings, rankings_path)
    all_recommendations = []
    for query in DEFAULT_QUERIES:
        all_recommendations.extend(rank_recommendations(query, canonical_documents, rankings, limit=10))
    recommendations_path = output_dir / "recommendations.jsonl"
    write_records(all_recommendations, recommendations_path)
    command_evaluate(
        argparse.Namespace(
            output_dir=output_dir / "reports",
            duplicate_groups=str(duplicate_groups_path),
            relations=str(relations_path),
            clusters=str(clusters_path),
            cluster_membership=str(memberships_path),
            rankings=str(rankings_path),
            recommendations=str(recommendations_path),
        )
    )
    LOGGER.info("P0 pipeline 完成: run_id=%s output_dir=%s", args.run_id, output_dir)


def build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器。

    参数:
        无。

    返回:
        argparse 根解析器。
    """
    parser = argparse.ArgumentParser(prog="python -m iad_sieve.cli", description="IAD-Sieve 身份-议题解耦科研文献误合并抑制 CLI")
    parser.add_argument("--log-level", default="INFO", help="日志级别")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare-sample", help="流式抽样 arXiv metadata")
    prepare_parser.add_argument("--input", required=True, help="输入 arXiv metadata JSONL")
    prepare_parser.add_argument("--output", required=True, help="输出样本 JSONL")
    prepare_parser.add_argument("--sample-size", type=int, required=True, help="样本数量")
    prepare_parser.add_argument("--seed", type=int, default=42, help="随机种子")
    prepare_parser.add_argument("--primary-category", default=None, help="主分类过滤")
    prepare_parser.add_argument("--limit", type=int, default=None, help="最多读取原始记录数")
    prepare_parser.set_defaults(func=command_prepare_sample)

    preprocess_parser = subparsers.add_parser("preprocess", help="标准化文献字段")
    preprocess_parser.add_argument("--input", required=True, help="输入 JSONL")
    preprocess_parser.add_argument("--output", required=True, help="输出 JSONL 或 Parquet")
    add_common_io_arguments(preprocess_parser)
    preprocess_parser.set_defaults(func=command_preprocess)

    views_parser = subparsers.add_parser("build-views", help="构建多语义视图")
    views_parser.add_argument("--input", required=True, help="输入标准化文献")
    views_parser.add_argument("--output", required=True, help="输出语义视图")
    add_common_io_arguments(views_parser)
    views_parser.set_defaults(func=command_build_views)

    embed_parser = subparsers.add_parser("embed", help="生成 embedding 和索引")
    embed_parser.add_argument("--input", required=True, help="输入标准化文献")
    embed_parser.add_argument("--output-dir", required=True, help="输出目录")
    embed_parser.add_argument("--embedding-model", default="hashing-fallback", help="embedding 模型")
    embed_parser.add_argument("--batch-size", type=int, default=32, help="批大小")
    add_common_io_arguments(embed_parser)
    embed_parser.set_defaults(func=command_embed)

    candidate_parser = subparsers.add_parser("generate-candidates", help="生成候选文献对")
    candidate_parser.add_argument("--input", required=True, help="输入标准化文献")
    candidate_parser.add_argument("--views", default=None, help="语义视图文件")
    candidate_parser.add_argument("--embedding-dir", default=None, help="embedding 目录")
    candidate_parser.add_argument("--output", required=True, help="输出候选对")
    candidate_parser.add_argument("--max-candidate-per-document", type=int, default=100, help="每篇最大候选数")
    candidate_parser.add_argument("--title-max-block-size", type=int, default=500, help="标题模糊召回最大 block 大小")
    candidate_parser.add_argument("--lexical-top-k", type=int, default=50, help="词法召回 top-k")
    candidate_parser.add_argument("--lexical-min-shared-tokens", type=int, default=2, help="词法候选最少共享 token 数")
    candidate_parser.add_argument("--lexical-max-postings-per-token", type=int, default=200, help="词法 token 最大 postings 数")
    candidate_parser.add_argument("--lexical-max-neighbors-per-token", type=int, default=80, help="词法 token 内每篇最大近邻数")
    candidate_parser.add_argument("--lexical-max-candidate-pairs", type=int, default=2_000_000, help="词法倒排最大候选 pair 数")
    candidate_parser.add_argument("--dense-top-k", type=int, default=50, help="向量召回 top-k")
    candidate_parser.add_argument("--dense-brute-force-limit", type=int, default=5000, help="缺少 FAISS 时允许 brute-force dense 的最大文献数")
    add_common_io_arguments(candidate_parser)
    candidate_parser.set_defaults(func=command_generate_candidates)

    relation_parser = subparsers.add_parser("score-relations", help="候选对关系分离评分")
    relation_parser.add_argument("--input", required=True, help="输入标准化文献")
    relation_parser.add_argument("--views", default=None, help="语义视图文件")
    relation_parser.add_argument("--candidates", required=True, help="候选对文件")
    relation_parser.add_argument("--embedding-dir", default=None, help="embedding 目录")
    relation_parser.add_argument("--output", required=True, help="输出关系文件")
    relation_parser.add_argument("--shard-count", type=int, default=1, help="候选对评分总分片数")
    relation_parser.add_argument("--shard-index", type=int, default=0, help="当前候选对评分分片序号，从 0 开始")
    add_relation_threshold_arguments(relation_parser)
    add_common_io_arguments(relation_parser)
    relation_parser.set_defaults(func=command_score_relations)

    dedup_parser = subparsers.add_parser("merge-duplicates", help="受约束合并重复组")
    dedup_parser.add_argument("--input", required=True, help="输入标准化文献")
    dedup_parser.add_argument("--relations", required=True, help="关系文件")
    dedup_parser.add_argument("--output-dir", required=True, help="输出目录")
    add_common_io_arguments(dedup_parser)
    dedup_parser.set_defaults(func=command_merge_duplicates)

    topic_parser = subparsers.add_parser("build-topic-graph", help="构建主题图")
    topic_parser.add_argument("--relations", required=True, help="关系文件")
    topic_parser.add_argument("--output", required=True, help="输出主题图")
    add_common_io_arguments(topic_parser)
    topic_parser.set_defaults(func=command_build_topic_graph)

    cluster_parser = subparsers.add_parser("cluster", help="主题聚类")
    cluster_parser.add_argument("--input", required=True, help="输入规范文献")
    cluster_parser.add_argument("--topic-graph", default=None, help="主题图文件")
    cluster_parser.add_argument("--output-dir", required=True, help="输出目录")
    add_common_io_arguments(cluster_parser)
    cluster_parser.set_defaults(func=command_cluster)

    rank_parser = subparsers.add_parser("rank", help="重要性排序")
    rank_parser.add_argument("--input", required=True, help="输入规范文献")
    rank_parser.add_argument("--output", required=True, help="输出排序文件")
    add_common_io_arguments(rank_parser)
    rank_parser.set_defaults(func=command_rank)

    recommend_parser = subparsers.add_parser("recommend", help="查询推荐")
    recommend_parser.add_argument("--input", required=True, help="输入规范文献")
    recommend_parser.add_argument("--rankings", default=None, help="排序文件")
    recommend_parser.add_argument("--query", required=True, help="查询文本")
    recommend_parser.add_argument("--rank-profile", default="balanced", help="排序配置")
    recommend_parser.add_argument("--output", required=True, help="输出推荐文件")
    recommend_parser.add_argument("--limit", type=int, default=20, help="推荐数量")
    recommend_parser.add_argument("--sample-size", type=int, default=None, help="兼容参数")
    recommend_parser.add_argument("--seed", type=int, default=42, help="随机种子")
    recommend_parser.set_defaults(func=command_recommend)

    evaluate_parser = subparsers.add_parser("evaluate", help="生成评估报告")
    evaluate_parser.add_argument("--output-dir", required=True, help="输出目录")
    evaluate_parser.add_argument("--duplicate-groups", default=None, help="重复组文件")
    evaluate_parser.add_argument("--relations", default=None, help="关系文件")
    evaluate_parser.add_argument("--clusters", default=None, help="聚类文件")
    evaluate_parser.add_argument("--cluster-membership", default=None, help="聚类成员文件")
    evaluate_parser.add_argument("--cluster-prediction-field", default=None, help="无聚类文件时，用该关系预测字段诱导预测 cluster")
    evaluate_parser.add_argument("--cluster-score-field", default=None, help="无聚类文件时，用该分数字段阈值诱导预测 cluster")
    evaluate_parser.add_argument("--cluster-score-threshold", type=float, default=None, help="cluster score 自动合并阈值")
    evaluate_parser.add_argument("--risk-protocol", default=None, help="risk_calibrated_protocol JSONL 文件")
    evaluate_parser.add_argument("--risk-system", default=None, help="risk protocol 中的系统名称")
    evaluate_parser.add_argument("--risk-fpr-budget", type=float, default=None, help="指定 selected FPR 预算")
    evaluate_parser.add_argument("--risk-fdr-budget", type=float, default=None, help="指定 selected FDR 预算")
    evaluate_parser.add_argument("--identity-field", default="identity_score", help="risk protocol 身份分数字段")
    evaluate_parser.add_argument("--conflict-field", default="conflict_score", help="risk protocol 冲突分数字段")
    evaluate_parser.add_argument("--uncertainty-field", default="uncertainty_score", help="risk protocol 不确定性字段")
    evaluate_parser.add_argument("--version-risk-field", default="version_risk_score", help="risk protocol 版本边界风险字段")
    evaluate_parser.add_argument("--eval-split", default=None, help="只评估指定 split，例如 test")
    evaluate_parser.add_argument("--rankings", default=None, help="排序文件")
    evaluate_parser.add_argument("--recommendations", default=None, help="推荐文件")
    evaluate_parser.set_defaults(func=command_evaluate)

    cluster_bootstrap_parser = subparsers.add_parser("run-cluster-contamination-bootstrap", help="运行 cluster contamination bootstrap 置信区间评估")
    cluster_bootstrap_parser.add_argument("--relations", required=True, help="带 expected_label 的关系文件")
    cluster_bootstrap_parser.add_argument("--output", required=True, help="输出 CSV 文件")
    cluster_bootstrap_parser.add_argument("--system-name", required=True, help="系统名称")
    cluster_bootstrap_parser.add_argument("--cluster-prediction-field", default=None, help="二值预测字段")
    cluster_bootstrap_parser.add_argument("--cluster-score-field", default=None, help="分数字段")
    cluster_bootstrap_parser.add_argument("--cluster-score-threshold", type=float, default=None, help="分数自动合并阈值")
    cluster_bootstrap_parser.add_argument("--risk-protocol", default=None, help="risk_calibrated_protocol JSONL 文件")
    cluster_bootstrap_parser.add_argument("--risk-system", default=None, help="risk protocol 中的系统名称")
    cluster_bootstrap_parser.add_argument("--risk-fpr-budget", type=float, default=None, help="指定 selected FPR 预算")
    cluster_bootstrap_parser.add_argument("--risk-fdr-budget", type=float, default=None, help="指定 selected FDR 预算")
    cluster_bootstrap_parser.add_argument("--identity-field", default="identity_score", help="risk protocol 身份分数字段")
    cluster_bootstrap_parser.add_argument("--conflict-field", default="conflict_score", help="risk protocol 冲突分数字段")
    cluster_bootstrap_parser.add_argument("--uncertainty-field", default="uncertainty_score", help="risk protocol 不确定性字段")
    cluster_bootstrap_parser.add_argument("--version-risk-field", default="version_risk_score", help="risk protocol 版本边界风险字段")
    cluster_bootstrap_parser.add_argument("--eval-split", default=None, help="只评估指定 split，例如 test")
    cluster_bootstrap_parser.add_argument("--iterations", type=int, default=1000, help="bootstrap 抽样次数")
    cluster_bootstrap_parser.add_argument("--confidence-level", type=float, default=0.95, help="置信水平")
    add_common_io_arguments(cluster_bootstrap_parser)
    cluster_bootstrap_parser.set_defaults(func=command_run_cluster_contamination_bootstrap)

    eval_set_parser = subparsers.add_parser("build-eval-set", help="构建 synthetic duplicate 与 hard negative 评估集")
    eval_set_parser.add_argument("--input", required=True, help="输入标准化文献")
    eval_set_parser.add_argument("--relations", default=None, help="可选 pair_relations，用于抽取 hard negative")
    eval_set_parser.add_argument("--output-dir", required=True, help="输出目录")
    eval_set_parser.add_argument("--synthetic-count", type=int, default=200, help="合成重复正例数量")
    eval_set_parser.add_argument("--hard-negative-count", type=int, default=200, help="同主题非重复硬负例数量")
    add_common_io_arguments(eval_set_parser)
    eval_set_parser.set_defaults(func=command_build_eval_set)

    score_eval_parser = subparsers.add_parser("score-eval-set", help="评分 synthetic/hard-negative 评估集")
    score_eval_parser.add_argument("--documents", required=True, help="评估文献文件")
    score_eval_parser.add_argument("--pairs", required=True, help="评估 pair 文件")
    score_eval_parser.add_argument("--output", required=True, help="输出评分关系文件")
    score_eval_parser.add_argument("--summary-output", default=None, help="可选评估指标输出 JSONL")
    add_common_io_arguments(score_eval_parser)
    score_eval_parser.set_defaults(func=command_score_eval_set)

    deepmatcher_parser = subparsers.add_parser("prepare-deepmatcher", help="转换 DeepMatcher DBLP/ACM/Scholar gold label 评估集")
    deepmatcher_parser.add_argument("--table-a", required=True, help="DeepMatcher tableA.csv 路径")
    deepmatcher_parser.add_argument("--table-b", required=True, help="DeepMatcher tableB.csv 路径")
    deepmatcher_parser.add_argument("--pairs", required=True, help="DeepMatcher train/valid/test pair CSV 路径")
    deepmatcher_parser.add_argument("--dataset-name", required=True, help="数据集名称，如 DBLP-ACM")
    deepmatcher_parser.add_argument("--output-dir", required=True, help="输出目录")
    deepmatcher_parser.set_defaults(func=command_prepare_deepmatcher)

    scirepeval_parser = subparsers.add_parser("prepare-scirepeval-proximity", help="转换 SciRepEval/SciDocs proximity same_agenda proxy 评估集")
    scirepeval_parser.add_argument("--metadata", required=True, help="SciRepEval metadata JSONL/JSON/CSV 路径")
    scirepeval_parser.add_argument("--pairs", required=True, help="SciRepEval proximity pair JSONL/JSON/CSV 路径")
    scirepeval_parser.add_argument("--dataset-name", required=True, help="数据集名称，如 scidocs_cite")
    scirepeval_parser.add_argument("--output-dir", required=True, help="输出目录")
    scirepeval_parser.add_argument("--min-relevance-score", type=float, default=1.0, help="视为 same_agenda proxy 的最低相关性分数")
    scirepeval_parser.set_defaults(func=command_prepare_scirepeval_proximity)

    openalex_parser = subparsers.add_parser("prepare-openalex-weak-labels", help="转换 OpenAlex/OpenCitations agenda_non_identity 弱监督评估集")
    openalex_parser.add_argument("--works", required=True, help="OpenAlex Works JSONL/JSON/CSV 路径")
    openalex_parser.add_argument("--citations", default=None, help="可选 OpenCitations COCI 风格 DOI-to-DOI CSV 路径")
    openalex_parser.add_argument("--dataset-name", required=True, help="数据集名称，如 openalex_cs_sample")
    openalex_parser.add_argument("--output-dir", required=True, help="输出目录")
    openalex_parser.add_argument("--min-shared-references", type=int, default=1, help="构造 hard negative 的最少共享引用数")
    openalex_parser.add_argument("--max-pairs-per-topic", type=int, default=200, help="每个 OpenAlex primary topic 最多输出 pair 数")
    openalex_parser.add_argument("--max-pairs", type=int, default=None, help="全局最多输出 pair 数")
    openalex_parser.add_argument("--require-opencitations", action="store_true", help="只输出包含 OpenCitations DOI 共享引用边的 pair")
    add_common_io_arguments(openalex_parser)
    openalex_parser.set_defaults(func=command_prepare_openalex_weak_labels)

    openalex_fetch_parser = subparsers.add_parser("fetch-openalex-works", help="从 OpenAlex Works API 拉取公开 Works JSONL")
    openalex_fetch_parser.add_argument("--output", required=True, help="OpenAlex Works JSONL 输出路径")
    openalex_fetch_parser.add_argument("--summary-output", required=True, help="ingestion summary JSONL 输出路径")
    openalex_fetch_parser.add_argument("--filter", default=None, help="OpenAlex filter 表达式")
    openalex_fetch_parser.add_argument("--select", default=None, help="OpenAlex select 字段")
    openalex_fetch_parser.add_argument("--per-page", type=int, default=100, help="每页记录数，OpenAlex 最大 100")
    openalex_fetch_parser.add_argument("--max-records", type=int, default=1000, help="最多拉取 Works 数")
    openalex_fetch_parser.add_argument("--mailto", default=None, help="可选 OpenAlex polite pool 邮箱")
    openalex_fetch_parser.add_argument("--api-key", default=None, help="可选 OpenAlex API key；未提供时读取 OPENALEX_API_KEY")
    openalex_fetch_parser.add_argument("--endpoint", default="https://api.openalex.org/works", help="OpenAlex Works API endpoint")
    openalex_fetch_parser.add_argument("--timeout", type=int, default=30, help="HTTP 超时时间，单位秒")
    add_common_io_arguments(openalex_fetch_parser)
    openalex_fetch_parser.set_defaults(func=command_fetch_openalex_works)

    sensitivity_parser = subparsers.add_parser("run-sensitivity", help="运行阈值与 candidate cap 参数敏感性分析")
    sensitivity_parser.add_argument("--relations", required=True, help="带 expected_label 的已评分关系文件")
    sensitivity_parser.add_argument("--output", required=True, help="输出 CSV 文件")
    sensitivity_parser.add_argument("--duplicate-thresholds", default=None, help="逗号分隔 duplicate_threshold 列表")
    sensitivity_parser.add_argument("--topic-thresholds", default=None, help="逗号分隔 topic_threshold 列表")
    sensitivity_parser.add_argument("--candidate-caps", default=None, help="逗号分隔 candidate cap 列表")
    sensitivity_parser.add_argument("--review-threshold", type=float, default=0.82, help="candidate cap 分析使用的复核阈值")
    sensitivity_parser.add_argument("--duplicate-threshold-for-tlnd", type=float, default=0.92, help="TLND 分析使用的 duplicate_score 上限")
    sensitivity_parser.add_argument("--contribution-threshold", type=float, default=0.70, help="TLND 分析使用的 contribution_score 上限")
    sensitivity_parser.add_argument("--conflict-threshold", type=float, default=0.25, help="duplicate/candidate 分析使用的 conflict_score 上限")
    add_common_io_arguments(sensitivity_parser)
    sensitivity_parser.set_defaults(func=command_run_sensitivity)

    iad_calibration_parser = subparsers.add_parser("run-iad-calibration", help="运行 IAD-Sieve identity/agenda 阈值校准")
    iad_calibration_parser.add_argument("--relations", required=True, help="已评分评估关系文件")
    iad_calibration_parser.add_argument("--output", required=True, help="输出 CSV 文件")
    iad_calibration_parser.add_argument("--identity-thresholds", default=None, help="逗号分隔 identity_score 阈值列表")
    iad_calibration_parser.add_argument("--agenda-thresholds", default=None, help="逗号分隔 agenda_score 阈值列表")
    iad_calibration_parser.add_argument("--false-merge-rate-constraint", type=float, default=0.01, help="允许的最大误合并率或议题误报率")
    iad_calibration_parser.add_argument("--false-merge-risk-threshold", type=float, default=0.50, help="自动合并允许的最高 false_merge_risk")
    add_common_io_arguments(iad_calibration_parser)
    iad_calibration_parser.set_defaults(func=command_run_iad_calibration)

    risk_protocol_parser = subparsers.add_parser("run-risk-calibrated-protocol", help="运行风险约束三态安全合并评价协议")
    risk_protocol_parser.add_argument("--relations", required=True, help="已评分评估关系文件")
    risk_protocol_parser.add_argument("--output-dir", required=True, help="输出目录")
    risk_protocol_parser.add_argument("--identity-thresholds", default=None, help="逗号分隔 identity 阈值列表")
    risk_protocol_parser.add_argument("--conflict-thresholds", default=None, help="逗号分隔 conflict 阈值列表")
    risk_protocol_parser.add_argument("--uncertainty-thresholds", default=None, help="逗号分隔 uncertainty 阈值列表")
    risk_protocol_parser.add_argument("--version-risk-thresholds", default=None, help="逗号分隔 version risk 阈值列表")
    risk_protocol_parser.add_argument("--fpr-budgets", default=None, help="逗号分隔 negative false merge rate 预算")
    risk_protocol_parser.add_argument("--fdr-budgets", default=None, help="逗号分隔 merge contamination/FDR 预算")
    risk_protocol_parser.add_argument("--identity-field", default="identity_score", help="身份分数字段")
    risk_protocol_parser.add_argument("--conflict-field", default="conflict_score", help="冲突分数字段")
    risk_protocol_parser.add_argument("--uncertainty-field", default="uncertainty_score", help="不确定性字段")
    risk_protocol_parser.add_argument("--version-risk-field", default="version_risk_score", help="版本边界风险字段")
    risk_protocol_parser.add_argument("--veto-fields", default=None, help="逗号分隔 manual_review/veto 字段")
    risk_protocol_parser.add_argument("--system-field", default="system", help="系统名称字段")
    risk_protocol_parser.add_argument("--system-name", default=None, help="显式系统名称，适合单文件 baseline 输入")
    risk_protocol_parser.add_argument("--eval-split", default=None, help="只评估指定 split，例如 test")
    add_common_io_arguments(risk_protocol_parser)
    risk_protocol_parser.set_defaults(func=command_run_risk_calibrated_protocol)

    hard_negative_stress_parser = subparsers.add_parser("build-hard-negative-stress-set", help="构建 agenda-level hard-negative stress set 三层分区")
    hard_negative_stress_parser.add_argument("--relations", nargs="+", required=True, help="一个或多个已评分关系或 IAD-Bench pair 文件")
    hard_negative_stress_parser.add_argument("--output-dir", required=True, help="输出目录")
    hard_negative_stress_parser.add_argument("--min-title-similarity", type=float, default=0.80, help="高置信 hard negative 最低标题相似度")
    hard_negative_stress_parser.add_argument("--min-embedding-similarity", type=float, default=0.75, help="高置信 hard negative 最低表示相似度")
    hard_negative_stress_parser.add_argument("--min-shared-references", type=int, default=2, help="citation-neighbor 最低共享引用数")
    add_common_io_arguments(hard_negative_stress_parser)
    hard_negative_stress_parser.set_defaults(func=command_build_hard_negative_stress_set)

    stress_cluster_parser = subparsers.add_parser("build-stress-cluster-contamination-audit", help="构建 hard-negative stress cluster contamination 审计")
    stress_cluster_parser.add_argument("--stress-relations", required=True, help="hard-negative stress pairs JSONL")
    stress_cluster_parser.add_argument("--scored-relations", required=True, help="系统 scored relations 或 predictions JSONL")
    stress_cluster_parser.add_argument("--output-dir", required=True, help="输出目录")
    stress_cluster_parser.add_argument("--system-name", required=True, help="系统名称")
    stress_cluster_parser.add_argument("--prediction-field", default=None, help="二值自动合并预测字段")
    stress_cluster_parser.add_argument("--score-field", default=None, help="分数字段")
    stress_cluster_parser.add_argument("--score-threshold", type=float, default=None, help="分数自动合并阈值")
    stress_cluster_parser.add_argument("--veto-fields", default=None, help="逗号分隔 manual_review/veto 字段")
    stress_cluster_parser.add_argument("--include-version-risk", action="store_true", help="纳入 version-risk ambiguous 样本")
    add_common_io_arguments(stress_cluster_parser)
    stress_cluster_parser.set_defaults(func=command_build_stress_cluster_contamination_audit)

    iad_classifier_parser = subparsers.add_parser("train-iad-classifier", help="训练 IAD-Sieve 轻量关系分类器")
    iad_classifier_parser.add_argument("--relations", nargs="+", required=True, help="一个或多个已评分评估关系文件")
    iad_classifier_parser.add_argument("--output-dir", required=True, help="输出模型目录")
    iad_classifier_parser.add_argument("--targets", default="same_work,same_agenda,agenda_non_identity", help="逗号分隔训练目标")
    add_common_io_arguments(iad_classifier_parser)
    iad_classifier_parser.set_defaults(func=command_train_iad_classifier)

    iad_risk_model_parser = subparsers.add_parser("train-iad-risk-model", help="训练 IAD-Risk 双空间风险模型")
    iad_risk_model_parser.add_argument("--relations", nargs="+", required=True, help="一个或多个已评分评估关系文件")
    iad_risk_model_parser.add_argument("--output-dir", required=True, help="输出 IAD-Risk 模型目录")
    iad_risk_model_parser.add_argument("--work-threshold", type=float, default=0.5, help="same_work 合并阈值")
    iad_risk_model_parser.add_argument("--agenda-block-threshold", type=float, default=0.5, help="agenda_non_identity 阻断阈值")
    iad_risk_model_parser.add_argument("--risk-threshold", type=float, default=0.5, help="false_merge_risk 阻断阈值")
    iad_risk_model_parser.add_argument("--train-split", default=None, help="训练 split 名称；为空时使用全部记录")
    iad_risk_model_parser.add_argument("--eval-splits", default="", help="逗号分隔评估 split；为空时保持单条 summary 兼容输出")
    add_common_io_arguments(iad_risk_model_parser)
    iad_risk_model_parser.set_defaults(func=command_train_iad_risk_model)

    iad_risk_transformer_parser = subparsers.add_parser("train-iad-risk-transformer-model", help="训练 IAD-Risk Transformer 双空间风险模型")
    iad_risk_transformer_parser.add_argument("--documents", nargs="+", required=True, help="一个或多个 IAD-Bench 文献 JSONL")
    iad_risk_transformer_parser.add_argument("--relations", nargs="+", required=True, help="一个或多个 IAD-Bench pair JSONL")
    iad_risk_transformer_parser.add_argument("--extra-train-relations", nargs="*", default=[], help="只参与训练、不进入评估输出的额外 pair JSONL")
    iad_risk_transformer_parser.add_argument("--output-dir", required=True, help="输出 IAD-Risk Transformer 模型目录")
    iad_risk_transformer_parser.add_argument("--system-name", default="iad_risk_transformer", help="输出摘要中的系统名称")
    iad_risk_transformer_parser.add_argument("--embedding-model", default="hashing-fallback", help="冻结 Transformer 或 sentence-transformers 模型名")
    iad_risk_transformer_parser.add_argument("--adapter-model", default=None, help="SPECTER2 adapter 模型名")
    iad_risk_transformer_parser.add_argument(
        "--model-backend",
        choices=["auto", "sentence-transformers", "transformers", "specter2-adapter", "hashing"],
        default="auto",
        help="embedding 后端",
    )
    iad_risk_transformer_parser.add_argument("--pooling-strategy", choices=["cls", "mean"], default="cls", help="transformers 后端池化策略")
    iad_risk_transformer_parser.add_argument("--batch-size", type=int, default=32, help="embedding 批大小")
    iad_risk_transformer_parser.add_argument("--train-split", default="train", help="用于训练的 split；为空字符串表示全量训练")
    iad_risk_transformer_parser.add_argument("--work-threshold", type=float, default=0.5, help="same_work 合并阈值")
    iad_risk_transformer_parser.add_argument("--agenda-block-threshold", type=float, default=0.5, help="agenda_non_identity 阻断阈值")
    iad_risk_transformer_parser.add_argument("--risk-threshold", type=float, default=0.5, help="false_merge_risk 阻断阈值")
    add_common_io_arguments(iad_risk_transformer_parser)
    iad_risk_transformer_parser.set_defaults(func=command_train_iad_risk_transformer_model)

    external_baseline_parser = subparsers.add_parser("evaluate-external-baseline", help="评估外部模型或强基线 pair 分数")
    external_baseline_parser.add_argument("--relations", required=True, help="已评分评估关系文件")
    external_baseline_parser.add_argument("--baseline", required=True, help="外部 baseline CSV/JSONL/JSON 分数文件")
    external_baseline_parser.add_argument("--output", required=True, help="输出合并外部分数后的关系文件")
    external_baseline_parser.add_argument("--summary-output", required=True, help="输出外部 baseline 指标 JSONL")
    external_baseline_parser.add_argument("--system-name", required=True, help="外部 baseline 名称，如 specter2_cosine")
    external_baseline_parser.add_argument("--score-field", required=True, help="外部 baseline 文件中的分数字段")
    external_baseline_parser.add_argument("--output-score-field", required=True, help="写入关系文件的分数字段")
    external_baseline_parser.add_argument("--thresholds", default="0.5", help="逗号分隔评估阈值")
    external_baseline_parser.add_argument("--metric-target", choices=["same_work", "same_agenda"], default="same_work", help="评估目标")
    external_baseline_parser.add_argument("--baseline-family", default="unknown", help="baseline 家族，如 representation、entity_matching、llm_judge")
    external_baseline_parser.add_argument("--execution-mode", default="precomputed_scores", help="执行模式，如 actual_model、api_model、precomputed_scores、fallback")
    external_baseline_parser.add_argument("--split-field", default="", help="可选 split 字段；设置后仅对指定 split 生成指标")
    external_baseline_parser.add_argument("--eval-splits", default="", help="逗号分隔的目标 split；需配合 --split-field 使用")
    add_common_io_arguments(external_baseline_parser)
    external_baseline_parser.set_defaults(func=command_evaluate_external_baseline)

    representation_baseline_parser = subparsers.add_parser("run-representation-baseline", help="运行 SPECTER2/SciNCL 等表示相似度 baseline")
    representation_baseline_parser.add_argument("--documents", required=True, help="IAD-Bench 或 eval_documents JSONL")
    representation_baseline_parser.add_argument("--pairs", required=True, help="IAD-Bench 或 eval_pairs JSONL")
    representation_baseline_parser.add_argument("--output", required=True, help="baseline pair 分数输出 JSONL")
    representation_baseline_parser.add_argument("--summary-output", required=True, help="baseline 执行摘要输出 JSONL")
    representation_baseline_parser.add_argument("--system-name", required=True, help="baseline 名称，如 specter2_cosine")
    representation_baseline_parser.add_argument("--embedding-model", default="hashing-fallback", help="sentence-transformers 模型名")
    representation_baseline_parser.add_argument("--adapter-model", default=None, help="SPECTER2 adapter 模型名")
    representation_baseline_parser.add_argument(
        "--model-backend",
        choices=["auto", "sentence-transformers", "transformers", "specter2-adapter", "hashing"],
        default="auto",
        help="embedding 后端",
    )
    representation_baseline_parser.add_argument("--pooling-strategy", choices=["cls", "mean"], default="cls", help="transformers 后端池化策略")
    representation_baseline_parser.add_argument("--score-field", default="score", help="输出分数字段名")
    representation_baseline_parser.add_argument("--batch-size", type=int, default=32, help="embedding 批大小")
    representation_baseline_parser.add_argument("--limit", type=int, default=None, help="最多读取文献数")
    representation_baseline_parser.set_defaults(func=command_run_representation_baseline)

    entity_matching_baseline_parser = subparsers.add_parser("run-entity-matching-baseline", help="运行 Ditto/RoBERTa 等实体匹配 pair classifier baseline")
    entity_matching_baseline_parser.add_argument("--documents", required=True, help="IAD-Bench 或 eval_documents JSONL")
    entity_matching_baseline_parser.add_argument("--pairs", required=True, help="IAD-Bench 或 eval_pairs JSONL")
    entity_matching_baseline_parser.add_argument("--output", required=True, help="baseline pair 分数输出 JSONL")
    entity_matching_baseline_parser.add_argument("--summary-output", required=True, help="baseline 执行摘要输出 JSONL")
    entity_matching_baseline_parser.add_argument("--system-name", required=True, help="baseline 名称，如 roberta_entity_matcher")
    entity_matching_baseline_parser.add_argument("--model-name", default="heuristic-entity-matcher", help="Hugging Face 序列分类模型名或本地路径")
    entity_matching_baseline_parser.add_argument("--model-backend", choices=["auto", "transformers", "heuristic"], default="auto", help="entity matching 后端")
    entity_matching_baseline_parser.add_argument("--score-field", default="score", help="输出分数字段名")
    entity_matching_baseline_parser.add_argument("--batch-size", type=int, default=32, help="模型推理批大小")
    entity_matching_baseline_parser.add_argument("--limit", type=int, default=None, help="最多读取文献数")
    entity_matching_baseline_parser.set_defaults(func=command_run_entity_matching_baseline)

    entity_matching_train_parser = subparsers.add_parser("train-entity-matching-baseline", help="训练 Ditto-style/RoBERTa 实体匹配 cross-encoder checkpoint")
    entity_matching_train_parser.add_argument("--documents", required=True, help="IAD-Bench 或 eval_documents JSONL")
    entity_matching_train_parser.add_argument("--pairs", required=True, help="IAD-Bench 或 eval_pairs JSONL")
    entity_matching_train_parser.add_argument("--output-dir", required=True, help="checkpoint 输出目录")
    entity_matching_train_parser.add_argument("--summary-output", required=True, help="训练摘要 JSONL")
    entity_matching_train_parser.add_argument("--system-name", required=True, help="训练系统名称")
    entity_matching_train_parser.add_argument("--base-model-name", default="textattack/roberta-base-MRPC", help="Hugging Face 序列分类 base model")
    entity_matching_train_parser.add_argument("--train-split", default="train", help="训练 split；为空字符串表示使用全部 pair")
    entity_matching_train_parser.add_argument("--split-field", default="split", help="split 字段名")
    entity_matching_train_parser.add_argument("--label-field", default="same_work", help="训练标签字段名")
    entity_matching_train_parser.add_argument("--batch-size", type=int, default=8, help="训练批大小")
    entity_matching_train_parser.add_argument("--epochs", type=int, default=1, help="训练 epoch 数")
    entity_matching_train_parser.add_argument("--learning-rate", type=float, default=2e-5, help="学习率")
    entity_matching_train_parser.add_argument("--max-length", type=int, default=512, help="最大 token 长度")
    entity_matching_train_parser.add_argument("--seed", type=int, default=42, help="随机种子")
    entity_matching_train_parser.add_argument("--limit", type=int, default=None, help="最多读取文献数")
    entity_matching_train_parser.set_defaults(func=command_train_entity_matching_baseline)

    llm_judge_baseline_parser = subparsers.add_parser("run-llm-judge-baseline", help="运行 GPT/LLM pair judge baseline")
    llm_judge_baseline_parser.add_argument("--documents", required=True, help="IAD-Bench 或 eval_documents JSONL")
    llm_judge_baseline_parser.add_argument("--pairs", required=True, help="IAD-Bench 或 eval_pairs JSONL")
    llm_judge_baseline_parser.add_argument("--output", required=True, help="baseline pair 分数输出 JSONL")
    llm_judge_baseline_parser.add_argument("--summary-output", required=True, help="baseline 执行摘要输出 JSONL")
    llm_judge_baseline_parser.add_argument("--system-name", required=True, help="baseline 名称，如 gpt_pair_judge")
    llm_judge_baseline_parser.add_argument("--model-name", default="gpt-5.5", help="LLM 模型名")
    llm_judge_baseline_parser.add_argument("--api-backend", choices=["auto", "openai", "transformers", "fallback"], default="auto", help="LLM judge 后端")
    llm_judge_baseline_parser.add_argument("--api-key-env", default="OPENAI_API_KEY", help="OpenAI API key 环境变量名")
    llm_judge_baseline_parser.add_argument("--score-field", default="same_work_probability", help="输出 same_work 分数字段名")
    llm_judge_baseline_parser.add_argument("--timeout-seconds", type=int, default=30, help="单次 API 请求超时时间")
    llm_judge_baseline_parser.add_argument("--max-new-tokens", type=int, default=80, help="本地 Transformers LLM 每个 pair 最大生成 token 数")
    llm_judge_baseline_parser.add_argument("--batch-size", type=int, default=4, help="本地 Transformers LLM 推理批大小")
    llm_judge_baseline_parser.add_argument("--limit", type=int, default=None, help="最多读取文献数")
    llm_judge_baseline_parser.set_defaults(func=command_run_llm_judge_baseline)

    baseline_error_parser = subparsers.add_parser("build-baseline-error-analysis", help="构建强 baseline hard-negative 错误分析")
    baseline_error_parser.add_argument("--relations", required=True, help="已合并 baseline 分数的 IAD-Bench pair JSONL")
    baseline_error_parser.add_argument("--output-dir", required=True, help="错误分析输出目录")
    baseline_error_parser.add_argument("--system-name", required=True, help="baseline 名称，如 scincl_cosine")
    baseline_error_parser.add_argument("--score-field", required=True, help="baseline 分数字段")
    baseline_error_parser.add_argument("--thresholds", default="0.5", help="逗号分隔评估阈值")
    baseline_error_parser.add_argument("--baseline-family", default="unknown", help="baseline 家族，如 representation、entity_matching、llm_judge")
    baseline_error_parser.add_argument("--execution-mode", default="unknown", help="执行模式，如 actual_model、api_model、fallback")
    baseline_error_parser.add_argument("--limit", type=int, default=None, help="最多读取关系数")
    baseline_error_parser.set_defaults(func=command_build_baseline_error_analysis)

    single_space_union_parser = subparsers.add_parser("run-single-space-union-baseline", help="运行普通 single-space union-find 合并 baseline")
    single_space_union_parser.add_argument("--relations", required=True, help="已合并单空间分数的 IAD-Bench pair JSONL")
    single_space_union_parser.add_argument("--output-dir", required=True, help="single-space union 输出目录")
    single_space_union_parser.add_argument("--system-name", required=True, help="baseline 名称，如 scincl_single_space_union")
    single_space_union_parser.add_argument("--score-field", required=True, help="单空间分数字段")
    single_space_union_parser.add_argument("--threshold", type=float, default=0.9, help="并查集合并阈值")
    single_space_union_parser.add_argument("--baseline-family", default="single_space_union", help="baseline 家族")
    single_space_union_parser.add_argument("--execution-mode", default="actual_algorithm", help="执行模式")
    single_space_union_parser.add_argument("--limit", type=int, default=None, help="最多读取关系数")
    single_space_union_parser.set_defaults(func=command_run_single_space_union_baseline)

    iad_paper_report_parser = subparsers.add_parser("build-iad-paper-report", help="汇总 IAD-Sieve 论文级 RQ 结果表")
    iad_paper_report_parser.add_argument("--output-dir", required=True, help="输出报告目录")
    iad_paper_report_parser.add_argument("--gold-summaries", nargs="*", default=[], help="same_work gold 指标 JSONL 文件")
    iad_paper_report_parser.add_argument("--proxy-summaries", nargs="*", default=[], help="same_agenda proxy 指标 JSONL 文件")
    iad_paper_report_parser.add_argument("--weak-summaries", nargs="*", default=[], help="agenda_non_identity weak label 指标 JSONL 文件")
    iad_paper_report_parser.add_argument("--external-summaries", nargs="*", default=[], help="外部强基线指标 JSONL 文件")
    iad_paper_report_parser.add_argument("--classifier-summaries", nargs="*", default=[], help="IAD 轻量分类器训练摘要 JSONL 文件")
    iad_paper_report_parser.add_argument("--ablation-summaries", nargs="*", default=[], help="IAD 专用消融指标 JSONL 文件")
    iad_paper_report_parser.add_argument("--iad-bench-summaries", nargs="*", default=[], help="IAD-Bench provenance 摘要 JSONL 文件")
    iad_paper_report_parser.add_argument("--iad-risk-summaries", nargs="*", default=[], help="IAD-Risk 双空间模型摘要 JSONL 文件")
    iad_paper_report_parser.add_argument("--bootstrap-summaries", nargs="*", default=[], help="IAD 分层 bootstrap CSV 文件")
    iad_paper_report_parser.add_argument("--openalex-ingestion-summaries", nargs="*", default=[], help="OpenAlex API 采集摘要 JSONL 文件")
    iad_paper_report_parser.add_argument("--openalex-dataset-summaries", nargs="*", default=[], help="OpenAlex API weak-label 数据集摘要 JSONL 文件")
    iad_paper_report_parser.add_argument("--human-audit-plans", nargs="*", default=[], help="后续人工 audit 标注计划文档")
    iad_paper_report_parser.set_defaults(func=command_build_iad_paper_report)

    iad_bench_parser = subparsers.add_parser("build-iad-bench", help="构建 IAD-Bench 标签 provenance 数据契约")
    iad_bench_parser.add_argument("--source-dirs", nargs="+", required=True, help="评估来源目录，需包含 eval_documents.jsonl 和 eval_pairs.jsonl")
    iad_bench_parser.add_argument("--output-dir", required=True, help="IAD-Bench 输出目录")
    iad_bench_parser.add_argument("--train-ratio", type=float, default=0.8, help="train split 比例")
    iad_bench_parser.add_argument("--dev-ratio", type=float, default=0.1, help="dev split 比例")
    iad_bench_parser.add_argument("--seed", type=int, default=42, help="split 随机种子")
    iad_bench_parser.set_defaults(func=command_build_iad_bench)

    iad_bench_balanced_parser = subparsers.add_parser("build-iad-bench-balanced-subset", help="构建 IAD-Bench 来源内关系平衡公开 gold 子集")
    iad_bench_balanced_parser.add_argument("--documents", required=True, help="IAD-Bench documents JSONL")
    iad_bench_balanced_parser.add_argument("--pairs", required=True, help="IAD-Bench pairs JSONL")
    iad_bench_balanced_parser.add_argument("--output-dir", required=True, help="输出目录")
    iad_bench_balanced_parser.add_argument("--relation-labels", default="same_work,unrelated", help="逗号分隔的配平关系标签")
    iad_bench_balanced_parser.add_argument("--include-label-sources", default=None, help="逗号分隔的保留 label_source；为空时不限制")
    iad_bench_balanced_parser.add_argument("--exclude-label-sources", default=None, help="逗号分隔的排除 label_source")
    iad_bench_balanced_parser.add_argument("--train-ratio", type=float, default=0.8, help="train split 比例")
    iad_bench_balanced_parser.add_argument("--dev-ratio", type=float, default=0.1, help="dev split 比例")
    iad_bench_balanced_parser.add_argument("--seed", type=int, default=42, help="抽样与 split 随机种子")
    iad_bench_balanced_parser.set_defaults(func=command_build_iad_bench_balanced_subset)

    iad_bench_stratification_parser = subparsers.add_parser("build-iad-bench-stratification-audit", help="构建 IAD-Bench 标签分层分布审计")
    iad_bench_stratification_parser.add_argument("--pairs", required=True, help="IAD-Bench pairs JSONL")
    iad_bench_stratification_parser.add_argument("--output-dir", required=True, help="输出目录")
    iad_bench_stratification_parser.add_argument("--max-top-strength-ratio", type=float, default=0.8, help="单一 label_strength 最大风险占比")
    iad_bench_stratification_parser.add_argument("--min-sources-per-relation", type=int, default=2, help="每类 relation 最少 label_source 数")
    iad_bench_stratification_parser.set_defaults(func=command_build_iad_bench_stratification_audit)

    iad_bench_source_bias_parser = subparsers.add_parser("build-iad-bench-source-bias-diagnostic", help="构建 IAD-Bench 来源字段偏置诊断")
    iad_bench_source_bias_parser.add_argument("--pairs", required=True, help="IAD-Bench pairs JSONL")
    iad_bench_source_bias_parser.add_argument("--output-dir", required=True, help="输出目录")
    iad_bench_source_bias_parser.add_argument("--train-split", default="train", help="拟合来源多数类映射使用的 split")
    iad_bench_source_bias_parser.add_argument("--eval-splits", default="dev,test", help="逗号分隔的评估 split")
    iad_bench_source_bias_parser.add_argument("--max-shortcut-accuracy", type=float, default=0.8, help="来源捷径风险准确率阈值")
    iad_bench_source_bias_parser.set_defaults(func=command_build_iad_bench_source_bias_diagnostic)

    iad_bench_provenance_balance_parser = subparsers.add_parser("build-iad-bench-provenance-balance-plan", help="构建 IAD-Bench provenance 来源平衡优化计划")
    iad_bench_provenance_balance_parser.add_argument("--pairs", required=True, help="IAD-Bench pairs JSONL")
    iad_bench_provenance_balance_parser.add_argument("--output-dir", required=True, help="输出目录")
    iad_bench_provenance_balance_parser.add_argument("--min-sources-per-relation", type=int, default=2, help="每类 relation 最少 label_source 数")
    iad_bench_provenance_balance_parser.add_argument("--max-dominant-source-ratio", type=float, default=0.8, help="单一来源最大建议占比")
    iad_bench_provenance_balance_parser.add_argument("--target-pairs-per-new-source", type=int, default=500, help="每个新增来源建议 pair 数")
    iad_bench_provenance_balance_parser.set_defaults(func=command_build_iad_bench_provenance_balance_plan)

    iad_bench_source_candidate_registry_parser = subparsers.add_parser(
        "build-iad-bench-source-candidate-registry",
        help="将 provenance 平衡缺口转换为公开来源候选 registry",
    )
    iad_bench_source_candidate_registry_parser.add_argument("--provenance-balance-plan", required=True, help="provenance balance plan JSONL")
    iad_bench_source_candidate_registry_parser.add_argument("--output-dir", required=True, help="输出目录")
    iad_bench_source_candidate_registry_parser.add_argument(
        "--public-gold-source-ids",
        nargs="+",
        default=["deepmatcher_dblp_scholar"],
        help="公开 entity matching gold 来源 ID",
    )
    iad_bench_source_candidate_registry_parser.add_argument(
        "--openalex-topic-seed-ids",
        nargs="+",
        default=["T10009"],
        help="OpenAlex topic seed ID",
    )
    iad_bench_source_candidate_registry_parser.set_defaults(func=command_build_iad_bench_source_candidate_registry)

    iad_bench_source_acquisition_parser = subparsers.add_parser(
        "build-iad-bench-source-acquisition-audit",
        help="检查公开来源候选的本地 raw 文件、下载命令与转换命令",
    )
    iad_bench_source_acquisition_parser.add_argument("--registry", required=True, help="source candidate registry JSONL")
    iad_bench_source_acquisition_parser.add_argument("--output-dir", required=True, help="输出目录")
    iad_bench_source_acquisition_parser.add_argument("--workspace-dir", default=".", help="工作区目录")
    iad_bench_source_acquisition_parser.set_defaults(func=command_build_iad_bench_source_acquisition_audit)

    iad_model_feature_guard_parser = subparsers.add_parser("build-iad-model-feature-guard", help="构建 IAD 模型特征泄漏审计")
    iad_model_feature_guard_parser.add_argument("--model-paths", nargs="+", required=True, help="一个或多个 IAD 模型 JSON 文件")
    iad_model_feature_guard_parser.add_argument("--output-dir", required=True, help="输出目录")
    iad_model_feature_guard_parser.add_argument("--denied-fields", default="", help="逗号分隔的禁止训练特征；为空时使用默认 provenance/label denylist")
    iad_model_feature_guard_parser.set_defaults(func=command_build_iad_model_feature_guard)

    public_data_validity_parser = subparsers.add_parser("build-public-data-validity-audit", help="构建公开 gold/proxy/silver 数据有效性审计")
    public_data_validity_parser.add_argument("--pairs", required=True, help="IAD-Bench pairs JSONL")
    public_data_validity_parser.add_argument("--documents", required=True, help="IAD-Bench documents JSONL")
    public_data_validity_parser.add_argument("--output-dir", required=True, help="输出目录")
    public_data_validity_parser.add_argument("--min-gold-pairs", type=int, default=500, help="期刊阶段建议最低公开 gold pair 数")
    public_data_validity_parser.add_argument("--max-single-silver-topic-ratio", type=float, default=0.8, help="单一 silver 主题最大建议占比")
    public_data_validity_parser.add_argument("--max-dominant-relation-label-ratio", type=float, default=0.8, help="单一关系标签最大建议占比")
    public_data_validity_parser.set_defaults(func=command_build_public_data_validity_audit)

    open_v3_plan_parser = subparsers.add_parser("build-open-v3-plan-audit", help="构建 IAD-Bench-Open-v3 数据目标差距审计")
    open_v3_plan_parser.add_argument("--pairs", required=True, help="IAD-Bench pairs JSONL")
    open_v3_plan_parser.add_argument("--documents", required=True, help="IAD-Bench documents JSONL")
    open_v3_plan_parser.add_argument("--output-dir", required=True, help="输出目录")
    open_v3_plan_parser.add_argument("--min-documents", type=int, default=20000, help="Open-v3 目标最少文档数")
    open_v3_plan_parser.add_argument("--min-gold-pairs", type=int, default=2000, help="Open-v3 目标最少公开 gold pair 数")
    open_v3_plan_parser.add_argument("--min-silver-pairs", type=int, default=50000, help="Open-v3 目标最少 silver hard negative pair 数")
    open_v3_plan_parser.add_argument("--min-topics", type=int, default=30, help="Open-v3 目标最少 OpenAlex topic 数")
    open_v3_plan_parser.add_argument("--max-top-topic-ratio", type=float, default=0.15, help="单一 silver topic 最大建议占比")
    open_v3_plan_parser.set_defaults(func=command_build_open_v3_plan_audit)

    open_v3_source_plan_parser = subparsers.add_parser("build-open-v3-source-plan", help="构建 IAD-Bench-Open-v3 数据源扩展计划")
    open_v3_source_plan_parser.add_argument("--pairs", required=True, help="IAD-Bench pairs JSONL")
    open_v3_source_plan_parser.add_argument("--documents", required=True, help="IAD-Bench documents JSONL")
    open_v3_source_plan_parser.add_argument("--output-dir", required=True, help="输出目录")
    open_v3_source_plan_parser.add_argument("--min-documents", type=int, default=20000, help="Open-v3 目标最少文档数")
    open_v3_source_plan_parser.add_argument("--min-gold-pairs", type=int, default=2000, help="Open-v3 目标最少公开 gold pair 数")
    open_v3_source_plan_parser.add_argument("--min-silver-pairs", type=int, default=50000, help="Open-v3 目标最少 silver hard negative pair 数")
    open_v3_source_plan_parser.add_argument("--min-topics", type=int, default=30, help="Open-v3 目标最少 OpenAlex topic 数")
    open_v3_source_plan_parser.add_argument("--target-records-per-topic", type=int, default=2000, help="每个 OpenAlex topic 目标 Works 数")
    open_v3_source_plan_parser.add_argument("--topic-seed-ids", default="", help="逗号分隔 OpenAlex topic seed ID，例如 T10009,T10010")
    open_v3_source_plan_parser.set_defaults(func=command_build_open_v3_source_plan)

    open_v3_split_parser = subparsers.add_parser("build-open-v3-split-readiness", help="构建 IAD-Bench-Open-v3 split 泛化就绪度审计")
    open_v3_split_parser.add_argument("--pairs", required=True, help="IAD-Bench pairs JSONL")
    open_v3_split_parser.add_argument("--output-dir", required=True, help="输出目录")
    open_v3_split_parser.add_argument("--min-sources-per-relation", type=int, default=2, help="source-held-out 每类 relation 最少来源数")
    open_v3_split_parser.add_argument("--min-topics-for-topic-holdout", type=int, default=30, help="topic-held-out 最少 topic 数")
    open_v3_split_parser.set_defaults(func=command_build_open_v3_split_readiness)

    open_v3_heldout_parser = subparsers.add_parser("build-open-v3-heldout-split-plan", help="构建 IAD-Bench-Open-v3 held-out split 执行计划")
    open_v3_heldout_parser.add_argument("--pairs", required=True, help="IAD-Bench pairs JSONL")
    open_v3_heldout_parser.add_argument("--output-dir", required=True, help="输出目录")
    open_v3_heldout_parser.add_argument("--min-sources-per-relation", type=int, default=2, help="source-held-out 每类 relation 最少来源数")
    open_v3_heldout_parser.add_argument("--min-topics-for-topic-holdout", type=int, default=30, help="topic-held-out 最少 topic 数")
    open_v3_heldout_parser.add_argument("--topic-test-ratio", type=float, default=0.2, help="topic-held-out 测试 topic 比例")
    open_v3_heldout_parser.set_defaults(func=command_build_open_v3_heldout_split_plan)

    heldout_assignment_parser = subparsers.add_parser("apply-heldout-split-assignment", help="将 held-out split assignment 应用到 IAD-Bench pair")
    heldout_assignment_parser.add_argument("--pairs", required=True, help="IAD-Bench pairs JSONL")
    heldout_assignment_parser.add_argument("--assignments", required=True, help="held-out split assignments JSONL")
    heldout_assignment_parser.add_argument("--split-strategy", required=True, help="要应用的 split 策略，如 source_held_out")
    heldout_assignment_parser.add_argument("--output-dir", required=True, help="输出目录")
    heldout_assignment_parser.set_defaults(func=command_apply_heldout_split_assignment)

    iad_ablation_parser = subparsers.add_parser("run-iad-ablation-suite", help="运行 IAD-Sieve 专用消融实验套件")
    iad_ablation_parser.add_argument("--relations", nargs="+", required=True, help="一个或多个已评分评估关系 JSONL 文件")
    iad_ablation_parser.add_argument("--output-dir", required=True, help="输出目录")
    iad_ablation_parser.add_argument("--identity-threshold", type=float, default=0.90, help="identity_score 合并阈值")
    iad_ablation_parser.add_argument("--agenda-block-threshold", type=float, default=0.60, help="agenda_non_identity 阻断阈值")
    iad_ablation_parser.add_argument("--false-merge-risk-threshold", type=float, default=0.50, help="false_merge_risk 阻断阈值")
    iad_ablation_parser.add_argument("--agenda-threshold", type=float, default=0.65, help="same_agenda 判定阈值")
    iad_ablation_parser.add_argument("--dense-threshold", type=float, default=0.90, help="单空间 full_similarity 阈值")
    add_common_io_arguments(iad_ablation_parser)
    iad_ablation_parser.set_defaults(func=command_run_iad_ablation_suite)

    reviewer_audit_parser = subparsers.add_parser("build-reviewer-audit", help="构建审稿人批判清单与论文回应矩阵")
    reviewer_audit_parser.add_argument("--rq-summaries", nargs="*", default=[], help="一个或多个 rq_summary JSONL 文件")
    reviewer_audit_parser.add_argument("--output-dir", required=True, help="输出目录")
    reviewer_audit_parser.set_defaults(func=command_build_reviewer_audit)

    journal_readiness_parser = subparsers.add_parser("build-journal-readiness", help="构建二区/B类期刊 readiness 诊断报告")
    journal_readiness_parser.add_argument("--rq-summaries", nargs="*", default=[], help="一个或多个 rq_summary JSONL 文件")
    journal_readiness_parser.add_argument("--reviewer-audits", nargs="*", default=[], help="一个或多个 reviewer_audit JSONL 文件")
    journal_readiness_parser.add_argument("--output-dir", required=True, help="输出目录")
    journal_readiness_parser.set_defaults(func=command_build_journal_readiness)

    experiment_queue_parser = subparsers.add_parser("build-experiment-queue", help="根据 readiness 报告生成下一轮实验队列")
    experiment_queue_parser.add_argument("--readiness-reports", nargs="*", default=[], help="一个或多个 journal_readiness JSONL 文件")
    experiment_queue_parser.add_argument("--output-dir", required=True, help="输出目录")
    experiment_queue_parser.set_defaults(func=command_build_experiment_queue)

    experiment_preflight_parser = subparsers.add_parser("check-experiment-queue", help="检查实验队列的输入、密钥、远程资源和输出状态")
    experiment_preflight_parser.add_argument("--queue", required=True, help="实验队列 JSONL 文件")
    experiment_preflight_parser.add_argument("--output-dir", required=True, help="输出目录")
    experiment_preflight_parser.add_argument("--workspace-dir", default=".", help="用于解析队列相对路径的工作区目录")
    experiment_preflight_parser.add_argument("--remote-available", action="store_true", help="标记当前已有可执行远程/GPU 环境")
    experiment_preflight_parser.set_defaults(func=command_check_experiment_queue)

    experiment_dependency_parser = subparsers.add_parser("build-experiment-dependency", help="根据队列和 preflight 构建实验依赖图")
    experiment_dependency_parser.add_argument("--queue", required=True, help="实验队列 JSONL 文件")
    experiment_dependency_parser.add_argument("--preflight", required=True, help="实验 preflight JSONL 文件")
    experiment_dependency_parser.add_argument("--output-dir", required=True, help="输出目录")
    experiment_dependency_parser.set_defaults(func=command_build_experiment_dependency)

    experiment_execution_parser = subparsers.add_parser("build-experiment-execution-pack", help="根据队列、preflight 和依赖图生成阶段化执行交接包")
    experiment_execution_parser.add_argument("--queue", required=True, help="实验队列 JSONL 文件")
    experiment_execution_parser.add_argument("--preflight", required=True, help="实验 preflight JSONL 文件")
    experiment_execution_parser.add_argument("--dependency", required=True, help="实验依赖图 JSONL 文件")
    experiment_execution_parser.add_argument("--output-dir", required=True, help="输出目录")
    experiment_execution_parser.set_defaults(func=command_build_experiment_execution_pack)

    remote_output_parser = subparsers.add_parser("validate-remote-outputs", help="验证远程实验输出是否存在、非空且格式可解析")
    remote_output_parser.add_argument("--manifest", required=True, help="remote_output_manifest JSONL 文件")
    remote_output_parser.add_argument("--workspace-dir", default=".", help="用于解析相对输出路径的工作区目录")
    remote_output_parser.add_argument("--output-dir", required=True, help="输出目录")
    remote_output_parser.set_defaults(func=command_validate_remote_outputs)

    remote_environment_parser = subparsers.add_parser("build-remote-environment-audit", help="构建强模型远程环境依赖审计")
    remote_environment_parser.add_argument("--output-dir", required=True, help="输出目录")
    remote_environment_parser.add_argument(
        "--required-modules",
        nargs="*",
        default=None,
        help="Python 模块依赖，格式为 module:package_spec:purpose；省略时使用强模型默认依赖",
    )
    remote_environment_parser.add_argument(
        "--required-env-vars",
        nargs="*",
        default=None,
        help="环境变量依赖，格式为 ENV_NAME:purpose；省略时检查 OPENAI_API_KEY",
    )
    remote_environment_parser.set_defaults(func=command_build_remote_environment_audit)

    remote_blueprint_parser = subparsers.add_parser("build-remote-execution-blueprint", help="聚合远程依赖、根任务和输出验收缺口")
    remote_blueprint_parser.add_argument("--execution-plan", required=True, help="experiment_execution_plan JSONL 文件")
    remote_blueprint_parser.add_argument("--environment-audit", required=True, help="remote_environment_audit JSONL 文件")
    remote_blueprint_parser.add_argument("--remote-output-validation", required=True, help="remote_output_validation JSONL 文件")
    remote_blueprint_parser.add_argument("--output-dir", required=True, help="输出目录")
    remote_blueprint_parser.set_defaults(func=command_build_remote_execution_blueprint)

    remote_connection_parser = subparsers.add_parser("build-remote-connection-pack", help="生成远程连接字段请求、命令模板和安全边界")
    remote_connection_parser.add_argument("--execution-plan", required=True, help="experiment_execution_plan JSONL 文件")
    remote_connection_parser.add_argument("--remote-blueprint", required=True, help="remote_execution_blueprint JSONL 文件")
    remote_connection_parser.add_argument("--profile", default=None, help="本地远程连接 profile JSON；不存在时按空 profile 生成")
    remote_connection_parser.add_argument("--output-dir", required=True, help="输出目录")
    remote_connection_parser.set_defaults(func=command_build_remote_connection_pack)

    remote_profile_parser = subparsers.add_parser("build-remote-connection-profile", help="从参数或环境变量生成本地远程连接 profile，不写入密钥值")
    remote_profile_parser.add_argument("--remote-host", default=None, help="远程服务器地址；为空时读取 REMOTE_HOST")
    remote_profile_parser.add_argument("--remote-port", default=None, help="SSH 端口；为空时读取 REMOTE_PORT")
    remote_profile_parser.add_argument("--remote-user", default=None, help="SSH 用户；为空时读取 REMOTE_USER")
    remote_profile_parser.add_argument("--ssh-key-path", default=None, help="本机 SSH 私钥路径；为空时读取 SSH_KEY_PATH，只写路径不写私钥内容")
    remote_profile_parser.add_argument("--remote-workspace", default=None, help="远程项目目录；为空时读取 REMOTE_WORKSPACE")
    remote_profile_parser.add_argument("--conda-env", default=None, help="远程 conda 环境名；为空时读取 CONDA_ENV")
    remote_profile_parser.add_argument("--remote-conda-path", default=None, help="远程 conda 可执行文件路径；为空时读取 REMOTE_CONDA_PATH，运行模板默认回退到 conda")
    remote_profile_parser.add_argument(
        "--configured-secret",
        dest="configured_secrets",
        nargs="*",
        default=[],
        help="已在远程环境安全配置的密钥变量名，例如 OPENAI_API_KEY；不要传入密钥值",
    )
    remote_profile_parser.add_argument(
        "--provided-model-artifact",
        dest="provided_model_artifacts",
        nargs="*",
        default=[],
        help="已在远程项目目录预置并通过预检的模型相对路径，例如 outputs/models/local_llm_judge",
    )
    remote_profile_parser.add_argument("--output-path", required=True, help="输出本地 profile JSON 路径")
    remote_profile_parser.set_defaults(func=command_build_remote_connection_profile)

    remote_input_request_parser = subparsers.add_parser("build-remote-input-request", help="生成需要用户提供的远程连接字段与安全密钥配置请求单")
    remote_input_request_parser.add_argument("--remote-connection-pack", required=True, help="remote_connection_pack JSONL 文件")
    remote_input_request_parser.add_argument("--q2b-roadmap", default=None, help="q2b_upgrade_roadmap JSONL 文件")
    remote_input_request_parser.add_argument("--reviewer-iteration", default=None, help="reviewer_iteration_audit JSONL 文件")
    remote_input_request_parser.add_argument("--output-dir", required=True, help="输出目录")
    remote_input_request_parser.set_defaults(func=command_build_remote_input_request)

    remote_execution_slice_parser = subparsers.add_parser("build-remote-execution-slice", help="按评估轨道生成远程强模型执行切片")
    remote_execution_slice_parser.add_argument("--q2b-action-board", required=True, help="q2b_action_board JSONL 文件")
    remote_execution_slice_parser.add_argument("--remote-connection-pack", required=True, help="remote_connection_pack JSONL 文件")
    remote_execution_slice_parser.add_argument("--remote-input-request", required=True, help="remote_input_request JSONL 文件")
    remote_execution_slice_parser.add_argument("--remote-execution-blueprint", default=None, help="remote_execution_blueprint JSONL 文件")
    remote_execution_slice_parser.add_argument("--output-dir", required=True, help="输出目录")
    remote_execution_slice_parser.set_defaults(func=command_build_remote_execution_slice)

    remote_slice_run_pack_parser = subparsers.add_parser("build-remote-slice-run-pack", help="按远程执行切片生成轨道级远程运行脚本")
    remote_slice_run_pack_parser.add_argument("--remote-execution-slice", required=True, help="remote_execution_slice JSONL 文件")
    remote_slice_run_pack_parser.add_argument("--execution-plan", required=True, help="experiment_execution_plan JSONL 文件")
    remote_slice_run_pack_parser.add_argument("--output-dir", required=True, help="输出目录")
    remote_slice_run_pack_parser.set_defaults(func=command_build_remote_slice_run_pack)

    primary_remote_readiness_parser = subparsers.add_parser("build-primary-remote-readiness", help="生成主轨道远程执行就绪审计")
    primary_remote_readiness_parser.add_argument("--remote-input-request", required=True, help="remote_input_request JSONL 文件")
    primary_remote_readiness_parser.add_argument("--remote-execution-slice", required=True, help="remote_execution_slice JSONL 文件")
    primary_remote_readiness_parser.add_argument("--remote-slice-run-pack", required=True, help="remote_slice_run_pack JSONL 文件")
    primary_remote_readiness_parser.add_argument("--output-dir", required=True, help="输出目录")
    primary_remote_readiness_parser.set_defaults(func=command_build_primary_remote_readiness)

    primary_remote_handoff_parser = subparsers.add_parser("build-primary-remote-handoff", help="生成主轨道远程执行交接包")
    primary_remote_handoff_parser.add_argument("--primary-remote-readiness", required=True, help="primary_remote_readiness JSONL 文件")
    primary_remote_handoff_parser.add_argument("--output-dir", required=True, help="输出目录")
    primary_remote_handoff_parser.set_defaults(func=command_build_primary_remote_handoff)

    primary_track_claim_gate_parser = subparsers.add_parser("build-primary-track-claim-gate", help="构建主轨道论文主张门禁")
    primary_track_claim_gate_parser.add_argument("--primary-remote-handoff", required=True, help="primary_remote_handoff JSONL 文件")
    primary_track_claim_gate_parser.add_argument("--advanced-track-summary", required=True, help="advanced_model_evidence_track_summary JSONL 文件")
    primary_track_claim_gate_parser.add_argument("--model-superiority-summary", required=True, help="model_superiority_audit_summary JSONL 文件")
    primary_track_claim_gate_parser.add_argument("--innovation-depth-summary", required=True, help="innovation_depth_stress_test_summary JSONL 文件")
    primary_track_claim_gate_parser.add_argument("--q2b-acceptance-summary", required=True, help="q2b_acceptance_rubric_summary JSONL 文件")
    primary_track_claim_gate_parser.add_argument("--output-dir", required=True, help="输出目录")
    primary_track_claim_gate_parser.set_defaults(func=command_build_primary_track_claim_gate)

    primary_track_superiority_protocol_parser = subparsers.add_parser(
        "build-primary-track-superiority-protocol",
        help="构建主轨道强模型优势判定协议",
    )
    primary_track_superiority_protocol_parser.add_argument("--primary-track-claim-gate", required=True, help="primary_track_claim_gate JSONL 文件")
    primary_track_superiority_protocol_parser.add_argument("--advanced-track-summary", required=True, help="advanced_model_evidence_track_summary JSONL 文件")
    primary_track_superiority_protocol_parser.add_argument("--model-superiority-summary", required=True, help="model_superiority_audit_summary JSONL 文件")
    primary_track_superiority_protocol_parser.add_argument("--output-dir", required=True, help="输出目录")
    primary_track_superiority_protocol_parser.set_defaults(func=command_build_primary_track_superiority_protocol)

    primary_track_superiority_evaluator_parser = subparsers.add_parser(
        "build-primary-track-superiority-evaluator",
        help="按预注册协议判定主轨道实际模型优势",
    )
    primary_track_superiority_evaluator_parser.add_argument(
        "--primary-track-superiority-protocol",
        required=True,
        help="primary_track_superiority_protocol JSONL 文件",
    )
    primary_track_superiority_evaluator_parser.add_argument(
        "--metric-summaries",
        nargs="*",
        default=[],
        help="一个或多个主轨道 metric summary JSONL 文件",
    )
    primary_track_superiority_evaluator_parser.add_argument(
        "--bootstrap-summaries",
        nargs="*",
        default=[],
        help="一个或多个主轨道 bootstrap confidence CSV 文件",
    )
    primary_track_superiority_evaluator_parser.add_argument("--output-dir", required=True, help="输出目录")
    primary_track_superiority_evaluator_parser.set_defaults(func=command_build_primary_track_superiority_evaluator)

    no_annotation_protocol_parser = subparsers.add_parser("build-no-annotation-protocol", help="生成无人工标注阶段的证据边界和审稿主张协议")
    no_annotation_protocol_parser.add_argument("--public-data-validity", nargs="+", required=True, help="一个或多个 public_data_validity_audit JSONL 文件")
    no_annotation_protocol_parser.add_argument("--q2b-roadmap", required=True, help="q2b_upgrade_roadmap JSONL 文件")
    no_annotation_protocol_parser.add_argument("--reviewer-iteration", default=None, help="reviewer_iteration_audit JSONL 文件")
    no_annotation_protocol_parser.add_argument("--remote-input-request", default=None, help="remote_input_request JSONL 文件")
    no_annotation_protocol_parser.add_argument("--output-dir", required=True, help="输出目录")
    no_annotation_protocol_parser.set_defaults(func=command_build_no_annotation_protocol)

    remote_result_acceptance_parser = subparsers.add_parser("build-remote-result-acceptance", help="构建远程输出到论文门禁的接收审计")
    remote_result_acceptance_parser.add_argument("--execution-plan", required=True, help="experiment_execution_plan JSONL 文件")
    remote_result_acceptance_parser.add_argument("--remote-output-validation", required=True, help="remote_output_validation JSONL 文件")
    remote_result_acceptance_parser.add_argument("--output-dir", required=True, help="输出目录")
    remote_result_acceptance_parser.set_defaults(func=command_build_remote_result_acceptance)

    q2b_action_board_parser = subparsers.add_parser("build-q2b-action-board", help="构建二区/B类投稿行动板")
    q2b_action_board_parser.add_argument("--submission-gates", required=True, help="submission_gate_audit JSONL 文件")
    q2b_action_board_parser.add_argument("--remote-blueprint", required=True, help="remote_execution_blueprint JSONL 文件")
    q2b_action_board_parser.add_argument("--journal-upgrade-plan", required=True, help="journal_upgrade_plan JSONL 文件")
    q2b_action_board_parser.add_argument("--advanced-model-evidence", required=True, help="advanced_model_evidence JSONL 文件")
    q2b_action_board_parser.add_argument("--remote-connection-pack", default=None, help="remote_connection_pack JSONL 文件")
    q2b_action_board_parser.add_argument("--output-dir", required=True, help="输出目录")
    q2b_action_board_parser.set_defaults(func=command_build_q2b_action_board)

    q2b_completion_parser = subparsers.add_parser("build-q2b-completion-audit", help="构建二区/B类最终目标完成度审计")
    q2b_completion_parser.add_argument("--submission-summaries", nargs="*", default=[], help="一个或多个 submission_gate_audit_summary JSONL 文件")
    q2b_completion_parser.add_argument("--q2b-summaries", nargs="*", default=[], help="一个或多个 q2b_action_board_summary JSONL 文件")
    q2b_completion_parser.add_argument("--reviewer-response-summaries", nargs="*", default=[], help="一个或多个 reviewer_response_summary JSONL 文件")
    q2b_completion_parser.add_argument("--remote-connection-summaries", nargs="*", default=[], help="一个或多个 remote_connection_pack_summary JSONL 文件")
    q2b_completion_parser.add_argument("--remote-result-acceptance-summaries", nargs="*", default=[], help="一个或多个 remote_result_acceptance_summary JSONL 文件")
    q2b_completion_parser.add_argument("--innovation-depth-summaries", nargs="*", default=[], help="一个或多个 innovation_depth_stress_test_summary JSONL 文件")
    q2b_completion_parser.add_argument("--advanced-model-summaries", nargs="*", default=[], help="一个或多个 advanced_model_evidence_summary JSONL 文件")
    q2b_completion_parser.add_argument("--split-readiness-summaries", nargs="*", default=[], help="一个或多个 open_v3_split_readiness_summary JSONL 文件")
    q2b_completion_parser.add_argument("--split-readiness-audits", nargs="*", default=[], help="一个或多个 open_v3_split_readiness JSONL 文件")
    q2b_completion_parser.add_argument("--training-input-summaries", nargs="*", default=[], help="一个或多个 iad_training_input_audit_summary JSONL 文件")
    q2b_completion_parser.add_argument("--source-heldout-coverage-summaries", nargs="*", default=[], help="一个或多个 iad_source_heldout_coverage_summary JSONL 文件")
    q2b_completion_parser.add_argument("--split-evaluation-summaries", nargs="*", default=[], help="一个或多个 iad_risk_split_evaluation_audit_summary JSONL 文件")
    q2b_completion_parser.add_argument("--output-dir", required=True, help="输出目录")
    q2b_completion_parser.set_defaults(func=command_build_q2b_completion_audit)

    q2b_external_blocker_parser = subparsers.add_parser(
        "build-q2b-external-blocker-audit",
        help="构建 Q2/B 外部密钥、远程输出和论文主张锁阻塞合同",
    )
    q2b_external_blocker_parser.add_argument("--completion-audit", required=True, help="q2b_completion_audit JSONL 文件")
    q2b_external_blocker_parser.add_argument("--action-board", required=True, help="q2b_action_board JSONL 文件")
    q2b_external_blocker_parser.add_argument("--remote-result-acceptance", required=True, help="remote_result_acceptance JSONL 文件")
    q2b_external_blocker_parser.add_argument("--advanced-model-evidence", required=True, help="advanced_model_evidence JSONL 文件")
    q2b_external_blocker_parser.add_argument("--output-dir", required=True, help="输出目录")
    q2b_external_blocker_parser.set_defaults(func=command_build_q2b_external_blocker_audit)

    q2b_acceptance_rubric_parser = subparsers.add_parser("build-q2b-acceptance-rubric", help="构建二区/B 类接收判定 rubric")
    q2b_acceptance_rubric_parser.add_argument("--remote-output-summary", required=True, help="remote_output_validation_summary JSONL")
    q2b_acceptance_rubric_parser.add_argument("--remote-result-acceptance-summary", required=True, help="remote_result_acceptance_summary JSONL")
    q2b_acceptance_rubric_parser.add_argument("--advanced-model-summary", required=True, help="advanced_model_evidence_summary JSONL")
    q2b_acceptance_rubric_parser.add_argument("--model-superiority-summary", required=True, help="model_superiority_audit_summary JSONL")
    q2b_acceptance_rubric_parser.add_argument("--innovation-depth-summary", required=True, help="innovation_depth_stress_test_summary JSONL")
    q2b_acceptance_rubric_parser.add_argument("--no-annotation-summary", required=True, help="no_annotation_protocol_summary JSONL")
    q2b_acceptance_rubric_parser.add_argument("--novelty-summary", required=True, help="novelty_falsification_matrix_summary JSONL")
    q2b_acceptance_rubric_parser.add_argument("--prior-art-summary", required=True, help="prior_art_novelty_audit_summary JSONL")
    q2b_acceptance_rubric_parser.add_argument("--q2b-completion-summary", required=True, help="q2b_completion_audit_summary JSONL")
    q2b_acceptance_rubric_parser.add_argument("--reviewer-iteration-summary", required=True, help="reviewer_iteration_audit_summary JSONL")
    q2b_acceptance_rubric_parser.add_argument("--output-dir", required=True, help="输出目录")
    q2b_acceptance_rubric_parser.set_defaults(func=command_build_q2b_acceptance_rubric)

    q2b_experiment_optimizer_parser = subparsers.add_parser("build-q2b-experiment-optimizer", help="把 Q2/B blocked gate 转成审稿驱动的下一轮实验优化清单")
    q2b_experiment_optimizer_parser.add_argument("--q2b-acceptance-rubric", required=True, help="q2b_acceptance_rubric JSONL")
    q2b_experiment_optimizer_parser.add_argument("--reviewer-iteration", required=True, help="reviewer_iteration_audit JSONL")
    q2b_experiment_optimizer_parser.add_argument("--remote-input-request", required=True, help="remote_input_request JSONL")
    q2b_experiment_optimizer_parser.add_argument("--remote-execution-slice", required=True, help="remote_execution_slice JSONL")
    q2b_experiment_optimizer_parser.add_argument("--advanced-track-summary", required=True, help="advanced_model_evidence_track_summary JSONL")
    q2b_experiment_optimizer_parser.add_argument("--output-dir", required=True, help="输出目录")
    q2b_experiment_optimizer_parser.set_defaults(func=command_build_q2b_experiment_optimizer)

    reviewer_threat_parser = subparsers.add_parser("build-reviewer-threat-model", help="构建审稿威胁模型，按拒稿风险聚合创新、先进性、深度和相似工作问题")
    reviewer_threat_parser.add_argument("--q2b-acceptance-rubric", required=True, help="q2b_acceptance_rubric JSONL")
    reviewer_threat_parser.add_argument("--q2b-experiment-optimizer", required=True, help="q2b_experiment_optimizer JSONL")
    reviewer_threat_parser.add_argument("--model-innovation-blueprints", nargs="*", default=[], help="一个或多个 model_innovation_blueprint JSONL 文件")
    reviewer_threat_parser.add_argument("--innovation-depth-audits", nargs="*", default=[], help="一个或多个 innovation_depth_stress_test JSONL 文件")
    reviewer_threat_parser.add_argument("--novelty-matrices", nargs="*", default=[], help="一个或多个 novelty_falsification_matrix JSONL 文件")
    reviewer_threat_parser.add_argument("--prior-art-audits", nargs="*", default=[], help="一个或多个 prior_art_novelty_audit JSONL 文件")
    reviewer_threat_parser.add_argument("--reviewer-iterations", nargs="*", default=[], help="一个或多个 reviewer_iteration_audit JSONL 文件")
    reviewer_threat_parser.add_argument("--output-dir", required=True, help="输出目录")
    reviewer_threat_parser.set_defaults(func=command_build_reviewer_threat_model)

    novelty_falsification_parser = subparsers.add_parser("build-novelty-falsification-matrix", help="构建创新可证伪矩阵，约束创新主张、反证实验和审稿边界")
    novelty_falsification_parser.add_argument("--model-innovation-blueprints", nargs="*", default=[], help="一个或多个 model_innovation_blueprint JSONL 文件")
    novelty_falsification_parser.add_argument("--innovation-depth-audits", nargs="*", default=[], help="一个或多个 innovation_depth_stress_test JSONL 文件")
    novelty_falsification_parser.add_argument("--model-superiority-summary", required=True, help="model_superiority_audit_summary JSONL")
    novelty_falsification_parser.add_argument("--no-annotation-summary", required=True, help="no_annotation_protocol_summary JSONL")
    novelty_falsification_parser.add_argument("--output-dir", required=True, help="输出目录")
    novelty_falsification_parser.set_defaults(func=command_build_novelty_falsification_matrix)

    prior_art_novelty_parser = subparsers.add_parser(
        "build-prior-art-novelty-audit",
        help="构建相关工作新颖性审计，约束相似工作、先进工作和论文创新边界",
    )
    prior_art_novelty_parser.add_argument("--novelty-matrices", nargs="*", default=[], help="一个或多个 novelty_falsification_matrix JSONL 文件")
    prior_art_novelty_parser.add_argument("--advanced-model-summary", required=True, help="advanced_model_evidence_summary JSONL")
    prior_art_novelty_parser.add_argument("--snapshot-date", required=True, help="外部相关工作检索快照日期，格式建议 YYYY-MM-DD")
    prior_art_novelty_parser.add_argument("--output-dir", required=True, help="输出目录")
    prior_art_novelty_parser.set_defaults(func=command_build_prior_art_novelty_audit)

    q2b_upgrade_parser = subparsers.add_parser("build-q2b-upgrade-roadmap", help="把二区/B类阻塞项聚合为阶段化升级路线图")
    q2b_upgrade_parser.add_argument("--completion-audit", required=True, help="q2b_completion_audit JSONL 文件")
    q2b_upgrade_parser.add_argument("--action-board", required=True, help="q2b_action_board JSONL 文件")
    q2b_upgrade_parser.add_argument("--remote-acceptance", default=None, help="remote_result_acceptance JSONL 文件")
    q2b_upgrade_parser.add_argument("--remote-output-summary", default=None, help="remote_output_validation_summary JSONL 文件")
    q2b_upgrade_parser.add_argument("--model-superiority-audit", default=None, help="model_superiority_audit JSONL 文件")
    q2b_upgrade_parser.add_argument("--output-dir", required=True, help="输出目录")
    q2b_upgrade_parser.set_defaults(func=command_build_q2b_upgrade_roadmap)

    reviewer_iteration_parser = subparsers.add_parser("build-reviewer-iteration-audit", help="从审稿人视角批判创新、先进性、深度和数据可信度，并生成下一轮优化动作")
    reviewer_iteration_parser.add_argument("--q2b-roadmap", required=True, help="q2b_upgrade_roadmap JSONL 文件")
    reviewer_iteration_parser.add_argument("--q2b-completion-audit", required=True, help="q2b_completion_audit JSONL 文件")
    reviewer_iteration_parser.add_argument("--model-superiority-audit", default=None, help="model_superiority_audit JSONL 文件")
    reviewer_iteration_parser.add_argument("--innovation-depth", default=None, help="innovation_depth_stress_test JSONL 文件")
    reviewer_iteration_parser.add_argument("--public-data-validity", default=None, help="public_data_validity_audit JSONL 文件")
    reviewer_iteration_parser.add_argument("--feature-guard", default=None, help="iad_model_feature_guard JSONL 文件")
    reviewer_iteration_parser.add_argument("--reviewer-response", default=None, help="reviewer_response_matrix JSONL 文件")
    reviewer_iteration_parser.add_argument("--output-dir", required=True, help="输出目录")
    reviewer_iteration_parser.set_defaults(func=command_build_reviewer_iteration_audit)

    claim_audit_parser = subparsers.add_parser("build-paper-claim-audit", help="构建论文主张审计，限制过度宣称")
    claim_audit_parser.add_argument("--rq-summaries", nargs="*", default=[], help="一个或多个 rq_summary JSONL 文件")
    claim_audit_parser.add_argument("--readiness-reports", nargs="*", default=[], help="一个或多个 journal_readiness JSONL 文件")
    claim_audit_parser.add_argument("--dependency-reports", nargs="*", default=[], help="一个或多个 experiment_dependency JSONL 文件")
    claim_audit_parser.add_argument("--output-dir", required=True, help="输出目录")
    claim_audit_parser.set_defaults(func=command_build_paper_claim_audit)

    research_depth_parser = subparsers.add_parser("build-research-depth-audit", help="构建研究深度审计，批判创新、先进性、模型深度与数据可信度")
    research_depth_parser.add_argument("--reviewer-audits", nargs="*", default=[], help="一个或多个 reviewer_audit JSONL 文件")
    research_depth_parser.add_argument("--claim-audits", nargs="*", default=[], help="一个或多个 paper_claim_audit JSONL 文件")
    research_depth_parser.add_argument("--readiness-reports", nargs="*", default=[], help="一个或多个 journal_readiness JSONL 文件")
    research_depth_parser.add_argument("--dependency-reports", nargs="*", default=[], help="一个或多个 experiment_dependency JSONL 文件")
    research_depth_parser.add_argument("--output-dir", required=True, help="输出目录")
    research_depth_parser.set_defaults(func=command_build_research_depth_audit)

    submission_gate_parser = subparsers.add_parser("build-submission-gate-audit", help="构建投稿门禁 go/no-go 审计")
    submission_gate_parser.add_argument("--readiness-reports", nargs="*", default=[], help="一个或多个 journal_readiness JSONL 文件")
    submission_gate_parser.add_argument("--claim-audits", nargs="*", default=[], help="一个或多个 paper_claim_audit JSONL 文件")
    submission_gate_parser.add_argument("--research-depth-audits", nargs="*", default=[], help="一个或多个 research_depth_audit JSONL 文件")
    submission_gate_parser.add_argument("--remote-output-summaries", nargs="*", default=[], help="一个或多个 remote_output_validation_summary JSONL 文件")
    submission_gate_parser.add_argument("--remote-result-acceptance-summaries", nargs="*", default=[], help="一个或多个 remote_result_acceptance_summary JSONL 文件")
    submission_gate_parser.add_argument("--remote-connection-summaries", nargs="*", default=[], help="一个或多个 remote_connection_pack_summary JSONL 文件")
    submission_gate_parser.add_argument("--source-bias-summaries", nargs="*", default=[], help="一个或多个 iad_bench_source_bias_diagnostic_summary JSONL 文件")
    submission_gate_parser.add_argument("--feature-guard-summaries", nargs="*", default=[], help="一个或多个 iad_model_feature_guard_summary JSONL 文件")
    submission_gate_parser.add_argument("--provenance-balance-summaries", nargs="*", default=[], help="一个或多个 iad_bench_provenance_balance_plan_summary JSONL 文件")
    submission_gate_parser.add_argument("--training-input-summaries", nargs="*", default=[], help="一个或多个 iad_training_input_audit_summary JSONL 文件")
    submission_gate_parser.add_argument("--output-dir", required=True, help="输出目录")
    submission_gate_parser.set_defaults(func=command_build_submission_gate_audit)

    manuscript_evidence_parser = subparsers.add_parser("build-manuscript-evidence-matrix", help="构建稿件主张证据矩阵")
    manuscript_evidence_parser.add_argument("--claim-audits", nargs="*", default=[], help="一个或多个 paper_claim_audit JSONL 文件")
    manuscript_evidence_parser.add_argument("--research-depth-audits", nargs="*", default=[], help="一个或多个 research_depth_audit JSONL 文件")
    manuscript_evidence_parser.add_argument("--submission-gate-audits", nargs="*", default=[], help="一个或多个 submission_gate_audit JSONL 文件")
    manuscript_evidence_parser.add_argument("--output-dir", required=True, help="输出目录")
    manuscript_evidence_parser.set_defaults(func=command_build_manuscript_evidence_matrix)

    reviewer_response_parser = subparsers.add_parser("build-reviewer-response-matrix", help="构建审稿回应矩阵，约束创新、先进性和深度回应边界")
    reviewer_response_parser.add_argument("--reviewer-audits", nargs="*", default=[], help="一个或多个 reviewer_audit JSONL 文件")
    reviewer_response_parser.add_argument("--research-depth-audits", nargs="*", default=[], help="一个或多个 research_depth_audit JSONL 文件")
    reviewer_response_parser.add_argument("--manuscript-evidence", nargs="*", default=[], help="一个或多个 manuscript_evidence_matrix JSONL 文件")
    reviewer_response_parser.add_argument("--submission-gate-audits", nargs="*", default=[], help="一个或多个 submission_gate_audit JSONL 文件")
    reviewer_response_parser.add_argument("--prior-art-audits", nargs="*", default=[], help="一个或多个 prior_art_novelty_audit JSONL 文件")
    reviewer_response_parser.add_argument("--output-dir", required=True, help="输出目录")
    reviewer_response_parser.set_defaults(func=command_build_reviewer_response_matrix)

    manuscript_draft_parser = subparsers.add_parser("build-manuscript-draft-skeleton", help="构建安全论文草稿骨架")
    manuscript_draft_parser.add_argument("--manuscript-evidence", nargs="*", default=[], help="一个或多个 manuscript_evidence_matrix JSONL 文件")
    manuscript_draft_parser.add_argument("--submission-summaries", nargs="*", default=[], help="一个或多个 submission gate summary JSONL 文件")
    manuscript_draft_parser.add_argument("--output-dir", required=True, help="输出目录")
    manuscript_draft_parser.set_defaults(func=command_build_manuscript_draft_skeleton)

    journal_upgrade_parser = subparsers.add_parser("build-journal-upgrade-plan", help="构建二区/B 类期刊升级优化计划")
    journal_upgrade_parser.add_argument("--submission-summaries", nargs="*", default=[], help="一个或多个 submission gate summary JSONL 文件")
    journal_upgrade_parser.add_argument("--research-depth-audits", nargs="*", default=[], help="一个或多个 research_depth_audit JSONL 文件")
    journal_upgrade_parser.add_argument("--remote-output-summaries", nargs="*", default=[], help="一个或多个 remote_output_validation_summary JSONL 文件")
    journal_upgrade_parser.add_argument("--manuscript-draft-summaries", nargs="*", default=[], help="一个或多个 manuscript_draft_skeleton_summary JSONL 文件")
    journal_upgrade_parser.add_argument(
        "--human-annotation-policy",
        choices=["defer", "require"],
        default="defer",
        help="人工标注策略；defer 表示当前暂缓，require 表示作为后续门禁任务",
    )
    journal_upgrade_parser.add_argument("--output-dir", required=True, help="输出目录")
    journal_upgrade_parser.set_defaults(func=command_build_journal_upgrade_plan)

    advanced_model_evidence_parser = subparsers.add_parser("build-advanced-model-evidence", help="构建高级模型证据矩阵")
    advanced_model_evidence_parser.add_argument("--baseline-metric-summaries", nargs="*", default=[], help="一个或多个 baseline metric summary JSONL 文件")
    advanced_model_evidence_parser.add_argument("--execution-summaries", nargs="*", default=[], help="一个或多个 execution summary JSONL 文件")
    advanced_model_evidence_parser.add_argument("--transformer-summaries", nargs="*", default=[], help="一个或多个 IAD-Risk Transformer summary JSONL 文件")
    advanced_model_evidence_parser.add_argument("--bootstrap-summaries", nargs="*", default=[], help="一个或多个 bootstrap confidence CSV 文件")
    advanced_model_evidence_parser.add_argument("--remote-output-summaries", nargs="*", default=[], help="一个或多个 remote output validation summary JSONL 文件")
    advanced_model_evidence_parser.add_argument("--required-systems", nargs="*", default=[], help="投稿前必须补齐的强模型 system 名称")
    advanced_model_evidence_parser.add_argument("--output-dir", required=True, help="输出目录")
    advanced_model_evidence_parser.set_defaults(func=command_build_advanced_model_evidence)

    model_innovation_parser = subparsers.add_parser("build-model-innovation-blueprint", help="构建投稿级模型创新实验蓝图")
    model_innovation_parser.add_argument("--advanced-model-evidence", nargs="*", default=[], help="一个或多个 advanced_model_evidence JSONL 文件")
    model_innovation_parser.add_argument("--q2b-completion-audits", nargs="*", default=[], help="一个或多个 q2b_completion_audit JSONL 文件")
    model_innovation_parser.add_argument("--split-readiness-audits", nargs="*", default=[], help="一个或多个 open_v3_split_readiness JSONL 文件")
    model_innovation_parser.add_argument("--output-dir", required=True, help="输出目录")
    model_innovation_parser.set_defaults(func=command_build_model_innovation_blueprint)

    model_superiority_parser = subparsers.add_parser("build-model-superiority-audit", help="构建模型优势审计，限制强模型优越和 SOTA 主张")
    model_superiority_parser.add_argument("--advanced-model-evidence", nargs="*", default=[], help="一个或多个 advanced_model_evidence JSONL 文件")
    model_superiority_parser.add_argument("--model-innovation-blueprints", nargs="*", default=[], help="一个或多个 model_innovation_blueprint JSONL 文件")
    model_superiority_parser.add_argument("--risk-protocols", nargs="*", default=[], help="一个或多个 risk_calibrated_protocol JSONL 文件")
    model_superiority_parser.add_argument("--main-system", default="iad_risk_transformer_open_v2", help="主方法 system 名称")
    model_superiority_parser.add_argument("--output-dir", required=True, help="输出目录")
    model_superiority_parser.set_defaults(func=command_build_model_superiority_audit)

    innovation_depth_parser = subparsers.add_parser("build-innovation-depth-stress-test", help="构建创新深度压力审计")
    innovation_depth_parser.add_argument("--model-innovation-blueprints", nargs="*", default=[], help="一个或多个 model_innovation_blueprint JSONL 文件")
    innovation_depth_parser.add_argument("--model-superiority-audits", nargs="*", default=[], help="一个或多个 model_superiority_audit JSONL 文件")
    innovation_depth_parser.add_argument("--mechanism-evidence", nargs="*", default=[], help="一个或多个 mechanism_error_evidence JSONL 文件")
    innovation_depth_parser.add_argument("--mechanism-sensitivity", nargs="*", default=[], help="一个或多个 mechanism_threshold_sensitivity JSONL 文件")
    innovation_depth_parser.add_argument("--mechanism-triangulation-summaries", nargs="*", default=[], help="一个或多个 mechanism_triangulation_summary JSONL 文件")
    innovation_depth_parser.add_argument(
        "--mechanism-triangulation-sensitivity-summaries",
        nargs="*",
        default=[],
        help="一个或多个 mechanism_triangulation_sensitivity_summary JSONL 文件",
    )
    innovation_depth_parser.add_argument("--split-readiness-audits", nargs="*", default=[], help="一个或多个 open_v3_split_readiness JSONL 文件")
    innovation_depth_parser.add_argument("--output-dir", required=True, help="输出目录")
    innovation_depth_parser.set_defaults(func=command_build_innovation_depth_stress_test)

    mechanism_error_parser = subparsers.add_parser("build-mechanism-error-evidence", help="构建 IAD-Risk 机制性错误证据")
    mechanism_error_parser.add_argument("--baseline", required=True, help="baseline scored relations JSONL 文件")
    mechanism_error_parser.add_argument("--iad-predictions", required=True, help="IAD-Risk predictions JSONL 文件")
    mechanism_error_parser.add_argument("--system-name", required=True, help="baseline 系统名")
    mechanism_error_parser.add_argument("--score-field", required=True, help="baseline 分数字段")
    mechanism_error_parser.add_argument("--threshold", type=float, required=True, help="baseline 判正阈值")
    mechanism_error_parser.add_argument("--sweep-thresholds", default=None, help="逗号分隔 baseline 阈值敏感性列表")
    mechanism_error_parser.add_argument("--output-dir", required=True, help="输出目录")
    mechanism_error_parser.add_argument("--max-cases", type=int, default=20, help="最多输出案例数")
    mechanism_error_parser.set_defaults(func=command_build_mechanism_error_evidence)

    mechanism_triangulation_parser = subparsers.add_parser("build-mechanism-triangulation-audit", help="构建跨 baseline 机制三角验证审计")
    mechanism_triangulation_parser.add_argument("--iad-predictions", required=True, help="IAD-Risk predictions JSONL 文件")
    mechanism_triangulation_parser.add_argument(
        "--baseline-specs",
        nargs="+",
        required=True,
        help="baseline spec，格式为 system=...,path=...,score_field=...,threshold=...",
    )
    mechanism_triangulation_parser.add_argument("--output-dir", required=True, help="输出目录")
    mechanism_triangulation_parser.set_defaults(func=command_build_mechanism_triangulation_audit)

    mechanism_triangulation_sensitivity_parser = subparsers.add_parser(
        "build-mechanism-triangulation-sensitivity",
        help="构建跨 baseline 机制三角验证阈值敏感性审计",
    )
    mechanism_triangulation_sensitivity_parser.add_argument("--iad-predictions", required=True, help="IAD-Risk predictions JSONL 文件")
    mechanism_triangulation_sensitivity_parser.add_argument(
        "--baseline-specs",
        nargs="+",
        required=True,
        help="baseline spec，格式为 system=...,path=...,score_field=...,thresholds=0.9|0.8",
    )
    mechanism_triangulation_sensitivity_parser.add_argument("--output-dir", required=True, help="输出目录")
    mechanism_triangulation_sensitivity_parser.set_defaults(func=command_build_mechanism_triangulation_sensitivity)

    iad_risk_split_evaluation_parser = subparsers.add_parser(
        "build-iad-risk-split-evaluation-audit",
        help="构建 IAD-Risk split-aware 泛化声明审计",
    )
    iad_risk_split_evaluation_parser.add_argument("--iad-risk-summary", required=True, help="IAD-Risk summary JSONL 文件")
    iad_risk_split_evaluation_parser.add_argument("--iad-risk-model", required=True, help="IAD-Risk model JSON 文件")
    iad_risk_split_evaluation_parser.add_argument("--output-dir", required=True, help="输出目录")
    iad_risk_split_evaluation_parser.set_defaults(func=command_build_iad_risk_split_evaluation_audit)

    iad_source_heldout_coverage_parser = subparsers.add_parser(
        "build-iad-source-heldout-coverage-audit",
        help="构建 IAD source-held-out 关系覆盖审计",
    )
    iad_source_heldout_coverage_parser.add_argument("--pairs", required=True, help="source-held-out pair 或 scored relations JSONL/Parquet 文件")
    iad_source_heldout_coverage_parser.add_argument("--output-dir", required=True, help="输出目录")
    iad_source_heldout_coverage_parser.add_argument(
        "--relation-labels",
        default="same_work,unrelated,agenda_non_identity",
        help="逗号分隔必需 IAD 关系标签",
    )
    iad_source_heldout_coverage_parser.add_argument("--min-train-pairs", type=int, default=1, help="每类关系最少 train pair 数")
    iad_source_heldout_coverage_parser.add_argument("--min-test-pairs", type=int, default=1, help="每类关系最少 test pair 数")
    iad_source_heldout_coverage_parser.set_defaults(func=command_build_iad_source_heldout_coverage_audit)

    iad_source_heldout_gap_plan_parser = subparsers.add_parser(
        "build-iad-source-heldout-gap-plan",
        help="构建 IAD source-held-out 缺口补齐计划",
    )
    iad_source_heldout_gap_plan_parser.add_argument("--coverage-audit", required=True, help="source-held-out coverage audit JSONL 文件")
    iad_source_heldout_gap_plan_parser.add_argument("--candidate-registry", required=True, help="source candidate registry JSONL 文件")
    iad_source_heldout_gap_plan_parser.add_argument("--output-dir", required=True, help="输出目录")
    iad_source_heldout_gap_plan_parser.set_defaults(func=command_build_iad_source_heldout_gap_plan)

    iad_training_input_audit_parser = subparsers.add_parser("build-iad-training-input-audit", help="构建 IAD-Risk 训练输入完备性审计")
    iad_training_input_audit_parser.add_argument("--relations", required=True, help="待审计训练关系 JSONL 或 Parquet 文件")
    iad_training_input_audit_parser.add_argument("--output-dir", required=True, help="输出目录")
    iad_training_input_audit_parser.set_defaults(func=command_build_iad_training_input_audit)

    iad_training_blend_parser = subparsers.add_parser("build-iad-training-blend", help="构建 IAD-Risk gold/silver 训练混合输入")
    iad_training_blend_parser.add_argument("--relations", nargs="+", required=True, help="一个或多个已评分关系 JSONL/Parquet 文件")
    iad_training_blend_parser.add_argument("--output-dir", required=True, help="输出训练混合输入目录")
    iad_training_blend_parser.add_argument(
        "--relation-labels",
        default="same_work,unrelated,agenda_non_identity",
        help="逗号分隔纳入训练的关系标签",
    )
    iad_training_blend_parser.add_argument("--max-per-relation", type=int, default=None, help="每个关系标签最多抽样数量")
    iad_training_blend_parser.add_argument("--train-ratio", type=float, default=0.8, help="训练 split 比例")
    iad_training_blend_parser.add_argument("--dev-ratio", type=float, default=0.1, help="开发 split 比例")
    add_common_io_arguments(iad_training_blend_parser)
    iad_training_blend_parser.set_defaults(func=command_build_iad_training_blend)

    mechanism_case_pack_parser = subparsers.add_parser("build-mechanism-case-pack", help="构建论文机制案例包")
    mechanism_case_pack_parser.add_argument("--triangulation", required=True, help="mechanism_triangulation_audit JSONL 文件")
    mechanism_case_pack_parser.add_argument("--documents", required=True, help="IAD-Bench documents JSONL 文件")
    mechanism_case_pack_parser.add_argument("--iad-predictions", required=True, help="IAD-Risk predictions JSONL 文件")
    mechanism_case_pack_parser.add_argument(
        "--baseline-specs",
        nargs="+",
        required=True,
        help="baseline spec，格式为 system=...,path=...,score_field=...,threshold=...",
    )
    mechanism_case_pack_parser.add_argument("--max-cases-per-group", type=int, default=2, help="每个三角验证分组最多案例数")
    mechanism_case_pack_parser.add_argument("--output-dir", required=True, help="输出目录")
    mechanism_case_pack_parser.set_defaults(func=command_build_mechanism_case_pack)

    topic_package_parser = subparsers.add_parser("export-topic-package", help="导出最终课题包")
    topic_package_parser.add_argument("--workspace-dir", default=".", help="项目工作区目录")
    topic_package_parser.add_argument("--output-dir", required=True, help="课题包输出目录")
    topic_package_parser.add_argument("--report-dirs", nargs="*", default=[], help="需要纳入课题包的报告目录")
    topic_package_parser.add_argument("--model-dir", default=None, help="IAD 轻量分类器模型目录")
    topic_package_parser.set_defaults(func=command_export_topic_package)

    candidate_cap_parser = subparsers.add_parser("analyze-candidate-cap", help="分析真实关系结果中的 candidate cap 截断影响")
    candidate_cap_parser.add_argument("--relations", required=True, help="已评分关系文件")
    candidate_cap_parser.add_argument("--output", required=True, help="输出 CSV 文件")
    candidate_cap_parser.add_argument("--candidate-caps", default=None, help="逗号分隔 candidate cap 列表")
    add_common_io_arguments(candidate_cap_parser)
    candidate_cap_parser.set_defaults(func=command_analyze_candidate_cap)

    bootstrap_parser = subparsers.add_parser("run-bootstrap", help="运行主要指标 bootstrap 置信区间评估")
    bootstrap_parser.add_argument("--relations", required=True, help="已评分关系文件")
    bootstrap_parser.add_argument("--output", required=True, help="输出 CSV 文件")
    bootstrap_parser.add_argument("--iterations", type=int, default=1000, help="bootstrap 抽样次数")
    bootstrap_parser.add_argument("--confidence-level", type=float, default=0.95, help="置信水平")
    add_common_io_arguments(bootstrap_parser)
    bootstrap_parser.set_defaults(func=command_run_bootstrap)

    iad_bootstrap_parser = subparsers.add_parser("run-iad-evidence-bootstrap", help="运行 IAD-Risk 与强 baseline 分层 bootstrap 置信区间评估")
    iad_bootstrap_parser.add_argument("--records", required=True, help="IAD prediction、single-space prediction 或 baseline scored relation JSONL")
    iad_bootstrap_parser.add_argument("--output", required=True, help="输出 CSV 文件")
    iad_bootstrap_parser.add_argument("--system-name", required=True, help="系统名称")
    iad_bootstrap_parser.add_argument("--prediction-field", default=None, help="直接 0/1 预测字段，例如 merge_prediction")
    iad_bootstrap_parser.add_argument("--score-field", default=None, help="分数字段，例如 match_probability")
    iad_bootstrap_parser.add_argument("--threshold", type=float, default=None, help="score_field 转 0/1 预测的阈值")
    iad_bootstrap_parser.add_argument("--split-field", default="", help="可选 split 字段；设置后仅对指定 split 生成 bootstrap")
    iad_bootstrap_parser.add_argument("--eval-splits", default="", help="逗号分隔的目标 split；需配合 --split-field 使用")
    iad_bootstrap_parser.add_argument("--iterations", type=int, default=1000, help="bootstrap 抽样次数")
    iad_bootstrap_parser.add_argument("--confidence-level", type=float, default=0.95, help="置信水平")
    add_common_io_arguments(iad_bootstrap_parser)
    iad_bootstrap_parser.set_defaults(func=command_run_iad_evidence_bootstrap)

    error_parser = subparsers.add_parser("export-error-analysis", help="导出错误分析案例和人工标注样本")
    error_parser.add_argument("--relations", required=True, help="已评分关系文件")
    error_parser.add_argument("--output-dir", required=True, help="输出目录")
    error_parser.add_argument("--documents", default=None, help="可选标准化文献文件，用于补充人工标注上下文")
    error_parser.add_argument("--systems", default=None, help="逗号分隔系统名称，空值表示全部")
    error_parser.add_argument("--max-cases-per-bucket", type=int, default=50, help="每个系统每类错误最多导出案例数")
    error_parser.add_argument("--annotation-sample-size", type=int, default=100, help="人工标注样本数量")
    add_common_io_arguments(error_parser)
    error_parser.set_defaults(func=command_export_error_analysis)

    manual_parser = subparsers.add_parser("score-manual-annotations", help="统计人工标注 JSONL 结果")
    manual_parser.add_argument("--input", required=True, help="人工标注 JSONL 文件")
    manual_parser.add_argument("--output-dir", required=True, help="输出目录")
    add_common_io_arguments(manual_parser)
    manual_parser.set_defaults(func=command_score_manual_annotations)

    pipeline_parser = subparsers.add_parser("run-pipeline", help="运行 P0 完整流水线")
    pipeline_parser.add_argument("--input", required=True, help="输入 arXiv JSONL")
    pipeline_parser.add_argument("--run-id", required=True, help="运行 ID")
    pipeline_parser.add_argument("--output-dir", required=True, help="输出目录")
    pipeline_parser.add_argument("--embedding-model", default="hashing-fallback", help="embedding 模型")
    pipeline_parser.add_argument("--batch-size", type=int, default=32, help="批大小")
    pipeline_parser.add_argument("--max-candidate-per-document", type=int, default=100, help="每篇最大候选数")
    pipeline_parser.add_argument("--title-max-block-size", type=int, default=500, help="标题模糊召回最大 block 大小")
    pipeline_parser.add_argument("--lexical-min-shared-tokens", type=int, default=2, help="词法候选最少共享 token 数")
    pipeline_parser.add_argument("--lexical-max-postings-per-token", type=int, default=200, help="词法 token 最大 postings 数")
    pipeline_parser.add_argument("--lexical-max-neighbors-per-token", type=int, default=80, help="词法 token 内每篇最大近邻数")
    pipeline_parser.add_argument("--lexical-max-candidate-pairs", type=int, default=2_000_000, help="词法倒排最大候选 pair 数")
    pipeline_parser.add_argument("--dense-top-k", type=int, default=50, help="向量召回 top-k")
    pipeline_parser.add_argument("--dense-brute-force-limit", type=int, default=5000, help="缺少 FAISS 时允许 brute-force dense 的最大文献数")
    add_relation_threshold_arguments(pipeline_parser)
    add_common_io_arguments(pipeline_parser)
    pipeline_parser.set_defaults(func=command_run_pipeline)

    artifact_parser = subparsers.add_parser("export-paper-artifacts", help="导出论文产物索引")
    artifact_parser.add_argument("--output-dir", required=True, help="输出目录")
    artifact_parser.add_argument("--input", default=None, help="可选输入目录")
    artifact_parser.set_defaults(func=command_export_paper_artifacts)
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 主函数。

    参数:
        argv: 可选命令行参数。

    返回:
        进程退出码。
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    try:
        args.func(args)
        return 0
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("命令执行失败: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
