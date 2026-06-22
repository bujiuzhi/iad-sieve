"""Shared checks for final-upload submission metadata."""

from __future__ import annotations

import ast
import datetime as dt
import re
from urllib.parse import unquote, urlparse


FINAL_UPLOAD_BLOCKED_MARKERS = {
    'target_journal: ""': "target journal is empty",
    "target_journal_template_bound: false": "target journal template is not bound",
    'selected_author_guide_source_url: ""': "selected author guide source URL is empty",
    'ranking_confirmation_source_url: ""': "ranking/category confirmation source URL is empty",
    "authors: []": "author list is empty",
    'name: ""': "corresponding author name is empty",
    'affiliation: ""': "corresponding author affiliation is empty",
    'email: ""': "corresponding author email is empty",
    "target_journal_selected: false": "target journal checklist item is incomplete",
    "article_type_confirmed: false": "article type checklist item is incomplete",
    "review_mode_confirmed: false": "review mode checklist item is incomplete",
    "target_journal_template_applied: false": "target journal template checklist item is incomplete",
    "author_metadata_completed: false": "author metadata checklist item is incomplete",
    "author_biographies_and_photos_ready: false": "author biographies and photographs checklist item is incomplete",
    "corresponding_author_completed: false": "corresponding author checklist item is incomplete",
    "funding_statement_text_ready: false": "funding statement text checklist item is incomplete",
    "contribution_statement_complete: false": "author contribution statement checklist item is incomplete",
    "permissions_statement_complete: false": "permissions statement checklist item is incomplete",
    "generative_ai_declaration_complete: false": "generative AI declaration checklist item is incomplete",
    "manuscript_pdf_rebuilt_after_template: false": "manuscript PDF rebuild checklist item is incomplete",
    "supplementary_pdf_rebuilt_after_template: false": "supplementary PDF rebuild checklist item is incomplete",
    "submission_system_files_verified: false": "submission system file checklist item is incomplete",
    "first_screen_claim_lockdown_confirmed: false": "first-screen claim lockdown checklist item is incomplete",
    "artifact_release_prepared_or_linked: false": "artifact release checklist item is incomplete",
}
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
URL_PATTERN = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
DOI_PATTERN = re.compile(r"^10\.[^\s/]+/[^\s]+$", re.IGNORECASE)
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PLACEHOLDER_URL_HOSTS = {
    "example",
    "example.com",
    "example.net",
    "example.org",
    "example.edu",
    "invalid",
    "localhost",
    "test",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
}
PLACEHOLDER_URL_SUFFIXES = (
    ".example",
    ".example.com",
    ".example.edu",
    ".example.net",
    ".example.org",
    ".invalid",
    ".localhost",
    ".test",
)
COMMIT_PLACEHOLDERS = {
    "<commit>",
    "commit",
    "fill-with-release-commit",
    "tbd",
    "todo",
}
AUTHOR_VISIBLE_REVIEW_JOURNALS = {
    "data & knowledge engineering": "Data & Knowledge Engineering",
    "information systems": "Information Systems",
    "scientometrics": "Scientometrics",
}
AUTHOR_VISIBLE_FINAL_REVIEW_MODES = {
    "single_anonymized_author_visible_final_upload",
    "single_anonymized_with_final_author_identities",
    "single_anonymized_review_with_final_author_identities",
}
ELSEVIER_TARGET_JOURNALS = {
    "data & knowledge engineering",
    "information systems",
}
CREDIT_AUTHOR_ROLES = {
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
}

