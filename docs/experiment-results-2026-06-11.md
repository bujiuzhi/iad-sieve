# 2026-06-11 真实 arXiv 实验记录

## 问题拆解

本轮工作验证三个问题：

1. Kaggle arXiv metadata 是否已完整下载并可复现实验；
2. 随机 50k 与 `cs.CL` 主题过滤 50k 是否能完整生成候选、关系、聚类、排序、推荐和论文产物；
3. 当前算法在真实 metadata 上的主要工程瓶颈和评估风险是什么。

## 结论

远程真实数据已完成下载，并基于同一份原始数据完成两轮 50k 实验：

- 随机 50k：`outputs/dev_50000`
- `cs.CL` 主题过滤 50k：`outputs/dev_50000_cs_CL`

随机样本适合验证端到端工程链路；`cs.CL` 样本提供更多弱正例，适合做初步 baseline 与消融对比。两者都不足以单独支撑最终期刊论文去重结论，后续必须补 synthetic duplicate、hard negative 和人工标注样本。

## 数据与产物

原始数据：

```text
data/raw/arxiv-metadata-oai-snapshot.json
size_bytes=5326165096
```

随机 50k 产物：

```text
candidate_pairs.jsonl      830326
pair_relations.jsonl       830326
canonical_documents.jsonl   50000
clusters.jsonl               1275
rankings.jsonl              50000
recommendations.jsonl          50
topic_graph.jsonl            7260
```

`cs.CL` 50k 产物：

```text
candidate_pairs.jsonl      856517
pair_relations.jsonl       856517
canonical_documents.jsonl   50000
clusters.jsonl                416
rankings.jsonl              50000
recommendations.jsonl          50
topic_graph.jsonl            1120
```

论文产物目录：

```text
outputs/paper_artifacts
outputs/paper_artifacts_cs_CL_50k
```

每个目录包含：

```text
tables/baseline_comparison.csv
tables/ablation_summary.csv
tables/run_summary.csv
tables/recommendation_summary.csv
tables/figure_index.csv
figures/baseline_f1.png
figures/cluster_size_distribution.png
figures/relation_type_distribution.png
```

## 关键指标

随机 50k 关系类型：

```text
unrelated                  824352
same_topic_non_duplicate     5972
suspected_duplicate             2
```

随机 50k 评估摘要：

```text
weak_label_count       5974
positive_label_count      2
negative_label_count   5972
cluster_count          1275
recommendation_count     50
```

`cs.CL` 50k 关系类型：

```text
unrelated                  855431
same_topic_non_duplicate     1074
suspected_duplicate             8
exact_duplicate                 4
```

`cs.CL` 50k 评估摘要：

```text
weak_label_count       1090
positive_label_count     17
negative_label_count   1073
cluster_count           416
recommendation_count     50
```

`cs.CL` 50k baseline 摘要：

| system | precision | recall | f1 | false_merge_rate |
|---|---:|---:|---:|---:|
| bm25_lexical_threshold | 0.772727 | 1.000000 | 0.871795 | 0.004660 |
| dense_cosine_threshold | 0.750000 | 0.529412 | 0.620690 | 0.002796 |
| title_author_year_rule | 1.000000 | 0.764706 | 0.866667 | 0.000000 |
| dense_threshold_dedup | 1.000000 | 0.352941 | 0.521739 | 0.000000 |
| rsl_sieve_conservative | 1.000000 | 0.235294 | 0.380952 | 0.000000 |
| rsl_sieve_review_inclusive | 1.000000 | 0.588235 | 0.740741 | 0.000000 |

## 工程修复

`src/iad_sieve/clustering/clusterer.py` 修复了大簇分类分布统计的 O(n²) 问题：

```text
修复前：对每个簇内文档重复扫描整个簇，cs.CL 大簇会长时间卡在聚类阶段。
修复后：使用 Counter 一次统计 primary_category_distribution。
```

新增测试：

```text
tests/test_clusterer.py
```

验证结果：

```text
本地 pytest: 24 passed
远程 pytest: 24 passed
```

## Synthetic Duplicate 与 Hard Negative 评估

新增评估集目录：

```text
outputs/eval_sets/cs_CL_50k_synth_hard_400
```

评估集规模：

```text
eval_documents.jsonl        759
eval_pairs.jsonl            400
positive synthetic pairs    200
hard negative pairs         200
```

