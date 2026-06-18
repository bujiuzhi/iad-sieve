"""Validate the manuscript package before journal submission.

The validation checks file completeness, unsupported claim wording, core section
coverage, PDF readability, and local LaTeX toolchain availability.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import re
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
    ROOT / "target_journal_shortlist.md",
    ROOT / "artifact_release_manifest.template.json",
    ROOT / "artifact_release_README.template.md",
    ROOT / "submission_system_checklist.md",
    ROOT / "reviewer_readiness_audit.md",
    ROOT / "submission_metadata.yml",
    ROOT / "scripts" / "validate_manuscript.py",
    ROOT / "scripts" / "verify_fixture_rebuild.py",
    ROOT / "scripts" / "build_submission_package.py",
    ROOT / "scripts" / "validate_submission_package.py",
    ROOT / "scripts" / "validate_artifact_release.py",
    ROOT / "scripts" / "build_elsevier_draft.py",
    ROOT / "scripts" / "check_latex_warnings.py",
    ROOT / "scripts" / "check_pdf_rendering.py",
    ROOT / "scripts" / "build_latex_pdf.sh",
    ROOT / "build" / "iad-risk-manuscript-latex.pdf",
    ROOT / "build" / "iad-risk-manuscript-elsevier.tex",
    ROOT / "build" / "iad-risk-manuscript-elsevier.pdf",
    ROOT / "build" / "iad-risk-supplementary-material.pdf",
]
REQUIRED_SECTIONS = [
    r"\begin{abstract}",
    r"\section{Introduction}",
    r"\section{Related Work}",
    r"\section{Problem Formulation}",
    r"\subsection{Notation and Relation Semantics}",
    r"\section{IAD-Bench}",
    r"\subsection{Document Schema Contract}",
    r"\subsection{Pair Schema Contract}",
    r"\section{Method}",
    r"\subsection{Training Objective}",
    r"\subsection{Failure-Control Rationale}",
    r"\subsection{Design Alternatives and Rejected Shortcuts}",
    r"\subsection{Implementation Details}",
    r"\subsection{Feature and Head Specification}",
    r"\subsection{Implementation and Reproducibility}",
    r"\section{Experiments}",
    r"\subsection{Split and Leakage Controls}",
    r"\subsection{Threshold Selection and Uncertainty Reporting}",
    r"\subsection{Statistical Interpretation Boundary}",
    r"\subsection{Operating Point Disclosure}",
    r"\subsection{Threshold Sensitivity Evidence Status}",
    r"\subsection{Claim-Evidence Boundary for Result Interpretation}",
    r"\subsection{Result Audit Trail}",
    r"\label{tab:result-artifact-crosswalk}",
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
    r"\section{Environment Setup}",
    r"\section{No-Network Fixture Rebuild}",
    r"\section{Public-Source Rebuild}",
    r"\section{Artifact Package Requirements}",
    r"\section{Claim-Evidence Matrix}",
    r"\section{Uncertainty and Ablation Requirements}",
    r"\section{Manual Validation Protocol}",
    r"\section{Claim Boundary}",
]
MIN_BIB_ENTRIES = 10
CITATION_COMMAND_PATTERN = re.compile(
    r"\\(?:cite|citep|citet|citealp|citealt|citeauthor|citeyear|citeyearpar)\*?(?:\s*\[[^\]]*\]){0,2}\s*\{([^}]+)\}"
)
BIBTEX_ENTRY_PATTERN = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,", re.MULTILINE)
LATEX_LABEL_PATTERN = re.compile(r"\\label\{([^}]+)\}")
LATEX_REFERENCE_PATTERN = re.compile(r"\\(?:ref|eqref|pageref|autoref)\{([^}]+)\}")
ALLOWED_LABEL_PREFIXES = ("fig:", "tab:", "eq:", "sec:", "alg:", "app:")
FORMAL_SOURCE_FORBIDDEN_CHARACTERS = {
    "\u2010": "Unicode hyphen",
    "\u2011": "non-breaking hyphen",
    "\u2012": "figure dash",
    "\u2013": "en dash",
    "\u2014": "em dash",
    "\u2015": "horizontal bar",
    "\u2212": "minus sign",
    "\u2018": "left single quotation mark",
    "\u2019": "right single quotation mark",
    "\u201c": "left double quotation mark",
    "\u201d": "right double quotation mark",
    "\u2026": "ellipsis",
    "\ufffd": "replacement character",
}
FORMAL_SOURCE_FORBIDDEN_MARKERS = [
    "TODO",
    "FIXME",
    "TBD",
    "[?]",
]
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
FORMAL_COMPLETION_OVERCLAIM_PATTERNS = [
    (
        re.compile(
            r"\bQ2\s*/?\s*B(?:[-_\s]*(?:complete|ready|accepted|acceptance\s+ready|standard\s+met|submission\s+ready))\b",
            re.IGNORECASE,
        ),
        "Q2/B completion claim",
    ),
    (
        re.compile(r"\b(?:meets?|reaches?|achieves?|satisfies?)\s+(?:the\s+)?Q2\s*/?\s*B\b", re.IGNORECASE),
        "Q2/B completion claim",
    ),
    (
        re.compile(r"(?:达到|满足|符合).{0,16}(?:二区\s*/?\s*B\s*类|二区|B\s*类).{0,16}(?:标准|要求|接收|投稿|水平)"),
        "Q2/B completion claim",
    ),
    (
        re.compile(r"\b(?:final[-\s]*upload|journal[-\s]*submission)[-\s]*(?:ready|complete)\b", re.IGNORECASE),
        "final-upload completion claim",
    ),
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


def extract_latex_section_body(document_text: str, section_marker: str) -> str:
    """Extract the body text after a LaTeX top-level section marker.

    参数:
        document_text: LaTeX document source.
        section_marker: Exact top-level section marker to locate.

    返回:
        str: Section body text up to the next top-level section, or an empty string when missing.
    """
    section_start = document_text.find(section_marker)
    if section_start < 0:
        return ""
    body_start = section_start + len(section_marker)
    next_section = re.search(r"\n\\section\*?\{", document_text[body_start:])
    if next_section is None:
        return document_text[body_start:]
    return document_text[body_start : body_start + next_section.start()]


def check_declaration_statements(manuscript_text: str) -> list[str]:
    """Check journal declaration statements for reviewer-auditable content.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for incomplete availability, ethics, or competing-interest statements.
    """
    required_markers_by_section = {
        r"\section*{Data and Code Availability}": [
            "source code",
            "benchmark construction scripts",
            "Raw third-party data are not redistributed",
            "data-processing commands",
            "schema contracts",
            "fixture tests",
            "artifact-release",
            "manifests",
            "checksums",
            "commit identifiers",
        ],
        r"\section*{Ethics Statement}": [
            "public scholarly metadata",
            "does not involve human participants",
            "clinical records",
            "private user behavior",
            "sensitive personal information",
        ],
        r"\section*{Competing Interests}": [
            "no competing interests",
        ],
    }
    errors: list[str] = []
    for section_marker, required_markers in required_markers_by_section.items():
        section_body = extract_latex_section_body(manuscript_text, section_marker)
        if not section_body.strip():
            errors.append(f"declaration statement missing section body: {section_marker}")
            continue
        for marker in required_markers:
            if marker not in section_body:
                errors.append(f"declaration statement {section_marker} missing marker: {marker}")
    return errors


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


def check_formal_submission_claim_lockdown(document_texts: dict[str, str]) -> list[str]:
    """Check formal submission materials for premature completion claims.

    参数:
        document_texts: Mapping from formal submission document name to text.

    返回:
        list[str]: Error messages for unsafe Q2/B or final-upload completion claims.
    """
    errors: list[str] = []
    for document_name, document_text in document_texts.items():
        for pattern, label in FORMAL_COMPLETION_OVERCLAIM_PATTERNS:
            match = pattern.search(document_text)
            if match is None:
                continue
            line_number = document_text.count("\n", 0, match.start()) + 1
            errors.append(f"{document_name} contains unsafe formal completion claim ({label}) on line {line_number}")
    return errors


def check_formal_source_typography_hygiene(document_texts: dict[str, str]) -> list[str]:
    """Check formal submission sources for unsafe typography and edit markers.

    参数:
        document_texts: Mapping from formal submission document name to text.

    返回:
        list[str]: Error messages for unsafe characters or unfinished edit markers.
    """
    errors: list[str] = []
    for document_name, document_text in document_texts.items():
        for line_number, line in enumerate(document_text.splitlines(), start=1):
            for character, label in FORMAL_SOURCE_FORBIDDEN_CHARACTERS.items():
                if character in line:
                    errors.append(f"{document_name} contains {label} on line {line_number}")
            for marker in FORMAL_SOURCE_FORBIDDEN_MARKERS:
                if marker in line:
                    errors.append(f"{document_name} contains unfinished edit marker {marker} on line {line_number}")
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


def check_abstract_length(manuscript_text: str, max_words: int = 250) -> list[str]:
    """Check whether the abstract stays within common journal word limits.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        max_words: Maximum allowed abstract word count.

    返回:
        list[str]: Error messages for abstract length violations.
    """
    begin_marker = r"\begin{abstract}"
    end_marker = r"\end{abstract}"
    if begin_marker not in manuscript_text or end_marker not in manuscript_text:
        return ["abstract length check could not locate abstract environment"]
    abstract_text = manuscript_text.split(begin_marker, 1)[1].split(end_marker, 1)[0]
    word_count = len(abstract_text.split())
    if word_count > max_words:
        return [f"abstract has {word_count} words; expected at most {max_words}"]
    return []


def check_contribution_evidence_summary(manuscript_text: str) -> list[str]:
    """Check whether the introduction aligns contributions with evidence and claim boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing contribution-evidence markers.
    """
    required_markers = [
        r"\label{tab:contribution-evidence-summary}",
        "Contribution-evidence summary",
        "Identity-agenda confusion as a scholarly deduplication failure mode",
        "IAD-Bench as a provenance-aware pair contract",
        "IAD-Risk as a risk-aware merge mechanism",
        "hard-negative false-merge rate",
        "Gold, proxy, silver, and manual-validation layers",
        "same-work F1=0.980",
        "HNFMR=0.000",
        "not a broad method-ranking claim",
    ]
    return [
        f"contribution-evidence summary missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_openv2_benchmark_composition(manuscript_text: str) -> list[str]:
    """Check whether the manuscript states Open-v2 evidence composition and boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing Open-v2 composition markers.
    """
    required_markers = [
        r"\label{tab:openv2-composition}",
        "Open-v2 benchmark composition",
        "415",
        "10,000",
        "10,415",
        "1,737 documents",
        "DeepMatcher gold identity",
        "OpenAlex and OpenCitations silver hard negatives",
        "Measures same-work matching ability",
        "Stresses agenda-level false-merge behavior",
        "not human non-identity gold",
        "broader source-heldout claims require additional artifacts",
    ]
    return [
        f"Open-v2 benchmark composition missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_iad_bench_pair_schema_contract(manuscript_text: str) -> list[str]:
    """Check whether IAD-Bench pair fields are stated in the manuscript.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing pair-schema contract markers.
    """
    required_markers = [
        r"\subsection{Pair Schema Contract}",
        r"\label{tab:iad-bench-pair-schema}",
        r"\texttt{pair\_id}",
        r"\texttt{source\_document\_id}",
        r"\texttt{target\_document\_id}",
        r"\texttt{relation\_label}",
        r"\texttt{expected\_label}",
        r"\texttt{expected\_agenda\_label}",
        r"\texttt{label\_source}",
        r"\texttt{label\_strength}",
        r"\texttt{label\_provenance}",
        r"\texttt{split}",
        r"\texttt{hard\_negative\_level}",
        "Separates same-work identity from agenda relatedness",
        "identifies agenda-level hard negatives for HNFMR",
    ]
    return [
        f"IAD-Bench pair schema contract missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_iad_bench_document_schema_contract(manuscript_text: str) -> list[str]:
    """Check whether IAD-Bench document fields are stated in the manuscript.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing document-schema contract markers.
    """
    required_markers = [
        r"\subsection{Document Schema Contract}",
        r"\label{tab:iad-bench-document-schema}",
        r"\texttt{document\_id}",
        r"\texttt{source\_dataset}",
        r"\texttt{title}",
        r"\texttt{abstract}",
        r"\texttt{authors}",
        r"\texttt{year}",
        r"\texttt{venue}",
        r"\texttt{doi}",
        r"\texttt{arxiv\_id}",
        r"\texttt{openalex\_work\_id}",
        r"\texttt{topics}",
        r"\texttt{references}",
        "Missing values are represented by empty strings, empty arrays, or null values",
        "without redistributing raw third-party files",
    ]
    return [
        f"IAD-Bench document schema contract missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


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


def extract_citation_keys(document_texts: dict[str, str]) -> set[str]:
    """Extract citation keys from LaTeX document texts.

    参数:
        document_texts: Mapping from document name to LaTeX text.

    返回:
        set[str]: Citation keys used by citation commands.
    """
    citation_keys: set[str] = set()
    for document_text in document_texts.values():
        for match in CITATION_COMMAND_PATTERN.finditer(document_text):
            for raw_key in match.group(1).split(","):
                key = raw_key.strip()
                if key:
                    citation_keys.add(key)
    return citation_keys


def extract_bibtex_keys(bibliography_text: str) -> list[str]:
    """Extract BibTeX entry keys while preserving duplicates.

    参数:
        bibliography_text: BibTeX source text.

    返回:
        list[str]: Entry keys in source order.
    """
    return [match.group(1).strip() for match in BIBTEX_ENTRY_PATTERN.finditer(bibliography_text)]


def check_citation_bibliography_alignment(document_texts: dict[str, str], bibliography_text: str) -> list[str]:
    """Check citation keys against the BibTeX bibliography.

    参数:
        document_texts: Mapping from formal LaTeX document name to text.
        bibliography_text: BibTeX source text.

    返回:
        list[str]: Error messages for missing, duplicate, or uncited bibliography entries.
    """
    citation_keys = extract_citation_keys(document_texts)
    bibliography_keys = extract_bibtex_keys(bibliography_text)
    bibliography_key_set = set(bibliography_keys)
    duplicate_keys = sorted({key for key in bibliography_keys if bibliography_keys.count(key) > 1})
    missing_bibliography_keys = sorted(citation_keys - bibliography_key_set)
    uncited_bibliography_keys = sorted(bibliography_key_set - citation_keys)
    errors: list[str] = []
    if not citation_keys:
        errors.append("formal LaTeX sources contain no citation commands")
    if not bibliography_keys:
        errors.append("references.bib contains no BibTeX entries")
    if duplicate_keys:
        errors.append(f"references.bib contains duplicate BibTeX keys: {duplicate_keys}")
    if missing_bibliography_keys:
        errors.append(f"citation keys missing from references.bib: {missing_bibliography_keys}")
    if uncited_bibliography_keys:
        errors.append(f"references.bib contains uncited entries: {uncited_bibliography_keys}")
    return errors


def extract_latex_labels(document_text: str) -> list[str]:
    """Extract LaTeX label keys while preserving duplicates.

    参数:
        document_text: LaTeX source text.

    返回:
        list[str]: Label keys in source order.
    """
    return [match.group(1).strip() for match in LATEX_LABEL_PATTERN.finditer(document_text)]


def extract_latex_references(document_text: str) -> set[str]:
    """Extract LaTeX cross-reference keys.

    参数:
        document_text: LaTeX source text.

    返回:
        set[str]: Referenced label keys.
    """
    return {match.group(1).strip() for match in LATEX_REFERENCE_PATTERN.finditer(document_text) if match.group(1).strip()}


def check_latex_cross_references(document_texts: dict[str, str]) -> list[str]:
    """Check LaTeX labels and cross-references within each source file.

    参数:
        document_texts: Mapping from document name to LaTeX source text.

    返回:
        list[str]: Error messages for duplicate labels, invalid label prefixes, or missing references.
    """
    errors: list[str] = []
    for document_name, document_text in document_texts.items():
        labels = extract_latex_labels(document_text)
        label_set = set(labels)
        duplicate_labels = sorted({label for label in labels if labels.count(label) > 1})
        invalid_labels = sorted(label for label in label_set if not label.startswith(ALLOWED_LABEL_PREFIXES))
        missing_reference_targets = sorted(extract_latex_references(document_text) - label_set)
        if duplicate_labels:
            errors.append(f"{document_name} contains duplicate LaTeX labels: {duplicate_labels}")
        if invalid_labels:
            errors.append(f"{document_name} contains labels without approved prefixes: {invalid_labels}")
        if missing_reference_targets:
            errors.append(f"{document_name} references missing LaTeX labels: {missing_reference_targets}")
    return errors


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
        r"\label{tab:result-artifact-crosswalk}",
        r"\label{tab:claim-evidence-boundary-main}",
        "prediction or score file",
        "metric summary",
        "checksum or manifest",
        r"\path{open_v2_main_results}",
        r"\path{iad_bench_split_summary}",
        r"\path{representation_baseline_scores}",
        r"\path{supervised_baseline_predictions}",
        r"\path{iad_risk_predictions}",
        r"\path{threshold_selection_logs}",
        r"\path{bootstrap_intervals}",
        r"\path{ablation_suite}",
        r"\path{manual_validation_slice}",
        r"\path{threshold_sensitivity_grid}",
        "does not support a broad method-ranking claim",
    ]
    required_supplement_markers = [
        r"\section{Artifact Package Requirements}",
        r"\section{Claim-Evidence Matrix}",
        "checksums.sha256",
        "released artifact package",
        "python manuscript/scripts/validate_artifact_release.py",
        "required result identifiers",
        "conditional claim artifacts",
        r"\path{threshold_sensitivity_grid}",
        "exclusion of raw third-party data",
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


def check_design_alternative_boundaries(manuscript_text: str) -> list[str]:
    """Check whether the method explains why simpler alternatives are insufficient.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing design-alternative boundaries.
    """
    required_markers = [
        r"\subsection{Design Alternatives and Rejected Shortcuts}",
        r"\label{tab:design-alternatives}",
        "Tune a representation-similarity threshold",
        "Use one supervised pair classifier",
        "Use provenance as a model feature",
        "Always force a binary merge decision",
        "Select thresholds after test results",
        "RoBERTa remains a strong baseline",
        "broad superiority is not claimed",
        "Threshold stability needs a released grid and checksums",
    ]
    return [
        f"design alternative boundary missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


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


def check_threshold_sensitivity_status(manuscript_text: str) -> list[str]:
    """Check whether threshold sensitivity claims are bounded by artifact evidence.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing threshold-sensitivity markers.
    """
    required_markers = [
        r"\subsection{Threshold Sensitivity Evidence Status}",
        r"\label{tab:threshold-sensitivity-status}",
        "Threshold stability is treated as an audit requirement",
        "not as an unsupported robustness claim",
        "same prediction files",
        "predefined threshold ranges",
        "not reported as primary evidence",
        "Per-threshold F1, FMR, HNFMR",
        "not threshold-stable ranking across all operating points",
    ]
    return [
        f"threshold sensitivity evidence status missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_statistical_interpretation_boundary(manuscript_text: str) -> list[str]:
    """Check whether point estimates are separated from interval and significance claims.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing statistical interpretation boundaries.
    """
    required_markers = [
        r"\subsection{Statistical Interpretation Boundary}",
        r"\label{tab:statistical-interpretation-boundary}",
        "point estimates for a fixed evidence snapshot",
        "not statistical superiority estimates",
        "Confidence intervals, significance tests, and model-ranking statements are intentionally withheld",
        "exact prediction files, resampling logs, random seeds, and checksums",
        "no hard-negative false merge was observed",
        "not be read as proof of zero risk",
        r"\path{bootstrap_intervals}",
        "Predefined tests, multiplicity handling, input artifacts, and reproducible analysis logs",
        "Same-scope predictions, interval estimates, ablations, and manual-validation slice",
    ]
    return [
        f"statistical interpretation boundary missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


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


def check_manual_validation_protocol(supplementary_text: str) -> list[str]:
    """Check whether the supplementary material defines manual validation requirements.

    参数:
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing manual-validation protocol markers.
    """
    required_markers = [
        r"\section{Manual Validation Protocol}",
        "future evidence layer",
        "500--1,000 pairs",
        "two independent reviewers",
        "blind to model scores",
        "adjudication log",
        "inter-annotator agreement",
        "must not claim human gold",
    ]
    return [
        f"manual validation protocol missing marker: {marker}"
        for marker in required_markers
        if marker not in supplementary_text
    ]


def check_environment_setup(supplementary_text: str) -> list[str]:
    """Check whether the supplementary material documents environment setup.

    参数:
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing environment setup markers.
    """
    required_markers = [
        r"\section{Environment Setup}",
        "conda create -n iad-sieve python=3.11 -y",
        "python -m pip install -e .",
        "python -m iad_sieve.cli --help",
        "python scripts/check_public_release.py",
        "python manuscript/scripts/verify_fixture_rebuild.py",
        "does not download full raw datasets",
        "Full numerical result reproduction still requires the L2/L3 data and artifact requirements",
    ]
    return [
        f"environment setup missing marker: {marker}"
        for marker in required_markers
        if marker not in supplementary_text
    ]


def check_target_journal_shortlist(shortlist_text: str) -> list[str]:
    """Check whether target journal planning records candidates and boundaries.

    参数:
        shortlist_text: Target journal shortlist Markdown text.

    返回:
        list[str]: Error messages for missing target-journal planning markers.
    """
    required_markers = [
        "# Target Journal Shortlist",
        "Rank-sensitive labels",
        "Primary practical target: Data & Knowledge Engineering",
        "Stretch target: Information Systems",
        "Domain backup: Scientometrics",
        "Candidate Matrix",
        "Template and File Implications",
        "Data & Knowledge Engineering Preflight",
        "Official guide rechecked: 2026-06-18",
        "provisional preparation only",
        "single anonymized review",
        "250-word limit",
        "1--7 semicolon-separated keywords",
        "3--5 highlights",
        "85-character limit",
        "Elsevier `elsarticle`",
        "real artifact URL or DOI",
        "not a final submission record",
        "must be reconfirmed",
    ]
    return [
        f"target journal shortlist missing marker: {marker}"
        for marker in required_markers
        if marker not in shortlist_text
    ]


def check_artifact_release_manifest_template(template_text: str) -> list[str]:
    """Check whether the artifact release manifest template covers result audit needs.

    参数:
        template_text: Artifact release manifest template JSON text.

    返回:
        list[str]: Error messages for malformed or incomplete release template content.
    """
    try:
        template = json.loads(template_text)
    except json.JSONDecodeError as exc:
        return [f"artifact release manifest template is invalid JSON: {exc}"]

    errors: list[str] = []
    if template.get("package_type") != "result_artifact_release":
        errors.append("artifact release manifest template package_type must be result_artifact_release")
    if template.get("release_status") != "template_pending_external_artifact":
        errors.append("artifact release manifest template must remain a pending external artifact template")

    data_policy = template.get("data_policy")
    if not isinstance(data_policy, dict):
        errors.append("artifact release manifest template missing data_policy object")
    else:
        expected_false_fields = [
            "raw_third_party_data_included",
            "model_checkpoints_included",
            "personal_or_secret_material_included",
        ]
        for field in expected_false_fields:
            if data_policy.get(field) is not False:
                errors.append(f"artifact release data_policy must set {field} to false")
        if data_policy.get("derived_evaluation_artifacts_included") is not True:
            errors.append("artifact release data_policy must include derived evaluation artifacts")

    required_directories = set(template.get("required_directories", []))
    for directory_name in {"configs", "tables", "predictions", "reports", "logs"}:
        if directory_name not in required_directories:
            errors.append(f"artifact release manifest template missing required directory: {directory_name}")

    required_top_level_files = set(template.get("required_top_level_files", []))
    for file_name in {"README.md", "manifest.json", "checksums.sha256"}:
        if file_name not in required_top_level_files:
            errors.append(f"artifact release manifest template missing top-level file: {file_name}")

    artifacts = template.get("required_artifacts")
    if not isinstance(artifacts, list):
        errors.append("artifact release manifest template missing required_artifacts list")
        artifact_ids: set[str] = set()
    else:
        artifact_ids = {str(row.get("artifact_id", "")) for row in artifacts if isinstance(row, dict)}
    required_artifact_ids = {
        "open_v2_main_results",
        "iad_risk_predictions",
        "representation_baseline_scores",
        "supervised_baseline_predictions",
        "threshold_selection_logs",
        "iad_bench_split_summary",
    }
    conditional_artifact_ids = {
        "bootstrap_intervals",
        "ablation_suite",
        "manual_validation_slice",
        "threshold_sensitivity_grid",
    }
    for artifact_id in required_artifact_ids:
        if artifact_id not in artifact_ids:
            errors.append(f"artifact release manifest template missing required artifact: {artifact_id}")
    for artifact_id in conditional_artifact_ids:
        if artifact_id not in artifact_ids:
            errors.append(f"artifact release manifest template missing conditional artifact: {artifact_id}")

    validation_commands = template.get("minimum_validation_commands")
    if not isinstance(validation_commands, list):
        errors.append("artifact release manifest template missing minimum_validation_commands list")
    else:
        validation_text = "\n".join(str(command) for command in validation_commands)
        for command in [
            "sha256sum -c checksums.sha256",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir",
            "python manuscript/scripts/validate_manuscript.py --strict-latex",
            "python manuscript/scripts/verify_fixture_rebuild.py",
            "python scripts/check_public_release.py",
        ]:
            if command not in validation_text:
                errors.append(f"artifact release manifest template missing validation command: {command}")

    claim_boundaries = template.get("claim_boundaries")
    if not isinstance(claim_boundaries, dict):
        errors.append("artifact release manifest template missing claim_boundaries object")
    else:
        for field in [
            "silver_labels_are_not_human_gold",
            "manual_validation_required_for_human_gold_claims",
            "same_scope_prediction_files_required_for_broad_ranking",
            "threshold_grid_required_for_threshold_stability_claims",
        ]:
            if claim_boundaries.get(field) is not True:
                errors.append(f"artifact release claim boundary must be true: {field}")
        for field in [
            "confidence_intervals_claimed",
            "component_causality_claimed",
            "human_validation_claimed",
            "threshold_stability_claimed",
            "broad_method_ranking_claimed",
        ]:
            if claim_boundaries.get(field) is not False:
                errors.append(f"artifact release claim boundary must default false: {field}")

    conditional_claim_artifacts = template.get("conditional_claim_artifacts")
    expected_conditional_claim_artifacts = {
        "confidence_intervals_claimed": {"bootstrap_intervals"},
        "component_causality_claimed": {"ablation_suite"},
        "human_validation_claimed": {"manual_validation_slice"},
        "threshold_stability_claimed": {"threshold_sensitivity_grid"},
        "broad_method_ranking_claimed": {
            "bootstrap_intervals",
            "manual_validation_slice",
            "threshold_sensitivity_grid",
        },
    }
    if not isinstance(conditional_claim_artifacts, dict):
        errors.append("artifact release manifest template missing conditional_claim_artifacts object")
    else:
        for claim_field, expected_ids in expected_conditional_claim_artifacts.items():
            actual_ids = set(conditional_claim_artifacts.get(claim_field, []))
            missing_ids = expected_ids - actual_ids
            if missing_ids:
                errors.append(
                    "artifact release manifest template conditional_claim_artifacts "
                    f"missing {claim_field}: {sorted(missing_ids)}"
                )

    return errors


def check_artifact_release_readme_template(readme_text: str) -> list[str]:
    """Check whether the artifact release README template gives reviewers a safe entry point.

    参数:
        readme_text: Artifact release README template Markdown text.

    返回:
        list[str]: Error messages for missing release instructions or claim boundaries.
    """
    required_markers = [
        "# IAD-Risk Artifact Release README Template",
        "external result artifact release",
        "Do not include raw third-party data",
        "Do not include model checkpoints",
        "Do not include credentials, personal identifiers, or local paths",
        "Required Top-Level Files",
        "README.md",
        "manifest.json",
        "checksums.sha256",
        "Required Directories",
        "configs/",
        "tables/",
        "predictions/",
        "reports/",
        "logs/",
        "Minimum Validation Commands",
        "sha256sum -c checksums.sha256",
        "python manuscript/scripts/validate_artifact_release.py --artifact-dir",
        "python manuscript/scripts/validate_manuscript.py --strict-latex",
        "python manuscript/scripts/verify_fixture_rebuild.py",
        "python scripts/check_public_release.py",
        "Required Artifact IDs",
        "open_v2_main_results",
        "iad_risk_predictions",
        "representation_baseline_scores",
        "supervised_baseline_predictions",
        "threshold_selection_logs",
        "iad_bench_split_summary",
        "Conditional Claim Artifacts",
        "confidence_intervals_claimed",
        "bootstrap_intervals",
        "component_causality_claimed",
        "ablation_suite",
        "human_validation_claimed",
        "manual_validation_slice",
        "threshold_stability_claimed",
        "threshold_sensitivity_grid",
        "broad_method_ranking_claimed",
        "Claim Boundaries",
        "silver labels are not human gold",
        "full numerical audit requires external artifacts",
        "broad method ranking is not claimed unless conditional artifacts are complete",
        "Reproduction Levels",
        "L0 code check",
        "L1 fixture rebuild",
        "L2 public-source rebuild",
        "L3 result audit",
    ]
    lowered_text = readme_text.lower()
    return [
        f"artifact release README template missing marker: {marker}"
        for marker in required_markers
        if marker.lower() not in lowered_text
    ]


def check_submission_system_checklist(checklist_text: str) -> list[str]:
    """Check whether the final upload checklist covers system-file review needs.

    参数:
        checklist_text: Submission system checklist Markdown text.

    返回:
        list[str]: Error messages for missing upload-checklist markers.
    """
    required_markers = [
        "# Submission System Checklist",
        "not a manuscript file for journal upload",
        "Required Upload Files",
        "Final Metadata Checks",
        "File Hygiene Checks",
        "Current Blocking Items",
        "Main manuscript source",
        "Main manuscript PDF",
        "DKE/Elsevier preflight source",
        "DKE/Elsevier preflight PDF",
        "Supplementary source",
        "Supplementary PDF",
        "Bibliography",
        "Cover letter",
        "Highlights",
        "Keywords",
        "Submission metadata",
        "Artifact release manifest",
        "Artifact Release Package Checks",
        "python manuscript/scripts/validate_artifact_release.py --artifact-dir",
        "DKE/Elsevier Preflight Package Checks",
        "python manuscript/scripts/build_submission_package.py --dke-preflight",
        "python manuscript/scripts/validate_submission_package.py --dke-preflight",
        "build/iad-risk-dke-preflight-package.zip",
        "iad-risk-manuscript-elsevier.tex",
        "iad-risk-manuscript-elsevier.pdf",
        "does not complete the final-upload gate",
        "No `data/`, `outputs/`, cache, local connection, credential, or raw third-party file",
        "author email addresses, ORCID values, personal account URLs, local absolute paths, or tool-generated process notes",
        "Target journal has not been author-confirmed",
        "Artifact release URL or DOI has not been created",
    ]
    return [
        f"submission system checklist missing marker: {marker}"
        for marker in required_markers
        if marker not in checklist_text
    ]


def check_reviewer_readiness_audit(audit_text: str) -> list[str]:
    """Check whether reviewer-readiness audit covers rejection risks and final gates.

    参数:
        audit_text: Reviewer readiness audit Markdown text.

    返回:
        list[str]: Error messages for missing reviewer-readiness markers.
    """
    required_markers = [
        "# Reviewer Readiness Audit",
        "conditionally ready for target-journal selection; not ready for final upload",
        "Audit Dimensions",
        "Reviewer Risk Register",
        "Claim-Evidence Check",
        "Adversarial Self-Review Matrix",
        "Contribution self-review",
        "Writing clarity self-review",
        "Experimental strength self-review",
        "Evaluation completeness self-review",
        "Method design soundness self-review",
        "`pass`",
        "`needs revision`",
        "`needs new experiment`",
        "same-scope prediction files",
        "artifact-backed ablations",
        "Reviewer Response Matrix",
        "likely reviewer questions",
        "identity-agenda confusion",
        "silver hard negatives",
        "scope-bounded evidence snapshot",
        "RoBERTa as a strong baseline",
        "mechanism-consistent",
        "fixture-level code reproduction",
        "Audit Cycle 1: Claim Discipline",
        "Audit Cycle 2: Submission Readiness",
        "Audit Cycle 3: Q2/B Acceptance Gate",
        "Audit Cycle 4: Final Package Hygiene",
        "Audit Cycle 5: Editorial Desk Check",
        "remote reproducibility",
        "strong model matrix",
        "model superiority",
        "innovation depth",
        "novelty and prior-art positioning",
        "claim lockdown",
        "anonymous package hygiene",
        "title, abstract, conclusion, cover letter, highlights, and keywords",
        "editorial claim alignment",
        "author email addresses, ORCID values, personal account URLs, local absolute paths, and tool-generated process notes",
        "Q2/B acceptance gate is either fully ready",
        "Minimum Gate Before Final Upload",
        "Contribution",
        "Writing clarity",
        "Experimental strength",
        "Evaluation completeness",
        "Method design soundness",
        "Silver hard negatives may not be true non-identity labels",
        "Threshold results may be sensitive",
        "Confidence intervals and statistical significance may be overread",
        "point estimates",
        "bootstrap intervals",
        "statistical significance",
        "Reproducibility depends on files outside Git",
        "python manuscript/scripts/validate_submission_package.py --final-upload",
    ]
    return [
        f"reviewer readiness audit missing marker: {marker}"
        for marker in required_markers
        if marker not in audit_text
    ]


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
    if not 3 <= len(bullet_lines) <= 5:
        errors.append(f"highlights has {len(bullet_lines)} bullet lines; expected 3 to 5")
    for line in bullet_lines:
        highlight = line[2:]
        word_count = len(highlight.split())
        if word_count > 22:
            errors.append(f"highlight is too long ({word_count} words): {line}")
        character_count = len(highlight)
        if character_count > 85:
            errors.append(f"highlight exceeds 85 characters ({character_count} characters): {line}")
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
    if not 1 <= len(keywords) <= 7:
        errors.append(f"keywords has {len(keywords)} entries; expected 1 to 7")
    for keyword in keywords:
        word_count = len(keyword.split())
        if word_count > 5:
            errors.append(f"keyword is too long ({word_count} words): {keyword}")
    return errors


def load_elsevier_draft_builder():
    """Load the Elsevier draft builder module used by the manuscript package.

    参数:
        无。

    返回:
        module: Loaded build_elsevier_draft module.

    异常:
        ImportError: Raised when the builder module cannot be loaded.
    """
    builder_path = ROOT / "scripts" / "build_elsevier_draft.py"
    spec = importlib.util.spec_from_file_location("build_elsevier_draft", builder_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load Elsevier draft builder: {builder_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_keyword_entries(keywords_text: str) -> list[str]:
    """Parse semicolon-separated keyword entries from Markdown text.

    参数:
        keywords_text: Keyword Markdown text.

    返回:
        list[str]: Parsed keyword entries.
    """
    keyword_lines = [line.strip() for line in keywords_text.splitlines() if line.strip() and not line.startswith("#")]
    return [keyword.strip() for keyword in " ".join(keyword_lines).split(";") if keyword.strip()]


def check_elsevier_draft_source(manuscript_text: str, keywords_text: str, generated_text: str) -> list[str]:
    """Check whether the generated Elsevier source matches the current manuscript.

    参数:
        manuscript_text: Main manuscript LaTeX source.
        keywords_text: Keyword Markdown text.
        generated_text: Generated Elsevier LaTeX source.

    返回:
        list[str]: Error messages for stale or invalid generated Elsevier source.
    """
    if not generated_text.strip():
        return ["Elsevier draft source is empty or missing"]
    try:
        builder = load_elsevier_draft_builder()
        expected_text = builder.build_elsevier_latex(manuscript_text, parse_keyword_entries(keywords_text))
    except Exception as exc:  # noqa: BLE001
        return [f"Elsevier draft source could not be regenerated: {exc}"]
    if generated_text.strip() != expected_text.strip():
        return ["Elsevier draft source is stale; rerun python manuscript/scripts/build_elsevier_draft.py"]
    return []


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


def check_editorial_claim_alignment(
    manuscript_text: str,
    cover_letter_text: str,
    highlights_text: str,
    keywords_text: str,
    metadata_text: str,
) -> list[str]:
    """Check first-screen claim alignment across formal submission materials.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        cover_letter_text: Cover letter Markdown text.
        highlights_text: Highlights Markdown text.
        keywords_text: Keywords Markdown text.
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for title, evidence, or claim-boundary drift.
    """
    expected_title = "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication"
    errors: list[str] = []
    for document_name, document_text in {
        "main manuscript": manuscript_text,
        "cover letter": cover_letter_text,
        "submission metadata": metadata_text,
    }.items():
        if expected_title not in document_text:
            errors.append(f"editorial claim alignment missing title in {document_name}: {expected_title}")

    begin_marker = r"\begin{abstract}"
    end_marker = r"\end{abstract}"
    abstract_text = ""
    if begin_marker in manuscript_text and end_marker in manuscript_text:
        abstract_text = manuscript_text.split(begin_marker, 1)[1].split(end_marker, 1)[0]
    else:
        errors.append("editorial claim alignment could not locate main manuscript abstract")
    conclusion_text = extract_latex_section_body(manuscript_text, r"\section{Conclusion}")
    if not conclusion_text.strip():
        errors.append("editorial claim alignment could not locate main manuscript conclusion")

    required_markers_by_document = {
        "main abstract": (
            abstract_text,
            [
                "identity-agenda confusion",
                "IAD-Risk",
                "IAD-Bench",
                "Open-v2 evidence snapshot",
                "HNFMR 0.790--0.999",
                "HNFMR=0.000",
                "broad method-ranking claims",
            ],
        ),
        "main conclusion": (
            conclusion_text,
            [
                "specific failure mode",
                "identity and agenda evidence",
                "false-merge risk",
                "targeted false-merge suppression",
                "reproducible benchmark contract",
                "Additional validation",
                "broad method ranking",
            ],
        ),
        "cover letter": (
            cover_letter_text,
            [
                "identity-agenda confusion",
                "IAD-Risk",
                "IAD-Bench",
                "Open-v2 evidence snapshot",
                "HNFMR 0.790--0.999",
                "HNFMR=0.000",
                "does not claim broad method superiority",
                "raw third-party data and full experimental outputs are not redistributed in Git",
            ],
        ),
        "highlights": (
            highlights_text,
            [
                "Identity-agenda confusion",
                "IAD-Risk",
                "IAD-Bench",
                "HNFMR 0.790--0.999",
                "IAD-Risk HNFMR=0.000",
                "artifact rules",
            ],
        ),
        "keywords": (
            keywords_text,
            [
                "scholarly entity matching",
                "work deduplication",
                "identity-agenda disentanglement",
                "false-merge risk",
                "provenance-aware evaluation",
            ],
        ),
        "submission metadata": (
            metadata_text,
            [
                "broad_method_ranking_claimed: false",
                "silver_labels_claimed_as_human_gold: false",
                "artifact_release_required_before_final_upload: true",
            ],
        ),
    }
    for document_name, (document_text, required_markers) in required_markers_by_document.items():
        lowered_text = document_text.lower()
        for marker in required_markers:
            if marker.lower() not in lowered_text:
                errors.append(f"editorial claim alignment missing marker in {document_name}: {marker}")
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
        "target_preparation:",
        "shortlist_file: \"target_journal_shortlist.md\"",
        "primary_practical_candidate: \"Data & Knowledge Engineering\"",
        "provisional_target_status: \"dke_preflight_ready_pending_author_confirmation\"",
        "dke_official_guide_rechecked: \"2026-06-18\"",
        "ranking_confirmation_required_before_final_upload: true",
        "selected_target_requires_author_confirmation: true",
        "dke_preflight:",
        "review_model: \"single_anonymized\"",
        "abstract_word_limit_checked: true",
        "keyword_count_checked: true",
        "highlight_count_and_length_checked: true",
        "elsarticle_conversion_pending_author_confirmation: true",
        "artifact_release_required_before_upload: true",
        "corresponding_author:",
        "competing_interests:",
        "data_code_availability:",
        "raw_third_party_data_included: false",
        "full_numeric_audit_requires_external_artifact: true",
        "broad_method_ranking_claimed: false",
        "silver_labels_claimed_as_human_gold: false",
        "release_manifest_template: \"artifact_release_manifest.template.json\"",
        "artifact_release_url: \"\"",
        "artifact_release_doi: \"\"",
        "artifact_release_required_before_final_upload: true",
        "upload_preparation:",
        "submission_system_checklist_file: \"submission_system_checklist.md\"",
        "reviewer_readiness_audit_file: \"reviewer_readiness_audit.md\"",
        "live_submission_system_verified: false",
        "final_upload_package_verified_against_system: false",
        "final_upload_checklist:",
        "target_journal_selected: false",
        "target_journal_template_applied: false",
        "author_metadata_completed: false",
        "corresponding_author_completed: false",
        "manuscript_pdf_rebuilt_after_template: false",
        "supplementary_pdf_rebuilt_after_template: false",
        "submission_system_files_verified: false",
        "artifact_release_prepared_or_linked: false",
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
        "target_journal_selected: false": "target journal checklist item is incomplete",
        "target_journal_template_applied: false": "target journal template checklist item is incomplete",
        "author_metadata_completed: false": "author metadata checklist item is incomplete",
        "corresponding_author_completed: false": "corresponding author checklist item is incomplete",
        "manuscript_pdf_rebuilt_after_template: false": "manuscript PDF rebuild checklist item is incomplete",
        "supplementary_pdf_rebuilt_after_template: false": "supplementary PDF rebuild checklist item is incomplete",
        "submission_system_files_verified: false": "submission system file checklist item is incomplete",
        "artifact_release_prepared_or_linked: false": "artifact release checklist item is incomplete",
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


def extract_pdf_text(pdf_path: Path) -> tuple[str, list[str]]:
    """Extract text from all pages of a PDF.

    参数:
        pdf_path: PDF file path.

    返回:
        tuple[str, list[str]]: Extracted full text and extraction errors.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        if len(reader.pages) < 1:
            return "", ["PDF has no pages"]
        return "\n".join(page.extract_text() or "" for page in reader.pages), []
    except ModuleNotFoundError:
        LOGGER.info("pypdf is not installed; falling back to pdftotext for full PDF text: %s", pdf_path.name)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("pypdf failed for full PDF text %s; falling back to pdftotext: %s", pdf_path.name, exc)

    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return "", ["pypdf is not installed and pdftotext is not available"]
    try:
        result = subprocess.run([pdftotext, str(pdf_path), "-"], check=True, capture_output=True, text=True)
        return result.stdout, []
    except subprocess.CalledProcessError as exc:
        return "", [f"pdftotext failed with exit code {exc.returncode}: {exc.stderr.strip()}"]


