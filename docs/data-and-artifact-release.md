# 数据集与实验产物发布说明

## 发布范围

本项目的数据体系由“公开原始来源、项目衍生评测包、实验输出产物”三层组成。公开仓库应包含可复现流程和小型测试夹具，但不直接提交大规模原始数据、模型权重和服务器产物。

## 仓库边界

`IAD-Bench-Open-v2` 和 `IAD-Bench-Open-v3` 是项目构建的数据集变体；它们不是第三方原封不动发布的数据集。论文中应称为“derived benchmark packages”或“project-built benchmark variants from public sources”。

远程仓库不提交原始数据、模型权重或完整实验输出；仓库责任是保留可运行代码、数据处理入口、fixture、schema、manifest 模板和 artifact 校验脚本。

Git 仓库只提交 `data/README.md` 和 `outputs/README.md` 作为目录说明。真实数据、远程回传结果、模型权重和论文产物应通过 artifact release 或受控对象存储分发，并用 manifest 与 checksum 固定版本。

## 数据层次

| 层次 | 内容 | 是否进入 Git 仓库 | 说明 |
| --- | --- | --- | --- |
| 原始公开数据 | arXiv metadata、OpenAlex、OpenCitations COCI、SciRepEval/SciDocs style metadata、DeepMatcher/py_entitymatching | 否 | 通过来源或下载脚本获取，遵循原始许可 |
| 小型测试夹具 | `tests/fixtures/` 下的极小样本 | 是 | 仅用于单元测试和协议验证 |
| Open-v2/Open-v3 衍生包 | 清洗、分层、切分后的实体匹配评测包 | 建议单独发布 | 可作为论文 artifact，附 manifest 和哈希 |
| 实验输出 | baseline、ablation、bootstrap、error analysis、paper artifacts | 建议单独发布 | 不进入 Git 仓库，发布到 release/Zenodo/OSF |
| 远程运行配置 | 服务器地址、用户名、密钥路径 | 否 | 只保留本地，不公开 |

## Git 仓库边界

公开仓库应保留：

- 源码、CLI 和可运行测试。
- 小型公开 fixture。
- 数据 schema、构建流程和下载脚本。
- 数据与产物目录说明。
- 实验命令、随机种子、阈值和验收脚本。

公开仓库不应保留：

- `data/raw/`、`data/interim/`、`data/processed/` 的真实大文件。
- `outputs/` 下的实验输出、模型、日志和最终课题包。
- `outputs/remote_connection_profile.local.json` 或任何远程连接配置。
- API key、SSH key、token、本机路径或服务器地址。

## Open-v2 与 Open-v3 的定位

Open-v2 主要用于验证公开来源组合下的实体匹配风险，重点是把相似但不应合并的样本纳入压力评测。

Open-v3 在 Open-v2 的基础上更强调 source-heldout 和来源隔离：训练、校准和评测尽量避免来自同一数据构造来源，从而降低“模型学会数据来源特征”而非实体关系的风险。

论文表述建议：

- 正确：`We construct IAD-Bench-Open-v3 from public scholarly metadata and citation-derived signals.`
- 正确：`Open-v3 uses source-heldout splits to stress-test agenda-level confounders.`
- 避免：`Open-v3 is an existing public gold benchmark.`
- 避免：`Open-v3 provides exhaustive human labels for scientific entity matching.`

## 复现等级

| 等级 | 目标 | 输入 | 运行时间 | 用途 |
| --- | --- | --- | --- | --- |
| L0 code check | 安装、CLI、测试和公开发布扫描 | 无大数据 | 分钟级 | 检查公开仓库是否可运行 |
| L1 fixture rebuild | 小型 fixture 重建 | `tests/fixtures/` | 分钟级 | 验证数据适配器、schema 和评测协议 |
| L2 public-source rebuild | 从独立获取的公开原始文件重建派生 eval source 和 IAD-Bench 包 | 本地 `data/raw/` 中的公开来源文件、`source_input_manifest` 和 `processing_run_log` | 小时级，取决于来源规模 | 审计公开输入、处理命令、输出摘要和 checksum 的 chain of custody |
| L3 result audit | 审计已发布的表格、预测、阈值日志、配置、运行日志、manifest 和 checksum | 外部 artifact release | 取决于 artifact 规模 | 复核论文主结果、阈值、分母和逐行预测边界 |

