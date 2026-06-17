# iad-sieve

Risk-Calibrated Scientific Entity Matching under Agenda-Level Confounders.

规范命名见 [docs/naming-convention.md](docs/naming-convention.md)：公开仓库名使用 `iad-sieve`，Python 包名使用 `iad_sieve`，论文方法名使用 `IAD-Sieve`。

## 问题拆解

本仓库面向“科研文献实体匹配/去重”场景：同一研究工作可能以预印本、会议版、期刊扩展版、数据集条目或引用记录等形态出现。传统相似度合并容易把“同主题但非同一实体”的论文误合并，进而污染综述、推荐、聚类和证据追踪结果。

`IAD-Sieve` 的核心目标不是最大化合并数量，而是在可解释的风险约束下识别“可以安全合并”的科学实体。

## 关键结论

当前仓库已经按公开复现方向整理为四类内容：

- `src/`：可运行的核心代码，包括候选生成、语义表示、关系打分、风险校准、受约束合并和评测模块。
- `tests/`：小规模夹具与自动化测试，用于验证算法逻辑、评测协议和投稿前检查项。
- `docs/`：课题重构、方法设计、实验方案、审稿风险、数据发布和公开仓库清单。
- `scripts/`：数据下载、实验运行、CUDA 检查和公开发布前自检脚本。

大规模原始数据、训练产物、模型权重和远程连接配置不纳入仓库版本控制；它们保留在本地或单独的 artifact release 中。

## 方法概览

`IAD-Sieve` 使用分阶段流程降低误合并风险：

1. 候选召回：基于标题、词项、标识符和向量近邻生成候选论文对。
2. 关系建模：区分 duplicate、successor、related、conflict 等关系，而不是把所有相似论文压成单一相似度。
3. 风险校准：在 held-out source 或压力集上校准合并阈值，优先控制 false merge。
4. 受约束合并：通过 cannot-link、污染检测和 union-find 约束，阻止高风险边进入实体簇。
5. 证据审计：输出 baseline、ablation、bootstrap、error analysis 和 reviewer-facing evidence matrix。

## 数据集边界

`IAD-Bench-Open-v2` 与 `IAD-Bench-Open-v3` 是本项目构建的衍生评测包，不是第三方直接发布的原始数据集。它们基于公开来源组合、清洗、分层和切分，用于测试“议题级混杂”下的实体匹配风险。

涉及的数据来源包括：

- arXiv metadata：用于论文元数据、主题过滤和大规模候选生成。
- DeepMatcher / py_entitymatching structured benchmarks：用于实体匹配金标对比。
- OpenAlex works：用于开放论文元数据和弱监督关系构造。
- OpenCitations COCI：用于引用关系辅助验证。
- SciRepEval / SciDocs style metadata：用于语义接近但不应合并的压力评测。

原始数据默认放在 `data/`，实验输出默认放在 `outputs/`。这两个目录已被 `.gitignore` 排除。

## 安装

推荐使用 Python 3.11。

```bash
conda create -n iad-sieve python=3.11 -y
conda activate iad-sieve
python -m pip install -e .
```

可选的 SPECTER2 adapter 依赖：

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

`python scripts/check_public_release.py` 会扫描公开发布风险，包括本机路径、远程地址、密钥片段、大文件和不应提交的本地产物。

## 复现实验

小规模开发实验：

```bash
scripts/download_kaggle_arxiv.sh
scripts/run_dev_experiment.sh 1000 42 cs.CL
```

主实验入口：

```bash
scripts/run_main_experiment.sh 42 100000 cs.CL
```

完整论文复现需要额外准备公开数据源、外部 baseline 分数或训练环境。数据与 artifact 发布策略见 [docs/data-and-artifact-release.md](docs/data-and-artifact-release.md)。

## 论文写作边界

适合在论文中主张：

- 在科学实体匹配中，议题级混杂会导致相似度合并产生高代价 false merge。
- 风险校准和受约束合并可以把目标从“尽量多合并”调整为“在错误预算下安全合并”。
- Open-v2/Open-v3 提供了可复验的衍生压力评测框架，但不替代人工大规模金标。

不建议在没有额外证据时主张：

- 全领域 SOTA。
- 对所有开放论文库均可无偏泛化。
- Open-v2/Open-v3 等同于人工全金标数据集。
- LLM judge 可以替代人工标注或第三方金标。

## 公开发布前检查

提交远程仓库前执行：

```bash
python scripts/check_public_release.py
python -m compileall -q src tests scripts
pytest -q
```

详细清单见 [docs/public-release-checklist.md](docs/public-release-checklist.md)。

## 目录结构

```text
iad-sieve/
  src/iad_sieve/      # 核心包
  tests/              # 自动化测试与小型公开夹具
  scripts/            # 运行脚本与发布前检查
  docs/               # 研究设计、实验方案、投稿与发布文档
  data/               # 本地原始/中间数据，不提交
  outputs/            # 本地实验产物，不提交
```

## License

代码许可证和数据再发布许可证需要在正式公开前补齐。原始公开数据仍遵循各自来源的许可与使用条款。
