#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEED="${1:-42}"
SAMPLE_SIZE="${2:-100000}"
if [[ "$#" -ge 3 ]]; then
  PRIMARY_CATEGORY="$3"
else
  PRIMARY_CATEGORY="${PRIMARY_CATEGORY:-cs.CL}"
fi

exec "${PROJECT_ROOT}/scripts/run_100k_sharded_experiment.sh" "${SAMPLE_SIZE}" "${SEED}" "${PRIMARY_CATEGORY}"
