# Journal Manuscript Package

## Scope

This directory is the single workspace for journal submission materials. It keeps the manuscript source, bibliography, build scripts, and generated PDFs separate from project documentation and experiment outputs.

## Files

```text
manuscript/
  main.tex
  references.bib
  cover_letter.md
  MANIFEST.md
  submission_checklist.md
  submission_quality_audit.md
  scripts/
    audit_manuscript.py
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

Quality gate:

```bash
python manuscript/scripts/audit_manuscript.py
```

## Submission Status

The draft is prepared as a journal manuscript and has a formal LaTeX PDF. It is still target-template pending: before journal submission, replace the generic `article` class with the selected journal template if required. The current evidence supports a conservative claim: IAD-Risk models identity-agenda confusion and reduces false-merge risk under stratified gold/proxy/silver evaluation. The draft must not claim broad method superiority or completed human gold annotation.