RESEARCH_DATA_STATEMENT_REQUIRED_TARGETS = {
    "data & knowledge engineering": "Data & Knowledge Engineering",
    "information systems": "Information Systems",
}
RESEARCH_DATA_STATEMENT_RAW_DATA_TERMS = (
    "raw third-party data",
    "raw third party data",
)
RESEARCH_DATA_STATEMENT_REDISTRIBUTION_BOUNDARY_TERMS = (
    "not redistributed",
    "not distributed",
    "not included",
    "not provided",
    "not shared",
    "not committed",
    "excluded",
    "original provider",
    "provider license",
    "provider licenses",
    "provider terms",
    "license boundary",
)
RESEARCH_DATA_STATEMENT_REPOSITORY_ONLY_TERMS = (
    "git",
    "git-only",
    "github",
    "repository",
)
DKE_ELSEVIER_FILE_REQUIREMENT_ERROR = "DKE/Elsevier final upload requires DKE/Elsevier source and PDF files"
FINAL_UPLOAD_REPOSITORY_BRANCH = "main"
FINAL_UPLOAD_TRUE_FIELDS = {
    "target_journal_template_bound": "target journal template is not bound",
    "target_journal_selected": "target journal checklist item is incomplete",
    "article_type_confirmed": "article type checklist item is incomplete",
    "review_mode_confirmed": "review mode checklist item is incomplete",
    "target_journal_template_applied": "target journal template checklist item is incomplete",
    "author_metadata_completed": "author metadata checklist item is incomplete",
    "author_biographies_and_photos_ready": "author biographies and photographs checklist item is incomplete",
    "corresponding_author_completed": "corresponding author checklist item is incomplete",
    "funding_statement_text_ready": "funding statement text checklist item is incomplete",
    "contribution_statement_complete": "author contribution statement checklist item is incomplete",
    "permissions_statement_complete": "permissions statement checklist item is incomplete",
    "generative_ai_declaration_complete": "generative AI declaration checklist item is incomplete",
    "manuscript_pdf_rebuilt_after_template": "manuscript PDF rebuild checklist item is incomplete",
    "supplementary_pdf_rebuilt_after_template": "supplementary PDF rebuild checklist item is incomplete",
    "submission_system_files_verified": "submission system file checklist item is incomplete",
    "live_submission_system_verified": "live submission system verification is incomplete",
    "final_upload_package_verified_against_system": "final upload package verification against live system is incomplete",
    "first_screen_claim_lockdown_confirmed": "first-screen claim lockdown checklist item is incomplete",
    "artifact_release_prepared_or_linked": "artifact release checklist item is incomplete",
}
ARTICLE_TYPE_COVER_LETTER_MARKERS = {
    "research_article": "research article",
}
FINAL_UPLOAD_ARTICLE_TYPES = set(ARTICLE_TYPE_COVER_LETTER_MARKERS)
DKE_EDITABLE_BIOGRAPHY_EXTENSIONS = {".doc", ".docx", ".rtf", ".txt", ".md", ".tex"}
DKE_PHOTOGRAPH_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
ELSEVIER_DECLARATION_FILE_EXTENSIONS = {".doc", ".docx"}
FINAL_UPLOAD_COVER_LETTER_UNRESOLVED_MARKERS = {
    "anonymous draft cover letter": "cover letter still describes an anonymous draft",
    "anonymous preflight": "cover letter still describes an anonymous preflight package",
    "preflight cover letter": "cover letter still describes a preflight cover letter",
    "submission-planning boundaries": "cover letter still describes submission-planning boundaries",
    "scope-fit note is preparatory": "cover letter still contains a preparatory scope-fit note",
    "must be replaced after author confirmation": "cover letter still contains replacement instructions",
}
FINAL_UPLOAD_COVER_LETTER_EVIDENCE_BOUNDARY_MARKERS = {
    "open-v2": "cover letter missing Open-v2 evidence boundary",
    "scope-bounded mechanism evidence": "cover letter missing scope-bounded mechanism wording",
    "same-scope comparative ranking": "cover letter missing same-scope ranking boundary",
    "confidence intervals": "cover letter missing confidence-interval boundary",
    "statistical significance": "cover letter missing statistical-significance boundary",
    "model-ranking claims": "cover letter missing model-ranking claim boundary",
}
FINAL_UPLOAD_COVER_LETTER_PUBLIC_SOURCE_BOUNDARY_MARKERS = {
    "public-source commands": "cover letter missing public-source command boundary",
    "reconstruction code paths": "cover letter missing reconstruction-code-path boundary",
    "frozen source snapshots": "cover letter missing frozen-source-snapshot boundary",
    "exact open-v2 numerical reproduction": "cover letter missing exact Open-v2 reproduction boundary",
    "recorded acquisition dates or versions": "cover letter missing acquisition-date-or-version boundary",
    "input checksums": "cover letter missing input-checksum boundary",
    "processing logs": "cover letter missing processing-log boundary",
    "released derived artifacts": "cover letter missing released-derived-artifact boundary",
    "live api calls or changed public dumps": "cover letter missing live-source-change boundary",
}


def strip_yaml_value(value: str) -> str:
    """Normalize a simple YAML scalar value.

    参数:
        value: Raw value text after a colon.

    返回:
        str: Unquoted scalar value.
    """
    cleaned_value = value.strip()
    if cleaned_value.startswith('"') and cleaned_value.endswith('"') and len(cleaned_value) >= 2:
        return cleaned_value[1:-1]
    if cleaned_value.startswith("'") and cleaned_value.endswith("'") and len(cleaned_value) >= 2:
        return cleaned_value[1:-1]
    return cleaned_value


def parse_key_value_line(line: str) -> tuple[str, str] | None:
    """Parse a simple YAML key-value line.

    参数:
        line: YAML line text.

    返回:
        tuple[str, str] | None: Key and normalized value, or None when not a key-value line.
    """
    if ":" not in line:
        return None
    key, value = line.split(":", 1)
    key = key.strip()
    if not key:
        return None
    return key, strip_yaml_value(value)


def section_lines(metadata_text: str, section_name: str) -> list[str]:
    """Extract indented lines under a top-level YAML section.

    参数:
        metadata_text: Submission metadata YAML text.
        section_name: Top-level section name.

    返回:
        list[str]: Section body lines.
    """
    lines = metadata_text.splitlines()
    section_header = f"{section_name}:"
    for index, line in enumerate(lines):
        if line.strip() == section_header:
            body_lines: list[str] = []
            for body_line in lines[index + 1 :]:
                if body_line and not body_line.startswith((" ", "\t")):
                    break
                body_lines.append(body_line)
            return body_lines
    return []


def scalar_value(metadata_text: str, key_name: str) -> str:
    """Extract the first simple scalar value for a YAML key.

    参数:
        metadata_text: Submission metadata YAML text.
        key_name: Key name to locate.

    返回:
        str: Normalized scalar value, or an empty string when absent.
    """
    pattern = re.compile(rf"^\s*{re.escape(key_name)}:\s*(.*)$", re.MULTILINE)
    match = pattern.search(metadata_text)
    if match is None:
        return ""
    return strip_yaml_value(match.group(1))


def parse_mapping_section(metadata_text: str, section_name: str) -> dict[str, str]:
    """Parse a simple top-level mapping section.

    参数:
        metadata_text: Submission metadata YAML text.
        section_name: Top-level section name.

    返回:
        dict[str, str]: Parsed key-value pairs.
    """
    mapping: dict[str, str] = {}
    for line in section_lines(metadata_text, section_name):
        parsed = parse_key_value_line(line)
        if parsed is None:
            continue
        key, value = parsed
        mapping[key] = value
    return mapping


def section_key_has_value(metadata_text: str, section_name: str, key_name: str) -> bool:
    """Check whether a section key has a scalar or sequence value.

    参数:
        metadata_text: Submission metadata YAML text.
        section_name: Top-level section name.
        key_name: Key name to inspect inside the section.

    返回:
        bool: True when the key contains at least one non-empty value.
    """
    lines = section_lines(metadata_text, section_name)
    for index, line in enumerate(lines):
        stripped_line = line.strip()
        if not stripped_line.startswith(f"{key_name}:"):
            continue
        inline_value = strip_yaml_value(stripped_line.split(":", 1)[1])
        if inline_value and inline_value != "[]":
            return True
        key_indent = len(line) - len(line.lstrip(" \t"))
        for following_line in lines[index + 1 :]:
            following_stripped = following_line.strip()
            if not following_stripped:
                continue
            following_indent = len(following_line) - len(following_line.lstrip(" \t"))
            if following_indent <= key_indent and ":" in following_stripped:
                break
            if following_stripped.startswith("- "):
                item_value = strip_yaml_value(following_stripped[2:])
                if item_value:
                    return True
        return False
    return False


