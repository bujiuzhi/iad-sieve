# 文档索引

## 问题拆解

公开仓库中的 `docs/` 只保留课题正式文档和复现边界文档。Codex 过程记录、阶段性审稿推演、远程执行交接和历史实验流水账已移出公开顶层，保存在本地忽略目录 `docs/_local_archive/`。

## 关键结论

当前公开 `docs/` 保持为 11 个文件，覆盖“课题是什么、方法如何做、数据如何构造、实验如何复现、论文如何写、哪些内容不能提交”。这比保留大量过程文件更适合公开仓库和第三方阅读。

## 推荐阅读顺序

| 阶段 | 文档 | 用途 |
| --- | --- | --- |
| 项目入口 | `../README.md` | 了解项目目标、安装、验证和复现边界 |
| 目录边界 | `project-structure.md` | 明确源码、数据、产物和文档的版本控制规则 |
| 命名规范 | `naming-convention.md` | 区分仓库名、包名、CLI 名、论文方法名 |
| 研究目标 | `GOAL.md` | 查看研究问题、阶段目标和评价方向 |
| 方法设计 | `method-design.md` | 查看 IAD-Sieve 的核心流程和模块 |
| 实验计划 | `experiment-plan.md` | 查看评测数据、baseline、消融和复现实验入口 |
| 数据契约 | `iad-bench-contract.md` | 查看 IAD-Bench 字段、标签和 provenance 约定 |
| 标注规范 | `annotation-requirements.md` | 查看人工 audit 和标签边界要求 |
| 论文大纲 | `paper-outline.md` | 查看论文结构、主张边界和写作组织 |
| 数据发布 | `data-and-artifact-release.md` | 查看数据、fixture、artifact release 和 checksum 策略 |
| 发布检查 | `public-release-checklist.md` | 提交前检查敏感信息、大文件和复现边界 |

## 保留文档

```text
docs/
  README.md
  project-structure.md
  naming-convention.md
  GOAL.md
  method-design.md
  experiment-plan.md
  iad-bench-contract.md
  annotation-requirements.md
  paper-outline.md
  data-and-artifact-release.md
  public-release-checklist.md
```

## 移出顶层的文档类型

以下内容不再放在公开 `docs/` 顶层：

- Codex 目标、GPT 简报和过程摘要。
- 阶段性重构计划、审稿模拟、远程执行交接。
- 带日期的历史实验结果和过程整理记录。
- 专利备忘、临时 prior-art/reviewer 审计草稿。

这些材料可在本地 `docs/_local_archive/` 中保留，但不进入 GitHub 公开文档面。
