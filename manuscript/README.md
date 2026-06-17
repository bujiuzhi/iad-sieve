# Journal Manuscript Package

## Scope

This directory contains the journal manuscript source, bibliography, build scripts, and compiled PDF. It is separate from project documentation and experiment outputs.

## Files

```text
manuscript/
  main.tex
  references.bib
  cover_letter.md
  MANIFEST.md
  scripts/
    validate_manuscript.py
    build_latex_pdf.sh
  build/
    iad-risk-manuscript-latex.pdf
```

## Build

Formal LaTeX build:

```bash
cd manuscript
tectonic main.tex
mv main.pdf build/iad-risk-manuscript-latex.pdf
```

Manuscript validation:

```bash
python manuscript/scripts/validate_manuscript.py
```

## Submission Boundary

The manuscript uses a template-independent LaTeX source. Before journal upload, adapt `main.tex` to the selected journal class file if required and replace anonymous placeholders with the target journal's required author metadata. The evidence supports a conservative claim: IAD-Risk models identity-agenda confusion and reduces false-merge risk under stratified gold/proxy/silver evaluation. The manuscript must not claim broad method superiority or completed human gold annotation.
