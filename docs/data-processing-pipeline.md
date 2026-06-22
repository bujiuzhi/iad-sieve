# 数据处理流水线

## 文档范围

远程仓库不提交原始数据时，复现能力不能依赖口头说明。仓库必须保留可复查的数据处理代码、CLI 入口、输入输出契约、小型 fixture 和正式 artifact 发布规则。

本项目的数据处理目标分为两类：一类是把公开来源转换为统一的 `eval_documents.jsonl` 与 `eval_pairs.jsonl`；另一类是把多个来源合并为带 provenance、label strength 和 split 的 IAD-Bench 契约文件。

## 仓库边界

本仓库不提交 `data/` 下的真实原始数据，也不提交 `outputs/` 下的实验产物；但保留了从公开原始数据到 IAD-Bench 的处理代码和可运行 CLI。第三方复现时应自行获取公开来源数据，把文件放入本地 `data/raw/`，再按本文命令生成 `data/processed/` 或 `outputs/` 产物。

## 代码入口

| 模块 | 职责 |
| --- | --- |
| `src/iad_sieve/data/arxiv_loader.py` | 读取 arXiv metadata dump 并输出统一记录 |
| `src/iad_sieve/data/sampler.py` | 对 arXiv metadata 做流式抽样和分类过滤 |
| `src/iad_sieve/evaluation/deepmatcher_adapter.py` | 转换 DeepMatcher / py_entitymatching gold 数据 |
| `src/iad_sieve/evaluation/scirepeval_adapter.py` | 转换 SciRepEval / SciDocs proximity proxy 数据 |
| `src/iad_sieve/evaluation/openalex_api_ingestion.py` | 从 OpenAlex Works API 拉取公开 works 记录 |
| `src/iad_sieve/evaluation/openalex_adapter.py` | 构造 OpenAlex / OpenCitations weak-label pair |
| `src/iad_sieve/evaluation/iad_bench_builder.py` | 合并多来源 eval set，生成 IAD-Bench 文档、pair、split 和 summary |

统一 CLI 入口：

```bash
python -m iad_sieve.cli --help
```

## 无网络最小复现

`tests/fixtures/` 保留极小样本，用于验证数据处理代码路径和输出契约。该流程不依赖外部网络，也不代表论文主实验规模。

```bash
python -m iad_sieve.cli prepare-deepmatcher \
  --table-a tests/fixtures/deepmatcher/tableA.csv \
  --table-b tests/fixtures/deepmatcher/tableB.csv \
  --pairs tests/fixtures/deepmatcher/test.csv \
  --dataset-name deepmatcher_fixture \
  --output-dir outputs/repro_fixture/deepmatcher

python -m iad_sieve.cli prepare-scirepeval-proximity \
  --metadata tests/fixtures/scirepeval/metadata.jsonl \
  --pairs tests/fixtures/scirepeval/scidocs_cite_pairs.csv \
  --dataset-name scirepeval_fixture \
  --output-dir outputs/repro_fixture/scirepeval

python -m iad_sieve.cli prepare-openalex-weak-labels \
  --works tests/fixtures/openalex/works.jsonl \
  --citations tests/fixtures/openalex/coci.csv \
  --dataset-name openalex_fixture \
  --output-dir outputs/repro_fixture/openalex \
  --min-shared-references 1 \
  --max-pairs 20

python -m iad_sieve.cli build-iad-bench \
  --source-dirs \
    outputs/repro_fixture/deepmatcher \
    outputs/repro_fixture/scirepeval \
    outputs/repro_fixture/openalex \
  --output-dir outputs/repro_fixture/iad_bench \
  --seed 42
```

期望输出：

