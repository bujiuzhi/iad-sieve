# Submission System Checklist

Updated: 2026-06-18

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
| Submission metadata | `submission_metadata.yml` | Fill target journal, authors, corresponding author, funding, artifact URL, and final-upload checklist fields. |
| Artifact release manifest | `artifact_release_manifest.template.json` | Replace with the real release manifest, DOI or URL, and SHA256 checksum file. |

## Artifact Release Package Checks

Before linking an external artifact release, verify:

1. `python manuscript/scripts/build_artifact_release_skeleton.py --output-dir /path/to/release --repository-commit <commit>` creates the release scaffold before artifact files are copied.
2. The release directory contains `README.md`, `manifest.json`, `checksums.sha256`, `configs/`, `tables/`, `predictions/`, `reports/`, and `logs/`.
3. Required tables, predictions, reports, configs, and logs have replaced all skeleton placeholders.
4. `python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release` refreshes `manifest.json` and `checksums.sha256`.
5. `python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release` passes.
6. `manifest.json` records the release commit, source-tree cleanliness, required artifact IDs, claim boundaries, and SHA256 values for required artifacts.
7. `checksums.sha256` covers every release file except itself and matches the file contents.
8. The release excludes `data/`, `outputs/`, cache files, credentials, raw third-party files, and model checkpoints.

## DKE/Elsevier Preflight Package Checks

Before using the DKE/Elsevier preflight package, verify:

1. `python manuscript/scripts/build_submission_package.py --dke-preflight` completes and writes `build/dke_preflight_package/`.
2. `python manuscript/scripts/validate_submission_package.py --dke-preflight` passes.
3. `build/iad-risk-dke-preflight-package.zip` contains `iad-risk-manuscript-elsevier.tex`, `iad-risk-manuscript-elsevier.pdf`, the generic LaTeX source files, submission text files, manifest, and checksums.
4. The DKE/Elsevier preflight package remains anonymous and does not include `data/`, `outputs/`, raw third-party files, local caches, credentials, artifact outputs, author emails, ORCID values, personal account URLs, local absolute paths, or tool-generated process notes.
5. Passing the DKE/Elsevier preflight package check does not complete the final-upload gate; author metadata, target confirmation, live submission-system fields, and artifact release URL or DOI remain required.

## Final Metadata Checks

Before upload, verify:

1. The selected target journal and article type match the submission system.
2. The author list, order, affiliations, ORCID values, and corresponding author match the title page.
3. The funding statement, competing-interest statement, data/code availability statement, and ethics statement are consistent across the manuscript and system fields.
4. The artifact release URL or DOI resolves publicly or according to the journal's access policy.
5. The manuscript does not claim human gold labels, broad method superiority, or threshold stability unless the corresponding artifact evidence exists.

## File Hygiene Checks

Before upload, verify:

1. No `data/`, `outputs/`, cache, local connection, credential, or raw third-party file is inside the upload package.
2. The uploaded source archive contains editable source files rather than only PDFs.
3. Anonymous pre-submission packages contain no author email addresses, ORCID values, personal account URLs, local absolute paths, or tool-generated process notes.
4. The manuscript PDF opens correctly and has no unresolved references, missing citations, or clipped tables.
5. The supplementary PDF opens correctly and has no stale text relative to `supplementary_material.tex`.
6. The checksums in the artifact release validate before citing artifact files in the manuscript.

## Current Blocking Items

- Target journal has not been author-confirmed.
- Target journal template has not been applied.
- Author and corresponding-author metadata are placeholders.
- Final template-specific PDFs have not been rebuilt.
- Submission-system file upload has not been checked against a live journal system.
- Artifact release URL or DOI has not been created.
