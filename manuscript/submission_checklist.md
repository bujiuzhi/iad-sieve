# Submission Checklist

## Problem Decomposition

The package must separate manuscript readiness from journal-template readiness. The manuscript can be reviewed as a conservative Q2/B-class draft, but final upload requirements depend on the selected journal.

## Current Submission Package

| Item | File | Status |
| --- | --- | --- |
| Main manuscript source | `main.tex` | Ready |
| Bibliography | `references.bib` | Ready |
| Formal compiled PDF | `build/iad-risk-manuscript-latex.pdf` | Ready |
| Cover letter draft | `cover_letter.md` | Ready |
| Package manifest | `MANIFEST.md` | Ready |
| Quality audit | `submission_quality_audit.md` | Ready |
| Build script | `scripts/build_latex_pdf.sh` | Ready |
| Audit script | `scripts/audit_manuscript.py` | Ready |

## Claim Boundaries

| Claim class | Submission decision |
| --- | --- |
| Identity-agenda confusion is a meaningful scholarly deduplication failure mode | Allowed |
| IAD-Risk separates identity evidence from agenda evidence and gates merge risk | Allowed |
| Open-v2 evidence supports targeted false-merge suppression | Allowed |
| OpenAlex/OpenCitations labels are human gold | Not allowed |
| The method is broadly superior across all scholarly domains | Not allowed |
| Human gold annotation is complete | Not allowed |

## Before Journal Upload

| Requirement | Why it remains journal-dependent |
| --- | --- |
| Journal class file or template | Some journals require a specific LaTeX class, bibliography style, and section order |
| Author names and affiliations | The current package uses anonymous placeholders |
| Corresponding author metadata | Required only when the target journal portal asks for it |
| Funding, ethics, and data availability wording | Journals differ in mandatory declaration format |
| Supplementary material upload | Depends on portal limits and whether artifact release is attached |

## Final Gate

The package is ready as a template-independent manuscript package. It becomes a final upload package after the selected journal template, author metadata, and journal-specific declaration wording are applied.
