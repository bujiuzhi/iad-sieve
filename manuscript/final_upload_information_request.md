# Final Upload Information Request

This file records external information that must be provided by the authors before final upload. It is not a manuscript file for journal upload.

## Minimal external input packet

Do not start final-upload package generation until this packet is complete and source-controlled metadata can be updated from confirmed values.

| Required packet item | Minimum evidence to provide | Where it will be synchronized |
| --- | --- | --- |
| Target route confirmation | Selected target journal, article type, review mode, author-guide URL, author-guide recheck date, template requirement confirmation, ranking/category source, ranking/category URL, and ranking/category checked date. | `submission_metadata.yml`, selected journal template source, cover letter, and live submission system. |
| Author identity materials | Final author order, affiliations, emails, ORCID values if used, corresponding author, DKE biography files, and photograph files when required. | Title page, `authors`, `corresponding_author`, `author_identity_materials`, cover letter, and live submission system. |
| Author-approved declarations | Funding statement, CRediT contribution statement, competing-interest statement, permissions statement, generative AI declaration, and Elsevier declaration-tool file when required. | Manuscript declaration sections, `submission_metadata.yml`, publisher declaration files, and live submission system. |
| Artifact publication record | Public artifact URL or DOI, publication access status, finalized release manifest, checksums, source artifact preflight result, source input manifest, and processing run log. | `artifact_boundary`, research-data statement, cover letter, artifact manifest publication object, and live submission system. |
| Final cover letter replacement values | Target-specific greeting, article type sentence, corresponding-author signature name, artifact URL or DOI sentence, declaration-status sentence, and confirmation that generic `Dear Editor`, anonymous signature, and anonymous preflight wording are removed. | `cover_letter.md`, `submission_metadata.yml`, and live submission system. |
| Live-system verification | Previewed title, abstract, keywords, highlights, uploaded files, source archive, final package, and first-screen claim boundary. | `upload_preparation`, `final_upload_checklist`, submission-system checklist, and final package validation. |

## Submission metadata mapping

After the authors complete this form, copy the confirmed values into `submission_metadata.yml`, `cover_letter.md`, and the live submission system before running `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release`.

Repository URL and commit binding: keep the source `repository_reference` fields blank until final upload unless the target journal explicitly requires them in the source metadata. The final-upload package builder reads `git remote origin`, `git rev-parse HEAD`, and the current branch, then writes `repository_url`, `repository_commit`, `repository_branch`, and the matching data/code availability wording into the package copy of `submission_metadata.yml`. This avoids a self-referential Git commit value in the tracked source file while keeping the final package manifest and package metadata aligned.

| Request section | Primary `submission_metadata.yml` target | Additional file or system target |
| --- | --- | --- |
| Target journal | `submission`, `target_preparation`, `target_journal_template_bound`, `final_upload_checklist.target_journal_selected`, `final_upload_checklist.article_type_confirmed`, `final_upload_checklist.review_mode_confirmed`, `final_upload_checklist.target_journal_template_applied` | Target-journal template source, institutional ranking/category source, and live submission system |
| Author list | `authors`, `author_contributions.roles`, `final_upload_checklist.author_metadata_completed` | Final title page and live submission system |
| Author biographies and photographs | `author_identity_materials`, `final_upload_checklist.author_biographies_and_photos_ready` | DKE/Elsevier biography text, editable biography files, and photograph upload files, if requested |
| Corresponding author | `corresponding_author`, `final_upload_checklist.corresponding_author_completed` | Final title page, cover letter, and live submission system |
| Funding statement | `funding`, `statements`, `final_upload_checklist.funding_statement_text_ready` | Manuscript declarations and live submission system |
| Author contribution statement | `author_contributions`, `final_upload_checklist.contribution_statement_complete` | Manuscript declarations and live submission system |
| Permissions statement | `permissions`, `final_upload_checklist.permissions_statement_complete` | Manuscript declarations and permission files, if required |
| Generative AI declaration | `generative_ai`, `final_upload_checklist.generative_ai_declaration_complete` | Manuscript declaration section and live submission system |
| Publisher declaration files | `publisher_declaration_files` | Elsevier declarations tool output, including the competing-interest `.doc` or `.docx` file when the DKE/Elsevier route is selected |
| Data and code availability statement | `repository_reference`, `artifact_boundary`, `statements.research_data_statement` | Manuscript declarations and research-data statement field |
| Artifact release | `artifact_boundary`, `final_upload_checklist.artifact_release_prepared_or_linked` | Public artifact record and live submission system |
| Final cover letter | `submission.target_journal`, `submission.article_type`, `corresponding_author`, `artifact_boundary`, `statements`, `funding`, `author_contributions`, `permissions`, and `generative_ai` | `cover_letter.md` and live submission system |
| PDF and system checks | `final_upload_checklist.manuscript_pdf_rebuilt_after_template`, `final_upload_checklist.supplementary_pdf_rebuilt_after_template`, `final_upload_checklist.submission_system_files_verified`, `final_upload_checklist.first_screen_claim_lockdown_confirmed`, `upload_preparation.live_submission_system_verified`, `upload_preparation.final_upload_package_verified_against_system` | Rebuilt PDFs, first-screen claim lockdown, and live submission system |
| Submission text consistency | `final_upload_checklist.submission_system_files_verified`, `upload_preparation.live_submission_system_verified`, `upload_preparation.final_upload_package_verified_against_system` | Title, abstract, keywords, highlights, uploaded files, and final package checked in the live submission system |