def parse_section_sequence_values(metadata_text: str, section_name: str, key_name: str) -> list[str]:
    """Parse simple inline or block sequence values from a metadata section.

    参数:
        metadata_text: Submission metadata YAML text.
        section_name: Top-level section name.
        key_name: Sequence key to parse inside the section.

    返回:
        list[str]: Parsed non-empty sequence item values.
    """
    lines = section_lines(metadata_text, section_name)
    for index, line in enumerate(lines):
        stripped_line = line.strip()
        if not stripped_line.startswith(f"{key_name}:"):
            continue
        inline_value = stripped_line.split(":", 1)[1].strip()
        if inline_value and inline_value != "[]":
            try:
                parsed_value = ast.literal_eval(inline_value)
            except (SyntaxError, ValueError):
                parsed_value = strip_yaml_value(inline_value)
            if isinstance(parsed_value, list):
                return [str(item).strip() for item in parsed_value if str(item).strip()]
            parsed_scalar = str(parsed_value).strip()
            return [parsed_scalar] if parsed_scalar else []

        values: list[str] = []
        key_indent = len(line) - len(line.lstrip(" \t"))
        for following_line in lines[index + 1 :]:
            following_stripped = following_line.strip()
            if not following_stripped:
                continue
            following_indent = len(following_line) - len(following_line.lstrip(" \t"))
            if following_indent <= key_indent and ":" in following_stripped:
                break
            if following_stripped.startswith("- "):
                item_value = strip_yaml_value(following_stripped[2:])
                if item_value:
                    values.append(item_value)
        return values
    return []


def check_non_placeholder_url(value: str, field_label: str) -> list[str]:
    """Validate a public-looking HTTP/HTTPS URL and reject placeholder hosts.

    参数:
        value: URL string supplied for a final-upload source field.
        field_label: Human-readable field label for error messages.

    返回:
        list[str]: Error messages for invalid or placeholder URLs.
    """
    if URL_PATTERN.fullmatch(value) is None:
        return [f"{field_label} is invalid"]
    parsed_url = urlparse(value)
    if parsed_url.scheme.lower() not in {"http", "https"} or not parsed_url.hostname:
        return [f"{field_label} is invalid"]
    host = parsed_url.hostname.lower().rstrip(".")
    if host in PLACEHOLDER_URL_HOSTS or host.endswith(PLACEHOLDER_URL_SUFFIXES):
        return [f"{field_label} must not use a placeholder URL"]
    return []


def check_non_future_date(value: str, field_label: str) -> list[str]:
    """Validate an ISO date and reject dates later than today.

    参数:
        value: Date string in YYYY-MM-DD format.
        field_label: Human-readable field label used in error messages.

    返回:
        list[str]: Error messages for invalid or future dates.
    """
    if DATE_PATTERN.fullmatch(value) is None:
        return [f"{field_label} is invalid"]
    try:
        parsed_date = dt.date.fromisoformat(value)
    except ValueError:
        return [f"{field_label} is invalid"]
    if parsed_date > dt.date.today():
        return [f"{field_label} must not be in the future"]
    return []


def parse_author_rows(metadata_text: str) -> list[dict[str, str]]:
    """Parse author rows from submission metadata.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[dict[str, str]]: Parsed author rows.
    """
    rows: list[dict[str, str]] = []
    current_row: dict[str, str] | None = None
    for raw_line in section_lines(metadata_text, "authors"):
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        if stripped_line.startswith("- "):
            if current_row is not None:
                rows.append(current_row)
            current_row = {}
            parsed = parse_key_value_line(stripped_line[2:])
            if parsed is not None:
                key, value = parsed
                current_row[key] = value
            continue
        if current_row is None:
            continue
        parsed = parse_key_value_line(stripped_line)
        if parsed is not None:
            key, value = parsed
            current_row[key] = value
    if current_row is not None:
        rows.append(current_row)
    return rows


def parse_contribution_role_rows(metadata_text: str) -> list[dict[str, str]]:
    """Parse structured author contribution role rows from submission metadata.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[dict[str, str]]: Parsed contribution rows under author_contributions.roles.
    """
    rows: list[dict[str, str]] = []
    current_row: dict[str, str] | None = None
    in_roles = False
    for raw_line in section_lines(metadata_text, "author_contributions"):
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        if stripped_line == "roles:":
            in_roles = True
            continue
        if not in_roles:
            continue
        if stripped_line.startswith("- "):
            if current_row is not None:
                rows.append(current_row)
            current_row = {}
            parsed = parse_key_value_line(stripped_line[2:])
            if parsed is not None:
                key, value = parsed
                current_row[key] = value
            continue
        if current_row is None:
            continue
        parsed = parse_key_value_line(stripped_line)
        if parsed is not None:
            key, value = parsed
            current_row[key] = value
    if current_row is not None:
        rows.append(current_row)
    return rows


def check_email(value: str, label: str) -> list[str]:
    """Check whether an email value is present and syntactically valid.

    参数:
        value: Email value.
        label: Diagnostic field label.

    返回:
        list[str]: Error messages.
    """
    if not value:
        return [f"{label} email is missing"]
    if EMAIL_PATTERN.fullmatch(value) is None:
        return [f"{label} email is invalid"]
    return []


