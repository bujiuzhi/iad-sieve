# Submission System Checklist

Status date: 2026-06-23

## Scope

This checklist is a final-upload preparation file for the manuscript "IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication." It is not a manuscript file for journal upload. It should be used immediately before submitting through the selected journal system.

The checklist intentionally remains incomplete until the authors confirm the target journal, author order, corresponding author, journal template, and artifact release URL.

## Required Upload Files

| Upload role | Current source file | Final-upload requirement |
| --- | --- | --- |
| Main manuscript source | `main.tex` | Convert to the selected journal template and rebuild the PDF. |
| Main manuscript PDF | `build/iad-risk-manuscript-latex.pdf` | Rebuild after template conversion and author metadata insertion. |
| DKE/Elsevier preflight source | `build/iad-risk-manuscript-elsevier.tex` | Use only for Data & Knowledge Engineering preflight until authors confirm the final target. |
| DKE/Elsevier preflight PDF | `build/iad-risk-manuscript-elsevier.pdf` | Check template fit and table rendering; do not treat it as final upload proof. |
| Supplementary source | `supplementary_material.tex` | Keep claim boundaries, reproducibility levels, and artifact requirements aligned with the main manuscript. |
| Supplementary PDF | `build/iad-risk-supplementary-material.pdf` | Rebuild after any supplementary source changes. |
| Bibliography | `references.bib` | Confirm all cited references compile under the selected bibliography style. |
| Cover letter | `cover_letter.md` | Replace the generic greeting and add target-journal-specific fit only after journal selection. |
| Highlights | `highlights.md` | Keep 3--5 bullets, each at most 85 characters, if the selected journal uses Elsevier-style highlights. |
| Keywords | `keywords.md` | Keep 1--7 keywords for the current Elsevier candidate route unless the selected journal specifies otherwise. |
| Submission metadata | `submission_metadata.yml` | Fill target journal, `target_journal_template_bound`, target ranking/category confirmation fields, authors, corresponding author, funding statement text, author contribution statement, permissions statement, third-party material permission status, artifact URL, and final-upload checklist fields. |
| Author biographies and photographs | External author-provided files | For the DKE route, prepare short author biographies with a maximum 100 words, editable non-PDF biography files, and passport-type photographs as final-upload materials after author identities are confirmed; record the external file list under `author_identity_materials`. |
| Elsevier competing-interest declaration file | External author-provided `.doc` or `.docx` | For the DKE/Elsevier route, use the Elsevier declarations tool to generate the competing-interest Word document and record the path and verification status under `publisher_declaration_files`. |
| Artifact release manifest | `artifact_release_manifest.template.json` | Replace with the real release manifest, DOI or URL, and SHA256 checksum file. |

## Artifact Release Package Checks

Before linking an external artifact release, verify:

1. `python manuscript/scripts/build_artifact_release_skeleton.py --output-dir /path/to/release --repository-commit <commit>` creates the release scaffold before artifact files are copied.
2. The release directory contains `README.md`, `manifest.json`, `checksums.sha256`, `configs/`, `tables/`, `predictions/`, `reports/`, and `logs/`.
3. `python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only` checks required source artifact files before anything is copied.
4. `python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts` copies generated result files from the source artifact directory.
5. Required tables, predictions, reports, configs, and logs have replaced all skeleton placeholders.
6. `python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release` refreshes `manifest.json` and `checksums.sha256`.
7. `python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release` passes.
8. `python -m pip install -e .` is run from the same repository checkout named by the release manifest, and `python -m iad_sieve.cli --help` then passes from that environment.
9. `manifest.json` records the release commit, source-tree cleanliness, required artifact IDs, claim boundaries, and SHA256 values for required artifacts.
10. `manifest.json` contains a `publication` object whose `artifact_release_url`, `artifact_release_doi`, and `public_access_status` match the final-upload metadata and public release record.
11. `checksums.sha256` covers every release file except itself and matches the file contents.
12. `configs/source_input_manifest.json` records the original provider, acquisition date or version, local file boundary, license boundary, and SHA256 checksum for each public input, and the release redistributes derived tables, predictions, logs, manifests, and checksums rather than raw provider files unless original provider terms explicitly allow redistribution.
13. `open_v2_main_results` resolves to `tables/open_v2_main_results.csv` with per-row denominator counts, per-row threshold source, scope label used in the main table, automatic merge count, block count, defer count, automatic merge coverage, defer rate, and capacity-normalized review load.
14. `iad_risk_predictions`, `representation_baseline_scores`, and `supervised_baseline_predictions` resolve to JSONL files with `pair_id`, `source_document_id`, `target_document_id`, expected labels, label strength, hard-negative level, split identifiers, score or probability fields, `threshold_value` where applicable, threshold source, and `merge_prediction`.
15. `threshold_selection_logs` resolves to a JSONL file with system, threshold_name, `threshold_value`, selection_split, selection_metric, selection_rule, applied_scope, and `score_field`.
16. The release excludes `data/`, `outputs/`, cache files, credentials, raw third-party files, and model checkpoints.

