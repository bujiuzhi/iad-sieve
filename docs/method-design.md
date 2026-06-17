# IAD-Risk 方法设计

## Motivation

科研文献去重中，语义相似性有两种含义：

```text
身份相似：两条记录是同一篇文献
议题相似：两篇论文研究相同或相近问题
```

传统单空间相似度把这两类关系混在一起，容易把同议题论文误合并为同一文献。IAD-Risk 的设计目标是显式分离身份空间和议题空间，并把同议题非同身份样本作为 hard negative 建模。

## Core Design

IAD-Risk 是一个风险学习框架：

```text
identity_space 学 same_work
agenda_space 学 same_agenda
agenda_non_identity 学 hard negative
false_merge_risk 由关系信号派生并控制合并
```

IAD-Sieve 保留为 rule-only baseline，其字段与合并器继续服务于工程兼容。

## 1. 输入表示

每篇文献标准化为：

```text
title
abstract
authors
venue
year
doi
arxiv_id
openalex_work_id
references
topics / concepts
```

每个 pair 还包含候选证据：

```text
title_similarity
author_overlap
identifier_match
semantic_similarity
shared_reference_count
same_topic
label_strength
label_provenance
```

## 2. 双空间编码

IAD-Risk 为同一文献生成两个向量：

```text
z_identity = f_identity(document)
z_agenda   = f_agenda(document)
```

### identity_space

目标是识别同一 scholarly work。

强证据：

```text
same DOI
same arXiv id
same OpenAlex work id
title near-duplicate
high author overlap
same venue / year
```

### agenda_space

目标是识别相同研究议题。

强证据：

```text
shared research problem
similar abstract
same OpenAlex topic
shared references
same benchmark or method family
high SPECTER2 / SciNCL similarity
```

## 3. Pair 关系信号

模型训练三个关系头，并由这些关系信号派生合并风险：

```text
p_same_work
p_same_agenda
p_agenda_non_identity
p_false_merge_risk = max(
  p_agenda_non_identity,
  p_same_agenda * (1 - p_same_work)
)
```

### p_same_work

表示 pair 是否可合并为同一文献。

### p_same_agenda

表示 pair 是否属于同一研究议题或引用社区。

### p_agenda_non_identity

表示 pair 议题相关但不能合并。

典型样本：

```text
BERT vs RoBERTa
同一数据集上的不同方法论文
同一任务下的综述论文与方法论文
同一引用社区中的不同贡献
```

### p_false_merge_risk

表示执行合并的风险。

高风险来源：

```text
p_agenda_non_identity 高
identifier 缺失或冲突
作者证据不足
年份或 venue 冲突
same_agenda 高但 p_same_work 不高
```

## 4. 训练目标

### same_work

约束：

```text
z_identity_i 接近 z_identity_j
p_same_work = 1
p_agenda_non_identity = 0
```

来源：

```text
DeepMatcher gold
same DOI distant
same arXiv id distant
same OpenAlex work id distant
```

### same_agenda_non_identity

约束：

```text
z_agenda_i 接近 z_agenda_j
z_identity_i 远离 z_identity_j
p_agenda_non_identity = 1
p_same_work = 0
```

来源：

```text
SciRepEval / SciDocs proxy
OpenAlex same-topic different-work
OpenCitations shared-reference
high semantic similarity + different identity evidence
LLM silver hard negative
```

### unrelated

约束：

```text
z_identity_i 远离 z_identity_j
z_agenda_i 远离 z_agenda_j
p_same_work = 0
p_same_agenda = 0
```

来源：

```text
different topic
low title and abstract similarity
no shared author / reference / keyword
```

## 5. 训练目标

训练损失覆盖三个监督关系：

```text
L = L_same_work
  + L_same_agenda
  + L_agenda_non_identity
  + L_consistency
```

一致性约束：

```text
p_same_work 高 => p_agenda_non_identity 低
p_agenda_non_identity 高 => p_same_work 低
p_same_agenda 高 不推出 p_same_work 高
```

## 6. 合并决策

IAD-Risk 的合并规则：

```text
p_same_work >= tau_work
p_agenda_non_identity < tau_block
p_false_merge_risk < tau_risk
cannot_link == false
```

IAD-Sieve rule-only baseline 的合并规则保留：

```text
identity_score >= tau_identity
agenda_non_identity_score < tau_block
false_merge_risk < tau_risk
```

两者都使用 constrained union-find，区别在于 IAD-Risk 的分数来自可训练模型。

## 7. IAD-Bench 接口

模型训练和评估统一读取 IAD-Bench pair 字段：

```text
relation_label
expected_label
expected_agenda_label
label_strength
label_provenance
hard_negative_level
split
```

报告时必须按 `label_strength` 分层：

```text
gold
distant
proxy
silver
llm_silver
human_audit
```

## 8. Baseline 接口

IAD-Risk 必须和以下强 baseline 对比：

```text
SPECTER2 cosine
SciNCL cosine
sentence-transformers scientific model
Ditto / RoBERTa pair classifier
LLM pair judge
single-space union-find
IAD-Sieve rule-only
```

所有 baseline 必须输出统一 pair score 或 prediction，进入同一报告器。

## 9. 评价指标

核心指标：

```text
same_work_precision
same_work_recall
same_work_f1
false_merge_rate
hard_negative_false_merge_rate
agenda_non_identity_precision
agenda_non_identity_recall
agenda_non_identity_f1
calibration_error
```

核心评价：

```text
在 same_work F1 不明显下降的情况下，hard_negative_false_merge_rate 是否降低。
```

## 10. 实现边界

Lightweight dual-space model 使用 identity、agenda、risk 三组特征训练 `same_work`、`same_agenda`、`agenda_non_identity` 三个 head，并由派生的 `p_false_merge_risk` 控制 `merge_prediction`。

Transformer-based model 使用冻结科学文档编码器与同一组关系头，适合在固定表示条件下验证身份证据、议题证据和 hard negative 风险之间的分离效果。