def is_valid_orcid_checksum(value: str) -> bool:
    """Validate an ORCID checksum with ISO 7064 11,2.

    参数:
        value: Hyphenated ORCID value.

    返回:
        bool: True when the final checksum character is valid.
    """
    compact_value = value.replace("-", "")
    if len(compact_value) != 16:
        return False
    total = 0
    for character in compact_value[:15]:
        if not character.isdigit():
            return False
        total = (total + int(character)) * 2
    remainder = total % 11
    checksum_value = (12 - remainder) % 11
    expected_character = "X" if checksum_value == 10 else str(checksum_value)
    return compact_value[-1] == expected_character


def check_orcid(value: str, label: str) -> list[str]:
    """Check an optional ORCID value.

    参数:
        value: ORCID value.
        label: Diagnostic field label.

    返回:
        list[str]: Error messages.
    """
    if not value:
        return []
    if ORCID_PATTERN.fullmatch(value) is None or not is_valid_orcid_checksum(value):
        return [f"{label} ORCID is invalid"]
    return []


def check_required_value(value: str, label: str) -> list[str]:
    """Check whether a required scalar value is present.

    参数:
        value: Scalar value.
        label: Diagnostic field label.

    返回:
        list[str]: Error messages.
    """
    if not value:
        return [f"{label} is missing"]
    return []


def check_true_fields(metadata_text: str) -> list[str]:
    """Check final-upload boolean gate fields.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages.
    """
    errors: list[str] = []
    for field_name, message in FINAL_UPLOAD_TRUE_FIELDS.items():
        if scalar_value(metadata_text, field_name).lower() != "true":
            errors.append(message)
    return errors


def check_author_rows(metadata_text: str) -> list[str]:
    """Check final-upload author rows.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages.
    """
    rows = parse_author_rows(metadata_text)
    if not rows:
        return ["author list is empty"]
    errors: list[str] = []
    for index, row in enumerate(rows, start=1):
        label = f"author row {index}"
        errors.extend(check_required_value(row.get("name", ""), f"{label} name"))
        errors.extend(check_required_value(row.get("affiliation", ""), f"{label} affiliation"))
        errors.extend(check_email(row.get("email", ""), label))
        errors.extend(check_orcid(row.get("orcid", ""), label))
    return errors


def check_author_orcid_uniqueness(metadata_text: str) -> list[str]:
    """Check whether non-empty author ORCID values are unique.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages.
    """
    seen_orcids: set[str] = set()
    duplicate_orcids: set[str] = set()
    for row in parse_author_rows(metadata_text):
        orcid = row.get("orcid", "").strip()
        if not orcid:
            continue
        if orcid in seen_orcids:
            duplicate_orcids.add(orcid)
        seen_orcids.add(orcid)
    if duplicate_orcids:
        return [f"duplicate author ORCID values: {sorted(duplicate_orcids)}"]
    return []


def check_author_email_uniqueness(metadata_text: str) -> list[str]:
    """Check whether author email values are unique.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages.
    """
    seen_emails: set[str] = set()
    duplicate_emails: set[str] = set()
    for row in parse_author_rows(metadata_text):
        email = row.get("email", "").strip().lower()
        if not email:
            continue
        if email in seen_emails:
            duplicate_emails.add(email)
        seen_emails.add(email)
    if duplicate_emails:
        return [f"duplicate author email values: {sorted(duplicate_emails)}"]
    return []


def check_corresponding_author(metadata_text: str) -> list[str]:
    """Check final-upload corresponding-author fields.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages.
    """
    row = parse_mapping_section(metadata_text, "corresponding_author")
    errors: list[str] = []
    errors.extend(check_required_value(row.get("name", ""), "corresponding author name"))
    errors.extend(check_required_value(row.get("affiliation", ""), "corresponding author affiliation"))
    errors.extend(check_email(row.get("email", ""), "corresponding author"))
    errors.extend(check_orcid(row.get("orcid", ""), "corresponding author"))
    return errors


def check_corresponding_author_matches_author_rows(metadata_text: str) -> list[str]:
    """Check whether the corresponding author is present in the author list.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages.
    """
    corresponding_author = parse_mapping_section(metadata_text, "corresponding_author")
    corresponding_name = corresponding_author.get("name", "").strip().lower()
    corresponding_email = corresponding_author.get("email", "").strip().lower()
    if not corresponding_name and not corresponding_email:
        return []
    for author_row in parse_author_rows(metadata_text):
        author_name = author_row.get("name", "").strip().lower()
        author_email = author_row.get("email", "").strip().lower()
        if corresponding_name and author_name == corresponding_name:
            return []
        if corresponding_email and author_email == corresponding_email:
            return []
    return ["corresponding author must match an author row by name or email"]


def check_target_preparation_confirmation(metadata_text: str) -> list[str]:
    """Check target-journal ranking and author confirmation gates.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for unresolved target-journal confirmation fields.
    """
    row = parse_mapping_section(metadata_text, "target_preparation")
    errors: list[str] = []
    if not row:
        return ["target preparation section is missing"]

    if not row.get("selected_author_guide_source", "").strip():
        errors.append("selected author guide source is missing")
    author_guide_source_url = row.get("selected_author_guide_source_url", "").strip()
    if not author_guide_source_url:
        errors.append("selected author guide source URL is missing")
    else:
        errors.extend(
            check_non_placeholder_url(
                author_guide_source_url,
                "selected author guide source URL",
            )
        )
    author_guide_date = row.get("selected_author_guide_rechecked_date", "").strip()
    if not author_guide_date:
        errors.append("selected author guide rechecked date is missing")
    else:
        errors.extend(check_non_future_date(author_guide_date, "selected author guide rechecked date"))
    if row.get("selected_template_requirements_confirmed", "").lower() != "true":
        errors.append("selected template requirements confirmation is incomplete")

    ranking_required = row.get("ranking_confirmation_required_before_final_upload", "").lower()
    if ranking_required != "true":
        errors.append("ranking/category confirmation requirement is missing")
    if row.get("ranking_confirmation_completed", "").lower() != "true":
        errors.append("ranking/category confirmation is incomplete")
    if not row.get("ranking_confirmation_source", "").strip():
        errors.append("ranking/category confirmation source is missing")
    ranking_source_url = row.get("ranking_confirmation_source_url", "").strip()
    if not ranking_source_url:
        errors.append("ranking/category confirmation source URL is missing")
    else:
        errors.extend(
            check_non_placeholder_url(
                ranking_source_url,
                "ranking/category confirmation source URL",
            )
        )
    checked_date = row.get("ranking_confirmation_checked_date", "").strip()
    if not checked_date:
        errors.append("ranking/category confirmation checked date is missing")
    else:
        errors.extend(check_non_future_date(checked_date, "ranking/category confirmation checked date"))

    selected_target_required = row.get("selected_target_requires_author_confirmation", "").lower()
    if selected_target_required != "true":
        errors.append("selected target journal author confirmation requirement is missing")
    if row.get("selected_target_author_confirmed", "").lower() != "true":
        errors.append("selected target journal author confirmation is incomplete")
    return errors


