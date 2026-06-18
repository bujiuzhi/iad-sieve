"""Validate an external result artifact release package.

The validator checks a release directory that is stored outside Git. It ensures
the package has the required manifest, result files, checksums, data-policy
boundaries, and no raw third-party data or local secrets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
MANUSCRIPT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = MANUSCRIPT_ROOT / "build" / "artifact_release"
DEFAULT_TEMPLATE_PATH = MANUSCRIPT_ROOT / "artifact_release_manifest.template.json"
REQUIRED_DIRECTORIES = {"configs", "tables", "predictions", "reports", "logs"}
REQUIRED_TOP_LEVEL_FILES = {"README.md", "manifest.json", "checksums.sha256"}
REQUIRED_README_MARKERS = {
    "release title": "IAD-Risk Artifact Release",
    "raw data exclusion": "Do not include raw third-party data",
    "manifest file": "manifest.json",
    "checksum file": "checksums.sha256",
    "checksum command": "sha256sum -c checksums.sha256",
    "validator command": "python manuscript/scripts/validate_artifact_release.py --artifact-dir",
    "repository commit": "Repository commit",
    "claim boundaries": "Claim Boundaries",
    "external artifact boundary": "Full numerical audit requires external artifacts",
    "source input manifest": "source_input_manifest",
    "processing run log": "processing_run_log",
    "result audit level": "L3 result audit",
}
FORBIDDEN_RELEASE_STATUSES = {"template_pending_external_artifact", "skeleton_pending_artifacts"}
REQUIRED_ARTIFACT_IDS = {
    "open_v2_main_results",
    "iad_risk_predictions",
    "representation_baseline_scores",
    "supervised_baseline_predictions",
    "threshold_selection_logs",
    "iad_bench_split_summary",
    "source_input_manifest",
    "processing_run_log",
}
OPEN_V2_MAIN_RESULTS_REQUIRED_COLUMNS = {
    "system",
    "scope_type",
    "same_work_f1",
    "fmr",
    "hnfmr",
    "same_work_f1_denominator",
    "fmr_denominator",
    "hnfmr_denominator",
    "threshold_source",
    "automatic_merge_count",
    "block_count",
    "defer_count",
    "automatic_merge_coverage",
    "defer_rate",
    "capacity_normalized_review_load",
}
ABLATION_SUITE_REQUIRED_COLUMNS = {
    "variant",
    "protocol_variant",
    "protocol_required",
    "accepted_for_component_causality",
    "metric_target",
    "threshold_source",
    "protocol_scope_rule",
    "requires_prediction_rows",
    "identity_threshold",
    "selected_identity_threshold",
    "weak_label_count",
    "precision",
    "recall",
    "f1",
    "false_merge_rate",
    "false_positive",
    "false_negative",
}
REQUIRED_ABLATION_PROTOCOL_VARIANTS = {
    "no-risk-gate",
    "no-ANI-head",
    "single-space",
    "no-cannot-link",
    "post-hoc-threshold",
}
MANUAL_VALIDATION_SLICE_REQUIRED_COLUMNS = {
    "pair_id",
    "source_document_id",
    "target_document_id",
    "manual_validation_stratum",
    "reviewer_1_code",
    "reviewer_2_code",
    "reviewer_1_label",
    "reviewer_2_label",
    "adjudicated_label",
    "reviewer_blinding_confirmed",
    "model_score_hidden",
    "merge_decision_hidden",
    "adjudication_status",
    "adjudication_rationale",
    "pair_level_notes",
    "agreement_status",
}
MANUAL_VALIDATION_REQUIRED_STRATA = {
    "silver_hard_negative",
    "high_score_false_merge_candidate",
    "blocked_or_deferred",
    "model_disagreement",
    "version_boundary",
    "identifier_conflict",
    "sparse_metadata",
}
MANUAL_VALIDATION_ALLOWED_LABELS = {
    "same_work",
    "agenda_non_identity",
    "unrelated",
    "version_boundary",
    "uncertain",
}
MANUAL_VALIDATION_ALLOWED_AGREEMENT_STATUSES = {"agreement", "disagreement"}
MANUAL_VALIDATION_ALLOWED_ADJUDICATION_STATUSES = {"agreement_confirmed", "adjudicated"}
MANUAL_VALIDATION_MIN_ROWS = 500
MANUAL_VALIDATION_MAX_ROWS = 1000
THRESHOLD_SENSITIVITY_GRID_REQUIRED_COLUMNS = {
    "system",
    "threshold_grid_id",
    "prediction_artifact_id",
    "prediction_file_sha256",
    "threshold_range_source",
    "threshold_source",
    "selection_split",
    "evaluation_split",
    "work_threshold",
    "agenda_block_threshold",
    "risk_threshold",
    "selected_operating_point",
    "same_work_f1",
    "fmr",
    "hnfmr",
    "same_work_f1_denominator",
    "fmr_denominator",
    "hnfmr_denominator",
    "automatic_merge_count",
    "block_count",
    "defer_count",
    "random_seed",
    "command_line",
}
THRESHOLD_SENSITIVITY_RATIO_FIELDS = {
    "work_threshold",
    "agenda_block_threshold",
    "risk_threshold",
    "same_work_f1",
    "fmr",
    "hnfmr",
}
THRESHOLD_SENSITIVITY_COUNT_FIELDS = {
    "same_work_f1_denominator",
    "fmr_denominator",
    "hnfmr_denominator",
    "automatic_merge_count",
    "block_count",
    "defer_count",
}
CLUSTER_METRIC_SUMMARY_REQUIRED_COLUMNS = {
    "system",
    "cluster_run_id",
    "merge_policy_id",
    "prediction_artifact_id",
    "prediction_file_sha256",
    "threshold_source",
    "work_threshold",
    "agenda_block_threshold",
    "risk_threshold",
    "cluster_assignment_file",
    "pair_to_cluster_trace_file",
    "cluster_id",
    "cluster_size",
    "accepted_link_count",
    "cannot_link_conflict_count",
    "unresolved_conflict_count",
    "cluster_contamination_rate",
    "singleton_rate",
    "merge_coverage",
    "random_seed",
    "command_line",
}
CLUSTER_METRIC_RATIO_FIELDS = {
    "work_threshold",
    "agenda_block_threshold",
    "risk_threshold",
    "cluster_contamination_rate",
    "singleton_rate",
    "merge_coverage",
}
CLUSTER_METRIC_COUNT_FIELDS = {
    "cluster_size",
    "accepted_link_count",
    "cannot_link_conflict_count",
    "unresolved_conflict_count",
}
CANNOT_LINK_AUDIT_REQUIRED_COLUMNS = {
    "system",
    "cluster_run_id",
    "merge_policy_id",
    "prediction_artifact_id",
    "prediction_file_sha256",
    "threshold_source",
    "work_threshold",
    "agenda_block_threshold",
    "risk_threshold",
    "cannot_link_rule_id",
    "conflict_type",
    "source_document_id",
    "target_document_id",
    "cannot_link_flag",
    "accepted_merge_blocked",
    "violation_detected",
    "unresolved_conflict",
    "cannot_link_coverage_rate",
    "identifier_conflict_rule",
    "pair_to_cluster_trace_file",
    "random_seed",
    "command_line",
}
CANNOT_LINK_RATIO_FIELDS = {
    "work_threshold",
    "agenda_block_threshold",
    "risk_threshold",
    "cannot_link_coverage_rate",
}
CANNOT_LINK_BOOLEAN_FIELDS = {
    "cannot_link_flag",
    "accepted_merge_blocked",
    "violation_detected",
    "unresolved_conflict",
}
JSONL_REQUIRED_FIELDS_BY_ARTIFACT = {
    "iad_risk_predictions": {
        "system",
        "pair_id",
        "source_document_id",
        "target_document_id",
        "expected_label",
        "expected_agenda_label",
        "label_strength",
        "hard_negative_level",
        "split",
        "p_same_work",
        "p_same_agenda",
        "p_agenda_non_identity",
        "p_false_merge_risk",
        "work_threshold",
        "agenda_block_threshold",
        "risk_threshold",
        "threshold_source",
        "merge_prediction",
    },
    "representation_baseline_scores": {
        "system",
        "pair_id",
        "source_document_id",
        "target_document_id",
        "expected_label",
        "expected_agenda_label",
        "label_strength",
        "hard_negative_level",
        "split",
        "score",
        "score_field",
        "threshold_value",
        "threshold_source",
        "merge_prediction",
    },
    "supervised_baseline_predictions": {
        "system",
        "pair_id",
        "source_document_id",
        "target_document_id",
        "expected_label",
        "expected_agenda_label",
        "label_strength",
        "hard_negative_level",
        "split",
        "match_probability",
        "threshold_value",
        "threshold_source",
        "merge_prediction",
    },
    "threshold_selection_logs": {
        "system",
        "threshold_name",
        "threshold_value",
        "selection_split",
        "selection_metric",
        "selection_rule",
        "applied_scope",
        "score_field",
    },
}
EXPECTED_FALSE_DATA_POLICY_FIELDS = {
    "raw_third_party_data_included",
    "model_checkpoints_included",
    "personal_or_secret_material_included",
}
REQUIRED_TRUE_DATA_POLICY_FIELDS = {
    "derived_evaluation_artifacts_included",
    "source_licenses_respected",
}
REQUIRED_TRUE_CLAIM_BOUNDARY_FIELDS = {
    "silver_labels_are_not_human_gold",
    "manual_validation_required_for_human_gold_claims",
    "same_scope_prediction_files_required_for_broad_ranking",
    "threshold_grid_required_for_threshold_stability_claims",
    "cluster_artifacts_required_for_cluster_level_quality_claims",
}
EXPECTED_FALSE_CLAIM_STATUS_FIELDS = {
    "confidence_intervals_claimed",
    "component_causality_claimed",
    "human_validation_claimed",
    "threshold_stability_claimed",
    "broad_method_ranking_claimed",
    "cluster_level_quality_claimed",
}
CLAIM_DEPENDENT_ARTIFACTS = {
    "confidence_intervals_claimed": {"bootstrap_intervals"},
    "component_causality_claimed": {"ablation_suite"},
    "human_validation_claimed": {"manual_validation_slice"},
    "threshold_stability_claimed": {"threshold_sensitivity_grid"},
    "cluster_level_quality_claimed": {"cluster_metric_summary", "cannot_link_audit"},
    "broad_method_ranking_claimed": {
        "bootstrap_intervals",
        "manual_validation_slice",
        "threshold_sensitivity_grid",
    },
}
FORBIDDEN_PATH_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "data",
    "raw",
    "raw_data",
    "outputs",
}
FORBIDDEN_NAME_FRAGMENTS = {
    ".env",
    ".secret",
    "api_key",
    "apikey",
    "credential",
    "password",
    "private_key",
    "remote_connection",
}
FORBIDDEN_MODEL_SUFFIXES = {".ckpt", ".onnx", ".pt", ".pth", ".safetensors"}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    参数:
        无。

    返回:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Validate an external IAD-Risk artifact release package.")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR), help="Artifact release directory.")
    parser.add_argument(
        "--manifest-template",
        default=str(DEFAULT_TEMPLATE_PATH),
        help="Artifact release manifest template used to check required IDs and policy fields.",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    return parser.parse_args()


def sha256_bytes(content: bytes) -> str:
    """Compute a SHA256 checksum for bytes.

    参数:
        content: File bytes.

    返回:
        str: Hexadecimal SHA256 digest.
    """
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    """Compute a SHA256 checksum for a file.

    参数:
        path: File path.

    返回:
        str: Hexadecimal SHA256 digest.
    """
    return sha256_bytes(path.read_bytes())


def load_json(path: Path, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Load a JSON object from disk with validation.

    参数:
        path: JSON file path.
        label: Human-readable file label.

    返回:
        tuple[dict[str, Any] | None, list[str]]: Parsed object and validation errors.
    """
    if not path.exists():
        return None, [f"{label} missing: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"{label} is invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{label} must contain a JSON object"]
    return data, []


def parse_checksums(text: str) -> dict[str, str]:
    """Parse a checksums.sha256 file.

    参数:
        text: Checksum file content.

    返回:
        dict[str, str]: Mapping from relative file path to SHA256 digest.

    异常:
        ValueError: Raised when a checksum line is malformed.
    """
    checksums: dict[str, str] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"malformed checksum line {line_number}: {line}")
        digest, file_name = parts
        digest = digest.strip().lower()
        file_name = file_name.strip()
        if not SHA256_PATTERN.fullmatch(digest):
            raise ValueError(f"malformed SHA256 digest on line {line_number}: {digest}")
        if file_name.startswith("/") or ".." in Path(file_name).parts:
            raise ValueError(f"unsafe checksum path on line {line_number}: {file_name}")
        if file_name in checksums:
            raise ValueError(f"duplicate checksum path on line {line_number}: {file_name}")
        checksums[file_name] = digest
    return checksums


