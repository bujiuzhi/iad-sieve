# 数据集与实验产物发布说明

## 问题拆解

本项目的数据体系由“公开原始来源、项目衍生评测包、实验输出产物”三层组成。公开仓库应包含可复现流程和小型测试夹具，但不直接提交大规模原始数据、模型权重和服务器产物。

## 关键结论

`IAD-Bench-Open-v2` 和 `IAD-Bench-Open-v3` 是项目构建的数据集变体；它们不是第三方原封不动发布的数据集。论文中应称为“derived benchmark packages”或“project-built benchmark variants from public sources”。

## 数据层次

| 层次 | 内容 | 是否进入 Git 仓库 | 说明 |
| --- | --- | --- | --- |
| 原始公开数据 | arXiv metadata、OpenAlex、OpenCitations COCI、SciRepEval/SciDocs style metadata、DeepMatcher/py_entitymatching | 否 | 通过来源或下载脚本获取，遵循原始许可 |
| 小型测试夹具 | `tests/fixtures/` 下的极小样本 | 是 | 仅用于单元测试和协议验证 |
| Open-v2/Open-v3 衍生包 | 清洗、分层、切分后的实体匹配评测包 | 建议单独发布 | 可作为论文 artifact，附 manifest 和哈希 |
| 实验输出 | baseline、ablation、bootstrap、error analysis、paper artifacts | 建议单独发布 | 不进入 Git 仓库，发布到 release/Zenodo/OSF |
| 远程运行配置 | 服务器地址、用户名、密钥路径 | 否 | 只保留本地，不公开 |

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
| L0 | 安装与接口验证 | 无大数据 | 分钟级 | 检查公开仓库可用 |
| L1 | 单元测试与夹具复现 | `tests/fixtures/` | 分钟级 | 验证算法和评测协议 |
| L2 | 小样本开发实验 | arXiv 小样本 | 分钟到小时级 | 验证端到端流程 |
| L3 | 论文主实验 | 完整公开数据与外部 baseline | 小时到天级 | 生成投稿表格和补充材料 |
| L4 | 第三方复验 | 固定 artifact release | 取决于硬件 | 审稿或读者复现 |

## Artifact 包建议结构

```text
paper-artifacts/
  manifest.json
  README.md
  configs/
  tables/
  figures/
  reports/
  logs/
  checksums.sha256
```

`manifest.json` 建议记录：

- 项目版本或提交哈希。
- Python 版本、依赖版本和硬件概况。
- 数据来源、下载日期和处理命令。
- 随机种子、阈值和 split 配置。
- 每个输出文件的 SHA256。

## 审稿风险控制

审稿人可能关注三类问题：

1. 数据是否自建且存在偏差：需要说明来源、构造规则、source-heldout 和局限。
2. 结果是否可复验：需要提供脚本、参数、manifest、哈希和小型可跑样本。
3. 主张是否过强：需要把结论限制在风险校准实体匹配，不扩展到全领域 SOTA。

因此，投稿材料中应把 Open-v2/Open-v3 写成“用于研究问题的衍生压力评测包”，并配套公开构造流程。
