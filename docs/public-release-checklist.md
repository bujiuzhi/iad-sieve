# 公开发布与投稿前检查清单

## 问题拆解

公开仓库需要同时满足三件事：别人能安装运行、别人能理解实验边界、仓库不泄露本地或服务器信息。投稿使用的代码包还需要把“可复现证据”和“论文主张边界”对应起来，避免审稿人认为结果不可复验或过度主张。

## 关键结论

公开版本只提交源码、测试、小型夹具、脚本和文档。`data/`、`outputs/`、模型权重、远程连接配置、历史过程日志和本机路径均不提交。

## 必跑检查

在提交远程仓库前执行：

```bash
python scripts/check_public_release.py
python -m compileall -q src tests scripts
pytest -q
python -m iad_sieve.cli --help
```

如果当前目录尚未初始化为 Git 仓库，先确认目标远程仓库目录，再执行提交。当前整理不依赖 `.git` 状态。

## 应提交内容

- `README.md`：公开仓库入口，说明问题、方法、安装、快速验证和复现边界。
- `pyproject.toml`：依赖与命令行入口。
- `src/`：核心 Python 包。
- `tests/`：自动化测试与小规模 fixture。
- `scripts/`：可复现实验脚本、环境检查脚本和公开发布检查脚本。
- `docs/`：方法、实验、数据、审稿风险和投稿辅助材料。

## 不应提交内容

- `data/`：原始数据、下载数据、中间样本。
- `outputs/`：实验输出、模型、embedding、报告临时产物。
- `docs/_local_archive/`：本地历史记录和长过程日志。
- 远程服务器地址、用户名、密钥路径和连接配置。
- `.env`、token、API key、私钥、模型 checkpoint。
- 任何未确认许可的大体积第三方数据压缩包。

## Artifact 发布建议

推荐把公开仓库和实验产物分开：

1. GitHub 仓库：代码、测试、轻量文档。
2. GitHub Release / Zenodo / OSF：论文 artifact 包、结果表、哈希清单和小型可复验样本。
3. 原始数据：只提供来源、下载脚本、版本说明和处理流程；不直接再发布受限数据。

artifact 包至少包含：

- `manifest.json`：文件列表、生成命令、数据来源、时间和 SHA256。
- `reports/`：baseline、ablation、bootstrap、error analysis。
- `tables/`：论文主表和补充表。
- `figures/`：论文图和机制示意图。
- `configs/`：运行参数、随机种子和阈值配置。

## 论文主张检查

可以主张：

- 方法针对科学实体匹配中的 false merge 风险。
- 风险校准和 constrained union 能在错误预算下提升合并安全性。
- Open-v2/Open-v3 是可复验的衍生压力评测包。
- baseline、消融和 bootstrap 共同支持方法有效性。

需要谨慎表述：

- 不把 Open-v2/Open-v3 写成第三方原始金标数据集。
- 不把 LLM judge 写成人工标注替代品。
- 不在缺少跨领域实验时声称全学科泛化。
- 不在缺少官方 baseline 复现实验时声称绝对 SOTA。

## 提交远程仓库前的人工确认

- README 中没有服务器地址、用户名、密钥路径和本机绝对路径。
- `.gitignore` 已覆盖 `data/`、`outputs/`、模型权重和本地配置。
- 测试夹具足够小，可以公开。
- 大规模结果已准备单独 artifact 发布方案。
- 论文表格中的每个数字能追溯到命令、输入和输出文件。
