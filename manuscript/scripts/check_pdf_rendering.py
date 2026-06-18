"""Check rendered PDF pages for blank or failed visual output.

The checker samples first, middle, and last pages from manuscript PDFs, renders
them with Poppler, and inspects PPM pixels with the Python standard library. It
is intended to catch blank pages, black pages, and rendering failures that text
extraction alone cannot detect.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDFS = [
    ROOT / "build" / "iad-risk-manuscript-latex.pdf",
    ROOT / "build" / "iad-risk-manuscript-elsevier.pdf",
    ROOT / "build" / "iad-risk-supplementary-material.pdf",
]


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    参数:
        无。

    返回:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Render and inspect sampled manuscript PDF pages.")
    parser.add_argument("--pdf", action="append", default=[], help="PDF path. May be passed multiple times.")
    parser.add_argument("--dpi", type=int, default=72, help="Render resolution for sampled pages.")
    parser.add_argument(
        "--min-non-white-ratio",
        type=float,
        default=0.002,
        help="Minimum non-white pixel ratio required for a page to be nonblank.",
    )
    parser.add_argument(
        "--max-dark-ratio",
        type=float,
        default=0.90,
        help="Maximum dark pixel ratio before a page is treated as failed rendering.",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    return parser.parse_args()


def require_command(command_name: str) -> tuple[str | None, list[str]]:
    """Locate a required command.

    参数:
        command_name: Command name to locate on PATH.

    返回:
        tuple[str | None, list[str]]: Command path and error messages.
    """
    command_path = shutil.which(command_name)
    if command_path is None:
        return None, [f"required PDF rendering command not found: {command_name}"]
    return command_path, []


def parse_pdf_page_count(pdfinfo_text: str) -> int:
    """Parse page count from pdfinfo output.

    参数:
        pdfinfo_text: Output text from pdfinfo.

    返回:
        int: Number of pages.

    异常:
        ValueError: Raised when the page count is missing or invalid.
    """
    for line in pdfinfo_text.splitlines():
        if line.startswith("Pages:"):
            raw_value = line.split(":", 1)[1].strip()
            page_count = int(raw_value)
            if page_count < 1:
                raise ValueError(f"invalid PDF page count: {page_count}")
            return page_count
    raise ValueError("pdfinfo output does not contain Pages field")


def get_pdf_page_count(pdf_path: Path, pdfinfo_command: str) -> tuple[int | None, list[str]]:
    """Read a PDF page count with pdfinfo.

    参数:
        pdf_path: PDF path.
        pdfinfo_command: Resolved pdfinfo command path.

    返回:
        tuple[int | None, list[str]]: Page count and error messages.
    """
    if not pdf_path.exists():
        return None, [f"PDF does not exist: {pdf_path}"]
    try:
        result = subprocess.run([pdfinfo_command, str(pdf_path)], check=True, capture_output=True, text=True)
        return parse_pdf_page_count(result.stdout), []
    except (subprocess.CalledProcessError, ValueError) as exc:
        return None, [f"cannot read PDF page count for {pdf_path.name}: {exc}"]


def sample_pages(page_count: int) -> list[int]:
    """Select first, middle, and last pages without duplicates.

    参数:
        page_count: Number of PDF pages.

    返回:
        list[int]: 1-based page numbers to inspect.
    """
    candidates = [1, (page_count + 1) // 2, page_count]
    return sorted(set(candidates))


def read_ppm_tokens(content: bytes, token_count: int = 4) -> tuple[list[bytes], int]:
    """Read PPM header tokens while respecting comments.

    参数:
        content: PPM file bytes.
        token_count: Number of header tokens to read.

    返回:
        tuple[list[bytes], int]: Header tokens and byte offset where pixel data starts.

    异常:
        ValueError: Raised when the PPM header is malformed.
    """
    tokens: list[bytes] = []
    offset = 0
    length = len(content)
    while len(tokens) < token_count:
        while offset < length and chr(content[offset]).isspace():
            offset += 1
        if offset >= length:
            raise ValueError("truncated PPM header")
        if content[offset : offset + 1] == b"#":
            while offset < length and content[offset : offset + 1] not in {b"\n", b"\r"}:
                offset += 1
            continue
        start = offset
        while offset < length and not chr(content[offset]).isspace():
            offset += 1
        tokens.append(content[start:offset])
    while offset < length and chr(content[offset]).isspace():
        offset += 1
    return tokens, offset


def load_ppm_pixels(ppm_path: Path) -> tuple[int, int, list[tuple[int, int, int]]]:
    """Load RGB pixels from a P3 or P6 PPM image.

    参数:
        ppm_path: PPM image path.

    返回:
        tuple[int, int, list[tuple[int, int, int]]]: Width, height, and RGB pixels.

    异常:
        ValueError: Raised when the PPM file is malformed or unsupported.
    """
    content = ppm_path.read_bytes()
    tokens, pixel_offset = read_ppm_tokens(content)
    magic = tokens[0]
    width = int(tokens[1])
    height = int(tokens[2])
    max_value = int(tokens[3])
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid PPM dimensions: {width}x{height}")
    if max_value <= 0 or max_value > 255:
        raise ValueError(f"unsupported PPM max value: {max_value}")
    expected_values = width * height * 3

    if magic == b"P6":
        pixel_bytes = content[pixel_offset:]
        if len(pixel_bytes) < expected_values:
            raise ValueError("truncated P6 pixel data")
        values = list(pixel_bytes[:expected_values])
    elif magic == b"P3":
        pixel_text = content[pixel_offset:].decode("ascii", errors="strict")
        values = [int(value) for value in pixel_text.split()]
        if len(values) < expected_values:
            raise ValueError("truncated P3 pixel data")
        values = values[:expected_values]
    else:
        raise ValueError(f"unsupported PPM format: {magic.decode('ascii', errors='replace')}")

    pixels = [(values[index], values[index + 1], values[index + 2]) for index in range(0, expected_values, 3)]
    return width, height, pixels


def analyze_pixels(
    width: int,
    height: int,
    pixels: list[tuple[int, int, int]],
    min_non_white_ratio: float,
    max_dark_ratio: float,
) -> list[str]:
    """Analyze rendered page pixels for blank or failed output.

    参数:
        width: Image width in pixels.
        height: Image height in pixels.
        pixels: RGB pixel list.
        min_non_white_ratio: Minimum non-white pixel ratio.
        max_dark_ratio: Maximum dark pixel ratio.

    返回:
        list[str]: Error messages.
    """
    pixel_count = width * height
    if pixel_count == 0 or len(pixels) < pixel_count:
        return ["rendered page has invalid pixel count"]
    non_white_count = sum(1 for red, green, blue in pixels if min(red, green, blue) < 250)
    dark_count = sum(1 for red, green, blue in pixels if max(red, green, blue) < 8)
    non_white_ratio = non_white_count / pixel_count
    dark_ratio = dark_count / pixel_count

    errors: list[str] = []
    if non_white_ratio < min_non_white_ratio:
        errors.append(
            f"rendered page appears blank: non_white_ratio={non_white_ratio:.6f} < {min_non_white_ratio:.6f}"
        )
    if dark_ratio > max_dark_ratio:
        errors.append(f"rendered page appears dark/failed: dark_ratio={dark_ratio:.6f} > {max_dark_ratio:.6f}")
    return errors


def render_pdf_page(pdf_path: Path, page_number: int, pdftoppm_command: str, output_dir: Path, dpi: int) -> Path:
    """Render one PDF page to a PPM image.

    参数:
        pdf_path: PDF path.
        page_number: 1-based page number.
        pdftoppm_command: Resolved pdftoppm command path.
        output_dir: Temporary render output directory.
        dpi: Render resolution.

    返回:
        Path: Rendered PPM path.

    异常:
        RuntimeError: Raised when pdftoppm does not write an output file.
        subprocess.CalledProcessError: Raised when pdftoppm fails.
    """
    output_prefix = output_dir / f"{pdf_path.stem}_p{page_number}"
    subprocess.run(
        [
            pdftoppm_command,
            "-r",
            str(dpi),
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-singlefile",
            str(pdf_path),
            str(output_prefix),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    ppm_path = output_prefix.with_suffix(".ppm")
    if not ppm_path.exists():
        raise RuntimeError(f"pdftoppm did not create expected PPM: {ppm_path}")
    return ppm_path


def check_pdf_rendering(
    pdf_path: Path,
    pdfinfo_command: str,
    pdftoppm_command: str,
    dpi: int = 72,
    min_non_white_ratio: float = 0.002,
    max_dark_ratio: float = 0.90,
) -> list[str]:
    """Render sampled pages from one PDF and inspect pixel output.

    参数:
        pdf_path: PDF path.
        pdfinfo_command: Resolved pdfinfo command path.
        pdftoppm_command: Resolved pdftoppm command path.
        dpi: Render resolution.
        min_non_white_ratio: Minimum non-white pixel ratio.
        max_dark_ratio: Maximum dark pixel ratio.

    返回:
        list[str]: Error messages.
    """
    page_count, page_errors = get_pdf_page_count(pdf_path, pdfinfo_command)
    if page_errors or page_count is None:
        return page_errors

    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="iad_sieve_pdf_render_") as temp_dir:
        output_dir = Path(temp_dir)
        for page_number in sample_pages(page_count):
            try:
                ppm_path = render_pdf_page(pdf_path, page_number, pdftoppm_command, output_dir, dpi)
                width, height, pixels = load_ppm_pixels(ppm_path)
                for error in analyze_pixels(width, height, pixels, min_non_white_ratio, max_dark_ratio):
                    errors.append(f"{pdf_path.name} page {page_number}: {error}")
            except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
                errors.append(f"{pdf_path.name} page {page_number} render check failed: {exc}")
    return errors


def check_pdf_files(
    pdf_paths: list[Path],
    dpi: int = 72,
    min_non_white_ratio: float = 0.002,
    max_dark_ratio: float = 0.90,
) -> list[str]:
    """Check rendered output for multiple PDFs.

    参数:
        pdf_paths: PDF paths.
        dpi: Render resolution.
        min_non_white_ratio: Minimum non-white pixel ratio.
        max_dark_ratio: Maximum dark pixel ratio.

    返回:
        list[str]: Error messages.
    """
    pdfinfo_command, pdfinfo_errors = require_command("pdfinfo")
    pdftoppm_command, pdftoppm_errors = require_command("pdftoppm")
    errors = pdfinfo_errors + pdftoppm_errors
    if errors or pdfinfo_command is None or pdftoppm_command is None:
        return errors

    for pdf_path in pdf_paths:
        errors.extend(
            check_pdf_rendering(
                pdf_path,
                pdfinfo_command,
                pdftoppm_command,
                dpi,
                min_non_white_ratio,
                max_dark_ratio,
            )
        )
    return errors


def main() -> int:
    """Run PDF rendering checks.

    参数:
        无。

    返回:
        int: Process exit code.
    """
    args = parse_arguments()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO), format="%(levelname)s %(message)s")
    pdf_paths = [Path(pdf_path).resolve() for pdf_path in args.pdf] if args.pdf else DEFAULT_PDFS
    errors = check_pdf_files(pdf_paths, args.dpi, args.min_non_white_ratio, args.max_dark_ratio)
    if errors:
        for error in errors:
            LOGGER.error(error)
        return 1
    LOGGER.info("PDF rendering check passed for %d PDF(s)", len(pdf_paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
