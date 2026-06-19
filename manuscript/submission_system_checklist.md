# Submission System Checklist

Updated: 2026-06-19

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
| Author biographies and photographs | External author-provided files | For the DKE route, prepare short author biographies and passport-type photographs as final-upload materials after author identities are confirmed; record the external file list under `author_identity_materials`. |
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
8. `python -m iad_sieve.cli --help` passes from the same repository checkout named by the release manifest.
9. `manifest.json` records the release commit, source-tree cleanliness, required artifact IDs, claim boundaries, and SHA256 values for required artifacts.
10. `manifest.json` contains a `publication` object whose `artifact_release_url`, `artifact_release_doi`, and `public_access_status` match the final-upload metadata and public release record.
11. `checksums.sha256` covers every release file except itself and matches the file contents.
12. `open_v2_main_results` resolves to `tables/open_v2_main_results.csv` with per-row denominator counts, per-row threshold source, scope label used in the main table, automatic merge count, block count, defer count, automatic merge coverage, defer rate, and capacity-normalized review load.
13. `iad_risk_predictions`, `representation_baseline_scores`, and `supervised_baseline_predictions` resolve to JSONL files with `pair_id`, `source_document_id`, `target_document_id`, expected labels, label strength, hard-negative level, split identifiers, score or probability fields, `threshold_value` where applicable, threshold source, and `merge_prediction`.
14. `threshold_selection_logs` resolves to a JSONL file with system, threshold_name, `threshold_value`, selection_split, selection_metric, selection_rule, applied_scope, and `score_field`.
15. The release excludes `data/`, `outputs/`, cache files, credentials, raw third-party files, and model checkpoints.

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
7. DKE-specific author biographies and passport-type photographs are prepared only after author identities are confirmed and are excluded from anonymous preflight packages.
8. `author_identity_materials`, `biography_files`, `photograph_files`, and `author_identity_materials_verified` are completed before `author_biographies_and_photos_ready` is marked true.

## Cover Letter Customization Checks

Before upload, verify:

1. The cover letter names the selected target journal.
2. The cover letter states the final article type.
3. The corresponding author name appears in the cover letter.
4. The artifact URL or DOI appears in the cover letter when available.
5. The cover letter no longer uses the generic Dear Editor greeting.
6. The cover letter no longer uses an anonymous author signature.

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
3. The package copy is bound to `git remote origin`, `git rev-parse HEAD`, and the current branch; `repository_url` must be a public non-placeholder HTTP/HTTPS URL.
4. `submission_manifest.json` records the same `repository_commit` as the package copy of `submission_metadata.yml`.
5. `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release` passes after the package is built, the external artifact release is finalized, and the artifact manifest publication object records the same public artifact URL or DOI as `submission_metadata.yml`.

## Final Metadata Checks

Before upload, verify:

1. The selected target journal and article type match the submission system; `article_type` uses `research_article` for this manuscript and does not use `review_article`, `case_report`, or another article-type value unless the manuscript is rewritten and revalidated for that route.
2. `target_journal_template_bound` is true and the selected journal template matches the final manuscript source.
3. `selected_author_guide_source`, non-placeholder `selected_author_guide_source_url`, `selected_author_guide_rechecked_date`, and `selected_template_requirements_confirmed` are complete before final upload.
4. `ranking_confirmation_completed`, `ranking_confirmation_source`, non-placeholder `ranking_confirmation_source_url`, `ranking_confirmation_checked_date`, and `selected_target_author_confirmed` are complete before final upload.
5. For single-anonymized routes such as DKE, Information Systems, or Scientometrics, `review_mode` uses an author-visible final-upload value such as `single_anonymized_with_final_author_identities` or `single_anonymized_author_visible_final_upload`; do not use `anonymous_review` or a generic `single_anonymized` value for final upload. The final title page and submission-system fields include author identities; the anonymous package is only a preflight package.
6. The author list, order, affiliations, ORCID values, and corresponding author match the title page.
7. The funding statement text is completed and matches the manuscript and submission system.
8. The author contribution statement is completed and matches the final author list.
9. The permissions statement records whether third-party material permission is not required or lists the permission files needed by the journal.
10. The generative AI declaration statement is complete and matches the selected journal's live submission field.
11. Author biographies and photographs are ready when the selected DKE/Elsevier route requests them, and `author_identity_materials.biography_files`, `author_identity_materials.photograph_files`, and `author_identity_materials.author_identity_materials_verified` record the external materials.
12. The competing-interest statement, data/code availability statement, and ethics statement are consistent across the manuscript and system fields.
13. The artifact release URL or DOI resolves publicly or according to the journal's access policy, the artifact release URL is a public non-placeholder HTTP/HTTPS URL when a URL is used, and the artifact manifest `publication.public_access_status` records that public access state.
14. `live_submission_system_verified` and `final_upload_package_verified_against_system` are true only after the live submission system preview and final package contents match the current source package.
15. The manuscript does not claim human gold labels, broad method superiority, or threshold stability unless the corresponding artifact evidence exists.

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

## Current Blocking Items

- Target journal has not been author-confirmed.
- Target journal template has not been applied.
- Author and corresponding-author metadata are placeholders.
- Funding, author contribution, and third-party material permission declarations are not final.
- Generative AI declaration is not final.
- Final template-specific PDFs have not been rebuilt.
- Submission-system file upload has not been checked against a live journal system.
- Artifact release URL or DOI has not been created.