### Author confirmation and synchronization ledger

Before final-upload validation, maintain one ledger row per external value so the upload package can be audited without relying on memory or informal notes.

| External value | Confirmed value | Evidence source | Responsible author confirmation | YYYY-MM-DD confirmation date | Synchronization target | Validation evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Selected target journal, article type, and review mode |  | Author decision record, author-guide URL, and ranking/category source |  |  | `submission_metadata.yml`, selected journal source package, and live submission-system field checked | `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release` |
| Target ranking/category evidence for Q2/B decision |  | JCR quartile, Chinese Academy of Sciences zone, CCF class when applicable, institutional ranking/category source, ISSN match, subject category, source URL, source access date, and evidence export or screenshot path |  |  | `target_preparation.ranking_confirmation_*`, `target_journal_shortlist.md`, and author decision record | Final-upload metadata validation plus author-confirmed rank/category evidence packet |
| Author order, affiliations, emails, ORCID values, and corresponding author |  | Author-provided metadata record |  |  | `submission_metadata.yml`, title page, cover letter, and live submission-system field checked | Final package preview and metadata validation |
| Funding, competing-interest, permissions, CRediT, and generative AI declarations |  | Author-approved declaration text and publisher declaration files when required |  |  | `submission_metadata.yml`, manuscript declaration sections, `cover_letter.md`, and live submission-system field checked | Final-upload package validation and publisher declaration-file check |
| Artifact URL or DOI and public access status |  | Public release page, DOI landing page, or archive record |  |  | `submission_metadata.yml`, artifact manifest publication object, research-data statement, `cover_letter.md`, and live submission-system field checked | Artifact release validation plus final-upload package validation |

## Target journal

All author-guide and ranking/category confirmation dates must use YYYY-MM-DD and must not be later than the actual check date.
Source URLs must be public HTTP/HTTPS URLs and must not use placeholder domains such as example.org, localhost, .test, or .invalid.

### DKE preflight source status

The DKE official-guide preflight source is already recorded in `submission_metadata.yml` as `dke_official_guide_source`, `dke_official_guide_source_url`, `dke_official_guide_rechecked`, and `dke_official_guide_constraints_verified`. These fields support preflight preparation only. They do not replace the final selected-author-guide fields or the author-confirmed target-journal decision.

- DKE official guide source recorded: ScienceDirect Data & Knowledge Engineering guide for authors
- DKE official guide source URL: https://www.sciencedirect.com/journal/data-and-knowledge-engineering/publish/guide-for-authors
- DKE official guide rechecked date: 2026-06-23
- DKE official guide constraints verified: true
- DKE primary practical candidate recorded: Data & Knowledge Engineering
- DKE provisional target status recorded: dke_preflight_ready_pending_author_confirmation
- Final selected-author-guide fields still require author confirmation: yes
- Final target journal decision still requires author confirmation: yes
- Final ranking/category confirmation still requires institutional source confirmation: yes

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

### Target ranking/category evidence packet

Use this packet before claiming a Q2/B route or marking `ranking_confirmation_completed: true`. Publisher CiteScore, Impact Factor, or scope text is not sufficient for Q2/B classification.

