# Manuscript Manifest

## Files

| Path | Purpose |
| --- | --- |
| `main.tex` | Main LaTeX manuscript |
| `supplementary_material.tex` | Supplementary reproducibility material |
| `references.bib` | Bibliography entries |
| `cover_letter.md` | Cover letter source |
| `scripts/validate_manuscript.py` | Manuscript package validation |
| `scripts/build_latex_pdf.sh` | Formal LaTeX PDF build script |
| `build/iad-risk-manuscript-latex.pdf` | Formal compiled PDF |
| `build/iad-risk-supplementary-material.pdf` | Formal compiled supplementary PDF |

## Build Commands

```bash
python manuscript/scripts/validate_manuscript.py
cd manuscript && ./scripts/build_latex_pdf.sh
```

## Submission Boundary

This package is template-independent. Before journal upload, adapt `main.tex` to the selected journal class file if required and set the author metadata according to the target journal's submission rules.
