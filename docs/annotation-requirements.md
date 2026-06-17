## 标注对象

每条样本是一对科研文献：

```text
paper_a, paper_b
```

标注员需要根据题名、作者、年份、摘要、出版源、DOI、arXiv id、关键词、引用信息等判断两篇文献的关系。

标注对象不要求标注员判断论文质量、创新性或推荐价值，只判断文献对关系。

## 标签定义

### same_work

定义：两条记录指向同一篇 scholarly work，可以被合并为同一文献记录。

判定依据：

- DOI、arXiv id、OpenAlex work id 等强标识一致；
- 标题基本一致，仅有大小写、标点、格式、短横线、子标题等差异；
- 作者列表高度一致；
- 摘要、研究问题、实验内容和主要贡献高度一致；
- 一个是预印本版本，另一个是正式发表版本，且可以明确判断为同一研究工作。

可标为 `same_work` 的例子：

```text
paper_a: Attention Is All You Need, arXiv preprint
paper_b: Attention Is All You Need, NeurIPS published version
```

不能标为 `same_work` 的情况：

- 只是研究主题相似；
- 只是方法名称相同；
- 只是同一作者团队的后续工作；
- 只是会议短文与扩展期刊版，但新增内容明显较多且无法确认数据库规则是否允许合并。

### same_agenda_non_identity

定义：两篇论文属于相同或高度相近的研究议题，但不是同一篇文献，不能合并。

判定依据：

- 研究问题、任务、方法族、数据集或关键词高度相似；
- 标题或摘要语义接近；
- 可能共享引用、研究社区或 OpenAlex topic；
- DOI、arXiv id、标题、作者或主要贡献不同；
- 合并后会造成误合并。

可标为 `same_agenda_non_identity` 的例子：

```text
paper_a: BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding
paper_b: RoBERTa: A Robustly Optimized BERT Pretraining Approach
```

说明：两篇论文都研究预训练语言模型，议题非常接近，但它们是不同论文，不能合并。

### unrelated

定义：两篇论文不是同一文献，也不属于明显相同的研究议题。

判定依据：

- 标题、摘要、关键词、任务、领域明显不同；
- 没有明显共享研究问题；
- 即使作者、年份或少量通用词相同，也不足以构成同议题关系。

可标为 `unrelated` 的例子：

```text
paper_a: Graph Neural Networks for Molecular Property Prediction
paper_b: Query Optimization in Relational Databases
```

### uncertain

定义：根据提供字段无法稳定判断，或样本属于版本、扩展版、元数据冲突等边界情况。

应标为 `uncertain` 的情况：

- 会议短文与期刊扩展版，内容相似但新增内容明显；
- 标题相近、作者相同，但摘要缺失；
- DOI 缺失且来源元数据冲突；
- 论文可能是同一工作不同版本，但无法确认；
- 标注员需要依赖外部搜索才能判断。

`uncertain` 不作为模型主要正负例训练标签，主要用于误差分析和规则边界讨论。

## 标注字段

每条样本建议包含以下字段：

```json
{
  "pair_id": "audit_000001",
  "source_dataset": "openalex_hard_negative",
  "paper_a": {
    "document_id": "A001",
    "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
    "authors": ["Jacob Devlin", "Ming-Wei Chang", "Kenton Lee", "Kristina Toutanova"],
    "year": 2019,
    "venue": "NAACL",
    "doi": "",
    "arxiv_id": "1810.04805",
    "abstract": "..."
  },
  "paper_b": {
    "document_id": "B001",
    "title": "RoBERTa: A Robustly Optimized BERT Pretraining Approach",
    "authors": ["Yinhan Liu", "Myle Ott", "Naman Goyal"],
    "year": 2019,
    "venue": "arXiv",
    "doi": "",
    "arxiv_id": "1907.11692",
    "abstract": "..."
  },
  "candidate_evidence": {
    "title_similarity": 0.71,
    "same_topic": true,
    "shared_keywords": ["BERT", "pretraining", "language model"],
    "same_doi": false,
    "same_arxiv_id": false,
    "shared_author_count": 0
  },
  "annotator_label": "same_agenda_non_identity",
  "annotator_confidence": 0.95,
  "annotation_notes": "两篇论文都研究预训练语言模型，但标题、作者和具体贡献不同，不能合并。"
}
```

## 标注规则

### 优先级规则

1. 如果能确认是同一篇文献，标 `same_work`。
2. 如果主题高度接近但不能合并，标 `same_agenda_non_identity`。
3. 如果既不是同一文献，也没有明显同议题关系，标 `unrelated`。
4. 如果无法稳定判断，标 `uncertain`。

### 禁止规则

标注员不得因为以下单一因素直接判定为 `same_work`：

- 标题中有相同关键词；
- 使用同一数据集；
- 使用同一模型名称；
- 属于同一领域；
- 作者团队部分重叠；
- 年份相同；
- 摘要语义相似。

标注员不得因为以下情况直接判定为 `unrelated`：

- 标题不同但研究问题高度一致；
- 作者不同但任务、方法和引用社区高度相近；
- DOI 缺失。

## 标注流程

### 阶段 1：试标

先抽取 50 至 100 条样本进行试标。

目标：

- 检查字段是否足够；
- 发现标签定义歧义；
- 统一 same_work 与 same_agenda_non_identity 的边界；
- 修改标注规范。

### 阶段 2：正式双标

正式样本建议采用双人独立标注。

规模建议：

- 正式标注范围：500 至 1,000 条 pair；
- 最低可用规模：500 条 pair；
- 推荐规模：800 至 1,000 条 pair；
- 若只作为内部误差分析，可先完成 500 条；若作为投稿增强证据，建议接近 1,000 条。

要求：

- 每条样本至少由 2 名标注员独立标注；
- 标注员不应看到模型最终预测结果；
- 可展示候选证据，但应避免展示 GPT 生成的结论性标签；
- 两名标注员不一致时进入仲裁。

### 阶段 3：仲裁

仲裁员处理双标不一致样本。

仲裁输出：

- `final_label`
- `adjudication_reason`
- `is_boundary_case`

边界样本不强行归入正负例，可保留为 `uncertain`。

## 质量控制

建议验收指标：

| 指标 | 最低要求 | 推荐要求 |
| --- | ---: | ---: |
| 双标一致率 | >= 80% | >= 85% |
| Cohen's Kappa | >= 0.70 | >= 0.75 |
| 仲裁完成率 | 100% | 100% |
| 缺失关键字段比例 | <= 5% | <= 2% |
| `uncertain` 占比 | <= 15% | <= 10% |

如果双标一致率低于 80%，需要重新培训标注员并修订标签定义。

## 数据来源建议

### same_work 候选

来源：

- DeepMatcher DBLP-ACM / DBLP-Scholar positive pair；
- DOI 相同；
- arXiv id 相同；
- OpenAlex work id 相同；
- 标题、作者、年份高度一致。

### same_agenda_non_identity 候选

来源：

- SciRepEval / SciDocs proximity pair；
- OpenAlex same topic；
- OpenCitations shared references；
- SPECTER2 / SciNCL 高相似但 DOI 不同；
- GPT 辅助筛选的 hard negative。

### unrelated 候选

来源：

- 不同 OpenAlex topic；
- 低标题相似度；
- 低摘要相似度；
- 无共享作者、无共享引用、无共享关键词。

### uncertain 候选

来源：

- 会议版与期刊扩展版；
- 标题近似但摘要缺失；
- DOI 冲突；
- 元数据字段不完整；
- 模型之间预测冲突的样本。

## GPT 辅助使用边界

GPT 可以用于：

- 生成候选 hard negative；
- 提供 pair 解释；
- 生成 silver label；
- 帮助筛选需要人工复核的争议样本。

GPT 不应作为：

- 最终人工 gold label；
- 仲裁员；
- 评价模型优劣的唯一依据。

建议标注流程中保留两套字段：

```text
llm_suggested_label：GPT 建议标签，只用于分析
final_label：人工最终标签，用于论文评估
```

正式标注时，默认不向标注员展示 `llm_suggested_label`，避免标注偏置。

## 验收产物

标准部门最终应交付：

1. `iad_risk_human_gold.jsonl`：逐条人工标注结果；
2. `iad_risk_human_gold.csv`：便于抽查的表格版本；
3. `annotation_summary.csv`：标签分布、标注员数量、一致率、仲裁数量；
4. `disagreement_cases.jsonl`：双标不一致样本与仲裁结果；
5. `boundary_cases.jsonl`：uncertain 和版本边界样本；
6. `annotation_guideline_version.txt`：标注规范版本号。
