# iad-sieve Codex GOAL

## 问题拆解

当前项目目标从 IAD-Sieve 规则型误合并抑制系统，升级为 IAD-Risk：面向科研文献误合并抑制的身份-议题解耦风险学习方法。Codex 后续开发必须服务于二区 / B 类期刊目标，重点推进强 baseline、IAD-Bench、双空间模型和审稿风险闭环。

## 关键结论

项目核心表述：

```text
IAD-Risk 是一种面向科研文献去重的身份-议题解耦误合并风险学习方法。
```

IAD-Sieve 保留为工程 pipeline 和 rule-only baseline，不再作为论文主方法。

## 执行约束

Codex 执行任务时必须遵守：

```text
1. 不把服务器 IP、用户名、密码、SSH key、Kaggle token 写入仓库。
2. 不提交 data/、models/、.env、缓存文件和大文件。
3. outputs/ 只保留可复现实验摘要、fixture 和最终课题包。
4. 项目默认使用 Python 3.11。
5. 默认 conda 环境名为 iad-sieve。
6. CLI 必须支持 python -m iad_sieve.cli --help。
7. CLI 使用 argparse。
8. 所有核心函数必须包含功能、参数、返回值注释。
9. 所有模块必须包含 logging 和异常处理。
10. 每个阶段完成后必须有可运行命令、测试样例和输出文件。
11. 不把 GPT、OpenAlex、SciRepEval 或 OpenCitations 标签写成 gold。
```

## 方法主线

IAD-Risk 主流程：

```text
公开数据与元数据
    ↓
IAD-Bench 分层样本构造
    ↓
候选文献对召回
    ↓
identity / agenda 双空间表示
    ↓
same_work / same_agenda / agenda_non_identity / false_merge_risk 多任务学习
    ↓
风险约束重复组合并
    ↓
canonical document 生成
    ↓
强 baseline、消融、错误分析和审稿矩阵
```

## 数据层级

```text
gold：DeepMatcher DBLP-ACM / DBLP-Scholar
distant：DOI / arXiv id / OpenAlex work id
proxy：SciRepEval / SciDocs
silver：OpenAlex / OpenCitations
llm_silver：GPT 或其他 LLM
human_audit：后续人工审查
```

## 工程阶段

### P0：课题与契约重构

```text
文档主线改为 IAD-Risk
IAD-Bench 契约写入
topic package 包含设计文档、标注规范和契约
审稿矩阵升级到模型深度、强 baseline 和标签 provenance
```

### P1：IAD-Bench 构造器

```text
状态：已完成 fixture 级构造器，待扩展大规模公开数据
gold / proxy / silver 合并
train / dev / test split
iad_bench_summary.jsonl
label_provenance_summary.csv
dataset_card.md
RQ 报告 iad_bench_provenance 证据层
```

### P2：强 baseline

```text
状态：执行框架已完成，真实强模型仍待运行
SPECTER2 / SciNCL
Ditto / RoBERTa
LLM pair judge
single-space union-find
IAD-Sieve rule-only baseline
baseline_family / execution_mode 审稿证据
```

### P3：IAD-Risk 模型

```text
状态：lightweight dual-space model 已完成，Transformer 级扩展待做
identity / agenda / risk 三组特征
same_work / same_agenda / agenda_non_identity 三个 head
risk-aware merge
transformer dual encoder / cross encoder
关键消融
```

### P4：期刊增强

```text
human_audit gold set
error analysis
reviewer response package
二区 / B 类投稿包
```

## 验收标准

P0 验收：

```text
1. 文档不再以完整推荐系统或规则去重系统作为主线；
2. 方法贡献围绕 identity-agenda confusion 和 hard negative false merge；
3. IAD-Bench 强制 label_strength 和 label_provenance；
4. 最终课题包包含 IAD-Risk 设计；
5. pytest 通过；
6. 本地与远程项目文件同步。
```

最终目标验收：

```text
1. 至少一个 same_work gold 完整实验；
2. 至少一个 hard negative 完整实验；
3. 至少两个科研表示强 baseline；
4. 至少一个实体匹配强 baseline；
5. 至少一个 LLM judge baseline；
6. IAD-Risk 在 hard_negative_false_merge_rate 上优于 rule-only 和 single-space baseline；
7. 消融证明 agenda_non_identity 与 false_merge_risk 有贡献；
8. 审稿矩阵显示创新、先进性和深度风险已被实验证据覆盖。
```