v1 评分结果显示原始阈值偏保守：

| system | precision | recall | f1 | false_merge_rate |
|---|---:|---:|---:|---:|
| rsl_sieve_review_inclusive | 1.000000 | 0.135000 | 0.237885 | 0.000000 |
| duplicate_score_threshold | 1.000000 | 0.135000 | 0.237885 | 0.000000 |
| title_author_rule | 1.000000 | 0.370000 | 0.540146 | 0.000000 |

基于分数分布增加复核规则：

```text
first_author_match = 1
author_overlap >= 0.5
title_similarity >= 0.90
full_similarity >= 0.70
conflict_score <= conflict_threshold
=> suspected_duplicate
```

该规则只进入复核池，不直接进入 high_confidence_duplicate 合并，避免扩大自动误合并风险。

v2 评分结果：

| system | precision | recall | f1 | false_merge_rate |
|---|---:|---:|---:|---:|
| rsl_sieve_review_inclusive | 1.000000 | 0.555000 | 0.713826 | 0.000000 |
| duplicate_score_threshold | 1.000000 | 0.135000 | 0.237885 | 0.000000 |
| title_author_rule | 1.000000 | 0.370000 | 0.540146 | 0.000000 |

v2 关系类型交叉表：

```text
(label=1, suspected_duplicate)         111
(label=1, unrelated)                    72
(label=1, same_topic_non_duplicate)     17
(label=0, unrelated)                   199
(label=0, same_topic_non_duplicate)      1
```

这说明关系分离逻辑对 hard negative 仍保持保守，但 synthetic duplicate 召回仍有提升空间。

## 流式关系评分改造

新增流式评分接口：

```text
src/iad_sieve/relations/relation_pipeline.py
score_candidate_pairs_iter(...)
```

`score-relations` 子命令在 JSONL 输出时改为：

```text
read_jsonl(candidates) -> score_candidate_pairs_iter(...) -> write_jsonl(output)
```

收益：

```text
不再把全部候选对关系结果一次性保存在 relations list 中；
适合 100k 主实验前的分步流水线；
保留原 score_candidate_pairs(...) 兼容小样本和已有调用。
```

远程验证：

```text
input:  outputs/eval_sets/cs_CL_50k_synth_hard_400/eval_pairs.jsonl
output: outputs/eval_sets/cs_CL_50k_synth_hard_400/eval_pair_relations_stream.jsonl
count:  400
```

流式输出 summary 与 v2 评分一致：

```text
rsl_sieve_review_inclusive precision=1.000000 recall=0.555000 f1=0.713826 false_merge_rate=0.000000
```

## 参数敏感性分析

新增 CLI：

```text
python -m iad_sieve.cli run-sensitivity
```

远程输出：

```text
outputs/eval_sets/cs_CL_50k_synth_hard_400/parameter_sensitivity.csv
```

本轮扫描：

```text
duplicate_threshold: 0.65,0.70,0.75,0.80,0.82,0.85,0.88,0.90
topic_threshold:     0.60,0.65,0.70,0.75,0.80
candidate_cap:       1,3,5,10,25,50,100
```

duplicate_threshold 结果：

| threshold | precision | recall | f1 | false_merge_rate |
|---:|---:|---:|---:|---:|
| 0.65 | 1.000000 | 0.765000 | 0.866856 | 0.000000 |
| 0.70 | 1.000000 | 0.605000 | 0.753894 | 0.000000 |
| 0.75 | 1.000000 | 0.455000 | 0.625430 | 0.000000 |
| 0.82 | 1.000000 | 0.135000 | 0.237885 | 0.000000 |
| 0.90 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |

topic_threshold_for_tlnd 结果：

| threshold | precision | recall | f1 | note |
|---:|---:|---:|---:|---|
| 0.60 | 0.772201 | 1.000000 | 0.871460 | 覆盖 hard negative 最强，但会把较多 synthetic duplicate 判为 TLND |
| 0.65 | 0.778656 | 0.985000 | 0.869757 | 与 0.60 接近，稍保守 |
| 0.70 | 0.390805 | 0.170000 | 0.236934 | 召回明显不足 |
| 0.75 | 0.022222 | 0.005000 | 0.008163 | 过于保守 |

candidate_cap 在当前 400 pair 评估集上不敏感：

