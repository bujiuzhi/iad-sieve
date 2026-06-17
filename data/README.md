# Data Directory

## Scope

`data/` 用于本地保存原始数据、下载数据、中间样本和处理后评测输入。真实数据默认不进入 Git 仓库，仓库只提交本说明文件。

## Repository Boundary

不要把原始大数据、第三方压缩包、下载缓存或本地构造样本提交到 Git。公开复现应依赖数据来源说明、下载脚本、manifest、checksum 和可公开 fixture。

## 建议结构

```text
data/
  raw/          # 第三方原始数据或下载解压结果
  interim/      # 清洗、过滤、规范化后的中间数据
  processed/    # 可直接进入实验的处理后数据
  samples/      # 本地开发样本，不提交
```

## 可提交替代物

- `tests/fixtures/`：小型、脱敏、可公开测试样例。
- `docs/data-and-artifact-release.md`：数据来源、复现等级和 artifact 发布策略。
- `scripts/download_kaggle_arxiv.sh`：数据获取脚本示例。

## 提交规则

提交前确认：

```bash
git status --ignored --short data
python scripts/check_public_release.py
```

只有 `data/README.md` 应进入 Git 跟踪范围。
