"""Verify the no-network fixture rebuild path for the manuscript package.

This script runs the small public fixture conversion commands documented in the
supplementary material. It writes outputs to a temporary directory by default and
checks that each required contract file is created and non-empty.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures"
REQUIRED_CLI_DISCOVERY_MARKERS = [
    "prepare-deepmatcher",
    "prepare-scirepeval-proximity",
    "fetch-openalex-works",
    "prepare-openalex-weak-labels",
    "build-iad-bench",
]


@dataclass(frozen=True)
class FixtureCommand:
    """Command specification for one fixture rebuild step."""

    name: str
    args: list[str]


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    参数:
        无。

    返回:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Verify no-network fixture rebuild commands for the manuscript.")
    parser.add_argument("--work-dir", default=None, help="Optional output directory for fixture rebuild outputs.")
    parser.add_argument("--keep-work-dir", action="store_true", help="Keep the temporary output directory after verification.")
    parser.add_argument("--python", default=sys.executable, help="Python executable used to run iad_sieve.cli.")
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    return parser.parse_args()


def build_fixture_commands(python_executable: str, output_root: Path) -> list[FixtureCommand]:
    """Build fixture rebuild commands.

    参数:
        python_executable: Python executable path.
        output_root: Root directory for generated fixture outputs.

    返回:
        list[FixtureCommand]: Ordered command specifications.
    """
    deepmatcher_output = output_root / "deepmatcher"
    scirepeval_output = output_root / "scirepeval"
    openalex_output = output_root / "openalex"
    iad_bench_output = output_root / "iad_bench"
    return [
        FixtureCommand(
            name="prepare-deepmatcher",
            args=[
                python_executable,
                "-m",
                "iad_sieve.cli",
                "prepare-deepmatcher",
                "--table-a",
                str(FIXTURE_ROOT / "deepmatcher" / "tableA.csv"),
                "--table-b",
                str(FIXTURE_ROOT / "deepmatcher" / "tableB.csv"),
                "--pairs",
                str(FIXTURE_ROOT / "deepmatcher" / "test.csv"),
                "--dataset-name",
                "deepmatcher_fixture",
                "--output-dir",
                str(deepmatcher_output),
            ],
        ),
        FixtureCommand(
            name="prepare-scirepeval-proximity",
            args=[
                python_executable,
                "-m",
                "iad_sieve.cli",
                "prepare-scirepeval-proximity",
                "--metadata",
                str(FIXTURE_ROOT / "scirepeval" / "metadata.jsonl"),
                "--pairs",
                str(FIXTURE_ROOT / "scirepeval" / "scidocs_cite_pairs.csv"),
                "--dataset-name",
                "scirepeval_fixture",
                "--output-dir",
                str(scirepeval_output),
            ],
        ),
        FixtureCommand(
            name="prepare-openalex-weak-labels",
            args=[
                python_executable,
                "-m",
                "iad_sieve.cli",
                "prepare-openalex-weak-labels",
                "--works",
                str(FIXTURE_ROOT / "openalex" / "works.jsonl"),
                "--citations",
                str(FIXTURE_ROOT / "openalex" / "coci.csv"),
                "--dataset-name",
                "openalex_fixture",
                "--output-dir",
                str(openalex_output),
                "--min-shared-references",
                "1",
                "--max-pairs",
                "20",
            ],
        ),
        FixtureCommand(
            name="build-iad-bench",
            args=[
                python_executable,
                "-m",
                "iad_sieve.cli",
                "build-iad-bench",
                "--source-dirs",
                str(deepmatcher_output),
                str(scirepeval_output),
                str(openalex_output),
                "--output-dir",
                str(iad_bench_output),
                "--seed",
                "42",
            ],
        ),
    ]


def build_subprocess_environment(project_root: Path) -> dict[str, str]:
    """Build subprocess environment with source-tree import support.

    参数:
        project_root: Project root directory.

    返回:
        dict[str, str]: Environment variables for subprocess execution.
    """
    environment = os.environ.copy()
    source_path = str(project_root / "src")
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = source_path if not existing_pythonpath else f"{source_path}{os.pathsep}{existing_pythonpath}"
    return environment


def check_cli_discovery(python_executable: str, environment: dict[str, str]) -> list[str]:
    """Check whether the public-source reconstruction CLI commands are discoverable.

    功能:
        Run the installable CLI help command and verify that required public-source
        reconstruction subcommands appear in the help output.

    参数:
        python_executable: Python executable path.
        environment: Subprocess environment.

    返回:
        list[str]: Error messages for failed CLI help execution or missing commands.
    """
    command_args = [python_executable, "-m", "iad_sieve.cli", "--help"]
    LOGGER.info("running cli-discovery")
    try:
        completed = subprocess.run(
            command_args,
            cwd=PROJECT_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        LOGGER.error("cli-discovery failed with exit code %s", exc.returncode)
        if exc.stdout:
            LOGGER.error("stdout:\n%s", exc.stdout.strip())
        if exc.stderr:
            LOGGER.error("stderr:\n%s", exc.stderr.strip())
        return ["CLI discovery command failed: python -m iad_sieve.cli --help"]

    help_text = f"{completed.stdout}\n{completed.stderr}"
    return [
        f"CLI discovery output missing command: {marker}"
        for marker in REQUIRED_CLI_DISCOVERY_MARKERS
        if marker not in help_text
    ]


def run_command(command: FixtureCommand, environment: dict[str, str]) -> None:
    """Run one fixture rebuild command.

    参数:
        command: Command specification.
        environment: Subprocess environment.

    返回:
        无。

    异常:
        RuntimeError: Raised when the command exits with a non-zero status.
    """
    LOGGER.info("running %s", command.name)
    try:
        subprocess.run(
            command.args,
            cwd=PROJECT_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        LOGGER.error("%s failed with exit code %s", command.name, exc.returncode)
        if exc.stdout:
            LOGGER.error("stdout:\n%s", exc.stdout.strip())
        if exc.stderr:
            LOGGER.error("stderr:\n%s", exc.stderr.strip())
        raise RuntimeError(f"fixture rebuild command failed: {command.name}") from exc


def count_jsonl_records(path: Path) -> int:
    """Count non-empty JSONL records in a file.

    参数:
        path: JSONL file path.

    返回:
        int: Number of non-empty lines.
    """
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def check_non_empty_file(path: Path) -> list[str]:
    """Check whether a required output file exists and is non-empty.

    参数:
        path: Required output file path.

    返回:
        list[str]: Error messages.
    """
    if not path.exists():
        return [f"missing output file: {path}"]
    if path.stat().st_size <= 0:
        return [f"empty output file: {path}"]
    return []


def check_rebuild_outputs(output_root: Path) -> list[str]:
    """Check fixture rebuild output contract files.

    参数:
        output_root: Root directory containing generated fixture outputs.

    返回:
        list[str]: Error messages for missing or empty outputs.
    """
    errors: list[str] = []
    for source_name in ["deepmatcher", "scirepeval", "openalex"]:
        source_dir = output_root / source_name
        for file_name in ["eval_documents.jsonl", "eval_pairs.jsonl", "dataset_summary.jsonl"]:
            file_path = source_dir / file_name
            errors.extend(check_non_empty_file(file_path))
            if file_path.exists() and file_path.suffix == ".jsonl" and count_jsonl_records(file_path) == 0:
                errors.append(f"no JSONL records in output file: {file_path}")

    iad_bench_dir = output_root / "iad_bench"
    required_iad_bench_files = [
        "iad_bench_documents.jsonl",
        "iad_bench_pairs.jsonl",
        "iad_bench_splits.jsonl",
        "iad_bench_summary.jsonl",
        "label_provenance_summary.csv",
        "dataset_card.md",
    ]
    for file_name in required_iad_bench_files:
        file_path = iad_bench_dir / file_name
        errors.extend(check_non_empty_file(file_path))
        if file_path.exists() and file_path.suffix == ".jsonl" and count_jsonl_records(file_path) == 0:
            errors.append(f"no JSONL records in output file: {file_path}")
    return errors


def run_fixture_rebuild(python_executable: str, output_root: Path) -> list[str]:
    """Run fixture rebuild commands and check their outputs.

    参数:
        python_executable: Python executable path.
        output_root: Output root directory.

    返回:
        list[str]: Error messages collected during output verification.
    """
    output_root.mkdir(parents=True, exist_ok=True)
    environment = build_subprocess_environment(PROJECT_ROOT)
    cli_errors = check_cli_discovery(python_executable, environment)
    if cli_errors:
        return cli_errors
    for command in build_fixture_commands(python_executable, output_root):
        run_command(command, environment)
    return check_rebuild_outputs(output_root)


def main() -> int:
    """Run the fixture rebuild verification entry point.

    参数:
        无。

    返回:
        int: Process exit code.
    """
    args = parse_arguments()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")
    if args.work_dir:
        output_root = Path(args.work_dir).resolve()
        cleanup = False
    else:
        output_root = Path(tempfile.mkdtemp(prefix="iad_sieve_fixture_rebuild_"))
        cleanup = not args.keep_work_dir

    try:
        errors = run_fixture_rebuild(args.python, output_root)
        if errors:
            for error in errors:
                LOGGER.error(error)
            return 1
        LOGGER.info("fixture rebuild verification passed: %s", output_root)
        return 0
    finally:
        if cleanup:
            shutil.rmtree(output_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