```text
cap=1..100 的指标完全一致。
原因：该评估集主要是一篇 source 对一个 synthetic pair 或少量 hard negative pair，不足以检验候选截断影响。
需要在 50k/100k 的真实 candidate_pairs 上按 source_id 分组抽样后再评估 candidate cap。
```

参数建议：

```text
1. 自动合并阈值仍不建议直接降到 0.65；
2. 可新增 review_threshold_candidate=0.65 作为人工复核/弱监督复核池；
3. TLND topic_threshold 可先试 0.65，而不是当前 0.75；
4. candidate_cap 需要换真实候选分布评估，当前 400 pair 不能证明。
```

## 风险与下一步

### 评估风险

真实 arXiv metadata 的弱正例仍然偏少。即使在 `cs.CL` 50k 样本中，弱正例也只有 17 个，不足以支撑稳定统计结论。

### 工程风险

关系评分仍是主要耗时阶段。50k 样本候选对约 83 万到 86 万，`pair_relations.jsonl` 接近 1GB。当前已完成流式写出，100k 主实验前还应继续做并行评分或分片任务调度。

### 下一步优先级

1. 在真实 candidate_pairs 上重新做 candidate cap 评估；
2. 将流式 relation scoring 继续扩展为多进程或分片任务调度；
3. 补人工标注 JSONL 样本；
4. 再运行 main_100k。

## 阈值配置与多扰动 synthetic 评估

已完成阈值配置化：

```text
duplicate_threshold
review_threshold
review_candidate_threshold
topic_threshold
contribution_threshold
conflict_threshold
```

`score-relations` 与 `run-pipeline` 均支持 CLI 覆盖：

```bash
python -m iad_sieve.cli score-relations \
  --review-candidate-threshold 0.65 \
  --topic-threshold 0.65

python -m iad_sieve.cli run-pipeline \
  --review-candidate-threshold 0.65 \
  --topic-threshold 0.65
```

默认阈值已按敏感性实验调整：

```text
review_candidate_threshold = 0.65
topic_threshold = 0.65
```

synthetic duplicate 扰动规则扩展为 5 类：

```text
title_subtitle_drop
author_abbreviation
abstract_sentence_drop
synonym_replacement
combined_title_author_abstract
```

远程新评估集：

```text
outputs/eval_sets/cs_CL_50k_synth_hard_400_v3
```

扰动规则分布：

| rule | count |
|---|---:|
| title_subtitle_drop | 40 |
| author_abbreviation | 40 |
| abstract_sentence_drop | 40 |
| synonym_replacement | 40 |
| combined_title_author_abstract | 40 |

v3 评分结果：

| system | precision | recall | f1 | false_merge_rate |
|---|---:|---:|---:|---:|
| rsl_sieve_review_inclusive | 1.000000 | 0.870000 | 0.930481 | 0.000000 |
| duplicate_score_threshold | 1.000000 | 0.460000 | 0.630137 | 0.000000 |
| title_author_rule | 1.000000 | 0.450000 | 0.620690 | 0.000000 |

v3 关系类型交叉表：

```text
(label=0, same_topic_non_duplicate)    197
(label=1, suspected_duplicate)         174
(label=1, unrelated)                    14
(label=1, same_topic_non_duplicate)     12
(label=0, unrelated)                     3
```

v3 参数敏感性摘要：

| analysis | best_value | precision | recall | f1 | false_merge_rate |
|---|---:|---:|---:|---:|---:|
| duplicate_threshold | 0.65 | 1.000000 | 0.865000 | 0.927614 | 0.000000 |
| topic_threshold_for_tlnd | 0.60 | 0.847458 | 1.000000 | 0.917431 | 0.180000 |
| candidate_cap | 1 | 1.000000 | 0.460000 | 0.630137 | 0.000000 |

解释：

```text
1. review_candidate_threshold=0.65 显著提升 synthetic duplicate 召回，并保持 hard negative false merge 为 0。
2. topic_threshold=0.65 是较稳妥的 TLND 默认值；0.60 召回更高，但会把更多 synthetic duplicate 判为 TLND。
3. candidate_cap 仍需在真实 candidate_pairs 分布上单独评估。
```

验证：

```text
本地 pytest: 30 passed
远程 pytest: 30 passed
```

## 真实 Candidate Cap 分析

新增 CLI：

```text
python -m iad_sieve.cli analyze-candidate-cap
```

