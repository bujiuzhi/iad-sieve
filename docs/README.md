# 文档索引

## 问题拆解

`docs/` 中同时包含研究目标、方法设计、实验方案、数据发布、远程运行和投稿审计材料。为避免移动历史文档破坏导出脚本，本目录采用“保留原文件名、增加索引和边界说明”的整理方式。

## 关键结论

优先阅读 `README.md`、`docs/project-structure.md`、`docs/data-and-artifact-release.md` 和 `docs/public-release-checklist.md`。历史推演、审稿审计和远程执行文档保留为证据链，不作为新读者的第一入口。

## 推荐阅读顺序

| 阶段 | 文档 | 用途 |
| --- | --- | --- |
| 项目入口 | `../README.md` | 了解项目目标、安装、验证和复现边界 |
| 目录边界 | `project-structure.md` | 明确源码、数据、产物和文档的管理规则 |
| 命名规范 | `naming-convention.md` | 区分仓库名、包名、CLI 名、论文方法名 |
| 方法设计 | `method-design.md` | 查看 IAD-Sieve 的核心流程和模块 |
| 研究目标 | `GOAL.md` | 查看研究问题、阶段目标和评价方向 |
| 数据发布 | `data-and-artifact-release.md` | 查看数据、fixture、artifact 的发布策略 |
| 发布检查 | `public-release-checklist.md` | 提交前检查敏感信息、大文件和复现边界 |

## 文档分组

### 架构与方法

- `method-design.md`
- `risk-calibrated-topic-restructure.md`
- `restructured-topic-plan.md`
- `iad-bench-contract.md`
- `annotation-requirements.md`

### 实验与复现

- `experiment-plan.md`
- `experiment-results-2026-06-11.md`
- `remote-dev-setup.md`
- `data-and-artifact-release.md`
- `artifact-organization-2026-06-17.md`

### 投稿与审稿

- `paper-outline.md`
- `prior-art-audit-2026-06-12.md`
- `reviewer-literature-audit-2026-06-13.md`
- `public-release-checklist.md`
- `patent-notes.md`

### 过程记录

- `current-work-summary.md`
- `gpt-pro-research-brief.md`
- `gpt-pro-idea-only-brief.md`
- `iad-sieve-codex-goal.md`

这些文件记录阶段性判断，其中较早的强模型、Q2/B 和 SOTA 表述应以当前 claim gate、`risk-calibrated-topic-restructure.md` 和公开发布清单为准。

## 本地归档

`docs/_local_archive/` 保存历史计划和长过程日志，已被 `.gitignore` 排除。该目录不属于公开仓库内容，不应作为论文证据直接引用。
