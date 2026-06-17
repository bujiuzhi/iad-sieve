#!/usr/bin/env bash
# 功能: 运行 main_100k 分片主实验，支持断点续跑。
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLE_SIZE="${1:-100000}"
SEED="${2:-42}"
if [[ "$#" -ge 3 ]]; then
  PRIMARY_CATEGORY="$3"
else
  PRIMARY_CATEGORY="${PRIMARY_CATEGORY:-cs.CL}"
fi

PYTHON_BIN="${PYTHON_BIN:-python}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-hashing-fallback}"
SHARD_COUNT="${SHARD_COUNT:-4}"
MAX_CANDIDATE_PER_DOCUMENT="${MAX_CANDIDATE_PER_DOCUMENT:-25}"
TITLE_MAX_BLOCK_SIZE="${TITLE_MAX_BLOCK_SIZE:-500}"
LEXICAL_MIN_SHARED_TOKENS="${LEXICAL_MIN_SHARED_TOKENS:-3}"
LEXICAL_MAX_POSTINGS_PER_TOKEN="${LEXICAL_MAX_POSTINGS_PER_TOKEN:-120}"
LEXICAL_MAX_NEIGHBORS_PER_TOKEN="${LEXICAL_MAX_NEIGHBORS_PER_TOKEN:-40}"
LEXICAL_MAX_CANDIDATE_PAIRS="${LEXICAL_MAX_CANDIDATE_PAIRS:-1500000}"
DENSE_TOP_K="${DENSE_TOP_K:-50}"
DENSE_BRUTE_FORCE_LIMIT="${DENSE_BRUTE_FORCE_LIMIT:-0}"
RECOMMENDATION_LIMIT="${RECOMMENDATION_LIMIT:-10}"
BOOTSTRAP_ITERATIONS="${BOOTSTRAP_ITERATIONS:-1000}"
BOOTSTRAP_CONFIDENCE_LEVEL="${BOOTSTRAP_CONFIDENCE_LEVEL:-0.95}"

RAW_FILE="${PROJECT_ROOT}/data/raw/arxiv-metadata-oai-snapshot.json"
SIZE_LABEL="${SAMPLE_SIZE}"
if [[ "${SAMPLE_SIZE}" == "100000" ]]; then
  SIZE_LABEL="100k"
fi

CATEGORY_SUFFIX=""
if [[ -n "${PRIMARY_CATEGORY}" ]]; then
  CATEGORY_SUFFIX="_${PRIMARY_CATEGORY//./_}"
fi

RUN_ID="${RUN_ID:-main_${SIZE_LABEL}${CATEGORY_SUFFIX}}"
SAMPLE_FILE="${PROJECT_ROOT}/data/samples/arxiv_${SIZE_LABEL}${CATEGORY_SUFFIX}.jsonl"
OUTPUT_DIR="${PROJECT_ROOT}/outputs/${RUN_ID}"
EMBEDDING_DIR="${OUTPUT_DIR}/embeddings"
REPORT_DIR="${OUTPUT_DIR}/reports"
ARTIFACT_DIR="${PROJECT_ROOT}/outputs/paper_artifacts_${RUN_ID}"

NORMALIZED_FILE="${OUTPUT_DIR}/normalized_documents.jsonl"
VIEWS_FILE="${OUTPUT_DIR}/semantic_views.jsonl"
CANDIDATES_FILE="${OUTPUT_DIR}/candidate_pairs.jsonl"
RELATIONS_FILE="${OUTPUT_DIR}/pair_relations.jsonl"
CANONICAL_FILE="${OUTPUT_DIR}/canonical_documents.jsonl"
DUPLICATE_GROUPS_FILE="${OUTPUT_DIR}/duplicate_groups.jsonl"
TOPIC_GRAPH_FILE="${OUTPUT_DIR}/topic_graph.jsonl"
CLUSTERS_FILE="${OUTPUT_DIR}/clusters.jsonl"
RANKINGS_FILE="${OUTPUT_DIR}/rankings.jsonl"
RECOMMENDATIONS_FILE="${OUTPUT_DIR}/recommendations.jsonl"
EVALUATION_REPORT_FILE="${REPORT_DIR}/evaluation_summary.md"
CANDIDATE_CAP_FILE="${REPORT_DIR}/candidate_cap_analysis.csv"
BOOTSTRAP_FILE="${REPORT_DIR}/bootstrap_confidence.csv"
ERROR_ANALYSIS_DIR="${REPORT_DIR}/error_analysis"
ERROR_ANALYSIS_SUMMARY_FILE="${ERROR_ANALYSIS_DIR}/error_analysis_summary.csv"
MANUAL_ANNOTATION_DIR="${REPORT_DIR}/manual_annotation"
MANUAL_ANNOTATION_SAMPLE_FILE="${ERROR_ANALYSIS_DIR}/manual_annotation_sample.jsonl"
MANUAL_ANNOTATION_SUMMARY_FILE="${MANUAL_ANNOTATION_DIR}/manual_annotation_summary.csv"

DEFAULT_QUERIES=(
  "semantic deduplication scientific papers"
  "scientific literature clustering recommendation"
  "relation separated duplicate detection"
  "survey of literature recommendation methods"
  "benchmark dataset for paper retrieval"
)

# 功能: 输出带时间戳的实验日志。
# 参数: 任意日志文本。
# 返回值: 无。
log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

# 功能: 输出错误并结束脚本。
# 参数: 错误说明文本。
# 返回值: 不返回，固定以 2 退出。
fail() {
  log "错误: $*"
  exit 2
}

# 功能: 判断文件是否存在且非空。
# 参数: 文件路径。
# 返回值: 文件存在且非空返回 0，否则返回 1。
file_ready() {
  [[ -s "$1" ]]
}

# 功能: 当目标文件不存在时执行生成命令。
# 参数: 第一个参数为目标文件，其余参数为待执行命令。
# 返回值: 命令执行结果；目标文件已存在时返回 0。
run_file_step() {
  local target_file="$1"
  shift
  if file_ready "${target_file}"; then
    log "跳过，产物已存在: ${target_file}"
    return 0
  fi
  log "开始生成: ${target_file}"
  "$@"
}

# 功能: 生成样本文件。
# 参数: 无。
# 返回值: 采样命令执行结果。
prepare_sample() {
  local prepare_args=(
    -m iad_sieve.cli prepare-sample
    --input "${RAW_FILE}"
    --output "${SAMPLE_FILE}"
    --sample-size "${SAMPLE_SIZE}"
    --seed "${SEED}"
  )
  if [[ -n "${PRIMARY_CATEGORY}" ]]; then
    prepare_args+=(--primary-category "${PRIMARY_CATEGORY}")
  fi
  run_file_step "${SAMPLE_FILE}" "${PYTHON_BIN}" "${prepare_args[@]}"
}

# 功能: 并行评分候选关系分片并合并为单文件。
# 参数: 无。
# 返回值: 全部分片评分与合并成功返回 0。
score_relation_shards() {
  if file_ready "${RELATIONS_FILE}"; then
    log "跳过，产物已存在: ${RELATIONS_FILE}"
    return 0
  fi

  local pids=()
  local shard_index
  for ((shard_index = 0; shard_index < SHARD_COUNT; shard_index += 1)); do
    local shard_file="${OUTPUT_DIR}/pair_relations_shard_${shard_index}.jsonl"
    if file_ready "${shard_file}"; then
      log "跳过，关系分片已存在: ${shard_file}"
      continue
    fi
    log "启动关系评分分片: ${shard_index}/${SHARD_COUNT}"
    (
      "${PYTHON_BIN}" -m iad_sieve.cli score-relations \
        --input "${NORMALIZED_FILE}" \
        --views "${VIEWS_FILE}" \
        --candidates "${CANDIDATES_FILE}" \
        --embedding-dir "${EMBEDDING_DIR}" \
        --output "${shard_file}" \
        --shard-count "${SHARD_COUNT}" \
        --shard-index "${shard_index}"
    ) &
    pids+=("$!")
  done

  local pid
  for pid in "${pids[@]}"; do
    wait "${pid}"
  done

  local merged_file="${RELATIONS_FILE}.tmp"
  : > "${merged_file}"
  for ((shard_index = 0; shard_index < SHARD_COUNT; shard_index += 1)); do
    local shard_file="${OUTPUT_DIR}/pair_relations_shard_${shard_index}.jsonl"
    file_ready "${shard_file}" || fail "关系分片缺失或为空: ${shard_file}"
    cat "${shard_file}" >> "${merged_file}"
  done
  mv "${merged_file}" "${RELATIONS_FILE}"
  log "关系分片合并完成: ${RELATIONS_FILE}"
}

