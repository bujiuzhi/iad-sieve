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
import shutil
import sys
import zipfile
from pathlib import Path


LOGGER = logging.getLogger(__name__)
MANUSCRIPT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
from submission_metadata_checks import check_final_upload_cover_letter_text, check_final_upload_metadata_text

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


def copy_submission_files(manuscript_root: Path, output_dir: Path, dke_preflight: bool = False) -> list[dict]:
    """Copy required submission files into the package directory.

    参数:
        manuscript_root: Manuscript package root.
        output_dir: Package output directory.
        dke_preflight: Whether to include DKE/Elsevier provisional files.

    返回:
        list[dict]: Manifest file records.

    异常:
        FileNotFoundError: Raised when a required submission file is missing.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    for relative_path, role in get_submission_files(dke_preflight):
        source_path = manuscript_root / relative_path
        if not source_path.exists():
            raise FileNotFoundError(f"missing required submission file: {source_path}")
        destination_path = output_dir / source_path.name
        shutil.copy2(source_path, destination_path)
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


def check_final_upload_metadata(manuscript_root: Path) -> list[str]:
    """Check whether submission metadata is ready for final journal upload.

    参数:
        manuscript_root: Manuscript root directory.

    返回:
        list[str]: Error messages for unresolved final-upload metadata.
    """
    metadata_path = manuscript_root / "submission_metadata.yml"
    if not metadata_path.exists():
        return ["missing submission_metadata.yml for final upload"]
    metadata_text = metadata_path.read_text(encoding="utf-8")
    return check_final_upload_metadata_text(metadata_text)


def check_final_upload_cover_letter(manuscript_root: Path) -> list[str]:
    """Check whether the cover letter is ready for final journal upload.

    参数:
        manuscript_root: Manuscript root directory.

    返回:
        list[str]: Error messages for unresolved final-upload cover letter fields.
    """
    metadata_path = manuscript_root / "submission_metadata.yml"
    cover_letter_path = manuscript_root / "cover_letter.md"
    if not metadata_path.exists():
        return ["missing submission_metadata.yml for final-upload cover letter check"]
    if not cover_letter_path.exists():
        return ["missing cover_letter.md for final upload"]
    metadata_text = metadata_path.read_text(encoding="utf-8")
    cover_letter_text = cover_letter_path.read_text(encoding="utf-8")
    return check_final_upload_cover_letter_text(cover_letter_text, metadata_text)


def write_manifest(output_dir: Path, records: list[dict], dke_preflight: bool = False) -> Path:
    """Write a JSON submission manifest.

    参数:
        output_dir: Package output directory.
        records: Manifest file records.
        dke_preflight: Whether the package includes DKE/Elsevier provisional files.

    返回:
        Path: Manifest path.
    """
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
    manifest = {
        "package_name": "iad-risk-dke-preflight-package" if dke_preflight else "iad-risk-submission-package",
        "package_type": "journal_submission",
        "submission_stage": submission_stage,
        "description": description,
        "anonymization": {
            "author_status": "anonymous_placeholder",
            "author_metadata_required_before_final_upload": True,
        },
        "journal_template": {
            "target_journal_bound": False,
            "dke_elsevier_preflight_included": dke_preflight,
            "final_upload_requirements": [
                "target journal document class",
                "journal-specific reference style",
                "author metadata",
            ],
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
    if final_upload:
        final_upload_errors = check_final_upload_metadata(manuscript_root)
        final_upload_errors.extend(check_final_upload_cover_letter(manuscript_root))
        if final_upload_errors:
            raise ValueError("; ".join(final_upload_errors))
    remove_existing_output(output_dir, zip_path)
    records = copy_submission_files(manuscript_root, output_dir, dke_preflight)
    manifest_path = write_manifest(output_dir, records, dke_preflight)
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
