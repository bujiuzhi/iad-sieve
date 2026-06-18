"""Build a self-contained manuscript submission package.

The package contains the LaTeX sources, bibliography, submission text files,
compiled PDFs, checksums, and a JSON manifest. Generated package files are
written under manuscript/build by default and are not intended to replace the
source manuscript files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import subprocess
import shutil
import sys
import zipfile
from pathlib import Path


LOGGER = logging.getLogger(__name__)
MANUSCRIPT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
from submission_metadata_checks import (
    DKE_ELSEVIER_FILE_REQUIREMENT_ERROR,
    check_final_upload_cover_letter_text,
    check_final_upload_metadata_text,
    scalar_value,
    target_journal_requires_elsevier_files,
)

DEFAULT_OUTPUT_DIR = MANUSCRIPT_ROOT / "build" / "submission_package"
DEFAULT_ZIP_PATH = MANUSCRIPT_ROOT / "build" / "iad-risk-submission-package.zip"
DEFAULT_DKE_PREFLIGHT_OUTPUT_DIR = MANUSCRIPT_ROOT / "build" / "dke_preflight_package"
DEFAULT_DKE_PREFLIGHT_ZIP_PATH = MANUSCRIPT_ROOT / "build" / "iad-risk-dke-preflight-package.zip"
BASE_SUBMISSION_FILES = [
    ("main.tex", "main_latex_source"),
    ("supplementary_material.tex", "supplementary_latex_source"),
    ("references.bib", "bibliography"),
    ("cover_letter.md", "cover_letter"),
    ("highlights.md", "submission_highlights"),
    ("keywords.md", "submission_keywords"),
    ("submission_metadata.yml", "submission_metadata"),
    ("build/iad-risk-manuscript-latex.pdf", "main_pdf"),
    ("build/iad-risk-supplementary-material.pdf", "supplementary_pdf"),
]
DKE_PREFLIGHT_FILES = [
    ("build/iad-risk-manuscript-elsevier.tex", "dke_elsevier_latex_source"),
    ("build/iad-risk-manuscript-elsevier.pdf", "dke_elsevier_pdf"),
]
def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    参数:
        无。

    返回:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Build a journal submission package from manuscript files.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for copied package files.")
    parser.add_argument("--zip-path", default=str(DEFAULT_ZIP_PATH), help="Output zip path.")
    parser.add_argument("--no-zip", action="store_true", help="Skip zip creation.")
    parser.add_argument("--final-upload", action="store_true", help="Require target journal and real author metadata.")
    parser.add_argument("--dke-preflight", action="store_true", help="Include provisional DKE/Elsevier elsarticle files.")
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


def remove_existing_output(output_dir: Path, zip_path: Path | None) -> None:
    """Remove previously generated package outputs.

    参数:
        output_dir: Package output directory.
        zip_path: Optional zip output path.

    返回:
        无。
    """
    if output_dir.exists():
        shutil.rmtree(output_dir)
    if zip_path and zip_path.exists():
        zip_path.unlink()


def get_submission_files(dke_preflight: bool = False) -> list[tuple[str, str]]:
    """Return submission file roles for the requested package profile.

    参数:
        dke_preflight: Whether to include DKE/Elsevier provisional files.

    返回:
        list[tuple[str, str]]: Relative source paths and manifest roles.
    """
    files = list(BASE_SUBMISSION_FILES)
    if dke_preflight:
        files.extend(DKE_PREFLIGHT_FILES)
    return files


def copy_submission_files(
    manuscript_root: Path,
    output_dir: Path,
    dke_preflight: bool = False,
    file_text_overrides: dict[str, str] | None = None,
) -> list[dict]:
    """Copy required submission files into the package directory.

    参数:
        manuscript_root: Manuscript package root.
        output_dir: Package output directory.
        dke_preflight: Whether to include DKE/Elsevier provisional files.
        file_text_overrides: Optional package-path text overrides applied after copy.

    返回:
        list[dict]: Manifest file records.

    异常:
        FileNotFoundError: Raised when a required submission file is missing.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    overrides = file_text_overrides or {}
    for relative_path, role in get_submission_files(dke_preflight):
        source_path = manuscript_root / relative_path
        if not source_path.exists():
            raise FileNotFoundError(f"missing required submission file: {source_path}")
        destination_path = output_dir / source_path.name
        shutil.copy2(source_path, destination_path)
        if source_path.name in overrides:
            destination_path.write_text(overrides[source_path.name], encoding="utf-8")
        records.append(
            {
                "role": role,
                "source_path": relative_path,
                "package_path": destination_path.name,
                "size_bytes": destination_path.stat().st_size,
                "sha256": sha256_file(destination_path),
            }
        )
    return records