L0/L1 只能证明公开仓库代码路径和小型样本处理契约可运行；L2/L3 才能支持 Open-v2 数值表的结果级审计。不存在单独的 L4 Git 仓库复现等级；第三方复验应通过 L2 public-source rebuild 或 L3 result audit 完成。

## Artifact 包建议结构

```text
paper-artifacts/
  README.md
  manifest.json
  checksums.sha256
  configs/
  tables/
  predictions/
  reports/
  logs/
```

## L3 source artifact 目录契约

`/path/to/source-artifacts` 是 `manuscript/scripts/populate_artifact_release.py` 的只读输入目录，不是 Git 仓库的 `outputs/` 根目录，不是 PDF 构建目录，也不是 Tectonic bundle。该目录应由 L2 public-source rebuild 或离线主实验流程在仓库外或 Git 忽略目录中生成，只包含可再分发的派生表格、预测、日志和配置。

最小必需结构如下：

```text
source-artifacts/
  tables/
    open_v2_main_results.csv
  predictions/
    iad_risk_transformer_predictions.jsonl
    representation_baseline_scores.jsonl
    roberta_pair_classifier_predictions.jsonl
  logs/
    threshold_selection_logs.jsonl
    processing_run_log.jsonl
  reports/
    iad_bench_split_summary.jsonl
  configs/
    source_input_manifest.json
```

必需文件的完整相对路径为：

- `tables/open_v2_main_results.csv`
- `predictions/iad_risk_transformer_predictions.jsonl`
- `predictions/representation_baseline_scores.jsonl`
- `predictions/roberta_pair_classifier_predictions.jsonl`
- `logs/threshold_selection_logs.jsonl`
- `reports/iad_bench_split_summary.jsonl`
- `configs/source_input_manifest.json`
- `logs/processing_run_log.jsonl`

正式发布前应先运行只读预检查：

```bash
python manuscript/scripts/populate_artifact_release.py \
  --artifact-dir /path/to/release \
  --source-dir /path/to/source-artifacts \
  --preflight-only
```

该命令会在复制、记录或定稿前只读检查必需 source artifact 文件是否齐全。缺少任一必需文件时，只能说明仓库代码和小型 fixture 可复现，不能声称已有可发布的 L3 artifact release；PDF 构建输出、`outputs/pdf_build/`、`manuscript/build/` 和离线 Tectonic bundle 均不能替代上述 source artifact。

`manifest.json` 建议记录：

- 项目版本或提交哈希。
- Python 版本、依赖版本和硬件概况。
- 数据来源、下载日期和处理命令。
- 随机种子、阈值和 split 配置。
- 每个输出文件的 SHA256。

正式论文 artifact 还应包含 `configs/source_input_manifest.json` 和 `logs/processing_run_log.jsonl`。前者记录公开输入的原始提供方、获取日期或版本、安全相对本地文件边界、许可边界和有效 SHA256；后者记录每个处理阶段的命令、与 `manifest.json` `repository.commit` 一致的代码提交、环境摘要、随机种子、开始/结束时间、输入 manifest 引用、进入 `checksums.sha256` 的输出路径和 `exit_status=0`。

建议同时提供 `checksums.sha256`，并在 README 中写清楚如何用以下命令验收：

```bash
sha256sum -c checksums.sha256
python -m pip install -e .
python -m iad_sieve.cli --help
```

## 证据边界

独立复验通常关注三类问题：

1. 数据是否自建且存在偏差：需要说明来源、构造规则、source-heldout 和局限。
2. 结果是否可复验：需要提供脚本、参数、manifest、哈希和小型可跑样本。
3. 主张是否过强：需要把结论限制在风险校准实体匹配，不扩展到全领域 SOTA。

因此，论文材料中应把 Open-v2/Open-v3 写成“用于研究问题的衍生压力评测包”，并配套公开构造流程。
