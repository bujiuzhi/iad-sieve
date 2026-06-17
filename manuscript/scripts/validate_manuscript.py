"""Validate the manuscript package before journal submission.

The validation checks file completeness, unsupported claim wording, core section
coverage, PDF readability, and local LaTeX toolchain availability.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
from pathlib import Path


LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    ROOT / "main.tex",
    ROOT / "supplementary_material.tex",
    ROOT / "references.bib",
    ROOT / "README.md",
    ROOT / "MANIFEST.md",
    ROOT / "cover_letter.md",
    ROOT / "highlights.md",
    ROOT / "keywords.md",
    ROOT / "scripts" / "validate_manuscript.py",
    ROOT / "scripts" / "verify_fixture_rebuild.py",
    ROOT / "scripts" / "build_latex_pdf.sh",
    ROOT / "build" / "iad-risk-manuscript-latex.pdf",
    ROOT / "build" / "iad-risk-supplementary-material.pdf",
]
REQUIRED_SECTIONS = [
    r"\begin{abstract}",
    r"\section{Introduction}",
    r"\section{Related Work}",
    r"\section{Problem Formulation}",
    r"\subsection{Notation and Relation Semantics}",
    r"\section{IAD-Bench}",
    r"\section{Method}",
    r"\subsection{Training Objective}",
    r"\subsection{Failure-Control Rationale}",
    r"\subsection{Implementation and Reproducibility}",
    r"\section{Experiments}",
    r"\subsection{Threshold Selection and Uncertainty Reporting}",
    r"\subsection{Claim-Evidence Boundary for Result Interpretation}",
    r"\section{Mechanism and Error Analysis}",
    r"\section{Limitations}",
    r"\section{Threats to Validity}",
    r"\section{Conclusion}",
    r"\section*{Data and Code Availability}",
    r"\section*{Ethics Statement}",
    r"\section*{Competing Interests}",
]
REQUIRED_SUPPLEMENT_SECTIONS = [
    r"\section{Scope}",
    r"\section{Reproduction Levels}",
    r"\section{No-Network Fixture Rebuild}",
    r"\section{Public-Source Rebuild}",
    r"\section{Artifact Package Requirements}",
    r"\section{Claim-Evidence Matrix}",
    r"\section{Uncertainty and Ablation Requirements}",
    r"\section{Claim Boundary}",
]
MIN_BIB_ENTRIES = 10
FORBIDDEN_PHRASES = [
    "state-of-the-art",
    "state of the art",
    "SOTA",
    "human gold has been completed",
    "completed human gold",
    "OpenAlex labels are gold",
    "OpenCitations labels are gold",
    "universal superiority",
    "all scholarly domains",
]


def parse_arguments() -> argparse.Namespace:
    """Parse validation command arguments.

    参数:
        无。

    返回:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Validate the manuscript package.")
    parser.add_argument("--strict-latex", action="store_true", help="Fail if no local LaTeX engine is available.")
    return parser.parse_args()


def check_required_files() -> list[str]:
    """Check whether all required manuscript files exist.

    参数:
        无。

    返回:
        list[str]: Error messages for missing files.
    """
    errors = []
    for path in REQUIRED_FILES:
        if not path.exists():
            errors.append(f"missing required file: {path.relative_to(ROOT)}")
    return errors


def check_sections(document_text: str, required_sections: list[str], document_name: str) -> list[str]:
    """Check required document sections.

    参数:
        document_text: LaTeX document source.
        required_sections: Required section markers.
        document_name: Human-readable document name.

    返回:
        list[str]: Error messages for missing sections.
    """
    return [f"{document_name} missing required section marker: {section}" for section in required_sections if section not in document_text]


def check_forbidden_claims(manuscript_text: str) -> list[str]:
    """Check forbidden unsupported claims in the manuscript.

    参数:
        manuscript_text: LaTeX manuscript source.

    返回:
        list[str]: Error messages for forbidden phrases.
    """
    lowered_text = manuscript_text.lower()
    errors = []
    for phrase in FORBIDDEN_PHRASES:
        if phrase.lower() in lowered_text:
            errors.append(f"forbidden or unsafe claim phrase found: {phrase}")
    return errors