## DKE/Elsevier Preflight Package Checks

Before using the DKE/Elsevier preflight package, verify:

1. `python manuscript/scripts/build_submission_package.py --dke-preflight` completes and writes `build/dke_preflight_package/`.
2. `python manuscript/scripts/validate_submission_package.py --dke-preflight` passes.
3. `build/iad-risk-dke-preflight-package.zip` contains `iad-risk-manuscript-elsevier.tex`, `iad-risk-manuscript-elsevier.pdf`, the generic LaTeX source files, submission text files, manifest, and checksums.
4. The DKE/Elsevier preflight package remains anonymous and does not include `data/`, `outputs/`, raw third-party files, local caches, credentials, artifact outputs, author emails, ORCID values, personal account URLs, local absolute paths, or development process notes.
5. Passing the DKE/Elsevier preflight package check does not complete the final-upload gate; author metadata, target confirmation, live submission-system fields, `live_submission_system_verified`, `final_upload_package_verified_against_system`, and artifact release URL or DOI remain required.

## Publisher Declaration Checks

Before upload, verify:

1. The declaration text matches submission_metadata.yml, the manuscript declaration sections, and the live submission system.
2. No declaration placeholder remains before final upload.
3. The funding role is stated when funding exists, including whether sponsors influenced study design, analysis, writing, or the decision to submit.
4. Permission files are listed when third-party permission is required.
5. The data availability statement matches artifact release status, including whether the release has a real URL or DOI.
6. The generative AI declaration records AI tool use status, author review and responsibility, AI authorship exclusion, and whether any machine-generated figures, images, or artwork are included.
7. DKE-specific author biographies with a maximum 100 words, editable biography files that must not be PDF, and passport-type photographs are prepared only after author identities are confirmed and are excluded from anonymous preflight packages.
8. For the DKE/Elsevier route, the Elsevier declarations tool has generated the competing-interest declaration file as `.doc` or `.docx`.
9. `publisher_declaration_files.competing_interest_declaration_file` and `publisher_declaration_files.competing_interest_declaration_file_verified` are completed before final upload.
10. `author_identity_materials`, `biography_files`, `photograph_files`, and `author_identity_materials_verified` are completed before `author_biographies_and_photos_ready` is marked true.

## Cover Letter Customization Checks

Before upload, verify:

1. The cover letter names the selected target journal.
2. The cover letter states the final article type.
3. The corresponding author name appears in the cover letter.
4. The artifact URL or DOI appears in the cover letter when available.
5. The cover letter keeps the Open-v2 evidence as scope-bounded mechanism evidence rather than a same-scope comparative ranking.
6. The cover letter does not present confidence intervals, statistical significance, or model-ranking claims unless the validated artifact package supports them.
7. The cover letter no longer uses the generic Dear Editor greeting.
8. The cover letter no longer uses an anonymous author signature.

## Source Archive Assembly Checks

Before upload, verify:

1. The source archive contains editable LaTeX sources, including the selected journal-template source and supplementary source when required.
2. The source archive includes references.bib and submission text files such as the cover letter, highlights, keywords, and metadata file when the journal system asks for them.
3. The source archive includes manifest and checksum files for files generated by the submission-package builder.
4. The source archive excludes build caches and generated zip files.
5. The source archive is rebuilt after template conversion, author metadata insertion, cover-letter customization, and artifact-link insertion.

