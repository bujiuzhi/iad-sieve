# 文档索引

## Overview

公开仓库中的 `docs/` 只保留课题正式文档和复现边界文档。文档面向读者说明研究问题、方法设计、数据契约、复现流程和证据边界。

## Scope

公开文档覆盖研究问题、方法设计、数据契约、数据处理、实验复现、标注边界和论文组织。非课题材料不纳入正式文档范围。

## 推荐阅读顺序

| 阶段 | 文档 | 用途 |
| --- | --- | --- |
| 项目入口 | `../README.md` | 了解项目目标、安装、验证和复现边界 |
| 方法设计 | `method-design.md` | 查看 IAD-Sieve 的核心流程和模块 |
| 实验计划 | `experiment-plan.md` | 查看评测数据、baseline、消融和复现实验入口 |
| 数据契约 | `iad-bench-contract.md` | 查看 IAD-Bench 字段、标签和 provenance 约定 |
| 数据处理 | `data-processing-pipeline.md` | 查看公开原始数据到 IAD-Bench 的处理代码和命令 |
| 标注规范 | `annotation-requirements.md` | 查看人工复核和标签边界要求 |
| 论文大纲 | `paper-outline.md` | 查看论文结构、主张边界和写作组织 |
| 数据发布 | `data-and-artifact-release.md` | 查看数据、fixture、artifact release 和 checksum 策略 |

## 保留文档

```text
docs/
  README.md
  method-design.md
  experiment-plan.md
  iad-bench-contract.md
  data-processing-pipeline.md
  annotation-requirements.md
  paper-outline.md
  data-and-artifact-release.md
```