远程输出：

```text
outputs/dev_50000/reports/candidate_cap_analysis.csv
outputs/dev_50000_cs_CL/reports/candidate_cap_analysis.csv
```

`cs.CL` 50k 结果：

| cap | retained_pair_ratio | suspected_retained | TLND_retained |
|---:|---:|---:|---:|
| 1 | 0.056534 | 8 / 8 | 213 / 1074 |
| 3 | 0.163592 | 8 / 8 | 499 / 1074 |
| 5 | 0.262802 | 8 / 8 | 677 / 1074 |
| 10 | 0.477332 | 8 / 8 | 925 / 1074 |
| 25 | 0.856549 | 8 / 8 | 1071 / 1074 |
| 50 | 1.000000 | 8 / 8 | 1074 / 1074 |

随机 50k 结果：

| cap | retained_pair_ratio | suspected_retained | TLND_retained |
|---:|---:|---:|---:|
| 1 | 0.058372 | 2 / 2 | 882 / 5972 |
| 3 | 0.168398 | 2 / 2 | 2052 / 5972 |
| 5 | 0.269181 | 2 / 2 | 2892 / 5972 |
| 10 | 0.483252 | 2 / 2 | 4228 / 5972 |
| 25 | 0.854743 | 2 / 2 | 5715 / 5972 |
| 50 | 0.999999 | 2 / 2 | 5972 / 5972 |

结论：

```text
cap=10 可以将关系评分量减少约 52%，但会损失较多 TLND 边；
cap=25 只能减少约 14% 到 15% 评分量，但基本保留 suspected duplicate 与 TLND；
100k 主实验如果优先保持方法证据完整，建议先用 max_candidate_per_document=25；
如果优先压缩耗时，可追加 cap=10 的消融实验，不作为主实验默认值。
```

验证：

```text
本地 pytest: 32 passed
远程 pytest: 32 passed
```

## 关系评分分片执行

`score-relations` 已支持按候选记录行号取模分片：

```bash
python -m iad_sieve.cli score-relations \
  --input outputs/eval_sets/cs_CL_50k_synth_hard_400_v3/eval_documents.jsonl \
  --views outputs/eval_sets/cs_CL_50k_synth_hard_400_v3/eval_views.jsonl \
  --candidates outputs/eval_sets/cs_CL_50k_synth_hard_400_v3/eval_pairs.jsonl \
  --output outputs/eval_sets/cs_CL_50k_synth_hard_400_v3/eval_pair_relations_shard_0.jsonl \
  --shard-count 2 \
  --shard-index 0
```

远程验证：

```text
shard_0 records = 200
shard_1 records = 200
merged records  = 400
unique pairs    = 400
```

分片合并后的关系类型分布与单文件流式评分一致：

```text
same_topic_non_duplicate    209
suspected_duplicate         174
unrelated                    17
```

100k 主实验建议：

```text
1. prepare/generate-candidates 仍单进程运行；
2. score-relations 使用 --shard-count 4 或 8 拆分；
3. 每个 shard 输出 pair_relations_shard_*.jsonl；
4. 合并 shard 后再执行 merge-duplicates、build-topic-graph、cluster、rank、recommend、evaluate。
```

验证：

```text
本地 pytest: 33 passed
远程 pytest: 33 passed
```

## 100k 分片主实验脚本

新增 `scripts/run_100k_sharded_experiment.sh`，用于执行 `main_100k` 主实验。

默认参数：

```text
sample_size = 100000
seed = 42
primary_category = cs.CL
shard_count = 4
max_candidate_per_document = 25
embedding_model = hashing-fallback
```

主入口 `scripts/run_main_experiment.sh` 已改为委托该脚本，仍兼容旧调用方式：

```bash
PYTHON_BIN=python scripts/run_main_experiment.sh 42
```

等价的显式命令：

```bash
PYTHON_BIN=python SHARD_COUNT=4 scripts/run_100k_sharded_experiment.sh 100000 42 cs.CL
```

输出目录：

```text
outputs/main_100k_cs_CL
outputs/paper_artifacts_main_100k_cs_CL
```

脚本按核心产物文件判断是否跳过步骤，支持断点续跑。关系评分阶段输出 `pair_relations_shard_*.jsonl`，全部分片成功后合并为 `pair_relations.jsonl`，再执行去重、主题图、聚类、排序、推荐、评估、candidate cap 分析和论文图表导出。

