# Prior Art Audit 2026-06-13

## 问题拆解

本审计回答三个问题：

1. 当前课题是否只是通用 entity matching、DBLP entity linking 或科学文献 embedding 的重复工作。
2. IAD-Risk 与 SPECTER2、SciNCL、Ditto、LLM entity matching、DBLPLink 和 OpenAlex 等相邻工作的可辩护差异在哪里。
3. 审稿人最可能从创新、先进性、方法深度和数据可信度四个方向如何攻击。

## 结论

截至 2026-06-13 的公开检索，未发现与 `IAD-Risk` 完全同名、且同时以 `same_work / same_agenda / agenda_non_identity / false_merge_risk` 为核心机制的直接重复工作。

但相邻工作非常强，不能写成“没有相似工作”。可辩护表述应收窄为：

```text
IAD-Risk 不是通用实体匹配，也不是普通科学文献表示学习；
它专门建模科研文献去重中的同议题误合并风险，
把“语义相近”与“同一 scholarly work”拆开，
并通过 provenance-aware IAD-Bench、source-held-out、topic-held-out 和 false_merge_rate 评估该风险。
```

## 相邻工作

### 通用实体匹配

代表来源：

- Ditto: Deep Entity Matching with Pre-Trained Language Models  
  https://arxiv.org/abs/2004.00584
- Entity Matching using Large Language Models  
  https://arxiv.org/abs/2310.11244
- Match, Compare, or Select? An Investigation of Large Language Models for Entity Matching  
  https://arxiv.org/abs/2405.16884
- Fine-tuning Large Language Models for Entity Matching  
  https://arxiv.org/abs/2409.08185
- AnyMatch: Efficient Zero-Shot Entity Matching with a Small Language Model  
  https://arxiv.org/abs/2409.04073

相似点：

```text
都把两个记录是否指向同一实体作为核心判断；
都可使用 Transformer、RoBERTa、BERT、LLM 或小语言模型；
都关注少标注、跨域和零样本实体匹配。
```

关键区别：

```text
通用实体匹配主要回答“两个记录是不是同一实体”；
IAD-Risk 额外回答“两个科研文献很像、同议题、甚至共享引用时，为什么仍不能合并”。
```

审稿门槛：

```text
必须把 RoBERTa / DistilBERT / Ditto-style pair classifier / LLM pair judge 纳入同口径 baseline；
必须报告 false_merge_rate，而不能只报告 same_work F1；
LLM judge 未跑完前，不能声称比 LLM entity matching 更先进。
```

### 科学文献表征

代表来源：

- SPECTER: Document-level Representation Learning using Citation-informed Transformers  
  https://arxiv.org/abs/2004.07180
- SciNCL: Neighborhood Contrastive Learning for Scientific Document Representations with Citation Embeddings  
  https://arxiv.org/abs/2202.06671
- SciRepEval / SPECTER2: A Multi-Format Benchmark for Scientific Document Representations  
  https://arxiv.org/abs/2211.13308
- Topic Is Not Agenda: A Citation-Community Audit of Text Embeddings  
  https://arxiv.org/abs/2605.07158

相似点：

```text
都服务于科学文献表示、检索、推荐、聚类或相似度建模；
SPECTER / SciNCL / SPECTER2 是 IAD-Risk 必须比较或复用的强表示模型。
```

关键区别：

```text
科学文献 embedding 主要产生相似度空间；
IAD-Risk 研究的是相似度空间在去重场景下的失败边界：
同主题、同研究议程或共享引用的论文可能被推得很近，但它们仍不是同一篇 work。
```

`Topic Is Not Agenda` 对 IAD-Risk 是双重信号：

```text
它支持“topic / agenda / embedding similarity 不等价”的问题意识；
但它也抬高审稿要求，要求 IAD-Risk 明确说明自己不是另一个 embedding audit，
而是面向 scholarly work deduplication 的 false merge risk 方法。
```

审稿门槛：

```text
必须执行 SciNCL、SPECTER2 adapter、single-space cosine 和 IAD-Risk Transformer 对比；
必须在 hard-negative false_merge_rate 上证明单空间 embedding 不足；
必须通过 provenance-blind 重训排除来源字段捷径。
```

### DBLP / 学术知识图谱实体链接

代表来源：

