#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
tectonic main.tex
mv main.pdf build/iad-risk-manuscript-latex.pdf