def release_file_names(artifact_dir: Path) -> set[str]:
    """List release files relative to the release root.

    参数:
        artifact_dir: Artifact release directory.

    返回:
        set[str]: POSIX-style relative file paths.
    """
    return {
        path.relative_to(artifact_dir).as_posix()
        for path in artifact_dir.rglob("*")
        if path.is_file() and path.name != ".DS_Store"
    }


def check_required_membership(artifact_dir: Path) -> list[str]:
    """Check required files and directories in the release root.

    参数:
        artifact_dir: Artifact release directory.

    返回:
        list[str]: Error messages.
    """
    errors: list[str] = []
    if not artifact_dir.exists():
        return [f"artifact release directory does not exist: {artifact_dir}"]
    if not artifact_dir.is_dir():
        return [f"artifact release path is not a directory: {artifact_dir}"]
    for file_name in sorted(REQUIRED_TOP_LEVEL_FILES):
        if not (artifact_dir / file_name).is_file():
            errors.append(f"artifact release missing top-level file: {file_name}")
    for directory_name in sorted(REQUIRED_DIRECTORIES):
        if not (artifact_dir / directory_name).is_dir():
            errors.append(f"artifact release missing required directory: {directory_name}")
    return errors


def check_readme_text(readme_text: str) -> list[str]:
    """Check reviewer-facing release README reproducibility instructions.

    参数:
        readme_text: README.md content from the artifact release root.

    返回:
        list[str]: Error messages for missing README instructions.
    """
    normalized_text = " ".join(readme_text.split()).casefold()
    errors: list[str] = []
    for label, marker in sorted(REQUIRED_README_MARKERS.items()):
        normalized_marker = " ".join(marker.split()).casefold()
        if normalized_marker not in normalized_text:
            errors.append(f"README.md missing required release instruction `{label}`: {marker}")
    return errors