def check_bibliography_depth(bibliography_text: str) -> list[str]:
    """Check whether the bibliography has enough source coverage.

    参数:
        bibliography_text: BibTeX source text.

    返回:
        list[str]: Error messages for insufficient bibliography depth.
    """
    entry_count = bibliography_text.count("@")
    if entry_count < MIN_BIB_ENTRIES:
        return [f"bibliography has {entry_count} entries; expected at least {MIN_BIB_ENTRIES}"]
    return []


def check_highlights(highlights_text: str) -> list[str]:
    """Check submission highlights format and scope.

    参数:
        highlights_text: Highlights Markdown text.

    返回:
        list[str]: Error messages for invalid highlights.
    """
    bullet_lines = [line for line in highlights_text.splitlines() if line.startswith("- ")]
    errors: list[str] = []
    if not 3 <= len(bullet_lines) <= 6:
        errors.append(f"highlights has {len(bullet_lines)} bullet lines; expected 3 to 6")
    for line in bullet_lines:
        word_count = len(line[2:].split())
        if word_count > 22:
            errors.append(f"highlight is too long ({word_count} words): {line}")
    return errors


def check_keywords(keywords_text: str) -> list[str]:
    """Check submission keyword count and format.

    参数:
        keywords_text: Keywords Markdown text.

    返回:
        list[str]: Error messages for invalid keywords.
    """
    keyword_lines = [line.strip() for line in keywords_text.splitlines() if line.strip() and not line.startswith("#")]
    keyword_text = " ".join(keyword_lines)
    keywords = [keyword.strip() for keyword in keyword_text.split(";") if keyword.strip()]
    errors: list[str] = []
    if not 4 <= len(keywords) <= 8:
        errors.append(f"keywords has {len(keywords)} entries; expected 4 to 8")
    for keyword in keywords:
        word_count = len(keyword.split())
        if word_count > 5:
            errors.append(f"keyword is too long ({word_count} words): {keyword}")
    return errors


