# IAD-Risk Artifact Release README Template

This template is for the external result artifact release associated with "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication". It documents how reviewers can audit released tables, predictions, logs, manifests, and checksums outside the Git repository.

## Data Policy

Do not include raw third-party data.
Do not include model checkpoints.
Do not include credentials, personal identifiers, or local paths.
Include only derived evaluation artifacts that can be redistributed under the release policy.

## Required Top-Level Files

- README.md
- manifest.json
- checksums.sha256

## Required Directories

- configs/
- tables/
- predictions/
- reports/
- logs/

## Minimum Validation Commands

Run these commands from the repository root after unpacking the release:

```bash
cd /path/to/iad-sieve
python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only
python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts
python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release
cd /path/to/release
sha256sum -c checksums.sha256
cd /path/to/iad-sieve
python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release
python -m iad_sieve.cli --help
python manuscript/scripts/validate_manuscript.py --strict-latex
python manuscript/scripts/verify_fixture_rebuild.py
python scripts/check_public_release.py
```

## Required Artifact IDs

- open_v2_main_results
  - tables/open_v2_main_results.csv must include per-row denominator counts, per-row threshold source, scope label used in the main table, automatic merge count, block count, defer count, automatic merge coverage, defer rate, and capacity-normalized review load.
- iad_risk_predictions
  - predictions/iad_risk_transformer_predictions.jsonl must include system, pair_id, source_document_id, target_document_id, expected labels, label strength, hard-negative level, split identifiers, relation-head scores, work_threshold, agenda_block_threshold, risk_threshold, threshold source, and merge_prediction.
- representation_baseline_scores
  - predictions/representation_baseline_scores.jsonl must include system, pair_id, source_document_id, target_document_id, expected labels, label strength, hard-negative level, split identifiers, normalized score, score_field, threshold_value, threshold source, and merge_prediction.
- supervised_baseline_predictions
  - predictions/roberta_pair_classifier_predictions.jsonl must include system, pair_id, source_document_id, target_document_id, expected labels, label strength, hard-negative level, split identifiers, match_probability, threshold_value, threshold source, and merge_prediction.
- threshold_selection_logs
  - logs/threshold_selection_logs.jsonl must include system, threshold_name, threshold_value, selection_split, selection_metric, selection_rule, applied_scope, and score_field.
- iad_bench_split_summary
- source_input_manifest
  - configs/source_input_manifest.json must record source name, acquisition date or version, original provider, local file name, record count when known, license boundary, and SHA256 checksum for each public input file.
- processing_run_log
  - logs/processing_run_log.jsonl must record command line, code commit, environment summary, random seed, start and finish timestamps, input manifest reference, output path, and exit status for each rebuild stage.
- bootstrap_intervals
  - reports/bootstrap_intervals.csv is required before confidence-interval claims. It must include metric_name rows for same_work_f1, fmr, and hnfmr, with system, scope_type, prediction_artifact_id, prediction_file_sha256, bootstrap_method, resample_unit, resample_count, confidence_level, alpha, random_seed, point_estimate, interval_lower, interval_upper, metric_denominator, threshold_source, and command_line. Each row must bind to the exact prediction file checksum and satisfy interval_lower <= point_estimate <= interval_upper.
- ablation_suite
  - reports/iad_ablation_suite.csv is required before component-causality claims. It must include protocol_variant rows for no-risk-gate, no-ANI-head, single-space, no-cannot-link, and post-hoc-threshold, with protocol_required, accepted_for_component_causality, threshold_source, protocol_scope_rule, requires_prediction_rows, denominators, and false-merge metrics. The post-hoc-threshold row must use threshold_source=post_hoc_labeled_sweep and must not be treated as standalone component-causality evidence.
- manual_validation_slice
  - reports/manual_validation_slice.csv is required before human-validation claims. It must contain a 500-1000 pair reviewed slice with manual_validation_stratum coverage for silver_hard_negative, high_score_false_merge_candidate, blocked_or_deferred, model_disagreement, version_boundary, identifier_conflict, and sparse_metadata; two independent reviewer codes through reviewer_1_code and reviewer_2_code; labels in reviewer_1_label, reviewer_2_label, and adjudicated_label; blinding fields reviewer_blinding_confirmed, model_score_hidden, and merge_decision_hidden; adjudication_status, adjudication_rationale, pair_level_notes, and agreement_status.