def check_forbidden_paths(file_names: set[str]) -> list[str]:
    """Check release paths for raw data, outputs, caches, secrets, and checkpoints.

    参数:
        file_names: POSIX-style relative file paths.

    返回:
        list[str]: Error messages.
    """
    errors: list[str] = []
    for file_name in sorted(file_names):
        lowered_parts = {part.lower() for part in Path(file_name).parts}
        lowered_name = file_name.lower()
        forbidden_parts = lowered_parts & FORBIDDEN_PATH_PARTS
        if forbidden_parts:
            errors.append(f"artifact release contains forbidden path part {sorted(forbidden_parts)}: {file_name}")
        for fragment in sorted(FORBIDDEN_NAME_FRAGMENTS):
            if fragment in lowered_name:
                errors.append(f"artifact release contains forbidden name fragment `{fragment}`: {file_name}")
        if Path(file_name).suffix.lower() in FORBIDDEN_MODEL_SUFFIXES:
            errors.append(f"artifact release contains a model checkpoint or binary model file: {file_name}")
    return errors


def required_ids_from_template(template: dict[str, Any] | None) -> set[str]:
    """Read required artifact IDs from the release manifest template.

    参数:
        template: Parsed release manifest template.

    返回:
        set[str]: Required artifact identifiers.
    """
    if not template:
        return set(REQUIRED_ARTIFACT_IDS)
    artifacts = template.get("required_artifacts")
    if not isinstance(artifacts, list):
        return set(REQUIRED_ARTIFACT_IDS)
    required_ids = {
        str(row.get("artifact_id"))
        for row in artifacts
        if isinstance(row, dict) and row.get("required") is True and row.get("artifact_id")
    }
    return required_ids or set(REQUIRED_ARTIFACT_IDS)


def check_data_policy(manifest: dict[str, Any]) -> list[str]:
    """Check release manifest data-policy boundaries.

    参数:
        manifest: Parsed release manifest.

    返回:
        list[str]: Error messages.
    """
    errors: list[str] = []
    data_policy = manifest.get("data_policy")
    if not isinstance(data_policy, dict):
        return ["manifest.json missing data_policy object"]
    for field in sorted(EXPECTED_FALSE_DATA_POLICY_FIELDS):
        if data_policy.get(field) is not False:
            errors.append(f"manifest.json data_policy must set {field} to false")
    for field in sorted(REQUIRED_TRUE_DATA_POLICY_FIELDS):
        if data_policy.get(field) is not True:
            errors.append(f"manifest.json data_policy must set {field} to true")
    return errors


def check_claim_boundaries(manifest: dict[str, Any]) -> list[str]:
    """Check release manifest claim-boundary flags.

    参数:
        manifest: Parsed release manifest.

    返回:
        list[str]: Error messages.
    """
    claim_boundaries = manifest.get("claim_boundaries")
    if not isinstance(claim_boundaries, dict):
        return ["manifest.json missing claim_boundaries object"]
    errors: list[str] = []
    for field in sorted(REQUIRED_TRUE_CLAIM_BOUNDARY_FIELDS):
        if claim_boundaries.get(field) is not True:
            errors.append(f"manifest.json claim boundary must be true: {field}")
    for field in sorted(EXPECTED_FALSE_CLAIM_STATUS_FIELDS):
        if claim_boundaries.get(field) not in {False, True}:
            errors.append(f"manifest.json claim boundary status must be explicit boolean: {field}")
    return errors


def check_repository_fields(manifest: dict[str, Any]) -> list[str]:
    """Check release manifest repository fields.

    参数:
        manifest: Parsed release manifest.

    返回:
        list[str]: Error messages.
    """
    repository = manifest.get("repository")
    if not isinstance(repository, dict):
        return ["manifest.json missing repository object"]
    errors: list[str] = []
    if not repository.get("url"):
        errors.append("manifest.json repository.url is empty")
    commit = str(repository.get("commit", "")).strip()
    if not commit or commit == "fill-with-release-commit":
        errors.append("manifest.json repository.commit must record the release commit")
    elif not COMMIT_PATTERN.fullmatch(commit):
        errors.append("manifest.json repository.commit must be a 7 to 40 character hexadecimal Git commit")
    if not repository.get("branch"):
        errors.append("manifest.json repository.branch is empty")
    if repository.get("source_tree_clean") is not True:
        errors.append("manifest.json repository.source_tree_clean must be true")
    return errors


def extract_readme_repository_commit(readme_text: str) -> str | None:
    """Extract the repository commit recorded in the release README.

    参数:
        readme_text: README.md content from the artifact release root.

    返回:
        str | None: Parsed Git commit, or None when no valid commit is recorded.
    """
    for line in readme_text.splitlines():
        match = re.match(r"^\s*-?\s*Repository commit\s*:\s*(?P<value>.+?)\s*$", line, re.IGNORECASE)
        if not match:
            continue
        value = match.group("value")
        commit_match = re.search(r"\b[0-9a-f]{7,40}\b", value, re.IGNORECASE)
        if commit_match:
            return commit_match.group(0)
        return None
    return None


def check_readme_repository_commit_binding(readme_text: str, manifest: dict[str, Any]) -> list[str]:
    """Check README and manifest repository-commit consistency.

    参数:
        readme_text: README.md content from the artifact release root.
        manifest: Parsed release manifest.

    返回:
        list[str]: Error messages.
    """
    readme_commit = extract_readme_repository_commit(readme_text)
    if readme_commit is None:
        return ["README.md repository commit is missing or not a 7 to 40 character hexadecimal Git commit"]
    repository = manifest.get("repository")
    if not isinstance(repository, dict):
        return []
    manifest_commit = str(repository.get("commit", "")).strip()
    if not COMMIT_PATTERN.fullmatch(manifest_commit):
        return []
    if readme_commit.lower() != manifest_commit.lower():
        return [
            "README.md repository commit does not match manifest.json repository.commit: "
            f"{readme_commit} != {manifest_commit}"
        ]
    return []


def check_open_v2_main_results_schema(csv_path: Path) -> list[str]:
    """Check the Open-v2 main result table row-level audit schema.

    参数:
        csv_path: Path to tables/open_v2_main_results.csv.

    返回:
        list[str]: Error messages for missing required columns.
    """
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as file_handle:
            reader = csv.reader(file_handle)
            header = next(reader, None)
    except OSError as exc:
        return [f"open_v2_main_results.csv cannot be read: {exc}"]
    if not header:
        return ["open_v2_main_results.csv is empty or missing a header row"]

    actual_columns = {column.strip() for column in header if column.strip()}
    missing_columns = OPEN_V2_MAIN_RESULTS_REQUIRED_COLUMNS - actual_columns
    return [
        f"open_v2_main_results.csv missing row-level audit column: {column}"
        for column in sorted(missing_columns)
    ]


