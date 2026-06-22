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
    parse_mapping_section,
    scalar_value,
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
    r"\section{Closest-Work Positioning}",
    r"\section{Reproduction Levels}",
    r"\section{IAD-Bench Schema Contracts}",
    r"\section{Method Design Boundaries}",
    r"\section{Environment Setup}",
    r"\section{No-Network Fixture Rebuild}",
    r"\section{Public-Source Rebuild}",
    r"\section{Public-Source Rebuild Audit Boundary}",
    r"\section{Artifact Package Requirements}",
    r"\section{Baseline Audit Boundary}",
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
            "original sources have their own access conditions and licenses",
            "data-processing commands",
            "schema contracts",
            "fixture tests",
            "artifact-release",
            "manifests",
            "checksums",
            "commit identifiers",
            "source_input_manifest",
            "license boundary",
            "derived tables, predictions, logs, manifests, and checksums rather than raw provider files",
        ],
        r"\section*{Ethics Statement}": [
            "public scholarly metadata",
            "does not involve human participants",
            "clinical records",
            "private user behavior",
            "sensitive personal information",
        ],
        r"\section*{Competing Interests}": [
            "not finalized in this anonymous preflight manuscript",
            "listed authors must confirm",
            "competing-interest status",
            r"\path{submission_metadata.yml}",
            "live submission system",
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
        "institutional ranking/category source",
        "`authors`, `author_contributions.roles`, `final_upload_checklist.author_metadata_completed`",
        "`author_identity_materials`, `final_upload_checklist.author_biographies_and_photos_ready`",
        "`corresponding_author`, `final_upload_checklist.corresponding_author_completed`",
        "`funding`, `statements`, `final_upload_checklist.funding_statement_text_ready`",
        "`author_contributions`, `final_upload_checklist.contribution_statement_complete`",
        "`permissions`, `final_upload_checklist.permissions_statement_complete`",
        "`generative_ai`, `final_upload_checklist.generative_ai_declaration_complete`",
        "`repository_reference`, `artifact_boundary`, `statements.research_data_statement`",
        "`artifact_boundary`, `final_upload_checklist.artifact_release_prepared_or_linked`",
        "`final_upload_checklist.manuscript_pdf_rebuilt_after_template`",
        "`upload_preparation.live_submission_system_verified`",
        "`upload_preparation.final_upload_package_verified_against_system`",
        "`final_upload_checklist.first_screen_claim_lockdown_confirmed`",
        "Target journal",
        "All author-guide and ranking/category confirmation dates must use YYYY-MM-DD",
        "must not be later than the actual check date",
        "Source URLs must be public HTTP/HTTPS URLs",
        "must not use placeholder domains",
        "example.org",
        "localhost",
        ".test",
        ".invalid",
        "DKE preflight source status",
        "`dke_official_guide_source`",
        "`dke_official_guide_source_url`",
        "`dke_official_guide_rechecked`",
        "`dke_official_guide_constraints_verified`",
        "preflight preparation only",
        "do not replace the final selected-author-guide fields",
        "DKE official guide source recorded",
        "DKE official guide source URL",
        "DKE official guide rechecked date",
        "DKE official guide constraints verified",
        "Final selected-author-guide fields still require author confirmation",
        "Final target journal decision still requires author confirmation",
        "Final ranking/category confirmation still requires institutional source confirmation",
        "Article type",
        "Article type controlled value for this manuscript",
        "Use `research_article` for the final upload",
        "Do not use `review_article`, `case_report`, or other article-type values",
        "Review mode",
        "Review mode value must be recorded whenever `review_mode_confirmed` is true",
        "Review mode controlled value for single-anonymized author-visible final upload routes",
        "`single_anonymized_with_final_author_identities`",
        "`single_anonymized_author_visible_final_upload`",
        "Do not use `anonymous_review`",
        "generic `single_anonymized` value",
        "Selected author-guide source",
        "Selected author-guide source URL",
        "Selected author-guide rechecked date",
        "Selected template requirements confirmed",
        "Institutional ranking/category source checked",
        "Institutional ranking/category source URL",
        "Ranking/category checked date",
        "Ranking/category confirmation completed",
        "Selected target journal author-confirmed",
        "Author list",
        "Author order",
        "Author biographies and photographs",
        "author_identity_materials",
        "author_biography_and_photo_required_before_upload",
        "biography_files",
        "photograph_files",
        "author_identity_materials_verified",
        "maximum 100 words",
        "editable format",
        "must not be PDF",
        ".doc",
        ".docx",
        "passport-type photograph",
        "Biography file path",
        "Photograph file path",
        "Author identity materials verified",
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
        "Repository URL must be a public non-placeholder HTTP/HTTPS URL",
        "Repository branch must be `main` for the final upload",
        "Artifact release URL or DOI",
        "Artifact release URL must be a public non-placeholder HTTP/HTTPS URL",
        "Artifact manifest `publication.artifact_release_url` matches this URL",
        "Artifact manifest `publication.artifact_release_doi` matches this DOI",
        "Artifact manifest `publication.public_access_status` is public",
        "Source artifact directory path for preflight",
        "Source artifact preflight command passed",
        "Artifact release directory path for final validation",
        "Artifact release manifest",
        "Live submission-system fields",
        "Submission text consistency",
        "Title source checked against `main.tex`",
        "Abstract copied exactly from `main.tex`",
        "Keywords copied exactly from `keywords.md`",
        "Highlights copied exactly from `highlights.md`",
        "First-page title, abstract, keywords, and highlights were previewed in the live submission system",
        "Live submission system verified",
        "Final upload package verified against live system",
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


def check_data_code_availability_boundary(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether the data/code availability statement separates repository and artifact scope.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing data/code availability boundary markers.
    """
    required_main_markers = [
        r"\section*{Data and Code Availability}",
        r"\path{src/iad_sieve}",
        r"\path{pyproject.toml}",
        r"\texttt{iad-sieve = iad\_sieve.cli:main}",
        r"\texttt{python -m iad\_sieve.cli --help}",
        "verifies command discovery",
        "full data and code availability boundary table is reported in the supplementary material",
        "source code and CLI entry points",
        "small public fixtures",
        "schema contracts",
        "data-processing commands",
        "version-controlled in Git",
        "raw third-party source files",
        "full prediction files",
        "model checkpoints",
        "derived evaluation artifacts",
        "remain outside Git",
        "external artifact package",
        "data-processing path",
        r"\path{manuscript/scripts/populate_artifact_release.py}",
        r"\texttt{--artifact-dir}",
        r"\path{/path/to/release}",
        r"\texttt{--source-dir}",
        r"\path{/path/to/source-artifacts}",
        r"\texttt{--preflight-only}",
        "source preflight can detect missing tables, predictions, reports, configurations, or logs early",
        "it is not itself result evidence",
        r"\path{source_input_manifest}",
        r"\path{processing_run_log}",
        "L0/L1 code-level reproduction",
        "L2/L3 result-level audit",
        "raw data or full experiment outputs",
        "original sources have their own access conditions and licenses",
        "derived tables, predictions, logs, manifests, and checksums rather than raw provider files",
        "original provider terms explicitly allow redistribution",
        "license boundary",
        "Full numerical reproduction requires public-source rebuilds or released artifacts",
    ]
    required_supplement_markers = [
        r"\section{Data and Code Availability Boundary}",
        r"\label{tab:data-code-availability-boundary}",
        "Data and code availability boundary",
        "Source code and CLI entry points",
        "Small public fixtures and schema contracts",
        "Raw third-party source files",
        "Full prediction files and model checkpoints",
        "Derived evaluation artifacts",
        "source input manifests",
        "processing run logs",
        "prediction files, threshold logs, manifests, checksums, and commit identifiers",
        "L0/L1 code-level reproduction",
        "L2/L3 result-level audit",
        "raw third-party data remain governed by original provider licenses",
        "released artifacts should not redistribute raw provider files unless source terms explicitly allow redistribution",
        "source terms explicitly permit redistribution",
        "full numerical reproduction requires public-source rebuilds or released artifacts",
    ]
    lowered_text = manuscript_text.lower()
    errors = [
        f"data/code availability boundary missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker.lower() not in lowered_text
    ]
    evidence_text = (supplementary_text or manuscript_text).lower()
    errors.extend(
        f"data/code availability boundary missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker.lower() not in evidence_text
    )
    return errors


def check_reproduction_command_chain(manuscript_text: str) -> list[str]:
    """Check whether the manuscript preserves the executable reproduction command chain.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing command-chain markers.
    """
    required_markers = [
        r"\section*{Data and Code Availability}",
        r"\texttt{python -m iad\_sieve.cli --help}",
        "fixture rebuild validation",
        r"\path{manuscript/scripts/verify_fixture_rebuild.py}",
        "public-release audit",
        r"\path{scripts/check_public_release.py}",
        r"\path{manuscript/scripts/populate_artifact_release.py}",
        r"\texttt{--artifact-dir}",
        r"\path{/path/to/release}",
        r"\texttt{--source-dir}",
        r"\path{/path/to/source-artifacts}",
        r"\texttt{--preflight-only}",
        "it is not itself result evidence",
        r"\path{source_input_manifest}",
        r"\path{processing_run_log}",
        r"\path{manuscript/scripts/validate_artifact_release.py}",
        r"\texttt{--artifact-dir /path/to/release}",
        r"\path{manuscript/scripts/validate_submission_package.py}",
        r"\texttt{--final-upload --artifact-dir /path/to/release}",
        "source-control commit",
        "same source commit",
        "do not reproduce the Open-v2 numerical table",
        "Full numerical reproduction requires public-source rebuilds or released artifacts",
    ]
    return [
        f"reproduction command chain missing manuscript marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_reproduction_levels_boundary(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether reproduction levels are stated without overloading the main text.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing reproduction-level boundary markers.
    """
    required_main_markers = [
        r"\subsection{Artifact Reproduction Protocol}",
        "full reproduction-level table is reported in the supplementary material",
        "L0 code check and L1 fixture rebuild verify executable contracts",
        "do not reproduce the Open-v2 numerical table",
        "L2 public-source rebuild requires independently obtained public raw files",
        r"\path{source_input_manifest}",
        r"\path{processing_run_log}",
        "L3 result audit requires released tables, predictions, logs, manifests, checksums, and commit identifiers",
        "reviewer who has only the Git repository",
        "cannot verify model predictions, threshold choices, or row-level Open-v2 numbers from Git alone",
        "L2/L3 artifact chain",
    ]
    required_supplement_markers = [
        r"\section{Reproduction Levels}",
        r"\label{tab:reproduction-levels}",
        "Reproduction levels for auditing the repository and the reported evidence",
        "L0/L1 levels verify executable code and fixture contracts",
        "L2/L3 levels are required for result-level numerical audit",
        "L0 code check",
        "L1 fixture rebuild",
        "L2 public-source rebuild",
        "L3 result audit",
        "Source tree, package environment, and manuscript scripts",
        r"\texttt{tests/fixtures}",
        r"\path{source_input_manifest}",
        r"\path{processing_run_log}",
        "Released tables, predictions, logs, manifests, checksums, and commit identifiers",
    ]
    errors = [
        f"reproduction-level boundary missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"reproduction-level boundary missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


def check_evaluation_protocol_boundary(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether experimental questions preserve label-stratum boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing evaluation-protocol markers.
    """
    required_main_markers = [
        r"\subsection{Experimental Questions}",
        "full evaluation-protocol table is reported in the supplementary material",
        "RQ1 tests whether IAD-Risk preserves same-work matching performance on gold identity pairs",
        "RQ2 tests whether it reduces false merges on silver hard negatives with HNFMR",
        "RQ3 examines whether the observed behavior is consistent with the proposed risk mechanism through FMR and HNFMR",
        "RQ4 tests whether results remain interpretable under gold, proxy, and silver label strata through split metrics",
        "evidence strength is tied to the label stratum behind each question",
        "gold, proxy, and silver evidence are not mixed into one undifferentiated score",
    ]
    required_supplement_markers = [
        r"\section{Evaluation Protocol Boundary}",
        r"\label{tab:evaluation-protocol}",
        "Evaluation protocol. Each question is tied to a label stratum and a metric",
        "RQ",
        "Evidence layer",
        "Metric",
        "Interpretation",
        "RQ1",
        "Gold identity pairs",
        "Same-work F1",
        "Duplicate matching ability",
        "RQ2",
        "Silver hard negatives",
        "HNFMR",
        "False-merge safety",
        "RQ3",
        "Mechanism analysis",
        "FMR and HNFMR",
        "Role of risk signals",
        "RQ4",
        "Gold/proxy/silver strata",
        "Split metrics",
        "Provenance-aware robustness",
    ]
    errors = [
        f"evaluation protocol boundary missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"evaluation protocol boundary missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


def check_cli_entrypoint_contract(pyproject_text: str, cli_text: str) -> list[str]:
    """Check whether the installable CLI entry point is auditable from source.

    参数:
        pyproject_text: Project pyproject.toml content.
        cli_text: src/iad_sieve/cli.py content.

    返回:
        list[str]: Error messages for missing package or CLI entry-point markers.
    """
    required_markers_by_source = {
        "pyproject.toml": [
            "[project.scripts]",
            'iad-sieve = "iad_sieve.cli:main"',
            "[tool.setuptools.packages.find]",
            'where = ["src"]',
        ],
        "src/iad_sieve/cli.py": [
            "import argparse",
            "def build_parser() -> argparse.ArgumentParser:",
            'prog="python -m iad_sieve.cli"',
            "def main(argv: list[str] | None = None) -> int:",
            "parser.parse_args(argv)",
            "args.func(args)",
        ],
    }
    source_text_by_name = {
        "pyproject.toml": pyproject_text,
        "src/iad_sieve/cli.py": cli_text,
    }
    errors: list[str] = []
    for source_name, required_markers in required_markers_by_source.items():
        source_text = source_text_by_name[source_name]
        for marker in required_markers:
            if marker not in source_text:
                errors.append(f"CLI entrypoint contract missing marker in {source_name}: {marker}")
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
        "zero observed HNFMR",
        "held-out test scope",
        "ordinary FMR still reported separately as 0.001",
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
        "shared Open-v2 pair schema",
        "row-scope differences between full-scope baselines and held-out IAD-Risk rows",
        "same-work F1=0.980",
        "zero observed HNFMR",
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
        "full pair schema table is reported in the supplementary material",
        r"\path{pair_id}",
        r"\path{source_document_id}",
        r"\path{target_document_id}",
        r"\path{relation_label}",
        r"\path{expected_label}",
        r"\path{expected_agenda_label}",
        r"\path{label_source}",
        r"\path{label_strength}",
        r"\path{label_provenance}",
        r"\path{split}",
        r"\path{hard_negative_level}",
        "separates the binary same-work target from agenda relatedness",
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
        "full document schema table is reported in the supplementary material",
        r"\path{document_id}",
        r"\path{source_dataset}",
        r"\path{title}",
        r"\path{abstract}",
        r"\path{authors}",
        r"\path{year}",
        r"\path{venue}",
        r"\path{doi}",
        r"\path{arxiv_id}",
        r"\path{openalex_work_id}",
        r"\path{topics}",
        r"\path{references}",
        "Missing values are represented by empty strings, empty arrays, or null values",
        "without redistributing raw third-party files",
    ]
    return [
        f"IAD-Bench document schema contract missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_iad_bench_supplementary_schema_tables(supplementary_text: str) -> list[str]:
    """Check whether supplementary material preserves full IAD-Bench schema tables.

    参数:
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing schema-table markers.
    """
    required_markers = [
        r"\section{IAD-Bench Schema Contracts}",
        r"\label{tab:iad-bench-document-schema}",
        r"\label{tab:iad-bench-pair-schema}",
        "Record identity",
        "Text and authorship",
        "Bibliographic metadata",
        "Agenda context",
        r"\texttt{document\_id}",
        r"\texttt{openalex\_work\_id}",
        r"\texttt{references}",
        "Pair identity",
        "Relation targets",
        "Evidence source",
        "Evaluation control",
        r"\texttt{pair\_id}",
        r"\texttt{expected\_agenda\_label}",
        r"\texttt{hard\_negative\_level}",
        "identifies agenda-level hard negatives for HNFMR",
    ]
    return [
        f"IAD-Bench supplementary schema table missing marker: {marker}"
        for marker in required_markers
        if marker not in supplementary_text
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
        "full claim-evidence boundary table is reported in the supplementary material",
        "identity-agenda confusion is supported only as a false-merge pathway",
        "IAD-Risk support is bounded to the reported Open-v2 setting",
        "IAD-Bench is a provenance-aware evaluation contract",
        "repository-level reproduction does not by itself prove full numerical results",
        "complete row-family artifact crosswalk is reported in the supplementary material",
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
        "capacity-normalized review load",
        "pair/document IDs",
        "score or probability fields",
        "threshold name",
        "selection split",
        "selection metric",
        r"\path{source_input_manifest}",
        r"\path{processing_run_log}",
        "public input provenance",
        "code commits",
        "output paths",
        "exit status",
        "artifact-level and manuscript-package validation",
        "source artifact directory contains the files required by the release manifest",
        "without writing release files",
        "not itself result evidence",
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
        r"\label{tab:claim-evidence-boundary-main}",
        "Claim-evidence boundary used to interpret the reported results",
        "Identity-agenda confusion is a concrete false-merge pathway",
        "IAD-Risk reduces risky automatic merges in the reported setting",
        "IAD-Bench supports provenance-aware evaluation",
        "Repository-level reproduction is possible without committing raw data",
        r"\label{tab:result-artifact-crosswalk}",
        "Result artifact crosswalk for the Open-v2 evidence snapshot",
        "checksums.sha256",
        "released artifact package",
        "python manuscript/scripts/build_artifact_release_skeleton.py",
        "--preflight-only",
        r"\path{artifact_population_log.jsonl}",
        "source artifact directory is structurally ready for population",
        "does not prove row-level schemas",
        "python manuscript/scripts/populate_artifact_release.py",
        "python manuscript/scripts/finalize_artifact_release.py",
        "python manuscript/scripts/validate_artifact_release.py",
        "required result identifiers",
        "conditional claim artifacts",
        r"\path{open_v2_main_results}",
        r"\path{iad_bench_split_summary}",
        r"\path{representation_baseline_scores}",
        r"\path{supervised_baseline_predictions}",
        r"\path{iad_risk_predictions}",
        r"\path{threshold_selection_logs}",
        r"\path{bootstrap_intervals}",
        r"\path{ablation_suite}",
        r"\path{manual_validation_slice}",
        "per-row denominator counts",
        "per-row threshold source",
        "scope label used in the main table",
        "automatic merge count",
        "block count",
        "defer count",
        "automatic merge coverage",
        "defer rate",
        "capacity-normalized review load",
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


def check_method_feature_contract(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether the method states implementation-level feature boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing method-contract markers.
    """
    required_main_markers = [
        r"\subsection{Feature and Head Specification}",
        "full feature and head specification table is reported in the supplementary material",
        "Transformer distances",
        "title similarity",
        "author overlap",
        "DOI/arXiv/OpenAlex identifier agreement",
        "topic overlap",
        "reference Jaccard similarity",
        "different-identifier conflicts",
        "provenance-aware masking",
        "audit metadata remains traceable but is not a training feature",
    ]
    required_supplement_markers = [
        r"\label{tab:feature-head-specification}",
        "Feature and head specification for IAD-Risk transformer variants",
        "Head or stage",
        "Main input fields",
        "Supervision or calculation",
        "Output role",
        "Identity head",
        "Agenda head",
        "ANI risk head",
        "Risk gate",
        "Audit metadata",
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
    errors = [
        f"method feature contract missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"method feature contract missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


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


def check_risk_score_design_rationale(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether the method explains the false-merge risk score design.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing risk-score rationale markers.
    """
    required_main_markers = [
        r"\subsection{Risk Score Design Rationale}",
        "full risk score design rationale table is reported in the supplementary material",
        r"$p_{\mathrm{risk}}$ is a conservative upper-envelope risk proxy",
        "increases monotonically with agenda-non-identity evidence",
        "agenda evidence is high and identity evidence is weak",
        "max operator",
        "direct ANI evidence or indirect agenda-without-identity evidence",
        "not a calibrated probability",
        "Threshold transfer must be rechecked under new source distributions",
        "defer rather than merge",
    ]
    required_supplement_markers = [
        r"\label{tab:risk-score-rationale}",
        "Risk score design rationale",
        "Design element",
        "Design rationale",
        "Boundary",
        r"$p_{\mathrm{ani}}$ term",
        r"$p_{\mathrm{agenda}}(1-p_{\mathrm{work}})$ term",
        "Max operator",
        "Threshold gate",
        "not a calibrated probability",
        "Threshold transfer must be rechecked under new source distributions",
    ]
    errors = [
        f"risk score design rationale missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"risk score design rationale missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


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
        "full operational net-benefit matrix is reported in the supplementary material",
        "false merges are more costly than additional review",
        "three relation heads and explicit threshold records",
        "automatic merge coverage must be large enough to reduce reviewer work",
        "Low FMR or HNFMR alone is insufficient for productivity or cost-saving claims",
        "deferral budget and manual-review capacity",
        "conservative safety filter",
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
        "full version and identifier boundary table is reported in the supplementary material",
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


def check_method_design_supplementary_boundaries(supplementary_text: str) -> list[str]:
    """Check whether supplementary material preserves method-design boundary matrices.

    参数:
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing method-design boundary markers.
    """
    required_markers = [
        r"\section{Method Design Boundaries}",
        r"\label{tab:operational-net-benefit}",
        r"\label{tab:version-identifier-boundary}",
        "Operational complexity and net-benefit boundary",
        "The net benefit is strongest in high-stakes scholarly indexes",
        "Thresholds are not tuned per pair",
        "deferral budget and manual-review capacity",
        "conservative safety filter",
        "not a universal replacement",
        "Version and identifier boundary for merge decisions",
        "identifier agreement supports merge eligibility",
        "identifier conflict creates cannot-link or defer evidence",
        "not every related version is automatically the same work",
        "manual adjudication is required for ambiguous version boundaries",
        "version policy must be declared before cluster-level merging",
    ]
    return [
        f"method design supplementary boundary missing marker: {marker}"
        for marker in required_markers
        if marker not in supplementary_text
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


def check_scoring_merge_algorithm(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether the method states executable scoring and merge order.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing scoring-algorithm markers.
    """
    required_main_markers = [
        r"\subsection{Scoring and Merge Algorithm}",
        r"\subsection{Training and Inference Trace}",
        "full training and inference trace table is reported in the supplementary material",
        "threshold fixation, inference, and metric export",
        "schema loading preserves pair IDs and split fields",
        "supervised fitting uses the masked objective",
        "threshold fixation records",
        "selection split",
        "selection metric",
        "pair scoring writes",
        "decision emission records merge, block, or defer",
        "metric export binds denominators and checksums",
        "full scoring and merge algorithm table is reported in the supplementary material",
        "fixed scoring and merge order",
        "identity, agenda, ANI, and audit fields",
        "without using audit metadata as predictors",
        r"$p_{\mathrm{work}}$",
        r"$p_{\mathrm{agenda}}$",
        r"$p_{\mathrm{ani}}$",
        r"$p_{\mathrm{risk}}=\max\{p_{\mathrm{ani}},p_{\mathrm{agenda}}(1-p_{\mathrm{work}})\}$",
        "cannot-link flag",
        "merge, block, or defer",
        "decision, row scope, denominators, thresholds, and checksum-bound artifact rows",
        "same-work F1, FMR, HNFMR, coverage, and defer-rate audits",
    ]
    required_supplement_markers = [
        r"\label{tab:training-inference-trace}",
        "Training and inference trace for IAD-Risk",
        "Phase",
        "Required operation",
        "Auditable output or invariant",
        "Schema loading",
        "Supervised fitting",
        "Threshold fixation",
        "Pair scoring",
        "Decision emission",
        "Metric export",
        "Pair IDs and split fields remain unchanged",
        "Gold, proxy, and silver labels are not silently converted",
        "Threshold source, value, selection split, and selection metric",
        "Prediction rows expose relation scores",
        "cannot-link status",
        "Metric summaries and checksums bind denominators",
        r"\label{tab:scoring-merge-algorithm}",
        "Scoring and merge algorithm for IAD-Risk",
        "Step",
        "Operation",
        "Required inputs or outputs",
        "Audit role",
        "Load a candidate pair and schema metadata",
        "Build feature groups without using audit metadata as predictors",
        "Predict relation heads",
        "Compute derived false-merge risk",
        "Apply the merge gate and cannot-link evidence",
        "Write prediction and metric audit fields",
        "Fixes row identity before scoring",
        "Prevents provenance or split leakage",
        "Emits merge, block, or defer under a fixed operating point",
        "Supports same-work F1, FMR, HNFMR, coverage, and defer-rate audits",
    ]
    errors = [
        f"scoring and merge algorithm missing marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"training and inference trace missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


def check_design_alternative_boundaries(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether the method explains why simpler alternatives are insufficient.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing design-alternative boundaries.
    """
    required_main_markers = [
        r"\subsection{Design Alternatives and Rejected Shortcuts}",
        "full design-alternatives table is reported in the supplementary material",
        "Tuning only a representation-similarity threshold",
        "Relying on one supervised pair classifier",
        "Using provenance as a model feature",
        "Forcing every candidate into a binary merge decision",
        "Selecting thresholds after test results",
        "RoBERTa remains a strong baseline",
        "broad superiority is not claimed",
        "threshold stability needs a released grid and checksums",
    ]
    required_supplement_markers = [
        r"\label{tab:design-alternatives}",
        "Design alternatives considered during method design",
        "Alternative",
        "Why it is insufficient for this failure mode",
        "IAD-Risk design response",
        "Evidence boundary",
        "Tune only a representation-similarity threshold",
        "Rely on one supervised pair classifier",
        "Use provenance as a model feature",
        "Force every candidate into a binary merge decision",
        "Select thresholds after test results",
        "RoBERTa remains a strong baseline",
        "broad superiority is not claimed",
        "Threshold stability needs a released grid and checksums",
    ]
    errors = [
        f"design alternative boundary missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"design alternative boundary missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


def check_failure_control_rationale(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether the method states failure-control pathways and boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing failure-control rationale markers.
    """
    required_main_markers = [
        r"\subsection{Failure-Control Rationale}",
        "full failure-control rationale table is reported in the supplementary material",
        "failure-control framework rather than another similarity scorer",
        "Topically close papers receive high semantic similarity",
        "Silver metadata is treated as if it were human gold",
        "Pairwise errors can contaminate clusters through transitivity",
        "Thresholds can turn a classifier into an unsafe automatic merger",
        "Proxy labels are over-interpreted",
        "Threshold transfer should be rechecked under new source distributions",
        "proxy rows remain non-human evidence even when reproducible",
    ]
    required_supplement_markers = [
        r"\label{tab:failure-controls}",
        "Failure-control rationale of IAD-Risk",
        "Failure pathway",
        "Design response",
        "Remaining boundary",
        "Topically close papers receive high semantic similarity",
        "Silver metadata is treated as if it were human gold",
        "Pairwise errors contaminate clusters through transitivity",
        "Thresholds turn a classifier into an unsafe automatic merger",
        "Proxy labels are over-interpreted",
        "Cluster-level guarantees require complete cannot-link coverage",
    ]
    errors = [
        f"failure-control rationale missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"failure-control rationale missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


def check_operating_point_disclosure(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether result operating points are disclosed for review.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing operating-point markers.
    """
    required_main_markers = [
        r"\subsection{Operating Point Disclosure}",
        "full operating-point disclosure table is reported in the supplementary material",
        "fixed operating points",
        "post-hoc best test thresholds",
        "Representation cosine baselines",
        "RoBERTa pair classifier",
        "IAD-Risk transformer variants",
        r"default $\tau_w=\tau_a=\tau_r=0.5$",
        "score file, metric summary, and threshold entry",
        "prediction file, metric summary, and model log",
        "prediction file, model JSON, thresholds, and checksums",
        "Default-threshold rows have a narrower interpretation",
        r"\texttt{threshold\_source=predeclared\_default}",
        "pre-run configuration checksum",
        "configuration timestamp or run identifier",
        "fixed before held-out scoring",
        "cannot be described as validation-selected, optimized, or threshold-stable",
        r"\path{threshold_selection_logs}",
        r"\path{threshold_sensitivity_grid}",
    ]
    required_supplement_markers = [
        r"\section{Operating Point Disclosure}",
        r"\label{tab:operating-point-disclosure}",
        "Operating point disclosure for the Open-v2 result table",
        "Row family",
        "Decision field",
        "Operating point source",
        "Audit requirement",
        "Representation cosine baselines",
        "RoBERTa pair classifier",
        "IAD-Risk transformer variants",
        "Score file, metric summary, and threshold entry",
        "Prediction file, model JSON, thresholds, and checksums",
        "Default-threshold audit rule",
        r"\texttt{threshold\_source=predeclared\_default}",
        "pre-run configuration checksum",
        "configuration timestamp or run identifier",
        "fixed before held-out scoring",
        "not evidence of validation-selected, optimized, or threshold-stable performance",
        r"\path{threshold_selection_logs}",
        r"\path{threshold_sensitivity_grid}",
    ]
    errors = [
        f"operating point disclosure missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"operating point disclosure missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


def check_selective_decision_coverage_boundary(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether selective merge decisions state coverage and deferral boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing selective-decision coverage markers.
    """
    required_main_markers = [
        r"\subsection{Selective Decision Coverage Boundary}",
        "full selective-decision coverage boundary table is reported in the supplementary material",
        "automatic merge coverage",
        "block rate",
        "defer rate",
        "review load",
        "capacity-normalized review load",
        "same prediction files",
        "low FMR or HNFMR but high deferral is a conservative triage result",
        "N=M+B+D",
        r"\mathrm{AMC}=\frac{M}{N}",
        r"\mathrm{BR}=\frac{B}{N}",
        r"\mathrm{DR}=\frac{D}{N}",
        r"B_{\mathrm{review}}\leq B",
        r"D_{\mathrm{review}}\leq D",
        "Terminal cannot-link blocks",
        r"R=B_{\mathrm{review}}+D_{\mathrm{review}}",
        r"\mathrm{CNRL}=\frac{R}{C}",
        "same prediction artifact, threshold configuration, row scope, and denominator record",
        "predeclared manual-review capacity and deferral budget",
        "does not claim throughput reduction",
        "does not claim all-pair automatic resolution",
    ]
    required_supplement_markers = [
        r"\section{Selective Decision Coverage Boundary}",
        r"\label{tab:selective-decision-coverage}",
        "Selective decision coverage boundary",
        "Quantity",
        "Required artifact source",
        "Interpretation boundary",
        "Automatic merge coverage",
        "Block rate",
        "Defer rate",
        "Review load",
        "Capacity-normalized review load",
        "N=M+B+D",
        r"\mathrm{AMC}=M/N",
        r"\mathrm{BR}=B/N",
        r"\mathrm{DR}=D/N",
        r"B_{\mathrm{review}}\leq B",
        r"D_{\mathrm{review}}\leq D",
        "terminal cannot-link blocks",
        r"R=B_{\mathrm{review}}+D_{\mathrm{review}}",
        r"\mathrm{CNRL}=R/C",
        "review-required blocked and deferred pairs",
        "Terminal safety blocks must be separated",
    ]
    errors = [
        f"selective decision coverage boundary missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"selective decision coverage boundary missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


def check_pair_cluster_evidence_boundary(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether pair-level metrics are separated from cluster-level claims.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing pair-to-cluster evidence boundaries.
    """
    required_main_markers = [
        r"\subsection{Pair-to-Cluster Evidence Boundary}",
        "full pair-to-cluster evidence boundary table is reported in the supplementary material",
        "pair-level metrics do not by themselves prove cluster-level deduplication quality",
        "transitive merge propagation",
        "cannot-link violations",
        "cluster assignments",
        "pair-to-cluster trace files",
        "cluster_metric_summary",
        "cannot_link_audit",
        "cluster contamination rate",
        "does not claim cluster-level contamination is eliminated",
    ]
    required_supplement_markers = [
        r"\section{Pair-to-Cluster Evidence Boundary}",
        r"\label{tab:pair-cluster-evidence-boundary}",
        "Pair-to-cluster evidence boundary",
        "Evidence item",
        "Required artifact source",
        "Interpretation boundary",
        "cluster assignments",
        "cannot-link violations",
        "Cluster metric summary",
        "Pair-to-cluster trace",
        "cluster contamination rate",
    ]
    errors = [
        f"pair-to-cluster evidence boundary missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"pair-to-cluster evidence boundary missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


def check_decision_metric_mapping(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether selective decisions are mapped to reported metrics.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing decision-to-metric mapping markers.
    """
    required_main_markers = [
        r"\subsection{Decision-to-Metric Mapping}",
        "full decision-to-metric mapping table is reported in the supplementary material",
        "automatic merge is the positive decision",
        "block and defer are non-merge decisions",
        "Deferred same-work pairs reduce recall",
        "FMR and HNFMR count only automatic merges among non-identity rows",
        "coverage and defer rate must be reported separately",
        "block suppresses false merges",
        "defer protects against unsafe automatic decisions",
    ]
    required_supplement_markers = [
        r"\section{Decision-to-Metric Mapping}",
        r"\label{tab:decision-metric-mapping}",
        "Decision-to-metric mapping for selective merge outputs",
        "Decision output",
        "Metric treatment",
        "Interpretation boundary",
        "Merge",
        "Block",
        "Defer",
    ]
    errors = [
        f"decision-to-metric mapping missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"decision-to-metric mapping missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


def check_metric_formula_boundary(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether reported metrics define formulas and denominators.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing metric-formula boundary markers.
    """
    required_main_markers = [
        r"\subsection{Metric Formula Boundary}",
        "TP",
        "FP",
        "FN",
        r"$2TP/(2TP+FP+FN)$",
        "FMR denominator is all non-identity rows in the evaluated scope",
        "HNFMR denominator is the agenda-level hard-negative subset",
        "missing labels are not silently added to denominators",
        "manual-review workload",
        "identity-agenda false merges",
        "full metric-formula boundary table is reported in the supplementary material",
    ]
    required_supplement_markers = [
        r"\section{Metric Formula Boundary}",
        r"\label{tab:metric-formula-boundary}",
        "Metric formula boundary",
        "Metric",
        "Formula or denominator",
        "Boundary",
        "Same-work F1",
        "FMR",
        "HNFMR",
        "Defer and block decisions on true same-work rows enter FN",
    ]
    errors = [
        f"metric formula boundary missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"metric formula boundary missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


def check_threshold_sensitivity_status(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether threshold sensitivity claims are bounded by artifact evidence.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing threshold-sensitivity markers.
    """
    required_main_markers = [
        r"\subsection{Threshold Sensitivity Evidence Status}",
        "full threshold-sensitivity evidence status table is reported in the supplementary material",
        "Threshold stability is treated as an audit requirement",
        "not as an unsupported robustness claim",
        "same prediction files",
        "predefined threshold ranges",
        "not reported as primary evidence",
        "per-threshold F1, FMR, HNFMR",
        "random seeds",
        "command logs",
        "a manifest",
        "checksums",
        "not threshold-stable ranking across all operating points",
    ]
    required_supplement_markers = [
        r"\section{Threshold Sensitivity Evidence Status}",
        r"\label{tab:threshold-sensitivity-status}",
        "Threshold sensitivity evidence status",
        "Audit item",
        "Current manuscript status",
        "Required artifact before stronger claim",
        "Fixed operating point",
        "Threshold grid",
        "Metric stability",
        "Artifact manifest",
        "Interpretation boundary",
    ]
    errors = [
        f"threshold sensitivity evidence status missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"threshold sensitivity evidence status missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


def check_threshold_uncertainty_reporting(manuscript_text: str) -> list[str]:
    """Check whether threshold and uncertainty boundaries remain visible in the main text.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing threshold and uncertainty boundaries.
    """
    required_markers = [
        r"\subsection{Threshold Selection and Uncertainty Reporting}",
        "full threshold and uncertainty reporting protocol is reported in the supplementary material",
        "fixed selection protocol",
        "best test threshold",
        "validation evidence",
        "default implementation threshold",
        "fixed operating point",
        "test split is then used only for final metric reporting",
        "FMR and HNFMR",
        "prediction files and resampling logs",
        "no-risk-gate, no-ANI-head, single-space, no-cannot-link, and post-hoc-threshold variants",
        "predictions, configs, logs, checksums, and commit identifiers",
    ]
    return [
        f"threshold uncertainty reporting missing marker: {marker}"
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
        "full statistical interpretation table is reported in the supplementary material",
        "point estimates for a fixed evidence snapshot",
        "not statistical superiority estimates",
        "Confidence intervals, significance tests, and model-ranking statements are intentionally withheld",
        "exact prediction files, resampling logs, random seeds, and checksums",
        "no hard-negative false merge was observed",
        "not be read as proof of zero risk",
        "Zero-observed HNFMR rows require numerator-denominator disclosure",
        "hard-negative false-merge numerator $=0$",
        "HNFMR denominator",
        "hard-negative label stratum",
        "evaluated split",
        "threshold source",
        "prediction-file checksum",
        "A rounded value of 0.000 without those fields is treated only as a manuscript summary",
        r"\path{bootstrap_intervals}",
        "Predefined tests, multiplicity handling, input artifacts, and reproducible analysis logs",
        "Same-scope predictions, interval estimates, ablations, and manual-validation slice",
    ]
    return [
        f"statistical interpretation boundary missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_ablation_acceptance_boundary(manuscript_text: str) -> list[str]:
    """Check whether the manuscript defines accepted ablation evidence.

    参数:
        manuscript_text: Main LaTeX manuscript source.

    返回:
        list[str]: Error messages for missing ablation-acceptance markers.
    """
    required_markers = [
        r"\subsection{Ablation Acceptance Boundary}",
        "same pair scope, split field, metric implementation, and predeclared operating-point rule",
        "no-risk-gate, no-ANI-head, single-space, no-cannot-link, and post-hoc-threshold",
        r"\texttt{protocol\_variant}",
        "prediction rows, threshold logs, denominator records",
        "same-work F1, FMR, and HNFMR",
        "checksum-bound configuration files",
        "exploratory diagnostic evidence rather than an accepted ablation",
        "post-hoc-threshold row is a diagnostic threshold-sweep control",
        "cannot by itself support a component-causality claim",
    ]
    return [
        f"ablation acceptance boundary missing marker: {marker}"
        for marker in required_markers
        if marker not in manuscript_text
    ]


def check_experiment_reporting_supplementary_boundaries(supplementary_text: str) -> list[str]:
    """Check whether moved experiment-reporting boundary tables are in the supplement.

    参数:
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing supplementary experiment-reporting tables.
    """
    required_markers = [
        r"\section{Uncertainty and Ablation Requirements}",
        r"\label{tab:threshold-uncertainty-protocol}",
        r"\label{tab:ablation-acceptance-protocol}",
        r"\label{tab:statistical-interpretation-boundary}",
        "Threshold and uncertainty reporting protocol",
        "Ablation acceptance protocol",
        "Merge thresholds",
        "Metric uncertainty",
        "Risk metrics",
        "Ablation claims",
        "Artifact audit",
        "Required variants",
        "no-risk-gate, no-ANI-head, single-space, no-cannot-link, and post-hoc-threshold",
        r"\texttt{protocol\_variant}",
        "Scope parity",
        "same pair scope, split field, label stratum, and metric implementation",
        "Decision trace",
        "prediction rows, threshold logs, same-work F1/FMR/HNFMR denominators",
        "Artifact binding",
        "configuration, command log, random seed when applicable, code commit, manifest entry, and checksum",
        "Interpretation rule",
        "changed pair universe, threshold-selection source, prediction schema, or post-hoc threshold selection",
        "post-hoc-threshold row is retained as a threshold-overfitting diagnostic",
        "Statistical interpretation boundary",
        "Point estimates",
        "Confidence intervals",
        "Statistical significance",
        "Zero HNFMR rows",
        "Hard-negative false-merge numerator $=0$",
        "HNFMR denominator",
        "hard-negative label stratum",
        "evaluated split",
        "threshold source",
        "prediction-file checksum",
        "Model ranking",
        r"\path{bootstrap_intervals}",
        "Predefined tests, multiplicity handling, input artifacts, and reproducible analysis logs",
        "Same-scope predictions, interval estimates, ablations, and manual-validation slice",
    ]
    return [
        f"experiment reporting supplementary boundary missing marker: {marker}"
        for marker in required_markers
        if marker not in supplementary_text
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
        "complete inclusion matrix is reported in the supplementary material",
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
        "full fairness-control matrix is in the supplementary material",
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


def check_baseline_supplementary_tables(supplementary_text: str) -> list[str]:
    """Check whether supplementary material preserves the full baseline audit matrices.

    参数:
        supplementary_text: Supplementary LaTeX source text.

    返回:
        list[str]: Error messages for missing supplementary baseline tables.
    """
    required_markers = [
        r"\section{Baseline Audit Boundary}",
        r"\label{tab:baseline-inclusion-rationale}",
        r"\label{tab:baseline-fairness-controls}",
        "Exact identifier matching",
        "Title-normalization rules",
        "Traditional entity-resolution systems",
        "Scientific representation baselines",
        "RoBERTa pair classification",
        "Included as primary evidence only when metric summaries, prediction files, threshold records, and checksums are available",
        "Excluded from primary result table when only utility code or fixture-level checks are available",
        "same IAD-Bench pair records",
        "same train/dev/test split field",
        "validation-selected operating points",
        "same-scope released prediction files",
        "not be read as a single comparative ranking",
    ]
    return [
        f"baseline supplementary audit table missing marker: {marker}"
        for marker in required_markers
        if marker not in supplementary_text
    ]


def check_result_interpretation_guardrails(manuscript_text: str, supplementary_text: str) -> list[str]:
    """Check whether the main result table states allowed and unsupported readings.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing result-interpretation guardrails.
    """
    required_main_markers = [
        r"\subsection{Result Interpretation Guardrails}",
        "full result interpretation guardrails table is reported in the supplementary material",
        "Scope type",
        "full available Open-v2 scope",
        "held-out Open-v2 test scope",
        "Scope labels prevent ranking interpretation",
        "representation rows test false-merge exposure",
        "RoBERTa row is a strong supervised comparator",
        "IAD-Risk rows test split-held-out risk gating",
        "FMR=0.001",
        "zero observed HNFMR should be read as no observed false merge in the agenda-hard-negative stratum",
        "not as absence of all non-identity false merges",
        "not a claim of broad method superiority",
        "not a same-scope comparative ranking",
        "not evidence of threshold stability or zero risk",
    ]
    required_supplementary_markers = [
        r"\section{Claim-Evidence Matrix}",
        r"\label{tab:result-interpretation-guardrails}",
        "Result interpretation guardrails for the Open-v2 evidence snapshot",
        "Directly supported reading",
        "Unsupported reading",
        "mechanism-supported reading",
        "Representation baselines",
        "RoBERTa pair classifier",
        "IAD-Risk transformer variants",
        "Zero-HNFMR IAD-Risk rows",
        "ordinary FMR is still reported separately",
        "not evidence that all non-identity false merges are absent",
        "not a claim of broad method superiority",
        "not a same-scope comparative ranking",
        "not evidence of threshold stability or zero risk",
    ]
    errors = [
        f"result interpretation guardrails missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    errors.extend(
        f"result interpretation guardrails missing supplementary marker: {marker}"
        for marker in required_supplementary_markers
        if marker not in supplementary_text
    )
    return errors


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
        "full manual validation boundary table is reported in the supplementary material",
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


def check_split_leakage_controls(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether evaluation split and leakage boundaries are stated.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing split-control markers.
    """
    required_main_markers = [
        r"\subsection{Split and Leakage Controls}",
        "full split and leakage controls table is reported in the supplementary material",
        "Training uses only the declared training split",
        "threshold selection uses validation evidence",
        "Metadata fields that identify source, provenance, or split",
        "Unordered pair leakage guard",
        "Document/cluster split-overread guard",
        "Label-stratum coverage audit",
        "Source-heldout readiness audit",
        "Topic-heldout readiness audit",
        "topic-stability claims",
        "pair-record held-out mechanism evidence",
        "document-disjoint, cluster-disjoint, or unseen-source generalization",
        "grouped split manifests",
        "document/cluster overlap reports",
        "per-scope denominators",
        "threshold logs",
    ]
    required_supplement_markers = [
        r"\section{Split and Leakage Controls}",
        r"\label{tab:split-leakage-controls}",
        "Split and leakage controls used to interpret IAD-Bench results",
        "Control",
        "Manuscript role",
        "Stronger evidence boundary",
        "Train/dev/test split field",
        "Unordered pair leakage guard",
        "Document/cluster split-overread guard",
        "pair-record held-out evidence",
        "document-disjoint or cluster-disjoint grouping before split assignment",
        "Document-disjoint, cluster-disjoint, or unseen-source generalization",
        "grouped split manifests",
        "document/cluster overlap reports",
        "per-scope denominators",
        "threshold logs",
        "Label-stratum coverage audit",
        "Source-heldout readiness audit",
        "train, validation, and held-out source partitions",
        "per-source denominators",
        "prediction checksums",
        "Topic-heldout readiness audit",
        "Cross-topic stability should not be claimed when topic coverage is insufficient",
    ]
    errors = [
        f"split and leakage controls missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"split and leakage controls missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


def check_scope_compatibility(manuscript_text: str, supplementary_text: str) -> list[str]:
    """Check whether mixed-scope Open-v2 rows have a clear interpretation boundary.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing scope-compatibility markers.
    """
    required_main_markers = [
        r"\subsection{Scope Compatibility of the Open-v2 Table}",
        "full scope compatibility matrix is reported in the supplementary material",
        "scope-bounded evidence table",
        "not a single comparative ranking",
        "Full pair-scope representation baselines",
        "Held-out IAD-Risk rows",
        "same released prediction scope",
        "manual-validation slice",
        "A claim that this stronger comparison has already been completed",
    ]
    required_supplementary_markers = [
        r"\section{Claim-Evidence Matrix}",
        r"\label{tab:scope-compatibility}",
        "Scope compatibility for interpreting the Open-v2 evidence snapshot",
        "Representation baselines",
        "Full available Open-v2 pair scope",
        "RoBERTa pair classifier",
        "IAD-Risk transformer variants",
        "Held-out Open-v2 test scope",
        "Future stronger comparison",
        "Same released prediction scope plus manual-validation slice",
        "A claim that this stronger comparison has already been completed",
    ]
    errors = [
        f"Open-v2 scope compatibility missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    errors.extend(
        f"Open-v2 scope compatibility missing supplementary marker: {marker}"
        for marker in required_supplementary_markers
        if marker not in supplementary_text
    )
    return errors


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
        "source-heldout claim to become admissible",
        "train, validation, and held-out source partitions",
        "keep source identifiers out of predictive features",
        "per-source denominators for same-work F1, FMR, and HNFMR",
        "command logs, split summaries, prediction checksums, and threshold records",
        "coverage gap or exploratory diagnostic",
        "source-heldout is therefore a readiness protocol rather than current evidence of source generalization",
    ]
    errors = [f"extended protocol boundary missing marker: {marker}" for marker in required_markers if marker not in manuscript_text]
    unsupported_phrases = [
        "Open-v3 and source-heldout experiments provide additional stress tests",
        "Open-v3 as extended validation",
        "source-heldout generalization remains mixed",
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
        r"\label{tab:manual-validation-boundary}",
        r"\label{tab:manual-validation-protocol}",
        "Manual validation boundary for interpreting silver hard negatives",
        "future evidence layer",
        "500--1,000 pairs",
        "500--1,000 pair reviewed slice",
        "two independent reviewers",
        "blind to model scores",
        "adjudication log",
        "agreement report",
        "pair-level notes",
        "inter-annotator agreement",
        "silver rows replace human-gold non-identity labels",
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


def check_public_source_rebuild_audit_boundary(supplementary_text: str) -> list[str]:
    """Check whether L2 public-source rebuilds have an auditable boundary.

    参数:
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing public-source rebuild audit markers.
    """
    required_markers = [
        r"\section{Public-Source Rebuild Audit Boundary}",
        r"\label{tab:public-source-rebuild-audit-boundary}",
        r"\path{source_input_manifest}",
        r"\path{processing_run_log}",
        "Source name",
        "acquisition date or version",
        "original provider",
        "license boundary",
        "SHA256 checksum",
        "Command line",
        "code commit",
        "environment summary",
        "random seed",
        "output summaries",
        "chain of custody",
        "do not upgrade fixture-level reproduction into a full numerical audit",
    ]
    return [
        f"public-source rebuild audit boundary missing marker: {marker}"
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
        "DKE guide source URL: https://www.sciencedirect.com/journal/data-and-knowledge-engineering/publish/guide-for-authors",
        "DKE Official Guide Evidence",
        "official-guide preflight record",
        "`selected_author_guide_source`",
        "`selected_author_guide_source_url`",
        "`selected_author_guide_rechecked_date`",
        "`selected_target_author_confirmed`",
        "Information Systems guide verified: 2026-06-19",
        "Scientometrics guide verified: 2026-06-19",
        "All publisher-page facts in this shortlist were rechecked on 2026-06-19",
        "official source links",
        "authors' authorized ranking systems",
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
        "maximum 100 words",
        "editable format",
        "must not be PDF",
        "passport-type photograph",
        "publisher metrics as screening signals",
        "final-upload blockers",
        "outside anonymous preflight packages",
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
        "source_input_manifest",
        "processing_run_log",
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
            "capacity-normalized review load",
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
        "source_input_manifest": [
            "source name",
            "acquisition date or version",
            "original provider",
            "local file name",
            "record count",
            "license boundary",
            "SHA256 checksum",
        ],
        "processing_run_log": [
            "command line",
            "code commit",
            "environment summary",
            "random seed",
            "start and finish timestamps",
            "input manifest reference",
            "output path",
            "exit status",
        ],
        "bootstrap_intervals": [
            "metric_name rows for same_work_f1, fmr, and hnfmr",
            "system",
            "scope_type",
            "prediction_artifact_id",
            "prediction_file_sha256",
            "bootstrap_method",
            "resample_unit",
            "resample_count",
            "confidence_level",
            "alpha",
            "random_seed",
            "point_estimate",
            "interval_lower",
            "interval_upper",
            "metric_denominator",
            "threshold_source",
            "command_line",
            "exact prediction file checksum",
            "interval_lower <= point_estimate <= interval_upper",
        ],
        "ablation_suite": [
            "protocol_variant",
            "no-risk-gate",
            "no-ANI-head",
            "single-space",
            "no-cannot-link",
            "post-hoc-threshold",
            "protocol_required",
            "accepted_for_component_causality",
            "threshold_source",
            "protocol_scope_rule",
            "requires_prediction_rows",
            "denominators",
            "false-merge metrics",
            "post_hoc_labeled_sweep",
            "must not be accepted as standalone component-causality evidence",
        ],
        "manual_validation_slice": [
            "500-1000 pair reviewed slice",
            "manual_validation_stratum",
            "silver_hard_negative",
            "high_score_false_merge_candidate",
            "blocked_or_deferred",
            "model_disagreement",
            "version_boundary",
            "identifier_conflict",
            "sparse_metadata",
            "two independent reviewer codes",
            "reviewer_1_code",
            "reviewer_2_code",
            "reviewer_1_label",
            "reviewer_2_label",
            "adjudicated_label",
            "reviewer_blinding_confirmed",
            "model_score_hidden",
            "merge_decision_hidden",
            "adjudication_status",
            "adjudication_rationale",
            "pair_level_notes",
            "agreement_status",
        ],
        "threshold_sensitivity_grid": [
            "at least two predefined threshold rows",
            "exactly one prediction_artifact_id",
            "prediction_file_sha256",
            "system",
            "threshold_grid_id",
            "threshold_range_source",
            "threshold_source",
            "selection_split",
            "evaluation_split",
            "work_threshold",
            "agenda_block_threshold",
            "risk_threshold",
            "selected_operating_point",
            "same_work_f1",
            "fmr",
            "hnfmr",
            "denominator counts",
            "automatic_merge_count",
            "block_count",
            "defer_count",
            "random_seed",
            "command_line",
            "separate selection and evaluation splits",
        ],
        "cluster_metric_summary": [
            "cluster_run_id",
            "merge_policy_id",
            "prediction_artifact_id",
            "prediction_file_sha256",
            "threshold_source",
            "work_threshold",
            "agenda_block_threshold",
            "risk_threshold",
            "cluster_assignment_file",
            "pair_to_cluster_trace_file",
            "cluster_id",
            "cluster_size",
            "accepted_link_count",
            "cannot_link_conflict_count",
            "unresolved_conflict_count",
            "cluster_contamination_rate",
            "singleton_rate",
            "merge_coverage",
            "random_seed",
            "command_line",
            "exactly one cluster_run_id",
            "exactly one merge_policy_id",
        ],
        "cannot_link_audit": [
            "cluster_run_id",
            "merge_policy_id",
            "prediction_artifact_id",
            "prediction_file_sha256",
            "threshold_source",
            "work_threshold",
            "agenda_block_threshold",
            "risk_threshold",
            "cannot_link_rule_id",
            "conflict_type",
            "source_document_id",
            "target_document_id",
            "cannot_link_flag",
            "accepted_merge_blocked",
            "violation_detected",
            "unresolved_conflict",
            "cannot_link_coverage_rate",
            "identifier_conflict_rule",
            "pair_to_cluster_trace_file",
            "random_seed",
            "command_line",
            "exactly one cluster_run_id",
            "exactly one merge_policy_id",
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
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
            "python manuscript/scripts/populate_artifact_release.py --artifact-dir",
            "python manuscript/scripts/finalize_artifact_release.py --artifact-dir",
            "python -m iad_sieve.cli --help",
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
        "Redistribute derived tables, predictions, logs, manifests, and checksums rather than raw provider files",
        "original provider terms explicitly allow redistribution",
        "local file boundary",
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
        "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
        "python manuscript/scripts/populate_artifact_release.py --artifact-dir",
        "python manuscript/scripts/finalize_artifact_release.py --artifact-dir",
        "python -m iad_sieve.cli --help",
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
        "capacity-normalized review load",
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
        "source_input_manifest",
        "acquisition date or version",
        "original provider",
        "license boundary",
        "processing_run_log",
        "command line",
        "code commit",
        "environment summary",
        "random seed",
        "exit status",
        "bootstrap_intervals",
        "metric_name rows for same_work_f1, fmr, and hnfmr",
        "scope_type",
        "prediction_artifact_id",
        "prediction_file_sha256",
        "bootstrap_method",
        "resample_unit",
        "resample_count",
        "confidence_level",
        "alpha",
        "point_estimate",
        "interval_lower",
        "interval_upper",
        "metric_denominator",
        "exact prediction file checksum",
        "interval_lower <= point_estimate <= interval_upper",
        "ablation_suite",
        "protocol_variant",
        "no-risk-gate",
        "no-ANI-head",
        "single-space",
        "no-cannot-link",
        "post-hoc-threshold",
        "protocol_required",
        "accepted_for_component_causality",
        "threshold_source",
        "protocol_scope_rule",
        "requires_prediction_rows",
        "denominators",
        "false-merge metrics",
        "post_hoc_labeled_sweep",
        "standalone component-causality evidence",
        "manual_validation_slice",
        "500-1000 pair reviewed slice",
        "manual_validation_stratum",
        "silver_hard_negative",
        "high_score_false_merge_candidate",
        "blocked_or_deferred",
        "model_disagreement",
        "version_boundary",
        "identifier_conflict",
        "sparse_metadata",
        "two independent reviewer codes",
        "reviewer_1_code",
        "reviewer_2_code",
        "reviewer_1_label",
        "reviewer_2_label",
        "adjudicated_label",
        "reviewer_blinding_confirmed",
        "model_score_hidden",
        "merge_decision_hidden",
        "adjudication_status",
        "adjudication_rationale",
        "pair_level_notes",
        "agreement_status",
        "threshold_sensitivity_grid",
        "at least two predefined threshold rows",
        "exactly one prediction_artifact_id",
        "prediction_file_sha256",
        "threshold_grid_id",
        "threshold_range_source",
        "evaluation_split",
        "selected_operating_point",
        "same_work_f1",
        "fmr",
        "hnfmr",
        "denominator counts",
        "automatic_merge_count",
        "block_count",
        "defer_count",
        "separate selection and evaluation splits",
        "Conditional Claim Artifacts",
        "cluster_run_id",
        "merge_policy_id",
        "cluster_assignment_file",
        "pair_to_cluster_trace_file",
        "cluster_id",
        "cluster_size",
        "accepted_link_count",
        "cannot_link_conflict_count",
        "unresolved_conflict_count",
        "cluster_contamination_rate",
        "singleton_rate",
        "merge_coverage",
        "cannot_link_rule_id",
        "conflict_type",
        "cannot_link_flag",
        "accepted_merge_blocked",
        "violation_detected",
        "cannot_link_coverage_rate",
        "identifier_conflict_rule",
        "exactly one cluster_run_id",
        "exactly one merge_policy_id",
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
        "L2 Public-Source Rebuild Boundary",
        "input boundary",
        "command boundary",
        "output boundary",
        "checksum boundary",
        "Release Metadata To Fill",
        "publication.artifact_release_url",
        "publication.artifact_release_doi",
        "publication.public_access_status",
        "final-upload `submission_metadata.yml`",
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
        "capacity-normalized review load",
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
        "publication",
        "publication.artifact_release_url",
        "publication.artifact_release_doi",
        "publication.public_access_status",
        "artifact manifest publication",
        "same public artifact URL or DOI",
        "repository_branch",
        "source_control.repository_branch",
        "分支必须为 `main`",
        "TECTONIC_BUNDLE_DIR",
        "本地 Tectonic bundle",
        "PDF rendering 检查",
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


def check_latex_build_scripts(build_script_text: str, elsevier_builder_text: str) -> list[str]:
    """Check whether LaTeX build scripts preserve offline bundle reproducibility.

    参数:
        build_script_text: Shell script source for full PDF builds.
        elsevier_builder_text: Python source for Elsevier preview builds.

    返回:
        list[str]: Error messages for missing offline bundle controls.
    """
    required_build_markers = [
        "TECTONIC_BUNDLE_DIR",
        "--bundle",
        "run_tectonic",
        "scripts/check_latex_warnings.py",
        "scripts/check_pdf_rendering.py",
    ]
    required_elsevier_markers = [
        "TECTONIC_BUNDLE_DIR",
        "--bundle",
        "os.environ.get",
        "subprocess.run(command",
    ]
    errors = [
        f"build_latex_pdf.sh missing offline bundle marker: {marker}"
        for marker in required_build_markers
        if marker not in build_script_text
    ]
    errors.extend(
        f"build_elsevier_draft.py missing offline bundle marker: {marker}"
        for marker in required_elsevier_markers
        if marker not in elsevier_builder_text
    )
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
        "L2 重建审计文件",
        "configs/source_input_manifest.json",
        "logs/processing_run_log.jsonl",
        "reports/iad_bench_split_summary.jsonl",
        "chain of custody",
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
        "def preflight_source_artifacts(",
        "def build_copy_plan(",
        "def copy_planned_artifacts(",
        "def write_population_log(",
        "def finalize_release(",
        "--source-dir",
        "--mapping",
        "--preflight-only",
        "--skip-finalize",
        "without copying, logging, or finalizing",
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
        "Blocking Evidence Matrix",
        "Required evidence before final upload",
        "Source field or file",
        "Current status",
        "Pending author confirmation",
        "Pending real artifact release",
        "Pending live system verification",
        "final_upload_checklist.target_journal_selected",
        "final_upload_checklist.manuscript_pdf_rebuilt_after_template",
        "author_identity_materials.biography_files",
        "artifact_boundary.artifact_release_url",
        "upload_preparation.live_submission_system_verified",
        "final_upload_checklist.first_screen_claim_lockdown_confirmed",
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
        "target ranking/category confirmation fields",
        "non-placeholder",
        "selected_author_guide_source",
        "selected_author_guide_source_url",
        "selected_author_guide_rechecked_date",
        "selected_template_requirements_confirmed",
        "ranking_confirmation_completed",
        "ranking_confirmation_source",
        "ranking_confirmation_source_url",
        "ranking_confirmation_checked_date",
        "selected_target_author_confirmed",
        "`article_type` uses `research_article`",
        "does not use `review_article`, `case_report`, or another article-type value",
        "`review_mode` records the live submission-system review setting",
        "`review_mode` uses an author-visible final-upload value",
        "single_anonymized_with_final_author_identities",
        "single_anonymized_author_visible_final_upload",
        "anonymous_review",
        "generic `single_anonymized` value",
        "live_submission_system_verified",
        "final_upload_package_verified_against_system",
        "author_identity_materials",
        "biography_files",
        "photograph_files",
        "author_identity_materials_verified",
        "maximum 100 words",
        "editable format",
        "must not be PDF",
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
        "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
        "checks required source artifact files before anything is copied",
        "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir",
        "python manuscript/scripts/finalize_artifact_release.py --artifact-dir",
        "python manuscript/scripts/validate_artifact_release.py --artifact-dir",
        "python -m iad_sieve.cli --help",
        "same repository checkout named by the release manifest",
        "configs/source_input_manifest.json",
        "local file boundary",
        "license boundary",
        "derived tables, predictions, logs, manifests, and checksums rather than raw provider files",
        "original provider terms explicitly allow redistribution",
        "open_v2_main_results",
        "per-row denominator counts",
        "per-row threshold source",
        "scope label used in the main table",
        "automatic merge count",
        "block count",
        "defer count",
        "automatic merge coverage",
        "defer rate",
        "capacity-normalized review load",
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
        "manifest.json` contains a `publication` object",
        "`artifact_release_url`, `artifact_release_doi`, and `public_access_status`",
        "artifact manifest publication object records the same public artifact URL or DOI as `submission_metadata.yml`",
        "artifact release URL is a public non-placeholder HTTP/HTTPS URL",
        "publication.public_access_status",
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
        "`repository_url` must be a public non-placeholder HTTP/HTTPS URL",
        "`repository_branch` must be `main`",
        "submission_manifest.json` records the same `repository_commit` and `repository_branch`",
        "python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release",
        "external artifact release is finalized",
        "Live Submission Text Checks",
        "Title, abstract, keywords, and highlights are copied from the current source files",
        "title and abstract match `main.tex`",
        "Keywords match `keywords.md` exactly",
        "Highlights match `highlights.md` exactly",
        "live submission system preview shows the same title, abstract, keywords, and highlights",
        "Mark `submission_system_files_verified`, `live_submission_system_verified`, and `final_upload_package_verified_against_system` true",
        "final package preview",
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
        "Completed audit cycles: 115",
        "Highest current reviewer-facing risks",
        "final-upload metadata",
        "target-journal template binding",
        "author-guide/template confirmation gap",
        "target ranking confirmation gap",
        "live final-package system verification gap",
        "DKE author biography and photograph materials",
        "DKE biography format and word-limit drift",
        "third-party data license and redistribution drift",
        "author identity material traceability",
        "external artifact release",
        "artifact source directory completeness",
        "artifact release validation bypass",
        "final-upload artifact-dir omission bypass",
        "artifact publication link mismatch",
        "zero-observed HNFMR overread",
        "FMR/HNFMR stratum conflation",
        "abstract FMR/HNFMR first-screen conflation",
        "highlights FMR/HNFMR first-screen conflation",
        "document/cluster split overread",
        "preflight package source freshness",
        "strict validation package freshness bypass",
        "reproduction command-chain drift",
        "strict PDF visual-quality validation bypass",
        "L2 public-source rebuild chain-of-custody gap",
        "selective-decision workload evidence",
        "selective workload denominator ambiguity",
        "anonymous cover-letter declaration confirmation",
        "preflight metadata declaration placeholders",
        "preflight manuscript declaration boundary",
        "introduction row-scope comparison overread",
        "artifact release README completeness",
        "artifact release commit validity",
        "artifact README/manifest commit mismatch",
        "final package/artifact commit mismatch",
        "final-upload artifact-dir instruction drift",
        "prediction artifact schema drift",
        "generative AI declaration consistency",
        "fixture/live evidence confusion",
        "live submission-system text consistency",
        "Git-only full-numerical audit overread",
        "source-to-PDF package consistency",
        "final-upload source-control package binding",
        "final-upload source-control branch drift",
        "final-upload artifact publication binding",
        "default-threshold provenance gap",
        "DKE official-guide source traceability",
        "DKE first-screen scope-fit drift",
        "keyword DKE scope-fit drift",
        "DKE abstract-length drift",
        "final article-type vocabulary gap",
        "final public-link placeholder gap",
        "final review-mode presence gap",
        "final cover-letter pass-path gap",
        "final cover-letter generic-variant gap",
        "final review-mode vocabulary gap",
        "method shortcut wording precision",
        "final-upload information request specificity",
        "stronger evidence gates",
        "Current stopping rule",
        "do not claim Q2/B completion or final-upload readiness",
        "real artifact URL or DOI",
        "author-guide source",
        "template requirements",
        "ranking/category status",
        "live submission system and final package preview",
        "artifact manifest publication object records the same URL or DOI with public access status",
        "Non-code external inputs still required",
        "author metadata",
        "DKE author biography and photograph materials",
        "target-journal confirmation",
        "selected author-guide source and rechecked date",
        "template requirements confirmation",
        "ranking/category confirmation source and date",
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
        "Audit Cycle 31: Zero-Observed HNFMR Wording Gate",
        "Audit Cycle 32: L2 Public-Source Rebuild Traceability Gate",
        "Audit Cycle 33: Main-Text L2 Provenance Alignment Gate",
        "Audit Cycle 41: Main-Text Schema Density Gate",
        "Audit Cycle 42: Related-Work Positioning Density Gate",
        "Audit Cycle 43: Method Design Boundary Density Gate",
        "Audit Cycle 44: Experiment Reporting Boundary Density Gate",
        "Audit Cycle 45: Result Artifact Crosswalk Density Gate",
        "Audit Cycle 46: Manual Validation Boundary Density Gate",
        "Audit Cycle 47: Scope Compatibility Matrix Density Gate",
        "Audit Cycle 48: Result Interpretation Guardrails Density Gate",
        "Audit Cycle 49: Claim-Evidence Boundary Density Gate",
        "Audit Cycle 50: Validity Threats Density Gate",
        "Audit Cycle 51: Claim Interpretation Boundary Density Gate",
        "Audit Cycle 52: Data and Code Availability Density Gate",
        "Audit Cycle 53: Error Taxonomy Density Gate",
        "Audit Cycle 54: Mechanism Evidence Boundary Density Gate",
        "Audit Cycle 55: Pair-to-Cluster Evidence Boundary Density Gate",
        "Audit Cycle 56: Selective Decision Coverage Boundary Density Gate",
        "Audit Cycle 57: Threshold Sensitivity Evidence Status Density Gate",
        "Audit Cycle 58: Operating Point Disclosure Density Gate",
        "Audit Cycle 59: Metric Formula Boundary Density Gate",
        "Audit Cycle 60: Decision-to-Metric Mapping Density Gate",
        "Audit Cycle 61: Split and Leakage Controls Density Gate",
        "Audit Cycle 62: Feature and Head Specification Density Gate",
        "Audit Cycle 63: Risk Score Design Rationale Density Gate",
        "Audit Cycle 64: Design Alternatives Density Gate",
        "Audit Cycle 65: Failure-Control Rationale Density Gate",
        "Audit Cycle 66: Reproduction Levels Density Gate",
        "Audit Cycle 67: Evaluation Protocol Density Gate",
        "Audit Cycle 68: Training and Inference Trace Density Gate",
        "Audit Cycle 69: Scoring and Merge Algorithm Density Gate",
        "Audit Cycle 70: Artifact Publication Binding Gate",
        "Audit Cycle 71: Target Ranking and Author Confirmation Gate",
        "Audit Cycle 72: Live System Final Package Verification Gate",
        "Audit Cycle 73: Author Guide and Template Requirement Confirmation Gate",
        "Audit Cycle 74: Author Identity Material Traceability Gate",
        "Audit Cycle 75: Closest-Work Decision-Semantics Gate",
        "Audit Cycle 76: Mechanism Ablation Acceptance Protocol Gate",
        "Audit Cycle 77: Ablation CLI Protocol-Variant Alignment Gate",
        "Audit Cycle 78: Ablation Artifact Release Schema Gate",
        "Audit Cycle 79: Manual Validation Artifact Release Schema Gate",
        "Audit Cycle 80: Threshold Sensitivity Artifact Release Schema Gate",
        "Audit Cycle 81: Cluster-Level Artifact Release Schema Gate",
        "Audit Cycle 82: Bootstrap Interval Artifact Release Schema Gate",
        "Audit Cycle 83: Artifact Release CLI Discovery Command Consistency Gate",
        "Audit Cycle 84: Submission Checklist Artifact CLI Discovery Gate",
        "Audit Cycle 85: Target Confirmation Date Validity Gate",
        "Audit Cycle 86: Target Confirmation Source URL Gate",
        "Audit Cycle 87: Target Source Placeholder URL Gate",
        "Audit Cycle 88: Selective Coverage Formula Gate",
        "Audit Cycle 89: Source-Heldout Readiness Gate",
        "Audit Cycle 90: Zero-HNFMR Numerator-Denominator Gate",
        "Audit Cycle 91: Default-Threshold Provenance Gate",
        "Audit Cycle 92: DKE Official Guide Source Gate",
        "Audit Cycle 93: Final-Upload Information Request Specificity Gate",
        "Audit Cycle 94: DKE First-Screen Scope-Fit Gate",
        "Audit Cycle 95: Keyword Scope-Fit Gate",
        "Audit Cycle 96: DKE Abstract-Length Gate",
        "Audit Cycle 97: Final Cover-Letter Pass-Path Gate",
        "Audit Cycle 98: Final Cover-Letter Generic-Variant Gate",
        "Audit Cycle 99: Final Review-Mode Vocabulary Gate",
        "Audit Cycle 100: Final Article-Type Vocabulary Gate",
        "Audit Cycle 101: Final Public-Link Placeholder Gate",
        "Audit Cycle 102: Final Review-Mode Presence Gate",
        "Audit Cycle 103: Final Source-Control Branch Gate",
        "Audit Cycle 104: Method Shortcut Wording Gate",
        "Audit Cycle 105: Selective Workload Denominator Gate",
        "Audit Cycle 106: FMR-HNFMR Stratum Gate",
        "Audit Cycle 107: Abstract FMR-HNFMR First-Screen Gate",
        "Audit Cycle 108: Highlights FMR-HNFMR First-Screen Gate",
        "Audit Cycle 109: Document-Cluster Split Overread Gate",
        "Audit Cycle 110: Current Package Source Freshness Gate",
        "Audit Cycle 111: Strict Validation Package Freshness Gate",
        "Audit Cycle 112: Reproduction Command Chain Gate",
        "Audit Cycle 113: Strict PDF Visual-Quality Gate",
        "Audit Cycle 114: DKE Biography Format and Word-Limit Gate",
        "Audit Cycle 115: Third-Party Data License and Redistribution Boundary Gate",
        "derived tables, predictions, logs, manifests, and checksums rather than raw provider files",
        "original provider terms explicitly allow redistribution",
        "source_input_manifest",
        "license boundary",
        "artifact release README template",
        "maximum 100 words",
        "editable format",
        "must not be PDF",
        "check_editable_biography_file_paths",
        "passport-type photograph",
        "author-material completion",
        "current abstract is 225 words",
        "250-word DKE preflight limit",
        "abstract-length compliance",
        "not writing quality or scientific evidence",
        "target journal name",
        "research article",
        "corresponding author name",
        "artifact release URL or DOI",
        "generic greeting and anonymous signature are absent",
        "generic-variant rejection coverage",
        "`Dear Editors:`",
        "`anonymous authors`",
        "target-specific greetings",
        "unsupported review-mode rejection coverage",
        "`single_anonymized_with_final_author_identities`",
        "`single_anonymized_author_visible_final_upload`",
        "`anonymous_review`",
        "generic `single_anonymized` value",
        "final author identities",
        "article-type rejection coverage",
        "`research_article`",
        "`review_article`",
        "`case_report`",
        "final article type",
        "public-link placeholder rejection coverage",
        "repository URL",
        "artifact release URL",
        "publication.artifact_release_url",
        "must not use a placeholder URL",
        "`example.org`",
        "`localhost`",
        "review-mode presence rejection coverage",
        "review mode must be recorded for final upload",
        "`review_mode` values",
        "metadata completeness",
        "final source-control branch rejection coverage",
        "repository_branch: \"main\"",
        "source-control branch differs from the package metadata",
        "pushed `main` branch",
        "method shortcut wording refinement",
        "threshold-only representation scoring",
        "single-score shortcuts",
        "post-hoc threshold selection",
        "rejected alternatives read as auditable design choices",
        "selective workload denominator clarification",
        r"B_{\mathrm{review}}",
        r"D_{\mathrm{review}}",
        r"R=B_{\mathrm{review}}+D_{\mathrm{review}}",
        "terminal cannot-link blocks",
        "workload denominator clarity",
        "FMR/HNFMR stratum separation",
        "FMR=0.001",
        "zero observed HNFMR means no observed false merge in the agenda-hard-negative stratum",
        "not absence of all non-identity false merges",
        "metric-stratum interpretation",
        "abstract and cover-letter FMR/HNFMR first-screen separation",
        "ordinary FMR still reported separately as 0.001",
        "first-screen metric separation",
        "same-scope comparative-ranking limits",
        "highlights FMR/HNFMR first-screen separation",
        "Open-v2 scope-bounded evidence: zero observed IAD-Risk HNFMR; FMR=0.001",
        "highlight-level metric separation",
        "document/cluster split-overread wording",
        "pair-record held-out evidence",
        "document-disjoint, cluster-disjoint, or unseen-source generalization",
        "grouped split manifests",
        "document/cluster overlap reports",
        "per-scope denominators",
        "threshold logs",
        "split-grain interpretation",
        "cannot by itself prove generalization to unseen documents, unseen clusters, or unseen sources",
        "source-root freshness validation",
        "`--source-root`",
        "current repository_commit",
        "package file main.tex differs from current source main.tex",
        "preflight packages from passing validation when generated from an older checkout",
        "rebuild the submission package",
        "strict-manuscript package freshness integration",
        "check_generated_submission_packages",
        "template-independent submission package",
        "DKE/Elsevier preflight package",
        "strict-manuscript validation failures",
        "validation coverage",
        "Git-only command chain",
        "check_reproduction_command_chain",
        "fixture rebuild validation",
        "public-release audit",
        "artifact source preflight",
        "artifact-level validation",
        "final-upload package binding",
        "full numerical reproduction requires public-source rebuilds or released artifacts",
        "strict PDF visual-quality integration",
        "check_latex_build_logs",
        "check_rendered_pdf_outputs",
        "LaTeX visual-quality gate",
        "PDF rendering gate",
        "severe overfull hbox",
        "blank pages, dark pages, or rendering failures",
        "first-screen PDF reliability",
        "Mechanism ablation acceptance protocol",
        "no-risk-gate, no-ANI-head, single-space, no-cannot-link, and post-hoc-threshold",
        "`protocol_variant`",
        "run-iad-ablation-suite",
        "post_hoc_labeled_sweep",
        "not as standalone causal evidence",
        "ablation artifact release schema validation",
        "reports/iad_ablation_suite.csv",
        "missing protocol variants",
        "post-hoc-threshold row marked as component-causality evidence",
        "same pair scope, split field, label stratum, and metric implementation",
        "prediction rows, threshold logs, same-work F1/FMR/HNFMR denominators",
        "changed pair universe, threshold-selection source, or prediction schema",
        "manual-validation artifact release schema validation",
        "reports/manual_validation_slice.csv",
        "500-1000 pair reviewed slice",
        "`manual_validation_stratum`",
        "`reviewer_blinding_confirmed`",
        "`adjudication_rationale`",
        "`pair_level_notes`",
        "`human_validation_claimed`",
        "missing required strata",
        "non-blinded reviewer rows",
        "threshold-sensitivity artifact release schema validation",
        "reports/threshold_sensitivity_grid.csv",
        "`threshold_stability_claimed`",
        "at least two predefined threshold rows",
        "exactly one `prediction_artifact_id`",
        "exactly one `prediction_file_sha256`",
        "`selected_operating_point`",
        "selection/evaluation split leakage",
        "mixed prediction-file checksums",
        "fixed-threshold false-merge control",
        "cluster-level artifact release schema validation",
        "`cluster_level_quality_claimed`",
        "reports/cluster_metric_summary.csv",
        "reports/cannot_link_audit.csv",
        "cluster assignment and pair-to-cluster trace file references",
        "cannot-link rule IDs",
        "blocked-merge indicators",
        "coverage rate",
        "mixed cluster runs or merge policies",
        "unparseable cannot-link booleans",
        "pair-level FMR and HNFMR support false-merge control",
        "bootstrap-interval artifact release schema validation",
        "`confidence_intervals_claimed`",
        "reports/bootstrap_intervals.csv",
        "required `metric_name` rows covering same-work F1, FMR, and HNFMR",
        "bootstrap method",
        "resample unit",
        "resample count",
        "confidence level",
        "interval lower and upper bounds",
        "too few resamples",
        "intervals that do not contain the point estimate",
        "Open-v2 values remain point estimates",
        "artifact release CLI discovery command consistency",
        "`python -m iad_sieve.cli --help`",
        "minimum_validation_commands",
        "README command block",
        "manifest command list",
        "release README validator",
        "Git-only reviewers can verify CLI discovery before artifact validation",
        "reviewer-facing boundary is command discoverability",
        "submission-system checklist alignment",
        "same repository checkout named by the release manifest",
        "manual submission workflow",
        "installable CLI discovery",
        "final-upload procedure consistency",
        "target-confirmation date validation",
        "`selected_author_guide_rechecked_date`",
        "`ranking_confirmation_checked_date`",
        "rejects dates later than the current validation date",
        "must not be later than the actual check date",
        "source traceability",
        "target-confirmation source URL validation",
        "`selected_author_guide_source_url`",
        "`ranking_confirmation_source_url`",
        "HTTP or HTTPS URLs",
        "source auditability",
        "target source placeholder URL validation",
        "placeholder domains",
        "example.org",
        "localhost",
        ".test",
        ".invalid",
        "must not use a placeholder URL",
        "source URL realism",
        "selective coverage formula disclosure",
        "operational throughput claims",
        "N=M+B+D",
        "automatic merge coverage",
        "block rate",
        "defer rate",
        "capacity-normalized review load",
        "same prediction artifact, threshold configuration, row scope, and denominator record",
        "workload interpretation",
        "review-cost savings",
        "manual-review capacity",
        "deferral budget",
        "source-heldout readiness wording",
        "source-generalization claims",
        "declared train, validation, and held-out source partitions",
        "source identifiers excluded from predictive features",
        "per-source denominators for same-work F1, FMR, and HNFMR",
        "command logs, split summaries, prediction checksums, and threshold records",
        "source-generalization readiness",
        "coverage gap or exploratory diagnostic",
        "readiness protocol rather than evidence of broad source generalization",
        "zero-HNFMR numerator-denominator wording",
        "zero-risk or interval-supported claims",
        "rounded HNFMR value of 0.000",
        "hard-negative false-merge numerator $=0$",
        "HNFMR denominator",
        "hard-negative label stratum",
        "evaluated split",
        "threshold source",
        "prediction-file checksum",
        "zero-observed auditability",
        "not zero-risk proof",
        "broader zero-risk, threshold-stability, or interval-supported superiority wording",
        "default-threshold provenance wording",
        "threshold-optimization claims",
        "default IAD-Risk operating point",
        "`threshold_source=predeclared_default`",
        "pre-run configuration checksum",
        "configuration timestamp or run identifier",
        "fixed before held-out scoring",
        "default-rule auditability",
        "not threshold optimality",
        "not evidence of validation-selected, optimized, or threshold-stable performance",
        "`threshold_selection_logs`",
        "`threshold_sensitivity_grid`",
        "DKE official-guide source traceability",
        "final target selection",
        "selected journal, ranking/category source, author-guide source, and live submission route",
        "`dke_official_guide_source`",
        "`dke_official_guide_source_url`",
        "`dke_official_guide_rechecked`",
        "`dke_official_guide_constraints_verified`",
        "DKE official guide URL",
        "DKE Official Guide Evidence",
        "scope and metrics, review and source files, front-matter limits, data and declarations, and author identity materials",
        "source traceability for preflight preparation",
        "not final author confirmation",
        "selected-author-guide fields",
        "ranking/category confirmation",
        "artifact URL or DOI",
        "live submission-system verification",
        "DKE final-upload information-request specificity",
        "requested external values are supplied and synchronized into metadata, cover letter, source package, and live submission system",
        "recorded DKE official-guide preflight source",
        "DKE preflight source status section",
        "final selected-author-guide fields",
        "final target-journal author confirmation",
        "final ranking/category confirmation",
        "request specificity",
        "not completed metadata",
        "`submission_metadata.yml`, `cover_letter.md`, the selected journal source package, the artifact release, and the live submission system",
        "Audit Cycle 39: Installable CLI Entry-Point Traceability Gate",
        "Audit Cycle 40: Artifact Source Preflight Gate",
        "scoring-algorithm table-density reduction",
        "full scoring and merge algorithm table",
        "fixed scoring and merge order",
        "identity, agenda, ANI, and cannot-link feature groups",
        "derived risk score",
        "merge gate combines",
        "decision, row scope, denominators, thresholds, and checksum-bound artifact rows",
        "scoring-algorithm clarity without main-text table overload",
        "supplementary scoring-merge algorithm table",
        "final-upload artifact publication binding",
        "artifact manifest publication object",
        "`artifact_release_url`",
        "`artifact_release_doi`",
        "`public_access_status`",
        "submission package is rejected",
        "publication URL or DOI differs from `submission_metadata.yml`",
        "public access status remains pending",
        "artifact-publication traceability",
        "public artifact link are aligned",
        "final-upload target-ranking gate implementation",
        "`target_preparation.ranking_confirmation_completed`",
        "ranking_confirmation_source",
        "ranking_confirmation_checked_date",
        "selected_target_author_confirmed",
        "publisher metrics remain screening signals",
        "rank/category traceability",
        "final-upload live-system verification gate implementation",
        "`upload_preparation.live_submission_system_verified`",
        "`upload_preparation.final_upload_package_verified_against_system`",
        "source-file text consistency",
        "operational traceability",
        "final-upload author-guide and template-requirement gate implementation",
        "`target_preparation.selected_author_guide_source`",
        "`target_preparation.selected_author_guide_rechecked_date`",
        "`target_preparation.selected_template_requirements_confirmed`",
        "formatting and submission-policy traceability",
        "training-trace table-density reduction",
        "full training and inference trace table",
        "schema loading preserves pair IDs and split fields",
        "supervised fitting uses the masked objective",
        "threshold fixation records",
        "decision emission records merge, block, or defer",
        "metric export binds denominators and checksums",
        "training-trace clarity without main-text table overload",
        "supplementary training-inference trace table",
        "evaluation-protocol table-density reduction",
        "full evaluation-protocol table",
        "RQ1 tests whether IAD-Risk preserves same-work matching performance",
        "RQ2 tests whether it reduces false merges on silver hard negatives",
        "RQ3 examines whether the observed behavior is consistent with the proposed risk mechanism",
        "RQ4 tests whether results remain interpretable under gold, proxy, and silver label strata",
        "evaluation-protocol clarity without main-text table overload",
        "supplementary evaluation-protocol table",
        "reproduction-level table-density reduction",
        "full reproduction-level table",
        "L0 code check and L1 fixture rebuild",
        "do not reproduce the Open-v2 numerical table",
        "L2 public-source rebuild requires independently obtained public raw files",
        "L3 result audit requires released tables, predictions, logs, manifests, checksums, and commit identifiers",
        "reproduction-level clarity without main-text table overload",
        "supplementary reproduction-level table",
        "failure-control table-density reduction",
        "full failure-control rationale table",
        "Topically close papers receive high semantic similarity",
        "Silver metadata is treated as if it were human gold",
        "Pairwise errors can contaminate clusters through transitivity",
        "Thresholds can turn a classifier into an unsafe automatic merger",
        "Proxy labels are over-interpreted",
        "failure-control clarity without main-text table overload",
        "supplementary failure-control rationale table",
        "design-alternatives table-density reduction",
        "full design-alternatives table",
        "tuning only a representation-similarity threshold",
        "relying on one supervised pair classifier",
        "using provenance as a model feature",
        "forcing every candidate into a binary merge decision",
        "selecting thresholds after test results",
        "design-alternative clarity without main-text table overload",
        "supplementary design-alternatives table",
        "risk-score rationale table-density reduction",
        "full risk score design rationale table",
        r"$p_{\mathrm{risk}}$ is a conservative upper-envelope risk proxy",
        "increases with agenda-non-identity evidence",
        "product term is not a calibrated probability",
        "Threshold transfer must be rechecked under new source distributions",
        "risk-score clarity without main-text table overload",
        "supplementary risk score design rationale table",
        "feature-head table-density reduction",
        "full feature and head specification table",
        "Transformer distances",
        "title similarity",
        "DOI/arXiv/OpenAlex identifier agreement",
        "reference Jaccard similarity",
        "different-identifier conflicts",
        "feature-head clarity without main-text table overload",
        "supplementary feature and head specification table",
        "split-control table-density reduction",
        "full split and leakage controls table",
        "Training uses only the declared training split",
        "threshold selection uses validation evidence",
        "Unordered pair leakage guard",
        "Label-stratum coverage audit",
        "Source-heldout readiness audit",
        "Topic-heldout readiness audit",
        "split-control clarity without main-text table overload",
        "supplementary split and leakage controls table",
        "decision-to-metric table-density reduction",
        "full decision-to-metric mapping table",
        "automatic merge is the positive decision",
        "block and defer are non-merge decisions",
        "deferred same-work pairs reduce recall",
        "FMR/HNFMR count only automatic merges",
        "decision-to-metric clarity without main-text table overload",
        "supplementary decision-to-metric mapping",
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
        "first-screen zero-risk overread control",
        "zero observed HNFMR rather than as wording that can be read as absolute zero risk",
        "first-screen prose",
        "no hard-negative false merge was observed",
        "does not prove zero risk under all scholarly sources",
        "L2 public-source rebuild traceability wording",
        "source_input_manifest",
        "processing_run_log",
        "output summaries",
        "chain of custody",
        "real public-source inputs",
        "alongside result tables, predictions, threshold logs, and split summaries",
        "main-text L2 provenance alignment",
        "reproduction-level table",
        "result audit trail",
        "result artifact crosswalk",
        "Data and Code Availability section now state",
        "source-to-result alignment",
        "same provenance vocabulary",
        "supplemental-only instructions",
        "schema-density reduction",
        "document-schema and pair-schema tables",
        "closest-work positioning matrix",
        "positioning matrix",
        "method-design tables",
        "operational net-benefit and version-identifier matrices",
        "Experiments table-density reduction",
        "threshold and uncertainty reporting protocol table",
        "statistical interpretation boundary table",
        "experimental interpretability without table overload",
        "result-audit table-density reduction",
        "row-level audit requirements",
        "prediction-file requirements",
        "threshold-log requirements",
        "public-source provenance requirements",
        "full result artifact crosswalk",
        "numerical-audit traceability without main-text table overload",
        "manual-validation table-density reduction",
        "final label-precision claims",
        "full manual validation boundary table",
        "full manual validation protocol table",
        "label-evidence clarity without main-text table overload",
        "human-gold wording limits",
        "mixed-scope comparison table-density reduction",
        "broad ranking claims",
        "full scope compatibility matrix",
        "row-family scopes",
        "mixed-scope interpretation clarity without main-text table overload",
        "explicit stronger-comparison boundary",
        "result-interpretation table-density reduction",
        "stronger result readings",
        "full result interpretation guardrails table",
        "row-family readings",
        "result-reading clarity without main-text table overload",
        "threshold-stability or zero-risk limits",
        "claim-evidence table-density reduction",
        "full claim-evidence boundary table",
        "IAD-Risk support",
        "repository-level reproduction",
        "claim-evidence clarity without main-text table overload",
        "supplementary claim-evidence boundary",
        "validity-threat table-density reduction",
        "full validity-threats matrix",
        "construct validity",
        "internal validity",
        "external validity",
        "conclusion validity",
        "operational validity",
        "validity-threat clarity without main-text table overload",
        "supplementary validity-threat boundary",
        "claim-interpretation table-density reduction",
        "full claim-interpretation boundary table",
        "contribution clarity",
        "writing reproducibility",
        "experimental strength",
        "evaluation completeness",
        "method design soundness",
        "claim-interpretation clarity without main-text table overload",
        "supplementary claim-interpretation boundary",
        "data/code availability table-density reduction",
        "full data and code availability boundary table",
        "L0/L1 code-level reproduction",
        "L2/L3 result-level audit",
        "data-processing commands",
        "data-processing path",
        "raw third-party source files",
        "derived evaluation artifacts",
        "data/code availability clarity without main-text table overload",
        "supplementary data/code availability boundary",
        "error-taxonomy table-density reduction",
        "full error taxonomy table",
        "same task, different contribution",
        "citation-neighborhood neighbors",
        "version or extension boundaries",
        "identifier conflicts",
        "sparse metadata cases",
        "error-taxonomy clarity without main-text table overload",
        "supplementary error taxonomy boundary",
        "mechanism-evidence table-density reduction",
        "full mechanism-evidence boundary table",
        "topical relatedness",
        "explicit risk gating",
        "component-causality claims",
        "cluster-level contamination claims",
        "mechanism-evidence clarity without main-text table overload",
        "supplementary mechanism-evidence boundary",
        "pair-to-cluster table-density reduction",
        "full pair-to-cluster evidence boundary table",
        "cluster assignments",
        "cannot-link violations",
        "pair-to-cluster trace files",
        "cluster contamination rate",
        "pair-to-cluster clarity without main-text table overload",
        "supplementary pair-to-cluster evidence boundary",
        "selective-decision coverage table-density reduction",
        "full selective-decision coverage boundary table",
        "automatic merge coverage",
        "block rate",
        "defer rate",
        "capacity-normalized review load",
        "selective-decision coverage clarity without main-text table overload",
        "supplementary selective-decision coverage boundary",
        "threshold-sensitivity table-density reduction",
        "full threshold-sensitivity evidence status table",
        "fixed operating points",
        "threshold grid",
        "per-threshold F1",
        "threshold-stable ranking",
        "threshold-sensitivity clarity without main-text table overload",
        "supplementary threshold-sensitivity evidence boundary",
        "operating-point table-density reduction",
        "full operating-point disclosure table",
        "fixed operating points",
        "post-hoc best test thresholds",
        "row family decision fields",
        "default threshold contract",
        "operating-point clarity without main-text table overload",
        "supplementary operating-point disclosure",
        "metric-formula table-density reduction",
        "full metric-formula boundary table",
        "same-work F1 denominator",
        "FMR denominator",
        "HNFMR denominator",
        "missing-label denominator rule",
        "metric-formula clarity without main-text table overload",
        "supplementary metric-formula boundary",
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
        "capacity-normalized review load",
        "validate_artifact_release.py",
        "Selective Decision Workload Boundary Gate",
        "selective-decision workload wording",
        "operational throughput or cost-saving claims",
        "Anonymous Cover-Letter Declaration Boundary Gate",
        "anonymous preflight cover-letter boundary",
        "author-provided metadata confirms originality",
        "competing-interest status",
        "author contribution",
        "generative AI declarations",
        "does not treat author declarations as finalized",
        "Preflight Metadata Declaration Placeholder Gate",
        "tracked metadata declaration placeholders",
        "statements.originality",
        "statements.author_approval",
        "statements.competing_interests",
        "structured metadata integrity",
        "Preflight Manuscript Declaration Boundary Gate",
        "anonymous preflight manuscript declaration boundary",
        "competing-interest declaration is not finalized",
        "listed authors confirm the competing-interest status",
        "declaration authority",
        "Introduction Row-Scope Comparison Boundary Gate",
        "shared Open-v2 pair schema",
        "row-scope differences between full-scope baselines and held-out IAD-Risk rows",
        "same-scope ranking implication",
        "contribution paragraph",
        "Installable CLI Entry-Point Traceability Gate",
        "Git-only command discovery and source entry-point binding",
        "`src/iad_sieve`",
        "`pyproject.toml`",
        "`iad-sieve = iad_sieve.cli:main`",
        "`python -m iad_sieve.cli --help`",
        "argparse command discovery",
        "tracked source contract",
        "Git-only reviewers can discover the CLI",
        "Artifact Source Preflight Gate",
        "source artifact completeness preflight coverage",
        "python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only",
        "checks required source artifact paths",
        "optional mapping paths",
        "without copying files",
        "artifact_population_log.jsonl",
        "source-package readiness",
        "row-level schemas",
        "validate_submission_package.py --final-upload --artifact-dir /path/to/release",
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


def check_related_work_positioning(manuscript_text: str, supplementary_text: str) -> list[str]:
    """Check whether related work includes closest-work positioning.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing related-work positioning markers.
    """
    required_main_markers = [
        r"\section{Related Work}",
        "complete positioning matrix is reported in the supplementary material",
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
        "decision semantics assigned to relatedness",
        "positive, negative, or deferred",
        "not as a direct merge decision",
        "connects IAD-Bench to HNFMR",
    ]
    required_supplement_markers = [
        r"\section{Closest-Work Positioning}",
        r"\label{tab:closest-work-positioning}",
        "Positioning against the closest lines of work",
        "Line of work",
        "Primary optimization target",
        "Limitation for scholarly deduplication",
        "IAD-Risk distinction",
        "End-to-end entity resolution systems",
        "Neural entity matching",
        "Scientific document representations",
        "Open scholarly metadata benchmarks",
        "false-merge risk gates",
        "gold, proxy, and silver strata",
    ]
    errors = [
        f"related work positioning missing main-text marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    errors.extend(
        f"related work positioning missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in supplementary_text
    )
    return errors


def check_error_taxonomy(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether the mechanism section includes error taxonomy boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing error-taxonomy markers.
    """
    required_main_markers = [
        r"\section{Mechanism and Error Analysis}",
        "full error taxonomy table is reported in the supplementary material",
        "same task, different contribution",
        "citation-neighborhood neighbors",
        "version or extension boundaries",
        "identifier conflicts",
        "sparse metadata cases",
        "diagnostic rather than a measured error distribution",
        "per-category annotations and adjudication logs",
        "human judgment beyond metadata-derived silver evidence",
    ]
    required_supplement_markers = [
        r"\section{Error Taxonomy Boundary}",
        r"\label{tab:error-taxonomy}",
        "Error taxonomy for identity-agenda confusion",
        "Same task, different contribution",
        "Citation-neighborhood neighbor",
        "Version or extension boundary",
        "Identifier conflict",
        "Sparse metadata",
        "Stronger audit evidence",
    ]
    errors = [
        f"error taxonomy missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"error taxonomy missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


def check_mechanism_evidence_boundary(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether mechanism evidence boundaries remain complete after table migration.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing mechanism-evidence markers.
    """
    required_main_markers = [
        r"\section{Mechanism and Error Analysis}",
        "full mechanism-evidence boundary table is reported in the supplementary material",
        "topical relatedness creates merge risk",
        "explicit risk gating supports the reported Open-v2 contract",
        "component-causality claims require ablations",
        "cluster-level contamination claims require sufficient cannot-link coverage",
        "cluster-level artifact audits",
    ]
    required_supplement_markers = [
        r"\section{Mechanism Evidence Boundary}",
        r"\label{tab:mechanism-evidence}",
        "Mechanism evidence and interpretation boundary",
        "Mechanism question",
        "Current evidence",
        "Interpretation boundary",
        "Does topical relatedness create merge risk?",
        "Does explicit risk gating suppress hard-negative merges?",
        "Is the gain caused by each IAD-Risk component?",
        "Can cluster-level contamination be eliminated?",
    ]
    errors = [
        f"mechanism evidence boundary missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"mechanism evidence boundary missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    return errors


def check_validity_threats(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether threats to validity state concrete reviewer-facing boundaries.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing validity-threat markers.
    """
    required_main_markers = [
        r"\section{Threats to Validity}",
        "full validity-threats matrix is reported in the supplementary material",
        "construct validity is bounded by label strata",
        "internal validity is bounded by threshold and split separation",
        "external validity is bounded by the current source mix",
        "conclusion validity is bounded by the absence of complete causal ablations",
        "reproducibility is bounded by source and artifact availability",
        "operational validity is bounded by the gap between pair-level decisions and cluster-level deployment",
        "not turn proxy or silver evidence into human-adjudicated truth",
        "full numeric audit requires L2/L3 artifacts",
    ]
    required_supplement_markers = [
        r"\section{Validity Threats Boundary}",
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
        "source-heldout generalization is not established by the current package",
        "declared source partitions",
        "per-source denominators",
        "prediction checksums",
        "source-level split summaries",
        "pair-level metrics do not by themselves establish cluster-level deployment quality",
        "cluster assignments",
        "cannot-link coverage",
        "cluster contamination rate",
    ]
    errors = [
        f"validity threats missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"validity threats missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
    errors.extend(
        f"Limitations missing cluster-level boundary marker: {marker}"
        for marker in required_limitation_markers
        if marker not in manuscript_text
    )
    return errors


def check_claim_interpretation_boundary(manuscript_text: str, supplementary_text: str = "") -> list[str]:
    """Check whether the main manuscript contains a formal claim-interpretation boundary.

    参数:
        manuscript_text: Main LaTeX manuscript source.
        supplementary_text: Supplementary LaTeX source.

    返回:
        list[str]: Error messages for missing claim-interpretation boundary markers.
    """
    required_main_markers = [
        r"\section{Claim Interpretation Boundary}",
        "full claim-interpretation boundary table is reported in the supplementary material",
        "contribution clarity is tied to the IAD-Bench contract",
        "identity-agenda confusion",
        "HNFMR as a false-merge safety problem",
        "writing reproducibility is limited to code-level checks",
        "fixture rebuilds",
        "schema validation",
        "artifact-release preparation",
        "experimental strength is limited to the Open-v2 evidence snapshot",
        "evaluation completeness is limited by artifact-backed ablations",
        "threshold grids",
        "manual-validation slice",
        "method design soundness remains bounded by source-heldout validation",
        "topic-heldout checks",
        "failure-case analysis",
    ]
    required_supplement_markers = [
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
        f"claim interpretation boundary missing manuscript marker: {marker}"
        for marker in required_main_markers
        if marker not in manuscript_text
    ]
    evidence_text = supplementary_text or manuscript_text
    errors.extend(
        f"claim interpretation boundary missing supplementary marker: {marker}"
        for marker in required_supplement_markers
        if marker not in evidence_text
    )
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
        if "zero observed" in highlight and "HNFMR" in highlight and "FMR=0.001" not in highlight:
            errors.append(
                "zero-observed HNFMR highlight must include ordinary FMR=0.001 boundary: "
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
    required_keywords = ["hard-negative false-merge rate", "scholarly data integration"]
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


def load_submission_package_validator():
    """Load the submission-package validator used by manuscript validation.

    参数:
        无。

    返回:
        module: Loaded validate_submission_package module.

    异常:
        ImportError: Raised when the validator module cannot be loaded.
    """
    validator_path = ROOT / "scripts" / "validate_submission_package.py"
    spec = importlib.util.spec_from_file_location("validate_submission_package", validator_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load submission package validator: {validator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_latex_warning_checker():
    """Load the LaTeX warning checker used by strict manuscript validation.

    参数:
        无。

    返回:
        module: Loaded check_latex_warnings module.

    异常:
        ImportError: Raised when the checker module cannot be loaded.
    """
    checker_path = ROOT / "scripts" / "check_latex_warnings.py"
    spec = importlib.util.spec_from_file_location("check_latex_warnings", checker_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load LaTeX warning checker: {checker_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_latex_build_logs(checker_module=None) -> list[str]:
    """Check generated LaTeX logs for submission-blocking warnings.

    参数:
        checker_module: Optional preloaded check_latex_warnings module.

    返回:
        list[str]: Error messages for missing logs or severe LaTeX warnings.
    """
    try:
        checker = checker_module or load_latex_warning_checker()
    except Exception as exc:  # noqa: BLE001
        return [f"LaTeX warning checker could not be loaded: {exc}"]
    try:
        return [f"LaTeX visual-quality gate: {error}" for error in checker.check_log_files(checker.DEFAULT_LOGS)]
    except Exception as exc:  # noqa: BLE001
        return [f"LaTeX visual-quality gate failed: {exc}"]


def load_pdf_rendering_checker():
    """Load the PDF rendering checker used by strict manuscript validation.

    参数:
        无。

    返回:
        module: Loaded check_pdf_rendering module.

    异常:
        ImportError: Raised when the checker module cannot be loaded.
    """
    checker_path = ROOT / "scripts" / "check_pdf_rendering.py"
    spec = importlib.util.spec_from_file_location("check_pdf_rendering", checker_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load PDF rendering checker: {checker_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_rendered_pdf_outputs(checker_module=None) -> list[str]:
    """Check generated PDFs by rendering sampled pages.

    参数:
        checker_module: Optional preloaded check_pdf_rendering module.

    返回:
        list[str]: Error messages for missing render tools, blank pages, or failed rendering.
    """
    try:
        checker = checker_module or load_pdf_rendering_checker()
    except Exception as exc:  # noqa: BLE001
        return [f"PDF rendering checker could not be loaded: {exc}"]
    try:
        return [f"PDF rendering gate: {error}" for error in checker.check_pdf_files(checker.DEFAULT_PDFS)]
    except Exception as exc:  # noqa: BLE001
        return [f"PDF rendering gate failed: {exc}"]


def check_generated_submission_packages(manuscript_root: Path = ROOT, validator_module=None) -> list[str]:
    """Check generated submission packages when they exist.

    参数:
        manuscript_root: Manuscript source root.
        validator_module: Optional preloaded submission-package validator module.

    返回:
        list[str]: Error messages for stale generated packages.
    """
    package_targets = [
        (
            "template-independent submission package",
            manuscript_root / "build" / "submission_package",
            manuscript_root / "build" / "iad-risk-submission-package.zip",
            False,
        ),
        (
            "DKE/Elsevier preflight package",
            manuscript_root / "build" / "dke_preflight_package",
            manuscript_root / "build" / "iad-risk-dke-preflight-package.zip",
            True,
        ),
    ]
    existing_targets = [
        target
        for target in package_targets
        if target[1].exists() or target[2].exists()
    ]
    if not existing_targets:
        return []
    try:
        validator = validator_module or load_submission_package_validator()
    except Exception as exc:  # noqa: BLE001
        return [f"submission package validator could not be loaded: {exc}"]
    errors: list[str] = []
    for label, package_dir, zip_path, dke_preflight in existing_targets:
        validation_errors = validator.validate_submission_package(
            package_dir,
            zip_path,
            dke_preflight=dke_preflight,
            source_root=manuscript_root,
        )
        errors.extend(f"{label}: {error}" for error in validation_errors)
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
        "anonymous preflight cover letter",
        "does not treat author declarations as finalized",
        "author-provided metadata must confirm originality",
        "author approval",
        "competing-interest status",
        "funding",
        "author contribution",
        "permission",
        "generative AI declarations",
        "raw third-party data",
        "full experimental outputs are not redistributed in Git",
        "artifact-release instructions",
        "manifests and checksums",
        "does not claim cluster-level deployment quality without cluster artifacts",
        "DKE-style data and knowledge engineering editorial screen",
        "database-oriented scholarly data integration",
        "knowledge engineering for scholarly records",
        "reproducible data-processing contracts",
        "does not finalize the target journal",
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
    premature_declaration_markers = [
        "All listed authors have approved the submitted version.",
        "The authors declare no competing interests.",
    ]
    errors.extend(
        f"cover letter contains premature final declaration: {marker}"
        for marker in premature_declaration_markers
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
        "zero observed IAD-Risk HNFMR",
        "FMR=0.001",
    ]
    errors: list[str] = []
    for marker in highlight_required_markers:
        if marker not in highlights_text:
            errors.append(f"highlights missing scoped quantitative evidence marker: {marker}")
    cover_letter_quantitative_markers = [
        "HNFMR 0.790--0.999",
        "zero observed HNFMR",
        "ordinary FMR still reported separately as 0.001",
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
                "zero observed HNFMR",
                "ordinary FMR still reported separately as 0.001",
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
                "zero observed HNFMR",
                "ordinary FMR still reported separately as 0.001",
                "does not claim broad method superiority",
                "raw third-party data and full experimental outputs are not redistributed in Git",
                "DKE-style data and knowledge engineering editorial screen",
                "does not finalize the target journal",
            ],
        ),
        "highlights": (
            highlights_text,
            [
                "Identity-agenda confusion",
                "data/knowledge-engineering",
                "IAD-Risk",
                "IAD-Bench",
                "Open-v2 scope-bounded evidence",
                "zero observed IAD-Risk HNFMR",
                "FMR=0.001",
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
                "scholarly data integration",
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
        "dke_official_guide_source: \"ScienceDirect Data & Knowledge Engineering guide for authors\"",
        "dke_official_guide_source_url: \"https://www.sciencedirect.com/journal/data-and-knowledge-engineering/publish/guide-for-authors\"",
        "dke_official_guide_rechecked: \"2026-06-19\"",
        "dke_official_guide_constraints_verified: true",
        "selected_author_guide_source: \"\"",
        "selected_author_guide_source_url: \"\"",
        "selected_author_guide_rechecked_date: \"\"",
        "selected_template_requirements_confirmed: false",
        "ranking_confirmation_required_before_final_upload: true",
        "ranking_confirmation_completed: false",
        "ranking_confirmation_source: \"\"",
        "ranking_confirmation_source_url: \"\"",
        "ranking_confirmation_checked_date: \"\"",
        "selected_target_requires_author_confirmation: true",
        "selected_target_author_confirmed: false",
        "dke_preflight:",
        "review_model: \"single_anonymized\"",
        "abstract_word_limit_checked: true",
        "keyword_count_checked: true",
        "highlight_count_and_length_checked: true",
        "elsarticle_conversion_pending_author_confirmation: true",
        "author_biography_and_photo_required_before_upload: true",
        "artifact_release_required_before_upload: true",
        "author_identity_materials:",
        "biography_files: []",
        "photograph_files: []",
        "author_identity_materials_verified: false",
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
    errors = [f"submission metadata missing marker: {marker}" for marker in required_markers if marker not in metadata_text]
    is_preflight_metadata = (
        "authors: []" in metadata_text
        or scalar_value(metadata_text, "author_metadata_completed").lower() != "true"
        or scalar_value(metadata_text, "target_journal_selected").lower() != "true"
    )
    if is_preflight_metadata:
        statements = parse_mapping_section(metadata_text, "statements")
        for field_name in ["originality", "author_approval", "competing_interests"]:
            if statements.get(field_name, ""):
                errors.append(
                    "submission metadata preflight declaration must remain empty until final upload: "
                    f"statements.{field_name}"
                )
    return errors


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
    latex_build_script_path = ROOT / "scripts" / "build_latex_pdf.sh"
    latex_build_script_text = (
        latex_build_script_path.read_text(encoding="utf-8") if latex_build_script_path.exists() else ""
    )
    elsevier_builder_path = ROOT / "scripts" / "build_elsevier_draft.py"
    elsevier_builder_text = elsevier_builder_path.read_text(encoding="utf-8") if elsevier_builder_path.exists() else ""
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
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    pyproject_text = pyproject_path.read_text(encoding="utf-8") if pyproject_path.exists() else ""
    cli_entrypoint_path = PROJECT_ROOT / "src" / "iad_sieve" / "cli.py"
    cli_entrypoint_text = cli_entrypoint_path.read_text(encoding="utf-8") if cli_entrypoint_path.exists() else ""
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
    errors.extend(check_iad_bench_supplementary_schema_tables(supplementary_text))
    errors.extend(check_method_feature_contract(manuscript_text, supplementary_text))
    errors.extend(check_training_objective_masking(manuscript_text))
    errors.extend(check_risk_score_design_rationale(manuscript_text, supplementary_text))
    errors.extend(check_risk_calibration_overclaims(manuscript_text))
    errors.extend(check_method_cluster_overclaims(manuscript_text))
    errors.extend(check_operational_net_benefit_boundary(manuscript_text))
    errors.extend(check_version_identifier_policy(manuscript_text))
    errors.extend(check_method_design_supplementary_boundaries(supplementary_text))
    errors.extend(check_method_pipeline_figure(manuscript_text))
    errors.extend(check_scoring_merge_algorithm(manuscript_text, supplementary_text))
    errors.extend(check_design_alternative_boundaries(manuscript_text, supplementary_text))
    errors.extend(check_failure_control_rationale(manuscript_text, supplementary_text))
    errors.extend(check_related_work_positioning(manuscript_text, supplementary_text))
    errors.extend(check_error_taxonomy(manuscript_text, supplementary_text))
    errors.extend(check_validity_threats(manuscript_text, supplementary_text))
    errors.extend(check_claim_interpretation_boundary(manuscript_text, supplementary_text))
    errors.extend(check_declaration_statements(manuscript_text))
    errors.extend(check_data_code_availability_boundary(manuscript_text, supplementary_text))
    errors.extend(check_reproduction_command_chain(manuscript_text))
    errors.extend(check_reproduction_levels_boundary(manuscript_text, supplementary_text))
    errors.extend(check_evaluation_protocol_boundary(manuscript_text, supplementary_text))
    errors.extend(check_cli_entrypoint_contract(pyproject_text, cli_entrypoint_text))
    errors.extend(check_operating_point_disclosure(manuscript_text, supplementary_text))
    errors.extend(check_selective_decision_coverage_boundary(manuscript_text, supplementary_text))
    errors.extend(check_pair_cluster_evidence_boundary(manuscript_text, supplementary_text))
    errors.extend(check_decision_metric_mapping(manuscript_text, supplementary_text))
    errors.extend(check_metric_formula_boundary(manuscript_text, supplementary_text))
    errors.extend(check_threshold_uncertainty_reporting(manuscript_text))
    errors.extend(check_statistical_interpretation_boundary(manuscript_text))
    errors.extend(check_ablation_acceptance_boundary(manuscript_text))
    errors.extend(check_threshold_sensitivity_status(manuscript_text, supplementary_text))
    errors.extend(check_baseline_scope_alignment(manuscript_text))
    errors.extend(check_baseline_inclusion_rationale(manuscript_text))
    errors.extend(check_baseline_fairness_controls(manuscript_text))
    errors.extend(check_baseline_supplementary_tables(supplementary_text))
    errors.extend(check_result_interpretation_guardrails(manuscript_text, supplementary_text))
    errors.extend(check_openv2_result_table_scope_labels(manuscript_text))
    errors.extend(check_manual_validation_boundary(manuscript_text))
    errors.extend(check_split_leakage_controls(manuscript_text, supplementary_text))
    errors.extend(check_scope_compatibility(manuscript_text, supplementary_text))
    errors.extend(check_extended_protocol_boundary(manuscript_text))
    errors.extend(check_environment_setup(supplementary_text))
    errors.extend(check_public_source_rebuild_audit_boundary(supplementary_text))
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
    errors.extend(check_latex_build_scripts(latex_build_script_text, elsevier_builder_text))
    errors.extend(check_submission_system_checklist(submission_system_checklist_text))
    errors.extend(check_reviewer_readiness_audit(reviewer_readiness_audit_text))
    errors.extend(check_manual_validation_protocol(supplementary_text))
    errors.extend(check_reviewer_evidence_gate(supplementary_text))
    errors.extend(check_experiment_reporting_supplementary_boundaries(supplementary_text))
    errors.extend(check_result_claim_boundary(manuscript_text, supplementary_text))
    errors.extend(check_mechanism_evidence_boundary(manuscript_text, supplementary_text))
    errors.extend(check_highlights(highlights_text))
    errors.extend(check_keywords(keywords_text))
    errors.extend(check_elsevier_draft_source(manuscript_text, keywords_text, elsevier_draft_source_text))
    errors.extend(check_generated_submission_packages(ROOT))
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
        "zero observed HNFMR",
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
    if args.strict_latex:
        errors.extend(check_latex_build_logs())
        errors.extend(check_rendered_pdf_outputs())

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
