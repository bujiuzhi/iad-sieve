# 项目结构与版本控制边界

## 问题拆解

本项目包含源码、测试夹具、公开文档、本地原始数据、远程实验结果和论文产物。Git 仓库只适合保存可审计、可复用、体积可控的内容；大规模数据、模型权重和运行输出需要单独发布或在本地保留。

## 关键结论

GitHub 仓库负责保存“如何复现”，不是保存所有“复现材料本体”。完整复现依赖数据来源说明、下载脚本、manifest、checksum、运行命令和 artifact release。

## 顶层目录

| 路径 | 是否提交 | 说明 |
| --- | --- | --- |
| `src/iad_sieve/` | 是 | 核心 Python 包，包含候选生成、关系建模、风险校准、聚类、推荐和评测模块 |
| `tests/` | 是 | 自动化测试与小型公开 fixture |
| `tests/fixtures/` | 是 | 可公开的小样例，只用于单元测试和协议验证 |
| `scripts/` | 是 | 下载、实验、CUDA 检查和公开发布检查脚本 |
| `docs/` | 是 | 方法、实验、数据发布、审稿和项目管理文档 |
| `data/` | 仅提交 `README.md` | 原始数据、中间数据和大样本，不提交真实内容 |
| `outputs/` | 仅提交 `README.md` | 实验输出、模型、报告和远程回传产物，不提交真实内容 |
| `models/` | 否 | 模型权重和 checkpoint，单独发布或本地保存 |
| `docs/_local_archive/` | 否 | 历史过程日志和本地计划归档 |

## 源码分层

| 模块 | 职责 |
| --- | --- |
| `data/` | 数据 schema、采样与公开来源加载 |
| `preprocessing/` | 标题、作者、标识符和文本规范化 |
| `candidates/` | 标题、词项、标识符和向量候选生成 |
| `embedding/` | 编码器、向量缓存和向量存储 |
| `relations/` | 候选对特征、关系打分和阈值适配 |
| `deduplication/` | cannot-link、受约束 union-find 和 canonical 选择 |
| `clustering/` | 主题图、聚类与聚类反馈 |
| `ranking/` | 新颖性、代表性、桥接性和 frontier 排序 |
| `recommendation/` | 查询分析、检索、重排和解释 |
| `evaluation/` | benchmark 构建、baseline、审计、远程验收和论文证据包 |
| `views/` | 语义视图、关键词和句子角色抽取 |
| `utils/` | IO、随机数、数学和文本相似度工具 |

## 数据管理规则

`data/` 中允许保存本地运行需要的数据，但不能进入 Git 历史。公开复现应通过以下材料完成：

1. 数据来源和许可说明。
2. 下载或构建脚本。
3. 文件清单、大小和 SHA256。
4. 处理命令、随机种子和 split 配置。
5. 可公开的小型 fixture。

从公开原始数据到 IAD-Bench 的具体处理入口见 `docs/data-processing-pipeline.md`。

## 产物管理规则

`outputs/` 保存运行结果，不作为代码仓库内容。需要公开的论文产物应打包到 GitHub Release、Zenodo、OSF 或对象存储，并附带：

- `manifest.json` 或 `manifest.jsonl`。
- `checksums.sha256`。
- 生成命令和提交哈希。
- 依赖版本、硬件信息和运行时间。
- 结果验收脚本输出。

## 提交前边界

提交远程仓库前至少执行：

```bash
python scripts/check_public_release.py
python -m compileall -q src tests scripts
pytest -q
```

禁止提交：

- API key、SSH key、token、远程 profile。
- 本机绝对路径和服务器地址。
- 原始大数据、压缩包、模型权重和 checkpoint。
- 未确认许可的第三方数据副本。
- 临时日志、缓存和历史过程归档。