def _csv_truthy(value: Any) -> bool:
    """Interpret CSV boolean-like values.

    参数:
        value: CSV cell value.

    返回:
        bool: True when the value is a recognized true value.
    """
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def check_ablation_suite_schema(csv_path: Path) -> list[str]:
    """Check ablation-suite artifact columns and protocol-variant coverage.

    参数:
        csv_path: Path to reports/iad_ablation_suite.csv.

    返回:
        list[str]: Error messages for missing protocol fields or invalid rows.
    """
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as file_handle:
            reader = csv.DictReader(file_handle)
            header = [column.strip() for column in (reader.fieldnames or []) if column and column.strip()]
            rows = list(reader)
    except OSError as exc:
        return [f"ablation_suite CSV cannot be read: {exc}"]
    if not header:
        return ["ablation_suite CSV is empty or missing a header row"]

    errors: list[str] = []
    actual_columns = set(header)
    missing_columns = ABLATION_SUITE_REQUIRED_COLUMNS - actual_columns
    for column in sorted(missing_columns):
        errors.append(f"ablation_suite CSV missing protocol audit column: {column}")
    if missing_columns:
        return errors
    if not rows:
        return ["ablation_suite CSV has no data rows"]

    protocol_rows = {str(row.get("protocol_variant", "")).strip(): row for row in rows if str(row.get("protocol_variant", "")).strip()}
    missing_variants = REQUIRED_ABLATION_PROTOCOL_VARIANTS - set(protocol_rows)
    if missing_variants:
        errors.append(f"ablation_suite CSV missing required protocol_variant rows: {sorted(missing_variants)}")
    for protocol_variant in sorted(REQUIRED_ABLATION_PROTOCOL_VARIANTS & set(protocol_rows)):
        row = protocol_rows[protocol_variant]
        if not _csv_truthy(row.get("protocol_required")):
            errors.append(f"ablation_suite protocol_variant {protocol_variant} must set protocol_required=true")
        if not _csv_truthy(row.get("requires_prediction_rows")):
            errors.append(f"ablation_suite protocol_variant {protocol_variant} must set requires_prediction_rows=true")
        if str(row.get("protocol_scope_rule", "")).strip() != "same_input_pair_scope_and_split_required":
            errors.append(
                f"ablation_suite protocol_variant {protocol_variant} must use protocol_scope_rule=same_input_pair_scope_and_split_required"
            )
    post_hoc_row = protocol_rows.get("post-hoc-threshold")
    if post_hoc_row:
        if str(post_hoc_row.get("threshold_source", "")).strip() != "post_hoc_labeled_sweep":
            errors.append("ablation_suite post-hoc-threshold row must set threshold_source=post_hoc_labeled_sweep")
        if _csv_truthy(post_hoc_row.get("accepted_for_component_causality")):
            errors.append("ablation_suite post-hoc-threshold row must not be accepted for component causality")
    for protocol_variant in sorted((REQUIRED_ABLATION_PROTOCOL_VARIANTS - {"post-hoc-threshold"}) & set(protocol_rows)):
        row = protocol_rows[protocol_variant]
        if not _csv_truthy(row.get("accepted_for_component_causality")):
            errors.append(f"ablation_suite protocol_variant {protocol_variant} must set accepted_for_component_causality=true")
        if str(row.get("threshold_source", "")).strip() != "predeclared_cli_argument":
            errors.append(f"ablation_suite protocol_variant {protocol_variant} must use predeclared_cli_argument threshold source")
    return errors


def check_manual_validation_slice_schema(csv_path: Path) -> list[str]:
    """Check manual-validation slice columns, strata coverage, and review protocol fields.

    参数:
        csv_path: Path to reports/manual_validation_slice.csv.

    返回:
        list[str]: Error messages for missing protocol evidence or invalid rows.
    """
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as file_handle:
            reader = csv.DictReader(file_handle)
            header = [column.strip() for column in (reader.fieldnames or []) if column and column.strip()]
            rows = [{str(key).strip(): value for key, value in raw_row.items() if key is not None} for raw_row in reader]
    except OSError as exc:
        return [f"manual_validation_slice CSV cannot be read: {exc}"]
    if not header:
        return ["manual_validation_slice CSV is empty or missing a header row"]

    errors: list[str] = []
    actual_columns = set(header)
    missing_columns = MANUAL_VALIDATION_SLICE_REQUIRED_COLUMNS - actual_columns
    for column in sorted(missing_columns):
        errors.append(f"manual_validation_slice CSV missing protocol audit column: {column}")
    if missing_columns:
        return errors

    row_count = len(rows)
    if row_count == 0:
        return ["manual_validation_slice CSV has no data rows"]
    if not MANUAL_VALIDATION_MIN_ROWS <= row_count <= MANUAL_VALIDATION_MAX_ROWS:
        errors.append(
            "manual_validation_slice CSV row count must be between "
            f"{MANUAL_VALIDATION_MIN_ROWS} and {MANUAL_VALIDATION_MAX_ROWS}; found {row_count}"
        )

    present_strata = {str(row.get("manual_validation_stratum", "")).strip() for row in rows}
    missing_strata = MANUAL_VALIDATION_REQUIRED_STRATA - present_strata
    if missing_strata:
        errors.append(f"manual_validation_slice CSV missing required strata: {sorted(missing_strata)}")

    reviewer_codes: set[str] = set()
    required_text_fields = [
        "pair_id",
        "source_document_id",
        "target_document_id",
        "manual_validation_stratum",
        "reviewer_1_code",
        "reviewer_2_code",
        "reviewer_1_label",
        "reviewer_2_label",
        "adjudicated_label",
        "adjudication_status",
        "adjudication_rationale",
        "pair_level_notes",
        "agreement_status",
    ]
    required_true_fields = ["reviewer_blinding_confirmed", "model_score_hidden", "merge_decision_hidden"]
    for line_number, row in enumerate(rows, start=2):
        for field in required_text_fields:
            if not str(row.get(field, "")).strip():
                errors.append(f"manual_validation_slice CSV line {line_number} missing required value: {field}")

        reviewer_1_code = str(row.get("reviewer_1_code", "")).strip()
        reviewer_2_code = str(row.get("reviewer_2_code", "")).strip()
        if reviewer_1_code:
            reviewer_codes.add(reviewer_1_code)
        if reviewer_2_code:
            reviewer_codes.add(reviewer_2_code)
        if reviewer_1_code and reviewer_2_code and reviewer_1_code == reviewer_2_code:
            errors.append(f"manual_validation_slice CSV line {line_number} must use two independent reviewer codes")

        stratum = str(row.get("manual_validation_stratum", "")).strip()
        if stratum and stratum not in MANUAL_VALIDATION_REQUIRED_STRATA:
            errors.append(f"manual_validation_slice CSV line {line_number} has unknown manual_validation_stratum: {stratum}")

        for label_field in ["reviewer_1_label", "reviewer_2_label", "adjudicated_label"]:
            label_value = str(row.get(label_field, "")).strip()
            if label_value and label_value not in MANUAL_VALIDATION_ALLOWED_LABELS:
                errors.append(f"manual_validation_slice CSV line {line_number} has unknown {label_field}: {label_value}")

        for field in required_true_fields:
            if not _csv_truthy(row.get(field)):
                errors.append(f"manual_validation_slice CSV line {line_number} must set {field}=true")

        agreement_status = str(row.get("agreement_status", "")).strip()
        if agreement_status and agreement_status not in MANUAL_VALIDATION_ALLOWED_AGREEMENT_STATUSES:
            errors.append(f"manual_validation_slice CSV line {line_number} has unknown agreement_status: {agreement_status}")
        adjudication_status = str(row.get("adjudication_status", "")).strip()
        if adjudication_status and adjudication_status not in MANUAL_VALIDATION_ALLOWED_ADJUDICATION_STATUSES:
            errors.append(f"manual_validation_slice CSV line {line_number} has unknown adjudication_status: {adjudication_status}")
        if agreement_status == "disagreement" and adjudication_status != "adjudicated":
            errors.append(f"manual_validation_slice CSV line {line_number} disagreement rows must set adjudication_status=adjudicated")
        if len(errors) >= 30:
            errors.append("manual_validation_slice CSV schema check stopped after 30 errors")
            return errors

    if len(reviewer_codes) < 2:
        errors.append("manual_validation_slice CSV must include at least two distinct reviewer codes")
    return errors


