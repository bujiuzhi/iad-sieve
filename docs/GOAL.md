# IAD-Risk：身份-议题解耦的误合并风险学习方法

版本：v4.0  
项目仓库名：`iad-sieve`  
论文方法名：`IAD-Risk`  
工程基线名：`IAD-Sieve`

## 问题拆解

科研文献去重的难点不是简单判断“像不像”，而是区分两种相似：

```text
same_work：两条记录是否是同一篇 scholarly work
same_agenda：两篇论文是否属于相同或相近研究议题
```

同议题论文通常在标题、摘要、关键词、引用社区上非常接近，但不能被合并。单一相似度、单空间 embedding 或普通 pair classifier 容易把 `same_agenda` 误判成 `same_work`，形成 false merge。

## 关键结论

`iad-sieve` 的课题主线升级为 IAD-Risk。系统最终要证明：

```text
IAD-Risk 能在保持 same_work 识别能力的同时，降低 same_agenda_non_identity hard negative 上的误合并率。
```

`IAD-Sieve` 不再作为论文主方法，而是保留为 rule-only baseline 和工程流水线。

## 1. 研究定位

IAD-Risk 面向科研文献组织中的 identity-agenda confusion。

核心假设：

```text
同一文献身份和同一研究议题是两种不同关系；
文献去重必须优先控制 false merge；
同议题非同身份样本应成为 hard negative，而不是普通负例。
```

方法输出：

```text
p_same_work
p_same_agenda
p_agenda_non_identity
p_false_merge_risk
```

合并条件：

```text
p_same_work >= tau_work
p_agenda_non_identity < tau_block
p_false_merge_risk < tau_risk
cannot_link == false
```

## 2. 贡献边界

### 主创新

1. 定义科研文献去重中的 `identity-agenda confusion` 问题；
2. 构建 `IAD-Bench`，分层组织 gold、distant、proxy、silver、llm_silver 和 human_audit 样本；
3. 设计身份-议题双空间风险学习框架；
4. 以 `hard_negative_false_merge_rate` 作为核心指标评估同议题误合并风险。

### 不作为主创新

以下内容只作为实现、baseline 或下游验证：

```text
arXiv metadata 使用
BM25 / FAISS / cosine similarity
SPECTER2 / SciNCL / sentence-transformers 调用
Ditto / RoBERTa / LLM pair judge baseline
完整推荐系统
聚类可视化
人工标注流程本身
```

## 3. 数据证据链

### Gold

DeepMatcher DBLP-ACM / DBLP-Scholar 用于 same_work gold 评估。

报告指标：

```text
same_work precision
same_work recall
same_work F1
false_merge_rate
```

### Distant Supervision

DOI、arXiv id、OpenAlex work id 可构造 high-confidence same_work distant label。

限制：

```text
这些标签不能与人工 gold 混写；
版本合并、元数据错误和扩展版论文需要单独分析。
```

### Proxy

SciRepEval / SciDocs proximity pair 用于 same_agenda proxy。

限制：

```text
相关性不等于 duplicate gold；
只能证明议题邻近或检索相关。
```

### Silver

OpenAlex topic、OpenCitations shared reference、high semantic similarity + different identity evidence 用于构造 `agenda_non_identity` silver hard negative。

限制：

```text
OpenAlex 和 OpenCitations 不能作为 same_work gold；
它们用于训练扩展、鲁棒性分析和 hard negative 测试。
```

### LLM Silver

GPT 或其他 LLM 可以用于候选解释、软标签和争议样本筛选。

限制：

```text
LLM 标签不是 gold；
论文中必须写作 llm_silver 或 teacher signal。
```

### Human Audit

人工审查暂不进入当前 P0-P3 依赖，保留为 P4 期刊增强。

目标规模：

```text
500-1,000 pair
```

## 4. 阶段目标

### P0：课题与数据契约重构

产出：

```text
IAD-Risk 设计文档
IAD-Bench 数据契约
核心文档重写
最终课题包导出
审稿风险矩阵升级
```

验收：

```text
本地和远程测试通过；
最终课题包包含 IAD-Risk、IAD-Bench、标注规范；
审稿矩阵明确指出强 baseline、模型深度、标签 provenance 风险。
```

### P1：IAD-Bench 构造器

状态：fixture 级构造器已完成，后续需要扩展到大规模公开数据。

产出：