def check_artifact_release_link(metadata_text: str) -> list[str]:
    """Check final-upload artifact release URL or DOI fields.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages.
    """
    row = parse_mapping_section(metadata_text, "artifact_boundary")
    artifact_url = row.get("artifact_release_url", "")
    artifact_doi = row.get("artifact_release_doi", "")
    if not artifact_url and not artifact_doi:
        return ["artifact release URL or DOI is required"]
    errors: list[str] = []
    if artifact_url:
        errors.extend(check_non_placeholder_url(artifact_url, "artifact release URL"))
    if artifact_doi and DOI_PATTERN.fullmatch(artifact_doi) is None:
        errors.append("artifact release DOI is invalid")
    doi_url_value = doi_from_url(artifact_url) if artifact_url else ""
    if doi_url_value and artifact_doi and doi_url_value.lower() != artifact_doi.lower():
        errors.append("artifact release URL DOI does not match artifact release DOI")
    return errors


def check_repository_reference(metadata_text: str) -> list[str]:
    """Check final-upload repository URL, branch, and commit reference fields.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for missing or invalid repository reference fields.
    """
    repository_row = parse_mapping_section(metadata_text, "repository_reference")
    repository_url = repository_row.get("repository_url", "")
    repository_commit = repository_row.get("repository_commit", "")
    repository_branch = repository_row.get("repository_branch", "")
    errors: list[str] = []
    if not repository_url:
        errors.append("repository URL is missing")
    else:
        errors.extend(check_non_placeholder_url(repository_url, "repository URL"))
    if not repository_commit:
        errors.append("repository commit is missing")
    elif repository_commit.strip().lower() in COMMIT_PLACEHOLDERS:
        errors.append("repository commit is still a placeholder")
    elif COMMIT_PATTERN.fullmatch(repository_commit) is None:
        errors.append("repository commit is invalid")
    if not repository_branch:
        errors.append("repository branch is missing")
    elif repository_branch != FINAL_UPLOAD_REPOSITORY_BRANCH:
        errors.append(f"repository branch must be {FINAL_UPLOAD_REPOSITORY_BRANCH}")
    return errors


def doi_from_url(value: str) -> str:
    """Extract a DOI from a doi.org URL.

    参数:
        value: Artifact release URL.

    返回:
        str: DOI path from the URL, or an empty string when the URL is not a doi.org URL.
    """
    parsed_url = urlparse(value)
    if parsed_url.netloc.lower() != "doi.org":
        return ""
    return unquote(parsed_url.path.lstrip("/")).strip()


def check_final_upload_article_type(metadata_text: str) -> list[str]:
    """Check whether final-upload article type is explicit and supported.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages.
    """
    article_type = scalar_value(metadata_text, "article_type").strip().lower()
    if not article_type:
        return ["article type is missing"]
    if article_type not in FINAL_UPLOAD_ARTICLE_TYPES:
        return [f"article type is unsupported: {article_type}"]
    return []


def check_final_upload_review_mode(metadata_text: str) -> list[str]:
    """Check whether final-upload review mode matches the selected journal route.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages.
    """
    target_journal = scalar_value(metadata_text, "target_journal")
    review_mode = scalar_value(metadata_text, "review_mode")
    normalized_target = target_journal.strip().lower()
    normalized_review_mode = review_mode.strip().lower()
    if not normalized_review_mode:
        if normalized_target in AUTHOR_VISIBLE_REVIEW_JOURNALS:
            journal_name = AUTHOR_VISIBLE_REVIEW_JOURNALS[normalized_target]
            return [f"review mode must be recorded for {journal_name}"]
        return ["review mode must be recorded for final upload"]
    if normalized_target in AUTHOR_VISIBLE_REVIEW_JOURNALS and (
        normalized_review_mode not in AUTHOR_VISIBLE_FINAL_REVIEW_MODES
    ):
        journal_name = AUTHOR_VISIBLE_REVIEW_JOURNALS[normalized_target]
        return [f"review mode must include final author identities for {journal_name}"]
    return []


def target_journal_requires_elsevier_files(metadata_text: str) -> bool:
    """Return whether the selected target journal needs Elsevier package files.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        bool: True when final upload should include DKE/Elsevier source and PDF files.
    """
    target_journal = scalar_value(metadata_text, "target_journal")
    return target_journal.strip().lower() in ELSEVIER_TARGET_JOURNALS


