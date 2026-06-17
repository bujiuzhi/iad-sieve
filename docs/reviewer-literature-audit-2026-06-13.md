# 审稿式相似工作核查

## 问题拆解

当前方法不能表述为“没有相似工作”。更准确的定位是：在实体匹配、科学文献表征和学术元数据质量控制之间，专门研究“同议题但非同一文献”的误合并风险。

## 关键结论

可主张的创新边界：

```text
IAD-Risk 不是通用 entity matching，也不是通用文献 embedding；
它把 same_work、same_agenda、agenda_non_identity 和 false_merge_risk 明确拆开，
并用 provenance-aware IAD-Bench 评估同议题 hard negative 下的误合并风险。
```

不能主张的内容：

```text
不能说没有重复工作；
不能说已经超过 SPECTER2、SciNCL、RoBERTa、Ditto 或 LLM entity matcher；
不能在远程强模型和 LLM judge 未跑完前声称达到二区 / B 类完成度。
```

## 相似工作边界

### 通用实体匹配

相关工作：

- Ditto：把实体匹配建模为 Transformer pair classification，并通过 domain knowledge、summarization 和 data augmentation 提升 EM 表现。
- LLM entity matching：用 GPT-4 等 LLM 做 zero-shot / few-shot 实体匹配，强调鲁棒性和解释。
- AnyMatch：用小语言模型做高效 zero-shot EM，并与多个 LLM / PLM baseline 比较。
- ComEM：比较 matching、comparing、selecting 三类 LLM entity matching 策略，并强调 record interaction。
- 2025-2026 年仍有 LLM calibration、multi-table entity matching 等新工作。

区别：

```text
这些方法主要回答“两个记录是不是同一实体”；
IAD-Risk 还要回答“它们很像、同议题，但是否仍然不能合并”。
```

审稿要求：

```text
必须把 RoBERTa / Ditto-style pair classifier / LLM pair judge 纳入强 baseline；
否则 baseline_strength 和 executed_strong_baselines 不能通过。
```

### 科学文献表征

相关工作：

- SPECTER：利用 citation graph 学科学文献 document-level representation。
- SciNCL：通过 citation embedding neighborhood contrastive learning 学科学文献相似度。
- SciRepEval / SPECTER2：提出多格式科学文献表征评估，并发布 SPECTER2 多格式模型。
- Topic Is Not Agenda：从 citation-community 角度审计 text embeddings，指出 topic、agenda 与 embedding similarity 之间存在边界。

区别：

```text
SPECTER2 / SciNCL 主要提供相似度空间；
IAD-Risk 需要证明相似度空间会把同议题 hard negative 推近，
因此需要 false_merge_risk 或 agenda_non_identity 约束。
```

审稿要求：

```text
必须报告 SciNCL / SPECTER2 在 same_agenda 或 agenda_non_identity hard negative 上的 false_merge_rate；
不能只报告普通 F1。
必须说明 IAD-Risk 不是另一个 embedding audit，而是面向 scholarly work deduplication 的 false merge risk 方法。
```

### DBLP 学术知识图谱实体链接

相关工作：

- DBLPLink：面向 DBLP scholarly knowledge graph 的实体链接系统。
- DBLPLink 2.0：面向 DBLP 2025 RDF knowledge graph 的 zero-shot LLM entity linker。

区别：

```text
DBLPLink 关注文本 mention 或候选实体到 DBLP 知识图谱实体的链接；
IAD-Risk 关注文献记录之间 same_work 与 same_agenda 的误合并风险。
```

审稿要求：

```text
不能只在 DBLP 来源上证明效果；
必须保留 scholarly-only gold、cross-domain balanced gold 和 source-held-out 的分轨报告。
```

### 开放学术元数据

相关工作：

- OpenAlex 提供开放 Works、Authors、Sources、Topics 等实体和 API / snapshot。
- 近期 OpenAlex 质量研究指出其覆盖广，但仍存在 abstract、affiliation、reference、document type、versioning 和 authority control 等元数据质量风险。

区别：

```text
OpenAlex 是数据基础设施；
IAD-Risk 使用 OpenAlex 构造同 topic、共享引用、不同 work id 的 silver hard negative，
但不能把它写成人工 gold。
```

审稿要求：

```text
OpenAlex / OpenCitations 来源必须标注为 silver；
DeepMatcher / py_entitymatching 等公开 gold 才能支撑 same_work 主评估；
人工 gold 暂缓时，论文必须把 human audit 写成后续增强。
```

## 当前审稿判断

当前可以防守：

```text
问题定义：defensible
公开 gold 规模与来源平衡：defensible
消融与 bootstrap 设计：defensible
可复现工程链路：defensible
```

当前仍会被质疑：

```text
强 baseline 是否真实执行：not_ready
SPECTER2 / LLM judge 是否完成：not_ready
Transformer 双空间模型是否真正优于规则 baseline：conditional
OpenAlex hard negative 是否可靠：conditional
二区 / B 类完成度：blocked
```

## 外部来源

- Ditto: https://arxiv.org/abs/2004.00584
- Entity Matching using Large Language Models: https://arxiv.org/abs/2310.11244
- Match, Compare, or Select? An Investigation of Large Language Models for Entity Matching: https://arxiv.org/abs/2405.16884
- AnyMatch: https://arxiv.org/abs/2409.04073
- LLM4MEM: https://arxiv.org/abs/2604.21238
- SPECTER: https://arxiv.org/abs/2004.07180
- SciNCL: https://arxiv.org/abs/2202.06671
- SciRepEval / SPECTER2: https://arxiv.org/abs/2211.13308
- Topic Is Not Agenda: https://arxiv.org/abs/2605.07158
- DBLPLink: https://arxiv.org/abs/2309.07545
- DBLPLink 2.0: https://arxiv.org/abs/2507.22811
- OpenAlex paper: https://arxiv.org/abs/2205.01833
- OpenAlex developer reference: https://developers.openalex.org/llms.txt
- OpenAlex metadata limitations: https://arxiv.org/abs/2512.16434
