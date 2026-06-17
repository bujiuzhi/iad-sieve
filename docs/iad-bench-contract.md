# IAD-Bench 数据契约

## 契约目标

IAD-Risk 需要同时使用公开 gold、proxy benchmark、weak / silver label、LLM 生成候选标签和人工复核标签。若这些标签混在同一个指标里，读者无法判断结论的证据强度。

IAD-Bench 的目标是把不同来源的科研文献 pair 统一成可追踪、可分层、可复现实验数据。它不是一个单一数据集名称，而是一套数据组织契约。

## 核心规则

所有 IAD-Bench 样本必须显式标注：

```text
标签是什么
标签从哪里来
标签强度是多少
能否作为 gold 使用
属于训练、验证还是测试
是否是 hard negative
```

禁止把 OpenAlex、SciRepEval、LLM 标签或引用邻近关系写成 gold label。

## 标签层级

| label_strength | 来源 | 可否作为 gold | 用途 |
| --- | --- | --- | --- |
| `gold` | DeepMatcher DBLP-ACM / DBLP-Scholar | 是 | same_work 主评估 |
| `distant` | DOI / arXiv id / OpenAlex work id 高置信匹配 | 否 | 扩展训练和鲁棒性分析 |
| `proxy` | SciRepEval / SciDocs proximity | 否 | same_agenda proxy 评估 |
| `silver` | OpenAlex topic / OpenCitations shared reference | 否 | agenda_non_identity hard negative |
| `llm_silver` | LLM 生成候选判断 | 否 | 数据增强和解释分析 |
| `human_audit` | 人工复核 | 可作为独立复核 gold | 论文增强和误差分析 |

## 关系标签

### same_work

两条记录指向同一篇 scholarly work，可以合并。

典型来源：

```text
DeepMatcher positive pair
same DOI
same arXiv id
same OpenAlex work id
```

### same_agenda

两篇文献属于相同或高度相近研究议题，但不一定能合并。

典型来源：

```text
SciRepEval / SciDocs proximity
OpenAlex same topic
shared citation community
```

### agenda_non_identity

两篇文献同议题或高度相关，但不是同一篇文献，不能合并。

典型来源：

```text
same topic + different DOI
shared references + different work id
high SPECTER2 / SciNCL similarity + different identity evidence
LLM suggested do_not_merge hard negative
```

### unrelated

两篇文献不是同一文献，也没有明显同议题关系。

典型来源：

```text
different topic
low title similarity
low abstract similarity
no shared authors
no shared references
```

### uncertain

无法稳定判断或属于版本边界样本。

典型情况：

```text
conference short paper vs journal extension
missing DOI and abstract
conflicting metadata
same authors and similar title but content not enough
```

## 文档字段

`iad_bench_documents.jsonl` 每行表示一篇标准化文献。

必填字段：

```json
{
  "document_id": "openalex:W123",
  "title": "paper title",
  "abstract": "paper abstract",
  "authors": ["author a", "author b"],
  "year": 2024,
  "venue": "venue name",
  "doi": "10.xxxx/example",
  "arxiv_id": "2401.00001",
  "openalex_work_id": "W123",
  "topics": ["information retrieval", "entity matching"],
  "references": ["W456", "W789"],
  "source_dataset": "openalex"
}
```

缺失字段使用空字符串、空数组或 `null`，不得省略必填字段。

## Pair 字段

`iad_bench_pairs.jsonl` 每行表示一对文献关系。

必填字段：