def check_editable_biography_file_paths(metadata_text: str) -> list[str]:
    """Check whether DKE author biography paths use editable non-PDF formats.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for missing or non-editable biography file paths.
    """
    biography_files = parse_section_sequence_values(metadata_text, "author_identity_materials", "biography_files")
    errors: list[str] = []
    for biography_file in biography_files:
        normalized_path = unquote(biography_file).strip()
        suffix_match = re.search(r"(\.[A-Za-z0-9]+)(?:[?#].*)?$", normalized_path)
        suffix = suffix_match.group(1).lower() if suffix_match else ""
        if not suffix:
            errors.append(f"author biography file must include an editable file extension: {biography_file}")
            continue
        if suffix == ".pdf":
            errors.append("author biography file must be editable and must not be PDF")
        elif suffix not in DKE_EDITABLE_BIOGRAPHY_EXTENSIONS:
            errors.append(
                "author biography file must use an editable format "
                f"({', '.join(sorted(DKE_EDITABLE_BIOGRAPHY_EXTENSIONS))}): {biography_file}"
            )
    return errors


def check_author_identity_material_counts(metadata_text: str) -> list[str]:
    """Check whether DKE biography and photograph file counts match authors.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for author-material count mismatches.
    """
    author_count = len(parse_author_rows(metadata_text))
    if author_count == 0:
        return []

    biography_files = parse_section_sequence_values(metadata_text, "author_identity_materials", "biography_files")
    photograph_files = parse_section_sequence_values(metadata_text, "author_identity_materials", "photograph_files")
    errors: list[str] = []
    if biography_files and len(biography_files) != author_count:
        errors.append(
            "author biography file count must match author count: "
            f"expected {author_count}, found {len(biography_files)}"
        )
    if photograph_files and len(photograph_files) != author_count:
        errors.append(
            "author photograph file count must match author count: "
            f"expected {author_count}, found {len(photograph_files)}"
        )
    return errors


def check_author_photograph_file_paths(metadata_text: str) -> list[str]:
    """Check whether DKE author photograph paths use image file formats.

    功能:
        Validate that DKE author photograph file paths use supported image extensions.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for missing or non-image photograph file paths.
    """
    photograph_files = parse_section_sequence_values(metadata_text, "author_identity_materials", "photograph_files")
    errors: list[str] = []
    for photograph_file in photograph_files:
        normalized_path = unquote(photograph_file).strip()
        suffix_match = re.search(r"(\.[A-Za-z0-9]+)(?:[?#].*)?$", normalized_path)
        suffix = suffix_match.group(1).lower() if suffix_match else ""
        if not suffix:
            errors.append(f"author photograph file must include an image file extension: {photograph_file}")
            continue
        if suffix not in DKE_PHOTOGRAPH_EXTENSIONS:
            errors.append(
                "author photograph file must use an image format "
                f"({', '.join(sorted(DKE_PHOTOGRAPH_EXTENSIONS))}): {photograph_file}"
            )
    return errors


def check_author_identity_materials(metadata_text: str) -> list[str]:
    """Check DKE/Elsevier author biography and photograph material records.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for unresolved author identity material records.
    """
    target_journal = scalar_value(metadata_text, "target_journal").strip().lower()
    row = parse_mapping_section(metadata_text, "author_identity_materials")
    requirement_recorded = (
        row.get("author_biography_and_photo_required_before_upload", "").lower() == "true"
    )
    required_for_selected_route = target_journal == "data & knowledge engineering" or requirement_recorded
    if not required_for_selected_route:
        return []
    if not row:
        return ["author identity materials section is missing"]

    errors: list[str] = []
    if row.get("author_identity_materials_verified", "").lower() != "true":
        errors.append("author identity materials verification is incomplete")
    if not section_key_has_value(metadata_text, "author_identity_materials", "biography_files"):
        errors.append("author biography file list is missing")
    else:
        errors.extend(check_editable_biography_file_paths(metadata_text))
    if not section_key_has_value(metadata_text, "author_identity_materials", "photograph_files"):
        errors.append("author photograph file list is missing")
    else:
        errors.extend(check_author_photograph_file_paths(metadata_text))
    errors.extend(check_author_identity_material_counts(metadata_text))
    return errors


def check_publisher_declaration_files(metadata_text: str) -> list[str]:
    """Check Elsevier declaration-tool output file records for final upload.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for unresolved publisher declaration files.
    """
    if not target_journal_requires_elsevier_files(metadata_text):
        return []

    row = parse_mapping_section(metadata_text, "publisher_declaration_files")
    if not row:
        return ["publisher declaration files section is missing"]

    errors: list[str] = []
    if row.get("elsevier_declarations_tool_required_before_upload", "").lower() != "true":
        errors.append("Elsevier declarations tool requirement is not recorded")

    declaration_file = row.get("competing_interest_declaration_file", "").strip()
    if not declaration_file:
        errors.append("Elsevier competing-interest declaration file is missing")
    else:
        normalized_path = unquote(declaration_file).strip()
        suffix_match = re.search(r"(\.[A-Za-z0-9]+)(?:[?#].*)?$", normalized_path)
        suffix = suffix_match.group(1).lower() if suffix_match else ""
        if suffix not in ELSEVIER_DECLARATION_FILE_EXTENSIONS:
            extensions = ", ".join(sorted(ELSEVIER_DECLARATION_FILE_EXTENSIONS))
            errors.append(f"Elsevier competing-interest declaration file must use {extensions}: {declaration_file}")

    if row.get("competing_interest_declaration_file_verified", "").lower() != "true":
        errors.append("Elsevier competing-interest declaration file verification is incomplete")
    return errors


def check_funding_statement(metadata_text: str) -> list[str]:
    """Check whether final-upload metadata declares funding status and wording.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for missing funding declaration fields.
    """
    funding_row = parse_mapping_section(metadata_text, "funding")
    funding_statement = funding_row.get("funding_statement", "") or funding_row.get("statement", "")
    no_external_funding = funding_row.get("no_external_funding_declared", "").lower() == "true"
    funding_sources = funding_row.get("funding_sources", "")
    has_funding_source = bool(funding_sources and funding_sources != "[]")
    errors: list[str] = []
    if not funding_statement:
        errors.append("funding statement text is missing")
    if not no_external_funding and not has_funding_source:
        errors.append("funding status is missing")
    return errors


