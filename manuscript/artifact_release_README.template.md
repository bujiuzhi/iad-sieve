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
python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts
python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release
cd /path/to/release
sha256sum -c checksums.sha256
cd /path/to/iad-sieve
python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release
python manuscript/scripts/validate_manuscript.py --strict-latex
python manuscript/scripts/verify_fixture_rebuild.py
python scripts/check_public_release.py
```

## Required Artifact IDs

- open_v2_main_results
  - tables/open_v2_main_results.csv must include per-row denominator counts, per-row threshold source, scope label used in the main table, automatic merge count, block count, defer count, automatic merge coverage, and defer rate.
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
- cluster_metric_summary
- cannot_link_audit

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
Component-causality claims require ablation_suite.
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
- Release DOI:
- Repository commit:
  - Must match `manifest.json` field `repository.commit` and the final manuscript package commit.
- Release date:
- Source data versions:
- Command logs location:
- Hardware and dependency summary:
