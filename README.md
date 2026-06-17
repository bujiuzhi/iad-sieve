# iad-sieve

Risk-Calibrated Scientific Entity Matching under Agenda-Level Confounders.

## 项目概述

科研文献去重和实体匹配不能只依赖文本相似度。预印本、会议版、期刊扩展版、数据集条目和引用记录可能指向同一研究工作；但同一议题下的不同论文也会高度相似。错误合并会污染综述、推荐、聚类和证据追踪。

`IAD-Sieve` 的目标是在可解释的风险约束下识别“可以安全合并”的科学实体，而不是尽量合并更多相似文献。

## 仓库边界

本仓库提交源码、测试、小型 fixture、脚本和公开文档；不提交原始大数据、实验输出、模型权重和远程连接配置。完整复现依赖公开数据来源、下载脚本、manifest、checksum 和单独发布的 artifact。

## 架构概览

```text
输入文献元数据
  -> preprocessing      文本、作者、标识符规范化
  -> candidates         标题、词项、标识符、向量候选召回
  -> relations          候选对特征、关系分类、阈值适配
  -> deduplication      cannot-link 与受约束 union-find
  -> clustering         主题图、簇标签和反馈
  -> ranking            新颖性、代表性、桥接性排序
  -> evaluation         benchmark、baseline、bootstrap、evidence reports
```

核心代码位于 `src/iad_sieve/`，CLI 入口为：

```bash
python -m iad_sieve.cli --help
```

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `src/iad_sieve/` | 核心 Python 包 |
| `tests/` | 自动化测试与小型公开 fixture |
| `scripts/` | 数据下载、实验运行、CUDA 检查和公开发布检查 |
| `docs/` | 方法、数据契约、数据处理、标注规范和复现边界 |
| `data/` | 本地数据目录，仅提交 `data/README.md` |
| `outputs/` | 本地实验产物目录，仅提交 `outputs/README.md` |

文档导航见 [docs/README.md](docs/README.md)。

## 安装

推荐使用 Python 3.11。

```bash
conda create -n iad-sieve python=3.11 -y
conda activate iad-sieve
python -m pip install -e .
```

可选 SPECTER2 adapter 依赖：

```bash
python -m pip install -e ".[specter2]"
```

## 快速验证

```bash
python -m iad_sieve.cli --help
python scripts/check_public_release.py
python -m compileall -q src tests scripts
pytest -q
```

`scripts/check_public_release.py` 会扫描公开范围内的大文件、密钥片段、本机路径和远程路径线索。

## 数据与复现

`IAD-Bench-Open-v2` 和 `IAD-Bench-Open-v3` 是项目基于公开来源构建的衍生评测包，不是第三方原封不动发布的原始金标数据集。

涉及来源包括：

- arXiv metadata。
- DeepMatcher / py_entitymatching structured benchmarks。
- OpenAlex works。
- OpenCitations COCI。
- SciRepEval / SciDocs style metadata。

复现分级：

| 等级 | 目标 | 输入 | 用途 |
| --- | --- | --- | --- |
| L0 | 安装与 CLI 验证 | 无大数据 | 检查仓库可用性 |
| L1 | 单元测试 | `tests/fixtures/` | 验证算法和评测协议 |
| L2 | 小样本开发实验 | 公开来源小样本 | 验证端到端流程 |
| L3 | 论文主实验 | 完整数据与外部 baseline | 生成论文表格和证据包 |
| L4 | 第三方复验 | 固定 artifact release | 独立读者复现 |

数据与 artifact 发布策略见 [docs/data-and-artifact-release.md](docs/data-and-artifact-release.md)。
从公开原始数据到 IAD-Bench 的处理命令见 [docs/data-processing-pipeline.md](docs/data-processing-pipeline.md)。

## 实验入口

小规模开发实验：

```bash
scripts/download_kaggle_arxiv.sh
scripts/run_dev_experiment.sh 1000 42 cs.CL
```

主实验入口：

```bash
scripts/run_main_experiment.sh 42 100000 cs.CL
```

大样本或 GPU 实验应通过单独的运行环境和 artifact release 记录输入、命令、提交哈希、manifest 与 checksum。仓库不会保存服务器地址、用户名、私钥路径或 API key。

## 文档入口

| 主题 | 文档 |
| --- | --- |
| 文档索引 | [docs/README.md](docs/README.md) |
| 方法设计 | [docs/method-design.md](docs/method-design.md) |
| IAD-Bench 契约 | [docs/iad-bench-contract.md](docs/iad-bench-contract.md) |
| 数据处理流水线 | [docs/data-processing-pipeline.md](docs/data-processing-pipeline.md) |
| 标注规范 | [docs/annotation-requirements.md](docs/annotation-requirements.md) |
| 数据与 artifact 发布 | [docs/data-and-artifact-release.md](docs/data-and-artifact-release.md) |

## 论文主张边界

适合主张：

- 议题级混杂会显著增加科学实体匹配中的 false merge 风险。
- 风险校准和受约束合并可以把目标从“多合并”调整为“在错误预算下安全合并”。
- Open-v2/Open-v3 是可复验的衍生压力评测框架。

需要避免：

- 声称全领域 SOTA。
- 将 Open-v2/Open-v3 表述为第三方原始人工金标。
- 将自动候选筛选结果表述为人工标注替代品。
- 在缺少跨来源和跨领域证据时声称无偏泛化。

## 提交前检查

```bash
python scripts/check_public_release.py
python -m compileall -q src tests scripts
pytest -q
```

确认 `git status --ignored --short` 中只有 `data/`、`outputs/` 和缓存类文件保持未提交。

## 许可边界

本仓库不再分发第三方原始数据。代码、衍生评测包和实验产物的再发布范围以仓库维护者发布的许可文件、artifact release 说明和第三方数据来源条款为准。