## Source-Control Binding Checks

Before upload, verify:

1. The tracked source `submission_metadata.yml` can keep `repository_reference` blank before final upload.
2. `python manuscript/scripts/build_submission_package.py --final-upload` writes `repository_url`, `repository_commit`, and `repository_branch` into the package copy of `submission_metadata.yml`.
3. The package copy is bound to `git remote origin`, `git rev-parse HEAD`, and the current branch; `repository_url` must be a public non-placeholder HTTP/HTTPS URL and `repository_branch` must be `main`.
4. `submission_manifest.json` records the same `repository_commit` and `repository_branch` as the package copy of `submission_metadata.yml`.
5. `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release` passes after the package is built, the external artifact release is finalized, and the artifact manifest publication object records the same public artifact URL or DOI as `submission_metadata.yml`.

## Final Evidence-Chain Cross-Checks

Before changing live submission-system fields from preparatory values to final-upload values, verify both evidence chains below.

### Q2/B ranking cross-check before final upload

1. Selected journal name exactly matches `submission.target_journal`.
2. Selected journal ISSN or eISSN matches the ranking source lookup.
3. Ranking source category and reported value are captured in the evidence export or screenshot.
4. Ranking source access date is not later than the final upload date.
5. Responsible author has confirmed the ranking/category interpretation.
6. Final cover letter, metadata fields, and live-system first-screen text still avoid Q2/B-complete wording unless the ranking evidence packet is complete and validated.

### Artifact publication cross-check before final upload

1. The public artifact URL or DOI resolves to the release landing page.
2. The artifact manifest `publication` object matches `submission_metadata.yml`.
3. The manifest repository commit matches the final repository commit.
4. `checksums.sha256` covers result files, `configs/source_input_manifest.json`, and `logs/processing_run_log.jsonl`.
5. `python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release` and `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release` pass against the same release.

## Final Metadata Checks

Before upload, verify:

1. The selected target journal and article type match the submission system; `article_type` uses `research_article` for this manuscript and does not use `review_article`, `case_report`, or another article-type value unless the manuscript is rewritten and revalidated for that route.
2. `target_journal_template_bound` is true and the selected journal template matches the final manuscript source.
3. `selected_author_guide_source`, non-placeholder `selected_author_guide_source_url`, `selected_author_guide_rechecked_date`, and `selected_template_requirements_confirmed` are complete before final upload.
4. `ranking_confirmation_completed`, `ranking_confirmation_source`, non-placeholder `ranking_confirmation_source_url`, `ranking_confirmation_checked_date`, and `selected_target_author_confirmed` are complete before final upload.
5. The Q2/B ranking evidence packet records the selected journal ISSN or eISSN, ranking source type, subject category, reported category value, ranking source URL or institutional system URL, ranking source access date, evidence export or screenshot path, and responsible author confirmation; publisher CiteScore, Impact Factor, aims-and-scope text, and this checklist are screening evidence only.
6. `review_mode` records the live submission-system review setting whenever `review_mode_confirmed` is true. For single-anonymized routes such as DKE, Information Systems, or Scientometrics, `review_mode` uses an author-visible final-upload value such as `single_anonymized_with_final_author_identities` or `single_anonymized_author_visible_final_upload`; do not use `anonymous_review` or a generic `single_anonymized` value for final upload. The final title page and submission-system fields include author identities; the anonymous package is only a preflight package.
7. The author list, order, affiliations, ORCID values, and corresponding author match the title page.
8. The funding statement text is completed and matches the manuscript and submission system.
9. The author contribution statement is completed and matches the final author list.
10. The permissions statement records whether third-party material permission is not required or lists the permission files needed by the journal.
11. The generative AI declaration statement is complete and matches the selected journal's live submission field.
12. Author biographies and photographs are ready when the selected DKE/Elsevier route requests them, each biography has a maximum 100 words, each biography file uses an editable format and must not be PDF, and `author_identity_materials.biography_files`, `author_identity_materials.photograph_files`, and `author_identity_materials.author_identity_materials_verified` record the external materials.
13. The competing-interest statement, Elsevier competing-interest declaration file, data/code availability statement, and ethics statement are consistent across the manuscript and system fields.
14. The DKE/Elsevier research data statement field includes the same artifact URL or DOI as `submission_metadata.yml`, preserves the raw third-party data redistribution boundary, and is not replaced by a Git-only repository statement.
15. The artifact release URL or DOI resolves publicly or according to the journal's access policy, the artifact release URL is a public non-placeholder HTTP/HTTPS URL when a URL is used, and the artifact manifest `publication.public_access_status` records that public access state.
16. `live_submission_system_verified` and `final_upload_package_verified_against_system` are true only after the live submission system preview and final package contents match the current source package.
17. The manuscript does not claim human gold labels, broad method superiority, or threshold stability unless the corresponding artifact evidence exists.

