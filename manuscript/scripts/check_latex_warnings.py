"""Check LaTeX build logs for submission-blocking layout warnings.

The checker turns severe overfull boxes, unresolved references, missing
citations, and fatal TeX errors into an automated manuscript gate. Mild
underfull boxes are tolerated because they are common in bibliography entries.
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOGS = [
    ROOT / "build" / "logs" / "main.log",
    ROOT / "build" / "logs" / "supplementary_material.log",
    ROOT / "build" / "logs" / "elsevier_draft.log",
]
OVERFULL_PATTERN = re.compile(r"Overfull \\hbox \((?P<points>[0-9]+(?:\.[0-9]+)?)pt too wide\)")


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    参数:
        无。

    返回:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Check LaTeX build logs for severe manuscript warnings.")
    parser.add_argument(
        "--log",
        action="append",
        default=[],
        help="Build log path. May be passed multiple times. Defaults to manuscript/build/logs/*.log.",
    )
    parser.add_argument(
        "--max-overfull-pt",
        type=float,
        default=5.0,
        help="Maximum tolerated overfull hbox width in points.",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    return parser.parse_args()


def check_log_text(log_text: str, log_name: str, max_overfull_pt: float = 5.0) -> list[str]:
    """Check one LaTeX build log text.

    参数:
        log_text: Log text emitted by the build command.
        log_name: Human-readable log name.
        max_overfull_pt: Maximum tolerated overfull hbox width in points.

    返回:
        list[str]: Error messages. Empty means the log passed.
    """
    errors: list[str] = []
    for match in OVERFULL_PATTERN.finditer(log_text):
        points = float(match.group("points"))
        if points > max_overfull_pt:
            errors.append(f"{log_name} has severe overfull hbox: {points:.3f}pt > {max_overfull_pt:.3f}pt")

    for line_number, line in enumerate(log_text.splitlines(), start=1):
        normalized = line.strip()
        if not normalized:
            continue
        if "undefined references" in normalized:
            errors.append(f"{log_name}:{line_number} has unresolved references: {normalized}")
        elif "LaTeX Warning: Citation" in normalized and "undefined" in normalized:
            errors.append(f"{log_name}:{line_number} has unresolved citation: {normalized}")
        elif "LaTeX Warning: Reference" in normalized and "undefined" in normalized:
            errors.append(f"{log_name}:{line_number} has unresolved reference: {normalized}")
        elif any(marker in normalized for marker in ["Undefined control sequence", "Emergency stop", "Fatal error"]):
            errors.append(f"{log_name}:{line_number} has fatal TeX marker: {normalized}")
        elif "No pages of output" in normalized:
            errors.append(f"{log_name}:{line_number} reports no PDF output: {normalized}")
    return errors


def check_log_files(log_paths: list[Path], max_overfull_pt: float = 5.0) -> list[str]:
    """Check LaTeX build log files.

    参数:
        log_paths: Log file paths.
        max_overfull_pt: Maximum tolerated overfull hbox width in points.

    返回:
        list[str]: Error messages. Empty means all logs passed.
    """
    errors: list[str] = []
    for log_path in log_paths:
        if not log_path.exists():
            errors.append(f"missing LaTeX build log: {log_path}")
            continue
        try:
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errors.append(f"cannot read LaTeX build log {log_path}: {exc}")
            continue
        errors.extend(check_log_text(log_text, log_path.name, max_overfull_pt))
    return errors


def main() -> int:
    """Run LaTeX warning checks.

    参数:
        无。

    返回:
        int: Process exit code.
    """
    args = parse_arguments()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO), format="%(levelname)s %(message)s")
    log_paths = [Path(log_path).resolve() for log_path in args.log] if args.log else DEFAULT_LOGS
    errors = check_log_files(log_paths, args.max_overfull_pt)
    if errors:
        for error in errors:
            LOGGER.error(error)
        return 1
    LOGGER.info("LaTeX warning check passed for %d log(s)", len(log_paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
