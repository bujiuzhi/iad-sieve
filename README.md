# iad-sieve

Risk-Aware Scientific Entity Matching under Agenda-Level Confounders.

## 项目概述

科研文献去重和实体匹配不能只依赖文本相似度。预印本、会议版、期刊扩展版、数据集条目和引用记录可能指向同一研究工作；但同一议题下的不同论文也会高度相似。错误合并会污染综述、推荐、聚类和证据追踪。

`IAD-Sieve` 的目标是在可解释的风险约束下识别“可以安全合并”的科学实体，而不是尽量合并更多相似文献。

## 仓库边界

本仓库提交源码、测试、小型 fixture、脚本和公开文档；不提交原始大数据、实验输出、模型权重和远程连接配置。结果级复核依赖公开数据来源记录、下载脚本、manifest、checksum 和单独发布的 artifact。

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

以下命令假定已执行 `python -m pip install -e .`，并且当前 shell 使用的是该环境中的 Python。若只想在未安装包前检查源码入口，可使用 `PYTHONPATH=src python -m iad_sieve.cli --help`；正式复现和审稿校验仍应使用安装后的环境。

```bash
python -m iad_sieve.cli --help
python scripts/check_public_release.py
python -m compileall -q src tests scripts
pytest -q
```

`scripts/check_public_release.py` 会扫描公开范围内的大文件、密钥片段、本机路径和远程路径线索。

## 稿件与投稿包验证

审稿人从 Git 仓库检查论文材料时，应先运行代码级验证，再运行稿件和投稿包验证。以下命令只证明 Git-only 审稿入口、fixture、PDF/LaTeX 和本地投稿包一致；不能复核 Open-v2 数值表，结果级复核仍需要 L2 public-source rebuild 或 L3 result audit。

```bash
python manuscript/scripts/verify_fixture_rebuild.py
python manuscript/scripts/validate_manuscript.py --strict-latex
python manuscript/scripts/build_submission_package.py
python manuscript/scripts/validate_submission_package.py
python manuscript/scripts/build_submission_package.py --dke-preflight
python manuscript/scripts/validate_submission_package.py --dke-preflight
```

生成目录 `manuscript/build/submission_package/` 和 `manuscript/build/dke_preflight_package/` 以及对应 zip 文件是本地检查产物，不提交仓库。正式上传前还必须补齐作者信息、目标期刊确认、artifact URL/DOI 和 live submission-system 核对，再使用 `python manuscript/scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release` 校验最终包。

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
| L0 code check | 安装、CLI、测试和公开发布扫描 | 无大数据 | 检查公开仓库是否可运行 |
| L1 fixture rebuild | 小型 fixture 重建 | `tests/fixtures/` | 验证数据适配器、schema 和评测协议 |
| L2 public-source rebuild | 从独立获取的公开原始文件重建派生 eval source 和 IAD-Bench 包 | 本地 `data/raw/` 中的公开来源文件、`source_input_manifest` 和 `processing_run_log` | 审计公开输入、处理命令、输出摘要和 checksum 的 chain of custody |
| L3 result audit | 审计已发布的表格、预测、阈值日志、配置、运行日志、manifest 和 checksum | 外部 artifact release | 复核论文主结果、阈值、分母和逐行预测边界 |

L0/L1 只能证明公开仓库代码路径和小型样本处理契约可运行；L2/L3 才能支持 Open-v2 数值表的结果级审计。不存在单独的 L4 Git 仓库复现等级；第三方复验应通过 L2 public-source rebuild 或 L3 result audit 完成。

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

- 议题级混杂会形成科学实体匹配中的 false merge 风险。
- 风险感知和受约束合并可以把目标从“多合并”调整为“在错误预算下安全合并”。
- Open-v2/Open-v3 是带有公开构造流程、复现分级和 artifact 审计边界的衍生压力评测框架；主数值复核仍依赖 L2/L3 产物。

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
