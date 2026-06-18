"""Shared checks for final-upload submission metadata."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse


FINAL_UPLOAD_BLOCKED_MARKERS = {
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
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
URL_PATTERN = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
DOI_PATTERN = re.compile(r"^10\.[^\s/]+/[^\s]+$", re.IGNORECASE)
AUTHOR_VISIBLE_REVIEW_JOURNALS = {
    "data & knowledge engineering": "Data & Knowledge Engineering",
    "information systems": "Information Systems",
    "scientometrics": "Scientometrics",
}
ELSEVIER_TARGET_JOURNALS = {
    "data & knowledge engineering",
    "information systems",
}
DKE_ELSEVIER_FILE_REQUIREMENT_ERROR = "DKE/Elsevier final upload requires DKE/Elsevier source and PDF files"
FINAL_UPLOAD_TRUE_FIELDS = {
    "target_journal_template_bound": "target journal template is not bound",
    "target_journal_selected": "target journal checklist item is incomplete",
    "target_journal_template_applied": "target journal template checklist item is incomplete",
    "author_metadata_completed": "author metadata checklist item is incomplete",
    "corresponding_author_completed": "corresponding author checklist item is incomplete",
    "manuscript_pdf_rebuilt_after_template": "manuscript PDF rebuild checklist item is incomplete",
    "supplementary_pdf_rebuilt_after_template": "supplementary PDF rebuild checklist item is incomplete",
    "submission_system_files_verified": "submission system file checklist item is incomplete",
    "artifact_release_prepared_or_linked": "artifact release checklist item is incomplete",
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
    if artifact_url and URL_PATTERN.fullmatch(artifact_url) is None:
        errors.append("artifact release URL is invalid")
    if artifact_doi and DOI_PATTERN.fullmatch(artifact_doi) is None:
        errors.append("artifact release DOI is invalid")
    doi_url_value = doi_from_url(artifact_url) if artifact_url else ""
    if doi_url_value and artifact_doi and doi_url_value.lower() != artifact_doi.lower():
        errors.append("artifact release URL DOI does not match artifact release DOI")
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
    if not review_mode and normalized_target in AUTHOR_VISIBLE_REVIEW_JOURNALS:
        journal_name = AUTHOR_VISIBLE_REVIEW_JOURNALS[normalized_target]
        return [f"review mode must be recorded for {journal_name}"]
    if review_mode == "anonymous_review" and normalized_target in AUTHOR_VISIBLE_REVIEW_JOURNALS:
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
    if "Dear Editor," in cover_letter_text:
        errors.append("final upload cover letter unresolved: cover letter uses generic editor greeting")
    if "Anonymous Authors" in cover_letter_text:
        errors.append("final upload cover letter unresolved: cover letter still uses anonymous author signature")
    lowered_text = cover_letter_text.lower()
    if "artifact release" not in lowered_text and "artifact url" not in lowered_text and "artifact doi" not in lowered_text:
        errors.append("final upload cover letter unresolved: cover letter missing artifact release boundary")
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
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_artifact_release_link(metadata_text))
    errors.extend(f"final upload metadata unresolved: {message}" for message in check_final_upload_review_mode(metadata_text))
    return sorted(set(errors))