def run_git_command(repository_root: Path, arguments: list[str]) -> str | None:
    """Run a Git command and return stripped stdout.

    参数:
        repository_root: Directory from which Git should be executed.
        arguments: Git command arguments after the `git` executable.

    返回:
        str | None: Command stdout when Git succeeds, otherwise None.
    """
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        LOGGER.warning("source-control metadata unavailable from git command %s: %s", arguments, exc)
        return None
    if result.returncode != 0:
        LOGGER.warning("source-control metadata command failed with exit %s: %s", result.returncode, arguments)
        return None
    return result.stdout.strip()


def normalize_repository_url(remote_url: str) -> str:
    """Normalize a Git remote URL for final-upload metadata.

    参数:
        remote_url: Raw Git remote URL from local repository configuration.

    返回:
        str: HTTPS URL when the remote can be normalized, otherwise the trimmed input.
    """
    value = remote_url.strip()
    if value.startswith("git@") and ":" in value:
        host, repository_path = value[4:].split(":", maxsplit=1)
        return f"https://{host}/{repository_path}"
    if value.startswith("ssh://git@"):
        without_prefix = value[len("ssh://git@") :]
        if "/" in without_prefix:
            host, repository_path = without_prefix.split("/", maxsplit=1)
            return f"https://{host}/{repository_path}"
    return value


def collect_repository_url(manuscript_root: Path) -> str:
    """Collect the repository URL used for final-upload metadata.

    参数:
        manuscript_root: Manuscript root directory.

    返回:
        str: Normalized repository URL, or an empty string when unavailable.
    """
    repository_root = manuscript_root.parent
    remote_url = run_git_command(repository_root, ["config", "--get", "remote.origin.url"])
    return normalize_repository_url(remote_url) if remote_url else ""


def collect_source_control_state(manuscript_root: Path) -> dict:
    """Collect Git source-control state for the generated package manifest.

    参数:
        manuscript_root: Manuscript root directory.

    返回:
        dict: Source-control metadata without local absolute paths.
    """
    repository_root = manuscript_root.parent
    repository_commit = run_git_command(repository_root, ["rev-parse", "HEAD"])
    repository_branch = run_git_command(repository_root, ["rev-parse", "--abbrev-ref", "HEAD"]) if repository_commit else None
    porcelain_status = run_git_command(repository_root, ["status", "--porcelain"]) if repository_commit else None
    if not repository_commit:
        return {
            "available": False,
            "repository_commit": "",
            "repository_branch": "",
            "worktree_dirty": None,
            "tracked_state": "unavailable",
        }
    worktree_dirty = bool(porcelain_status)
    return {
        "available": True,
        "repository_commit": repository_commit,
        "repository_branch": repository_branch or "",
        "worktree_dirty": worktree_dirty,
        "tracked_state": "dirty" if worktree_dirty else "clean",
    }