- DBLPLink: An Entity Linker for the DBLP Scholarly Knowledge Graph  
  https://arxiv.org/abs/2309.07545
- DBLPLink 2.0: An Entity Linker for the DBLP Scholarly Knowledge Graph  
  https://arxiv.org/abs/2507.22811

相似点：

```text
都涉及 DBLP scholarly knowledge graph；
都处理学术实体链接、候选生成、重排序或 LLM 辅助判断。
```

关键区别：

```text
DBLPLink 关注知识图谱实体链接；
IAD-Risk 关注文献记录去重中的 same_work 与 same_agenda 分离。
```

审稿门槛：

```text
必须避免把 DBLP gold 写成唯一泛化证据；
必须使用 source-held-out 和 scholarly-only / cross-domain balanced gold 分轨报告。
```

### 开放学术元数据

代表来源：

- OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts  
  https://arxiv.org/abs/2205.01833

相似点：

```text
OpenAlex 提供 Works、Authors、Sources、Topics 等开放元数据；
IAD-Risk 使用 OpenAlex topics、work ids、references 构造公开 silver hard negative。
```

关键区别：

```text
OpenAlex 是数据基础设施，不是去重风险模型；
OpenAlex work id 和 topic 只能作为 silver / distant evidence，不能写成人工 gold。
```

审稿门槛：

```text
OpenAlex hard negative 必须写成 silver；
DeepMatcher / py_entitymatching 等公开 gold 才能支撑 same_work 主评估；
人工标注暂缓时，human audit 只能写成后续增强。
```

## 审稿人批判

### 创新风险

风险：

```text
审稿人可能认为 IAD-Risk 只是把已有 EM、scientific embedding 和阈值规则重新组合。
```

优化：

```text
论文贡献必须围绕 false_merge_risk、agenda_non_identity、provenance-aware evaluation 和 mechanism triangulation；
不要把“使用 SciNCL/SPECTER2/LLM”写成方法创新。
```

### 先进性风险

风险：

```text
SPECTER2、SciNCL、RoBERTa pair classifier、LLM judge 和 AnyMatch 类零样本 EM 未闭环时，先进性不足。
```

优化：

```text
统一 same_work F1、agenda_non_identity F1、hard-negative false_merge_rate、source-held-out test 指标和 bootstrap 置信区间；
只有这些结果闭环后，才能讨论 advancedness。
```

### 深度风险

风险：

```text
如果 IAD-Risk 只是轻量规则或逻辑回归，容易被认为方法深度不足。
```

优化：

```text
保留可解释风险头，但必须补齐 IAD-Risk Transformer、encoder 稳定性、provenance-blind 重训、source-held-out 和 topic-held-out。
```

### 数据风险

风险：

```text
没有人工 gold 时，审稿人会质疑 OpenAlex silver hard negative 和公开 gold 的适用边界。
```

优化：

```text
严格区分 gold、silver、proxy 和 human_audit；
scholarly-only gold 作为领域主评估；
cross-domain balanced gold 作为来源捷径防御；
OpenAlex multi-topic silver 作为 hard-negative 风险控制，不替代人工 gold。
```

## 当前可写与不可写

可写：

```text
未发现直接覆盖 IAD-Risk 四类关系与 false_merge_risk 证据链的重复工作。
IAD-Risk 与通用 EM、科学文献 embedding、DBLP entity linking 和 OpenAlex 数据基础设施相邻但不等价。
```

不可写：

```text
不能写没有相似工作；
不能写已经优于 SPECTER2、SciNCL、Ditto、AnyMatch 或 LLM entity matching；
不能写 silver hard negative 等同人工 gold；
不能写已经达到二区 / B 类完成度。
```

## 下一轮实验优先级

1. 执行 SPECTER2 adapter baseline 与 IAD-Risk Transformer。
2. 执行 SciNCL / RoBERTa pair 在 open-v3 balanced、scholarly-only 和 source-held-out 上的 actual_model 结果。
3. 在远程安全配置 `OPENAI_API_KEY` 后执行 LLM pair judge baseline。
4. 对所有强 baseline 和 IAD-Risk 变体补充分层 bootstrap。
5. 重建 advanced_model_evidence、model_superiority_audit、innovation_depth_stress_test、q2b_acceptance_rubric 和 topic_package_final。