验证：

```text
本地脚本契约测试: 3 passed
```

## main_100k_cs_CL 主实验

远程命令：

```bash
PYTHON_BIN=/path/to/miniconda3/envs/iad-sieve/bin/python \
SHARD_COUNT=4 \
scripts/run_100k_sharded_experiment.sh 100000 42 cs.CL
```

运行参数：

```text
sample_size = 100000
primary_category = cs.CL
max_candidate_per_document = 25
lexical_max_candidate_pairs = 1500000
shard_count = 4
```

核心产物规模：

| artifact | records |
|---|---:|
| normalized_documents | 100000 |
| candidate_pairs | 1001022 |
| pair_relations | 1001022 |
| duplicate_groups | 99983 |
| canonical_documents | 99983 |
| topic_graph | 10007 |
| clusters | 1173 |
| rankings | 99983 |
| recommendations | 50 |

关系类型分布：

| relation_type | count |
|---|---:|
| exact_duplicate | 21 |
| suspected_duplicate | 182 |
| same_topic_non_duplicate | 9860 |
| unrelated | 990959 |

去重与聚类摘要：

```text
positive_relation_count = 21
merged_group_count = 14
duplicate_group_count = 99983
cluster_count = 1173
max_cluster_size = 67167
mean_cluster_size = 85.23699914748508
ranking_count = 99983
recommendation_count = 50
```

Baseline 与消融摘要：

| system / variant | precision | recall | f1 | false_merge_rate |
|---|---:|---:|---:|---:|
| bm25_lexical_threshold | 0.631579 | 1.000000 | 0.774194 | 0.002840 |
| dense_cosine_threshold | 0.405405 | 0.312500 | 0.352941 | 0.002231 |
| title_author_year_rule | 1.000000 | 0.562500 | 0.720000 | 0.000000 |
| dense_threshold_dedup | 1.000000 | 0.187500 | 0.315789 | 0.000000 |
| rsl_sieve_conservative | 1.000000 | 0.437500 | 0.608696 | 0.000000 |
| rsl_sieve_review_inclusive | 1.000000 | 0.916667 | 0.956522 | 0.000000 |
| ours_no_relation_separation | 0.405405 | 0.312500 | 0.352941 | 0.002231 |
| ours_no_tlnd | 0.004544 | 0.937500 | 0.009043 | 1.000000 |

Bootstrap 95% 置信区间：

| system | precision_mean | recall_mean | f1_mean | f1_95%_ci | false_merge_rate_mean | false_merge_rate_95%_ci |
|---|---:|---:|---:|---|---:|---|
| bm25_lexical_threshold | 0.631643 | 1.000000 | 0.772769 | [0.685714, 0.851923] | 0.002832 | [0.001824, 0.003857] |
| dense_cosine_threshold | 0.405757 | 0.316379 | 0.352593 | [0.219504, 0.476190] | 0.002238 | [0.001319, 0.003246] |
| title_author_year_rule | 1.000000 | 0.561042 | 0.715988 | [0.582237, 0.825476] | 0.000000 | [0.000000, 0.000000] |
| dense_threshold_dedup | 1.000000 | 0.185869 | 0.309682 | [0.142857, 0.463938] | 0.000000 | [0.000000, 0.000000] |
| rsl_sieve_conservative | 1.000000 | 0.436142 | 0.603739 | [0.451613, 0.735662] | 0.000000 | [0.000000, 0.000000] |
| rsl_sieve_review_inclusive | 1.000000 | 0.915280 | 0.955302 | [0.903194, 0.990485] | 0.000000 | [0.000000, 0.000000] |

配置：

```text
weak_label_count = 9907
bootstrap_iterations = 1000
confidence_level = 0.95
seed = 42
output = outputs/main_100k_cs_CL/reports/bootstrap_confidence.csv
paper_table = outputs/paper_artifacts_main_100k_cs_CL/tables/bootstrap_confidence.csv
```

Candidate cap 分析：

| cap | retained_pair_ratio | exact_retained | suspected_retained | TLND_retained |
|---:|---:|---:|---:|---:|
| 1 | 0.095180 | 14 / 21 | 167 / 182 | 2219 / 9860 |
| 3 | 0.270060 | 17 / 21 | 181 / 182 | 5042 / 9860 |
| 5 | 0.423980 | 20 / 21 | 182 / 182 | 6791 / 9860 |
| 10 | 0.717165 | 21 / 21 | 182 / 182 | 8984 / 9860 |
| 25 | 1.000000 | 21 / 21 | 182 / 182 | 9860 / 9860 |