## Live Submission Text Checks

Before upload, verify:

1. Title, abstract, keywords, and highlights are copied from the current source files.
2. The title and abstract match `main.tex` after journal-template conversion.
3. Keywords match `keywords.md` exactly unless the selected journal requires a documented wording change.
4. Highlights match `highlights.md` exactly unless the selected journal does not collect highlights.
5. The live submission system preview shows the same title, abstract, keywords, and highlights that appear in the source files.
6. Mark `submission_system_files_verified`, `live_submission_system_verified`, and `final_upload_package_verified_against_system` true only after these text fields, uploaded files, and the final package preview are checked in the live submission system.

## First-Screen Claim Lockdown Checks

Before upload, verify:

1. `cover_letter.md`, `highlights.md`, `keywords.md`, the abstract, and the conclusion describe the same problem, method, Open-v2 evidence snapshot, and claim boundary.
2. Any journal-specific cover-letter or highlight edit keeps the Open-v2 numbers scope-bounded and preserves the distinction between full pair scope and held-out test scope.
3. No first-screen material claims broad method superiority, SOTA ranking, statistical superiority, threshold stability, human-gold validation, Q2/B completion, final-upload readiness, or cluster-level deployment quality.
4. Artifact URL or DOI insertion does not upgrade the scientific claim unless the released artifact validates the corresponding optional evidence, such as bootstrap intervals, threshold grids, ablations, manual-validation slice, or cluster artifacts.
5. After any target-journal wording edit, rerun `python manuscript/scripts/validate_manuscript.py --strict-latex` and rebuild the submission package before upload.

## File Hygiene Checks

Before upload, verify:

1. No `data/`, `outputs/`, cache, local connection, credential, or raw third-party file is inside the upload package.
2. The uploaded source archive contains editable source files rather than only PDFs.
3. Anonymous pre-submission packages contain no author email addresses, ORCID values, personal account URLs, local absolute paths, or development process notes.
4. The manuscript PDF opens correctly and has no unresolved references, missing citations, or clipped tables.
5. The supplementary PDF opens correctly and has no stale text relative to `supplementary_material.tex`.
6. The checksums in the artifact release validate before citing artifact files in the manuscript.

## Hard Stop Rules Before Final Upload

Do not upload the manuscript package until all hard-stop conditions are cleared:

1. Target journal, selected author-guide source, template requirements, review mode, article type, and Q2/B or institutional ranking evidence are author-confirmed and recorded in `submission_metadata.yml`.
2. Final author identities, affiliations, corresponding author, CRediT contribution roles, funding statement, permissions statement, competing-interest declaration, generative AI declaration, and DKE/Elsevier biography and photograph materials are complete when the selected route requires them.
3. The selected journal source and PDF files are rebuilt from the current source tree, and the final source-control package records `repository_url`, `repository_commit`, and `repository_branch` with `repository_branch` equal to `main`.
4. A public artifact URL or DOI resolves, the external artifact release validates, and the artifact manifest `publication` object matches the final-upload metadata.
5. The live submission system preview has been checked against the current title, abstract, keywords, highlights, uploaded files, declaration fields, and final package contents.
6. No first-screen material, cover letter, metadata field, or live-system text claims Q2/B completion, final-upload readiness, broad method superiority, fixed-number reproducibility from Git alone, threshold stability, statistical superiority, human-gold validation, cluster-level deployment quality, or workload reduction unless the corresponding evidence package validates.
7. The Q2/B ranking cross-check and artifact publication cross-check are complete before final-upload package validation is treated as a pass condition.

