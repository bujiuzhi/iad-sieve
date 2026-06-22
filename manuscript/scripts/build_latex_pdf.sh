#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p build
mkdir -p build/logs

run_and_log() {
  local log_path="$1"
  shift
  if "$@" >"$log_path" 2>&1; then
    cat "$log_path"
  else
    local status=$?
    cat "$log_path"
    return "$status"
  fi
}

run_tectonic() {
  local input_path="$1"
  if [[ -n "${TECTONIC_BUNDLE_DIR:-}" ]]; then
    tectonic --bundle "$TECTONIC_BUNDLE_DIR" "$input_path"
  else
    tectonic "$input_path"
  fi
}

run_and_log build/logs/main.log run_tectonic main.tex
mv main.pdf build/iad-risk-manuscript-latex.pdf
run_and_log build/logs/supplementary_material.log run_tectonic supplementary_material.tex
mv supplementary_material.pdf build/iad-risk-supplementary-material.pdf
run_and_log build/logs/elsevier_draft.log python scripts/build_elsevier_draft.py
python scripts/check_latex_warnings.py \
  --log build/logs/main.log \
  --log build/logs/supplementary_material.log \
  --log build/logs/elsevier_draft.log
python scripts/check_pdf_rendering.py \
  --pdf build/iad-risk-manuscript-latex.pdf \
  --pdf build/iad-risk-supplementary-material.pdf \
  --pdf build/iad-risk-manuscript-elsevier.pdf
