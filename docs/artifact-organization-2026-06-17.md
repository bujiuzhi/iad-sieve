# 产物整理说明

## 问题拆解

当前项目产物分为代码、数据、模型、实验输出、审稿证据和最终课题包。`outputs/` 中存在大量历史实验目录，直接改名会破坏现有测试、README 命令和远程执行脚本中的固定路径，因此本轮整理采用“删除明确缓存、保留主路径、补充目录地图、远程大产物归档”的策略。

## 本地目录策略

```text
docs/                         课题方案、方法、实验、审稿与整理说明
src/                          可运行源码
tests/                        单元测试与回归测试
data/                         原始/中间/处理后数据，默认不纳入版本控制
outputs/topic_package_final/  最终课题包
outputs/models/               模型 checkpoint 与本地模型工件
outputs/*open_v3*             当前主证据链
outputs/*fixture*             测试或报告复现产物
outputs/remote_*              远程执行、验收、交接产物
```

## 已执行清理

```text
删除 Python __pycache__ 和 .pyc
删除 .pytest_cache
删除 .DS_Store
删除 outputs/models 根目录中与 ditto_style_em_source_heldout 完全重复的模型文件
新增 outputs/README.md 作为产物地图
```

## 未执行的本地移动

未把 `outputs/*` 大批量搬入分组子目录，原因是测试、文档和远程脚本中存在大量硬编码 `outputs/...` 路径。若后续要彻底重构目录，应先修改命令生成器和测试断言，再执行迁移。

## 远程目录策略

远程服务器保存了多轮大规模历史实验，包括 `large_300k_random`、`main_100k_cs_CL`、`dev_50000*` 等。这些不属于当前 Q2/B 主证据链，适合压缩归档后移除原目录；当前主证据链、模型目录、最终课题包和远程交接产物应保留。
