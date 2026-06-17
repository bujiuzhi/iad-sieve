# Outputs Directory

## 目录用途

`outputs/` 用于本地保存实验产物、模型权重、复现实验结果和最终 artifact 包。真实产物默认不进入 Git 仓库，仓库只提交本说明文件。

## 仓库边界

不要把实验输出、模型 checkpoint、远程 profile、日志或最终 artifact 包直接提交到 Git。需要公开的产物应通过 GitHub Release、Zenodo、OSF 或对象存储发布，并附 manifest 与 checksum。

## 本地目录建议

```text
outputs/
  experiments/   # baseline、ablation、bootstrap 和误差分析结果
  artifacts/     # 对外发布前的论文复现包
  models/        # 本地训练或下载的模型权重
  reports/       # 本地生成的表格、图和运行摘要
```

上述目录默认不进入 Git。需要公开的结果应整理为单独 artifact 包，并通过 release 或受控对象存储分发。

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
