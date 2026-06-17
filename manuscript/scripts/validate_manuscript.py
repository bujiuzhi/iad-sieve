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
    ROOT / "submission_metadata.yml",
    ROOT / "scripts" / "validate_manuscript.py",
    ROOT / "scripts" / "verify_fixture_rebuild.py",
    ROOT / "scripts" / "build_submission_package.py",
    ROOT / "scripts" / "validate_submission_package.py",
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
    r"\subsection{Implementation Details}",
    r"\subsection{Feature and Head Specification}",
    r"\subsection{Implementation and Reproducibility}",
    r"\section{Experiments}",
    r"\subsection{Split and Leakage Controls}",
    r"\subsection{Threshold Selection and Uncertainty Reporting}",
    r"\subsection{Operating Point Disclosure}",
    r"\subsection{Claim-Evidence Boundary for Result Interpretation}",
    r"\subsection{Result Audit Trail}",
    r"\subsection{Scope Compatibility of the Open-v2 Table}",
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
    "Universal method superiority",
    "all scholarly domains",
]
AUXILIARY_MODEL_EVIDENCE_PHRASES = [
    "LLM",
    "GPT",
    "OpenAI",
    "ChatGPT",
    "pair-judge",
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
    parser.add_argument("--final-upload", action="store_true", help="Require target journal and real author metadata.")
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


def check_auxiliary_model_evidence_absent(document_texts: dict[str, str]) -> list[str]:
    """Check whether formal submission materials exclude unsupported auxiliary model evidence.

    参数:
        document_texts: Mapping from document name to formal submission text.

    返回:
        list[str]: Error messages for auxiliary model evidence phrases.
    """
    errors: list[str] = []
    for document_name, document_text in document_texts.items():
        lowered_text = document_text.lower()
        for phrase in AUXILIARY_MODEL_EVIDENCE_PHRASES:
            if phrase.lower() in lowered_text:
                errors.append(f"{document_name} contains unsupported auxiliary model evidence phrase: {phrase}")
    return errors


def check_abstract_quantitative_evidence(manuscript_text: str) -> list[str]:
    """Check whether the abstract reports bounded quantitative evidence.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing abstract evidence markers.
    """
    begin_marker = r"\begin{abstract}"
    end_marker = r"\end{abstract}"
    if begin_marker not in manuscript_text or end_marker not in manuscript_text:
        return ["abstract evidence check could not locate abstract environment"]
    abstract_text = manuscript_text.split(begin_marker, 1)[1].split(end_marker, 1)[0]
    required_markers = [
        "Open-v2 evidence snapshot",
        "single-space scientific representation baselines",
        "HNFMR 0.790--0.999",
        "full pair scope",
        "same-work F1=0.980",
        "HNFMR=0.000",
        "held-out test scope",
    ]
    return [f"abstract missing bounded quantitative evidence marker: {marker}" for marker in required_markers if marker not in abstract_text]


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


def check_result_claim_boundary(manuscript_text: str, supplementary_text: str) -> list[str]:
    """Check result-table audit and claim-evidence boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing result-boundary markers.
    """
    if r"\label{tab:openv2-results}" not in manuscript_text:
        return []
    required_main_markers = [
        r"\subsection{Claim-Evidence Boundary for Result Interpretation}",
        r"\subsection{Result Audit Trail}",
        r"\label{tab:claim-evidence-boundary-main}",
        "prediction or score file",
        "metric summary",
        "checksum or manifest",
        "does not support a broad method-ranking claim",
    ]
    required_supplement_markers = [
        r"\section{Artifact Package Requirements}",
        r"\section{Claim-Evidence Matrix}",
        "checksums.sha256",
        "released artifact package",
    ]
    errors: list[str] = []
    for marker in required_main_markers:
        if marker not in manuscript_text:
            errors.append(f"Open-v2 result table missing manuscript audit boundary marker: {marker}")
    for marker in required_supplement_markers:
        if marker not in supplementary_text:
            errors.append(f"Open-v2 result table missing supplementary artifact boundary marker: {marker}")
    return errors


def check_method_feature_contract(manuscript_text: str) -> list[str]:
    """Check whether the method states implementation-level feature boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing method-contract markers.
    """
    required_markers = [
        r"\subsection{Feature and Head Specification}",
        r"\label{tab:feature-head-specification}",
        "Transformer distances",
        "title similarity",
        "author overlap",
        "DOI/arXiv/OpenAlex identifier agreement",
        "topic overlap",
        "reference Jaccard similarity",
        "different-identifier conflicts",
        "provenance-aware masking",
        "it is not a training feature",
    ]
    return [f"method feature contract missing marker: {marker}" for marker in required_markers if marker not in manuscript_text]


def check_operating_point_disclosure(manuscript_text: str) -> list[str]:
    """Check whether result operating points are disclosed for review.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing operating-point markers.
    """
    required_markers = [
        r"\subsection{Operating Point Disclosure}",
        r"\label{tab:operating-point-disclosure}",
        "fixed operating points",
        "post-hoc best test thresholds",
        "Representation cosine baselines",
        "RoBERTa pair classifier",
        "IAD-Risk transformer variants",
        r"default $\tau_w=\tau_a=\tau_r=0.5$",
        "Score file, metric summary, and threshold entry",
        "Prediction file, model JSON, thresholds, and checksums",
    ]
    return [f"operating point disclosure missing marker: {marker}" for marker in required_markers if marker not in manuscript_text]


def check_baseline_scope_alignment(manuscript_text: str) -> list[str]:
    """Check whether the baseline section matches the reported result table.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for baseline-scope mismatches.
    """
    if r"\label{tab:openv2-results}" not in manuscript_text:
        return []
    required_markers = [
        r"\subsection{Baselines}",
        "main table reports two scientific representation cosine baselines",
        "SciNCL cosine",
        "SPECTER2 adapter cosine",
        "RoBERTa pair classification",
        "not used as primary manuscript evidence",
        "metric summaries, prediction files, thresholds, and checksums",
    ]
    errors = [f"baseline scope alignment missing marker: {marker}" for marker in required_markers if marker not in manuscript_text]
    unsupported_primary_phrases = [
        "completed actual-model baselines include rule-based matching",
        "single-space union baselines",
    ]
    errors.extend(
        f"baseline scope lists unsupported primary evidence phrase: {phrase}"
        for phrase in unsupported_primary_phrases
        if phrase in manuscript_text
    )
    return errors


def check_split_leakage_controls(manuscript_text: str) -> list[str]:
    """Check whether evaluation split and leakage boundaries are stated.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing split-control markers.
    """
    required_markers = [
        r"\subsection{Split and Leakage Controls}",
        r"\label{tab:split-leakage-controls}",
        "Training uses only the declared training split",
        "threshold selection uses validation evidence",
        "Metadata fields that identify source, provenance, or split",
        "Unordered pair leakage guard",
        "Label-stratum coverage audit",
        "Source-heldout readiness audit",
        "Topic-heldout readiness audit",
        "not be claimed when topic coverage is insufficient",
    ]
    return [f"split and leakage controls missing marker: {marker}" for marker in required_markers if marker not in manuscript_text]


def check_scope_compatibility(manuscript_text: str) -> list[str]:
    """Check whether mixed-scope Open-v2 rows have a clear interpretation boundary.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing scope-compatibility markers.
    """
    required_markers = [
        r"\subsection{Scope Compatibility of the Open-v2 Table}",
        r"\label{tab:scope-compatibility}",
        "scope-bounded evidence table",
        "not a single leaderboard",
        "Full pair-scope representation baselines",
        "Held-out IAD-Risk rows",
        "same released prediction scope",
        "manual-validation slice",
        "A claim that this stronger comparison has already been completed",
    ]
    return [f"Open-v2 scope compatibility missing marker: {marker}" for marker in required_markers if marker not in manuscript_text]


def check_extended_protocol_boundary(manuscript_text: str) -> list[str]:
    """Check whether extended protocols are not overstated as current evidence.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for overstated extended protocol evidence.
    """
    required_markers = [
        r"\subsection{Extended Protocols and Boundaries}",
        "follow-up evaluation paths",
        "not as additional result evidence in the current manuscript package",
        "Open-v2 as the core mechanism demonstration",
        "reserves Open-v3/source-heldout conclusions for a released artifact package",
        "matched prediction scopes, threshold logs, checksums, and manual-validation evidence",
    ]
    errors = [f"extended protocol boundary missing marker: {marker}" for marker in required_markers if marker not in manuscript_text]
    unsupported_phrases = [
        "Open-v3 and source-heldout experiments provide additional stress tests",
        "Open-v3 as extended validation",
    ]
    errors.extend(
        f"extended protocol boundary overstates unreported evidence: {phrase}"
        for phrase in unsupported_phrases
        if phrase in manuscript_text
    )
    return errors


def check_related_work_positioning(manuscript_text: str) -> list[str]:
    """Check whether related work includes closest-work positioning.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing related-work positioning markers.
    """
    required_markers = [
        r"\label{tab:closest-work-positioning}",
        "Positioning against the closest lines of work",
        "End-to-end entity resolution systems",
        "Neural entity matching",
        "Scientific document representations",
        "Open scholarly metadata benchmarks",
        "false-merge risk gates",
        "gold, proxy, and silver strata",
    ]
    return [f"related work positioning missing marker: {marker}" for marker in required_markers if marker not in manuscript_text]


def check_error_taxonomy(manuscript_text: str) -> list[str]:
    """Check whether the mechanism section includes error taxonomy boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing error-taxonomy markers.
    """
    required_markers = [
        r"\label{tab:error-taxonomy}",
        "Error taxonomy for identity-agenda confusion",
        "Same task, different contribution",
        "Citation-neighborhood neighbor",
        "Version or extension boundary",
        "Identifier conflict",
        "Sparse metadata",
        "diagnostic rather than a measured error distribution",
    ]
    return [f"error taxonomy missing marker: {marker}" for marker in required_markers if marker not in manuscript_text]


def check_validity_threats(manuscript_text: str) -> list[str]:
    """Check whether threats to validity state concrete reviewer-facing boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing validity-threat markers.
    """
    required_markers = [
        r"\label{tab:validity-threats}",
        "Threats to validity and claim boundaries",
        "Construct validity",
        "Internal validity",
        "External validity",
        "Conclusion validity",
        "Reproducibility",
        "Operational validity",
        "not turn proxy or silver evidence into human-adjudicated truth",
        "Full numeric audit requires L2/L3 artifacts",
    ]
    return [f"validity threats missing marker: {marker}" for marker in required_markers if marker not in manuscript_text]


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


def check_cover_letter(cover_letter_text: str) -> list[str]:
    """Check cover letter completeness for journal submission.

    参数:
        cover_letter_text: Cover letter Markdown text.

    返回:
        list[str]: Error messages for missing cover letter statements.
    """
    required_markers = [
        "Dear Editor",
        "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication",
        "not under consideration elsewhere",
        "All listed authors have approved",
        "no competing interests",
        "raw third-party data",
        "manifests and checksums",
    ]
    return [f"cover letter missing required statement: {marker}" for marker in required_markers if marker not in cover_letter_text]


def check_submission_material_quantitative_summary(highlights_text: str, cover_letter_text: str) -> list[str]:
    """Check whether submission materials match the manuscript evidence scope.

    参数:
        highlights_text: Highlights Markdown text.
        cover_letter_text: Cover letter Markdown text.

    返回:
        list[str]: Error messages for missing quantitative submission markers.
    """
    required_markers = [
        "HNFMR 0.790--0.999",
        "HNFMR=0.000",
    ]
    errors: list[str] = []
    for marker in required_markers:
        if marker not in highlights_text:
            errors.append(f"highlights missing quantitative evidence marker: {marker}")
        if marker not in cover_letter_text:
            errors.append(f"cover letter missing quantitative evidence marker: {marker}")
    cover_letter_scope_markers = [
        "Open-v2 evidence snapshot",
        "full pair scope",
        "same-work F1=0.980",
        "held-out test scope",
    ]
    for marker in cover_letter_scope_markers:
        if marker not in cover_letter_text:
            errors.append(f"cover letter missing bounded evidence scope marker: {marker}")
    return errors


def check_submission_metadata(metadata_text: str) -> list[str]:
    """Check structured submission metadata required before journal upload.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for missing metadata markers.
    """
    required_markers = [
        "article_type: \"research_article\"",
        "review_mode: \"anonymous_review\"",
        "target_journal_template_bound: false",
        "author_metadata_required_before_final_upload: true",
        "corresponding_author:",
        "competing_interests:",
        "data_code_availability:",
        "raw_third_party_data_included: false",
        "full_numeric_audit_requires_external_artifact: true",
        "broad_method_ranking_claimed: false",
        "silver_labels_claimed_as_human_gold: false",
    ]
    return [f"submission metadata missing marker: {marker}" for marker in required_markers if marker not in metadata_text]


def check_final_upload_metadata(metadata_text: str) -> list[str]:
    """Check metadata fields that must be filled before final journal upload.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for unresolved final-upload metadata.
    """
    blocked_markers = {
        'target_journal: ""': "target journal is empty",
        "target_journal_template_bound: false": "target journal template is not bound",
        "authors: []": "author list is empty",
        'name: ""': "corresponding author name is empty",
        'affiliation: ""': "corresponding author affiliation is empty",
        'email: ""': "corresponding author email is empty",
    }
    return [f"final upload metadata unresolved: {message}" for marker, message in blocked_markers.items() if marker in metadata_text]


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
    cover_letter_path = ROOT / "cover_letter.md"
    cover_letter_text = cover_letter_path.read_text(encoding="utf-8") if cover_letter_path.exists() else ""
    submission_metadata_path = ROOT / "submission_metadata.yml"
    submission_metadata_text = submission_metadata_path.read_text(encoding="utf-8") if submission_metadata_path.exists() else ""
    errors.extend(check_sections(supplementary_text, REQUIRED_SUPPLEMENT_SECTIONS, "supplementary material"))
    errors.extend(check_forbidden_claims(manuscript_text))
    errors.extend(check_forbidden_claims(supplementary_text))
    errors.extend(check_forbidden_claims(highlights_text))
    errors.extend(check_forbidden_claims(keywords_text))
    errors.extend(check_forbidden_claims(cover_letter_text))
    errors.extend(
        check_auxiliary_model_evidence_absent(
            {
                "main manuscript": manuscript_text,
                "supplementary material": supplementary_text,
                "highlights": highlights_text,
                "keywords": keywords_text,
                "cover letter": cover_letter_text,
            }
        )
    )
    errors.extend(check_abstract_quantitative_evidence(manuscript_text))
    errors.extend(check_method_feature_contract(manuscript_text))
    errors.extend(check_related_work_positioning(manuscript_text))
    errors.extend(check_error_taxonomy(manuscript_text))
    errors.extend(check_validity_threats(manuscript_text))
    errors.extend(check_operating_point_disclosure(manuscript_text))
    errors.extend(check_baseline_scope_alignment(manuscript_text))
    errors.extend(check_split_leakage_controls(manuscript_text))
    errors.extend(check_scope_compatibility(manuscript_text))
    errors.extend(check_extended_protocol_boundary(manuscript_text))
    errors.extend(check_result_claim_boundary(manuscript_text, supplementary_text))
    errors.extend(check_highlights(highlights_text))
    errors.extend(check_keywords(keywords_text))
    errors.extend(check_cover_letter(cover_letter_text))
    errors.extend(check_submission_material_quantitative_summary(highlights_text, cover_letter_text))
    errors.extend(check_submission_metadata(submission_metadata_text))
    if args.final_upload:
        errors.extend(check_final_upload_metadata(submission_metadata_text))
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
