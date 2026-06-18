# Outputs Directory

## 目录用途

`outputs/` 用于本地保存实验产物、模型权重、复现实验结果和最终 artifact 包。真实产物默认不进入 Git 仓库，仓库只提交本说明文件。

## 仓库边界

不要把实验输出、模型 checkpoint、远程 profile、日志或最终 artifact 包直接提交到 Git。需要公开的产物应通过 GitHub Release、Zenodo、OSF 或对象存储发布，并附 manifest 与 checksum。

## 本地目录建议

```text
outputs/
  experiments/   # baseline、ablation、bootstrap 和误差分析结果
  source_artifacts/  # 由实验流程整理出的 release 输入文件
  artifacts/     # 对外发布前的 artifact release 目录
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
  tables/
  predictions/
  reports/
  logs/
```

`manifest.json` 至少记录提交哈希、生成命令、输入数据版本、随机种子、依赖版本和每个文件的 SHA256。

推荐流程：

```bash
python manuscript/scripts/build_artifact_release_skeleton.py --output-dir outputs/artifacts/iad-risk-release --repository-commit <commit>
python manuscript/scripts/populate_artifact_release.py --artifact-dir outputs/artifacts/iad-risk-release --source-dir outputs/source_artifacts/<run-id>
python manuscript/scripts/validate_artifact_release.py --artifact-dir outputs/artifacts/iad-risk-release
```

`outputs/source_artifacts/<run-id>` 应按 `manuscript/artifact_release_manifest.template.json` 的 `expected_location` 准备表格、预测、报告、配置和日志文件；如本地实验输出命名不同，应使用 `populate_artifact_release.py --mapping <mapping.json>` 显式声明 artifact ID 到源文件路径的映射。

## 提交规则

提交前确认：

```bash
git status --ignored --short outputs
python scripts/check_public_release.py
```

只有 `outputs/README.md` 应进入 Git 跟踪范围。