def check_submission_statement_fields(metadata_text: str) -> list[str]:
    """Check whether final-upload metadata declares required submission statements.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for missing journal declaration statements.
    """
    statements = parse_mapping_section(metadata_text, "statements")
    required_fields = {
        "originality": "originality statement is missing",
        "author_approval": "author approval statement is missing",
        "competing_interests": "competing interests statement is missing",
        "ethics": "ethics statement is missing",
        "data_code_availability": "data/code availability statement is missing",
    }
    return [
        message
        for field_name, message in required_fields.items()
        if not statements.get(field_name, "")
    ]


def check_data_code_availability_statement(metadata_text: str) -> list[str]:
    """Check whether the data/code availability statement carries release references.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for missing repository or artifact references in the statement.
    """
    statements = parse_mapping_section(metadata_text, "statements")
    data_code_availability = statements.get("data_code_availability", "")
    if not data_code_availability:
        return []
    repository_row = parse_mapping_section(metadata_text, "repository_reference")
    artifact_row = parse_mapping_section(metadata_text, "artifact_boundary")
    errors: list[str] = []
    repository_url = repository_row.get("repository_url", "")
    repository_commit = repository_row.get("repository_commit", "")
    artifact_values = [
        value
        for value in (
            artifact_row.get("artifact_release_url", ""),
            artifact_row.get("artifact_release_doi", ""),
        )
        if value
    ]
    if repository_url and repository_url not in data_code_availability:
        errors.append("data/code availability statement missing repository URL value")
    if repository_commit and repository_commit not in data_code_availability:
        errors.append("data/code availability statement missing repository commit value")
    if artifact_values and not any(value in data_code_availability for value in artifact_values):
        errors.append("data/code availability statement missing artifact release URL or DOI value")
    return errors


def check_research_data_statement(metadata_text: str) -> list[str]:
    """Check whether target-specific research data statement metadata is usable.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for missing or inconsistent research data statement fields.
    """
    target_journal = scalar_value(metadata_text, "target_journal").strip().lower()
    statements = parse_mapping_section(metadata_text, "statements")
    research_data_statement = statements.get("research_data_statement", "")
    target_journal_label = RESEARCH_DATA_STATEMENT_REQUIRED_TARGETS.get(target_journal)
    errors: list[str] = []
    if target_journal_label and not research_data_statement:
        errors.append(f"research data statement is missing for {target_journal_label}")
    if target_journal_label and research_data_statement:
        artifact_row = parse_mapping_section(metadata_text, "artifact_boundary")
        artifact_values = [
            value
            for value in (
                artifact_row.get("artifact_release_url", ""),
                artifact_row.get("artifact_release_doi", ""),
            )
            if value
        ]
        if artifact_values and not any(value in research_data_statement for value in artifact_values):
            errors.append(
                f"research data statement missing artifact release URL or DOI value for {target_journal_label}"
            )
        normalized_statement = research_data_statement.lower()
        includes_raw_data = any(term in normalized_statement for term in RESEARCH_DATA_STATEMENT_RAW_DATA_TERMS)
        includes_redistribution_boundary = any(
            term in normalized_statement for term in RESEARCH_DATA_STATEMENT_REDISTRIBUTION_BOUNDARY_TERMS
        )
        if not includes_raw_data or not includes_redistribution_boundary:
            errors.append(
                "research data statement missing raw third-party data redistribution "
                f"boundary for {target_journal_label}"
            )
        mentions_repository = any(
            term in normalized_statement for term in RESEARCH_DATA_STATEMENT_REPOSITORY_ONLY_TERMS
        )
        contains_artifact_value = any(value.lower() in normalized_statement for value in artifact_values)
        if artifact_values and mentions_repository and not contains_artifact_value:
            errors.append(
                f"research data statement must not be a Git-only repository statement for {target_journal_label}"
            )
    return errors


def check_author_contribution_statement(metadata_text: str) -> list[str]:
    """Check whether final-upload metadata declares author contributions.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for missing author contribution information.
    """
    contribution_row = parse_mapping_section(metadata_text, "author_contributions")
    contribution_statement = contribution_row.get("contribution_statement", "") or contribution_row.get(
        "credit_statement",
        "",
    )
    credit_required = contribution_row.get("credit_taxonomy_required_before_final_upload", "true").lower() != "false"
    contribution_role_rows = parse_contribution_role_rows(metadata_text)
    valid_role_rows = [
        row
        for row in contribution_role_rows
        if row.get("author", "").strip()
        and any(role_name in row.get("credit_roles", "") for role_name in CREDIT_AUTHOR_ROLES)
    ]
    has_credit_roles = bool(valid_role_rows)
    errors: list[str] = []
    if not contribution_statement and not has_credit_roles:
        errors.append("author contribution statement is missing")
    if credit_required and not has_credit_roles:
        errors.append("CRediT author contribution roles are missing")
    if credit_required and valid_role_rows:
        role_authors = {row.get("author", "").strip().lower() for row in valid_role_rows}
        for author_row in parse_author_rows(metadata_text):
            author_name = author_row.get("name", "").strip()
            if author_name and author_name.lower() not in role_authors:
                errors.append(f"CRediT author contribution roles missing for author: {author_name}")
    return errors


def check_permissions_statement(metadata_text: str) -> list[str]:
    """Check whether final-upload metadata declares third-party material permissions.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for missing permissions declaration fields.
    """
    permissions_row = parse_mapping_section(metadata_text, "permissions")
    permissions_statement = permissions_row.get("permissions_statement", "") or permissions_row.get("statement", "")
    no_permission_required = (
        permissions_row.get("no_third_party_material_requiring_permission_declared", "").lower() == "true"
    )
    requires_permission = permissions_row.get("third_party_material_requires_permission", "").lower() == "true"
    permission_files = permissions_row.get("permission_files", "")
    has_permission_files = bool(permission_files and permission_files != "[]")
    errors: list[str] = []
    if not permissions_statement:
        errors.append("permissions statement is missing")
    if not no_permission_required and not requires_permission:
        errors.append("permissions status is missing")
    if requires_permission and not has_permission_files:
        errors.append("permission files are missing")
    return errors