# 功能: 对默认查询集分别推荐并合并结果。
# 参数: 无。
# 返回值: 推荐命令和合并成功返回 0。
build_recommendations() {
  if file_ready "${RECOMMENDATIONS_FILE}"; then
    log "跳过，产物已存在: ${RECOMMENDATIONS_FILE}"
    return 0
  fi

  local merged_file="${RECOMMENDATIONS_FILE}.tmp"
  : > "${merged_file}"
  local query_index=0
  local query_text
  for query_text in "${DEFAULT_QUERIES[@]}"; do
    local part_file="${OUTPUT_DIR}/recommendations_query_${query_index}.jsonl"
    "${PYTHON_BIN}" -m iad_sieve.cli recommend \
      --input "${CANONICAL_FILE}" \
      --rankings "${RANKINGS_FILE}" \
      --query "${query_text}" \
      --limit "${RECOMMENDATION_LIMIT}" \
      --output "${part_file}"
    cat "${part_file}" >> "${merged_file}"
    query_index=$((query_index + 1))
  done
  mv "${merged_file}" "${RECOMMENDATIONS_FILE}"
  log "推荐结果合并完成: ${RECOMMENDATIONS_FILE}"
}

mkdir -p "${PROJECT_ROOT}/data/samples" "${OUTPUT_DIR}" "${REPORT_DIR}"

if [[ ! -f "${RAW_FILE}" ]]; then
  fail "缺少原始数据: ${RAW_FILE}"
fi

log "实验参数: run_id=${RUN_ID}, sample_size=${SAMPLE_SIZE}, primary_category=${PRIMARY_CATEGORY:-none}, shard_count=${SHARD_COUNT}, max_candidate_per_document=${MAX_CANDIDATE_PER_DOCUMENT}"

prepare_sample

run_file_step "${NORMALIZED_FILE}" "${PYTHON_BIN}" -m iad_sieve.cli preprocess \
  --input "${SAMPLE_FILE}" \
  --output "${NORMALIZED_FILE}" \
  --seed "${SEED}"

run_file_step "${VIEWS_FILE}" "${PYTHON_BIN}" -m iad_sieve.cli build-views \
  --input "${NORMALIZED_FILE}" \
  --output "${VIEWS_FILE}" \
  --seed "${SEED}"

run_file_step "${EMBEDDING_DIR}/embeddings.npy" "${PYTHON_BIN}" -m iad_sieve.cli embed \
  --input "${NORMALIZED_FILE}" \
  --output-dir "${EMBEDDING_DIR}" \
  --embedding-model "${EMBEDDING_MODEL}" \
  --seed "${SEED}"

run_file_step "${CANDIDATES_FILE}" "${PYTHON_BIN}" -m iad_sieve.cli generate-candidates \
  --input "${NORMALIZED_FILE}" \
  --views "${VIEWS_FILE}" \
  --embedding-dir "${EMBEDDING_DIR}" \
  --output "${CANDIDATES_FILE}" \
  --max-candidate-per-document "${MAX_CANDIDATE_PER_DOCUMENT}" \
  --title-max-block-size "${TITLE_MAX_BLOCK_SIZE}" \
  --lexical-min-shared-tokens "${LEXICAL_MIN_SHARED_TOKENS}" \
  --lexical-max-postings-per-token "${LEXICAL_MAX_POSTINGS_PER_TOKEN}" \
  --lexical-max-neighbors-per-token "${LEXICAL_MAX_NEIGHBORS_PER_TOKEN}" \
  --lexical-max-candidate-pairs "${LEXICAL_MAX_CANDIDATE_PAIRS}" \
  --dense-top-k "${DENSE_TOP_K}" \
  --dense-brute-force-limit "${DENSE_BRUTE_FORCE_LIMIT}" \
  --seed "${SEED}"

