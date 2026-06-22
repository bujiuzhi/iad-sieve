"""Build a provisional Elsevier elsarticle draft from the main manuscript.

The generated draft is a target-journal preview for Data & Knowledge
Engineering preparation. It remains anonymous and must not be treated as the
final upload file until the target journal, author metadata, and artifact
release are confirmed.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
from pathlib import Path


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "main.tex"
DEFAULT_KEYWORDS = ROOT / "keywords.md"
DEFAULT_OUTPUT_TEX = ROOT / "build" / "iad-risk-manuscript-elsevier.tex"
DEFAULT_OUTPUT_PDF = ROOT / "build" / "iad-risk-manuscript-elsevier.pdf"


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    参数:
        无。

    返回:
        argparse.Namespace: Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Build a provisional Elsevier elsarticle draft.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Input main manuscript LaTeX file.")
    parser.add_argument("--keywords", default=str(DEFAULT_KEYWORDS), help="Input keyword Markdown file.")
    parser.add_argument("--output-tex", default=str(DEFAULT_OUTPUT_TEX), help="Generated Elsevier LaTeX output.")
    parser.add_argument("--output-pdf", default=str(DEFAULT_OUTPUT_PDF), help="Generated Elsevier PDF output.")
    parser.add_argument("--no-pdf", action="store_true", help="Only write the generated LaTeX source.")
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    return parser.parse_args()


def extract_required_regex(pattern: str, text: str, field_name: str) -> str:
    """Extract a required regex group from manuscript text.

    参数:
        pattern: Regex pattern with one capture group.
        text: Source text to search.
        field_name: Human-readable field name for error messages.

    返回:
        str: Extracted and stripped group content.

    异常:
        ValueError: Raised when the field cannot be located.
    """
    match = re.search(pattern, text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"cannot locate required LaTeX field: {field_name}")
    return match.group(1).strip()


def extract_main_body(manuscript_text: str) -> str:
    """Extract body content between abstract and bibliography commands.

    参数:
        manuscript_text: Source manuscript LaTeX text.

    返回:
        str: Main manuscript body without front matter or bibliography commands.

    异常:
        ValueError: Raised when required boundaries are missing.
    """
    abstract_end = r"\end{abstract}"
    bibliography_marker = r"\bibliographystyle"
    if abstract_end not in manuscript_text:
        raise ValueError("cannot locate abstract end marker")
    if bibliography_marker not in manuscript_text:
        raise ValueError("cannot locate bibliography style marker")
    return manuscript_text.split(abstract_end, 1)[1].split(bibliography_marker, 1)[0].strip()


def load_keywords(keywords_path: Path) -> list[str]:
    """Load semicolon-separated submission keywords.

    参数:
        keywords_path: Markdown file containing submission keywords.

    返回:
        list[str]: Keyword entries.

    异常:
        ValueError: Raised when keyword count is outside the Elsevier-compatible range.
    """
    keywords_text = keywords_path.read_text(encoding="utf-8")
    keyword_lines = [line.strip() for line in keywords_text.splitlines() if line.strip() and not line.startswith("#")]
    keywords = [keyword.strip() for keyword in " ".join(keyword_lines).split(";") if keyword.strip()]
    if not 1 <= len(keywords) <= 7:
        raise ValueError(f"expected 1 to 7 keywords, found {len(keywords)}")
    return keywords


def build_elsevier_latex(manuscript_text: str, keywords: list[str]) -> str:
    """Build provisional Elsevier elsarticle LaTeX source.

    参数:
        manuscript_text: Source manuscript LaTeX text.
        keywords: Elsevier keyword entries.

    返回:
        str: Generated elsarticle LaTeX source.
    """
    title = extract_required_regex(r"\\title\{(.+?)\}", manuscript_text, "title")
    abstract = extract_required_regex(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", manuscript_text, "abstract")
    body = extract_main_body(manuscript_text)
    keyword_text = r" \sep ".join(keywords)
    return "\n".join(
        [
            r"\documentclass[preprint,12pt]{elsarticle}",
            "",
            r"\usepackage{booktabs}",
            r"\usepackage{float}",
            r"\usepackage{amsmath}",
            r"\usepackage{amssymb}",
            r"\usepackage{array}",
            r"\usepackage{graphicx}",
            r"\usepackage{xcolor}",
            r"\usepackage{tikz}",
            r"\usepackage[hidelinks]{hyperref}",
            r"\usetikzlibrary{arrows.meta,positioning}",
            r"\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}",
            r"\emergencystretch=3em",
            r"\biboptions{numbers,sort&compress}",
            "",
            r"\journal{Data \& Knowledge Engineering}",
            "",
            r"\begin{document}",
            r"\begin{frontmatter}",
            "",
            rf"\title{{{title}}}",
            r"\author{Anonymous Authors}",
            "",
            r"\begin{abstract}",
            abstract,
            r"\end{abstract}",
            "",
            r"\begin{keyword}",
            keyword_text,
            r"\end{keyword}",
            "",
            r"\end{frontmatter}",
            "",
            body,
            "",
            r"\bibliographystyle{elsarticle-num}",
            r"\bibliography{../references}",
            r"\end{document}",
            "",
        ]
    )


def run_tectonic(output_tex: Path, output_pdf: Path) -> None:
    """Compile generated Elsevier LaTeX source with tectonic.

    参数:
        output_tex: Generated LaTeX source path.
        output_pdf: Expected PDF path.

    返回:
        无。

    异常:
        RuntimeError: Raised when tectonic fails or the PDF is missing.
    """
    run_latex_environment_preflight()
    command = ["tectonic"]
    bundle_dir = os.environ.get("TECTONIC_BUNDLE_DIR")
    if bundle_dir:
        command.extend(["--bundle", bundle_dir])
    command.append(output_tex.name)
    try:
        subprocess.run(command, cwd=output_tex.parent, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError("tectonic is required to build the Elsevier preview PDF") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"tectonic failed while building {output_tex.name}") from exc
    generated_pdf = output_tex.with_suffix(".pdf")
    if not generated_pdf.exists():
        raise RuntimeError(f"tectonic did not create expected PDF: {generated_pdf}")
    if generated_pdf != output_pdf:
        output_pdf.write_bytes(generated_pdf.read_bytes())
        generated_pdf.unlink()


def run_latex_environment_preflight() -> None:
    """Run the LaTeX environment diagnostic before invoking Tectonic.

    参数:
        无。

    返回:
        无。

    异常:
        RuntimeError: Raised when the diagnostic detects an engine or bundle problem.
    """
    diagnostic_script = Path(__file__).with_name("diagnose_latex_environment.py")
    command = ["python", str(diagnostic_script), "--skip-logs"]
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError("python is required to run the LaTeX environment diagnostic") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("LaTeX environment diagnostic failed before Elsevier PDF build") from exc


def build_draft(source_path: Path, keywords_path: Path, output_tex: Path, output_pdf: Path | None) -> dict[str, str]:
    """Build the provisional Elsevier draft files.

    参数:
        source_path: Main manuscript source path.
        keywords_path: Keyword Markdown path.
        output_tex: Generated Elsevier source path.
        output_pdf: Optional generated Elsevier PDF path.

    返回:
        dict[str, str]: Paths for generated artifacts.
    """
    manuscript_text = source_path.read_text(encoding="utf-8")
    keywords = load_keywords(keywords_path)
    output_tex.parent.mkdir(parents=True, exist_ok=True)
    output_tex.write_text(build_elsevier_latex(manuscript_text, keywords), encoding="utf-8")
    result = {"output_tex": str(output_tex)}
    if output_pdf is not None:
        run_tectonic(output_tex, output_pdf)
        result["output_pdf"] = str(output_pdf)
    return result


def main() -> int:
    """Run the Elsevier draft build command.

    参数:
        无。

    返回:
        int: Process exit code.
    """
    args = parse_arguments()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")
    try:
        result = build_draft(
            source_path=Path(args.source),
            keywords_path=Path(args.keywords),
            output_tex=Path(args.output_tex),
            output_pdf=None if args.no_pdf else Path(args.output_pdf),
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Elsevier draft build failed: %s", exc)
        return 1
    LOGGER.info("Elsevier draft built: %s", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
