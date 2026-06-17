# Journal Manuscript Package

## Scope

This directory is the single workspace for journal submission materials. It keeps the manuscript source, bibliography, build scripts, and generated PDFs separate from project documentation and experiment outputs.

## Files

```text
manuscript/
  main.tex
  references.bib
  scripts/
    audit_manuscript.py
    build_latex_pdf.sh
    build_preview_pdf.py
  build/
    iad-risk-manuscript-latex.pdf
    iad-risk-manuscript-preview.pdf
```

## Build

Formal LaTeX build:

```bash
cd manuscript
tectonic main.tex
mv main.pdf build/iad-risk-manuscript-latex.pdf
```

Preview PDF generated from the same manuscript text:

```bash
python manuscript/scripts/build_preview_pdf.py \
  --input manuscript/main.tex \
  --output manuscript/build/iad-risk-manuscript-preview.pdf
```

Quality gate:

```bash
python manuscript/scripts/audit_manuscript.py
```

## Submission Status

The draft is reviewer-facing and has a formal LaTeX PDF. It is still target-template pending: before journal submission, replace the generic `article` class with the selected journal template if required. The current evidence supports a conservative claim: IAD-Risk models identity-agenda confusion and reduces false-merge risk under stratified gold/proxy/silver evaluation. The draft must not claim broad method superiority or completed human gold annotation.