score_relation_shards

run_file_step "${CANONICAL_FILE}" "${PYTHON_BIN}" -m iad_sieve.cli merge-duplicates \
  --input "${NORMALIZED_FILE}" \
  --relations "${RELATIONS_FILE}" \
  --output-dir "${OUTPUT_DIR}" \
  --seed "${SEED}"

run_file_step "${TOPIC_GRAPH_FILE}" "${PYTHON_BIN}" -m iad_sieve.cli build-topic-graph \
  --relations "${RELATIONS_FILE}" \
  --output "${TOPIC_GRAPH_FILE}" \
  --seed "${SEED}"

run_file_step "${CLUSTERS_FILE}" "${PYTHON_BIN}" -m iad_sieve.cli cluster \
  --input "${CANONICAL_FILE}" \
  --topic-graph "${TOPIC_GRAPH_FILE}" \
  --output-dir "${OUTPUT_DIR}" \
  --seed "${SEED}"

run_file_step "${RANKINGS_FILE}" "${PYTHON_BIN}" -m iad_sieve.cli rank \
  --input "${CANONICAL_FILE}" \
  --output "${RANKINGS_FILE}" \
  --seed "${SEED}"

build_recommendations

run_file_step "${EVALUATION_REPORT_FILE}" "${PYTHON_BIN}" -m iad_sieve.cli evaluate \
  --output-dir "${REPORT_DIR}" \
  --duplicate-groups "${DUPLICATE_GROUPS_FILE}" \
  --relations "${RELATIONS_FILE}" \
  --clusters "${CLUSTERS_FILE}" \
  --rankings "${RANKINGS_FILE}" \
  --recommendations "${RECOMMENDATIONS_FILE}"

run_file_step "${CANDIDATE_CAP_FILE}" "${PYTHON_BIN}" -m iad_sieve.cli analyze-candidate-cap \
  --relations "${RELATIONS_FILE}" \
  --output "${CANDIDATE_CAP_FILE}" \
  --candidate-caps "1,3,5,10,25,50,100"

run_file_step "${BOOTSTRAP_FILE}" "${PYTHON_BIN}" -m iad_sieve.cli run-bootstrap \
  --relations "${RELATIONS_FILE}" \
  --output "${BOOTSTRAP_FILE}" \
  --iterations "${BOOTSTRAP_ITERATIONS}" \
  --confidence-level "${BOOTSTRAP_CONFIDENCE_LEVEL}" \
  --seed "${SEED}"

run_file_step "${ERROR_ANALYSIS_SUMMARY_FILE}" "${PYTHON_BIN}" -m iad_sieve.cli export-error-analysis \
  --relations "${RELATIONS_FILE}" \
  --documents "${NORMALIZED_FILE}" \
  --output-dir "${ERROR_ANALYSIS_DIR}" \
  --max-cases-per-bucket 50 \
  --annotation-sample-size 100 \
  --seed "${SEED}"

run_file_step "${MANUAL_ANNOTATION_SUMMARY_FILE}" "${PYTHON_BIN}" -m iad_sieve.cli score-manual-annotations \
  --input "${MANUAL_ANNOTATION_SAMPLE_FILE}" \
  --output-dir "${MANUAL_ANNOTATION_DIR}"

run_file_step "${ARTIFACT_DIR}/tables/run_summary.csv" "${PYTHON_BIN}" -m iad_sieve.cli export-paper-artifacts \
  --input "${OUTPUT_DIR}" \
  --output-dir "${ARTIFACT_DIR}"

log "main_100k 分片主实验完成: ${OUTPUT_DIR}"