def check_generative_ai_declaration(metadata_text: str) -> list[str]:
    """Check whether final-upload metadata declares AI-tool use status.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for missing or unsafe generative AI declaration fields.
    """
    generative_ai_row = parse_mapping_section(metadata_text, "generative_ai")
    ai_tools_used = generative_ai_row.get("ai_tools_used_in_manuscript_preparation", "")
    declaration_statement = generative_ai_row.get("declaration_statement", "")
    author_review_confirmed = generative_ai_row.get("author_review_and_responsibility_confirmed", "").lower() == "true"
    ai_author_excluded = generative_ai_row.get("ai_not_listed_as_author_confirmed", "").lower() == "true"
    ai_artwork_included = generative_ai_row.get("ai_generated_images_or_artwork_included", "").lower() == "true"
    errors: list[str] = []
    if not ai_tools_used:
        errors.append("generative AI use status is missing")
    if not declaration_statement:
        errors.append("generative AI declaration statement is missing")
    if not author_review_confirmed:
        errors.append("generative AI author review confirmation is incomplete")
    if not ai_author_excluded:
        errors.append("AI authorship exclusion confirmation is incomplete")
    if ai_artwork_included:
        errors.append("machine-generated figures or artwork are not cleared for the selected submission route")
    return errors


def check_final_upload_cover_letter_text(cover_letter_text: str, metadata_text: str) -> list[str]:
    """Check final-upload cover letter target and artifact boundaries.

    参数:
        cover_letter_text: Cover letter Markdown text.
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for unresolved final-upload cover letter fields.
    """
    errors: list[str] = []
    target_journal = scalar_value(metadata_text, "target_journal")
    if target_journal and target_journal not in cover_letter_text:
        errors.append(f"final upload cover letter unresolved: cover letter missing target journal: {target_journal}")
    article_type = scalar_value(metadata_text, "article_type")
    expected_article_type = ARTICLE_TYPE_COVER_LETTER_MARKERS.get(article_type)
    if expected_article_type and expected_article_type not in cover_letter_text.lower():
        errors.append(
            "final upload cover letter unresolved: "
            f"cover letter missing article type: {expected_article_type}"
        )
    corresponding_author = parse_mapping_section(metadata_text, "corresponding_author")
    corresponding_author_name = corresponding_author.get("name", "")
    if corresponding_author_name and corresponding_author_name not in cover_letter_text:
        errors.append(
            "final upload cover letter unresolved: "
            f"cover letter missing corresponding author name: {corresponding_author_name}"
        )
    if re.search(r"(?im)^\s*dear\s+editors?\s*[,.:;-]?\s*$", cover_letter_text):
        errors.append("final upload cover letter unresolved: cover letter uses generic editor greeting")
    if re.search(r"(?im)^\s*anonymous\s+authors?\s*[,.:;-]?\s*$", cover_letter_text):
        errors.append("final upload cover letter unresolved: cover letter still uses anonymous author signature")
    lowered_text = cover_letter_text.lower()
    for marker, message in FINAL_UPLOAD_COVER_LETTER_UNRESOLVED_MARKERS.items():
        if marker in lowered_text:
            errors.append(f"final upload cover letter unresolved: {message}")
    if "artifact release" not in lowered_text and "artifact url" not in lowered_text and "artifact doi" not in lowered_text:
        errors.append("final upload cover letter unresolved: cover letter missing artifact release boundary")
    for marker, message in FINAL_UPLOAD_COVER_LETTER_EVIDENCE_BOUNDARY_MARKERS.items():
        if marker not in lowered_text:
            errors.append(f"final upload cover letter unresolved: {message}")
    for marker, message in FINAL_UPLOAD_COVER_LETTER_PUBLIC_SOURCE_BOUNDARY_MARKERS.items():
        if marker not in lowered_text:
            errors.append(f"final upload cover letter unresolved: {message}")
    artifact_row = parse_mapping_section(metadata_text, "artifact_boundary")
    artifact_values = [
        value
        for value in (
            artifact_row.get("artifact_release_url", ""),
            artifact_row.get("artifact_release_doi", ""),
        )
        if value
    ]
    if artifact_values and not any(value in cover_letter_text for value in artifact_values):
        errors.append("final upload cover letter unresolved: cover letter missing artifact release URL or DOI value")
    return errors


def check_final_upload_metadata_text(metadata_text: str) -> list[str]:
    """Check final-upload submission metadata for completeness and structure.

    参数:
        metadata_text: Submission metadata YAML text.

    返回:
        list[str]: Error messages for unresolved final-upload metadata.
    """
    errors = [
        f"final upload metadata unresolved: {message}"
        for marker, message in FINAL_UPLOAD_BLOCKED_MARKERS.items()
        if marker in metadata_text
    ]
    if not scalar_value(metadata_text, "target_journal"):
        errors.append("final upload metadata unresolved: target journal is empty")
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_true_fields(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_author_rows(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_author_email_uniqueness(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_author_orcid_uniqueness(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_corresponding_author(metadata_text))
    errors.extend(
        f"final upload metadata unresolved: {message}"
        for message in check_corresponding_author_matches_author_rows(metadata_text)
    )
    errors.extend(
        f"final upload metadata unresolved: {message}"
        for message in check_target_preparation_confirmation(metadata_text)
    )
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_author_identity_materials(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_publisher_declaration_files(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_funding_statement(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_submission_statement_fields(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_data_code_availability_statement(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_research_data_statement(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_author_contribution_statement(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_permissions_statement(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_generative_ai_declaration(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_artifact_release_link(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_repository_reference(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_final_upload_article_type(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_final_upload_review_mode(metadata_text))
    return sorted(set(errors))
