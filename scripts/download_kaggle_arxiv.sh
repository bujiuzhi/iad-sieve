#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_DIR="${PROJECT_ROOT}/data/raw"
DATASET_NAME="${1:-Cornell-University/arxiv}"

mkdir -p "${RAW_DIR}"

if ! command -v kaggle >/dev/null 2>&1; then
  echo "kaggle CLI 未安装。请先在当前环境安装 kaggle，并在用户目录配置 Kaggle 凭据。"
  exit 1
fi

echo "下载 Kaggle arXiv metadata 到 ${RAW_DIR}"
kaggle datasets download -d "${DATASET_NAME}" -p "${RAW_DIR}" --unzip

if [[ ! -f "${RAW_DIR}/arxiv-metadata-oai-snapshot.json" ]]; then
  echo "未找到 ${RAW_DIR}/arxiv-metadata-oai-snapshot.json"
  exit 1
fi

echo "下载完成: ${RAW_DIR}/arxiv-metadata-oai-snapshot.json"