def _parse_float(value: Any) -> float | None:
    """Parse a CSV value as float.

    参数:
        value: CSV cell value.

    返回:
        float | None: Parsed float, or None when parsing fails.
    """
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _parse_int(value: Any) -> int | None:
    """Parse a CSV value as integer.

    参数:
        value: CSV cell value.

    返回:
        int | None: Parsed integer, or None when parsing fails.
    """
    try:
        text = str(value).strip()
        if not text:
            return None
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    if not parsed.is_integer():
        return None
    return int(parsed)


def check_threshold_sensitivity_grid_schema(csv_path: Path) -> list[str]:
    """Check threshold-sensitivity grid columns and row-level audit fields.

    参数:
        csv_path: Path to reports/threshold_sensitivity_grid.csv.

    返回:
        list[str]: Error messages for missing threshold-stability evidence.
    """
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as file_handle:
            reader = csv.DictReader(file_handle)
            header = [column.strip() for column in (reader.fieldnames or []) if column and column.strip()]
            rows = [{str(key).strip(): value for key, value in raw_row.items() if key is not None} for raw_row in reader]
    except OSError as exc:
        return [f"threshold_sensitivity_grid CSV cannot be read: {exc}"]
    if not header:
        return ["threshold_sensitivity_grid CSV is empty or missing a header row"]

    errors: list[str] = []
    actual_columns = set(header)
    missing_columns = THRESHOLD_SENSITIVITY_GRID_REQUIRED_COLUMNS - actual_columns
    for column in sorted(missing_columns):
        errors.append(f"threshold_sensitivity_grid CSV missing stability audit column: {column}")
    if missing_columns:
        return errors
    if len(rows) < 2:
        return ["threshold_sensitivity_grid CSV must include at least two threshold rows"]

    prediction_artifact_ids: set[str] = set()
    prediction_checksums: set[str] = set()
    selected_operating_point_count = 0
    required_text_fields = [
        "system",
        "threshold_grid_id",
        "prediction_artifact_id",
        "prediction_file_sha256",
        "threshold_range_source",
        "threshold_source",
        "selection_split",
        "evaluation_split",
        "command_line",
    ]
    for line_number, row in enumerate(rows, start=2):
        for field in required_text_fields:
            if not str(row.get(field, "")).strip():
                errors.append(f"threshold_sensitivity_grid CSV line {line_number} missing required value: {field}")

        prediction_artifact_id = str(row.get("prediction_artifact_id", "")).strip()
        if prediction_artifact_id:
            prediction_artifact_ids.add(prediction_artifact_id)
        prediction_checksum = str(row.get("prediction_file_sha256", "")).strip().lower()
        if prediction_checksum:
            prediction_checksums.add(prediction_checksum)
            if not SHA256_PATTERN.fullmatch(prediction_checksum):
                errors.append(f"threshold_sensitivity_grid CSV line {line_number} has invalid prediction_file_sha256")

        if str(row.get("threshold_range_source", "")).strip() not in {"predefined_grid", "registered_grid_config"}:
            errors.append(
                f"threshold_sensitivity_grid CSV line {line_number} must use threshold_range_source="
                "predefined_grid or registered_grid_config"
            )
        if str(row.get("selection_split", "")).strip() == str(row.get("evaluation_split", "")).strip():
            errors.append(f"threshold_sensitivity_grid CSV line {line_number} must separate selection_split and evaluation_split")

        for field in sorted(THRESHOLD_SENSITIVITY_RATIO_FIELDS):
            parsed_value = _parse_float(row.get(field))
            if parsed_value is None or not 0.0 <= parsed_value <= 1.0:
                errors.append(f"threshold_sensitivity_grid CSV line {line_number} must set {field} between 0 and 1")
        for field in sorted(THRESHOLD_SENSITIVITY_COUNT_FIELDS):
            parsed_value = _parse_int(row.get(field))
            if parsed_value is None or parsed_value < 0:
                errors.append(f"threshold_sensitivity_grid CSV line {line_number} must set {field} to a non-negative integer")
        random_seed = _parse_int(row.get("random_seed"))
        if random_seed is None:
            errors.append(f"threshold_sensitivity_grid CSV line {line_number} must set random_seed to an integer")
        if _csv_truthy(row.get("selected_operating_point")):
            selected_operating_point_count += 1
        if len(errors) >= 30:
            errors.append("threshold_sensitivity_grid CSV schema check stopped after 30 errors")
            return errors

    if not selected_operating_point_count:
        errors.append("threshold_sensitivity_grid CSV must mark at least one selected_operating_point=true row")
    if len(prediction_artifact_ids) != 1:
        errors.append("threshold_sensitivity_grid CSV must be generated from exactly one prediction_artifact_id")
    if len(prediction_checksums) != 1:
        errors.append("threshold_sensitivity_grid CSV must be generated from exactly one prediction_file_sha256")
    return errors


def _check_single_prediction_binding(rows: list[dict[str, Any]], artifact_id: str) -> list[str]:
    """Check that rows bind to exactly one prediction artifact and checksum.

    参数:
        rows: Parsed CSV rows.
        artifact_id: Artifact identifier for diagnostics.

    返回:
        list[str]: Error messages for invalid binding fields.
    """
    errors: list[str] = []
    prediction_artifact_ids = {str(row.get("prediction_artifact_id", "")).strip() for row in rows if str(row.get("prediction_artifact_id", "")).strip()}
    prediction_checksums = {str(row.get("prediction_file_sha256", "")).strip().lower() for row in rows if str(row.get("prediction_file_sha256", "")).strip()}
    for line_number, row in enumerate(rows, start=2):
        prediction_checksum = str(row.get("prediction_file_sha256", "")).strip().lower()
        if prediction_checksum and not SHA256_PATTERN.fullmatch(prediction_checksum):
            errors.append(f"{artifact_id} CSV line {line_number} has invalid prediction_file_sha256")
    if len(prediction_artifact_ids) != 1:
        errors.append(f"{artifact_id} CSV must be generated from exactly one prediction_artifact_id")
    if len(prediction_checksums) != 1:
        errors.append(f"{artifact_id} CSV must be generated from exactly one prediction_file_sha256")
    return errors