错误分析与人工标注样本：

```text
output_dir = outputs/main_100k_cs_CL/reports/error_analysis
error_analysis_summary = error_analysis_summary.csv
error_cases = error_cases.jsonl
manual_annotation_sample = manual_annotation_sample.jsonl
annotation_sample_size = 100
```

错误分析摘要：

| system | TP | FP | TN | FN | precision | recall | f1 | false_merge_rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bm25_lexical_threshold | 48 | 28 | 9831 | 0 | 0.631579 | 1.000000 | 0.774194 | 0.002840 |
| dense_cosine_threshold | 15 | 22 | 9837 | 33 | 0.405405 | 0.312500 | 0.352941 | 0.002231 |
| title_author_year_rule | 27 | 0 | 9859 | 21 | 1.000000 | 0.562500 | 0.720000 | 0.000000 |
| dense_threshold_dedup | 9 | 0 | 9859 | 39 | 1.000000 | 0.187500 | 0.315789 | 0.000000 |
| rsl_sieve_conservative | 21 | 0 | 9859 | 27 | 1.000000 | 0.437500 | 0.608696 | 0.000000 |
| rsl_sieve_review_inclusive | 44 | 0 | 9859 | 4 | 1.000000 | 0.916667 | 0.956522 | 0.000000 |

导出规模：

```text
error_cases.jsonl = 234
manual_annotation_sample.jsonl = 100
paper_table = outputs/paper_artifacts_main_100k_cs_CL/tables/error_analysis_summary.csv
```

人工标注样本字段包含 `source_title`、`target_title`、`source_abstract`、`target_abstract`、作者、类别、年份、建议标签、待填写 `annotator_label` 与 `annotation_notes`。

人工标注评分工具：

```bash
python -m iad_sieve.cli score-manual-annotations \
  --input outputs/main_100k_cs_CL/reports/error_analysis/manual_annotation_sample.jsonl \
  --output-dir outputs/main_100k_cs_CL/reports/manual_annotation
```

当前样本尚未人工填写 `annotator_label`，评分摘要用于记录待标注覆盖状态：

| sample_count | labeled_count | unlabeled_count | suggested_agreement_rate | suggested_label_f1 |
|---:|---:|---:|---:|---:|
| 100 | 0 | 100 | 0.000000 | 0.000000 |

输出：

```text
outputs/main_100k_cs_CL/reports/manual_annotation/manual_annotation_summary.csv
outputs/main_100k_cs_CL/reports/manual_annotation/manual_annotation_disagreements.jsonl
outputs/paper_artifacts_main_100k_cs_CL/tables/manual_annotation_summary.csv
```

论文产物：

```text
outputs/paper_artifacts_main_100k_cs_CL/tables/run_summary.csv
outputs/paper_artifacts_main_100k_cs_CL/tables/baseline_comparison.csv
outputs/paper_artifacts_main_100k_cs_CL/tables/ablation_summary.csv
outputs/paper_artifacts_main_100k_cs_CL/tables/bootstrap_confidence.csv
outputs/paper_artifacts_main_100k_cs_CL/tables/error_analysis_summary.csv
outputs/paper_artifacts_main_100k_cs_CL/tables/manual_annotation_summary.csv
outputs/paper_artifacts_main_100k_cs_CL/tables/recommendation_summary.csv
outputs/paper_artifacts_main_100k_cs_CL/tables/figure_index.csv
outputs/paper_artifacts_main_100k_cs_CL/figures/baseline_f1.png
outputs/paper_artifacts_main_100k_cs_CL/figures/cluster_size_distribution.png
outputs/paper_artifacts_main_100k_cs_CL/figures/relation_type_distribution.png
```

### exact duplicate 合并修复

主实验第一次评估发现：

```text
exact_duplicate = 21
merged_group_count = 0
```

根因是 `exact_duplicate` 由 identifier 命中判定，但去重流水线仍把其 `duplicate_score` 交给并查集阈值 `0.92` 判断。100k 中 21 条 exact duplicate 的 `duplicate_score` 范围为 `0.2714275377151837` 到 `0.7895355917122195`，因此全部被阈值拦截。