def check_pdf_first_page_markers(pdf_name: str, first_page_text: str, required_texts: list[str]) -> list[str]:
    """Check required text markers in extracted PDF first-page text.

    参数:
        pdf_name: PDF file name for diagnostics.
        first_page_text: Extracted first-page text.
        required_texts: Text markers expected on the first page.

    返回:
        list[str]: Error messages for missing or unresolved first-page text markers.
    """
    errors: list[str] = []
    for required_text in required_texts:
        if required_text not in first_page_text:
            errors.append(f"{pdf_name} first page text does not contain required text: {required_text}")
    unresolved_markers = ["undefined references", "LaTeX Warning", "[?]", "??"]
    for marker in unresolved_markers:
        if marker in first_page_text:
            errors.append(f"{pdf_name} may contain unresolved marker on first page: {marker}")
    return errors


def check_pdf_full_text_markers(pdf_path: Path, required_texts: list[str]) -> list[str]:
    """Check required text markers in extracted full PDF text.

    参数:
        pdf_path: PDF file path.
        required_texts: Text markers expected somewhere in the PDF.

    返回:
        list[str]: Error messages for full-text extraction or missing markers.
    """
    full_text, extraction_errors = extract_pdf_text(pdf_path)
    errors = [f"{pdf_path.name} full text is not readable: {error}" for error in extraction_errors]
    if extraction_errors:
        return errors
    for required_text in required_texts:
        if required_text not in full_text:
            errors.append(f"{pdf_path.name} full text does not contain required text: {required_text}")
    return errors