def check_cluster_metric_summary_schema(csv_path: Path) -> list[str]:
    """Check cluster-level metric artifact columns and row-level audit fields.

    参数:
        csv_path: Path to reports/cluster_metric_summary.csv.

    返回:
        list[str]: Error messages for missing cluster-level audit evidence.
    """
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as file_handle:
            reader = csv.DictReader(file_handle)
            header = [column.strip() for column in (reader.fieldnames or []) if column and column.strip()]
            rows = [{str(key).strip(): value for key, value in raw_row.items() if key is not None} for raw_row in reader]
    except OSError as exc:
        return [f"cluster_metric_summary CSV cannot be read: {exc}"]
    if not header:
        return ["cluster_metric_summary CSV is empty or missing a header row"]

    errors: list[str] = []
    actual_columns = set(header)
    missing_columns = CLUSTER_METRIC_SUMMARY_REQUIRED_COLUMNS - actual_columns
    for column in sorted(missing_columns):
        errors.append(f"cluster_metric_summary CSV missing cluster audit column: {column}")
    if missing_columns:
        return errors
    if not rows:
        return ["cluster_metric_summary CSV has no data rows"]

    required_text_fields = [
        "system",
        "cluster_run_id",
        "merge_policy_id",
        "prediction_artifact_id",
        "prediction_file_sha256",
        "threshold_source",
        "cluster_assignment_file",
        "pair_to_cluster_trace_file",
        "cluster_id",
        "command_line",
    ]
    cluster_run_ids: set[str] = set()
    merge_policy_ids: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        for field in required_text_fields:
            if not str(row.get(field, "")).strip():
                errors.append(f"cluster_metric_summary CSV line {line_number} missing required value: {field}")
        cluster_run_id = str(row.get("cluster_run_id", "")).strip()
        merge_policy_id = str(row.get("merge_policy_id", "")).strip()
        if cluster_run_id:
            cluster_run_ids.add(cluster_run_id)
        if merge_policy_id:
            merge_policy_ids.add(merge_policy_id)
        for field in sorted(CLUSTER_METRIC_RATIO_FIELDS):
            parsed_value = _parse_float(row.get(field))
            if parsed_value is None or not 0.0 <= parsed_value <= 1.0:
                errors.append(f"cluster_metric_summary CSV line {line_number} must set {field} between 0 and 1")
        for field in sorted(CLUSTER_METRIC_COUNT_FIELDS):
            parsed_value = _parse_int(row.get(field))
            minimum_value = 1 if field == "cluster_size" else 0
            if parsed_value is None or parsed_value < minimum_value:
                errors.append(f"cluster_metric_summary CSV line {line_number} must set {field} to an integer >= {minimum_value}")
        random_seed = _parse_int(row.get("random_seed"))
        if random_seed is None:
            errors.append(f"cluster_metric_summary CSV line {line_number} must set random_seed to an integer")
        if len(errors) >= 30:
            errors.append("cluster_metric_summary CSV schema check stopped after 30 errors")
            return errors
    if len(cluster_run_ids) != 1:
        errors.append("cluster_metric_summary CSV must describe exactly one cluster_run_id")
    if len(merge_policy_ids) != 1:
        errors.append("cluster_metric_summary CSV must describe exactly one merge_policy_id")
    errors.extend(_check_single_prediction_binding(rows, "cluster_metric_summary"))
    return errors


def check_cannot_link_audit_schema(csv_path: Path) -> list[str]:
    """Check cannot-link audit artifact columns and row-level evidence fields.

    参数:
        csv_path: Path to reports/cannot_link_audit.csv.

    返回:
        list[str]: Error messages for missing cannot-link audit evidence.
    """
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as file_handle:
            reader = csv.DictReader(file_handle)
            header = [column.strip() for column in (reader.fieldnames or []) if column and column.strip()]
            rows = [{str(key).strip(): value for key, value in raw_row.items() if key is not None} for raw_row in reader]
    except OSError as exc:
        return [f"cannot_link_audit CSV cannot be read: {exc}"]
    if not header:
        return ["cannot_link_audit CSV is empty or missing a header row"]

    errors: list[str] = []
    actual_columns = set(header)
    missing_columns = CANNOT_LINK_AUDIT_REQUIRED_COLUMNS - actual_columns
    for column in sorted(missing_columns):
        errors.append(f"cannot_link_audit CSV missing cannot-link audit column: {column}")
    if missing_columns:
        return errors
    if not rows:
        return ["cannot_link_audit CSV has no data rows"]

    required_text_fields = [
        "system",
        "cluster_run_id",
        "merge_policy_id",
        "prediction_artifact_id",
        "prediction_file_sha256",
        "threshold_source",
        "cannot_link_rule_id",
        "conflict_type",
        "source_document_id",
        "target_document_id",
        "identifier_conflict_rule",
        "pair_to_cluster_trace_file",
        "command_line",
    ]
    cluster_run_ids: set[str] = set()
    merge_policy_ids: set[str] = set()
    conflict_types: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        for field in required_text_fields:
            if not str(row.get(field, "")).strip():
                errors.append(f"cannot_link_audit CSV line {line_number} missing required value: {field}")
        cluster_run_id = str(row.get("cluster_run_id", "")).strip()
        merge_policy_id = str(row.get("merge_policy_id", "")).strip()
        conflict_type = str(row.get("conflict_type", "")).strip()
        if cluster_run_id:
            cluster_run_ids.add(cluster_run_id)
        if merge_policy_id:
            merge_policy_ids.add(merge_policy_id)
        if conflict_type:
            conflict_types.add(conflict_type)
        for field in sorted(CANNOT_LINK_RATIO_FIELDS):
            parsed_value = _parse_float(row.get(field))
            if parsed_value is None or not 0.0 <= parsed_value <= 1.0:
                errors.append(f"cannot_link_audit CSV line {line_number} must set {field} between 0 and 1")
        for field in sorted(CANNOT_LINK_BOOLEAN_FIELDS):
            value = str(row.get(field, "")).strip().casefold()
            if value not in {"0", "1", "false", "true", "no", "yes", "n", "y"}:
                errors.append(f"cannot_link_audit CSV line {line_number} must set {field} to a boolean value")
        random_seed = _parse_int(row.get("random_seed"))
        if random_seed is None:
            errors.append(f"cannot_link_audit CSV line {line_number} must set random_seed to an integer")
        if len(errors) >= 30:
            errors.append("cannot_link_audit CSV schema check stopped after 30 errors")
            return errors
    if len(cluster_run_ids) != 1:
        errors.append("cannot_link_audit CSV must describe exactly one cluster_run_id")
    if len(merge_policy_ids) != 1:
        errors.append("cannot_link_audit CSV must describe exactly one merge_policy_id")
    if not conflict_types:
        errors.append("cannot_link_audit CSV must include at least one conflict_type")
    errors.extend(_check_single_prediction_binding(rows, "cannot_link_audit"))
    return errors