```json
{
  "pair_id": "iadbench_000001",
  "source_document_id": "openalex:W123",
  "target_document_id": "openalex:W456",
  "relation_label": "agenda_non_identity",
  "expected_label": 0,
  "expected_agenda_label": 1,
  "label_source": "openalex_opencitations",
  "label_strength": "silver",
  "label_provenance": {
    "same_topic": true,
    "shared_reference_count": 3,
    "same_doi": false,
    "same_arxiv_id": false,
    "llm_used": false
  },
  "split": "train",
  "hard_negative_level": "high"
}
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `pair_id` | 全局唯一 pair ID |
| `source_document_id` | 左侧文献 ID |
| `target_document_id` | 右侧文献 ID |
| `relation_label` | `same_work`、`same_agenda`、`agenda_non_identity`、`unrelated`、`uncertain` |
| `expected_label` | same_work 二分类标签，1 表示可合并 |
| `expected_agenda_label` | same_agenda 二分类标签，1 表示议题相关 |
| `label_source` | 标签来源系统或数据集 |
| `label_strength` | `gold`、`distant`、`proxy`、`silver`、`llm_silver`、`human_audit` |
| `label_provenance` | 支撑标签的证据字段 |
| `split` | `train`、`dev`、`test`、`audit` |
| `hard_negative_level` | `none`、`low`、`medium`、`high` |

## 切分规则

### train

可包含：

```text
gold
distant
proxy
silver
llm_silver
```

必须保留 `label_strength`，训练报告中需分层统计。

### dev

可包含：

```text
gold
proxy
silver
```

用于阈值选择和模型选择。不得把 `llm_silver` 作为唯一 dev 信号。

### test

优先使用：

```text
gold
proxy
silver hard negative
```

测试报告必须分开呈现，不得汇总成一个无来源说明的总 F1。

### audit

保留给人工复核和边界样本分析。

```text
human_audit
uncertain
boundary cases
```

## Provenance 规则

`label_provenance` 必须记录生成标签的可解释证据。

same_work provenance 示例：

```json
{
  "same_doi": true,
  "same_arxiv_id": false,
  "same_openalex_work_id": true,
  "title_similarity": 0.97,
  "author_overlap": 0.90
}
```

agenda_non_identity provenance 示例：

```json
{
  "same_topic": true,
  "shared_reference_count": 5,
  "specter2_cosine": 0.86,
  "same_doi": false,
  "same_openalex_work_id": false,
  "title_exact_match": false
}
```

LLM provenance 示例：

```json
{
  "llm_used": true,
  "llm_model": "account_available_model",
  "llm_label": "agenda_non_identity",
  "llm_confidence": 0.91,
  "llm_reason": "same research agenda but different contributions and authors"
}
```

## Hard Negative 分级

| hard_negative_level | 判定规则 |
| --- | --- |
| `none` | unrelated 或普通 same_work |
| `low` | 同领域但标题和摘要相似度不高 |
| `medium` | 同 topic 或共享引用，但标题相似度一般 |
| `high` | 高语义相似、同 topic 或共享引用，同时 identity 证据明确不同 |

`high` hard negative 是 IAD-Risk 的核心测试对象。

## 指标输出

IAD-Bench 报告必须包含：

```text
same_work_precision
same_work_recall
same_work_f1
false_merge_rate
hard_negative_false_merge_rate
agenda_non_identity_precision
agenda_non_identity_recall
agenda_non_identity_f1
label_strength_breakdown
```

## 禁止事项

禁止：

- 把 `proxy`、`silver`、`llm_silver` 写成 gold；
- 把不同 `label_strength` 的结果混成一个主指标；
- 用 LLM 生成标签作为唯一测试集；
- 用训练中见过的 weak pair 作为无说明测试结果；
- 只报告普通 F1，不报告 hard negative false merge。

## 质量要求

IAD-Bench 的最低可用要求：

1. 至少接入 DeepMatcher same_work gold；
2. 至少接入 SciRepEval / SciDocs same_agenda proxy；
3. 至少接入 OpenAlex / OpenCitations agenda_non_identity silver；
4. 每条 pair 有 `label_strength` 和 `label_provenance`；
5. 输出 train/dev/test split；
6. 输出 label provenance summary；
7. 报告 gold、proxy、silver 分层指标。

投稿级补充要求：

1. 增加 500-1,000 条 `human_audit`；
2. 输出双标一致率和仲裁结果；
3. 对 `uncertain` 和版本边界样本单独分析；
4. 在论文说明中明确人工复核只用于独立评估，不污染训练集。