def check_pdf(pdf_path: Path, required_text: str | list[str] = "IAD-Risk") -> list[str]:
    """Check whether a generated PDF is readable.

    参数:
        pdf_path: Path to the generated PDF.
        required_text: Text marker or markers expected on the first page.

    返回:
        list[str]: Error messages for PDF readability issues.
    """
    errors = []
    first_page_text, extraction_errors = extract_first_page_text(pdf_path)
    errors.extend(f"{pdf_path.name} is not readable: {error}" for error in extraction_errors)
    if extraction_errors:
        return errors
    required_texts = [required_text] if isinstance(required_text, str) else required_text
    return errors + check_pdf_first_page_markers(pdf_path.name, first_page_text, list(required_texts))


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
    target_journal_shortlist_path = ROOT / "target_journal_shortlist.md"
    target_journal_shortlist_text = (
        target_journal_shortlist_path.read_text(encoding="utf-8") if target_journal_shortlist_path.exists() else ""
    )
    artifact_release_template_path = ROOT / "artifact_release_manifest.template.json"
    artifact_release_template_text = (
        artifact_release_template_path.read_text(encoding="utf-8") if artifact_release_template_path.exists() else ""
    )
    artifact_release_readme_template_path = ROOT / "artifact_release_README.template.md"
    artifact_release_readme_template_text = (
        artifact_release_readme_template_path.read_text(encoding="utf-8")
        if artifact_release_readme_template_path.exists()
        else ""
    )
    submission_system_checklist_path = ROOT / "submission_system_checklist.md"
    submission_system_checklist_text = (
        submission_system_checklist_path.read_text(encoding="utf-8") if submission_system_checklist_path.exists() else ""
    )
    reviewer_readiness_audit_path = ROOT / "reviewer_readiness_audit.md"
    reviewer_readiness_audit_text = (
        reviewer_readiness_audit_path.read_text(encoding="utf-8") if reviewer_readiness_audit_path.exists() else ""
    )
    cover_letter_path = ROOT / "cover_letter.md"
    cover_letter_text = cover_letter_path.read_text(encoding="utf-8") if cover_letter_path.exists() else ""
    submission_metadata_path = ROOT / "submission_metadata.yml"
    submission_metadata_text = submission_metadata_path.read_text(encoding="utf-8") if submission_metadata_path.exists() else ""
    elsevier_draft_source_path = ROOT / "build" / "iad-risk-manuscript-elsevier.tex"
    elsevier_draft_source_text = (
        elsevier_draft_source_path.read_text(encoding="utf-8") if elsevier_draft_source_path.exists() else ""
    )
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
                "target journal shortlist": target_journal_shortlist_text,
                "cover letter": cover_letter_text,
            }
        )
    )
    errors.extend(
        check_formal_submission_claim_lockdown(
            {
                "main manuscript": manuscript_text,
                "supplementary material": supplementary_text,
                "highlights": highlights_text,
                "keywords": keywords_text,
                "cover letter": cover_letter_text,
                "DKE/Elsevier draft source": elsevier_draft_source_text,
            }
        )
    )
    errors.extend(
        check_formal_source_typography_hygiene(
            {
                "main manuscript": manuscript_text,
                "supplementary material": supplementary_text,
                "highlights": highlights_text,
                "keywords": keywords_text,
                "cover letter": cover_letter_text,
                "references": bibliography_text,
                "DKE/Elsevier draft source": elsevier_draft_source_text,
            }
        )
    )
    errors.extend(check_abstract_quantitative_evidence(manuscript_text))
    errors.extend(check_abstract_length(manuscript_text))
    errors.extend(check_contribution_evidence_summary(manuscript_text))
    errors.extend(check_openv2_benchmark_composition(manuscript_text))
    errors.extend(check_iad_bench_document_schema_contract(manuscript_text))
    errors.extend(check_iad_bench_pair_schema_contract(manuscript_text))
    errors.extend(check_method_feature_contract(manuscript_text))
    errors.extend(check_design_alternative_boundaries(manuscript_text))
    errors.extend(check_related_work_positioning(manuscript_text))
    errors.extend(check_error_taxonomy(manuscript_text))
    errors.extend(check_validity_threats(manuscript_text))
    errors.extend(check_declaration_statements(manuscript_text))
    errors.extend(check_operating_point_disclosure(manuscript_text))
    errors.extend(check_statistical_interpretation_boundary(manuscript_text))
    errors.extend(check_threshold_sensitivity_status(manuscript_text))
    errors.extend(check_baseline_scope_alignment(manuscript_text))
    errors.extend(check_split_leakage_controls(manuscript_text))
    errors.extend(check_scope_compatibility(manuscript_text))
    errors.extend(check_extended_protocol_boundary(manuscript_text))
    errors.extend(check_environment_setup(supplementary_text))
    errors.extend(check_target_journal_shortlist(target_journal_shortlist_text))
    errors.extend(check_artifact_release_manifest_template(artifact_release_template_text))
    errors.extend(check_artifact_release_readme_template(artifact_release_readme_template_text))
    errors.extend(check_submission_system_checklist(submission_system_checklist_text))
    errors.extend(check_reviewer_readiness_audit(reviewer_readiness_audit_text))
    errors.extend(check_manual_validation_protocol(supplementary_text))
    errors.extend(check_result_claim_boundary(manuscript_text, supplementary_text))
    errors.extend(check_highlights(highlights_text))
    errors.extend(check_keywords(keywords_text))
    errors.extend(check_elsevier_draft_source(manuscript_text, keywords_text, elsevier_draft_source_text))
    errors.extend(check_cover_letter(cover_letter_text))
    errors.extend(check_submission_material_quantitative_summary(highlights_text, cover_letter_text))
    errors.extend(
        check_editorial_claim_alignment(
            manuscript_text,
            cover_letter_text,
            highlights_text,
            keywords_text,
            submission_metadata_text,
        )
    )
    errors.extend(check_submission_metadata(submission_metadata_text))
    if args.final_upload:
        errors.extend(check_final_upload_metadata(submission_metadata_text))
    errors.extend(check_bibliography_depth(bibliography_text))
    errors.extend(
        check_citation_bibliography_alignment(
            {
                "main manuscript": manuscript_text,
                "supplementary material": supplementary_text,
                "DKE/Elsevier draft source": elsevier_draft_source_text,
            },
            bibliography_text,
        )
    )
    errors.extend(
        check_latex_cross_references(
            {
                "main manuscript": manuscript_text,
                "supplementary material": supplementary_text,
                "DKE/Elsevier draft source": elsevier_draft_source_text,
            }
        )
    )
    latex_pdf_path = ROOT / "build" / "iad-risk-manuscript-latex.pdf"
    elsevier_pdf_path = ROOT / "build" / "iad-risk-manuscript-elsevier.pdf"
    supplementary_pdf_path = ROOT / "build" / "iad-risk-supplementary-material.pdf"
    main_pdf_markers = [
        "IAD-Risk: Risk-Aware",
        "Scholarly Work Deduplication",
        "Anonymous Authors",
        "Abstract",
        "Open-v2 evidence snapshot",
        "same-work F1=0.980",
        "HNFMR=0.000",
    ]
    errors.extend(check_pdf(latex_pdf_path, main_pdf_markers))
    main_full_text_markers = [
        "Related Work",
        "Problem Formulation",
        "Experiments",
        "Mechanism and Error Analysis",
        "Threats to Validity",
        "Conclusion",
        "Data and Code Availability",
        "Ethics Statement",
        "Competing Interests",
        "References",
    ]
    errors.extend(check_pdf_full_text_markers(latex_pdf_path, main_full_text_markers))
    errors.extend(check_pdf_freshness(latex_pdf_path, manuscript_path))
    errors.extend(check_pdf(elsevier_pdf_path, main_pdf_markers + ["Keywords:", "Data & Knowledge Engineering"]))
    errors.extend(check_pdf_full_text_markers(elsevier_pdf_path, main_full_text_markers))
    errors.extend(check_pdf_freshness(elsevier_pdf_path, manuscript_path))
    errors.extend(check_pdf_freshness(elsevier_pdf_path, keywords_path))
    errors.extend(
        check_pdf(
            supplementary_pdf_path,
            ["Supplementary Material for IAD-Risk", "Anonymous Authors", "Scope", "Reproduction Levels"],
        )
    )
    errors.extend(
        check_pdf_full_text_markers(
            supplementary_pdf_path,
            [
                "Artifact Package Requirements",
                "Claim-Evidence Matrix",
                "Manual Validation Protocol",
                "Claim Boundary",
            ],
        )
    )
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
