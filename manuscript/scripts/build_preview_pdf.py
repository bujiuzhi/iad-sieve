"""Build a PDF preview from the LaTeX manuscript source.

This script is a fallback for environments without a LaTeX engine. It extracts
readable prose from `main.tex` and creates a journal-style preview PDF. The
source of record remains `manuscript/main.tex`.
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer


LOGGER = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    参数:
        无。

    返回:
        argparse.Namespace: Parsed input and output paths.
    """
    parser = argparse.ArgumentParser(description="Build a PDF preview from manuscript/main.tex.")
    parser.add_argument("--input", required=True, help="Path to the LaTeX manuscript source.")
    parser.add_argument("--output", required=True, help="Path to the generated preview PDF.")
    return parser.parse_args()


def strip_latex_commands(raw_text: str) -> list[tuple[str, str]]:
    """Convert a limited LaTeX manuscript into sectioned plain text blocks.

    参数:
        raw_text: Raw LaTeX source text.

    返回:
        list[tuple[str, str]]: Tuples of block type and cleaned block text.
    """
    blocks: list[tuple[str, str]] = []
    in_abstract = False
    in_table = False
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%"):
            continue
        if line.startswith("\\begin{abstract}"):
            in_abstract = True
            blocks.append(("heading", "Abstract"))
            continue
        if line.startswith("\\end{abstract}"):
            in_abstract = False
            continue
        if line.startswith("\\begin{table}") or line.startswith("\\begin{tabular}"):
            in_table = True
            continue
        if line.startswith("\\end{table}") or line.startswith("\\end{tabular}"):
            in_table = False
            continue
        if line.startswith("\\caption"):
            caption = re.sub(r"\\caption\{(.*)\}", r"Table. \1", line)
            blocks.append(("body", clean_inline_latex(caption)))
            continue
        if in_table:
            continue
        section_match = re.match(r"\\section\{(.+)\}", line)
        subsection_match = re.match(r"\\subsection\{(.+)\}", line)
        title_match = re.match(r"\\title\{(.+)\}", line)
        author_match = re.match(r"\\author\{(.+)\}", line)
        if title_match:
            blocks.append(("title", clean_inline_latex(title_match.group(1))))
            continue
        if author_match:
            blocks.append(("body", clean_inline_latex(author_match.group(1))))
            continue
        if section_match:
            blocks.append(("heading", clean_inline_latex(section_match.group(1))))
            continue
        if subsection_match:
            blocks.append(("subheading", clean_inline_latex(subsection_match.group(1))))
            continue
        if line.startswith("\\") or line in {"}", "{"}:
            continue
        block_type = "body" if not in_abstract else "abstract"
        blocks.append((block_type, clean_inline_latex(line)))
    return blocks


def clean_inline_latex(text: str) -> str:
    """Remove common inline LaTeX commands while preserving readable text.

    参数:
        text: A LaTeX line or fragment.

    返回:
        str: Plain text suitable for PDF preview rendering.
    """
    cleaned = text
    replacements = {
        r"\\emph\{([^{}]+)\}": r"\1",
        r"\\citet?\{([^{}]+)\}": r"[\1]",
        r"\\citep\{([^{}]+)\}": r"[\1]",
        r"\\mathrm\{([^{}]+)\}": r"\1",
    }
    for pattern, replacement in replacements.items():
        cleaned = re.sub(pattern, replacement, cleaned)
    cleaned = cleaned.replace("\\_", "_")
    cleaned = cleaned.replace("\\%", "%")
    cleaned = cleaned.replace("$", "")
    cleaned = re.sub(r"\\[a-zA-Z]+", "", cleaned)
    cleaned = cleaned.replace("{", "").replace("}", "")
    cleaned = cleaned.replace("&", " and ")
    cleaned = cleaned.replace("\\", "")
    return " ".join(cleaned.split())


def build_pdf(blocks: list[tuple[str, str]], output_path: Path) -> None:
    """Render extracted manuscript blocks into a PDF preview.

    参数:
        blocks: Sectioned text blocks.
        output_path: Destination PDF path.

    返回:
        无。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="PaperTitle", parent=styles["Title"], fontSize=16, leading=20, spaceAfter=12))
    styles.add(ParagraphStyle(name="PaperHeading", parent=styles["Heading1"], fontSize=13, leading=16, spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name="PaperSubheading", parent=styles["Heading2"], fontSize=11, leading=14, spaceBefore=8, spaceAfter=4))
    styles.add(ParagraphStyle(name="PaperBody", parent=styles["BodyText"], fontSize=9.5, leading=12, firstLineIndent=0.18 * inch, spaceAfter=5))
    styles.add(ParagraphStyle(name="PaperAbstract", parent=styles["BodyText"], fontSize=9.5, leading=12, leftIndent=0.15 * inch, rightIndent=0.15 * inch, spaceAfter=6))

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.85 * inch,
        leftMargin=0.85 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="IAD-Risk Manuscript Preview",
    )
    story = []
    for block_type, text in blocks:
        if not text:
            continue
        if block_type == "title":
            story.append(Paragraph(text, styles["PaperTitle"]))
        elif block_type == "heading":
            if text == "References":
                story.append(PageBreak())
            story.append(Paragraph(text, styles["PaperHeading"]))
        elif block_type == "subheading":
            story.append(Paragraph(text, styles["PaperSubheading"]))
        elif block_type == "abstract":
            story.append(Paragraph(text, styles["PaperAbstract"]))
        else:
            story.append(Paragraph(text, styles["PaperBody"]))
        story.append(Spacer(1, 2))
    document.build(story, onFirstPage=draw_page_background, onLaterPages=draw_page_background)
    LOGGER.info("Preview PDF written: %s", output_path)


def draw_page_background(canvas, document) -> None:
    """Draw an opaque white page background before rendering text.

    参数:
        canvas: ReportLab canvas object for the current page.
        document: ReportLab document object with page dimensions.

    返回:
        无。
    """
    del document
    canvas.saveState()
    canvas.setFillColorRGB(1, 1, 1)
    canvas.rect(0, 0, letter[0], letter[1], stroke=0, fill=1)
    canvas.setFillColorRGB(0, 0, 0)
    canvas.restoreState()


def main() -> int:
    """Run the PDF preview builder.

    参数:
        无。

    返回:
        int: Process exit code.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_arguments()
    input_path = Path(args.input)
    output_path = Path(args.output)
    try:
        raw_text = input_path.read_text(encoding="utf-8")
        blocks = strip_latex_commands(raw_text)
        build_pdf(blocks, output_path)
    except Exception:
        LOGGER.exception("Failed to build preview PDF")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