- threshold_sensitivity_grid
  - reports/threshold_sensitivity_grid.csv is required before threshold-stability claims. It must include at least two predefined threshold rows generated from exactly one prediction_artifact_id and prediction_file_sha256, with system, threshold_grid_id, threshold_range_source, threshold_source, selection_split, evaluation_split, work_threshold, agenda_block_threshold, risk_threshold, selected_operating_point, same_work_f1, fmr, hnfmr, denominator counts, automatic_merge_count, block_count, defer_count, random_seed, command_line, and separate selection and evaluation splits.
- cluster_metric_summary
  - reports/cluster_metric_summary.csv is required before cluster-level quality claims. It must include system, cluster_run_id, merge_policy_id, prediction_artifact_id, prediction_file_sha256, threshold_source, work_threshold, agenda_block_threshold, risk_threshold, cluster_assignment_file, pair_to_cluster_trace_file, cluster_id, cluster_size, accepted_link_count, cannot_link_conflict_count, unresolved_conflict_count, cluster_contamination_rate, singleton_rate, merge_coverage, random_seed, and command_line, with exactly one cluster_run_id, exactly one merge_policy_id, prediction_artifact_id, and prediction_file_sha256.
- cannot_link_audit
  - reports/cannot_link_audit.csv is required before cluster-level quality claims. It must include system, cluster_run_id, merge_policy_id, prediction_artifact_id, prediction_file_sha256, threshold_source, work_threshold, agenda_block_threshold, risk_threshold, cannot_link_rule_id, conflict_type, source_document_id, target_document_id, cannot_link_flag, accepted_merge_blocked, violation_detected, unresolved_conflict, cannot_link_coverage_rate, identifier_conflict_rule, pair_to_cluster_trace_file, random_seed, and command_line, with exactly one cluster_run_id, exactly one merge_policy_id, prediction_artifact_id, and prediction_file_sha256.

## Conditional Claim Artifacts

- confidence_intervals_claimed requires bootstrap_intervals.
- component_causality_claimed requires ablation_suite.
- human_validation_claimed requires manual_validation_slice.
- threshold_stability_claimed requires threshold_sensitivity_grid.
- cluster_level_quality_claimed requires cluster_metric_summary and cannot_link_audit.
- broad_method_ranking_claimed requires bootstrap_intervals, manual_validation_slice, and threshold_sensitivity_grid.

## Claim Boundaries

Silver labels are not human gold.
Full numerical audit requires external artifacts.
Broad method ranking is not claimed unless conditional artifacts are complete.
Threshold-stability claims require threshold_sensitivity_grid and threshold_selection_logs.
Component-causality claims require ablation_suite with full protocol_variant coverage and post-hoc threshold diagnostics separated from causal evidence.
Human-validation claims require manual_validation_slice and adjudication records.
Cluster-level quality is not claimed unless cluster artifacts are complete.

## Reproduction Levels

- L0 code check: verify package installation, CLI availability, tests, manuscript validation, and public-release scanning.
- L1 fixture rebuild: rebuild the no-network fixture package under tests/fixtures.
- L2 public-source rebuild: rebuild derived evaluation sources from independently obtained public raw files.
- L3 result audit: verify released tables, predictions, configs, logs, manifests, checksums, and commit identifiers.

## L2 Public-Source Rebuild Boundary

The release must include source_input_manifest and processing_run_log so reviewers can trace public inputs to derived evaluation artifacts without receiving raw third-party data in Git. These files document the input boundary, command boundary, output boundary, and checksum boundary for the rebuild.

## Release Metadata To Fill

- Release URL:
  - Must match `manifest.json` field `publication.artifact_release_url` and the final-upload `submission_metadata.yml`.
- Release DOI:
  - Must match `manifest.json` field `publication.artifact_release_doi` and the final-upload `submission_metadata.yml`.
- Public access status:
  - Must match `manifest.json` field `publication.public_access_status`; final upload accepts public, published, publicly accessible, or archived.
- Repository commit:
  - Must match `manifest.json` field `repository.commit` and the final manuscript package commit.
- Release date:
- Source data versions:
- Command logs location:
- Hardware and dependency summary:
