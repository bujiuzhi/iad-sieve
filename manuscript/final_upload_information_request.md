# Final Upload Information Request

This file records external information that must be provided by the authors before final upload. It is not a manuscript file for journal upload.

## Submission metadata mapping

After the authors complete this form, copy the confirmed values into `submission_metadata.yml`, `cover_letter.md`, and the live submission system before running `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release`.

Repository URL and commit binding: keep the source `repository_reference` fields blank until final upload unless the target journal explicitly requires them in the source metadata. The final-upload package builder reads `git remote origin`, `git rev-parse HEAD`, and the current branch, then writes `repository_url`, `repository_commit`, `repository_branch`, and the matching data/code availability wording into the package copy of `submission_metadata.yml`. This avoids a self-referential Git commit value in the tracked source file while keeping the final package manifest and package metadata aligned.

| Request section | Primary `submission_metadata.yml` target | Additional file or system target |
| --- | --- | --- |
| Target journal | `submission`, `target_preparation`, `target_journal_template_bound`, `final_upload_checklist.target_journal_selected`, `final_upload_checklist.article_type_confirmed`, `final_upload_checklist.review_mode_confirmed`, `final_upload_checklist.target_journal_template_applied` | Target-journal template source, institutional ranking/category source, and live submission system |
| Author list | `authors`, `author_contributions.roles`, `final_upload_checklist.author_metadata_completed` | Final title page and live submission system |
| Author biographies and photographs | `author_identity_materials`, `final_upload_checklist.author_biographies_and_photos_ready` | DKE/Elsevier biography text and photograph upload files, if requested |
| Corresponding author | `corresponding_author`, `final_upload_checklist.corresponding_author_completed` | Final title page, cover letter, and live submission system |
| Funding statement | `funding`, `statements`, `final_upload_checklist.funding_statement_text_ready` | Manuscript declarations and live submission system |
| Author contribution statement | `author_contributions`, `final_upload_checklist.contribution_statement_complete` | Manuscript declarations and live submission system |
| Permissions statement | `permissions`, `final_upload_checklist.permissions_statement_complete` | Manuscript declarations and permission files, if required |
| Generative AI declaration | `generative_ai`, `final_upload_checklist.generative_ai_declaration_complete` | Manuscript declaration section and live submission system |
| Data and code availability statement | `repository_reference`, `artifact_boundary`, `statements.research_data_statement` | Manuscript declarations and research-data statement field |
| Artifact release | `artifact_boundary`, `final_upload_checklist.artifact_release_prepared_or_linked` | Public artifact record and live submission system |
| PDF and system checks | `final_upload_checklist.manuscript_pdf_rebuilt_after_template`, `final_upload_checklist.supplementary_pdf_rebuilt_after_template`, `final_upload_checklist.submission_system_files_verified`, `final_upload_checklist.first_screen_claim_lockdown_confirmed`, `upload_preparation.live_submission_system_verified`, `upload_preparation.final_upload_package_verified_against_system` | Rebuilt PDFs, first-screen claim lockdown, and live submission system |
| Submission text consistency | `final_upload_checklist.submission_system_files_verified`, `upload_preparation.live_submission_system_verified`, `upload_preparation.final_upload_package_verified_against_system` | Title, abstract, keywords, highlights, uploaded files, and final package checked in the live submission system |

## Target journal

All author-guide and ranking/category confirmation dates must use YYYY-MM-DD and must not be later than the actual check date.
Source URLs must be public HTTP/HTTPS URLs and must not use placeholder domains such as example.org, localhost, .test, or .invalid.

### DKE preflight source status

The DKE official-guide preflight source is already recorded in `submission_metadata.yml` as `dke_official_guide_source`, `dke_official_guide_source_url`, `dke_official_guide_rechecked`, and `dke_official_guide_constraints_verified`. These fields support preflight preparation only. They do not replace the final selected-author-guide fields or the author-confirmed target-journal decision.

- DKE official guide source recorded:
- DKE official guide source URL:
- DKE official guide rechecked date:
- DKE official guide constraints verified:
- Final selected-author-guide fields still require author confirmation:
- Final target journal decision still requires author confirmation:
- Final ranking/category confirmation still requires institutional source confirmation:

- Selected target journal:
- Article type:
- Article type controlled value for this manuscript:
- Use `research_article` for the final upload:
- Do not use `review_article`, `case_report`, or other article-type values unless the manuscript is rewritten and revalidated for that route:
- Review mode:
- Review mode value must be recorded whenever `review_mode_confirmed` is true:
- Review mode controlled value for single-anonymized author-visible final upload routes:
- Use `single_anonymized_with_final_author_identities` or `single_anonymized_author_visible_final_upload` for DKE, Information Systems, or Scientometrics final upload:
- Do not use `anonymous_review` or a generic `single_anonymized` value for final upload:
- Journal template:
- Selected author-guide source:
- Selected author-guide source URL:
- Selected author-guide rechecked date:
- Selected template requirements confirmed:
- Submission system URL:
- Rechecked author-guide date:
- Institutional ranking/category source checked:
- Institutional ranking/category source URL:
- Ranking/category checked date:
- Ranking/category confirmation completed:
- Selected target journal author-confirmed:

## Author list

For each author, provide the final Author order, name, affiliation, email, ORCID, and contribution roles.