## Current Blocking Items

- Target journal has not been author-confirmed.
- Target journal template has not been applied.
- Author and corresponding-author metadata are placeholders.
- Funding, author contribution, and third-party material permission declarations are not final.
- Generative AI declaration is not final.
- Final template-specific PDFs have not been rebuilt.
- Submission-system file upload has not been checked against a live journal system.
- Artifact release URL or DOI has not been created.

## Blocking Evidence Matrix

| Blocking item | Required evidence before final upload | Source field or file | Current status |
| --- | --- | --- | --- |
| Target journal and ranking/category confirmation | Author-confirmed selected journal, selected author-guide source URL, author-guide recheck date, and ranking/category source with checked date. | `submission_metadata.yml`: `final_upload_checklist.target_journal_selected`, `target_preparation.selected_author_guide_source`, `target_preparation.selected_author_guide_source_url`, `target_preparation.selected_author_guide_rechecked_date`, `target_preparation.ranking_confirmation_completed`, `target_preparation.ranking_confirmation_source_url`, `target_preparation.selected_target_author_confirmed`; `target_journal_shortlist.md`. | Pending author confirmation and ranking/category evidence; the DKE preflight guide source was rechecked on 2026-06-23, but this is source-freshness evidence only. |
| Journal template and rebuilt PDFs | Selected journal template is applied to the manuscript source, and final manuscript and supplementary PDFs are rebuilt from that source. | `submission_metadata.yml`: `submission.target_journal_template_bound`, `final_upload_checklist.target_journal_template_applied`, `final_upload_checklist.manuscript_pdf_rebuilt_after_template`, `final_upload_checklist.supplementary_pdf_rebuilt_after_template`; `build/`. | Pending selected-template binding and final rebuild. |
| Author identity metadata | Final author order, affiliations, corresponding author, ORCID values when used, biographies, and photographs are complete and match the title page and journal system. | `submission_metadata.yml`: `authors`, `corresponding_author`, `author_identity_materials.biography_files`, `author_identity_materials.photograph_files`, `author_identity_materials.author_identity_materials_verified`, `final_upload_checklist.author_metadata_completed`, `final_upload_checklist.author_biographies_and_photos_ready`. | Pending author-provided identity materials. |
| Publisher declarations | Funding, CRediT contribution, competing-interest, permission, data/code availability, ethics, generative AI declarations, and the Elsevier competing-interest declaration file match the manuscript and live submission fields. | `submission_metadata.yml`: `funding.funding_statement`, `author_contributions.contribution_statement`, `permissions.permissions_statement`, `generative_ai.declaration_statement`, `statements.*`, `publisher_declaration_files.competing_interest_declaration_file`, `publisher_declaration_files.competing_interest_declaration_file_verified`, `final_upload_checklist.funding_statement_text_ready`, `final_upload_checklist.contribution_statement_complete`, `final_upload_checklist.permissions_statement_complete`, `final_upload_checklist.generative_ai_declaration_complete`. | Pending author-approved declarations and Elsevier declaration file. |
| Artifact release and public reference | Real artifact release URL or DOI resolves, release manifest records the publication object, and checksums validate before the URL or DOI is cited in submission files. | `submission_metadata.yml`: `artifact_boundary.artifact_release_url`, `artifact_boundary.artifact_release_doi`, `artifact_boundary.artifact_release_required_before_final_upload`, `final_upload_checklist.artifact_release_prepared_or_linked`; `artifact_release_manifest.template.json`; external release manifest. | Pending real artifact release. |
| Live submission-system verification | Uploaded files, metadata fields, first-screen text, and final package preview are checked in the selected journal submission system. | `submission_metadata.yml`: `upload_preparation.live_submission_system_verified`, `upload_preparation.final_upload_package_verified_against_system`, `final_upload_checklist.submission_system_files_verified`, `final_upload_checklist.first_screen_claim_lockdown_confirmed`; `submission_system_checklist.md`. | Pending live system verification. |
