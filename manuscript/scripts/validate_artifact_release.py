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