| Evidence field | Confirmed value |
| --- | --- |
| Selected journal ISSN or eISSN matched to ranking source |  |
| Ranking source type, such as JCR, Chinese Academy of Sciences zone, CCF class, or institutional list |  |
| Subject category used by the ranking source |  |
| Reported category value, such as Q2, CAS Zone 2, CCF B, or institutional B-class equivalent |  |
| Ranking source URL or institutional system URL |  |
| Ranking source access date in YYYY-MM-DD |  |
| Evidence export, screenshot, or author decision record path |  |
| Responsible author confirming the target route |  |

- `target_preparation.ranking_confirmation_completed` must remain false until the packet is complete:
- `target_preparation.ranking_confirmation_source`:
- `target_preparation.ranking_confirmation_source_url`:
- `target_preparation.ranking_confirmation_checked_date`:
- Publisher metrics are screening signals only and do not replace JCR, CAS, CCF, or institutional category evidence:

### Q2/B ranking cross-check before final upload

Complete this cross-check before changing `ranking_confirmation_completed` to true or using any Q2/B-complete wording in the manuscript, cover letter, metadata, or live system.

- Selected journal name exactly matches `submission.target_journal`:
- Selected journal ISSN or eISSN matches the ranking source lookup:
- Ranking source category and reported value are captured in the evidence export or screenshot:
- Ranking source access date is not later than the final upload date:
- Responsible author has confirmed the ranking/category interpretation:
- Final cover letter and first-screen materials still avoid Q2/B-complete wording unless the packet above is complete and validated:

## Author list

For each author, provide the final Author order, name, affiliation, email, ORCID, and contribution roles.

| Author order | Name | Affiliation | Email | ORCID | Contribution roles |
| --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  |  |

## Author biographies and photographs

For the DKE/Elsevier route, provide a short biography and a passport-type photograph for each author when requested by the live submission system. Each DKE biography must have a maximum 100 words. The biography file must use an editable format such as `.doc`, `.docx`, `.rtf`, `.txt`, `.md`, or `.tex`, and must not be PDF. The passport-type photograph is a separate image file and must use an image format such as `.jpg`, `.jpeg`, `.png`, `.tif`, or `.tiff`.

Each listed author must have one editable biography file and one passport-type photograph file. Final-upload metadata validation rejects biography_files or photograph_files counts that differ from the number of author rows.

| Author order | Biography text ready | Biography word count <=100 | Editable biography file path, non-PDF | Photograph file path |
| --- | --- | --- | --- | --- |
| 1 |  |  |  |  |

- `author_identity_materials.author_biography_and_photo_required_before_upload`:
- `author_identity_materials.biography_files`:
- `author_identity_materials.photograph_files`:
- `author_identity_materials.author_identity_materials_verified`:
- Editable format confirmed:
- Biography word count, maximum 100 words:
- Biography file must not be PDF:
- Biography file path:
- Photograph file path:
- Photograph file must use image format `.jpg`, `.jpeg`, `.png`, `.tif`, or `.tiff`:
- Author identity materials verified:

## Corresponding author

- Name:
- Affiliation:
- Email:
- ORCID:
- Postal address, if required:

## Final cover letter replacement

Use this section to replace the anonymous preflight cover letter only after the selected target journal, corresponding author, artifact release, and declarations are confirmed. The final cover letter must pass `check_final_upload_cover_letter` through `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release`.

- Target-specific greeting line:
- Article type sentence:
- Target-journal scope sentence:
- Evidence-boundary sentence preserving the Open-v2 scope-bounded mechanism evidence, same-scope ranking boundary, and no confidence-interval, statistical-significance, or model-ranking claim wording:
- Public-source temporal-boundary sentence stating that public-source commands are reconstruction code paths rather than frozen source snapshots, and that exact Open-v2 numerical reproduction requires recorded acquisition dates or versions, input checksums, processing logs, and released derived artifacts rather than live API calls or changed public dumps:
- Corresponding author name used for signature:
- Artifact URL or DOI sentence:
- Declaration-status sentence covering funding, competing-interest, permissions, generative AI, data availability, and research data declarations and aligned with `submission_metadata.yml`:
- Generic `Dear Editor` greeting removed:
- Anonymous author signature removed:
- Anonymous preflight wording removed:
- Final cover letter checked by `check_final_upload_cover_letter`:

### Final cover letter sentence map

Use this sentence map only after the external values above are confirmed; do not copy the anonymous pre-submission cover letter into the live system.

| Letter unit | Source fields to use | Required boundary |
| --- | --- | --- |
| Greeting line | Use the confirmed `submission.target_journal` value and selected journal editor convention. | Do not use the generic `Dear Editor` greeting for final upload. |
| Submission sentence | Use `submission.title`, `submission.article_type`, and `submission.target_journal`. | State the final article type exactly as recorded in `submission_metadata.yml`. |
| Scope-fit sentence | Use `target_preparation.selected_author_guide_source`, target scope notes, and the paper's data-integration framing. | Treat the DKE-style route as scope-fit preparation unless the target is author-confirmed. |
| Evidence-boundary sentence | Reuse the bounded Open-v2 wording from the abstract and cover letter. | Do not claim broad superiority, Q2/B completion, or final-upload readiness. Also state that the evidence remains scope-bounded mechanism evidence rather than a same-scope comparative ranking, and do not present confidence intervals, statistical significance, or model-ranking claims unless validated artifacts support them. |
| Public-source temporal-boundary sentence | Use the Data and Code Availability boundary, `configs/source_input_manifest.json`, `logs/processing_run_log.jsonl`, and artifact-release provenance fields. | State that public-source commands are reconstruction code paths rather than frozen source snapshots, and that exact Open-v2 numerical reproduction requires recorded acquisition dates or versions, input checksums, processing logs, and released derived artifacts rather than live API calls or changed public dumps. |
| Artifact sentence | Use `artifact_boundary.artifact_release_url` or `artifact_boundary.artifact_release_doi`. | Do not cite an artifact link until the release validates against the final package. |
| Declaration sentence | Use funding, competing-interest, permissions, generative-AI, data, and research-data fields from `submission_metadata.yml`. | The sentence must match the live submission system and publisher declaration files. |
| Signature line | Use `corresponding_author.name` and confirmed author metadata. | Do not use `Anonymous Authors` in the final cover letter. |

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
- Elsevier declarations tool output required for the DKE/Elsevier route:
- Elsevier competing-interest declaration file path:
- Elsevier competing-interest declaration file must use `.doc` or `.docx`:
- Elsevier competing-interest declaration file verified against the live submission-system upload field:
- `publisher_declaration_files.elsevier_declarations_tool_required_before_upload`:
- `publisher_declaration_files.competing_interest_declaration_file`:
- `publisher_declaration_files.competing_interest_declaration_file_verified`:

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

For the DKE/Elsevier route, the research data statement must either link to the public artifact release or explain why research data cannot be shared. For this manuscript, use the artifact release route once the release URL or DOI exists; do not describe the Git repository alone as the full research data record.

- DKE/Elsevier research data statement option selected:
- Research data statement includes public artifact URL or DOI:
- Research data statement preserves raw third-party data redistribution boundary:
- Research data statement matches live submission-system data statement field:

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

### Artifact publication cross-check before final upload

Complete this cross-check before inserting an artifact URL or DOI into the final cover letter, research-data statement, or live submission-system fields.

- Public artifact URL or DOI resolves to the release landing page:
- Artifact manifest `publication` object matches `submission_metadata.yml`:
- Artifact manifest repository commit matches the final repository commit:
- `checksums.sha256` covers result files, source manifest, and processing logs:
- `configs/source_input_manifest.json` is included in the public release:
- `logs/processing_run_log.jsonl` is included in the public release:
- `python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release` passed:
- `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release` passed against the same release:

### Artifact processing provenance

- `configs/source_input_manifest.json` completed with source acquisition date or version, original provider, local file boundary, license boundary, safe relative local file names, and SHA256 checksums:
- `logs/processing_run_log.jsonl` completed with command line, environment summary, random seed or not_applicable, started_at, finished_at, input_manifest_reference, output_path, and exit_status:
- `python -m pip install -e .` run from final source checkout:
- `python -m iad_sieve.cli --help` run from final source checkout:
- Processing code path and release manifest commit match the final repository commit:
- Raw third-party data is not redistributed unless provider terms allow redistribution:

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
