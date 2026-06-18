"""Populate an artifact release scaffold from completed experiment outputs.

The script copies required and available optional result artifacts from a
source directory into an external release scaffold, writes a population log,
and can call finalize_artifact_release.py to refresh manifest and checksum
metadata.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import shutil
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
MANUSCRIPT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = MANUSCRIPT_ROOT / "build" / "artifact_release"
DEFAULT_TEMPLATE_PATH = MANUSCRIPT_ROOT / "artifact_release_manifest.template.json"
POPULATION_LOG_PATH = "logs/artifact_population_log.jsonl"


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    参数:
        无。

    返回:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Populate an IAD-Risk artifact release from experiment outputs.")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR), help="Artifact release scaffold directory.")
    parser.add_argument("--source-dir", required=True, help="Directory containing generated artifact files.")
    parser.add_argument(
        "--manifest-template",
        default=str(DEFAULT_TEMPLATE_PATH),
        help="Artifact release manifest template used for final validation.",
    )
    parser.add_argument(
        "--mapping",
        default=None,
        help="Optional JSON mapping from artifact_id to source-relative path.",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Check required source artifact files without copying, logging, or finalizing.",
    )
    parser.add_argument("--release-status", default="release_candidate", help="Release status passed to finalizer.")
    parser.add_argument("--skip-finalize", action="store_true", help="Copy files without finalizing manifest/checksums.")
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    return parser.parse_args()


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


def validate_relative_path(relative_path: str, label: str) -> str:
    """Validate a source or destination relative path.

    参数:
        relative_path: POSIX-style relative path string.
        label: Diagnostic label for errors.

    返回:
        str: Normalized relative path string.

    异常:
        ValueError: Raised when the path is empty, absolute, or parent-relative.
    """
    normalized_path = relative_path.strip()
    path = Path(normalized_path)
    if not normalized_path or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe relative path for {label}: {relative_path}")
    return normalized_path


def load_mapping(mapping_path: Path | None) -> dict[str, str]:
    """Load an optional artifact source-path mapping.

    参数:
        mapping_path: Optional JSON mapping path.

    返回:
        dict[str, str]: Mapping from artifact ID to source-relative path.

    异常:
        ValueError: Raised when the mapping shape or paths are invalid.
        OSError: Raised when the mapping file cannot be read.
    """
    if mapping_path is None:
        return {}
    raw_mapping = load_json(mapping_path)
    mapping: dict[str, str] = {}
    for artifact_id, value in raw_mapping.items():
        if isinstance(value, str):
            source_path = value
        elif isinstance(value, dict):
            source_path = str(value.get("source", ""))
        else:
            raise ValueError(f"artifact mapping value must be a string or object: {artifact_id}")
        mapping[str(artifact_id)] = validate_relative_path(source_path, f"mapping {artifact_id}")
    return mapping


def resolve_inside_root(root_dir: Path, relative_path: str, label: str) -> Path:
    """Resolve a relative path and ensure it stays inside a root directory.

    参数:
        root_dir: Root directory.
        relative_path: Safe relative path string.
        label: Diagnostic label for errors.

    返回:
        Path: Resolved path.

    异常:
        ValueError: Raised when resolution escapes the root directory.
    """
    root = root_dir.resolve()
    resolved_path = (root / relative_path).resolve()
    try:
        resolved_path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes root directory: {relative_path}") from exc
    return resolved_path


def build_copy_plan(artifact_dir: Path, source_dir: Path, mapping: dict[str, str]) -> list[dict[str, str]]:
    """Build a copy plan from manifest artifact rows.

    参数:
        artifact_dir: Artifact release directory.
        source_dir: Source artifact directory.
        mapping: Artifact ID to source-relative path mapping.

    返回:
        list[dict[str, str]]: Copy plan rows.

    异常:
        FileNotFoundError: Raised when manifest.json is missing.
        ValueError: Raised when required source files are missing or manifest rows are malformed.
    """
    manifest_path = artifact_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"artifact release manifest missing: {manifest_path}")
    manifest = load_json(manifest_path)
    artifacts = manifest.get("required_artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("manifest.json missing required_artifacts list")

    copy_plan: list[dict[str, str]] = []
    missing_required_artifacts: list[str] = []
    for row in artifacts:
        if not isinstance(row, dict):
            raise ValueError("manifest required_artifacts rows must be objects")
        artifact_id = str(row.get("artifact_id", "")).strip()
        destination_relative_path = validate_relative_path(
            str(row.get("expected_location", "")),
            f"destination {artifact_id}",
        )
        source_relative_path = mapping.get(artifact_id, destination_relative_path)
        source_relative_path = validate_relative_path(source_relative_path, f"source {artifact_id}")
        source_path = resolve_inside_root(source_dir, source_relative_path, f"source {artifact_id}")
        destination_path = resolve_inside_root(artifact_dir, destination_relative_path, f"destination {artifact_id}")
        if source_path.is_file():
            copy_plan.append(
                {
                    "artifact_id": artifact_id,
                    "source_relative_path": source_relative_path,
                    "destination_relative_path": destination_relative_path,
                    "source_path": str(source_path),
                    "destination_path": str(destination_path),
                    "required": str(row.get("required") is True).lower(),
                }
            )
            continue
        if row.get("required") is True:
            missing_required_artifacts.append(f"{artifact_id} -> {source_relative_path}")
    if missing_required_artifacts:
        missing_text = ", ".join(sorted(missing_required_artifacts))
        raise ValueError(f"missing required source artifact files: {missing_text}")
    return copy_plan


def copy_planned_artifacts(copy_plan: list[dict[str, str]]) -> list[dict[str, str]]:
    """Copy planned artifact files into the release directory.

    参数:
        copy_plan: Rows produced by build_copy_plan.

    返回:
        list[dict[str, str]]: Copied artifact rows.

    异常:
        OSError: Raised when copying fails.
    """
    copied_rows: list[dict[str, str]] = []
    for row in copy_plan:
        source_path = Path(row["source_path"])
        destination_path = Path(row["destination_path"])
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        copied_rows.append(
            {
                "artifact_id": row["artifact_id"],
                "source_relative_path": row["source_relative_path"],
                "destination_relative_path": row["destination_relative_path"],
                "required": row["required"],
            }
        )
    return copied_rows


def write_population_log(artifact_dir: Path, copied_rows: list[dict[str, str]]) -> Path:
    """Write a JSONL log for artifact population.

    参数:
        artifact_dir: Artifact release directory.
        copied_rows: Copied artifact rows.

    返回:
        Path: Population log path.

    异常:
        OSError: Raised when the log cannot be written.
    """
    log_path = artifact_dir / POPULATION_LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, sort_keys=True) for row in copied_rows]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


def load_finalizer():
    """Load the sibling artifact release finalizer module.

    参数:
        无。

    返回:
        module: Loaded finalize_artifact_release module.

    异常:
        ImportError: Raised when the finalizer script cannot be loaded.
    """
    finalizer_path = Path(__file__).resolve().with_name("finalize_artifact_release.py")
    spec = importlib.util.spec_from_file_location("finalize_artifact_release", finalizer_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load artifact release finalizer: {finalizer_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finalize_release(artifact_dir: Path, manifest_template_path: Path, release_status: str) -> None:
    """Finalize the populated release directory.

    参数:
        artifact_dir: Artifact release directory.
        manifest_template_path: Manifest template path.
        release_status: Release status to write.

    返回:
        无。

    异常:
        ImportError: Raised when the finalizer cannot be loaded.
        ValueError: Raised when finalization or validation fails.
        OSError: Raised when finalization cannot write files.
    """
    finalizer = load_finalizer()
    finalizer.finalize_artifact_release(
        artifact_dir=artifact_dir,
        manifest_template_path=manifest_template_path,
        release_status=release_status,
        validate=True,
    )


def populate_artifact_release(
    artifact_dir: Path,
    source_dir: Path,
    manifest_template_path: Path,
    mapping_path: Path | None = None,
    finalize: bool = True,
    release_status: str = "release_candidate",
) -> list[dict[str, str]]:
    """Populate an artifact release scaffold from a source artifact directory.

    参数:
        artifact_dir: Artifact release scaffold directory.
        source_dir: Directory containing source artifact files.
        manifest_template_path: Manifest template path for final validation.
        mapping_path: Optional artifact ID mapping JSON path.
        finalize: Whether to run finalization after copying.
        release_status: Release status passed to the finalizer.

    返回:
        list[dict[str, str]]: Copied artifact rows.

    异常:
        FileNotFoundError: Raised when source or artifact directories are missing.
        ValueError: Raised when required source artifacts are missing.
        OSError: Raised when copying or logging fails.
    """
    if not artifact_dir.is_dir():
        raise FileNotFoundError(f"artifact release directory missing: {artifact_dir}")
    if not source_dir.is_dir():
        raise FileNotFoundError(f"source artifact directory missing: {source_dir}")
    mapping = load_mapping(mapping_path)
    copy_plan = build_copy_plan(artifact_dir, source_dir, mapping)
    copied_rows = copy_planned_artifacts(copy_plan)
    write_population_log(artifact_dir, copied_rows)
    if finalize:
        finalize_release(artifact_dir, manifest_template_path, release_status)
    return copied_rows


def preflight_source_artifacts(
    artifact_dir: Path,
    source_dir: Path,
    mapping_path: Path | None = None,
) -> list[dict[str, str]]:
    """Check source artifact files against the release manifest without writing files.

    参数:
        artifact_dir: Artifact release scaffold directory containing manifest.json.
        source_dir: Directory containing generated source artifact files.
        mapping_path: Optional artifact ID mapping JSON path.

    返回:
        list[dict[str, str]]: Planned artifact rows that would be copied by population.

    异常:
        FileNotFoundError: Raised when source or artifact directories are missing.
        ValueError: Raised when required source artifacts are missing or paths are unsafe.
        OSError: Raised when the mapping or manifest cannot be read.
    """
    if not artifact_dir.is_dir():
        raise FileNotFoundError(f"artifact release directory missing: {artifact_dir}")
    if not source_dir.is_dir():
        raise FileNotFoundError(f"source artifact directory missing: {source_dir}")
    mapping = load_mapping(mapping_path)
    return build_copy_plan(artifact_dir, source_dir, mapping)


def main() -> int:
    """Run artifact release population.

    参数:
        无。

    返回:
        int: Process exit code.
    """
    args = parse_arguments()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO), format="%(levelname)s %(message)s")
    try:
        if args.preflight_only:
            planned_rows = preflight_source_artifacts(
                artifact_dir=Path(args.artifact_dir).resolve(),
                source_dir=Path(args.source_dir).resolve(),
                mapping_path=Path(args.mapping).resolve() if args.mapping else None,
            )
            LOGGER.info("Artifact source preflight passed with %d planned file(s): %s", len(planned_rows), args.source_dir)
            return 0
        copied_rows = populate_artifact_release(
            artifact_dir=Path(args.artifact_dir).resolve(),
            source_dir=Path(args.source_dir).resolve(),
            manifest_template_path=Path(args.manifest_template).resolve(),
            mapping_path=Path(args.mapping).resolve() if args.mapping else None,
            finalize=not args.skip_finalize,
            release_status=args.release_status,
        )
    except (FileNotFoundError, ImportError, OSError, ValueError, json.JSONDecodeError) as exc:
        LOGGER.error("artifact release population failed: %s", exc)
        return 1
    LOGGER.info("Artifact release populated with %d file(s): %s", len(copied_rows), args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
