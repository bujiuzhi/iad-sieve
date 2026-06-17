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
import zipfile
from pathlib import Path


LOGGER = logging.getLogger(__name__)
MANUSCRIPT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = MANUSCRIPT_ROOT / "build" / "submission_package"
DEFAULT_ZIP_PATH = MANUSCRIPT_ROOT / "build" / "iad-risk-submission-package.zip"
SUBMISSION_FILES = [
    ("main.tex", "main_latex_source"),
    ("supplementary_material.tex", "supplementary_latex_source"),
    ("references.bib", "bibliography"),
    ("cover_letter.md", "cover_letter"),
    ("highlights.md", "submission_highlights"),
    ("keywords.md", "submission_keywords"),
    ("build/iad-risk-manuscript-latex.pdf", "main_pdf"),
    ("build/iad-risk-supplementary-material.pdf", "supplementary_pdf"),
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


def copy_submission_files(manuscript_root: Path, output_dir: Path) -> list[dict]:
    """Copy required submission files into the package directory.

    参数:
        manuscript_root: Manuscript package root.
        output_dir: Package output directory.

    返回:
        list[dict]: Manifest file records.

    异常:
        FileNotFoundError: Raised when a required submission file is missing.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    for relative_path, role in SUBMISSION_FILES:
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


def write_manifest(output_dir: Path, records: list[dict]) -> Path:
    """Write a JSON submission manifest.

    参数:
        output_dir: Package output directory.
        records: Manifest file records.

    返回:
        Path: Manifest path.
    """
    manifest = {
        "package_name": "iad-risk-submission-package",
        "description": "Template-independent manuscript submission package.",
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


def build_submission_package(manuscript_root: Path, output_dir: Path, zip_path: Path | None = None) -> dict:
    """Build the submission package directory and optional zip archive.

    参数:
        manuscript_root: Manuscript root directory.
        output_dir: Package output directory.
        zip_path: Optional zip archive path.

    返回:
        dict: Build summary.
    """
    remove_existing_output(output_dir, zip_path)
    records = copy_submission_files(manuscript_root, output_dir)
    manifest_path = write_manifest(output_dir, records)
    checksum_path = write_checksums(output_dir)
    archive_path = create_zip_archive(output_dir, zip_path) if zip_path else None
    summary = {
        "output_dir": str(output_dir),
        "zip_path": str(archive_path) if archive_path else "",
        "file_count": len([path for path in output_dir.iterdir() if path.is_file()]),
        "manifest_path": str(manifest_path),
        "checksum_path": str(checksum_path),
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
    zip_path = None if args.no_zip else Path(args.zip_path).resolve()
    try:
        build_submission_package(MANUSCRIPT_ROOT, Path(args.output_dir).resolve(), zip_path)
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("submission package build failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
