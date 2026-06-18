"""Build an external artifact release scaffold for the manuscript.

The scaffold is stored outside Git by default. It contains the release
directory layout, README, manifest, and checksum file required before the real
tables, predictions, logs, and reports are copied into the release.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
MANUSCRIPT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = MANUSCRIPT_ROOT / "build" / "artifact_release"
DEFAULT_MANIFEST_TEMPLATE_PATH = MANUSCRIPT_ROOT / "artifact_release_manifest.template.json"
DEFAULT_README_TEMPLATE_PATH = MANUSCRIPT_ROOT / "artifact_release_README.template.md"
REQUIRED_DIRECTORIES = ("configs", "tables", "predictions", "reports", "logs")
SKELETON_RELEASE_STATUS = "skeleton_pending_artifacts"
TEMPLATE_RELEASE_STATUS = "template_pending_external_artifact"
ARTIFACT_SHA256_PLACEHOLDER = "fill-after-artifact-export"
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    参数:
        无。

    返回:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Build an external IAD-Risk artifact release scaffold.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output artifact release directory.")
    parser.add_argument(
        "--manifest-template",
        default=str(DEFAULT_MANIFEST_TEMPLATE_PATH),
        help="Artifact release manifest template path.",
    )
    parser.add_argument(
        "--readme-template",
        default=str(DEFAULT_README_TEMPLATE_PATH),
        help="Artifact release README template path.",
    )
    parser.add_argument(
        "--repository-commit",
        required=True,
        help="Clean repository commit that the external artifact release should reference.",
    )
    parser.add_argument("--force", action="store_true", help="Replace an existing non-empty scaffold directory.")
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
        ValueError: Raised when the file is not a JSON object.
        json.JSONDecodeError: Raised when the file contains invalid JSON.
        OSError: Raised when the file cannot be read.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return data


def validate_repository_commit(repository_commit: str) -> str:
    """Validate and normalize the repository commit value.

    参数:
        repository_commit: Commit identifier provided by the caller.

    返回:
        str: Normalized commit identifier.

    异常:
        ValueError: Raised when the commit value is empty or still a placeholder.
    """
    commit = repository_commit.strip()
    if not commit or commit == "fill-with-release-commit":
        raise ValueError("repository commit must be a real commit identifier")
    if not COMMIT_PATTERN.fullmatch(commit):
        raise ValueError("repository commit must be a 7 to 40 character hexadecimal Git commit")
    return commit


def assert_safe_output_directory(output_dir: Path) -> None:
    """Reject output directories that are too broad to remove safely.

    参数:
        output_dir: Output directory requested by the caller.

    返回:
        无。

    异常:
        ValueError: Raised when the output path is unsafe for scaffold replacement.
    """
    resolved_output = output_dir.resolve()
    unsafe_roots = {
        Path("/").resolve(),
        Path.home().resolve(),
        MANUSCRIPT_ROOT.resolve(),
        MANUSCRIPT_ROOT.parent.resolve(),
    }
    if resolved_output in unsafe_roots:
        raise ValueError(f"refusing to use unsafe output directory: {resolved_output}")


def prepare_output_directory(output_dir: Path, force: bool) -> None:
    """Create a clean scaffold output directory.

    参数:
        output_dir: Output directory for the scaffold.
        force: Whether to replace an existing non-empty directory.

    返回:
        无。

    异常:
        FileExistsError: Raised when a non-empty directory exists and force is false.
        NotADirectoryError: Raised when the path exists but is not a directory.
        ValueError: Raised when the output path is unsafe.
        OSError: Raised when filesystem operations fail.
    """
    assert_safe_output_directory(output_dir)
    if output_dir.exists() and not output_dir.is_dir():
        raise NotADirectoryError(f"artifact release output path is not a directory: {output_dir}")
    if output_dir.exists() and any(output_dir.iterdir()):
        if not force:
            raise FileExistsError(f"artifact release output directory is not empty: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def build_readme_text(template_text: str) -> str:
    """Convert the README template into a scaffold README.

    参数:
        template_text: README template text.

    返回:
        str: README content for the scaffold.
    """
    readme_text = template_text.replace(
        "# IAD-Risk Artifact Release README Template",
        "# IAD-Risk Artifact Release",
        1,
    )
    readme_text = readme_text.replace(
        "This template is for the external result artifact release",
        "This README is for the external result artifact release",
        1,
    )
    skeleton_notice = "\n".join(
        [
            "",
            "## Skeleton Status",
            "",
            "This directory is a scaffold. Fill the required artifact files, replace SHA256 placeholders in",
            "`manifest.json`, refresh `checksums.sha256`, and run the validator before linking the release.",
            "",
        ]
    )
    return readme_text.rstrip() + "\n" + skeleton_notice


def build_manifest(
    manifest_template_path: Path,
    readme_template_path: Path,
    repository_commit: str,
) -> dict[str, Any]:
    """Build a scaffold manifest from the release template.

    参数:
        manifest_template_path: Source manifest template path.
        readme_template_path: Source README template path.
        repository_commit: Repository commit to record in the scaffold.

    返回:
        dict[str, Any]: Scaffold manifest object.

    异常:
        ValueError: Raised when the template has an unexpected status or malformed artifact rows.
    """
    template = load_json(manifest_template_path)
    if template.get("release_status") != TEMPLATE_RELEASE_STATUS:
        raise ValueError(f"manifest template must keep release_status={TEMPLATE_RELEASE_STATUS}")
    manifest = json.loads(json.dumps(template))
    manifest["release_status"] = SKELETON_RELEASE_STATUS
    repository = manifest.setdefault("repository", {})
    if not isinstance(repository, dict):
        raise ValueError("manifest template repository field must be an object")
    repository["commit"] = validate_repository_commit(repository_commit)
    repository["source_tree_clean"] = True
    manifest["generated_from_template"] = {
        "manifest_template": manifest_template_path.name,
        "readme_template": readme_template_path.name,
        "artifact_files_pending": True,
        "final_validation_required": "python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release",
    }
    artifacts = manifest.get("required_artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("manifest template must contain required_artifacts list")
    for row in artifacts:
        if not isinstance(row, dict):
            raise ValueError("manifest template required_artifacts rows must be objects")
        if "expected_location" in row:
            row["sha256"] = ARTIFACT_SHA256_PLACEHOLDER
    return manifest


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON object with stable formatting.

    参数:
        path: Destination JSON path.
        payload: JSON-serializable object.

    返回:
        无。

    异常:
        OSError: Raised when the file cannot be written.
    """
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_checksums(output_dir: Path) -> Path:
    """Write checksums.sha256 for scaffold files.

    参数:
        output_dir: Artifact release scaffold directory.

    返回:
        Path: Written checksum file path.

    异常:
        OSError: Raised when files cannot be read or written.
    """
    checksum_path = output_dir / "checksums.sha256"
    checksum_lines = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name == checksum_path.name or path.name == ".DS_Store":
            continue
        relative_path = path.relative_to(output_dir).as_posix()
        checksum_lines.append(f"{sha256_file(path)}  {relative_path}")
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    return checksum_path


