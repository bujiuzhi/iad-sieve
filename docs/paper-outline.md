# IAD-Risk 论文大纲

## 问题拆解

论文不能写成“实现了一个文献去重系统”，而要写成：

```text
科研文献去重中的 identity-agenda confusion 会导致同议题论文被误合并。
```

IAD-Risk 的论文目标是证明双空间风险学习能降低 hard negative false merge。

## 关键结论

建议论文题目：

```text
IAD-Risk: Risk-Aware Identity-Agenda Disentanglement for Scholarly Work Deduplication
```

中文题目：

```text
面向科研文献误合并抑制的身份-议题解耦风险学习方法
```

## 摘要结构

1. 背景：科研文献去重依赖语义相似度和元数据匹配；
2. 问题：同议题论文在语义空间接近，但不是同一文献；
3. 方法：IAD-Risk 分离 identity space 和 agenda space，并学习 false_merge_risk；
4. 实验：在 gold、proxy、silver 和强 baseline 上验证；
5. 结果：重点报告 hard_negative_false_merge_rate 降低。

## 1. Introduction

应回答：

```text
为什么文献去重中的 false merge 比 missed duplicate 更危险？
为什么 same_agenda 不能被普通相似度合并？
为什么需要 identity-agenda disentanglement？
```

贡献写法：

1. 提出 `identity-agenda confusion` 问题；
2. 构建 IAD-Bench 分层评估契约；
3. 提出 IAD-Risk 双空间风险学习方法；
4. 系统比较 SPECTER2、SciNCL、Ditto、LLM judge 和 rule-only IAD-Sieve。

## 2. Related Work

必须覆盖：

```text
Entity matching and record linkage
Scholarly document representation
Scientific paper deduplication
Hard negative learning
Constrained clustering
LLM-based entity matching
```

核心区别：

```text
已有工作通常优化 same_work matching 或文献表示；
IAD-Risk 专门建模 same_agenda_non_identity hard negative，并以 false merge suppression 为核心目标。
```

## 3. Problem Formulation

定义：

```text
document pair: (d_i, d_j)
same_work
same_agenda
agenda_non_identity
false_merge_risk
hard_negative_false_merge_rate
```

核心约束：

```text
same_work => may_merge
same_agenda 不推出 may_merge
agenda_non_identity => cannot_merge
```

## 4. IAD-Bench

说明数据分层：

```text
gold
distant
proxy
silver
llm_silver
human_audit
```

强调：

```text
OpenAlex、SciRepEval、GPT 不是 gold；
所有实验按 label_strength 分层报告。
```

## 5. Method: IAD-Risk

### 5.1 Dual-Space Encoding

```text
z_identity = f_identity(document)
z_agenda = f_agenda(document)
```

### 5.2 Multi-Task Relation Heads

```text
p_same_work
p_same_agenda
p_agenda_non_identity
p_false_merge_risk
```

### 5.3 Consistency and Risk Loss

```text
same_work 高 => agenda_non_identity 低
agenda_non_identity 高 => same_work 低
same_agenda 高 不代表 same_work 高
```

### 5.4 Risk-Aware Merge

```text
p_same_work >= tau_work
p_agenda_non_identity < tau_block
p_false_merge_risk < tau_risk
```

## 6. Experiments

### RQ1：same_work

数据：

```text
DBLP-ACM
DBLP-Scholar
```

### RQ2：hard negative false merge

数据：

```text
SciRepEval / SciDocs
OpenAlex / OpenCitations
LLM silver hard negative
```

### RQ3：ablation

消融：

```text
w/o identity_space
w/o agenda_space
w/o agenda_non_identity
w/o false_merge_risk
single-space embedding
rule-only IAD-Sieve
```

### RQ4：weak supervision robustness

训练设置：

```text
gold only
gold + proxy
gold + proxy + silver
gold + proxy + silver + llm_silver
```

## 7. Baselines

必须比较：

```text
BM25 / title-author-year
SPECTER2 cosine
SciNCL cosine
sentence-transformers scientific model
Ditto / RoBERTa pair classifier
LLM pair judge
single-space union-find
IAD-Sieve rule-only
```

审稿重点：

```text
强 baseline 是否也会在 same_agenda_non_identity hard negative 上误合并。
```

## 8. Results

主表：

```text
same_work F1
false_merge_rate
hard_negative_false_merge_rate
agenda_non_identity F1
calibration error
```

所有表必须标明：

```text
label_strength
dataset
baseline
threshold
```

## 9. Error Analysis

必须分析：

```text
高议题相似但身份不同的误合并
同 DOI / arXiv 版本边界
LLM 判断错误
OpenAlex topic 过粗
作者同名或作者缺失
```

## 10. Limitations

必须诚实写：

```text
OpenAlex / SciRepEval / GPT 不是 gold；
人工 audit 暂作为后续增强；
双空间模型效果依赖 hard negative 构造质量；
不同领域的合并规则可能不同。
```

## 11. Reviewer Defense

| 审稿质疑 | 回应 |
| --- | --- |
| baseline 太弱 | 加入 SPECTER2、SciNCL、Ditto、LLM |
| 模型不新 | 创新在 identity-agenda risk formulation 与 hard negative false merge |
| weak label 不可信 | IAD-Bench 强制 label provenance，分层报告 |
| 无人工 gold | P4 增加 human audit；P0-P3 不夸大结论 |
| 只是工程系统 | IAD-Sieve 降为 baseline，IAD-Risk 作为主方法 |

## 12. 结论

结论应写：

```text
IAD-Risk 通过身份-议题双空间风险学习，降低科研文献去重中的同议题误合并风险。
```

不要写：

```text
本文构建了一个完整文献推荐系统。
本文证明 OpenAlex/GPT 标签是真实 gold。
```