```text
outputs/repro_fixture/
  deepmatcher/
    eval_documents.jsonl
    eval_pairs.jsonl
    dataset_summary.jsonl
  scirepeval/
    eval_documents.jsonl
    eval_pairs.jsonl
    dataset_summary.jsonl
  openalex/
    eval_documents.jsonl
    eval_pairs.jsonl
    dataset_summary.jsonl
  iad_bench/
    iad_bench_documents.jsonl
    iad_bench_pairs.jsonl
    iad_bench_splits.jsonl
    iad_bench_summary.jsonl
```

## 公开数据处理流程

真实复现时，本地目录建议如下：

```text
data/
  raw/
    arxiv/
    deepmatcher/
    scirepeval/
    openalex/
    opencitations/
  processed/
    eval_sources/
    iad_bench/
```

这些真实数据目录不进入 Git。提交仓库时只保留 `data/README.md` 和处理代码。

## L2 重建审计文件

第三方不拿到仓库中的原始数据时，正式复验不能只依赖命令文本。公开来源重建应同步生成或整理以下审计文件，并在外部 artifact release 中用 checksum 固定。

| 文件 | 内容 | 用途 |
| --- | --- | --- |
| `configs/source_input_manifest.json` | 来源名称、获取日期或版本、原始提供方、安全相对本地文件边界、记录数、许可边界和有效输入文件 SHA256。 | 说明使用的是可识别公开输入，而不是仓库中隐藏的私有数据。 |
| `logs/processing_run_log.jsonl` | 每个阶段的 CLI 命令、与 artifact `manifest.json` `repository.commit` 一致的代码提交、环境摘要、随机种子、开始/结束时间、输入 manifest 引用、进入 `checksums.sha256` 的输出路径和 `exit_status=0`。 | 说明数据转换和 IAD-Bench 组装在固定源码版本下成功执行。 |
| `reports/iad_bench_split_summary.jsonl` | 文档数、pair 数、split 分布、label strength 分布和来源覆盖。 | 说明派生评估包与论文报告的范围一致。 |
| `checksums.sha256` | 所有可发布派生文件、日志、配置和报告的 SHA256。 | 让审稿人能验证 artifact release 未被后续替换。 |

这些文件不要求把 raw third-party data 放进 Git。它们用于记录从公开来源到派生评估产物的 chain of custody；缺少这些文件时，只能说明代码路径可运行，不能支持论文主结果的逐行数值复核。

## arXiv 样本处理

arXiv metadata 可用于端到端开发实验，不作为 IAD-Bench gold label 来源。

```bash
scripts/download_kaggle_arxiv.sh

python -m iad_sieve.cli prepare-sample \
  --input data/raw/arxiv-metadata-oai-snapshot.json \
  --output data/processed/arxiv_cs_cl_sample.jsonl \
  --sample-size 1000 \
  --seed 42 \
  --primary-category cs.CL

python -m iad_sieve.cli preprocess \
  --input data/processed/arxiv_cs_cl_sample.jsonl \
  --output data/processed/arxiv_cs_cl_normalized.jsonl
```

## DeepMatcher gold 数据

DeepMatcher / py_entitymatching structured benchmarks 提供明确的 match label，适合作为 `same_work` / `unrelated` gold 来源。第三方应从原始公开来源获取 `tableA.csv`、`tableB.csv` 和 `train.csv`、`valid.csv` 或 `test.csv`。

```bash
python -m iad_sieve.cli prepare-deepmatcher \
  --table-a data/raw/deepmatcher/DBLP-ACM/tableA.csv \
  --table-b data/raw/deepmatcher/DBLP-ACM/tableB.csv \
  --pairs data/raw/deepmatcher/DBLP-ACM/test.csv \
  --dataset-name DBLP-ACM \
  --output-dir data/processed/eval_sources/deepmatcher_dblp_acm
```

输出契约：

- `eval_documents.jsonl`：统一文献记录。
- `eval_pairs.jsonl`：带 gold label 的文献 pair。
- `dataset_summary.jsonl`：来源、样本数和标签分布摘要。

## SciRepEval / SciDocs proxy 数据

SciRepEval / SciDocs proximity 只能作为 same-agenda proxy，不应表述为人工实体匹配 gold。