def build_artifact_release_skeleton(
    output_dir: Path,
    manifest_template_path: Path,
    readme_template_path: Path,
    repository_commit: str,
    force: bool = False,
) -> Path:
    """Build an artifact release scaffold directory.

    参数:
        output_dir: Output artifact release directory.
        manifest_template_path: Manifest template path.
        readme_template_path: README template path.
        repository_commit: Clean repository commit to record.
        force: Whether to replace an existing non-empty output directory.

    返回:
        Path: Written manifest path.

    异常:
        FileExistsError: Raised when an existing non-empty output directory is not forced.
        ValueError: Raised when template content or output path is unsafe.
        OSError: Raised when filesystem operations fail.
    """
    prepare_output_directory(output_dir, force)
    for directory_name in REQUIRED_DIRECTORIES:
        (output_dir / directory_name).mkdir(parents=True, exist_ok=True)
    readme_text = build_readme_text(readme_template_path.read_text(encoding="utf-8"))
    (output_dir / "README.md").write_text(readme_text, encoding="utf-8")
    manifest = build_manifest(manifest_template_path, readme_template_path, repository_commit)
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest)
    write_checksums(output_dir)
    return manifest_path


def main() -> int:
    """Run artifact release scaffold generation.

    参数:
        无。

    返回:
        int: Process exit code.
    """
    args = parse_arguments()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO), format="%(levelname)s %(message)s")
    try:
        manifest_path = build_artifact_release_skeleton(
            output_dir=Path(args.output_dir).resolve(),
            manifest_template_path=Path(args.manifest_template).resolve(),
            readme_template_path=Path(args.readme_template).resolve(),
            repository_commit=args.repository_commit,
            force=args.force,
        )
    except (FileExistsError, NotADirectoryError, OSError, ValueError, json.JSONDecodeError) as exc:
        LOGGER.error("artifact release scaffold generation failed: %s", exc)
        return 1
    LOGGER.info("Artifact release scaffold written: %s", manifest_path.parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
