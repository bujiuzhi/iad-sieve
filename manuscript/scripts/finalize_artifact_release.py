"""Finalize an external artifact release after result files are copied.

The script updates manifest artifact checksums, refreshes checksums.sha256, and
optionally runs the artifact release validator. It does not create or infer
result files; missing required artifacts remain a hard error.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import logging
import re
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
MANUSCRIPT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = MANUSCRIPT_ROOT / "build" / "artifact_release"
DEFAULT_TEMPLATE_PATH = MANUSCRIPT_ROOT / "artifact_release_manifest.template.json"
DEFAULT_RELEASE_STATUS = "release_candidate"
FORBIDDEN_RELEASE_STATUSES = {"template_pending_external_artifact", "skeleton_pending_artifacts"}
CHECKSUM_FILE_NAME = "checksums.sha256"
ARTIFACT_SHA256_PLACEHOLDERS = {"", "fill-after-artifact-export", "fill-with-artifact-sha256"}
REQUIRED_VALIDATION_COMMANDS = [
    "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts",
    "python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release",
    "sha256sum -c checksums.sha256",
    "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
    "python manuscript/scripts/validate_manuscript.py --strict-latex",
    "python manuscript/scripts/verify_fixture_rebuild.py",
    "python scripts/check_public_release.py",
]


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    参数:
        无。

    返回:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Finalize an external IAD-Risk artifact release package.")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR), help="Artifact release directory.")
    parser.add_argument(
        "--manifest-template",
        default=str(DEFAULT_TEMPLATE_PATH),
        help="Artifact release manifest template used for final validation.",
    )
    parser.add_argument("--release-status", default=DEFAULT_RELEASE_STATUS, help="Final release status to write.")
    parser.add_argument("--skip-validate", action="store_true", help="Skip validate_artifact_release.py after writing.")
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    """Compute a SHA256 checksum for a file.

    参数:
        path: File path.

    返回:
        str: Hexadecimal SHA256 digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk.

    参数:
        path: JSON file path.

    返回:
        dict[str, Any]: Parsed JSON object.

    异常:
        ValueError: Raised when the JSON root is not an object.
        json.JSONDecodeError: Raised when JSON parsing fails.
        OSError: Raised when the file cannot be read.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON object with stable formatting.

    参数:
        path: Destination path.
        payload: JSON object to write.

    返回:
        无。

    异常:
        OSError: Raised when the file cannot be written.
    """
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def validate_release_status(release_status: str) -> str:
    """Validate and normalize the final release status.

    参数:
        release_status: Release status requested by the caller.

    返回:
        str: Normalized release status.

    异常:
        ValueError: Raised when the status is empty or still a template/skeleton status.
    """
    status = release_status.strip()
    if not status:
        raise ValueError("release status must not be empty")
    if status in FORBIDDEN_RELEASE_STATUSES:
        raise ValueError(f"release status must not remain {status}")
    return status


def validate_relative_location(location: str, artifact_id: str) -> str:
    """Validate an artifact location from manifest.json.

    参数:
        location: Relative artifact path string.
        artifact_id: Artifact identifier used for diagnostics.

    返回:
        str: Safe POSIX-style relative path.

    异常:
        ValueError: Raised when the location is empty, absolute, or parent-relative.
    """
    normalized_location = location.strip()
    location_path = Path(normalized_location)
    if not normalized_location or location_path.is_absolute() or ".." in location_path.parts:
        raise ValueError(f"unsafe artifact location for {artifact_id}: {location}")
    return normalized_location


def update_artifact_checksums(manifest: dict[str, Any], artifact_dir: Path) -> None:
    """Update manifest artifact rows with file availability and SHA256 values.

    参数:
        manifest: Parsed release manifest.
        artifact_dir: Artifact release directory.

    返回:
        无。

    异常:
        ValueError: Raised when required artifacts are missing or rows are malformed.
    """
    artifacts = manifest.get("required_artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("manifest.json missing required_artifacts list")
    missing_required_artifacts: list[str] = []
    for row in artifacts:
        if not isinstance(row, dict):
            raise ValueError("manifest required_artifacts rows must be objects")
        artifact_id = str(row.get("artifact_id", "")).strip()
        location = validate_relative_location(str(row.get("expected_location", "")), artifact_id)
        artifact_path = artifact_dir / location
        if artifact_path.is_file():
            row["sha256"] = sha256_file(artifact_path)
            row["availability_status"] = "included"
            continue
        if row.get("required") is True:
            missing_required_artifacts.append(f"{artifact_id} -> {location}")
            continue
        if str(row.get("sha256", "")).strip() in ARTIFACT_SHA256_PLACEHOLDERS:
            row.pop("sha256", None)
        row["availability_status"] = "not_included_not_claimed"
    if missing_required_artifacts:
        missing_text = ", ".join(sorted(missing_required_artifacts))
        raise ValueError(f"missing required artifact files: {missing_text}")


def mark_manifest_finalized(manifest: dict[str, Any], release_status: str) -> None:
    """Update manifest-level finalization metadata.

    参数:
        manifest: Parsed release manifest.
        release_status: Validated release status.

    返回:
        无。
    """
    manifest["release_status"] = release_status
    generated_from_template = manifest.get("generated_from_template")
    if isinstance(generated_from_template, dict):
        generated_from_template["artifact_files_pending"] = False
        generated_from_template["finalized_by"] = "finalize_artifact_release.py"
        generated_from_template[
            "final_validation_required"
        ] = "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release"


def ensure_minimum_validation_commands(manifest: dict[str, Any]) -> None:
    """Ensure manifest validation commands include the current release workflow.

    参数:
        manifest: Parsed release manifest.

    返回:
        无。
    """
    existing_commands = manifest.get("minimum_validation_commands")
    if not isinstance(existing_commands, list):
        existing_commands = []
    existing_text = "\n".join(str(command) for command in existing_commands)
    commands = [str(command) for command in existing_commands]
    for required_command in REQUIRED_VALIDATION_COMMANDS:
        if required_command not in existing_text:
            commands.append(required_command)
    manifest["minimum_validation_commands"] = commands


def update_readme_repository_commit(artifact_dir: Path, manifest: dict[str, Any]) -> None:
    """Synchronize README repository commit with the release manifest.

    参数:
        artifact_dir: Artifact release directory.
        manifest: Parsed and finalized release manifest.

    返回:
        无。

    异常:
        FileNotFoundError: Raised when README.md is missing.
        ValueError: Raised when manifest repository.commit is not usable.
        OSError: Raised when README.md cannot be read or written.
    """
    repository = manifest.get("repository")
    if not isinstance(repository, dict):
        raise ValueError("manifest.json missing repository object")
    repository_commit = str(repository.get("commit", "")).strip()
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", repository_commit):
        raise ValueError("manifest.json repository.commit must be a 7 to 40 character hexadecimal Git commit")
    readme_path = artifact_dir / "README.md"
    if not readme_path.is_file():
        raise FileNotFoundError(f"artifact release README missing: {readme_path}")
    readme_lines = readme_path.read_text(encoding="utf-8").splitlines()
    marker_pattern = re.compile(r"^(?P<prefix>\s*-?\s*Repository commit\s*:\s*)(?P<value>.*)$", re.IGNORECASE)
    updated = False
    for index, line in enumerate(readme_lines):
        match = marker_pattern.match(line)
        if not match:
            continue
        readme_lines[index] = f"{match.group('prefix')}{repository_commit}"
        updated = True
        break
    if not updated:
        readme_lines.extend(["", f"Repository commit: {repository_commit}"])
    readme_path.write_text("\n".join(readme_lines) + "\n", encoding="utf-8")


def write_checksums(artifact_dir: Path) -> Path:
    """Refresh checksums.sha256 for every release file except itself.

    参数:
        artifact_dir: Artifact release directory.

    返回:
        Path: Written checksum file path.

    异常:
        OSError: Raised when files cannot be read or written.
    """
    checksum_path = artifact_dir / CHECKSUM_FILE_NAME
    checksum_lines = []
    for path in sorted(artifact_dir.rglob("*")):
        if not path.is_file() or path.name in {CHECKSUM_FILE_NAME, ".DS_Store"}:
            continue
        relative_path = path.relative_to(artifact_dir).as_posix()
        checksum_lines.append(f"{sha256_file(path)}  {relative_path}")
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    return checksum_path


def load_artifact_validator():
    """Load the sibling artifact release validator module.

    参数:
        无。

    返回:
        module: Loaded validate_artifact_release module.

    异常:
        ImportError: Raised when the validator script cannot be loaded.
    """
    validator_path = Path(__file__).resolve().with_name("validate_artifact_release.py")
    spec = importlib.util.spec_from_file_location("validate_artifact_release", validator_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load artifact release validator: {validator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_artifact_validator(artifact_dir: Path, manifest_template_path: Path) -> None:
    """Run the artifact release validator and raise on validation errors.

    参数:
        artifact_dir: Artifact release directory.
        manifest_template_path: Manifest template path.

    返回:
        无。

    异常:
        ValueError: Raised when the validator reports errors.
        ImportError: Raised when the validator cannot be loaded.
    """
    validator = load_artifact_validator()
    errors = validator.validate_artifact_release(artifact_dir, manifest_template_path)
    if errors:
        raise ValueError("artifact release validation failed: " + "; ".join(errors))


def finalize_artifact_release(
    artifact_dir: Path,
    manifest_template_path: Path,
    release_status: str = DEFAULT_RELEASE_STATUS,
    validate: bool = True,
) -> Path:
    """Finalize a populated external artifact release directory.

    参数:
        artifact_dir: Artifact release directory.
        manifest_template_path: Manifest template path for optional validation.
        release_status: Final release status to write.
        validate: Whether to run validate_artifact_release.py after writing.

    返回:
        Path: Updated manifest path.

    异常:
        FileNotFoundError: Raised when manifest.json is missing.
        ValueError: Raised when required artifacts are missing or validation fails.
        OSError: Raised when files cannot be read or written.
    """
    if not artifact_dir.is_dir():
        raise FileNotFoundError(f"artifact release directory missing: {artifact_dir}")
    manifest_path = artifact_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"artifact release manifest missing: {manifest_path}")
    normalized_status = validate_release_status(release_status)
    manifest = load_json(manifest_path)
    update_artifact_checksums(manifest, artifact_dir)
    mark_manifest_finalized(manifest, normalized_status)
    ensure_minimum_validation_commands(manifest)
    write_json(manifest_path, manifest)
    update_readme_repository_commit(artifact_dir, manifest)
    write_checksums(artifact_dir)
    if validate:
        run_artifact_validator(artifact_dir, manifest_template_path)
    return manifest_path


def main() -> int:
    """Run artifact release finalization.

    参数:
        无。

    返回:
        int: Process exit code.
    """
    args = parse_arguments()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO), format="%(levelname)s %(message)s")
    try:
        manifest_path = finalize_artifact_release(
            artifact_dir=Path(args.artifact_dir).resolve(),
            manifest_template_path=Path(args.manifest_template).resolve(),
            release_status=args.release_status,
            validate=not args.skip_validate,
        )
    except (FileNotFoundError, ImportError, OSError, ValueError, json.JSONDecodeError) as exc:
        LOGGER.error("artifact release finalization failed: %s", exc)
        return 1
    LOGGER.info("Artifact release finalized: %s", manifest_path.parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