def _missing_jsonl_required_fields(row: dict[str, Any], required_fields: set[str]) -> list[str]:
    """Return required JSONL fields that are absent or empty.

    参数:
        row: Parsed JSONL row.
        required_fields: Fields required by the artifact schema.

    返回:
        list[str]: Missing or empty field names.
    """
    missing_fields: list[str] = []
    for field in sorted(required_fields):
        value = row.get(field)
        if field not in row or value is None or (isinstance(value, str) and not value.strip()):
            missing_fields.append(field)
    return missing_fields


def check_jsonl_required_fields(jsonl_path: Path, artifact_id: str, required_fields: set[str]) -> list[str]:
    """Check row-level required fields in a JSONL artifact.

    参数:
        jsonl_path: JSONL artifact path.
        artifact_id: Manifest artifact identifier.
        required_fields: Required row fields.

    返回:
        list[str]: Error messages for invalid JSONL rows.
    """
    errors: list[str] = []
    row_count = 0
    try:
        with jsonl_path.open("r", encoding="utf-8") as file_handle:
            for line_number, line in enumerate(file_handle, start=1):
                if not line.strip():
                    continue
                row_count += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"{artifact_id} JSONL line {line_number} is invalid JSON: {exc}")
                    continue
                if not isinstance(row, dict):
                    errors.append(f"{artifact_id} JSONL line {line_number} must contain a JSON object")
                    continue
                missing_fields = _missing_jsonl_required_fields(row, required_fields)
                for field in missing_fields:
                    errors.append(f"{artifact_id} JSONL line {line_number} missing row-level audit field: {field}")
                if len(errors) >= 20:
                    errors.append(f"{artifact_id} JSONL schema check stopped after 20 errors")
                    return errors
    except OSError as exc:
        return [f"{artifact_id} JSONL cannot be read: {exc}"]
    if row_count == 0:
        errors.append(f"{artifact_id} JSONL is empty")
    return errors


def check_manifest_artifacts(
    manifest: dict[str, Any],
    template: dict[str, Any] | None,
    artifact_dir: Path,
    checksums: dict[str, str],
) -> list[str]:
    """Check required artifact rows, files, and per-artifact checksums.

    参数:
        manifest: Parsed release manifest.
        template: Parsed release manifest template.
        artifact_dir: Artifact release directory.
        checksums: Parsed checksums mapping.

    返回:
        list[str]: Error messages.
    """
    artifacts = manifest.get("required_artifacts")
    if not isinstance(artifacts, list):
        return ["manifest.json missing required_artifacts list"]
    errors: list[str] = []
    required_ids = required_ids_from_template(template)
    artifact_rows = {str(row.get("artifact_id")): row for row in artifacts if isinstance(row, dict)}
    missing_ids = required_ids - set(artifact_rows)
    if missing_ids:
        errors.append(f"manifest.json missing required artifact IDs: {sorted(missing_ids)}")

    def check_artifact_payload(artifact_id: str, row: dict[str, Any], context: str, require_required_flag: bool) -> None:
        """Validate a manifest artifact row in the surrounding check context.

        参数:
            artifact_id: Artifact identifier used in the manifest row.
            row: Parsed artifact row from manifest.json.
            context: Diagnostic context for error messages.
            require_required_flag: Whether the row must set required=true.

        返回:
            无。
        """
        if require_required_flag and row.get("required") is not True:
            errors.append(f"manifest.json {context} row must mark required=true: {artifact_id}")
        location = str(row.get("expected_location", "")).strip()
        if not location:
            errors.append(f"manifest.json {context} row missing expected_location: {artifact_id}")
            return
        location_path = Path(location)
        if location_path.is_absolute() or ".." in location_path.parts:
            errors.append(f"manifest.json {context} row has unsafe location: {artifact_id} -> {location}")
            return
        if not (artifact_dir / location).is_file():
            errors.append(f"{context} file missing: {location}")
            return
        checksum_value = str(row.get("sha256", "")).strip().lower()
        if not SHA256_PATTERN.fullmatch(checksum_value):
            errors.append(f"manifest.json {context} row missing valid sha256: {artifact_id}")
            return
        checksum_file_value = checksums.get(location)
        if checksum_file_value is None:
            errors.append(f"checksums.sha256 missing {context} entry: {location}")
            return
        if checksum_file_value != checksum_value:
            errors.append(f"manifest.json sha256 does not match checksums.sha256 for {location}")

    for artifact_id in sorted(required_ids & set(artifact_rows)):
        check_artifact_payload(artifact_id, artifact_rows[artifact_id], "required_artifacts", True)

    open_v2_row = artifact_rows.get("open_v2_main_results")
    if isinstance(open_v2_row, dict):
        open_v2_location = str(open_v2_row.get("expected_location", "")).strip()
        open_v2_location_path = Path(open_v2_location)
        if (
            open_v2_location
            and not open_v2_location_path.is_absolute()
            and ".." not in open_v2_location_path.parts
            and (artifact_dir / open_v2_location).is_file()
        ):
            errors.extend(check_open_v2_main_results_schema(artifact_dir / open_v2_location))

    for artifact_id, required_fields in sorted(JSONL_REQUIRED_FIELDS_BY_ARTIFACT.items()):
        artifact_row = artifact_rows.get(artifact_id)
        if not isinstance(artifact_row, dict):
            continue
        artifact_location = str(artifact_row.get("expected_location", "")).strip()
        artifact_location_path = Path(artifact_location)
        if (
            artifact_location
            and not artifact_location_path.is_absolute()
            and ".." not in artifact_location_path.parts
            and (artifact_dir / artifact_location).is_file()
        ):
            errors.extend(check_jsonl_required_fields(artifact_dir / artifact_location, artifact_id, required_fields))

    ablation_row = artifact_rows.get("ablation_suite")
    if isinstance(ablation_row, dict):
        ablation_location = str(ablation_row.get("expected_location", "")).strip()
        ablation_location_path = Path(ablation_location)
        if (
            ablation_location
            and not ablation_location_path.is_absolute()
            and ".." not in ablation_location_path.parts
            and (artifact_dir / ablation_location).is_file()
        ):
            errors.extend(check_ablation_suite_schema(artifact_dir / ablation_location))

    manual_validation_row = artifact_rows.get("manual_validation_slice")
    if isinstance(manual_validation_row, dict):
        manual_validation_location = str(manual_validation_row.get("expected_location", "")).strip()
        manual_validation_location_path = Path(manual_validation_location)
        if (
            manual_validation_location
            and not manual_validation_location_path.is_absolute()
            and ".." not in manual_validation_location_path.parts
            and (artifact_dir / manual_validation_location).is_file()
        ):
            errors.extend(check_manual_validation_slice_schema(artifact_dir / manual_validation_location))

    threshold_grid_row = artifact_rows.get("threshold_sensitivity_grid")
    if isinstance(threshold_grid_row, dict):
        threshold_grid_location = str(threshold_grid_row.get("expected_location", "")).strip()
        threshold_grid_location_path = Path(threshold_grid_location)
        if (
            threshold_grid_location
            and not threshold_grid_location_path.is_absolute()
            and ".." not in threshold_grid_location_path.parts
            and (artifact_dir / threshold_grid_location).is_file()
        ):
            errors.extend(check_threshold_sensitivity_grid_schema(artifact_dir / threshold_grid_location))

    cluster_metric_row = artifact_rows.get("cluster_metric_summary")
    if isinstance(cluster_metric_row, dict):
        cluster_metric_location = str(cluster_metric_row.get("expected_location", "")).strip()
        cluster_metric_location_path = Path(cluster_metric_location)
        if (
            cluster_metric_location
            and not cluster_metric_location_path.is_absolute()
            and ".." not in cluster_metric_location_path.parts
            and (artifact_dir / cluster_metric_location).is_file()
        ):
            errors.extend(check_cluster_metric_summary_schema(artifact_dir / cluster_metric_location))

    cannot_link_row = artifact_rows.get("cannot_link_audit")
    if isinstance(cannot_link_row, dict):
        cannot_link_location = str(cannot_link_row.get("expected_location", "")).strip()
        cannot_link_location_path = Path(cannot_link_location)
        if (
            cannot_link_location
            and not cannot_link_location_path.is_absolute()
            and ".." not in cannot_link_location_path.parts
            and (artifact_dir / cannot_link_location).is_file()
        ):
            errors.extend(check_cannot_link_audit_schema(artifact_dir / cannot_link_location))

    claim_boundaries = manifest.get("claim_boundaries")
    if isinstance(claim_boundaries, dict):
        for claim_field, artifact_ids in sorted(CLAIM_DEPENDENT_ARTIFACTS.items()):
            if claim_boundaries.get(claim_field) is not True:
                continue
            for artifact_id in sorted(artifact_ids):
                row = artifact_rows.get(artifact_id)
                if row is None:
                    errors.append(
                        "manifest.json conditional claim "
                        f"{claim_field} requires artifact ID: {artifact_id}"
                    )
                    continue
                check_artifact_payload(
                    artifact_id,
                    row,
                    f"conditional claim {claim_field}",
                    True,
                )
    return errors