修复：

```text
exact_duplicate 使用 1.0 作为并查集合并置信度；
high_confidence_duplicate 仍按 duplicate_score 阈值合并；
cannot-link 约束仍由 ConstrainedUnionFind 检查。
```

验证：

```text
本地 pytest: 37 passed
远程 pytest: 37 passed
修复后 main_100k_cs_CL: merged_group_count = 14
```

## large_300k_random 随机大样本实验

远程命令：

```bash
PYTHON_BIN=/path/to/miniconda3/envs/iad-sieve/bin/python \
RUN_ID=large_300k_random \
SHARD_COUNT=4 \
MAX_CANDIDATE_PER_DOCUMENT=25 \
BOOTSTRAP_ITERATIONS=1000 \
scripts/run_100k_sharded_experiment.sh 300000 42 ""
```

运行参数：

```text
sample_size = 300000
primary_category = none
max_candidate_per_document = 25
lexical_max_candidate_pairs = 1500000
shard_count = 4
bootstrap_iterations = 1000
```

核心产物规模：

| artifact | records |
|---|---:|
| normalized_documents | 300000 |
| semantic_views | 300000 |
| candidate_pairs | 2982331 |
| pair_relations | 2982331 |
| duplicate_groups | 299979 |
| canonical_documents | 299979 |
| topic_graph | 235849 |
| clusters | 2753 |
| cluster_membership | 299979 |
| rankings | 299979 |
| recommendations | 50 |

关系类型分布：

| relation_type | count |
|---|---:|
| unrelated | 2754904 |
| same_topic_non_duplicate | 225512 |
| suspected_duplicate | 1894 |
| exact_duplicate | 21 |

去重与聚类摘要：

```text
positive_relation_count = 21
merged_group_count = 21
duplicate_group_count = 299979
cluster_count = 2753
max_cluster_size = 91445
mean_cluster_size = 108.9644024700327
ranking_count = 299979
recommendation_count = 50
```

Baseline 与消融摘要：

| system / variant | precision | recall | f1 | false_merge_rate |
|---|---:|---:|---:|---:|
| bm25_lexical_threshold | 0.074830 | 0.985075 | 0.139094 | 0.003618 |
| dense_cosine_threshold | 0.026889 | 0.313433 | 0.049528 | 0.003370 |
| title_author_year_rule | 1.000000 | 0.671642 | 0.803571 | 0.000000 |
| dense_threshold_dedup | 1.000000 | 0.268657 | 0.423529 | 0.000000 |
| rsl_sieve_conservative | 1.000000 | 0.313433 | 0.477273 | 0.000000 |
| rsl_sieve_review_inclusive | 1.000000 | 0.880597 | 0.936508 | 0.000000 |
| ours_no_relation_separation | 0.026889 | 0.313433 | 0.049528 | 0.003370 |
| ours_no_tlnd | 0.000270 | 0.910448 | 0.000541 | 1.000000 |

Bootstrap 95% 置信区间：

| system | precision_mean | recall_mean | f1_mean | f1_95%_ci | false_merge_rate_mean |
|---|---:|---:|---:|---|---:|
| bm25_lexical_threshold | 0.075568 | 0.984975 | 0.140240 | [0.111728, 0.171314] | 0.003612 |
| dense_cosine_threshold | 0.027113 | 0.316551 | 0.049890 | [0.030075, 0.071862] | 0.003375 |
| title_author_year_rule | 1.000000 | 0.671979 | 0.802182 | [0.701680, 0.880600] | 0.000000 |
| dense_threshold_dedup | 1.000000 | 0.265861 | 0.417026 | [0.270729, 0.547241] | 0.000000 |
| rsl_sieve_conservative | 1.000000 | 0.312565 | 0.473208 | [0.333333, 0.601947] | 0.000000 |
| rsl_sieve_review_inclusive | 1.000000 | 0.879063 | 0.935124 | [0.885468, 0.976387] | 0.000000 |

配置：

```text
weak_label_count = 225577
positive_label_count = 67
negative_label_count = 225510
bootstrap_iterations = 1000
confidence_level = 0.95
seed = 42
output = outputs/large_300k_random/reports/bootstrap_confidence.csv
paper_table = outputs/paper_artifacts_large_300k_random/tables/bootstrap_confidence.csv
```