def yaml_double_quote(value: str) -> str:
    """Quote a scalar value for the simple YAML files used by this package.

    参数:
        value: Scalar value to quote.

    返回:
        str: Double-quoted YAML scalar.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def replace_yaml_scalar(text: str, key: str, value: str) -> str:
    """Replace a simple YAML scalar line by key.

    参数:
        text: YAML text.
        key: Scalar key to replace.
        value: New scalar value.

    返回:
        str: Updated YAML text.
    """
    pattern = re.compile(rf"(?m)^(\s*{re.escape(key)}:\s*).*$")
    return pattern.sub(lambda match: f"{match.group(1)}{yaml_double_quote(value)}", text, count=1)


def final_upload_data_code_availability_statement(metadata_text: str, source_control: dict, repository_url: str) -> str:
    """Build the final-upload data/code availability statement with Git binding.

    参数:
        metadata_text: Submission metadata YAML text.
        source_control: Git source-control metadata.
        repository_url: Public repository URL.

    返回:
        str: Data/code availability statement containing repository and artifact references.
    """
    repository_commit = str(source_control.get("repository_commit", "")).strip()
    repository_branch = str(source_control.get("repository_branch", "")).strip()
    artifact_value = scalar_value(metadata_text, "artifact_release_url") or scalar_value(metadata_text, "artifact_release_doi")
    statement = (
        "Source code, small public fixtures, schema contracts, build scripts, and artifact-release "
        f"instructions are available at {repository_url} commit {repository_commit} on branch "
        f"{repository_branch}. Raw third-party data and full experimental outputs are not redistributed in Git."
    )
    if artifact_value:
        statement += f" Full result artifacts are available at {artifact_value}."
    return statement


def bind_final_upload_repository_metadata(metadata_text: str, source_control: dict, repository_url: str) -> str:
    """Inject Git repository references into final-upload metadata text.

    参数:
        metadata_text: Source submission metadata text.
        source_control: Git source-control metadata collected for the package.
        repository_url: Repository URL collected from Git remote configuration.

    返回:
        str: Metadata text with repository URL, commit, branch, and availability statement bound.
    """
    if source_control.get("available") is not True or not repository_url:
        return metadata_text
    bound_text = metadata_text
    bound_text = replace_yaml_scalar(bound_text, "repository_url", repository_url)
    bound_text = replace_yaml_scalar(bound_text, "repository_commit", str(source_control.get("repository_commit", "")))
    bound_text = replace_yaml_scalar(bound_text, "repository_branch", str(source_control.get("repository_branch", "")))
    data_code_statement = final_upload_data_code_availability_statement(bound_text, source_control, repository_url)
    return replace_yaml_scalar(bound_text, "data_code_availability", data_code_statement)


def has_final_upload_repository_reference(metadata_text: str) -> bool:
    """Return whether metadata already records repository URL, commit, and branch.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        bool: True when repository reference fields are already filled.
    """
    return all(
        scalar_value(metadata_text, key)
        for key in ("repository_url", "repository_commit", "repository_branch")
    )


def read_final_upload_metadata(manuscript_root: Path, source_control: dict) -> tuple[str, list[str]]:
    """Read and bind final-upload metadata for validation and packaging.

    参数:
        manuscript_root: Manuscript root directory.
        source_control: Git source-control metadata collected for the package.

    返回:
        tuple[str, list[str]]: Effective metadata text and metadata-binding errors.
    """
    metadata_path = manuscript_root / "submission_metadata.yml"
    if not metadata_path.exists():
        return "", ["missing submission_metadata.yml for final upload"]
    metadata_text = metadata_path.read_text(encoding="utf-8")
    if has_final_upload_repository_reference(metadata_text):
        return metadata_text, []
    repository_url = collect_repository_url(manuscript_root)
    bound_metadata_text = bind_final_upload_repository_metadata(metadata_text, source_control, repository_url)
    return bound_metadata_text, []


def check_final_upload_metadata_text_for_package(metadata_text: str, dke_preflight: bool = False) -> list[str]:
    """Check whether effective submission metadata is ready for final journal upload.

    参数:
        metadata_text: Effective submission metadata text.
        dke_preflight: Whether the package includes DKE/Elsevier source and PDF files.

    返回:
        list[str]: Error messages for unresolved final-upload metadata.
    """
    errors = check_final_upload_metadata_text(metadata_text)
    if target_journal_requires_elsevier_files(metadata_text) and not dke_preflight:
        errors.append(DKE_ELSEVIER_FILE_REQUIREMENT_ERROR)
    return errors


def check_final_upload_cover_letter(manuscript_root: Path, metadata_text: str) -> list[str]:
    """Check whether the cover letter is ready for final journal upload.

    参数:
        manuscript_root: Manuscript root directory.
        metadata_text: Effective submission metadata text.

    返回:
        list[str]: Error messages for unresolved final-upload cover letter fields.
    """
    cover_letter_path = manuscript_root / "cover_letter.md"
    if not cover_letter_path.exists():
        return ["missing cover_letter.md for final upload"]
    cover_letter_text = cover_letter_path.read_text(encoding="utf-8")
    return check_final_upload_cover_letter_text(cover_letter_text, metadata_text)


def write_manifest(
    output_dir: Path,
    records: list[dict],
    dke_preflight: bool = False,
    final_upload: bool = False,
    source_control: dict | None = None,
) -> Path:
    """Write a JSON submission manifest.

    参数:
        output_dir: Package output directory.
        records: Manifest file records.
        dke_preflight: Whether the package includes DKE/Elsevier provisional files.
        final_upload: Whether the package is a final journal upload preflight package.
        source_control: Git source-control metadata for the packaged source state.

    返回:
        Path: Manifest path.
    """
    if final_upload:
        submission_stage = "final_journal_upload_preflight"
        description = "Final journal upload preflight package with target journal and author metadata."
        author_status = "provided_for_final_upload"
        target_journal_bound = True
        final_upload_requirements = [
            "target journal document class",
            "journal-specific reference style",
            "author metadata",
            "author biographies and photographs",
            "artifact release linked",
        ]
    else:
        submission_stage = (
            "dke_elsevier_anonymous_preflight"
            if dke_preflight
            else "template_independent_anonymous_pre_submission"
        )
        description = (
            "DKE/Elsevier preflight package with anonymous elsarticle source and PDF."
            if dke_preflight
            else "Template-independent manuscript submission package."
        )
        author_status = "anonymous_placeholder"
        target_journal_bound = False
        final_upload_requirements = [
            "target journal document class",
            "journal-specific reference style",
            "author metadata",
            "author biographies and photographs",
        ]
    manifest = {
        "package_name": "iad-risk-dke-preflight-package" if dke_preflight else "iad-risk-submission-package",
        "package_type": "journal_submission",
        "submission_stage": submission_stage,
        "description": description,
        "anonymization": {
            "author_status": author_status,
            "author_metadata_required_before_final_upload": True,
        },
        "journal_template": {
            "target_journal_bound": target_journal_bound,
            "dke_elsevier_preflight_included": dke_preflight,
            "final_upload_requirements": final_upload_requirements,
        },
        "reproducibility_level": {
            "code_and_fixture_rebuild": "covered by repository scripts",
            "raw_data_distribution": "excluded",
            "full_numeric_audit": "requires separate L2/L3 artifact package",
        },
        "claim_boundary": {
            "no_broad_method_ranking": True,
            "no_human_gold_claim_for_silver_labels": True,
            "manual_validation_required_for_stronger_label_precision": True,
        },
        "source_control": source_control
        or {
            "available": False,
            "repository_commit": "",
            "repository_branch": "",
            "worktree_dirty": None,
            "tracked_state": "unavailable",
        },
        "files": records,
        "excluded": [
            "raw third-party data",
            "local experiment outputs",
            "model checkpoints",
            "remote connection profiles",
            "API keys or credentials",
        ],
    }
    manifest_path = output_dir / "submission_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def write_checksums(output_dir: Path) -> Path:
    """Write SHA256 checksums for package files.

    参数:
        output_dir: Package output directory.

    返回:
        Path: Checksum file path.
    """
    checksum_path = output_dir / "checksums.sha256"
    lines = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.name == checksum_path.name:
            continue
        lines.append(f"{sha256_file(path)}  {path.name}")
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksum_path


def create_zip_archive(output_dir: Path, zip_path: Path) -> Path:
    """Create a deterministic zip archive for the package directory.

    参数:
        output_dir: Package output directory.
        zip_path: Zip output path.

    返回:
        Path: Zip output path.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    package_root_name = output_dir.name
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
            if not path.is_file():
                continue
            zip_info = zipfile.ZipInfo(f"{package_root_name}/{path.name}")
            zip_info.date_time = (2024, 1, 1, 0, 0, 0)
            zip_info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(zip_info, path.read_bytes())
    return zip_path


