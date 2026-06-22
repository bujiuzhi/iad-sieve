"""Diagnose the local LaTeX/PDF build environment.

This script is intentionally diagnostic. It does not rebuild manuscript PDFs and
does not replace the strict LaTeX build gate. It helps authors distinguish TeX
source problems from local engine, bundle, or Tectonic runtime failures.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOGS = [
    ROOT / "build" / "logs" / "main.log",
    ROOT / "build" / "logs" / "supplementary_material.log",
    ROOT / "build" / "logs" / "elsevier_draft.log",
]
LATEX_ENGINES = ["tectonic", "latexmk", "pdflatex", "xelatex"]
TECTONIC_RUNTIME_PATTERNS = [
    re.compile(r"panicked at", re.IGNORECASE),
    re.compile(r"event loop thread panicked", re.IGNORECASE),
    re.compile(r"Attempted to create a NULL object", re.IGNORECASE),
    re.compile(r"system-configuration", re.IGNORECASE),
    re.compile(r"reqwest", re.IGNORECASE),
]


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Diagnose the local LaTeX/PDF build environment.")
    parser.add_argument(
        "--log",
        action="append",
        default=[],
        help="LaTeX build log to inspect. May be passed multiple times.",
    )
    parser.add_argument(
        "--bundle-dir",
        default=os.environ.get("TECTONIC_BUNDLE_DIR", ""),
        help="Local Tectonic bundle directory. Defaults to TECTONIC_BUNDLE_DIR.",
    )
    parser.add_argument(
        "--skip-smoke-test",
        action="store_true",
        help="Skip the minimal Tectonic compile smoke test and inspect only installed commands, bundle path, and logs.",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    return parser.parse_args()


def command_version(command_name: str) -> str:
    """Return a short version string for a local command.

    Args:
        command_name: Executable name to inspect.

    Returns:
        str: First output line from the command version check, or an error note.
    """
    command_path = shutil.which(command_name)
    if command_path is None:
        return "missing"
    version_command = [command_name, "--version"]
    try:
        completed = subprocess.run(version_command, check=False, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"available at {command_path}; version check failed: {exc}"
    version_text = completed.stdout.strip() or completed.stderr.strip()
    first_line = version_text.splitlines()[0] if version_text else "version output empty"
    return f"{command_path}: {first_line}"


def check_engine_availability(engine_names: list[str] | None = None) -> tuple[list[str], list[str]]:
    """Check whether at least one supported LaTeX engine is installed.

    Args:
        engine_names: Optional engine names to inspect.

    Returns:
        tuple[list[str], list[str]]: Warnings and errors.
    """
    engine_names = engine_names or LATEX_ENGINES
    warnings: list[str] = []
    available_engines: list[str] = []
    for engine_name in engine_names:
        version = command_version(engine_name)
        warnings.append(f"{engine_name}: {version}")
        if version != "missing":
            available_engines.append(engine_name)
    errors: list[str] = []
    if not available_engines:
        errors.append("no supported LaTeX engine found: tectonic, latexmk, pdflatex, or xelatex")
    return warnings, errors


def check_bundle_directory(bundle_dir: str) -> tuple[list[str], list[str]]:
    """Check optional Tectonic bundle configuration.

    Args:
        bundle_dir: Tectonic bundle directory path.

    Returns:
        tuple[list[str], list[str]]: Warnings and errors.
    """
    if not bundle_dir.strip():
        return ["TECTONIC_BUNDLE_DIR is not set; Tectonic may use its default bundle resolution."], []
    bundle_path = Path(bundle_dir).expanduser()
    if not bundle_path.is_dir():
        return [], [f"TECTONIC_BUNDLE_DIR does not point to a directory: {bundle_path}"]
    return [f"TECTONIC_BUNDLE_DIR points to a local directory: {bundle_path}"], []


def analyze_log_text(log_text: str, log_name: str) -> list[str]:
    """Inspect one LaTeX build log for engine-level runtime failures.

    Args:
        log_text: Build log text.
        log_name: Human-readable log name.

    Returns:
        list[str]: Diagnostic errors found in the log.
    """
    errors: list[str] = []
    lowered_text = log_text.casefold()
    has_panic = "panicked at" in lowered_text or "event loop thread panicked" in lowered_text
    has_tectonic_runtime_marker = "reqwest" in lowered_text or "system-configuration" in lowered_text
    if has_panic and has_tectonic_runtime_marker:
        errors.append(
            f"{log_name} contains a Tectonic/Rust runtime panic; check TECTONIC_BUNDLE_DIR or reinstall Tectonic"
        )
    for pattern in TECTONIC_RUNTIME_PATTERNS:
        match = pattern.search(log_text)
        if match is not None:
            errors.append(f"{log_name} contains LaTeX engine runtime marker: {match.group(0)}")
    return sorted(set(errors))


def analyze_log_files(log_paths: list[Path]) -> list[str]:
    """Inspect LaTeX build logs for diagnostic runtime failures.

    Args:
        log_paths: Build log paths.

    Returns:
        list[str]: Diagnostic errors found in existing logs.
    """
    errors: list[str] = []
    for log_path in log_paths:
        if not log_path.exists():
            errors.append(f"missing LaTeX build log for diagnosis: {log_path}")
            continue
        try:
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"cannot read LaTeX build log {log_path}: {exc}")
            continue
        errors.extend(analyze_log_text(log_text, log_path.name))
    return errors


def check_tectonic_smoke_test(bundle_dir: str, timeout_seconds: int = 15) -> tuple[list[str], list[str]]:
    """Compile a minimal document to detect runtime failures before manuscript builds.

    Args:
        bundle_dir: Optional Tectonic bundle directory.
        timeout_seconds: Maximum seconds to wait for the smoke compile.

    Returns:
        tuple[list[str], list[str]]: Warnings and errors from the smoke test.
    """
    if shutil.which("tectonic") is None:
        return ["Tectonic smoke test skipped because tectonic is missing."], []
    with tempfile.TemporaryDirectory(prefix="iad-sieve-tectonic-smoke-") as temporary_directory:
        smoke_tex = Path(temporary_directory) / "smoke.tex"
        smoke_tex.write_text(
            "\\documentclass{article}\n\\begin{document}\nIAD-Sieve LaTeX smoke test.\n\\end{document}\n",
            encoding="utf-8",
        )
        command = ["tectonic", "-C"]
        if bundle_dir.strip():
            command.extend(["--bundle", str(Path(bundle_dir).expanduser())])
        command.append(str(smoke_tex))
        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            return [], [f"Tectonic smoke test timed out after {timeout_seconds} seconds: {exc}"]
        except OSError as exc:
            return [], [f"Tectonic smoke test failed to start: {exc}"]
    combined_output = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    runtime_errors = analyze_log_text(combined_output, "tectonic smoke test")
    errors = list(runtime_errors)
    if completed.returncode != 0 and not runtime_errors:
        errors.append(f"Tectonic smoke test failed with exit code {completed.returncode}")
    if errors:
        return [], errors
    return ["Tectonic smoke test completed without runtime panic."], []


def diagnose_latex_environment(
    log_paths: list[Path],
    bundle_dir: str,
    run_smoke_test: bool = True,
) -> tuple[list[str], list[str]]:
    """Diagnose local LaTeX engine, bundle, and recent build logs.

    Args:
        log_paths: Log paths to inspect.
        bundle_dir: Optional Tectonic bundle directory.
        run_smoke_test: Whether to run a minimal Tectonic compile smoke test.

    Returns:
        tuple[list[str], list[str]]: Warnings and errors.
    """
    warnings, errors = check_engine_availability()
    bundle_warnings, bundle_errors = check_bundle_directory(bundle_dir)
    warnings.extend(bundle_warnings)
    errors.extend(bundle_errors)
    errors.extend(analyze_log_files(log_paths))
    if run_smoke_test:
        smoke_warnings, smoke_errors = check_tectonic_smoke_test(bundle_dir)
        warnings.extend(smoke_warnings)
        errors.extend(smoke_errors)
    return warnings, errors


def main() -> int:
    """Run LaTeX environment diagnostics.

    Returns:
        int: Process exit code.
    """
    args = parse_arguments()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO), format="%(levelname)s %(message)s")
    log_paths = [Path(log_path).resolve() for log_path in args.log] if args.log else DEFAULT_LOGS
    warnings, errors = diagnose_latex_environment(log_paths, args.bundle_dir, not args.skip_smoke_test)
    for warning in warnings:
        LOGGER.warning(warning)
    if errors:
        for error in errors:
            LOGGER.error(error)
        return 1
    LOGGER.info("LaTeX environment diagnosis found no blocking issue in inspected inputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