def extract_first_page_text(pdf_path: Path) -> tuple[str, list[str]]:
    """Extract text from the first page of a PDF.

    参数:
        pdf_path: PDF file path.

    返回:
        tuple[str, list[str]]: Extracted first-page text and extraction errors.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        if len(reader.pages) < 1:
            return "", ["PDF has no pages"]
        return reader.pages[0].extract_text() or "", []
    except ModuleNotFoundError:
        LOGGER.info("pypdf is not installed; falling back to pdftotext for %s", pdf_path.name)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("pypdf failed for %s; falling back to pdftotext: %s", pdf_path.name, exc)

    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return "", ["pypdf is not installed and pdftotext is not available"]
    try:
        result = subprocess.run(
            [pdftotext, "-f", "1", "-l", "1", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout, []
    except subprocess.CalledProcessError as exc:
        return "", [f"pdftotext failed with exit code {exc.returncode}: {exc.stderr.strip()}"]


def check_pdf(pdf_path: Path, required_text: str = "IAD-Risk") -> list[str]:
    """Check whether a generated PDF is readable.

    参数:
        pdf_path: Path to the generated PDF.
        required_text: Text expected on the first page.

    返回:
        list[str]: Error messages for PDF readability issues.
    """
    errors = []
    first_page_text, extraction_errors = extract_first_page_text(pdf_path)
    errors.extend(f"{pdf_path.name} is not readable: {error}" for error in extraction_errors)
    if extraction_errors:
        return errors
    if required_text not in first_page_text:
        errors.append(f"{pdf_path.name} first page text does not contain required text: {required_text}")
    unresolved_markers = ["undefined references", "LaTeX Warning", "[?]", "??"]
    for marker in unresolved_markers:
        if marker in first_page_text:
            errors.append(f"{pdf_path.name} may contain unresolved marker on first page: {marker}")
    return errors


def check_pdf_freshness(pdf_path: Path, source_path: Path) -> list[str]:
    """Check whether the generated PDF is newer than the LaTeX source.

    参数:
        pdf_path: Generated PDF path.
        source_path: Main LaTeX source path.

    返回:
        list[str]: Error messages for stale PDF output.
    """
    if not pdf_path.exists() or not source_path.exists():
        return []
    if pdf_path.stat().st_mtime < source_path.stat().st_mtime:
        return [f"{pdf_path.name} is older than {source_path.name}; rebuild the LaTeX PDF"]
    return []


def check_latex_toolchain(strict_latex: bool) -> tuple[list[str], list[str]]:
    """Check local LaTeX toolchain availability.

    参数:
        strict_latex: Whether missing LaTeX engines should fail the validation.

    返回:
        tuple[list[str], list[str]]: Warnings and errors.
    """
    engines = ["latexmk", "pdflatex", "xelatex", "tectonic"]
    found = [engine for engine in engines if shutil.which(engine)]
    if found:
        return [f"latex engine available: {', '.join(found)}"], []
    message = "no LaTeX engine found; PDF is preview-only until pdflatex/xelatex/latexmk/tectonic is installed"
    if strict_latex:
        return [], [message]
    return [message], []


def main() -> int:
    """Run manuscript validation checks.

    参数:
        无。

    返回:
        int: Process exit code.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_arguments()
    errors: list[str] = []
    warnings: list[str] = []
    errors.extend(check_required_files())
    manuscript_path = ROOT / "main.tex"
    manuscript_text = manuscript_path.read_text(encoding="utf-8") if manuscript_path.exists() else ""
    bibliography_path = ROOT / "references.bib"
    bibliography_text = bibliography_path.read_text(encoding="utf-8") if bibliography_path.exists() else ""
    errors.extend(check_sections(manuscript_text, REQUIRED_SECTIONS, "main manuscript"))
    supplementary_path = ROOT / "supplementary_material.tex"
    supplementary_text = supplementary_path.read_text(encoding="utf-8") if supplementary_path.exists() else ""
    highlights_path = ROOT / "highlights.md"
    highlights_text = highlights_path.read_text(encoding="utf-8") if highlights_path.exists() else ""
    keywords_path = ROOT / "keywords.md"
    keywords_text = keywords_path.read_text(encoding="utf-8") if keywords_path.exists() else ""
    errors.extend(check_sections(supplementary_text, REQUIRED_SUPPLEMENT_SECTIONS, "supplementary material"))
    errors.extend(check_forbidden_claims(manuscript_text))
    errors.extend(check_forbidden_claims(supplementary_text))
    errors.extend(check_forbidden_claims(highlights_text))
    errors.extend(check_forbidden_claims(keywords_text))
    errors.extend(check_highlights(highlights_text))
    errors.extend(check_keywords(keywords_text))
    errors.extend(check_bibliography_depth(bibliography_text))
    latex_pdf_path = ROOT / "build" / "iad-risk-manuscript-latex.pdf"
    supplementary_pdf_path = ROOT / "build" / "iad-risk-supplementary-material.pdf"
    errors.extend(check_pdf(latex_pdf_path))
    errors.extend(check_pdf_freshness(latex_pdf_path, manuscript_path))
    errors.extend(check_pdf(supplementary_pdf_path, "Supplementary Material"))
    errors.extend(check_pdf_freshness(supplementary_pdf_path, supplementary_path))
    latex_warnings, latex_errors = check_latex_toolchain(args.strict_latex)
    warnings.extend(latex_warnings)
    errors.extend(latex_errors)

    for warning in warnings:
        LOGGER.warning(warning)
    if errors:
        for error in errors:
            LOGGER.error(error)
        return 1
    LOGGER.info("manuscript validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
