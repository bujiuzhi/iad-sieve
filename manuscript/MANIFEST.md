# Manuscript Manifest

## Files

| Path | Purpose |
| --- | --- |
| `main.tex` | Main LaTeX manuscript |
| `supplementary_material.tex` | Supplementary reproducibility material |
| `references.bib` | Bibliography entries |
| `cover_letter.md` | Cover letter source |
| `highlights.md` | Submission highlights |
| `keywords.md` | Submission keywords |
| `scripts/validate_manuscript.py` | Manuscript package validation |
| `scripts/verify_fixture_rebuild.py` | No-network fixture rebuild verification |
| `scripts/build_submission_package.py` | Self-contained submission package builder |
| `scripts/validate_submission_package.py` | Submission package integrity validator |
| `scripts/build_latex_pdf.sh` | Formal LaTeX PDF build script |
| `build/iad-risk-manuscript-latex.pdf` | Formal compiled PDF |
| `build/iad-risk-supplementary-material.pdf` | Formal compiled supplementary PDF |

## Build Commands

```bash
python manuscript/scripts/validate_manuscript.py
python manuscript/scripts/verify_fixture_rebuild.py
python manuscript/scripts/build_submission_package.py
python manuscript/scripts/validate_submission_package.py
cd manuscript && ./scripts/build_latex_pdf.sh
```

## Submission Boundary

This package is template-independent. Before journal upload, adapt `main.tex` to the selected journal class file if required and set the author metadata according to the target journal's submission rules.