```text
iad_bench_documents.jsonl
iad_bench_pairs.jsonl
iad_bench_splits.jsonl
iad_bench_summary.jsonl
dataset_card.md
label_provenance_summary.csv
```

已接入：

```text
build-iad-bench CLI
gold / proxy / silver 标签强度映射
label_provenance
train / dev / test split
RQ 报告 iad_bench_provenance 证据层
最终课题包 IAD-Bench 产物复制
```

### P2：强 Baseline

状态：执行框架已完成，真实强模型结果仍待补齐。

必须覆盖：

```text
SPECTER2 cosine
SciNCL cosine
sentence-transformers scientific model
Ditto / RoBERTa pair classifier
LLM pair judge
single-space union-find
IAD-Sieve rule-only baseline
```

已接入：

```text
run-representation-baseline CLI
run-entity-matching-baseline CLI
run-llm-judge-baseline CLI
build-baseline-error-analysis CLI
run-single-space-union-baseline CLI
run-iad-evidence-bootstrap CLI
baseline_family
execution_mode
fallback 检测
external_baseline 统一评估
SciNCL actual_model
RoBERTa / DistilBERT pair classifier actual_model
LLM judge fallback 链路验证
hard_negative_false_merge_rate 错误分析
single-space union-find actual_algorithm 对照
IAD-Risk / strong baseline bootstrap confidence interval
审稿矩阵三类强 baseline 真实执行判定
```

审稿边界：

```text
execution_mode = fallback 只能说明接口跑通；
只有 representation / entity_matching / llm_judge 三类真实执行同时出现，才能消除强 baseline 风险。
当前仍缺 LLM judge api_model；RoBERTa / DistilBERT 是 pair-classification 迁移 baseline，不等同于 Ditto 专用复现。
```

### P3：IAD-Risk 模型

状态：lightweight dual-space model 已完成，Transformer 级模型仍待扩展。

产出：

```text
identity_space
agenda_space
multi-task heads
false_merge_risk head
risk-aware merge
```

已接入：

```text
train-iad-risk-model CLI
iad_risk_model.json
iad_risk_summary.jsonl
iad_risk_predictions.jsonl
RQ3 iad_risk_model 证据层
审稿矩阵 model_depth 风险判定
```

当前边界：

```text
当前模型是 standardized centroid heads 的 lightweight 实现；
只能证明双空间、多 head 和 risk merge policy 已落地；
二区 / B 类仍需要真实强 baseline、大规模数据和更强模型实验。
```

### P4：期刊级增强

产出：

```text
human_audit gold set
error analysis
reviewer response matrix
二区 / B 类投稿包
```

## 5. 研究问题

### RQ1：same_work 能力

IAD-Risk 是否能在公开 same_work gold benchmark 上保持有效的身份判定能力？

### RQ2：hard negative 误合并抑制

IAD-Risk 是否能降低 same_agenda_non_identity hard negative 上的 false merge？

### RQ3：双空间与风险头贡献

去掉 identity space、agenda space、agenda_non_identity loss 或 false_merge_risk 后，性能是否下降？

### RQ4：弱监督鲁棒性

gold、proxy、silver、llm_silver 的组合是否能降低 hard negative false merge，同时不破坏 same_work gold F1？

## 6. 审稿风险

| 风险 | 当前处理 |
| --- | --- |
| baseline 太弱 | P2 执行强模型 baseline |
| 方法只是规则组合 | P3 升级双空间风险学习 |
| 标签不可信 | IAD-Bench 强制 label_strength 与 provenance |
| 无人工标注 | P4 保留 human audit，P0-P3 不夸大结论 |
| 创新不足 | 聚焦 identity-agenda confusion 和 hard negative false merge |
| 指标普通 | 主指标加入 hard_negative_false_merge_rate |

## 7. 最终完成标准

达到二区 / B 类目标前，必须满足：

1. DeepMatcher same_work gold 完整实验；
2. SciRepEval / OpenAlex hard negative 完整实验；
3. 至少两个科研表示强 baseline；
4. 至少一个实体匹配强 baseline；
5. 至少一个 LLM judge baseline；
6. IAD-Risk 相比 IAD-Sieve rule-only 和 single-space baseline 降低 hard_negative_false_merge_rate；
7. 消融证明 `agenda_non_identity` 与 `false_merge_risk` 贡献；
8. 关键 hard negative 指标包含 bootstrap 置信区间，避免只报告小样本点估计；
9. 论文包包含实验表、误差分析、审稿回应和人工 audit 后续计划。