| Author order | Name | Affiliation | Email | ORCID | Contribution roles |
| --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  |  |

## Author biographies and photographs

For the DKE/Elsevier route, provide a short biography and a passport-type photograph for each author when requested by the live submission system.

| Author order | Biography text ready | Photograph file path | Editable biography file, if required |
| --- | --- | --- | --- |
| 1 |  |  |  |

- `author_identity_materials.author_biography_and_photo_required_before_upload`:
- `author_identity_materials.biography_files`:
- `author_identity_materials.photograph_files`:
- `author_identity_materials.author_identity_materials_verified`:
- Biography file path:
- Photograph file path:
- Author identity materials verified:

## Corresponding author

- Name:
- Affiliation:
- Email:
- ORCID:
- Postal address, if required:

## Funding statement

- Funding statement for the manuscript:
- Grant identifiers:
- Funder role statement:
- No-funding wording, if applicable:
- Funding statement text finalized even when no external funding is declared:

## Author contribution statement

- Contribution taxonomy required by target journal:
- Final Author contribution statement:
- Author-order confirmation:
- CRediT roles cover every listed author:

### CRediT author contribution statement

For each author, select the applicable CRediT roles and then draft the final author contribution statement required by the selected journal.

| Author order | Conceptualization | Data curation | Formal analysis | Funding acquisition | Investigation | Methodology | Project administration | Resources | Software | Supervision | Validation | Visualization | Writing - original draft | Writing - review and editing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

## Permissions statement

- Third-party material used in the manuscript:
- Permission status:
- Permissions statement text finalized even when no third-party material permission is required:
- License or approval record:
- Figure/table reuse notes:

## Generative AI declaration

- AI tools used in manuscript preparation:
- Final generative AI declaration statement:
- Author review and responsibility confirmed:
- AI tool not listed as author or co-author:
- Machine-generated figures, images, or artwork included:
- If no AI tools were used, final no-use wording:
- If only copy editing tools were used, target-journal exception confirmed:

## Declarations

### Competing interests

- Final competing-interest statement:

### Ethics statement

- Final ethics statement:
- Human-participant, clinical-record, or sensitive-data involvement:

### Data and code availability statement

- Repository URL:
- Repository URL must be a public non-placeholder HTTP/HTTPS URL:
- Repository commit:
- Repository branch:
- Repository branch must be `main` for the final upload:
- Repository URL and commit will be injected into the final-upload package copy from `git remote origin` and `git rev-parse HEAD`:
- Repository commit matches artifact release manifest:
- Data boundary:
- Artifact boundary:
- Final data/code availability statement, including repository URL, commit, artifact URL or DOI, and raw-data redistribution boundary:
- Research data statement for submission system:
- Artifact URL or DOI embedded in research data statement:
- Raw third-party data redistribution boundary included:

## Artifact release

- Artifact release URL or DOI:
- Artifact release URL must be a public non-placeholder HTTP/HTTPS URL when a URL is used:
- Artifact manifest `publication.artifact_release_url` matches this URL:
- Artifact manifest `publication.artifact_release_doi` matches this DOI:
- Artifact manifest `publication.public_access_status` is public, published, publicly accessible, or archived:
- Source artifact directory path for preflight:
- Source artifact preflight command passed:
- Artifact release directory path for final validation:
- Artifact release manifest:
- `checksums.sha256` validation status:
- `open_v2_main_results` row-level schema validated:
- Public access status:

## Live submission-system fields

- Title:
- Abstract:
- Keywords:
- Highlights:
- Suggested reviewers, if required:
- Excluded reviewers, if any:
- Research data statement, including the artifact URL or DOI exactly as recorded above:
- Additional declarations required by the live submission system:

### Submission text consistency

- Title source checked against `main.tex` after journal-template conversion:
- Abstract copied exactly from `main.tex` after journal-template conversion:
- Keywords copied exactly from `keywords.md`:
- Highlights copied exactly from `highlights.md`:
- First-page title, abstract, keywords, and highlights were previewed in the live submission system:
- First-screen claim lockdown confirmed for `cover_letter.md`, `highlights.md`, `keywords.md`, the abstract, and the conclusion:
- Live submission system verified:
- Final upload package verified against live system:
- First-screen materials preserve the Open-v2 evidence boundary and do not claim broad method superiority, SOTA ranking, statistical superiority, threshold stability, human-gold validation, Q2/B completion, final-upload readiness, or cluster-level deployment quality:

## Final title page

- Title page source:
- Author metadata inserted:
- Corresponding author marked:
- Affiliation numbering checked:
- ORCID and email visibility checked:

## Final-upload checklist

- target_journal_selected:
- article_type_confirmed:
- review_mode_confirmed:
- target_journal_template_applied:
- author_metadata_completed:
- author_biographies_and_photos_ready:
- corresponding_author_completed:
- funding_statement_text_ready:
- contribution_statement_complete:
- permissions_statement_complete:
- generative_ai_declaration_complete:
- manuscript_pdf_rebuilt_after_template:
- supplementary_pdf_rebuilt_after_template:
- submission_system_files_verified:
- live_submission_system_verified:
- final_upload_package_verified_against_system:
- first_screen_claim_lockdown_confirmed:
- artifact_release_prepared_or_linked:
