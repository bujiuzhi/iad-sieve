#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLE_SIZE="${1:-1000}"
SEED="${2:-42}"
PRIMARY_CATEGORY="${3:-}"
RAW_FILE="${PROJECT_ROOT}/data/raw/arxiv-metadata-oai-snapshot.json"
SAMPLE_FILE="${PROJECT_ROOT}/data/samples/arxiv_${SAMPLE_SIZE}.jsonl"
OUTPUT_DIR="${PROJECT_ROOT}/outputs/dev_${SAMPLE_SIZE}"
PYTHON_BIN="${PYTHON_BIN:-python}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-hashing-fallback}"

mkdir -p "${PROJECT_ROOT}/data/samples" "${OUTPUT_DIR}"

if [[ ! -f "${RAW_FILE}" ]]; then
  echo "缺少原始数据: ${RAW_FILE}"
  echo "请将 arxiv-metadata-oai-snapshot.json 放到项目 data/raw 目录。"
  exit 2
fi

PREPARE_ARGS=(
  -m iad_sieve.cli prepare-sample
  --input "${RAW_FILE}"
  --output "${SAMPLE_FILE}"
  --sample-size "${SAMPLE_SIZE}"
  --seed "${SEED}"
)

if [[ -n "${PRIMARY_CATEGORY}" ]]; then
  PREPARE_ARGS+=(--primary-category "${PRIMARY_CATEGORY}")
fi

"${PYTHON_BIN}" "${PREPARE_ARGS[@]}"

"${PYTHON_BIN}" -m iad_sieve.cli run-pipeline \
  --input "${SAMPLE_FILE}" \
  --run-id "dev_${SAMPLE_SIZE}" \
  --output-dir "${OUTPUT_DIR}" \
  --embedding-model "${EMBEDDING_MODEL}" \
  --seed "${SEED}" \
  --max-candidate-per-document 100 \
  --title-max-block-size 500 \
  --lexical-min-shared-tokens 3 \
  --lexical-max-postings-per-token 120 \
  --lexical-max-neighbors-per-token 40 \
  --lexical-max-candidate-pairs 500000 \
  --dense-top-k 50 \
  --dense-brute-force-limit 0

echo "实验完成: ${OUTPUT_DIR}"
