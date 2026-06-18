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
import sys
from pathlib import Path


LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
from submission_metadata_checks import (
    FINAL_UPLOAD_TRUE_FIELDS,
    check_final_upload_cover_letter_text as check_structured_final_upload_cover_letter_text,
    check_final_upload_metadata_text as check_structured_final_upload_metadata_text,
)

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
    ROOT / "final_upload_information_request.md",
    ROOT / "submission_system_checklist.md",
    ROOT / "reviewer_readiness_audit.md",
    ROOT / "submission_metadata.yml",
    ROOT / "scripts" / "validate_manuscript.py",
    ROOT / "scripts" / "submission_metadata_checks.py",
    ROOT / "scripts" / "verify_fixture_rebuild.py",
    ROOT / "scripts" / "build_submission_package.py",
    ROOT / "scripts" / "validate_submission_package.py",
    ROOT / "scripts" / "validate_artifact_release.py",
    ROOT / "scripts" / "build_artifact_release_skeleton.py",
    ROOT / "scripts" / "populate_artifact_release.py",
    ROOT / "scripts" / "finalize_artifact_release.py",
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
    r"\subsection{Scoring and Merge Algorithm}",
    r"\subsection{Implementation and Reproducibility}",
    r"\section{Experiments}",
    r"\subsection{Split and Leakage Controls}",
    r"\subsection{Threshold Selection and Uncertainty Reporting}",
    r"\subsection{Decision-to-Metric Mapping}",
    r"\subsection{Metric Formula Boundary}",
    r"\subsection{Statistical Interpretation Boundary}",
    r"\subsection{Operating Point Disclosure}",
    r"\subsection{Selective Decision Coverage Boundary}",
    r"\subsection{Pair-to-Cluster Evidence Boundary}",
    r"\subsection{Threshold Sensitivity Evidence Status}",
    r"\subsection{Claim-Evidence Boundary for Result Interpretation}",
    r"\subsection{Result Audit Trail}",
    r"\label{tab:result-artifact-crosswalk}",
    r"\subsection{Scope Compatibility of the Open-v2 Table}",
    r"\section{Mechanism and Error Analysis}",
    r"\section{Limitations}",
    r"\section{Threats to Validity}",
    r"\section{Claim Interpretation Boundary}",
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
    r"\section{Reviewer Evidence Gate}",
    r"\section{Manual Validation Protocol}",
    r"\section{Claim Boundary}",
]
MIN_BIB_ENTRIES = 10
CITATION_COMMAND_PATTERN = re.compile(
    r"\\(?:cite|citep|citet|citealp|citealt|citeauthor|citeyear|citeyearpar)\*?(?:\s*\[[^\]]*\]){0,2}\s*\{([^}]+)\}"
)
BIBTEX_ENTRY_PATTERN = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,", re.MULTILINE)
BIBTEX_ENTRY_BLOCK_PATTERN = re.compile(
    r"@(?P<entry_type>\w+)\s*\{\s*(?P<entry_key>[^,\s]+)\s*,(?P<body>.*?)(?=\n@\w+\s*\{|\Z)",
    re.DOTALL,
)
BIBTEX_FIELD_PATTERN = re.compile(r"(?<![A-Za-z0-9_-])(?P<field_name>[A-Za-z][A-Za-z0-9_-]*)\s*=")
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
FORMAL_MANUSCRIPT_INTERNAL_REVIEW_MARKERS = [
    "Reviewer-Facing",
    "reviewer-facing",
    "Reviewer interpretation",
    "Reviewer audit purpose",
    "Reviewer use",
    "reviewer relevance",
    "reviewer concerns",
    "important for review",
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
UNSUPPORTED_RISK_CALIBRATION_PATTERNS = [
    re.compile(r"\brisk[-\s]?calibrated\b", re.IGNORECASE),
    re.compile(r"\bcalibrated\s+false[-\s]?merge\s+risk\b", re.IGNORECASE),
    re.compile(r"\bcalibrated\s+risk\s+(?:score|estimate|probability)\b", re.IGNORECASE),
    re.compile(r"\bwell[-\s]?calibrated\s+(?:risk|probability|score)\b", re.IGNORECASE),
]
UNSUPPORTED_ABSTRACT_CLUSTER_PATTERNS = [
    re.compile(r"\bprevent\w*\b.{0,120}\bautomatic\s+merge\s+clusters\b", re.IGNORECASE),
    re.compile(r"\beliminat\w*\b.{0,120}\bcluster[-\s]?level\s+contamination\b", re.IGNORECASE),
    re.compile(r"\bguarantee\w*\b.{0,120}\bcluster[-\s]?level\b", re.IGNORECASE),
]
UNSUPPORTED_METHOD_CLUSTER_PATTERNS = [
    re.compile(r"\bcannot-link\s+evidence\s+prevents\s+transitive\s+false\s+merges\b", re.IGNORECASE),
    re.compile(r"\bguarantee\w*\s+(?:complete\s+)?cluster[-\s]?level\b", re.IGNORECASE),
]
AUXILIARY_MODEL_EVIDENCE_PHRASES = [
    "LLM",
    "GPT",
    "OpenAI",
    "ChatGPT",
    "pair-judge",
]
FORMAL_PROCESS_TRACE_PATTERNS = [
    (re.compile(r"\b(?:Codex|Claude)\b", re.IGNORECASE), "AI tool trace"),
    (re.compile(r"\b(?:AI-assisted|AI-generated|generated by AI)\b", re.IGNORECASE), "AI generation trace"),
    (
        re.compile(r"(?:AI\s*辅助|AI\s*生成|已修改|修改记录|工作记录|工作总结|本次修改|本轮修改|处理记录|变更记录)"),
        "process-note trace",
    ),
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
FINAL_UPLOAD_REQUEST_EXCLUDED_TRUE_FIELDS = {"target_journal_template_bound"}
FINAL_UPLOAD_REQUEST_CHECKLIST_FIELDS = [
    field_name
    for field_name in FINAL_UPLOAD_TRUE_FIELDS
    if field_name not in FINAL_UPLOAD_REQUEST_EXCLUDED_TRUE_FIELDS
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


def check_final_upload_information_request(request_text: str) -> list[str]:
    """Check whether the final-upload information request covers external inputs.

    参数:
        request_text: Final-upload information request Markdown text.

    返回:
        list[str]: Error messages for missing request fields.
    """
    required_markers = [
        "# Final Upload Information Request",
        "Submission metadata mapping",
        "After the authors complete this form",
        "`submission_metadata.yml`, `cover_letter.md`, and the live submission system",
        "python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release",
        "Repository URL and commit binding",
        "git remote origin",
        "git rev-parse HEAD",
        "package copy of `submission_metadata.yml`",
        "self-referential Git commit value",
        "Primary `submission_metadata.yml` target",
        "Additional file or system target",
        "`submission`, `target_preparation`, `target_journal_template_bound`, `final_upload_checklist.target_journal_selected`",
        "`authors`, `author_contributions.roles`, `final_upload_checklist.author_metadata_completed`",
        "`corresponding_author`, `final_upload_checklist.corresponding_author_completed`",
        "`funding`, `statements`, `final_upload_checklist.funding_statement_text_ready`",
        "`author_contributions`, `final_upload_checklist.contribution_statement_complete`",
        "`permissions`, `final_upload_checklist.permissions_statement_complete`",
        "`generative_ai`, `final_upload_checklist.generative_ai_declaration_complete`",
        "`repository_reference`, `artifact_boundary`, `statements.research_data_statement`",
        "`artifact_boundary`, `final_upload_checklist.artifact_release_prepared_or_linked`",
        "`final_upload_checklist.manuscript_pdf_rebuilt_after_template`",
        "`final_upload_checklist.first_screen_claim_lockdown_confirmed`",
        "Target journal",
        "Article type",
        "Review mode",
        "Author list",
        "Author order",
        "Corresponding author",
        "Funding statement",
        "Author contribution statement",
        "CRediT author contribution statement",
        "Conceptualization",
        "Data curation",
        "Formal analysis",
        "Funding acquisition",
        "Investigation",
        "Methodology",
        "Project administration",
        "Resources",
        "Software",
        "Supervision",
        "Validation",
        "Visualization",
        "Writing - original draft",
        "Writing - review and editing",
        "Permissions statement",
        "Generative AI declaration",
        "AI tools used in manuscript preparation",
        "Author review and responsibility confirmed",
        "AI tool not listed as author or co-author",
        "Machine-generated figures, images, or artwork included",
        "Competing interests",
        "Ethics statement",
        "Data and code availability statement",
        "Repository URL and commit will be injected into the final-upload package copy",
        "Artifact release URL or DOI",
        "Artifact release directory path for final validation",
        "Artifact release manifest",
        "Live submission-system fields",
        "Submission text consistency",
        "Title source checked against `main.tex`",
        "Abstract copied exactly from `main.tex`",
        "Keywords copied exactly from `keywords.md`",
        "Highlights copied exactly from `highlights.md`",
        "First-page title, abstract, keywords, and highlights were previewed in the live submission system",
        "First-screen claim lockdown confirmed",
        "First-screen materials preserve the Open-v2 evidence boundary",
        "Final title page",
        "Final-upload checklist",
    ]
    required_markers.extend(f"- {field_name}:" for field_name in FINAL_UPLOAD_REQUEST_CHECKLIST_FIELDS)
    return [
        f"final upload information request missing marker: {marker}"
        for marker in required_markers
        if marker not in request_text
    ]


def check_data_code_availability_boundary(manuscript_text: str) -> list[str]:
    """Check whether the data/code availability statement separates repository and artifact scope.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing data/code availability boundary markers.
    """
    required_markers = [
        r"\section*{Data and Code Availability}",
        r"\label{tab:data-code-availability-boundary}",
        "Source code and CLI entry points",
        "Small public fixtures and schema contracts",
        "Raw third-party source files",
        "Full prediction files and model checkpoints",
        "Derived evaluation artifacts",
        "prediction files, threshold logs, manifests, checksums, and commit identifiers",
        "L0/L1 code-level reproduction",
        "L2/L3 result-level audit",
        "raw third-party data remain governed by original provider licenses",
        "full numerical reproduction requires public-source rebuilds or released artifacts",
    ]
    lowered_text = manuscript_text.lower()
    return [
        f"data/code availability boundary missing marker: {marker}"
        for marker in required_markers
        if marker.lower() not in lowered_text
    ]


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
    """Check whether formal submission materials exclude unsupported model or process traces.

    参数:
        document_texts: Mapping from document name to formal submission text.

    返回:
        list[str]: Error messages for auxiliary model evidence phrases or process traces.
    """
    errors: list[str] = []
    for document_name, document_text in document_texts.items():
        lowered_text = document_text.lower()
        for phrase in AUXILIARY_MODEL_EVIDENCE_PHRASES:
            if phrase.lower() in lowered_text:
                errors.append(f"{document_name} contains unsupported auxiliary model evidence phrase: {phrase}")
        for pattern, label in FORMAL_PROCESS_TRACE_PATTERNS:
            for match in pattern.finditer(document_text):
                errors.append(f"{document_name} contains {label}: {match.group(0)}")
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


def check_formal_manuscript_review_language(
    manuscript_text: str,
    document_name: str = "formal manuscript",
) -> list[str]:
    """Check whether formal manuscript text avoids internal review-workflow labels.

    参数:
        manuscript_text: Formal manuscript or supplementary LaTeX source text.
        document_name: Human-readable document name used in validation errors.

    返回:
        list[str]: Error messages for internal reviewer-workflow markers.
    """
    errors: list[str] = []
    for marker in FORMAL_MANUSCRIPT_INTERNAL_REVIEW_MARKERS:
        if marker in manuscript_text:
            errors.append(f"{document_name} contains internal review marker: {marker}")
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


def check_abstract_cluster_overclaim(manuscript_text: str) -> list[str]:
    """Check whether the abstract avoids unsupported cluster-level guarantees.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for cluster-level claims that exceed current evidence.
    """
    begin_marker = r"\begin{abstract}"
    end_marker = r"\end{abstract}"
    if begin_marker not in manuscript_text or end_marker not in manuscript_text:
        return ["abstract cluster claim check could not locate abstract environment"]
    abstract_text = manuscript_text.split(begin_marker, 1)[1].split(end_marker, 1)[0]
    errors: list[str] = []
    for pattern in UNSUPPORTED_ABSTRACT_CLUSTER_PATTERNS:
        for match in pattern.finditer(abstract_text):
            errors.append(f"unsupported abstract cluster-level claim found: {match.group(0)}")
    required_markers = [
        "pair-level",
        "cluster artifacts",
    ]
    for marker in required_markers:
        if marker not in abstract_text:
            errors.append(f"abstract missing pair-level claim boundary marker: {marker}")
    return errors


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


def check_motivating_failure_case(manuscript_text: str) -> list[str]:
    """Check whether the introduction includes a concrete identity-agenda failure case.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing motivating failure-case markers.
    """
    required_markers = [
        r"\subsection{Motivating Failure Case}",
        r"\label{tab:motivating-failure-case}",
        "same task or benchmark",
        "different contribution",
        "high semantic similarity",
        "unsafe automatic merge",
        "same-work identity evidence",
        "agenda relatedness is not identity evidence",
        "illustrative failure case, not a prevalence estimate",
        "HNFMR",
    ]
    return [
        f"motivating failure case missing marker: {marker}"
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


def extract_bibtex_entry_fields(bibliography_text: str) -> dict[str, set[str]]:
    """Extract field names for each BibTeX entry.

    参数:
        bibliography_text: BibTeX source text.

    返回:
        dict[str, set[str]]: Mapping from BibTeX key to lower-cased field names.
    """
    entry_fields: dict[str, set[str]] = {}
    for match in BIBTEX_ENTRY_BLOCK_PATTERN.finditer(bibliography_text):
        entry_key = match.group("entry_key").strip()
        body = match.group("body")
        field_names = {
            field_match.group("field_name").strip().lower()
            for field_match in BIBTEX_FIELD_PATTERN.finditer(body)
        }
        entry_fields[entry_key] = field_names
    return entry_fields


def check_bibliography_entry_metadata(bibliography_text: str) -> list[str]:
    """Check whether each BibTeX entry has core publication metadata.

    参数:
        bibliography_text: BibTeX source text.

    返回:
        list[str]: Error messages for incomplete BibTeX metadata fields.
    """
    entry_fields = extract_bibtex_entry_fields(bibliography_text)
    errors: list[str] = []
    for entry_key, field_names in entry_fields.items():
        for required_field in ["title", "author", "year"]:
            if required_field not in field_names:
                errors.append(f"references.bib entry {entry_key} missing required field: {required_field}")
        if "journal" not in field_names and "booktitle" not in field_names:
            errors.append(f"references.bib entry {entry_key} missing venue field: journal or booktitle")
    return errors


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
        "per-row denominator counts",
        "per-row threshold source",
        "scope label used in the main table",
        "automatic merge count",
        "block count",
        "defer count",
        "automatic merge coverage",
        "defer rate",
        "pair/document IDs",
        "score or probability fields",
        "threshold name",
        "selection split",
        "selection metric",
        "artifact-level and manuscript-package validation",
        r"\path{manuscript/scripts/validate_artifact_release.py}",
        r"\path{manuscript/scripts/validate_submission_package.py}",
        r"\texttt{--final-upload --artifact-dir /path/to/release}",
        "same source commit",
        "should not be used to support the Open-v2 numerical table",
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
        "python manuscript/scripts/build_artifact_release_skeleton.py",
        "python manuscript/scripts/populate_artifact_release.py",
        "python manuscript/scripts/finalize_artifact_release.py",
        "python manuscript/scripts/validate_artifact_release.py",
        "required result identifiers",
        "conditional claim artifacts",
        r"\path{open_v2_main_results}",
        "per-row denominator counts",
        "per-row threshold source",
        "scope label used in the main table",
        "automatic merge count",
        "block count",
        "defer count",
        "automatic merge coverage",
        "defer rate",
        "row-auditable",
        "pair_id",
        "normalized score",
        "match_probability",
        "selection_rule",
        r"\path{threshold_sensitivity_grid}",
        r"\path{cluster_metric_summary}",
        r"\path{cannot_link_audit}",
        "cluster-level quality claims",
        "cluster assignments",
        "cannot-link coverage",
        "cluster contamination rate",
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


def check_training_objective_masking(manuscript_text: str) -> list[str]:
    """Check whether the training objective states explicit supervision masks.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing masked-loss markers.
    """
    required_markers = [
        r"\subsection{Training Objective}",
        r"m^w_{ij}",
        r"m^a_{ij}",
        r"m^n_{ij}",
        r"\sum_{(i,j)}",
        r"\sum_{(i,j)}(m^w_{ij}+m^a_{ij}+m^n_{ij})",
        "valid supervision channels",
        "Missing labels therefore do not create negative examples",
        "Z=0",
        "skipped before the optimizer update",
        "positive mask coverage in the declared training split",
        "false-merge risk score is not directly supervised",
    ]
    return [f"training objective masking missing marker: {marker}" for marker in required_markers if marker not in manuscript_text]


def check_risk_score_design_rationale(manuscript_text: str) -> list[str]:
    """Check whether the method explains the false-merge risk score design.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing risk-score rationale markers.
    """
    required_markers = [
        r"\subsection{Risk Score Design Rationale}",
        r"\label{tab:risk-score-rationale}",
        r"$p_{\mathrm{risk}}$ is a conservative upper-envelope risk proxy",
        "increases monotonically with agenda-non-identity evidence",
        "agenda evidence is high and identity evidence is weak",
        "max operator",
        "direct ANI evidence or indirect agenda-without-identity evidence",
        "not a calibrated probability",
        "Threshold transfer must be rechecked under new source distributions",
        "defer rather than merge",
    ]
    return [
        f"risk score design rationale missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_risk_calibration_overclaims(manuscript_text: str) -> list[str]:
    """Check whether the manuscript avoids unsupported risk-calibration wording.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for calibration wording that requires unavailable evidence.
    """
    errors: list[str] = []
    for pattern in UNSUPPORTED_RISK_CALIBRATION_PATTERNS:
        for match in pattern.finditer(manuscript_text):
            errors.append(f"unsupported risk calibration wording found: {match.group(0)}")
    return errors


def check_method_cluster_overclaims(manuscript_text: str) -> list[str]:
    """Check whether the method avoids unsupported cluster-level guarantees.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for method claims that require cluster artifacts.
    """
    errors: list[str] = []
    for pattern in UNSUPPORTED_METHOD_CLUSTER_PATTERNS:
        for match in pattern.finditer(manuscript_text):
            errors.append(f"unsupported method cluster-level claim found: {match.group(0)}")
    return errors


def check_operational_net_benefit_boundary(manuscript_text: str) -> list[str]:
    """Check whether the method states deployment cost and net-benefit boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing operational net-benefit markers.
    """
    required_markers = [
        r"\subsection{Operational Complexity and Net Benefit}",
        r"\label{tab:operational-net-benefit}",
        "false merges are more costly than additional review",
        "three relation heads and explicit threshold records",
        "deferral budget and manual-review capacity",
        "not tuned per pair",
        "not a universal replacement",
        "net benefit is strongest in high-stakes scholarly indexes",
        "low-risk bulk cleanup",
    ]
    return [
        f"operational net-benefit boundary missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_version_identifier_policy(manuscript_text: str) -> list[str]:
    """Check whether the method states version and identifier merge boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing version/identifier boundary markers.
    """
    required_markers = [
        r"\subsection{Version and Identifier Boundary}",
        r"\label{tab:version-identifier-boundary}",
        "DOI, arXiv, and OpenAlex identifiers",
        "publication-lineage evidence",
        "identifier agreement supports merge eligibility",
        "identifier conflict creates cannot-link or defer evidence",
        "preprint, conference, and journal versions",
        "version policy must be declared before cluster-level merging",
        "not every related version is automatically the same work",
        "manual adjudication is required for ambiguous version boundaries",
    ]
    return [
        f"version and identifier boundary missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_method_pipeline_figure(manuscript_text: str) -> list[str]:
    """Check whether the method section includes the IAD-Risk pipeline figure.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing pipeline figure markers.
    """
    required_markers = [
        r"\subsection{Overview}",
        r"\ref{fig:iad-risk-pipeline}",
        r"\begin{figure}",
        "Candidate",
        "record pair",
        "Identity and",
        "agenda evidence",
        "Work, agenda",
        "ANI heads",
        "Risk-aware",
        "merge gate",
        "Merge, block",
        "or defer",
        r"\caption{IAD-Risk pipeline",
        r"\label{fig:iad-risk-pipeline}",
    ]
    return [f"method pipeline figure missing marker: {marker}" for marker in required_markers if marker not in manuscript_text]


def check_scoring_merge_algorithm(manuscript_text: str) -> list[str]:
    """Check whether the method states executable scoring and merge order.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing scoring-algorithm markers.
    """
    required_markers = [
        r"\subsection{Scoring and Merge Algorithm}",
        r"\subsection{Training and Inference Trace}",
        r"\label{tab:training-inference-trace}",
        "threshold fixation, inference, and metric export",
        "Schema loading",
        "Supervised fitting",
        "Threshold fixation",
        "Pair scoring",
        "Decision emission",
        "Metric export",
        r"\label{tab:scoring-merge-algorithm}",
        "fixed scoring and merge order",
        "identity, agenda, ANI, and audit fields",
        "without using audit metadata as predictors",
        r"$p_{\mathrm{work}}$",
        r"$p_{\mathrm{agenda}}$",
        r"$p_{\mathrm{ani}}$",
        r"$p_{\mathrm{risk}}=\max\{p_{\mathrm{ani}},p_{\mathrm{agenda}}(1-p_{\mathrm{work}})\}$",
        "cannot-link flag",
        "merge, block, or defer",
        "same-work F1, FMR, HNFMR, coverage, and defer-rate audits",
    ]
    return [
        f"scoring and merge algorithm missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


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


def check_selective_decision_coverage_boundary(manuscript_text: str) -> list[str]:
    """Check whether selective merge decisions state coverage and deferral boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing selective-decision coverage markers.
    """
    required_markers = [
        r"\subsection{Selective Decision Coverage Boundary}",
        r"\label{tab:selective-decision-coverage}",
        "Automatic merge coverage",
        "Block rate",
        "defer rate",
        "Review load",
        "same prediction files",
        "does not claim throughput reduction",
        "does not claim all-pair automatic resolution",
    ]
    return [
        f"selective decision coverage boundary missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_pair_cluster_evidence_boundary(manuscript_text: str) -> list[str]:
    """Check whether pair-level metrics are separated from cluster-level claims.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing pair-to-cluster evidence boundaries.
    """
    required_markers = [
        r"\subsection{Pair-to-Cluster Evidence Boundary}",
        r"\label{tab:pair-cluster-evidence-boundary}",
        "pair-level metrics do not by themselves prove cluster-level deduplication quality",
        "transitive merge propagation",
        "cannot-link violations",
        "cluster assignments",
        "cluster_metric_summary",
        "cannot_link_audit",
        "cluster contamination rate",
        "does not claim cluster-level contamination is eliminated",
    ]
    return [
        f"pair-to-cluster evidence boundary missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_decision_metric_mapping(manuscript_text: str) -> list[str]:
    """Check whether selective decisions are mapped to reported metrics.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing decision-to-metric mapping markers.
    """
    required_markers = [
        r"\subsection{Decision-to-Metric Mapping}",
        r"\label{tab:decision-metric-mapping}",
        "automatic merge is the positive decision",
        "block and defer are non-merge decisions",
        "Deferred same-work pairs reduce recall",
        "FMR and HNFMR count only automatic merges among non-identity rows",
        "coverage and defer rate must be reported separately",
    ]
    return [
        f"decision-to-metric mapping missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_metric_formula_boundary(manuscript_text: str) -> list[str]:
    """Check whether reported metrics define formulas and denominators.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing metric-formula boundary markers.
    """
    required_markers = [
        r"\subsection{Metric Formula Boundary}",
        r"\label{tab:metric-formula-boundary}",
        "TP",
        "FP",
        "FN",
        r"$2TP/(2TP+FP+FN)$",
        "FMR denominator is all non-identity rows in the evaluated scope",
        "HNFMR denominator is the agenda-level hard-negative subset",
        "missing labels are not silently added to denominators",
    ]
    return [
        f"metric formula boundary missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


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


def check_baseline_inclusion_rationale(manuscript_text: str) -> list[str]:
    """Check whether baseline inclusion and exclusion rules are explicit.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing baseline inclusion rationale.
    """
    required_markers = [
        r"\subsection{Baseline Inclusion Rationale}",
        r"\label{tab:baseline-inclusion-rationale}",
        "exact identifier matching",
        "title-normalization rules",
        "Traditional entity-resolution systems",
        "Scientific representation baselines",
        "RoBERTa pair classification",
        "Included as primary evidence only when metric summaries, prediction files, threshold records, and checksums are available",
        "Excluded from primary result table when only utility code or fixture-level checks are available",
        "not a claim that omitted baselines were outperformed",
        "same-scope baseline matrix is required before broad ranking claims",
    ]
    return [
        f"baseline inclusion rationale missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_baseline_fairness_controls(manuscript_text: str) -> list[str]:
    """Check whether baseline comparisons state fairness controls.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing baseline fairness markers.
    """
    required_markers = [
        r"\subsection{Baseline Fairness Controls}",
        r"\label{tab:baseline-fairness-controls}",
        "same IAD-Bench pair records",
        "same train/dev/test split field",
        "validation-selected operating points",
        "same-work F1, FMR, and HNFMR",
        "same metric implementation",
        "not predictive features",
        "same-scope released prediction files",
        "not be read as a single comparative ranking",
    ]
    return [
        f"baseline fairness controls missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_result_interpretation_guardrails(manuscript_text: str) -> list[str]:
    """Check whether the main result table states allowed and unsupported readings.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing result-interpretation guardrails.
    """
    required_markers = [
        r"\subsection{Result Interpretation Guardrails}",
        r"\label{tab:result-interpretation-guardrails}",
        "Directly supported reading",
        "Mechanism-supported reading",
        "Unsupported reading",
        "Scope type",
        "full available Open-v2 scope",
        "held-out Open-v2 test scope",
        "Scope labels prevent ranking interpretation",
        "representation rows test false-merge exposure",
        "RoBERTa row is a strong supervised comparator",
        "IAD-Risk rows test split-held-out risk gating",
        "not a claim of broad method superiority",
        "not a same-scope comparative ranking",
        "not evidence of threshold stability or zero risk",
    ]
    return [
        f"result interpretation guardrails missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def extract_latex_table_by_label(manuscript_text: str, table_label: str) -> str:
    """Extract a LaTeX table environment by label.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        table_label: LaTeX label text, including the ``tab:`` prefix.

    返回:
        str: Table environment text, or an empty string when the label is absent.
    """
    label_marker = rf"\label{{{table_label}}}"
    label_position = manuscript_text.find(label_marker)
    if label_position < 0:
        return ""
    table_start = manuscript_text.rfind(r"\begin{table}", 0, label_position)
    table_end = manuscript_text.find(r"\end{table}", label_position)
    if table_start < 0 or table_end < 0:
        return ""
    return manuscript_text[table_start : table_end + len(r"\end{table}")]


def parse_latex_tabular_rows(table_text: str) -> list[list[str]]:
    """Parse simple booktabs-style LaTeX table rows into cells.

    参数:
        table_text: LaTeX table source text.

    返回:
        list[list[str]]: Parsed rows, with cells stripped of row terminators and whitespace.
    """
    rows: list[list[str]] = []
    for raw_line in table_text.splitlines():
        line = raw_line.strip()
        if "&" not in line or line.startswith("\\"):
            continue
        line = line.removesuffix(r"\\").strip()
        rows.append([cell.strip() for cell in line.split("&")])
    return rows


def check_openv2_result_table_scope_labels(manuscript_text: str) -> list[str]:
    """Check that each Open-v2 result row records its evaluation scope.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing or incorrect Open-v2 result-table scope labels.
    """
    if r"\label{tab:openv2-results}" not in manuscript_text:
        return []
    table_text = extract_latex_table_by_label(manuscript_text, "tab:openv2-results")
    if not table_text:
        return ["Open-v2 result table could not be extracted by label: tab:openv2-results"]
    rows = parse_latex_tabular_rows(table_text)
    if not rows:
        return ["Open-v2 result table contains no parseable rows"]
    header = rows[0]
    errors: list[str] = []
    if len(header) < 2 or header[1] != "Scope type":
        errors.append("Open-v2 result table must use Scope type as the second column")
    if len(header) < 4 or header[3] != "Denom. audit":
        errors.append("Open-v2 result table must include Denom. audit as the fourth column")
    if "Denom. audit column" not in table_text or r"\texttt{open\_v2\_main\_results}" not in table_text:
        errors.append("Open-v2 result table caption must bind denominator audit to open_v2_main_results")
    expected_scopes = {
        "SciNCL cosine": "Full Open-v2",
        "SPECTER2 adapter cosine": "Full Open-v2",
        "RoBERTa pair classifier": "Full Open-v2",
        "IAD-Risk (SciNCL)": "Held-out test",
        "IAD-Risk (SPECTER2)": "Held-out test",
    }
    row_by_system = {row[0]: row for row in rows[1:] if row}
    for system_name, expected_scope in expected_scopes.items():
        row = row_by_system.get(system_name)
        if row is None:
            errors.append(f"Open-v2 result table missing result row: {system_name}")
            continue
        actual_scope = row[1] if len(row) > 1 else ""
        if actual_scope != expected_scope:
            errors.append(
                f"Open-v2 result row {system_name} must use scope type {expected_scope}; found {actual_scope or '<missing>'}"
            )
        denominator_audit = row[3] if len(row) > 3 else ""
        if denominator_audit != "Artifact row":
            errors.append(
                f"Open-v2 result row {system_name} must mark Denom. audit as Artifact row; "
                f"found {denominator_audit or '<missing>'}"
            )
    return errors


def check_manual_validation_boundary(manuscript_text: str) -> list[str]:
    """Check whether the main manuscript states manual-validation limits for silver labels.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing manual-validation boundary markers.
    """
    required_markers = [
        r"\subsection{Manual Validation Boundary}",
        r"\label{tab:manual-validation-boundary}",
        "Manual validation is not completed in the current manuscript package",
        "Silver hard negatives are stress-test evidence",
        "not human-gold non-identity labels",
        "500--1,000 pair reviewed slice",
        "two independent reviewers",
        "blind to model scores",
        "adjudication log",
        "agreement report",
        "does not claim complete human validation",
    ]
    return [
        f"manual validation boundary missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


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
        "not a single comparative ranking",
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


def check_reviewer_evidence_gate(supplementary_text: str) -> list[str]:
    """Check whether supplementary material states reviewer-facing evidence gates.

    参数:
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing reviewer-evidence gate markers.
    """
    required_markers = [
        r"\section{Reviewer Evidence Gate}",
        "Contribution clarity",
        "same-scope prediction files",
        "bootstrap intervals",
        "ablation suite",
        "manual-validation slice",
        "source-heldout validation",
        "cluster-level artifact audits",
        "do not upgrade claims",
    ]
    return [
        f"reviewer evidence gate missing marker: {marker}"
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
        "Source-to-Decision Audit",
        "Data & Knowledge Engineering Preflight",
        "Official guide rechecked: 2026-06-19",
        "Official source snapshot date: 2026-06-19",
        "DKE guide verified: 2026-06-19",
        "Information Systems guide verified: 2026-06-18",
        "Scientometrics guide verified: 2026-06-18",
        "provisional preparation only",
        "single anonymized review",
        "250-word limit",
        "1--7 semicolon-separated keywords",
        "3--5 highlights",
        "85-character limit",
        "Elsevier `elsarticle`",
        "real artifact URL or DOI",
        "generative AI declaration",
        "author biographies and photographs",
        "AI-tool use",
        "AI tools as authors",
        "Information Systems data statement is required",
        "CRediT author contribution statement",
        "large-language-model use should be documented",
        "copy-editing-only tool use",
        "Metrics are screening signals, not ranking proof",
        "Review model and author metadata rules determine anonymization",
        "Data statement and artifact link requirements determine final-upload blockers",
        "Recheck publisher pages on submission day",
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
        artifact_rows_by_id: dict[str, dict[str, object]] = {}
    else:
        artifact_ids = {str(row.get("artifact_id", "")) for row in artifacts if isinstance(row, dict)}
        artifact_rows_by_id = {
            str(row.get("artifact_id", "")): row for row in artifacts if isinstance(row, dict)
        }
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
        "cluster_metric_summary",
        "cannot_link_audit",
    }
    for artifact_id in required_artifact_ids:
        if artifact_id not in artifact_ids:
            errors.append(f"artifact release manifest template missing required artifact: {artifact_id}")
    for artifact_id in conditional_artifact_ids:
        if artifact_id not in artifact_ids:
            errors.append(f"artifact release manifest template missing conditional artifact: {artifact_id}")
    open_v2_row = artifact_rows_by_id.get("open_v2_main_results")
    if isinstance(open_v2_row, dict):
        claim_support = str(open_v2_row.get("claim_support", ""))
        for marker in [
            "per-row denominator counts",
            "per-row threshold source",
            "scope label used in the main table",
            "automatic merge count",
            "block count",
            "defer count",
            "automatic merge coverage",
            "defer rate",
        ]:
            if marker not in claim_support:
                errors.append(
                    "artifact release manifest template open_v2_main_results "
                    f"claim_support missing marker: {marker}"
                )
    claim_support_markers_by_artifact = {
        "iad_risk_predictions": [
            "pair_id",
            "source_document_id",
            "target_document_id",
            "expected labels",
            "label strength",
            "hard-negative level",
            "split identifiers",
            "relation-head scores",
            "work_threshold",
            "agenda_block_threshold",
            "risk_threshold",
            "threshold source",
            "merge_prediction",
        ],
        "representation_baseline_scores": [
            "pair_id",
            "source_document_id",
            "target_document_id",
            "expected labels",
            "label strength",
            "hard-negative level",
            "split identifiers",
            "normalized score",
            "score_field",
            "threshold_value",
            "threshold source",
            "merge_prediction",
        ],
        "supervised_baseline_predictions": [
            "pair_id",
            "source_document_id",
            "target_document_id",
            "expected labels",
            "label strength",
            "hard-negative level",
            "split identifiers",
            "match_probability",
            "threshold_value",
            "threshold source",
            "merge_prediction",
        ],
        "threshold_selection_logs": [
            "threshold_name",
            "threshold_value",
            "selection_split",
            "selection_metric",
            "selection_rule",
            "applied_scope",
            "score_field",
        ],
    }
    for artifact_id, markers in claim_support_markers_by_artifact.items():
        artifact_row = artifact_rows_by_id.get(artifact_id)
        if not isinstance(artifact_row, dict):
            continue
        claim_support = str(artifact_row.get("claim_support", ""))
        for marker in markers:
            if marker not in claim_support:
                errors.append(
                    "artifact release manifest template "
                    f"{artifact_id} claim_support missing marker: {marker}"
                )

    validation_commands = template.get("minimum_validation_commands")
    if not isinstance(validation_commands, list):
        errors.append("artifact release manifest template missing minimum_validation_commands list")
    else:
        validation_text = "\n".join(str(command) for command in validation_commands)
        for command in [
            "sha256sum -c checksums.sha256",
            "python manuscript/scripts/validate_artifact_release.py --artifact-dir",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir",
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
            "cluster_artifacts_required_for_cluster_level_quality_claims",
        ]:
            if claim_boundaries.get(field) is not True:
                errors.append(f"artifact release claim boundary must be true: {field}")
        for field in [
            "confidence_intervals_claimed",
            "component_causality_claimed",
            "human_validation_claimed",
            "threshold_stability_claimed",
            "broad_method_ranking_claimed",
            "cluster_level_quality_claimed",
        ]:
            if claim_boundaries.get(field) is not False:
                errors.append(f"artifact release claim boundary must default false: {field}")

    conditional_claim_artifacts = template.get("conditional_claim_artifacts")
    expected_conditional_claim_artifacts = {
        "confidence_intervals_claimed": {"bootstrap_intervals"},
        "component_causality_claimed": {"ablation_suite"},
        "human_validation_claimed": {"manual_validation_slice"},
        "threshold_stability_claimed": {"threshold_sensitivity_grid"},
        "cluster_level_quality_claimed": {"cluster_metric_summary", "cannot_link_audit"},
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
        "python manuscript/scripts/populate_artifact_release.py --artifact-dir",
        "python manuscript/scripts/finalize_artifact_release.py --artifact-dir",
        "python manuscript/scripts/validate_manuscript.py --strict-latex",
        "python manuscript/scripts/verify_fixture_rebuild.py",
        "python scripts/check_public_release.py",
        "Required Artifact IDs",
        "open_v2_main_results",
        "per-row denominator counts",
        "per-row threshold source",
        "scope label used in the main table",
        "automatic merge count",
        "block count",
        "defer count",
        "automatic merge coverage",
        "defer rate",
        "iad_risk_predictions",
        "relation-head scores",
        "work_threshold",
        "agenda_block_threshold",
        "risk_threshold",
        "merge_prediction",
        "representation_baseline_scores",
        "normalized score",
        "score_field",
        "threshold_value",
        "supervised_baseline_predictions",
        "match_probability",
        "threshold_selection_logs",
        "threshold_name",
        "selection_split",
        "selection_metric",
        "selection_rule",
        "applied_scope",
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
        "cluster_level_quality_claimed",
        "cluster_metric_summary",
        "cannot_link_audit",
        "broad_method_ranking_claimed",
        "Claim Boundaries",
        "silver labels are not human gold",
        "full numerical audit requires external artifacts",
        "broad method ranking is not claimed unless conditional artifacts are complete",
        "cluster-level quality is not claimed unless cluster artifacts are complete",
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


def check_manuscript_package_docs(readme_text: str, manifest_text: str) -> list[str]:
    """Check whether manuscript package docs describe release-critical artifacts.

    参数:
        readme_text: Manuscript directory README Markdown text.
        manifest_text: Manuscript MANIFEST Markdown text.

    返回:
        list[str]: Error messages for missing package documentation markers.
    """
    required_markers = [
        "open_v2_main_results",
        "per-row denominator counts",
        "per-row threshold source",
        "scope label used in the main table",
        "automatic merge count",
        "block count",
        "defer count",
        "automatic merge coverage",
        "defer rate",
        "iad_risk_predictions",
        "representation_baseline_scores",
        "supervised_baseline_predictions",
        "threshold_selection_logs",
        "pair_id",
        "source_document_id",
        "target_document_id",
        "label strength",
        "hard-negative level",
        "split identifiers",
        "score_field",
        "threshold_value",
        "merge_prediction",
        "final_upload_information_request.md",
        "Author list",
        "Corresponding author",
        "Funding statement",
        "Generative AI declaration",
        "Artifact release URL or DOI",
    ]
    errors: list[str] = []
    for document_name, document_text in {
        "manuscript README": readme_text,
        "manuscript MANIFEST": manifest_text,
    }.items():
        for marker in required_markers:
            if marker not in document_text:
                errors.append(f"{document_name} missing package artifact schema marker: {marker}")
    return errors


def check_data_processing_pipeline_document(document_text: str) -> list[str]:
    """Check whether the repository documents data processing without committing raw data.

    参数:
        document_text: Data processing pipeline Markdown text.

    返回:
        list[str]: Error messages for missing reproducible data-processing markers.
    """
    required_markers = [
        "# 数据处理流水线",
        "远程仓库不提交原始数据",
        "python -m iad_sieve.cli --help",
        "tests/fixtures/",
        "outputs/repro_fixture",
        "data/raw/",
        "prepare-deepmatcher",
        "prepare-scirepeval-proximity",
        "fetch-openalex-works",
        "prepare-openalex-weak-labels",
        "build-iad-bench",
        "Artifact release",
        "manifest",
        "checksum",
    ]
    lowered_text = document_text.lower()
    return [
        f"data processing pipeline document missing marker: {marker}"
        for marker in required_markers
        if marker.lower() not in lowered_text
    ]


def check_artifact_release_skeleton_builder(script_text: str) -> list[str]:
    """Check whether the artifact release scaffold builder keeps required safeguards.

    参数:
        script_text: Artifact release scaffold builder source text.

    返回:
        list[str]: Error messages for missing scaffold generation safeguards.
    """
    required_markers = [
        "import argparse",
        "import logging",
        'SKELETON_RELEASE_STATUS = "skeleton_pending_artifacts"',
        'ARTIFACT_SHA256_PLACEHOLDER = "fill-after-artifact-export"',
        "artifact_release_manifest.template.json",
        "artifact_release_README.template.md",
        "checksums.sha256",
        "REQUIRED_DIRECTORIES",
        "def build_artifact_release_skeleton(",
        "def write_checksums(",
        "def parse_arguments(",
        "--repository-commit",
        "--force",
    ]
    return [
        f"artifact release skeleton builder missing marker: {marker}"
        for marker in required_markers
        if marker not in script_text
    ]


def check_artifact_release_finalizer(script_text: str) -> list[str]:
    """Check whether the artifact release finalizer keeps required safeguards.

    参数:
        script_text: Artifact release finalizer source text.

    返回:
        list[str]: Error messages for missing finalization safeguards.
    """
    required_markers = [
        "import argparse",
        "import logging",
        'DEFAULT_RELEASE_STATUS = "release_candidate"',
        "checksums.sha256",
        "def finalize_artifact_release(",
        "def update_artifact_checksums(",
        "def write_checksums(",
        "def run_artifact_validator(",
        "--artifact-dir",
        "--release-status",
        "--skip-validate",
        "missing required artifact files",
    ]
    return [
        f"artifact release finalizer missing marker: {marker}"
        for marker in required_markers
        if marker not in script_text
    ]


def check_artifact_release_populator(script_text: str) -> list[str]:
    """Check whether the artifact release populator keeps required safeguards.

    参数:
        script_text: Artifact release populator source text.

    返回:
        list[str]: Error messages for missing population safeguards.
    """
    required_markers = [
        "import argparse",
        "import logging",
        'POPULATION_LOG_PATH = "logs/artifact_population_log.jsonl"',
        "def populate_artifact_release(",
        "def build_copy_plan(",
        "def copy_planned_artifacts(",
        "def write_population_log(",
        "def finalize_release(",
        "--source-dir",
        "--mapping",
        "--skip-finalize",
        "missing required source artifact files",
    ]
    return [
        f"artifact release populator missing marker: {marker}"
        for marker in required_markers
        if marker not in script_text
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
        "target_journal_template_bound",
        "Artifact release manifest",
        "funding statement",
        "author contribution statement",
        "permissions statement",
        "third-party material permission",
        "generative AI declaration",
        "AI tool use status",
        "author review and responsibility",
        "AI authorship exclusion",
        "machine-generated figures, images, or artwork",
        "Artifact Release Package Checks",
        "python manuscript/scripts/build_artifact_release_skeleton.py --output-dir /path/to/release --repository-commit",
        "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir",
        "python manuscript/scripts/finalize_artifact_release.py --artifact-dir",
        "python manuscript/scripts/validate_artifact_release.py --artifact-dir",
        "open_v2_main_results",
        "per-row denominator counts",
        "per-row threshold source",
        "scope label used in the main table",
        "automatic merge count",
        "block count",
        "defer count",
        "automatic merge coverage",
        "defer rate",
        "iad_risk_predictions",
        "representation_baseline_scores",
        "supervised_baseline_predictions",
        "threshold_selection_logs",
        "pair_id",
        "source_document_id",
        "target_document_id",
        "label strength",
        "hard-negative level",
        "split identifiers",
        "score or probability fields",
        "threshold_value",
        "threshold source",
        "merge_prediction",
        "threshold_name",
        "selection_split",
        "selection_metric",
        "selection_rule",
        "applied_scope",
        "score_field",
        "DKE/Elsevier Preflight Package Checks",
        "python manuscript/scripts/build_submission_package.py --dke-preflight",
        "python manuscript/scripts/validate_submission_package.py --dke-preflight",
        "build/iad-risk-dke-preflight-package.zip",
        "iad-risk-manuscript-elsevier.tex",
        "iad-risk-manuscript-elsevier.pdf",
        "does not complete the final-upload gate",
        "Publisher Declaration Checks",
        "The declaration text matches submission_metadata.yml",
        "No declaration placeholder remains before final upload",
        "funding role is stated when funding exists",
        "Permission files are listed when third-party permission is required",
        "data availability statement matches artifact release status",
        "generative AI declaration records AI tool use status",
        "Cover Letter Customization Checks",
        "cover letter names the selected target journal",
        "cover letter states the final article type",
        "corresponding author name appears in the cover letter",
        "artifact URL or DOI appears in the cover letter when available",
        "cover letter no longer uses the generic Dear Editor greeting",
        "cover letter no longer uses an anonymous author signature",
        "Source Archive Assembly Checks",
        "source archive contains editable LaTeX sources",
        "source archive includes references.bib and submission text files",
        "source archive includes manifest and checksum files",
        "source archive excludes build caches and generated zip files",
        "source archive is rebuilt after template conversion",
        "Source-Control Binding Checks",
        "tracked source `submission_metadata.yml` can keep `repository_reference` blank",
        "python manuscript/scripts/build_submission_package.py --final-upload",
        "writes `repository_url`, `repository_commit`, and `repository_branch`",
        "package copy of `submission_metadata.yml`",
        "git remote origin",
        "git rev-parse HEAD",
        "submission_manifest.json` records the same `repository_commit`",
        "python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release",
        "external artifact release is finalized",
        "Live Submission Text Checks",
        "Title, abstract, keywords, and highlights are copied from the current source files",
        "title and abstract match `main.tex`",
        "Keywords match `keywords.md` exactly",
        "Highlights match `highlights.md` exactly",
        "live submission system preview shows the same title, abstract, keywords, and highlights",
        "Mark `submission_system_files_verified` true only after these text fields and upload files are checked",
        "First-Screen Claim Lockdown Checks",
        "`cover_letter.md`, `highlights.md`, `keywords.md`, the abstract, and the conclusion",
        "same problem, method, Open-v2 evidence snapshot, and claim boundary",
        "keeps the Open-v2 numbers scope-bounded",
        "preserves the distinction between full pair scope and held-out test scope",
        "No first-screen material claims broad method superiority",
        "SOTA ranking",
        "statistical superiority",
        "threshold stability",
        "human-gold validation",
        "Q2/B completion",
        "final-upload readiness",
        "cluster-level deployment quality",
        "Artifact URL or DOI insertion does not upgrade the scientific claim",
        "bootstrap intervals, threshold grids, ablations, manual-validation slice, or cluster artifacts",
        "rerun `python manuscript/scripts/validate_manuscript.py --strict-latex`",
        "rebuild the submission package before upload",
        "selected journal template matches the final manuscript source",
        "No `data/`, `outputs/`, cache, local connection, credential, or raw third-party file",
        "author email addresses, ORCID values, personal account URLs, local absolute paths, or development process notes",
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
        "Audit Iteration Summary",
        "Completed audit cycles: 30",
        "Highest current reviewer-facing risks",
        "final-upload metadata",
        "target-journal template binding",
        "DKE author biography and photograph materials",
        "external artifact release",
        "artifact release validation bypass",
        "final-upload artifact-dir omission bypass",
        "manuscript artifact-validation text drift",
        "artifact release README completeness",
        "artifact release commit validity",
        "artifact README/manifest commit mismatch",
        "final package/artifact commit mismatch",
        "final-upload artifact-dir instruction drift",
        "prediction artifact schema drift",
        "generative AI declaration consistency",
        "fixture/live evidence confusion",
        "live submission-system text consistency",
        "Git-only fixture reproducibility",
        "source-to-PDF package consistency",
        "final-upload source-control package binding",
        "stronger evidence gates",
        "Current stopping rule",
        "do not claim Q2/B completion or final-upload readiness",
        "real artifact URL or DOI",
        "Non-code external inputs still required",
        "author metadata",
        "DKE author biography and photograph materials",
        "target-journal confirmation",
        "funding statement",
        "author contribution statement",
        "permissions statement",
        "generative AI declaration",
        "live submission-system fields",
        "Next revision trigger",
        "repeat the editorial desk check after target-journal template binding",
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
        "Audit Cycle 6: Reviewer Rebuttal Boundary",
        "Audit Cycle 7: Journal Fit and Novelty Desk Check",
        "Audit Cycle 8: Pair-to-Cluster Claim Lockdown",
        "Audit Cycle 9: Artifact Row-Level Result Audit",
        "Audit Cycle 10: Final Template Binding and System Metadata Gate",
        "Audit Cycle 11: Live Submission Text Consistency Gate",
        "Audit Cycle 12: Git-Only Fixture Reproducibility Gate",
        "Audit Cycle 13: Submission Package Source-PDF Consistency Gate",
        "Audit Cycle 14: Source-Control Manifest Binding Gate",
        "Audit Cycle 15: Artifact Release Commit Validity Gate",
        "Audit Cycle 16: Artifact Release README Reproducibility Gate",
        "Audit Cycle 17: Final-Upload Source-Control Package Binding Gate",
        "Audit Cycle 18: Prediction Artifact Schema Gate",
        "Audit Cycle 19: Generative AI Declaration Gate",
        "Audit Cycle 20: Fixture Evidence Isolation Gate",
        "Audit Cycle 21: DKE Author Biography and Photograph Gate",
        "Audit Cycle 22: Method Execution Traceability Gate",
        "Audit Cycle 23: First-Screen Claim Lockdown Gate",
        "Audit Cycle 24: Final-Upload Claim-Lock Metadata Gate",
        "Audit Cycle 25: Artifact README-Manifest Commit Consistency Gate",
        "Audit Cycle 26: Final Package-Artifact Commit Binding Gate",
        "Audit Cycle 27: Final-Upload Artifact-Dir Instruction Consistency Gate",
        "Audit Cycle 28: Final-Upload Artifact Release Validation Gate",
        "Audit Cycle 29: Final-Upload Artifact-Dir Required Gate",
        "Audit Cycle 30: Main-Manuscript Artifact Validation Text Gate",
        "method-writing clarity",
        "training and inference trace",
        "schema loading",
        "masked supervision",
        "threshold fixation",
        "pair scoring",
        "decision emission",
        "metric export",
        "relation-head predictions",
        "final-upload checklist coverage",
        "first-screen upgrades",
        "SOTA ranking",
        "statistical superiority",
        "human-gold validation",
        "Q2/B completion",
        "first_screen_claim_lockdown_confirmed",
        "metadata-validator coverage",
        "live system preview",
        "README.md",
        "Repository commit",
        "manifest.json",
        "repository.commit",
        "commit-consistency coverage",
        "same source revision",
        "submission-package validator coverage",
        "validate_submission_package.py --final-upload --artifact-dir",
        "artifact manifest",
        "submission_metadata.yml",
        "repository_commit",
        "final-upload instruction coverage",
        "final_upload_information_request.md",
        "submission_system_checklist.md",
        "older command without `--artifact-dir`",
        "integrated artifact-release validation coverage",
        "required artifact IDs",
        "Open-v2 row-level audit columns",
        "prediction JSONL fields",
        "claim-dependent artifact requirements",
        "missing artifact-directory rejection",
        "finalized artifact release directory",
        "omit `--artifact-dir`",
        "local checksum, manifest, row-schema, prediction-schema, and package-artifact commit checks",
        "cannot bypass the external release directory",
        "manuscript-level reproducibility wording",
        "Data and Code Availability section",
        "validate_artifact_release.py --artifact-dir /path/to/release",
        "validate_submission_package.py --final-upload --artifact-dir /path/to/release",
        "source-control commit",
        "main text tells reviewers",
        "should not be used to support the Open-v2 numerical table",
        "remote reproducibility",
        "strong model matrix",
        "model superiority",
        "innovation depth",
        "novelty and prior-art positioning",
        "claim lockdown",
        "desk-rejection risk",
        "target-journal scope fit",
        "novelty beyond ordinary entity matching",
        "Data & Knowledge Engineering",
        "Information Systems",
        "Scientometrics",
        "pair-level metrics",
        "cluster-level deployment quality",
        "cluster artifacts",
        "cluster_metric_summary",
        "cannot_link_audit",
        "cover letter, highlights, and conclusion",
        "artifact-backed audits",
        "open_v2_main_results",
        "per-row denominator counts",
        "per-row threshold source",
        "scope label used in the main table",
        "automatic merge count",
        "block count",
        "defer count",
        "automatic merge coverage",
        "defer rate",
        "validate_artifact_release.py",
        "target_journal_template_bound",
        "target_journal_template_applied",
        "source archive rebuilt after template conversion",
        "selected journal template matches the final manuscript source",
        "DKE/Elsevier preflight package",
        "submission_system_files_verified",
        "title, abstract, keywords, and highlights",
        "`main.tex`",
        "`keywords.md`",
        "`highlights.md`",
        "live submission system preview",
        "python manuscript/scripts/verify_fixture_rebuild.py",
        "python scripts/check_public_release.py",
        "no-network code-path evidence",
        "data adapters, CLI entry points, schema contracts, and IAD-Bench assembly path",
        "does not prove the Open-v2 numerical table",
        "packaged PDFs",
        "source dependencies",
        "main PDF",
        "supplementary PDF",
        "DKE/Elsevier preflight PDF",
        "rebuild PDF before packaging",
        "source_control",
        "repository_commit",
        "repository_branch",
        "worktree_dirty",
        "tracked_state",
        "matches `submission_metadata.yml`",
        "final package is rebuilt from the submitted repository commit",
        "7 to 40 character hexadecimal Git commit",
        "repository.commit",
        "artifact release skeleton builder and validator",
        "same committed source revision as the final manuscript package",
        "README.md",
        "manifest.json",
        "checksums.sha256",
        "raw third-party data exclusions",
        "data policy",
        "reproduction levels",
        "claim boundaries",
        "tracked `submission_metadata.yml`",
        "cannot reliably contain the Git commit of the commit that contains itself",
        "writes `repository_url`, `repository_commit`, `repository_branch`",
        "matching data/code availability statement",
        "final package metadata and `submission_manifest.json` agree",
        "row-level prediction schema enforced by `validate_artifact_release.py`",
        "iad_risk_predictions",
        "representation_baseline_scores",
        "supervised_baseline_predictions",
        "threshold_selection_logs",
        "pair_id",
        "source_document_id",
        "target_document_id",
        "label strength",
        "hard-negative level",
        "split identifiers",
        "score or probability fields",
        "threshold_value",
        "threshold source",
        "merge_prediction",
        "threshold_name",
        "selection_split",
        "selection_metric",
        "selection_rule",
        "applied_scope",
        "score_field",
        "recompute row-level decisions, denominators, and fixed operating points",
        "publisher-required AI-tool disclosure",
        "removable process notes",
        "AI-tool use status",
        "author review and responsibility",
        "AI tools are not listed as authors",
        "machine-generated figures, images, or artwork",
        "generative_ai_declaration_complete",
        "test fixtures from being mistaken for current manuscript evidence",
        "Unit-test fixtures",
        "generated fixture reports",
        "validator coverage only",
        "live outputs regenerated from the current repository commit",
        "current live artifacts",
        "current commit metadata",
        "data/",
        "outputs/",
        "anonymous package hygiene",
        "title, abstract, conclusion, cover letter, highlights, and keywords",
        "editorial claim alignment",
        "ready_to_answer",
        "limited_answer",
        "do_not_answer_as_claim",
        "safe response scope",
        "must-not-claim boundary",
        "Revision Trigger Register",
        "reviewer concern triggers a concrete manuscript revision",
        "Contribution trigger",
        "Writing clarity trigger",
        "Experimental strength trigger",
        "Evaluation completeness trigger",
        "Method design soundness trigger",
        "weaken the claim",
        "add artifact-backed evidence",
        "do not upgrade the abstract, introduction, conclusion, cover letter, or highlights",
        "author email addresses, ORCID values, personal account URLs, local absolute paths, and development process notes",
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
        "python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release",
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
        "not a replacement for end-to-end entity resolution workflows",
        "not a comparative ranking over all neural matching methods",
        "does not claim that OpenAlex/OpenCitations silver evidence is human gold",
        "merge-safety framing",
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
    required_limitation_markers = [
        "This study has five limitations",
        "pair-level metrics do not by themselves establish cluster-level deployment quality",
        "cluster assignments",
        "cannot-link coverage",
        "cluster contamination rate",
    ]
    errors = [f"validity threats missing marker: {marker}" for marker in required_markers if marker not in manuscript_text]
    errors.extend(
        f"Limitations missing cluster-level boundary marker: {marker}"
        for marker in required_limitation_markers
        if marker not in manuscript_text
    )
    return errors


def check_claim_interpretation_boundary(manuscript_text: str) -> list[str]:
    """Check whether the main manuscript contains a formal claim-interpretation boundary.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing claim-interpretation boundary markers.
    """
    required_markers = [
        r"\section{Claim Interpretation Boundary}",
        r"\label{tab:claim-interpretation-boundary}",
        "Claim interpretation boundary",
        "Contribution clarity",
        "Writing reproducibility",
        "Experimental strength",
        "Evaluation completeness",
        "Method design soundness",
        "Main evidence location",
        "Supported wording",
        "Boundary before stronger wording",
        "identity-agenda confusion",
        "IAD-Bench contract",
        "Open-v2 evidence snapshot",
        "artifact-backed ablations",
        "manual-validation slice",
        "source-heldout validation",
    ]
    forbidden_markers = [
        "Reviewer-Facing Claim Checklist",
        "reviewer-facing-claim-checklist",
        "Reviewer-facing claim checklist",
    ]
    errors = [
        f"claim interpretation boundary missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]
    errors.extend(
        f"claim interpretation boundary uses internal-review marker: {marker}"
        for marker in forbidden_markers
        if marker in manuscript_text
    )
    return errors


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
    required_markers = [
        "Cluster-level claims require artifact-backed audits",
    ]
    for marker in required_markers:
        if marker not in highlights_text:
            errors.append(f"highlights missing cluster-level claims boundary marker: {marker}")
    for line in bullet_lines:
        highlight = line[2:]
        word_count = len(highlight.split())
        if word_count > 22:
            errors.append(f"highlight is too long ({word_count} words): {line}")
        character_count = len(highlight)
        if character_count > 85:
            errors.append(f"highlight exceeds 85 characters ({character_count} characters): {line}")
        if "HNFMR" in highlight and re.search(r"\d", highlight):
            if "Open-v2" not in highlight or "scope" not in highlight.lower():
                errors.append(
                    "HNFMR highlight must mention Open-v2 and scope boundary when reporting numbers: "
                    f"{line}"
                )
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
    required_keywords = ["hard-negative false-merge rate"]
    for required_keyword in required_keywords:
        if required_keyword not in keywords:
            errors.append(f"keywords missing required term: {required_keyword}")
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
        "full experimental outputs are not redistributed in Git",
        "artifact-release instructions",
        "manifests and checksums",
        "does not claim cluster-level deployment quality without cluster artifacts",
    ]
    errors = [f"cover letter missing required statement: {marker}" for marker in required_markers if marker not in cover_letter_text]
    subjective_fit_markers = [
        "We believe",
        "we believe",
        "I believe",
    ]
    errors.extend(
        f"cover letter contains subjective fit language: {marker}"
        for marker in subjective_fit_markers
        if marker in cover_letter_text
    )
    return errors


def check_submission_material_quantitative_summary(highlights_text: str, cover_letter_text: str) -> list[str]:
    """Check whether submission materials match the manuscript evidence scope.

    参数:
        highlights_text: Highlights Markdown text.
        cover_letter_text: Cover letter Markdown text.

    返回:
        list[str]: Error messages for missing quantitative submission markers.
    """
    highlight_required_markers = [
        "Open-v2 scope-bounded evidence",
        "IAD-Risk HNFMR=0.000",
    ]
    errors: list[str] = []
    for marker in highlight_required_markers:
        if marker not in highlights_text:
            errors.append(f"highlights missing scoped quantitative evidence marker: {marker}")
    cover_letter_quantitative_markers = [
        "HNFMR 0.790--0.999",
        "HNFMR=0.000",
    ]
    for marker in cover_letter_quantitative_markers:
        if marker not in cover_letter_text:
            errors.append(f"cover letter missing quantitative evidence marker: {marker}")
    cover_letter_scope_markers = [
        "Open-v2 evidence snapshot",
        "scope-bounded mechanism evidence",
        "same-scope comparative ranking",
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
                "scope-bounded mechanism evidence",
                "same-scope comparative ranking",
                "HNFMR 0.790--0.999",
                "HNFMR=0.000",
                "pair-level conclusion",
                "cluster artifacts",
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
                "does not claim cluster-level deployment quality without cluster artifacts",
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
                "Open-v2 scope-bounded evidence",
                "IAD-Risk HNFMR=0.000",
                "artifact-backed audits",
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
        "dke_official_guide_rechecked: \"2026-06-19\"",
        "ranking_confirmation_required_before_final_upload: true",
        "selected_target_requires_author_confirmation: true",
        "dke_preflight:",
        "review_model: \"single_anonymized\"",
        "abstract_word_limit_checked: true",
        "keyword_count_checked: true",
        "highlight_count_and_length_checked: true",
        "elsarticle_conversion_pending_author_confirmation: true",
        "author_biography_and_photo_required_before_upload: true",
        "artifact_release_required_before_upload: true",
        "corresponding_author:",
        "competing_interests:",
        "data_code_availability:",
        "research_data_statement:",
        "author_contributions:",
        "credit_taxonomy_required_before_final_upload: true",
        "contribution_statement:",
        "permissions:",
        "no_third_party_material_requiring_permission_declared: false",
        "third_party_material_requires_permission: false",
        "permissions_statement:",
        "generative_ai:",
        "declaration_required_before_final_upload: true",
        "ai_tools_used_in_manuscript_preparation:",
        "declaration_statement:",
        "author_review_and_responsibility_confirmed: false",
        "ai_not_listed_as_author_confirmed: false",
        "ai_generated_images_or_artwork_included: false",
        "repository_reference:",
        "repository_url: \"\"",
        "repository_commit: \"\"",
        "repository_branch: \"main\"",
        "repository_commit_required_before_final_upload: true",
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
        "author_biographies_and_photos_ready: false",
        "corresponding_author_completed: false",
        "generative_ai_declaration_complete: false",
        "manuscript_pdf_rebuilt_after_template: false",
        "supplementary_pdf_rebuilt_after_template: false",
        "submission_system_files_verified: false",
        "first_screen_claim_lockdown_confirmed: false",
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
    return check_structured_final_upload_metadata_text(metadata_text)


def check_final_upload_cover_letter(cover_letter_text: str, metadata_text: str) -> list[str]:
    """Check cover letter fields that must be resolved before final journal upload.

    参数:
        cover_letter_text: Cover letter Markdown text.
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for unresolved final-upload cover letter fields.
    """
    return check_structured_final_upload_cover_letter_text(cover_letter_text, metadata_text)


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


def normalize_pdf_marker_text(text: str) -> str:
    """Normalize extracted PDF text for stable marker matching.

    参数:
        text: Extracted PDF text or expected marker text.

    返回:
        str: Text with line-break hyphenation and whitespace normalized.
    """
    text_without_hyphen_linebreaks = re.sub(r"-\s*\n\s*", "-", text)
    return re.sub(r"\s+", " ", text_without_hyphen_linebreaks).strip()


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
    normalized_first_page_text = normalize_pdf_marker_text(first_page_text)
    for required_text in required_texts:
        if normalize_pdf_marker_text(required_text) not in normalized_first_page_text:
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
    normalized_full_text = normalize_pdf_marker_text(full_text)
    for required_text in required_texts:
        if normalize_pdf_marker_text(required_text) not in normalized_full_text:
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
    """Check whether the generated PDF is newer than a source dependency.

    参数:
        pdf_path: Generated PDF path.
        source_path: Source dependency path.

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
    final_upload_information_request_path = ROOT / "final_upload_information_request.md"
    final_upload_information_request_text = (
        final_upload_information_request_path.read_text(encoding="utf-8")
        if final_upload_information_request_path.exists()
        else ""
    )
    data_processing_pipeline_path = PROJECT_ROOT / "docs" / "data-processing-pipeline.md"
    data_processing_pipeline_text = (
        data_processing_pipeline_path.read_text(encoding="utf-8") if data_processing_pipeline_path.exists() else ""
    )
    artifact_release_skeleton_builder_path = ROOT / "scripts" / "build_artifact_release_skeleton.py"
    artifact_release_skeleton_builder_text = (
        artifact_release_skeleton_builder_path.read_text(encoding="utf-8")
        if artifact_release_skeleton_builder_path.exists()
        else ""
    )
    artifact_release_populator_path = ROOT / "scripts" / "populate_artifact_release.py"
    artifact_release_populator_text = (
        artifact_release_populator_path.read_text(encoding="utf-8") if artifact_release_populator_path.exists() else ""
    )
    artifact_release_finalizer_path = ROOT / "scripts" / "finalize_artifact_release.py"
    artifact_release_finalizer_text = (
        artifact_release_finalizer_path.read_text(encoding="utf-8") if artifact_release_finalizer_path.exists() else ""
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
    errors.extend(check_formal_manuscript_review_language(manuscript_text, "main manuscript"))
    errors.extend(check_formal_manuscript_review_language(supplementary_text, "supplementary material"))
    errors.extend(check_abstract_quantitative_evidence(manuscript_text))
    errors.extend(check_abstract_length(manuscript_text))
    errors.extend(check_abstract_cluster_overclaim(manuscript_text))
    errors.extend(check_contribution_evidence_summary(manuscript_text))
    errors.extend(check_motivating_failure_case(manuscript_text))
    errors.extend(check_openv2_benchmark_composition(manuscript_text))
    errors.extend(check_iad_bench_document_schema_contract(manuscript_text))
    errors.extend(check_iad_bench_pair_schema_contract(manuscript_text))
    errors.extend(check_method_feature_contract(manuscript_text))
    errors.extend(check_training_objective_masking(manuscript_text))
    errors.extend(check_risk_score_design_rationale(manuscript_text))
    errors.extend(check_risk_calibration_overclaims(manuscript_text))
    errors.extend(check_method_cluster_overclaims(manuscript_text))
    errors.extend(check_operational_net_benefit_boundary(manuscript_text))
    errors.extend(check_version_identifier_policy(manuscript_text))
    errors.extend(check_method_pipeline_figure(manuscript_text))
    errors.extend(check_scoring_merge_algorithm(manuscript_text))
    errors.extend(check_design_alternative_boundaries(manuscript_text))
    errors.extend(check_related_work_positioning(manuscript_text))
    errors.extend(check_error_taxonomy(manuscript_text))
    errors.extend(check_validity_threats(manuscript_text))
    errors.extend(check_claim_interpretation_boundary(manuscript_text))
    errors.extend(check_declaration_statements(manuscript_text))
    errors.extend(check_data_code_availability_boundary(manuscript_text))
    errors.extend(check_operating_point_disclosure(manuscript_text))
    errors.extend(check_selective_decision_coverage_boundary(manuscript_text))
    errors.extend(check_pair_cluster_evidence_boundary(manuscript_text))
    errors.extend(check_decision_metric_mapping(manuscript_text))
    errors.extend(check_metric_formula_boundary(manuscript_text))
    errors.extend(check_statistical_interpretation_boundary(manuscript_text))
    errors.extend(check_threshold_sensitivity_status(manuscript_text))
    errors.extend(check_baseline_scope_alignment(manuscript_text))
    errors.extend(check_baseline_inclusion_rationale(manuscript_text))
    errors.extend(check_baseline_fairness_controls(manuscript_text))
    errors.extend(check_result_interpretation_guardrails(manuscript_text))
    errors.extend(check_openv2_result_table_scope_labels(manuscript_text))
    errors.extend(check_manual_validation_boundary(manuscript_text))
    errors.extend(check_split_leakage_controls(manuscript_text))
    errors.extend(check_scope_compatibility(manuscript_text))
    errors.extend(check_extended_protocol_boundary(manuscript_text))
    errors.extend(check_environment_setup(supplementary_text))
    errors.extend(check_target_journal_shortlist(target_journal_shortlist_text))
    errors.extend(check_artifact_release_manifest_template(artifact_release_template_text))
    errors.extend(check_artifact_release_readme_template(artifact_release_readme_template_text))
    errors.extend(check_final_upload_information_request(final_upload_information_request_text))
    readme_path = ROOT / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
    manifest_path = ROOT / "MANIFEST.md"
    manifest_text = manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else ""
    errors.extend(check_manuscript_package_docs(readme_text, manifest_text))
    errors.extend(check_data_processing_pipeline_document(data_processing_pipeline_text))
    errors.extend(check_artifact_release_skeleton_builder(artifact_release_skeleton_builder_text))
    errors.extend(check_artifact_release_populator(artifact_release_populator_text))
    errors.extend(check_artifact_release_finalizer(artifact_release_finalizer_text))
    errors.extend(check_submission_system_checklist(submission_system_checklist_text))
    errors.extend(check_reviewer_readiness_audit(reviewer_readiness_audit_text))
    errors.extend(check_manual_validation_protocol(supplementary_text))
    errors.extend(check_reviewer_evidence_gate(supplementary_text))
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
        errors.extend(check_final_upload_cover_letter(cover_letter_text, submission_metadata_text))
    errors.extend(check_bibliography_depth(bibliography_text))
    errors.extend(check_bibliography_entry_metadata(bibliography_text))
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
    errors.extend(check_pdf_freshness(latex_pdf_path, bibliography_path))
    errors.extend(check_pdf(elsevier_pdf_path, main_pdf_markers + ["Keywords:", "Data & Knowledge Engineering"]))
    errors.extend(check_pdf_full_text_markers(elsevier_pdf_path, main_full_text_markers))
    errors.extend(check_pdf_freshness(elsevier_pdf_path, manuscript_path))
    errors.extend(check_pdf_freshness(elsevier_pdf_path, keywords_path))
    errors.extend(check_pdf_freshness(elsevier_pdf_path, bibliography_path))
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