def check_manifest_structure(
    manifest: dict[str, Any],
    template: dict[str, Any] | None,
    artifact_dir: Path,
    checksums: dict[str, str],
) -> list[str]:
    """Check release manifest structure and policy content.

    参数:
        manifest: Parsed release manifest.
        template: Parsed release manifest template.
        artifact_dir: Artifact release directory.
        checksums: Parsed checksums mapping.

    返回:
        list[str]: Error messages.
    """
    errors: list[str] = []
    if manifest.get("package_type") != "result_artifact_release":
        errors.append("manifest.json package_type must be result_artifact_release")
    release_status = str(manifest.get("release_status", "")).strip()
    if release_status in FORBIDDEN_RELEASE_STATUSES:
        errors.append(f"manifest.json release_status must not remain {release_status}")
    if not manifest.get("package_name"):
        errors.append("manifest.json package_name is empty")
    required_directories = set(manifest.get("required_directories", []))
    missing_directories = REQUIRED_DIRECTORIES - required_directories
    if missing_directories:
        errors.append(f"manifest.json missing required_directories entries: {sorted(missing_directories)}")
    required_top_level_files = set(manifest.get("required_top_level_files", []))
    missing_top_level_files = REQUIRED_TOP_LEVEL_FILES - required_top_level_files
    if missing_top_level_files:
        errors.append(f"manifest.json missing required_top_level_files entries: {sorted(missing_top_level_files)}")
    errors.extend(check_repository_fields(manifest))
    errors.extend(check_data_policy(manifest))
    errors.extend(check_claim_boundaries(manifest))
    errors.extend(check_manifest_artifacts(manifest, template, artifact_dir, checksums))
    validation_commands = manifest.get("minimum_validation_commands")
    if not isinstance(validation_commands, list):
        errors.append("manifest.json missing minimum_validation_commands list")
    else:
        validation_text = "\n".join(str(command) for command in validation_commands)
        for command in [
            "sha256sum -c checksums.sha256",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir",
            "python manuscript/scripts/validate_manuscript.py --strict-latex",
            "python manuscript/scripts/verify_fixture_rebuild.py",
            "python scripts/check_public_release.py",
        ]:
            if command not in validation_text:
                errors.append(f"manifest.json missing validation command: {command}")
    return errors


def check_checksums(artifact_dir: Path, file_names: set[str]) -> tuple[dict[str, str], list[str]]:
    """Check checksums.sha256 coverage and digest correctness.

    参数:
        artifact_dir: Artifact release directory.
        file_names: POSIX-style relative file paths.

    返回:
        tuple[dict[str, str], list[str]]: Parsed checksums and error messages.
    """
    checksum_path = artifact_dir / "checksums.sha256"
    if not checksum_path.exists():
        return {}, ["artifact release missing checksums.sha256"]
    try:
        checksums = parse_checksums(checksum_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return {}, [f"checksums.sha256 is invalid: {exc}"]

    errors: list[str] = []
    expected_file_names = file_names - {"checksums.sha256"}
    if "checksums.sha256" in checksums:
        errors.append("checksums.sha256 must not include itself")
    missing_entries = expected_file_names - set(checksums)
    extra_entries = set(checksums) - expected_file_names
    if missing_entries:
        errors.append(f"checksums.sha256 missing entries: {sorted(missing_entries)}")
    if extra_entries:
        errors.append(f"checksums.sha256 has unexpected entries: {sorted(extra_entries)}")
    for file_name in sorted(expected_file_names & set(checksums)):
        actual_digest = sha256_file(artifact_dir / file_name)
        if checksums[file_name] != actual_digest:
            errors.append(f"checksum mismatch for {file_name}")
    return checksums, errors


def validate_artifact_release(artifact_dir: Path, template_path: Path) -> list[str]:
    """Validate a result artifact release directory.

    参数:
        artifact_dir: Artifact release directory.
        template_path: Artifact release manifest template path.

    返回:
        list[str]: Error messages. An empty list means validation passed.
    """
    errors = check_required_membership(artifact_dir)
    if errors:
        return errors

    readme_text = ""
    try:
        readme_text = (artifact_dir / "README.md").read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"README.md cannot be read: {exc}")
    else:
        errors.extend(check_readme_text(readme_text))

    file_names = release_file_names(artifact_dir)
    errors.extend(check_forbidden_paths(file_names))
    checksums, checksum_errors = check_checksums(artifact_dir, file_names)
    errors.extend(checksum_errors)
    manifest, manifest_errors = load_json(artifact_dir / "manifest.json", "manifest.json")
    errors.extend(manifest_errors)
    template, template_errors = load_json(template_path, "artifact release manifest template")
    errors.extend(template_errors)
    if manifest is not None:
        errors.extend(check_manifest_structure(manifest, template, artifact_dir, checksums))
        if readme_text:
            errors.extend(check_readme_repository_commit_binding(readme_text, manifest))
    return errors


def main() -> int:
    """Run artifact release validation.

    参数:
        无。

    返回:
        int: Process exit code.
    """
    args = parse_arguments()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO), format="%(levelname)s %(message)s")
    artifact_dir = Path(args.artifact_dir).resolve()
    template_path = Path(args.manifest_template).resolve()
    try:
        errors = validate_artifact_release(artifact_dir, template_path)
    except OSError as exc:
        LOGGER.error("artifact release validation failed to read files: %s", exc)
        return 1
    if errors:
        for error in errors:
            LOGGER.error(error)
        return 1
    LOGGER.info("Artifact release validation passed: %s", artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
