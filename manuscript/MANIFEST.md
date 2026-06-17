# Manuscript Manifest

## Files

| Path | Purpose |
| --- | --- |
| `main.tex` | Main LaTeX manuscript |
| `references.bib` | Bibliography entries |
| `cover_letter.md` | Generic cover letter draft |
| `submission_checklist.md` | Final pre-upload checklist |
| `submission_quality_audit.md` | Claim and readiness audit |
| `scripts/audit_manuscript.py` | Manuscript package audit |
| `scripts/build_latex_pdf.sh` | Formal LaTeX PDF build script |
| `build/iad-risk-manuscript-latex.pdf` | Formal compiled PDF |

## Build Commands

```bash
python manuscript/scripts/audit_manuscript.py
cd manuscript && ./scripts/build_latex_pdf.sh
```

## Submission Boundary

This package is template-independent. Before journal upload, adapt `main.tex` to the selected journal class file if required and replace anonymous placeholders with the target journal's required author metadata.