Candidate cap 分析：

| cap | retained_pair_ratio | exact_retained | suspected_retained | TLND_retained |
|---:|---:|---:|---:|---:|
| 1 | 0.095790 | 21 / 21 | 1653 / 1894 | 33412 / 225512 |
| 3 | 0.270178 | 21 / 21 | 1840 / 1894 | 84577 / 225512 |
| 5 | 0.421549 | 21 / 21 | 1874 / 1894 | 122968 / 225512 |
| 10 | 0.708233 | 21 / 21 | 1891 / 1894 | 184353 / 225512 |
| 25 | 1.000000 | 21 / 21 | 1894 / 1894 | 225512 / 225512 |
| 50 | 1.000000 | 21 / 21 | 1894 / 1894 | 225512 / 225512 |
| 100 | 1.000000 | 21 / 21 | 1894 / 1894 | 225512 / 225512 |

错误分析与人工标注样本：

```text
output_dir = outputs/large_300k_random/reports/error_analysis
error_cases.jsonl = 332
manual_annotation_sample.jsonl = 100
paper_table = outputs/paper_artifacts_large_300k_random/tables/error_analysis_summary.csv
```

错误分析摘要：

| system | TP | FP | TN | FN | precision | recall | f1 | false_merge_rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bm25_lexical_threshold | 66 | 816 | 224694 | 1 | 0.074830 | 0.985075 | 0.139094 | 0.003618 |
| dense_cosine_threshold | 21 | 760 | 224750 | 46 | 0.026889 | 0.313433 | 0.049528 | 0.003370 |
| title_author_year_rule | 45 | 0 | 225510 | 22 | 1.000000 | 0.671642 | 0.803571 | 0.000000 |
| dense_threshold_dedup | 18 | 0 | 225510 | 49 | 1.000000 | 0.268657 | 0.423529 | 0.000000 |
| rsl_sieve_conservative | 21 | 0 | 225510 | 46 | 1.000000 | 0.313433 | 0.477273 | 0.000000 |
| rsl_sieve_review_inclusive | 59 | 0 | 225510 | 8 | 1.000000 | 0.880597 | 0.936508 | 0.000000 |

人工标注评分摘要：

| sample_count | labeled_count | unlabeled_count | suggested_agreement_rate | suggested_label_f1 |
|---:|---:|---:|---:|---:|
| 100 | 0 | 100 | 0.000000 | 0.000000 |

论文产物：

```text
outputs/paper_artifacts_large_300k_random/tables/run_summary.csv
outputs/paper_artifacts_large_300k_random/tables/baseline_comparison.csv
outputs/paper_artifacts_large_300k_random/tables/ablation_summary.csv
outputs/paper_artifacts_large_300k_random/tables/bootstrap_confidence.csv
outputs/paper_artifacts_large_300k_random/tables/error_analysis_summary.csv
outputs/paper_artifacts_large_300k_random/tables/manual_annotation_summary.csv
outputs/paper_artifacts_large_300k_random/tables/recommendation_summary.csv
outputs/paper_artifacts_large_300k_random/tables/figure_index.csv
outputs/paper_artifacts_large_300k_random/figures/baseline_f1.png
outputs/paper_artifacts_large_300k_random/figures/cluster_size_distribution.png
outputs/paper_artifacts_large_300k_random/figures/relation_type_distribution.png
```

工程修复：

```text
1. cluster_documents 不再对每篇文档重复扫描 topic_edges，300k 聚类续跑从卡住降到约 21 秒。
2. bootstrap 从逐条重采样改为基于混淆矩阵计数的 multinomial 重采样，300k 1000 次 bootstrap 约 76 秒完成。
3. run_100k_sharded_experiment.sh 补充 score-manual-annotations 步骤，确保 artifact 导出 manual_annotation_summary.csv。
```

运行日志摘要：

```text
首段运行到聚类阶段后终止: elapsed = 59:51.08, max_rss = 19678136 KB
修复聚类后续跑到 bootstrap 阶段后终止: elapsed = 22:16.32, max_rss = 15954556 KB
修复 bootstrap 后最终增量段完成: elapsed = 5:19.28, max_rss = 18444200 KB, exit_status = 0
```

验证：

```text
本地全量 pytest: 47 passed
远程全量 pytest: 47 passed
```
