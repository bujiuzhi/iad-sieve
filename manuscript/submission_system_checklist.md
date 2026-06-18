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
| Supplementary source | `supplementary_material.tex` | Keep claim boundaries, reproducibility levels, and artifact requirements aligned with the main manuscript. |
| Supplementary PDF | `build/iad-risk-supplementary-material.pdf` | Rebuild after any supplementary source changes. |
| Bibliography | `references.bib` | Confirm all cited references compile under the selected bibliography style. |
| Cover letter | `cover_letter.md` | Replace the generic greeting and add target-journal-specific fit only after journal selection. |
| Highlights | `highlights.md` | Keep 3--5 bullets, each at most 85 characters, if the selected journal uses Elsevier-style highlights. |
| Keywords | `keywords.md` | Keep 1--7 keywords for the current Elsevier candidate route unless the selected journal specifies otherwise. |
| Submission metadata | `submission_metadata.yml` | Fill target journal, authors, corresponding author, funding, artifact URL, and final-upload checklist fields. |
| Artifact release manifest | `artifact_release_manifest.template.json` | Replace with the real release manifest, DOI or URL, and SHA256 checksum file. |

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
3. The manuscript PDF opens correctly and has no unresolved references, missing citations, or clipped tables.
4. The supplementary PDF opens correctly and has no stale text relative to `supplementary_material.tex`.
5. The checksums in the artifact release validate before citing artifact files in the manuscript.

## Current Blocking Items

- Target journal has not been author-confirmed.
- Target journal template has not been applied.
- Author and corresponding-author metadata are placeholders.
- Final template-specific PDFs have not been rebuilt.
- Submission-system file upload has not been checked against a live journal system.
- Artifact release URL or DOI has not been created.