```bash
python -m iad_sieve.cli prepare-scirepeval-proximity \
  --metadata data/raw/scirepeval/metadata.jsonl \
  --pairs data/raw/scirepeval/scidocs_cite_pairs.csv \
  --dataset-name scidocs_cite \
  --output-dir data/processed/eval_sources/scirepeval_scidocs_cite \
  --min-relevance-score 1.0
```

## OpenAlex / OpenCitations weak label 数据

OpenAlex Works 可通过 API 拉取，也可以从已下载的公开 dump 转换。若需要 polite pool，应提供 `--mailto`；API key 只应通过本地环境变量传入，不写入仓库。

```bash
python -m iad_sieve.cli fetch-openalex-works \
  --output data/raw/openalex/works_cs_sample.jsonl \
  --summary-output data/raw/openalex/works_cs_sample_summary.jsonl \
  --filter "primary_topic.id:T10009" \
  --select "id,doi,title,publication_year,authorships,primary_topic,referenced_works,abstract_inverted_index" \
  --max-records 1000 \
  --seed 42 \
  --mailto your_email@example.com
```

转换为 weak-label eval set：

```bash
python -m iad_sieve.cli prepare-openalex-weak-labels \
  --works data/raw/openalex/works_cs_sample.jsonl \
  --citations data/raw/opencitations/coci.csv \
  --dataset-name openalex_cs_sample \
  --output-dir data/processed/eval_sources/openalex_cs_sample \
  --min-shared-references 1 \
  --max-pairs-per-topic 200 \
  --max-pairs 5000
```

OpenAlex / OpenCitations 产生的是 `agenda_non_identity` 或 hard-negative weak label，不能替代人工 gold。

## IAD-Bench 构建

多个来源先统一成 eval source，再合并为 IAD-Bench：

```bash
python -m iad_sieve.cli build-iad-bench \
  --source-dirs \
    data/processed/eval_sources/deepmatcher_dblp_acm \
    data/processed/eval_sources/scirepeval_scidocs_cite \
    data/processed/eval_sources/openalex_cs_sample \
  --output-dir data/processed/iad_bench/open_v3 \
  --train-ratio 0.8 \
  --dev-ratio 0.1 \
  --seed 42
```

核心输出：

| 文件 | 说明 |
| --- | --- |
| `iad_bench_documents.jsonl` | 统一文献表 |
| `iad_bench_pairs.jsonl` | 统一 pair 表，包含 relation label、label source、label strength 和 split |
| `iad_bench_splits.jsonl` | split 摘要 |
| `iad_bench_summary.jsonl` | 总体来源和标签分布摘要 |

## 审计与平衡检查

构建后建议运行来源偏置和标签分层审计：

```bash
python -m iad_sieve.cli build-iad-bench-stratification-audit \
  --pairs data/processed/iad_bench/open_v3/iad_bench_pairs.jsonl \
  --output-dir outputs/iad_bench_audit/stratification

python -m iad_sieve.cli build-iad-bench-source-bias-diagnostic \
  --pairs data/processed/iad_bench/open_v3/iad_bench_pairs.jsonl \
  --output-dir outputs/iad_bench_audit/source_bias
```

若审计发现单一来源或单一标签强度占比过高，应补充来源或构建 balanced subset，不应直接扩大论文主张。

## 复现边界

可复现内容：

- 数据转换代码和 CLI。
- 小型 fixture 的无网络 smoke test。
- 公开来源到统一 eval set 的处理命令。
- IAD-Bench 契约构建、split 和审计命令。

不可由 Git 仓库单独保证的内容：

- 第三方原始数据是否仍可下载。
- API 响应在不同日期完全一致。
- 外部数据许可是否允许重新分发原始副本。
- 论文主实验的大规模输出和模型权重。

正式论文复验应配套 artifact release，包含 manifest、checksum、处理日期、提交哈希、依赖版本和运行命令。
