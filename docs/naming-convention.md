# 命名规范与投稿题名

## 问题拆解

本项目需要区分三个名称：代码工程名、Python 包名和论文投稿名。工程名应便于公开仓库检索与安装；包名应符合 Python import 规范；论文名应突出方法贡献和研究问题。

## 关键结论

推荐统一采用以下命名：

| 场景 | 名称 | 用途 |
| --- | --- | --- |
| 本地项目目录 | `iad-sieve` | 本地文件夹和远程仓库目录 |
| 远程仓库名 | `iad-sieve` | GitHub/Gitee 仓库名 |
| Python 发行包 | `iad-sieve` | `pyproject.toml` 中的 project name |
| Python import 包 | `iad_sieve` | `python -m iad_sieve.cli` 与源码导入 |
| CLI 命令 | `iad-sieve` | 安装后命令行入口 |
| 论文方法名 | `IAD-Sieve` | 正文、图表、实验方法简称 |
| 数据集名 | `IAD-Bench-Open-v3` | 公开衍生评测包 |

## 期刊投稿题名

推荐主标题：

`IAD-Sieve: Risk-Calibrated Scientific Entity Matching under Agenda-Level Confounders`

可选更保守标题：

`Risk-Calibrated Scientific Entity Matching under Agenda-Level Confounders`

可选更强调数据集标题：

`IAD-Sieve: Risk-Calibrated Scientific Entity Matching with Open Benchmark Stress Tests`

## 命名理由

`iad-sieve` 比 `lit-sieve` 更贴近论文核心贡献。`IAD` 对应 identity-agenda disentanglement，能直接表达“身份匹配”和“议题混杂”之间的区分；`sieve` 表达筛除高风险误合并边的算法行为。

`iad_sieve` 作为 Python 包名符合下划线 import 规范；`iad-sieve` 作为仓库名和发行包名符合 Python packaging 与 GitHub 仓库命名习惯。

## 不建议的名称

- `lit-sieve`：过于宽泛，容易被理解为普通文献筛选工具。
- `risk-calibrated-scientific-entity-matching`：描述准确但过长，不适合作为仓库名。
- `iad-risk`：偏模型模块名，不能覆盖候选生成、受约束合并、benchmark 和 artifact 体系。
- `IADBenchSieve`：混合大小写，不利于命令行和包管理。

## 当前迁移状态

代码层面已经迁移为：

```text
src/iad_sieve/
python -m iad_sieve.cli --help
iad-sieve
```

当前 Codex 工作区物理路径仍可能显示为旧目录名，这是工作区绑定造成的本地路径问题。公开仓库和最终本地目录应使用 `iad-sieve`。
