# Outputs Directory

## Scope

`outputs/` 用于本地保存实验产物、模型权重、复现实验结果和最终 artifact 包。真实产物默认不进入 Git 仓库，仓库只提交本说明文件。

## Repository Boundary

不要把实验输出、模型 checkpoint、远程 profile、日志或最终 artifact 包直接提交到 Git。需要公开的产物应通过 GitHub Release、Zenodo、OSF 或对象存储发布，并附 manifest 与 checksum。

## 保留原则

- `topic_package_final/`：最终 artifact 包，包含论文所需的核心文档和报告副本。
- `iad_bench_open_v3*`、`strong_baseline_open_v3*`、`iad_risk_transformer_scincl_open_v3*`、`risk_protocol_*open_v3*`：主实验证据链。
- `advanced_model_evidence_*`、`model_superiority_*`、`q2b_*`、`novelty_*`：论文主张、模型对照和风险分析产物。
- `models/ditto_style_em_source_heldout/`：Ditto-style EM source-held-out checkpoint。
- `experiment_*`、`remote_*`、`primary_*`：复现实验执行与结果验收产物。

## 非正式产物

- `*_fixture/`：测试与报告复现用的小型 fixture 输出。
- `open_v2`、`openalex_v1`：较早实验包，主要用于方法验证和对照。
- `openalex_only_gap_patch`、`multitopic_silver_patch`、`coci_source_patch`：公开 silver hard-negative 数据补丁与审计链。

## Artifact 发布要求

公开产物包建议包含：

```text
paper-artifacts/
  README.md
  manifest.json
  checksums.sha256
  configs/
  reports/
  tables/
  figures/
  logs/
```

`manifest.json` 至少记录提交哈希、生成命令、输入数据版本、随机种子、依赖版本和每个文件的 SHA256。

## 提交规则

提交前确认：

```bash
git status --ignored --short outputs
python scripts/check_public_release.py
```

只有 `outputs/README.md` 应进入 Git 跟踪范围。
