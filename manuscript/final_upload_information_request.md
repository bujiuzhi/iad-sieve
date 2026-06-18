# Final Upload Information Request

This file records external information that must be provided by the authors before final upload. It is not a manuscript file for journal upload.

## Submission metadata mapping

After the authors complete this form, copy the confirmed values into `submission_metadata.yml`, `cover_letter.md`, and the live submission system before running `python manuscript/scripts/validate_submission_package.py --final-upload`.

Repository URL and commit binding: keep the source `repository_reference` fields blank until final upload unless the target journal explicitly requires them in the source metadata. The final-upload package builder reads `git remote origin`, `git rev-parse HEAD`, and the current branch, then writes `repository_url`, `repository_commit`, `repository_branch`, and the matching data/code availability wording into the package copy of `submission_metadata.yml`. This avoids a self-referential Git commit value in the tracked source file while keeping the final package manifest and package metadata aligned.

| Request section | Primary `submission_metadata.yml` target | Additional file or system target |
| --- | --- | --- |
| Target journal | `submission`, `target_preparation`, `target_journal_template_bound`, `final_upload_checklist.target_journal_selected`, `final_upload_checklist.article_type_confirmed`, `final_upload_checklist.review_mode_confirmed`, `final_upload_checklist.target_journal_template_applied` | Target-journal template source and live submission system |
| Author list | `authors`, `author_contributions.roles`, `final_upload_checklist.author_metadata_completed` | Final title page and live submission system |
| Author biographies and photographs | `final_upload_checklist.author_biographies_and_photos_ready` | DKE/Elsevier biography text and photograph upload files, if requested |
| Corresponding author | `corresponding_author`, `final_upload_checklist.corresponding_author_completed` | Final title page, cover letter, and live submission system |
| Funding statement | `funding`, `statements`, `final_upload_checklist.funding_statement_text_ready` | Manuscript declarations and live submission system |
| Author contribution statement | `author_contributions`, `final_upload_checklist.contribution_statement_complete` | Manuscript declarations and live submission system |
| Permissions statement | `permissions`, `final_upload_checklist.permissions_statement_complete` | Manuscript declarations and permission files, if required |
| Generative AI declaration | `generative_ai`, `final_upload_checklist.generative_ai_declaration_complete` | Manuscript declaration section and live submission system |
| Data and code availability statement | `repository_reference`, `artifact_boundary`, `statements.research_data_statement` | Manuscript declarations and research-data statement field |
| Artifact release | `artifact_boundary`, `final_upload_checklist.artifact_release_prepared_or_linked` | Public artifact record and live submission system |
| PDF and system checks | `final_upload_checklist.manuscript_pdf_rebuilt_after_template`, `final_upload_checklist.supplementary_pdf_rebuilt_after_template`, `final_upload_checklist.submission_system_files_verified`, `final_upload_checklist.first_screen_claim_lockdown_confirmed` | Rebuilt PDFs, first-screen claim lockdown, and live submission system |
| Submission text consistency | `final_upload_checklist.submission_system_files_verified` | Title, abstract, keywords, and highlights copied from source files into the live submission system |

## Target journal

- Selected target journal:
- Article type:
- Review mode:
- Journal template:
- Submission system URL:
- Rechecked author-guide date:

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
- Repository commit:
- Repository branch:
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
- first_screen_claim_lockdown_confirmed:
- artifact_release_prepared_or_linked:
