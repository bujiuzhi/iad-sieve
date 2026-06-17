# IAD-Risk 实验计划

## Objective

IAD-Risk 的实验不能只证明去重 F1，而要证明：

```text
同议题非同身份 hard negative 不会被误合并。
```

因此实验必须同时覆盖 same_work gold、same_agenda proxy、agenda_non_identity silver、强模型 baseline 和双空间风险学习消融。

## Evidence Structure

实验主线采用 IAD-Bench 分层证据链：

```text
gold：DeepMatcher same_work
distant：DOI / arXiv / OpenAlex work id
proxy：SciRepEval / SciDocs same_agenda
silver：OpenAlex / OpenCitations agenda_non_identity
llm_silver：LLM 辅助软标签
human_audit：后续人工复核增强，不作为 P0-P3 自动化链路依赖
```

所有结果必须按标签强度分层报告。

## 1. 数据集

### 1.1 DeepMatcher

用途：

```text
same_work gold
```

数据：

```text
DBLP-ACM
DBLP-Scholar
Dirty DBLP-ACM
Dirty DBLP-Scholar
```

指标：

```text
same_work_precision
same_work_recall
same_work_f1
false_merge_rate
```

命令：

```bash
python -m iad_sieve.cli prepare-deepmatcher \
  --table-a data/raw/deepmatcher/DBLP-ACM/tableA.csv \
  --table-b data/raw/deepmatcher/DBLP-ACM/tableB.csv \
  --pairs data/raw/deepmatcher/DBLP-ACM/test.csv \
  --dataset-name DBLP-ACM \
  --output-dir outputs/deepmatcher/DBLP-ACM/test
```

### 1.2 SciRepEval / SciDocs

用途：

```text
same_agenda proxy
agenda_non_identity proxy hard negative
```

限制：

```text
SciRepEval / SciDocs 相关性不能写成 duplicate gold。
```

命令：

```bash
python -m iad_sieve.cli prepare-scirepeval-proximity \
  --metadata data/raw/scirepeval/scidocs_view_cite_read/metadata.jsonl \
  --pairs data/raw/scirepeval_test/scidocs_cite/test.jsonl \
  --dataset-name scidocs_cite \
  --output-dir outputs/scirepeval/scidocs_cite/test \
  --min-relevance-score 1.0
```

### 1.3 OpenAlex / OpenCitations

用途：

```text
agenda_non_identity silver hard negative
same_work distant supervision
topic / citation provenance
```

公开 API 拉取命令：

```bash
python -m iad_sieve.cli fetch-openalex-works \
  --output data/raw/openalex/works_api_sample.jsonl \
  --summary-output outputs/openalex_api_ingestion/ingestion_summary.jsonl \
  --filter "from_publication_date:2020-01-01,type:article" \
  --select "id,doi,display_name,publication_year,authorships,primary_topic,topics,referenced_works,abstract_inverted_index" \
  --per-page 100 \
  --max-records 1000 \
  --seed 42
```

该命令生成公开数据采集 summary，用于记录 endpoint、filter、select、per_page、max_records、seed、是否使用 API key 和实际拉取数量。若进入正式实验，应把 `max_records` 提升到 50k-150k 级别或切换 OpenAlex snapshot。

IAD-Bench-Open-v1 压力测试命令：

```bash
python -m iad_sieve.cli fetch-openalex-works \
  --output data/raw/openalex/iad_bench_open_v1_works.jsonl \
  --summary-output outputs/openalex_api_ingestion_v1/ingestion_summary.jsonl \
  --filter "primary_topic.id:T10009,publication_year:2024,type:article" \
  --select "id,doi,display_name,publication_year,authorships,primary_topic,topics,referenced_works" \
  --per-page 100 \
  --max-records 1000

python -m iad_sieve.cli prepare-openalex-weak-labels \
  --works data/raw/openalex/iad_bench_open_v1_works.jsonl \
  --dataset-name iad_bench_open_v1_t10009_2024 \
  --output-dir outputs/openalex_api_v1 \
  --min-shared-references 1 \
  --max-pairs-per-topic 10000 \
  --max-pairs 10000 \
  --limit 1000

python -m iad_sieve.cli build-iad-bench \
  --source-dirs outputs/openalex_api_v1 \
  --output-dir outputs/iad_bench_open_v1 \
  --train-ratio 0.8 \
  --dev-ratio 0.1 \
  --seed 42
```

v1 参考产物包含 1,000 条 OpenAlex Works、963 篇有效文档、10,000 对 `agenda_non_identity` silver hard negative。该数据只用于公开 hard-negative 压力测试，不能替代 same_work gold 或 human audit。

IAD-Bench-Open-v2 是不依赖新增人工标注的主实验数据包。它把 py_entitymatching 公开 DBLP-ACM same_work gold 与 OpenAlex hard negative 合并，形成同时包含 identity 正负样本和 agenda_non_identity 压力样本的分层 benchmark。

命令：

```bash
python -m iad_sieve.cli prepare-deepmatcher \
  --table-a data/raw/deepmatcher/py_entitymatching_dblp_acm/tableA.csv \
  --table-b data/raw/deepmatcher/py_entitymatching_dblp_acm/tableB.csv \
  --pairs data/raw/deepmatcher/py_entitymatching_dblp_acm/test.csv \
  --dataset-name py_entitymatching_dblp_acm \
  --output-dir outputs/deepmatcher_public_dblp_acm

python -m iad_sieve.cli build-iad-bench \
  --source-dirs outputs/deepmatcher_public_dblp_acm outputs/openalex_api_v1 \
  --output-dir outputs/iad_bench_open_v2 \
  --train-ratio 0.8 \
  --dev-ratio 0.1 \
  --seed 42
```

v2 参考产物：

```text
document_count：1,737
pair_count：10,415
gold_pair_count：415
same_work_pair_count：231
unrelated_gold_pair_count：184
silver_pair_count：10,000
agenda_non_identity_pair_count：10,000
human_audit_pair_count：0
```

边界：

```text
v2 可以作为公开可复现实验主线；
OpenAlex 仍是 silver，不写成人工 gold；
DBLP-ACM gold 规模偏小，正式论文扩展前需继续补充 DBLP-Scholar、Dirty DBLP 系列或人工复核样本。
```

构造规则：

```text
same topic
shared references >= threshold
different DOI
different OpenAlex work id
high semantic similarity
```

命令：

```bash
python -m iad_sieve.cli prepare-openalex-weak-labels \
  --works data/raw/openalex/works_sample.jsonl \
  --citations data/raw/opencitations/coci_sample.csv \
  --dataset-name openalex_cs_sample \
  --output-dir outputs/openalex/openalex_cs_sample \
  --min-shared-references 1 \
  --max-pairs-per-topic 200 \
  --max-pairs 5000
```

### 1.4 LLM Silver

用途：

```text
候选解释
soft label
争议样本筛选
LLM pair judge baseline
```

限制：

```text
LLM 输出不能作为 gold；
必须记录 model、prompt version、confidence 和 reason。
```

### 1.5 Human Audit

人工审查不作为自动化复现链路的前置条件。

增强目标：

```text
500-1,000 pair
same_work / same_agenda_non_identity / unrelated / uncertain 分层
双人独立标注 + 仲裁
```

## 2. IAD-Bench 构造

IAD-Bench 构造器统一输出：

```text
iad_bench_documents.jsonl
iad_bench_pairs.jsonl
iad_bench_splits.jsonl
iad_bench_summary.jsonl
dataset_card.md
label_provenance_summary.csv
```

核心字段：

```text
pair_id
source_document_id
target_document_id
relation_label
expected_label
expected_agenda_label
label_source
label_strength
label_provenance
split
hard_negative_level
```

split 设计：

```text
train：gold + distant + proxy + silver + llm_silver
dev：gold + proxy + silver
test：gold / proxy / silver 分层报告
audit：后续 human_audit
```

构建命令：

```bash
python -m iad_sieve.cli build-iad-bench \
  --source-dirs outputs/deepmatcher_fixture outputs/scirepeval_fixture outputs/openalex_fixture \
  --output-dir outputs/iad_bench_fixture \
  --seed 11 \
  --train-ratio 0.5 \
  --dev-ratio 0.25
```

下一步不是改字段契约，而是扩大 `source_dirs` 到真实公开数据输出目录，并在 RQ 报告中持续保留 `--iad-bench-summaries`。

主实验构造命令：

```bash
python -m iad_sieve.cli build-iad-bench \
  --source-dirs outputs/deepmatcher_public_dblp_acm outputs/openalex_api_v1 \
  --output-dir outputs/iad_bench_open_v2 \
  --seed 42 \
  --train-ratio 0.8 \
  --dev-ratio 0.1
```

## 3. Baseline

### 3.1 规则 baseline

```text
BM25 threshold
title-author-year rule
DOI / arXiv exact match
IAD-Sieve rule-only
```

### 3.2 科研表示 baseline

```text
SPECTER2 cosine
SciNCL cosine
sentence-transformers scientific model
single-space union-find
```

执行框架命令：

```bash
python -m iad_sieve.cli run-representation-baseline \
  --documents outputs/iad_bench_fixture/iad_bench_documents.jsonl \
  --pairs outputs/iad_bench_fixture/iad_bench_pairs.jsonl \
  --output outputs/strong_baseline_fixture/baseline_scores.jsonl \
  --summary-output outputs/strong_baseline_fixture/baseline_execution_summary.jsonl \
  --system-name specter2_adapter_cosine \
  --embedding-model allenai/specter2_base \
  --adapter-model allenai/specter2 \
  --model-backend specter2-adapter \
  --pooling-strategy cls
```

SPECTER2 复核必须使用 adapter 路径：`allenai/specter2_base` 作为 base encoder，`allenai/specter2` 作为 proximity adapter。直接以 `transformers` 后端加载 base model 只能作为兼容性尝试，不能优先作为正式强 baseline。

SciNCL 命令：

```bash
python -m iad_sieve.cli run-representation-baseline \
  --documents outputs/iad_bench_fixture/iad_bench_documents.jsonl \
  --pairs outputs/iad_bench_fixture/iad_bench_pairs.jsonl \
  --output outputs/strong_baseline_fixture/scincl_scores.jsonl \
  --summary-output outputs/strong_baseline_fixture/scincl_execution_summary.jsonl \
  --system-name scincl_cosine \
  --embedding-model malteos/scincl \
  --model-backend sentence-transformers
```

统一评估：

```bash
python -m iad_sieve.cli evaluate-external-baseline \
  --relations outputs/iad_bench_fixture/iad_bench_pairs.jsonl \
  --baseline outputs/strong_baseline_fixture/baseline_scores.jsonl \
  --output outputs/strong_baseline_fixture/baseline_scored_relations.jsonl \
  --summary-output outputs/strong_baseline_fixture/baseline_metric_summary.jsonl \
  --system-name specter2_adapter_cosine \
  --score-field score \
  --output-score-field specter2_score \
  --thresholds 0.5,0.8,0.9 \
  --metric-target same_work \
  --baseline-family representation \
  --execution-mode actual_model
```

证据边界：

```text
execution_mode = actual_model 才能作为真实强 baseline；
execution_mode = fallback 只能作为工程接口验证。
```

IAD-Bench-Open-v2 的 SciNCL actual_model 对比结果：

```text
system：scincl_cosine_open_v2
model：malteos/scincl
execution_mode：actual_model
document_count：1,737
pair_count：10,415
threshold = 0.8
same_work_f1：0.054393
hard_negative_false_merge_rate_mean：0.790663
```

解释：SciNCL 是科学文献表示强 baseline，但单空间 cosine 相似度会把大量同议题 OpenAlex hard negative 误判为 same_work。该结果正好支撑 IAD-Risk 的问题设定：科学语义相似不能直接等价为身份相同。

### 3.3 实体匹配 baseline

```text
Ditto
RoBERTa pair classifier
DeepMatcher
```

接口要求：

```text
run-entity-matching-baseline CLI
textattack/roberta-base-MRPC actual_model
textattack/distilbert-base-uncased-MRPC actual_model
heuristic_entity_matcher fallback
baseline_family = entity_matching
```

证据边界：RoBERTa/DistilBERT 是 pair-classification 迁移 baseline，不是 Ditto/DeepMatcher 论文级复现。若论文强调实体匹配强基线，需要继续补 Ditto/DeepMatcher 专用实现或公开 checkpoint。

IAD-Bench-Open-v2 的 transformers entity-matching actual_model 对比结果：

```text
system：distilbert_mrpc_open_v2
model：textattack/distilbert-base-uncased-MRPC
device：cuda
threshold = 0.8
same_work_f1：0.359270
hard_negative_false_merge_rate_mean：0.061683

system：roberta_pair_open_v2
model：textattack/roberta-base-MRPC
device：cuda
threshold = 0.8
same_work_f1：0.824691
hard_negative_false_merge_rate_mean：0.000103
```

解释：RoBERTa pair classifier 是较强对照，hard-negative 误合并率接近 IAD-Risk；因此创新论证不能只说“比 baseline 低误合并”，还要证明 IAD-Risk 在可解释风险分解、弱监督扩展和不同标签层泛化上有额外价值。

### 3.4 LLM baseline

```text
zero-shot LLM pair judge
few-shot LLM pair judge
LLM with explanation
```

接口要求：

```text
run-llm-judge-baseline CLI
OpenAI Responses API structured output
fallback lexical judgment
baseline_family = llm_judge
```

证据边界：缺少 `OPENAI_API_KEY` 时只能生成 `execution_mode = fallback` 的链路验证产物；只有 API 实际调用成功并输出 `execution_mode = api_model` 时，证据矩阵才会把 LLM judge 计为真实强 baseline。

统一输出：

```text
baseline_scores.jsonl
baseline_summary.csv
baseline_error_cases.jsonl
```

## 4. IAD-Risk 模型实验

### P3.1 lightweight dual-space

使用现有可解释特征构造：

```text
identity feature group
agenda feature group
risk feature group
```

输出：

```text
p_same_work
p_same_agenda
p_agenda_non_identity
p_false_merge_risk
```

训练命令：

```bash
python -m iad_sieve.cli train-iad-risk-model \
  --relations outputs/deepmatcher_fixture/scored_relations.jsonl outputs/scirepeval_fixture/scored_relations.jsonl outputs/openalex_fixture/scored_relations.jsonl \
  --output-dir outputs/iad_risk_model_fixture \
  --seed 7 \
  --work-threshold 0.5 \
  --agenda-block-threshold 0.5 \
  --risk-threshold 0.5
```

输出：

```text
iad_risk_model.json
iad_risk_summary.jsonl
iad_risk_predictions.jsonl
```

fixture 参考结果：

```text
same_work_f1 = 1.0
same_agenda_f1 = 0.8
agenda_non_identity_f1 = 0.8
```

IAD-Bench-Open-v2 参考结果：

```bash
python -m iad_sieve.cli train-iad-risk-model \
  --relations outputs/iad_bench_open_v2/iad_bench_pairs.jsonl \
  --output-dir outputs/iad_risk_open_v2 \
  --seed 7 \
  --work-threshold 0.5 \
  --agenda-block-threshold 0.5 \
  --risk-threshold 0.5
```

```text
trained = true
trained_head_count = 2
required_head_count = 2
same_work_f1 = 0.970213
same_agenda_f1 = 0.0
agenda_non_identity_f1 = 0.99975
```

解释：

```text
required heads 是 same_work 与 agenda_non_identity；
same_agenda 在 v2 中因缺少平衡 proxy 标签作为 auxiliary head，不能把 0.0 写成主任务失败；
但如果论文强调 agenda 关系学习，必须补 SciRepEval/SciDocs 或人工 same_agenda 标签。
```

边界：

```text
该结果只证明 lightweight IAD-Risk 结构跑通；
真实强 baseline、Transformer 扩展和更大规模 gold 完成前，不能写成期刊最终主结论。
```

### P3.2 transformer dual encoder

升级方向不是把 SciNCL/SPECTER2 只作为外部 cosine baseline，而是把冻结科学文献 Transformer 表示接入 IAD-Risk 主方法：

```text
document encoder：SPECTER2 / SciNCL / SciBERT
identity head：判断 same_work
agenda head：判断 same_agenda
risk head：判断 agenda_non_identity 与 false_merge_risk
```

输出：

```text
iad_risk_transformer_model.json
iad_risk_transformer_summary.jsonl
iad_risk_transformer_predictions.jsonl
all / train / dev / test 分层指标
encoder execution_mode
embedding_model / embedding_version / embedding_dim
train_pair_count / eval_pair_count
```

命令：

```bash
python -m iad_sieve.cli train-iad-risk-transformer-model \
  --documents outputs/iad_bench_open_v2/iad_bench_documents.jsonl \
  --relations outputs/iad_bench_open_v2/iad_bench_pairs.jsonl \
  --output-dir outputs/iad_risk_transformer_open_v2 \
  --embedding-model malteos/scincl \
  --model-backend sentence-transformers \
  --batch-size 64 \
  --train-split train \
  --seed 7 \
  --work-threshold 0.5 \
  --agenda-block-threshold 0.5 \
  --risk-threshold 0.5
```

实现边界：

```text
这是 frozen encoder + transparent risk heads，不是端到端微调；
它能补足模型深度和 split-aware 证据，但若目标是更强创新，应继续扩展为可微 fine-tuning 或 cross-encoder risk head；
训练特征禁止使用 label_provenance、label_source、label_strength 等标签来源字段，避免数据泄漏。
```

IAD-Bench-Open-v2 actual_model 参考结果：

```text
encoder：malteos/scincl
execution_mode：actual_model
train_pair_count：8,332
eval_pair_count：10,415

all：
  same_work_f1 = 0.955789
  agenda_non_identity_f1 = 0.996512
  merge_f1 = 0.961864
  false_merge_rate = 0.001375

test：
  same_work_f1 = 0.979592
  agenda_non_identity_f1 = 0.997030
  merge_f1 = 0.979592
  false_merge_rate = 0.000982

bootstrap hard_negative_false_merge_rate_mean = 0.0
```

结果解释：

```text
Transformer 版比 lightweight 版本更能支撑模型深度和 split-aware 训练；
hard negative 上没有误合并，说明 risk head 学到了同议题非同身份阻断；
但 all split 的 same_work_f1 低于 lightweight 版本，说明 frozen encoder + transparent head 仍不是最终最优结构；
下一步应比较 SPECTER2 encoder，并考虑 cross-encoder / fine-tuning 提升 gold same_work 召回。
```

## 5. RQ 设计

### RQ1：same_work 判定

问题：

```text
IAD-Risk 是否能在 same_work gold benchmark 上保持有效 F1？
```

数据：

```text
DeepMatcher
high-confidence distant split
```

### RQ2：hard negative false merge

问题：

```text
IAD-Risk 是否能降低 same_agenda_non_identity hard negative 的误合并率？
```

数据：

```text
SciRepEval / SciDocs
OpenAlex / OpenCitations
LLM silver hard negative
```

### RQ3：模型深度

问题：

```text
双空间、多任务头和 risk head 是否必要？
```

消融：

```text
w/o identity_space
w/o agenda_space
w/o agenda_non_identity loss
w/o false_merge_risk
single-space embedding
IAD-Sieve rule-only
```

### RQ4：弱监督鲁棒性

问题：

```text
加入 proxy / silver / llm_silver 是否提升 hard negative 表现，同时不损害 gold same_work？
```

训练设置：

```text
gold only
gold + proxy
gold + proxy + silver
gold + proxy + silver + llm_silver
```

## 6. 指标

主指标：

```text
same_work_precision
same_work_recall
same_work_f1
false_merge_rate
hard_negative_false_merge_rate
agenda_non_identity_precision
agenda_non_identity_recall
agenda_non_identity_f1
```

辅助指标：

```text
cross_space_separation_score
calibration_error
bootstrap confidence interval
label_strength_breakdown
```

IAD 专用 bootstrap 命令：

```bash
python -m iad_sieve.cli run-iad-evidence-bootstrap \
  --records outputs/iad_risk_model/iad_risk_predictions.jsonl \
  --output outputs/iad_bootstrap/iad_risk_bootstrap_confidence.csv \
  --system-name iad_risk_dual_space \
  --prediction-field merge_prediction \
  --iterations 1000 \
  --confidence-level 0.95
```

强 baseline 使用 `score_field + threshold`：

```bash
python -m iad_sieve.cli run-iad-evidence-bootstrap \
  --records outputs/strong_baselines/scincl_scored_relations.jsonl \
  --output outputs/iad_bootstrap/scincl_bootstrap_confidence.csv \
  --system-name scincl_cosine \
  --score-field scincl_score \
  --threshold 0.9 \
  --iterations 1000 \
  --confidence-level 0.95
```

报告时必须优先解释 `hard_negative_pairs` 和 `same_agenda_negative_pairs` 的置信区间。若样本量较小，置信区间过宽时只能作为链路验证，不能作为期刊主结论。

## 7. 报告规则

必须分开报告：

```text
gold result
distant result
proxy result
silver result
llm_silver result
human_audit result
```

禁止：

```text
把 proxy/silver/llm_silver 写成 gold；
只汇总一个总体 F1；
只和规则 baseline 对比；
只报告普通 false_merge_rate 而不报告 hard_negative_false_merge_rate。
```

## 8. 验收条件

实验报告应区分链路验证、真实模型运行和论文主实验，不把未运行的强 baseline、人工 gold 或大规模实验写成既有结果。

最低验收项：

1. IAD-Bench 契约、数据处理流程和 provenance summary 可复验。
2. RQ 报告能追踪 `iad_bench_provenance` 证据层。
3. IAD-Risk 模型输出 `iad_risk_model` 证据层。
4. SciNCL、RoBERTa/DistilBERT 或同等级强 baseline 至少包含 `actual_model` 结果。
5. `build-baseline-error-analysis` 输出 `hard_negative_false_merge_rate` 和错误案例。
6. `run-single-space-union-baseline` 输出普通并查集合并对照。
7. `run-iad-evidence-bootstrap` 输出 IAD-Risk 与强 baseline 分层置信区间。
8. 自动化测试和公开发布检查通过。

后续增强项：

1. 多 topic / 多学科公开数据扩展到 50k-150k pair；
2. LLM judge `api_model` 实际运行；
3. Transformer 级 IAD-Risk 双空间模型；
4. 远程大样本验证；
5. 后续人工复核增强。