def build_submission_package(
    manuscript_root: Path,
    output_dir: Path,
    zip_path: Path | None = None,
    final_upload: bool = False,
    dke_preflight: bool = False,
) -> dict:
    """Build the submission package directory and optional zip archive.

    参数:
        manuscript_root: Manuscript root directory.
        output_dir: Package output directory.
        zip_path: Optional zip archive path.
        final_upload: Whether to require journal and author metadata for final upload.
        dke_preflight: Whether to include DKE/Elsevier provisional files.

    返回:
        dict: Build summary.

    异常:
        ValueError: Raised when final-upload metadata is unresolved.
    """
    source_control = collect_source_control_state(manuscript_root)
    file_text_overrides: dict[str, str] = {}
    if final_upload:
        effective_metadata_text, metadata_binding_errors = read_final_upload_metadata(manuscript_root, source_control)
        final_upload_errors = metadata_binding_errors
        final_upload_errors.extend(check_final_upload_metadata_text_for_package(effective_metadata_text, dke_preflight))
        final_upload_errors.extend(check_final_upload_cover_letter(manuscript_root, effective_metadata_text))
        if final_upload_errors:
            raise ValueError("; ".join(final_upload_errors))
        file_text_overrides["submission_metadata.yml"] = effective_metadata_text
    remove_existing_output(output_dir, zip_path)
    records = copy_submission_files(manuscript_root, output_dir, dke_preflight, file_text_overrides)
    manifest_path = write_manifest(output_dir, records, dke_preflight, final_upload, source_control)
    checksum_path = write_checksums(output_dir)
    archive_path = create_zip_archive(output_dir, zip_path) if zip_path else None
    summary = {
        "output_dir": str(output_dir),
        "zip_path": str(archive_path) if archive_path else "",
        "file_count": len([path for path in output_dir.iterdir() if path.is_file()]),
        "manifest_path": str(manifest_path),
        "checksum_path": str(checksum_path),
        "dke_preflight": dke_preflight,
    }
    LOGGER.info("submission package built: %s", summary)
    return summary


def main() -> int:
    """Run the submission package builder.

    参数:
        无。

    返回:
        int: Process exit code.
    """
    args = parse_arguments()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")
    output_dir = Path(args.output_dir)
    zip_argument = Path(args.zip_path)
    if args.dke_preflight and output_dir == DEFAULT_OUTPUT_DIR:
        output_dir = DEFAULT_DKE_PREFLIGHT_OUTPUT_DIR
    if args.dke_preflight and zip_argument == DEFAULT_ZIP_PATH:
        zip_argument = DEFAULT_DKE_PREFLIGHT_ZIP_PATH
    zip_path = None if args.no_zip else zip_argument.resolve()
    try:
        build_submission_package(MANUSCRIPT_ROOT, output_dir.resolve(), zip_path, args.final_upload, args.dke_preflight)
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("submission package build failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
