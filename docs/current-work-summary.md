# 当前工作核心与产出总结

## 问题拆解

2026-06-16 最新重构结论：当前课题应从 `IAD-Risk Transformer` 主方法叙事，重构为 **Risk-Calibrated Scientific Entity Matching under Agenda-Level Confounders**。

新的问题定义不是“提出一个新 Transformer 架构”，而是：

```text
在同议题非同文干扰下，系统如何在显式 false-merge 风险预算内最大化 safe_merge 覆盖率，并把高风险样本交给 reject 或 manual_review。
```

`IAD-Risk` 保留为 `agenda-aware conflict/risk module`；旧的 frozen SciNCL encoder + 多头风险头结果只能作为阶段性风险模块证据，不能写成 SOTA、强模型全面优势或 Q2/B ready。

## 2026-06-17 最新审稿状态

本轮目标是先消除不依赖外部密钥的审稿阻塞，再把剩余问题收敛到可明确请求的远程输入。

已完成证据：

```text
provenance-blind SciNCL IAD-Risk Transformer open_v2：
  execution_mode = actual_model
  device = cuda:0
  test f1 = 0.979592
  test false_merge_rate = 0.000982

SPECTER2 IAD-Risk Transformer open_v2：
  execution_mode = actual_model
  device = cuda
  test f1 = 0.979592
  test false_merge_rate = 0.000982

SPECTER2 adapter cosine open_v2：
  execution_mode = actual_model
  pair_count = 10,415
  missing_pair_count = 0
  已生成 metric summary 与 bootstrap

Ditto-style EM source-heldout：
  checkpoint 已从远程回传到 outputs/models/ditto_style_em_source_heldout/
  model.safetensors 约 499MB
  checkpoint、training summary、scores、metric summary 与 bootstrap 均通过输出验收
```

已修复工程问题：

```text
build-iad-paper-report 不再因缺失可选 GPT summary / bootstrap 中断重建；缺失项记录 warning 并继续由 preflight / remote validation 门禁追踪。
experiment_queue 中含 | 的 thresholds 参数已加 shell 引号，避免机制敏感性重建命令被管道符截断。
iad_source_heldout_coverage_audit 新增 train/test label_source 不相交检查；单来源 OpenAlex 或 topic split 不能被误报为 source-heldout。
iad_bench_source_acquisition_audit 新增 COCI 有效 DOI-to-DOI 边数量检查；空 CSV 或无效格式不能被误报为 ready_to_convert。
```

最新门禁状态：

```text
iad_model_feature_guard：
  audit_count = 4
  defensible_count = 4
  missing_model_count = 0
  violation_count = 0
  overall_feature_guard_status = defensible

remote_output_validation：
  total_output_count = 171
  valid_output_count = 161
  missing_output_count = 10

remote_result_acceptance：
  accepted_task_count = 38
  blocked_task_count = 6
  accepted_gate_count = 5
  blocked_gate_count = 2

remote_execution_blueprint：
  root_task_count = 2
  root_task_blocked_count = 2
  missing_output_count = 4

advanced_model_evidence：
  evidence_count = 22
  ready_actual_model_count = 19
  missing_required_count = 2

q2b_completion_audit：
  criterion_count = 12
  ready_count = 4
  blocked_count = 8
  q2_b_goal_ready = false

q2b_external_blocker_audit：
  blocker_count = 6
  external_secret_count = 1
  advanced_missing_count = 2
  missing_output_count = 10
  highest_priority_blocker = external_secret:OPENAI_API_KEY

iad_bench_source_acquisition_audit：
  overall_acquisition_status = ready
  missing_raw_file_count = 0
  invalid_raw_file_count = 0
  coci_T10009.csv valid DOI-to-DOI citation edges = 13,252

iad_source_heldout_coverage_audit_coci_source_patch：
  relation_count = 3
  ready_relation_count = 3
  blocked_relation_count = 0
  source_heldout_full_iad_data_ready = true

iad_risk_split_evaluation_audit_coci_source_patch_source_heldout：
  overall_split_evaluation_status = source_heldout_full_iad_limited_ready
  limited_source_heldout_count = 1
  test agenda_non_identity_f1 = 0.948917
  test same_work_f1 = 0.086066
  test false_merge_rate = 0.000154
```

剩余根阻塞：

```text
run_llm_pair_judge_api_model_open_v2：
  blocked_missing_secret = OPENAI_API_KEY

run_gpt_pair_judge_open_v3_scholarly_balanced_gold_source_heldout：
  blocked_missing_secret = OPENAI_API_KEY

primary_remote_readiness：
  readiness_status = blocked_missing_primary_secret
  primary_track = open_v3_scholarly_balanced_gold_source_heldout

remote_result_acceptance / model_superiority / innovation_depth：
  GPT/LLM judge 输出、强模型矩阵、主轨道优势和创新深度仍未闭环
  COCI source-heldout 只能作为 silver hard-negative limited evidence，不能替代人工 gold 或 SOTA 结论

remote_secret_preflight：
  remote_workspace = present
  OPENAI_API_KEY = missing
  default_shell_conda = missing
```

当前可写结论：

```text
provenance-blind 特征泄漏门禁已通过；
SPECTER2 encoder 稳定性和 Ditto-style EM actual_model 证据已补齐；
OpenAlex+COCI 已补齐 agenda_non_identity 的第二公开来源 silver 覆盖，并形成 limited source-heldout 评估证据；
强模型矩阵仍缺 GPT/LLM judge，source-heldout same_work 轻量模型表现较弱，不允许写成 SOTA、主方法整体优越或已达到二区/B 类投稿标准。
```

新增 P0 工程产物：

```text
src/iad_sieve/evaluation/risk_calibrated_protocol.py
tests/test_risk_calibrated_protocol.py
docs/risk-calibrated-topic-restructure.md
```

新增主评价入口：

```bash
python -m iad_sieve.cli run-risk-calibrated-protocol --help
```

该协议将主指标从 `best F1` 改为：

```text
Recall @ FPR <= α
Coverage @ FDR <= β
safe-merge precision / recall
review rate
hard-negative false merge rate
```

新增 P1 hard-negative stress set 入口：

```bash
python -m iad_sieve.cli build-hard-negative-stress-set --help
```

已基于 `outputs/iad_bench_open_v3_multitopic_silver_patch/scored_relations.jsonl` 生成：

```text
outputs/hard_negative_stress_open_v3_multitopic_silver_patch/
stress_pair_count = 6,820
high_confidence_non_identity_count = 6,802
version_risk_ambiguous_count = 18
weak_pseudo_negative_count = 0
```

该集合排除了普通 unrelated gold negative，只保留 agenda-level non-identity silver / version-risk 样本；仍然是 pseudo-gold stress test，不等同人工 gold。

新增 hard-negative stress cluster contamination 审计入口：

```bash
python -m iad_sieve.cli build-stress-cluster-contamination-audit --help
```

已生成当前 stress cluster 审计：

```text
outputs/stress_cluster_contamination_iad_risk_open_v3_multitopic_silver_patch/
outputs/stress_cluster_contamination_iad_risk_identifier_veto_open_v3_multitopic_silver_patch/
outputs/stress_cluster_contamination_iad_sieve_duplicate_score_open_v3_multitopic_silver_patch/
```

balanced source-heldout historical 核心结果：

```text
IAD-Risk lightweight：evaluated_stress_pair_count = 6,802，cluster_contamination_rate = 0.006747，over_merge_pair_count = 18，largest_contaminated_cluster_size = 3
IAD-Risk + identifier_conflict veto：evaluated_stress_pair_count = 6,802，vetoed_merge_count = 17，cluster_contamination_rate = 0.0，over_merge_pair_count = 0，largest_contaminated_cluster_size = 0
IAD-Sieve duplicate_score >= 0.92：evaluated_stress_pair_count = 6,802，cluster_contamination_rate = 0.0，over_merge_pair_count = 0，largest_contaminated_cluster_size = 0
```

审稿结论：hard-negative stress cluster 审计已经补齐。原始 lightweight IAD-Risk 暴露 18 个 pseudo-gold stress over-merge pair；加入 `identifier_conflict` veto 后，17 条直接自动合并被转入 manual_review/veto，cluster_contamination_rate 降为 0。该结果支持“显式冲突 veto 是必要安全机制”，但不能写成模型本体 hard-negative stress 泛化已通过。

`identifier_conflict` veto 已纳入正式 selective decision protocol：

```text
outputs/stress_risk_protocol_input_iad_risk_open_v3_multitopic_silver_patch/
outputs/risk_protocol_stress_iad_risk_raw_open_v3_multitopic_silver_patch/
outputs/risk_protocol_stress_iad_risk_identifier_veto_open_v3_multitopic_silver_patch/
```

formal stress protocol 结果：

```text
raw stress protocol：pair_count = 6,802，safe_merge_count = 17，hard_negative_false_merge_count = 17，hard_negative_false_merge_rate = 0.002499，merge_contamination_fdr = 1.0
identifier_conflict veto protocol：pair_count = 6,802，safe_merge_count = 0，vetoed_merge_count = 17，hard_negative_false_merge_count = 0，hard_negative_false_merge_rate = 0.0，review_rate = 0.005293
```

说明：该 protocol 输入只有 hard-negative stress pairs，没有 same_work 正例，因此 `selected_row_count = 0` 是预期结果；它用于验证 veto 风险闸门，不用于选择主 operating point。

已补齐 SciNCL / RoBERTa actual-model stress 对照：

```text
outputs/strong_baseline_stress_open_v3_multitopic_silver_patch/
outputs/stress_cluster_contamination_scincl_bestf1_open_v3_multitopic_silver_patch/
outputs/stress_cluster_contamination_roberta_bestf1_open_v3_multitopic_silver_patch/
outputs/risk_protocol_stress_scincl_bestf1_open_v3_multitopic_silver_patch/
outputs/risk_protocol_stress_roberta_bestf1_open_v3_multitopic_silver_patch/
```

强 baseline stress 结果：

```text
SciNCL actual_model malteos/scincl，threshold = 0.90：safe_merge_count = 2,668，hard_negative_false_merge_rate = 0.392238，cluster_contamination_rate = 0.304791，over_merge_pair_count = 3,960，largest_contaminated_cluster_size = 64
RoBERTa MRPC actual_model textattack/roberta-base-MRPC，threshold = 0.50：safe_merge_count = 38，hard_negative_false_merge_rate = 0.005587，cluster_contamination_rate = 0.011187，over_merge_pair_count = 46，largest_contaminated_cluster_size = 5
```

审稿结论：该对照补上了 hard-negative stress 的两个实际强 baseline。SciNCL 证明单空间科学语义相似在 agenda-level hard negative 上存在严重传递误合并；RoBERTa 风险较低但仍有非零 false merge。IAD-Risk + `identifier_conflict` veto 的 stress 归零只能写成显式风险闸门有效，不能写成模型本体已完成 hard-negative 泛化；SPECTER2、DeBERTa、Ditto-style EM 和 LLM judge 的同口径 stress 对照仍需继续闭环。

新增 P1 constrained-risk baseline 审计入口：

```bash
python -m iad_sieve.cli build-model-superiority-audit --help
```

已生成当前 source-heldout 风险预算比较：

```text
outputs/risk_protocol_iad_risk_open_v3_balanced_gold_source_heldout/
outputs/risk_protocol_scincl_open_v3_balanced_gold_source_heldout/
outputs/risk_protocol_roberta_open_v3_balanced_gold_source_heldout/
outputs/model_superiority_constrained_risk_open_v3_source_heldout/
```

balanced source-heldout historical 核心结果：

```text
IAD-Risk risk module：selected_row_count = 3
selected operating point：FPR <= 0.03, FDR <= 0.10, safe_merge_recall = 0.246484, safe_merge_coverage = 0.136936
SciNCL baseline：selected_row_count = 0
RoBERTa pair historical baseline：selected_row_count = 0
model_superiority_audit constrained_risk_advantage_count = 2
model_superiority_audit overall_superiority_status = limited
```

open_v3 scholarly source-heldout 当前主轨道 constrained-risk 结果：

```text
IAD-Risk Transformer actual_model：selected_row_count = 9，max_selected_safe_merge_recall = 0.983696
IAD-Risk Transformer SPECTER2 actual_model：selected_row_count = 9，max_selected_safe_merge_recall = 0.983696
SciNCL actual_model：selected_row_count = 0
RoBERTa MRPC actual_model：selected_row_count = 9，max_selected_safe_merge_recall = 0.711957
DeBERTa NLI cross-encoder actual_model：selected_row_count = 0，protocol_status = blocked_no_feasible_threshold
SPECTER2 adapter cosine actual_model：selected_row_count = 0，protocol_status = blocked_no_feasible_threshold
Ditto-style EM actual_model：same_work_f1 = 0.986523，false_merge_rate = 0.021739
model_superiority_open_v3_scholarly_source_heldout blocked_missing_comparison_count = 1
model_superiority_open_v3_scholarly_source_heldout overall_superiority_status = blocked
```

新增 P2 cluster-level contamination 审计：

```text
src/iad_sieve/evaluation/clustering_evaluator.py
tests/test_cluster_contamination.py
outputs/cluster_contamination_iad_risk_selected_open_v3_balanced_gold_source_heldout_test/evaluation_summary.md
outputs/cluster_contamination_scincl_bestf1_open_v3_balanced_gold_source_heldout_test/evaluation_summary.md
outputs/cluster_contamination_roberta_bestf1_open_v3_balanced_gold_source_heldout_test/evaluation_summary.md
outputs/cluster_bootstrap_open_v3_balanced_gold_source_heldout/iad_risk_selected_cluster_bootstrap.csv
outputs/cluster_bootstrap_open_v3_balanced_gold_source_heldout/scincl_bestf1_cluster_bootstrap.csv
outputs/cluster_bootstrap_open_v3_balanced_gold_source_heldout/roberta_bestf1_cluster_bootstrap.csv
```

当前 source-heldout test cluster 对照结果：

```text
IAD risk-selected：cluster_contamination_rate = 0.011958，over_merge_pair_count = 37，largest_contaminated_cluster_size = 4，pairwise_clustering_f1 = 0.386984
SciNCL best-F1 threshold 0.90：cluster_contamination_rate = 0.094168，over_merge_pair_count = 570，largest_contaminated_cluster_size = 125，pairwise_clustering_f1 = 0.692308
RoBERTa best-F1 threshold 0.50：cluster_contamination_rate = 0.069926，over_merge_pair_count = 659，largest_contaminated_cluster_size = 262，pairwise_clustering_f1 = 0.645096
```

300 次 pair bootstrap、95% CI：

```text
IAD risk-selected：cluster_contamination_rate point = 0.011958，mean = 0.010472，CI = [0.007814, 0.012860]；pairwise_clustering_f1 point = 0.386984，CI = [0.366882, 0.411009]
SciNCL best-F1 threshold 0.90：cluster_contamination_rate point = 0.094168，mean = 0.107316，CI = [0.096376, 0.117412]；pairwise_clustering_f1 point = 0.692308，CI = [0.694738, 0.723662]
RoBERTa best-F1 threshold 0.50：cluster_contamination_rate point = 0.069926，mean = 0.086604，CI = [0.077011, 0.094528]；pairwise_clustering_f1 point = 0.645096，CI = [0.641031, 0.670696]
```

解释：该结果支持“风险预算下 IAD operating point 可显著降低 cluster-level over-merge 污染”，且 contamination bootstrap CI 与两个 best-F1 baseline 不重叠；但 IAD 的 pairwise recall / F1 和 B3 F1 低于两个 best-F1 baseline，因此不能写成整体聚类优越或跨来源泛化。

以下内容保留为历史阶段总结；其中涉及 IAD-Risk 主方法、Transformer 架构贡献、Q2/B readiness 或模型优势的表述，以 `docs/risk-calibrated-topic-restructure.md` 和当前 claim gate 为准。

当前课题从 IAD-Sieve 规则型误合并抑制系统，进一步升级为 IAD-Risk：身份-议题解耦的误合并风险学习方法。

升级原因是：仅用规则评分、阈值门控和 cannot-link 合并，难以支撑二区或 B 类期刊对强 baseline、模型深度和创新性的要求。

## 关键结论

## 2026-06-16 优化进展与审稿结论

本轮优化不是简单调参，而是修复了 source-heldout 训练链路的一个关键问题：

```text
旧 source-heldout 训练集缺少 agenda_non_identity 正例，
导致 IAD-Risk Transformer 只能以 identity_only 模式预测，
无法真正学习“同议题但非同一文献”的风险阻断。
```

已完成的工程改造：

- `train-iad-risk-transformer-model` 支持多个 `--documents` 输入，允许同时读取 gold 文档与 OpenAlex 文档；
- 新增 `--extra-train-relations`，额外 gold/silver 关系只参与训练，不进入 source-heldout gold 测试输出；
- IAD-Risk Transformer 训练函数支持 eval relations 与 extra train relations 分离，避免把额外训练样本混入评估集；
- 修复 `model_superiority_audit` 汇总逻辑，全部强基线比较失败时不再误报 `supported_limited`。

本轮新增主实验结果：

```text
system：iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout_extra_train_calibrated_fmr10
encoder：malteos/scincl
train_pair_count：26,768
test_pair_count：2,702
prediction_mode：full_iad_risk
full_risk_trained：true
test precision：0.836601
test recall：0.473723
test F1：0.604915
test false_merge_rate：0.092524
bootstrap F1 mean：0.604824
bootstrap F1 95% CI：0.579993 - 0.629519
bootstrap false_merge_rate mean：0.092561
bootstrap false_merge_rate 95% CI：0.077800 - 0.108619
```

与旧 source-heldout IAD-Risk Transformer 相比：

```text
旧模型：identity_only，test F1 = 0.370283，recall = 0.232420，false_merge_rate = 0.022946
新模型：full_iad_risk，test F1 = 0.604915，recall = 0.473723，false_merge_rate = 0.092524
```

解释：

```text
新模型显著提高了召回和总体 F1，并真正训练了 agenda_non_identity head；
但为了提升召回，false_merge_rate 从 0.022946 上升到 0.092524；
这仍低于强基线的误合并率，但 same_work F1 / source-heldout 主判定仍未超过强基线。
```

当前强基线比较结论：

```text
vs RoBERTa source-heldout：same_work_f1_delta = -0.276210，false_merge_rate_reduction = 0.332346，status = not_supported
vs SciNCL source-heldout：same_work_f1_delta = -0.327452，false_merge_rate_reduction = 0.262028，status = not_supported
constrained-risk vs RoBERTa：baseline 已运行 risk_calibrated_protocol，但 selected_row_count = 0；IAD-Risk selected safe_merge_recall = 0.246484
constrained-risk vs SciNCL：baseline 已运行 risk_calibrated_protocol，但 selected_row_count = 0；IAD-Risk selected safe_merge_recall = 0.246484
model_superiority_audit overall_superiority_status：limited
```

审稿结论：

```text
本轮优化证明“额外 gold/silver 训练 + 风险校准”是有效方向；
但当前结果不能支撑“常规 F1 优于强模型”“SOTA”“达到二区/B类投稿要求”；
可以写成风险预算 operating-point 可行性优势和误合并风险降低方向的阶段性证据，不能写成完整模型优势结论。
```

当前 Q2/B 门控状态：

```text
q2b_acceptance_ready：false
blocked_gate_count：8 / 9
claim_gate_status：blocked
primary_track_superiority_evaluator：blocked_missing_primary_metrics
q2_b_innovation_claim_allowed：false
no_annotation_stage_allowed：true
q2_b_ready_under_no_annotation_strategy：false
```

下一步优先级：

```text
1. 不再继续只做阈值搜索，应升级模型结构，例如 cross-encoder reranker、contrastive hard-negative training 或 multi-task loss；
2. 补齐 GPT/LLM judge、provenance-blind 和旧远程验收链刷新；
3. 构建真正的 hard-negative test set，当前 balanced gold source-heldout 中 hard_negative_pair_count 为 0；
4. 若暂不做人工标注，只能作为 no-annotation 阶段继续推进，不能把它包装成最终 gold 结论。
```

当前主线：

```text
IAD-Risk：论文主方法
IAD-Sieve：工程 pipeline 和 rule-only baseline
IAD-Bench：gold / proxy / silver / human_audit 分层数据契约
```

核心问题：

```text
同议题论文在语义空间接近，但不是同一篇文献，不能被误合并。
```

## 当前核心思想

IAD-Risk 将文献 pair 分为：

```text
same_work：同一篇 scholarly work
same_agenda：同一研究议题
agenda_non_identity：同议题但非同一文献
unrelated：无明显身份或议题关系
```

模型目标：

```text
identity_space 学 same_work
agenda_space 学 same_agenda
agenda_non_identity 作为 hard negative
false_merge_risk 控制合并风险
```

## 已有工程基础

已完成并可复用：

- 文献预处理、候选生成、关系评分、去重合并、主题图、聚类、排序和推荐；
- DeepMatcher gold label 适配；
- SciRepEval / SciDocs same_agenda proxy 适配；
- OpenAlex / OpenCitations agenda_non_identity weak label 适配；
- 阈值校准；
- 轻量关系分类器；
- 外部 baseline 分数评估接口；
- representation baseline 分数生成器和执行模式记录；
- IAD-Bench 构造器、split 输出、label provenance summary 和 dataset card；
- lightweight IAD-Risk 双空间风险模型；
- IAD 专用消融；
- 论文 RQ 汇总；
- 审稿风险矩阵；
- 最终课题包导出；
- 人工标注要求文档。
- 安全论文草稿骨架。

## 新增设计产出

- `docs/superpowers/specs/2026-06-12-iad-risk-redesign.md`：IAD-Risk 正式重构设计；
- `docs/superpowers/plans/2026-06-12-iad-risk-p0-redesign.md`：P0 实施计划；
- `docs/iad-bench-contract.md`：IAD-Bench 数据契约；
- `docs/annotation-requirements.md`：后续人工 gold audit 标注规范。
- `src/iad_sieve/evaluation/iad_bench_builder.py`：IAD-Bench 数据契约构建器。
- `src/iad_sieve/evaluation/strong_baseline_runner.py`：表示模型 baseline 分数生成器。
- `src/iad_sieve/evaluation/iad_risk_model.py`：IAD-Risk 双空间风险模型。
- `src/iad_sieve/evaluation/bootstrap_confidence.py`：IAD 专用分层 bootstrap 置信区间评估。
- `src/iad_sieve/evaluation/openalex_api_ingestion.py`：OpenAlex Works API 公开数据采集器。
- `src/iad_sieve/evaluation/iad_bench_provenance_balance_plan.py`：来源捷径缓解与 relation 级公开数据补齐计划。

## IAD-Bench-Open-v1 公开压力测试

已完成不依赖人工标注的公开 hard-negative 压力测试集：

```text
source：OpenAlex Works API
filter：primary_topic.id:T10009,publication_year:2024,type:article
works：1,000
effective_documents：963
agenda_non_identity_pairs：10,000
label_strength：silver
human_audit_pair_count：0
```

该数据集证明公开数据扩展链路可复现，并能用于同议题误合并压力测试；但它没有 same_work 正例，不能单独支撑完整模型训练或身份判定性能结论。

## IAD-Bench-Open-v2 当前主实验数据包

已完成公开 same_work gold 与公开 hard negative 的合并数据包：

```text
same_work gold：py_entitymatching DBLP-ACM
hard negative：OpenAlex Works API same primary topic + shared references + different work id
documents：1,737
pairs：10,415
gold pairs：415
same_work positive：231
gold unrelated negative：184
silver agenda_non_identity hard negative：10,000
human_audit_pair_count：0
```

当前 lightweight IAD-Risk 在 v2 上已经可训练：

```text
trained：true
trained_head_count：2
required_head_count：2
same_work_f1：0.970213
agenda_non_identity_f1：0.99975
same_agenda_f1：0.0
```

解释：

```text
same_work 与 agenda_non_identity 是 required heads；
same_agenda 是 auxiliary head，v2 缺少平衡 same_agenda proxy 标签，因此不能把该 head 写成正式议题学习结论；
v2 可作为当前公开可复现实验主线，但不能替代后续 human audit。
```

## IAD-Bench-Open-v3 重构目标

已新增 Open-v3 设计与实施计划：

```text
docs/superpowers/specs/2026-06-13-iad-risk-open-v3-redesign.md
docs/superpowers/plans/2026-06-13-iad-risk-open-v3-implementation.md
```

Open-v3 暂不依赖新增人工标注，人工 gold 保留为后续增强。当前差距审计结果：

```text
document_scale：1,737 / 20,000，blocked
gold_pair_scale：415 / 2,000，blocked
silver_pair_scale：10,000 / 50,000，blocked
silver_topic_diversity：1 / 30，blocked
split_and_provenance：defensible
human_audit_position：deferred_enhancement
overall_open_v3_status：blocked
```

Open-v3 source plan 已生成下一轮公开数据任务：

```text
plan_count：5
needs_public_data_count：2
already_seen_topic_count：1
waiting_source_inputs_count：1
deferred_enhancement_count：1
公开 gold 缺口：1,585 pair
OpenAlex silver 缺口：40,000 pair
OpenAlex topic 缺口：29
```

## IAD-Bench-Open-v3 当前公开 gold 进展

已在不增加人工标注的条件下接入 DeepMatcher / py_entitymatching 公开 gold 来源：

```text
full open_v3：
documents：17,489
pairs：40,582
gold_pair_count：40,582
same_work_pair_count：6,745
unrelated_pair_count：33,837
label_source_count：3

balanced gold：
documents：13,404
pairs：13,396
same_work_pair_count：6,698
unrelated_pair_count：6,698
label_source_count：3
source_bias_max_eval_accuracy：0.5
overall_source_bias_status：defensible
overall_provenance_balance_status：defensible
overall_stratification_status：defensible

scholarly-only balanced gold：
documents：10,797
pairs：11,062
same_work_pair_count：5,531
unrelated_pair_count：5,531
label_source_count：2
include_label_sources：deepmatcher_dblp_scholar, deepmatcher_py_entitymatching_dblp_acm
source_bias_max_eval_accuracy：0.5
overall_source_bias_status：defensible
overall_provenance_balance_status：high_risk
```

解释：

```text
full open_v3 用于报告公开 gold 全量规模；
scholarly-only balanced gold 用于科研文献 same_work / unrelated 领域主评估；
balanced gold 用于来源捷径防御和跨域鲁棒性补充，不能混写成纯科研文献 gold；
balanced gold 不包含 agenda_non_identity，不能替代 OpenAlex hard-negative 风险控制实验。
```

Open-v3 split readiness 已审计泛化验证条件：

```text
dimension_count：4
balanced_gold_blocked_count：1
balanced_gold_defensible_count：3
overall_split_readiness：blocked
random_split_coverage：defensible
pair_leakage_guard：defensible
source_held_out_readiness：defensible
topic_held_out_readiness：blocked
```

Open-v3 held-out split plan 已生成多来源 source-held-out 复核与未来 topic-held-out 泛化实验计划：

```text
plan_count：4
ready_count：1
blocked_count：1
conditional_count：0
defensible_count：2
assignment_count：13,396
overall_heldout_split_status：blocked
source_held_out_split：ready，heldout_relation_count = 2，heldout_relation_source_count = 4，heldout_source_count = 2
heldout_source_diversity：defensible，min_unique_heldout_source_count = 2
balanced_gold_topic_held_out_split：blocked，topic_count = 0 / 3
pair_leakage_guard：defensible，leaked_pair_count = 0
```

审稿含义：

```text
当前阶段可以支撑公开 gold 身份判定、balanced evaluation 和多来源 source-held-out 复核；
不能把 balanced gold 写成完整 IAD hard-negative 数据集；
balanced gold 本身不能声称已有跨 topic 泛化结果；
不能声称已经满足二区 / B 类投稿完成度；
下一轮必须补齐强模型结果、provenance-blind 重训和跨 topic OpenAlex hard negative。
```

scholarly-only source-held-out 已派生为远程强模型输入：

```text
assignment_count：11,062
train_pair_count：10,694
test_pair_count：368
same_work：limited_source_heldout_coverage
unrelated：limited_source_heldout_coverage
agenda_non_identity：blocked_missing_relation
source_heldout_full_iad_data_ready：false
```

审稿含义：

```text
该轨道能回答领域内 same_work / unrelated 来源泛化问题；
不能回答完整 IAD hard-negative source-held-out 问题；
provenance_balance high_risk 说明 DBLP-Scholar 占比过高，需与原 balanced gold 和 OpenAlex multi-topic silver 分层报告。
```

Open-v3 multi-topic silver patch 已补齐第一轮跨 topic hard-negative 证据：

```text
OpenAlex works：3,000
document_count：2,103
agenda_non_identity_pair_count：6,820
topic_count：344
top_silver_topic_ratio：0.043988
combined_documents：19,592
combined_pairs：47,402
gold_pair_count：40,582
silver_pair_count：6,820
```

对应审计边界：

```text
silver_topic_concentration：defensible
silver_topic_diversity：defensible
topic_held_out_split：ready
heldout_topic_count：69
topic_held_out_assignment_count：6,820
source_held_out_split：blocked
overall_source_bias_status：high_risk
source_bias_max_eval_accuracy：0.859614
overall_provenance_balance_status：blocked
```

topic-heldout lightweight IAD-Risk 只作为 hard-negative 风险控制证据：

```text
test_eval_pair_count：5,580
agenda_non_identity_f1：0.929355
false_merge_rate：0.004677
same_work_f1：0.337756
```

解释：

```text
multi-topic patch 已缓解 single-topic concentration；
topic-held-out 可执行，但仍是 OpenAlex silver；
source-held-out hard negative、强模型、provenance-blind 重训和远程验收未完成前，不能写成 Q2/B 完成证据。
```

已完成的 v2 输出目录：

```text
outputs/deepmatcher_public_dblp_acm/
outputs/iad_bench_open_v2/
outputs/iad_risk_open_v2/
outputs/iad_risk_transformer_open_v2/
outputs/iad_ablation_open_v2/
outputs/iad_bootstrap_open_v2/
outputs/strong_baseline_open_v2/
outputs/baseline_error_analysis_open_v2/
outputs/single_space_union_open_v2/
```

待远程生成并回传的关键目录：

```text
outputs/iad_risk_transformer_scincl_provenance_blind_open_v2/
outputs/iad_risk_transformer_specter2_open_v2/
```

当前 v2 强 baseline 对比：

```text
SciNCL actual_model：
  same_work_f1 = 0.054393
  hard_negative_false_merge_rate_mean = 0.790663

DistilBERT MRPC actual_model：
  same_work_f1 = 0.359270
  hard_negative_false_merge_rate_mean = 0.061683

RoBERTa MRPC actual_model：
  same_work_f1 = 0.824691
  hard_negative_false_merge_rate_mean = 0.000103

IAD-Risk lightweight：
  same_work_f1 = 0.970213
  hard_negative_false_merge_rate_mean = 0.000203

IAD-Risk Transformer actual_model：
  encoder = malteos/scincl
  train_pair_count = 8,332
  test same_work_f1 = 0.979592
  test agenda_non_identity_f1 = 0.997030
  test false_merge_rate = 0.000982
  hard_negative_false_merge_rate_mean = 0.0

SPECTER2 adapter：
  backend = specter2-adapter
  base_encoder = allenai/specter2_base
  adapter_model = allenai/specter2
  status = 本地代码与测试已补齐，远程 actual_model 实验待连接恢复后执行
```

审稿解释：

```text
SciNCL 证明单空间科学语义相似会严重误合并 hard negative；
RoBERTa 已经是强 pair-classifier 对照，IAD-Risk 需要继续证明风险分解、弱监督扩展、可解释错误控制和跨数据源泛化，而不是只强调单一指标领先。
```

## 当前保留的输出目录

本地 `outputs/` 当前只保留论文证据链和最终交付相关目录：

- `outputs/deepmatcher_fixture/`
- `outputs/scirepeval_fixture/`
- `outputs/openalex_fixture/`
- `outputs/openalex_api_ingestion_fixture/`
- `outputs/openalex_api_ingestion_v1/`
- `outputs/openalex_api_fixture/`
- `outputs/openalex_api_v1/`
- `outputs/deepmatcher_public_dblp_acm/`
- `outputs/external_baseline_fixture/`
- `outputs/iad_classifier_fixture/`
- `outputs/iad_ablation_fixture/`
- `outputs/iad_ablation_openalex_v1/`
- `outputs/iad_ablation_open_v2/`
- `outputs/iad_bench_fixture/`
- `outputs/iad_bench_open_v1/`
- `outputs/iad_bench_open_v2/`
- `outputs/strong_baseline_fixture/`
- `outputs/strong_baseline_open_v2/`
- `outputs/baseline_error_analysis_open_v2/`
- `outputs/single_space_union_open_v2/`
- `outputs/iad_risk_model_fixture/`
- `outputs/iad_risk_openalex_v1/`
- `outputs/iad_risk_open_v2/`
- `outputs/iad_risk_transformer_open_v2/`
- `outputs/iad_bootstrap_fixture/`
- `outputs/iad_bootstrap_openalex_v1/`
- `outputs/iad_bootstrap_open_v2/`
- `outputs/iad_paper_report_fixture/`
- `outputs/reviewer_audit_fixture/`
- `outputs/journal_readiness_fixture/`
- `outputs/experiment_queue_fixture/`
- `outputs/experiment_preflight_fixture/`
- `outputs/experiment_dependency_fixture/`
- `outputs/experiment_execution_pack_fixture/`
- `outputs/remote_output_validation_fixture/`
- `outputs/remote_result_acceptance_fixture/`
- `outputs/remote_environment_audit_fixture/`
- `outputs/remote_execution_blueprint_fixture/`
- `outputs/remote_connection_pack_fixture/`
- `outputs/paper_claim_audit_fixture/`
- `outputs/research_depth_audit_fixture/`
- `outputs/submission_gate_audit_fixture/`
- `outputs/manuscript_evidence_matrix_fixture/`
- `outputs/manuscript_draft_skeleton_fixture/`
- `outputs/journal_upgrade_plan_fixture/`
- `outputs/advanced_model_evidence_fixture/`
- `outputs/q2b_action_board_fixture/`
- `outputs/q2b_completion_audit_fixture/`
- `outputs/q2b_acceptance_rubric_fixture/`
- `outputs/q2b_experiment_optimizer_fixture/`
- `outputs/q2b_upgrade_roadmap_fixture/`
- `outputs/primary_track_superiority_evaluator_fixture/`
- `outputs/public_data_validity_audit_fixture/`
- `outputs/iad_bench_stratification_audit_fixture/`
- `outputs/iad_bench_source_bias_diagnostic_fixture/`
- `outputs/iad_bench_provenance_balance_plan_fixture/`
- `outputs/iad_bench_source_candidate_registry_fixture/`
- `outputs/iad_model_feature_guard_fixture/`
- `outputs/open_v3_plan_audit_fixture/`
- `outputs/open_v3_source_plan_fixture/`
- `outputs/open_v3_split_readiness_fixture/`
- `outputs/open_v3_heldout_split_plan_fixture/`
- `outputs/mechanism_error_evidence_fixture/`
- `outputs/topic_package_final/`

## 后续工作优先级

### P1：IAD-Bench 构造器

状态：

```text
已完成 fixture 级构造器与论文证据接入。
```

当前产物：

```text
iad_bench_documents.jsonl
iad_bench_pairs.jsonl
iad_bench_splits.jsonl
iad_bench_summary.jsonl
label_provenance_summary.csv
dataset_card.md
```

### P2：强 baseline

状态：

```text
已完成 representation baseline、entity matching baseline 执行框架和 execution_mode 证据记录。
```

已完成：

```text
run-representation-baseline CLI
run-entity-matching-baseline CLI
run-llm-judge-baseline CLI
build-baseline-error-analysis CLI
run-single-space-union-baseline CLI
run-iad-evidence-bootstrap CLI
baseline_scores.jsonl
baseline_execution_summary.jsonl
baseline_metric_summary.jsonl
baseline_error_summary.jsonl
baseline_error_cases.jsonl
single_space_union_summary.jsonl
single_space_union_predictions.jsonl
iad_risk_bootstrap_confidence.csv
scincl_bootstrap_confidence.csv
roberta_pair_bootstrap_confidence.csv
scincl_single_space_union_bootstrap_confidence.csv
baseline_family / execution_mode 进入 RQ 报告
SciNCL actual_model 远程执行
RoBERTa/DistilBERT pair classifier actual_model 远程执行
LLM judge fallback 链路验证
hard_negative_false_merge_rate 错误分析
single-space union-find 对照实验
IAD-Risk 与强 baseline 分层 bootstrap 置信区间
审稿矩阵不把 fallback 误判为真实强 baseline
IAD-Bench-Open-v2 上 SciNCL actual_model 执行
IAD-Bench-Open-v2 上 DistilBERT MRPC actual_model 执行
IAD-Bench-Open-v2 上 RoBERTa MRPC actual_model 执行
实体匹配 baseline 自动使用 CUDA 并记录 device
IAD-Bench-Open-v2 上 IAD-Risk Transformer actual_model 执行
IAD-Risk Transformer all/train/dev/test 分层摘要
```

仍需补齐：

```text
provenance-blind SciNCL IAD-Risk Transformer actual_model 重训
Ditto / DeepMatcher 专用复现
LLM pair judge api_model 实际执行
```

### P3：IAD-Risk 模型

目标：

```text
已实现 lightweight dual-space model；
已完成 frozen Transformer encoder + transparent risk heads 链路；
已完成 IAD-Bench-Open-v2 actual_model 实验；
已补齐 SPECTER2 adapter 编码入口、CLI/RQ 字段和 open_v3 scholarly source-heldout CUDA actual_model；
源码已移除 Transformer 训练特征和中间增强 relation 中的 same_source_dataset；
已完成 DeBERTa NLI cross-encoder 与 SPECTER2 IAD-Risk Transformer source-heldout 评估；后续仍可补 fine-tuning 或更多 cross-encoder 变体。
```

当前产物：

```text
iad_risk_model.json
iad_risk_summary.jsonl
iad_risk_predictions.jsonl
iad_risk_transformer_model.json
iad_risk_transformer_summary.jsonl
iad_risk_transformer_predictions.jsonl
```

当前边界：

```text
fixture 级训练 same_work_f1 = 1.0，same_agenda_f1 = 0.8，agenda_non_identity_f1 = 0.8；
v2 公开数据训练 same_work_f1 = 0.970213，agenda_non_identity_f1 = 0.99975；
IAD-Risk Transformer test same_work_f1 = 0.979592，test agenda_non_identity_f1 = 0.997030；
IAD-Risk Transformer hard_negative_false_merge_rate_mean = 0.0；
已生成的旧 SciNCL Transformer actual-model 含 same_source_dataset，当前不能写成 provenance-blind 主结果；
本地严格 SciNCL 重训探测失败，原因是当前 conda 环境缺少 sentence_transformers；不能把 hashing fallback 写成强模型 actual_model；
当前结果可以作为公开主链路阶段性结果，但不能替代 human audit。
```

### P4：期刊增强

目标：

```text
接入 500-1,000 条 human_audit gold，完成二区 / B 类投稿包。
```

## 审稿判断

当前重构完成后，课题将从“工程原型”进入“可投稿研究路线”。但在强 baseline 和 IAD-Risk 模型真正跑完前，仍不能声称已经达到二区或 B 类完成状态。

当前最关键风险：

```text
表示模型与 pair-classifier baseline 已在 v2 达到 actual_model；SPECTER2 adapter actual_model 已闭环，LLM pair judge api_model 仍缺
Transformer 级 IAD-Risk 已实现 frozen encoder 版本，但尚未 fine-tuning / cross encoder
IAD-Bench 大规模 gold/proxy/silver 已有 v2 起点，但 gold 规模仍偏小
human_audit_plan 已接入 RQ 报告，正式计划规模 500-1,000 条 pair；audit_status = planned_not_collected，不表示已有人工 gold
当前阶段暂不把新增人工标注作为前置条件，人工 gold 仅保留为后续增强；论文主线必须依赖公开 gold、proxy、silver 与强 baseline 证据链
journal_readiness high_severity_blocker_count = 3
experiment_queue 已按当前 journal_readiness 重建；当前 44 个任务中 21 个 already_satisfied，SPECTER2 adapter、SPECTER2 IAD-Risk Transformer 与 Ditto-style EM 已由 open_v3 scholarly source-heldout CUDA actual_model 结果闭环，不再作为远程根阻塞；剩余高风险项集中在主轨道 GPT judge 密钥、LLM api_model、provenance-blind SciNCL open_v2 重训和后续 venue rebuild
experiment_preflight 当前 44 个任务中，21 个 already_satisfied；其余主要状态为 remote/API/GPU、输入缺失与密钥缺失阻塞；远程输出验收当前 total_output_count = 171，valid_output_count = 155，missing_output_count = 16
experiment_dependency 已按当前 journal_readiness 重建，SPECTER2 adapter baseline / Transformer 与 Ditto-style EM 不再作为根阻塞；当前实际剩余根阻塞收敛到 GPT judge、LLM pair judge API、provenance-blind SciNCL open_v2 远程 GPU 和后续 venue rebuild
experiment_execution_pack 已生成 4 个阶段脚本：stage 0 负责 GPT judge、LLM、open_v2 provenance-blind Transformer、balanced gold 和 source-held-out 根任务，stage 1/2 负责评估和 bootstrap，stage 3 负责证据包重建；同时生成 remote_handoff.md 和 remote_output_manifest.jsonl，用于远程执行交接与输出验收
remote_output_validation 已接入，用于远程结果回传后检查输出文件存在性、非空性和 JSONL/CSV 基础格式，防止缺失或损坏文件进入论文证据链；当前 all_outputs_valid = false，total_output_count = 171，valid_output_count = 161，missing_output_count = 10
remote_result_acceptance 已接入远程结果接收审计，用于把输出验收结果映射到论文门禁；当前已重建到 open_v3 scholarly source-heldout Ditto/GPT 主轨道口径，task_count = 44，accepted_task_count = 38，blocked_task_count = 6，gate_count = 7，accepted_gate_count = 5，blocked_gate_count = 2，missing_output_count = 10，all_claim_gates_accepted = false；Ditto-style EM 已完成远程 4090 actual_model 训练、推理、评估和 bootstrap；OPENAI_API_KEY 现在是 GPT judge 主轨道密钥阻塞，未闭环前不得写成强模型矩阵完成
remote_environment_audit 已接入强模型远程环境依赖审计；当前 check_count = 5，ready_count = 4，missing_count = 1，all_required_ready = false；远程 iad-sieve conda 环境中 sentence_transformers、torch、transformers、adapters 已 ready，torch CUDA 可用，唯一缺失项是 OPENAI_API_KEY。该密钥只允许作为远程环境变量安全配置，不得写入代码、JSONL、Markdown、profile 或脚本
remote_execution_blueprint 已接入远程强模型执行蓝图；当前 blueprint_item_count = 7，environment_missing_count = 1，root_task_count = 2，root_task_blocked_count = 2，missing_output_count = 4，all_remote_prerequisites_ready = false；该蓝图根阻塞已收敛为 GPT judge / LLM API 输出与 OPENAI_API_KEY，已验收的 open_v3 SciNCL/RoBERTa/SPECTER2/Ditto 任务不再重复进入待执行蓝图
remote_connection_pack 已接入远程连接准备包；当前 item_count = 15，connection_field_count = 6，missing_required_field_count = 0，blocked_secret_count = 1，stage_command_count = 4，script_template_count = 3，all_remote_run_inputs_ready = false；连接字段已由本地 profile 识别为 ready；remote_preflight.template.sh、remote_sync_and_run.template.sh 和 remote_pull_outputs.template.sh 新增 REMOTE_CONDA_PATH / REMOTE_CONDA_COMMAND，支持显式远程 conda 可执行文件路径，避免默认 PATH 误判；模板仍不保存 API 密钥或私钥内容
remote_input_request 已接入远程输入请求包；当前 request_count = 8，missing_connection_field_count = 0，blocked_secret_configuration_count = 1，deferred_secret_configuration_count = 1，unsafe_to_store_count = 1，primary_track_ready_to_execute_remote_stages = true，global_ready_to_execute_all_remote_stages = false；当前连接字段已齐备，OPENAI_API_KEY 被列为远程安全配置输入，主轨道切片与 readiness 已将其识别为 GPT judge 主轨道密钥阻塞；不要发送私钥内容、密码或 sk- 密钥值
remote_execution_slice 已接入远程执行切片；当前 slice_count = 4，track_slice_count = 2，blocked_slice_count = 4，ready_slice_count = 0，remote_input_blocked = true，primary_track = open_v3_scholarly_balanced_gold_source_heldout，primary_track_task_count = 1，primary_track_missing_output_count = 2，unmapped_track_slice_count = 0，q2b_remote_execution_slice_ready = false；该切片不再要求重复运行已验收的 open_v3 SciNCL/RoBERTa/SPECTER2/Ditto root task，当前主轨道阻塞是 OPENAI_API_KEY 缺失与 GPT judge 两个原始输出未回传
remote_slice_run_pack 已接入切片级远程运行包；当前 slice_script_count = 3，slice_task_command_count = 3，blocked_script_count = 0，primary_track = open_v3_scholarly_balanced_gold_source_heldout，primary_track_command_count = 1，primary_track_required_secret_count = 1，q2b_remote_slice_run_pack_ready = true；已生成主轨道执行脚本 run_remote_slice_open_v3_scholarly_balanced_gold_source_heldout.template.sh，运行前必须在远程安全配置 OPENAI_API_KEY
primary_remote_readiness 已接入主轨道远程就绪审计；当前 primary_track = open_v3_scholarly_balanced_gold_source_heldout，readiness_status = blocked_missing_primary_secret，missing_connection_field_count = 0，missing_primary_secret_count = 1，deferred_global_secret_count = 0，unmapped_system_count = 0，primary_remote_ready = false；主轨道连接字段已齐备，真实阻塞是 GPT judge 所需 OPENAI_API_KEY 尚未安全配置
primary_remote_handoff 已接入主轨道远程交接包；当前 handoff_status = waiting_for_primary_secret，connection_field_count = 0，primary_task_count = 1，missing_primary_secret_count = 1，deferred_global_secret_count = 0，unmapped_system_count = 0，post_run_validation_step_count = 27；交接包已生成主轨道执行脚本和回传后的本地验证脚本，后处理脚本会从 GPT 原始 scores 生成 metric summary、bootstrap 与 advanced evidence 输入
primary_track_claim_gate 已接入主轨道论文主张门禁；当前 primary_track = open_v3_scholarly_balanced_gold_source_heldout，claim_gate_status = blocked，claim_allowed = false，blocking_reason_count = 6，connection_field_count = 0，ready_model_count = 4，missing_required_system_count = 1，reviewer_risk = high；该门禁把主轨道密钥、GPT 缺失输出、模型优势、创新深度和 Q2/B 接收判定合并为论文主张边界，禁止写 SOTA、强模型闭环、跨来源泛化完成或二区/B 类完成
primary_track_superiority_protocol 已接入主轨道优势判定协议；当前 primary_track = open_v3_scholarly_balanced_gold_source_heldout，protocol_status = blocked_waiting_for_primary_models，required_system_count = 11，required_comparison_count = 2，minimum_f1_delta = 0.0，minimum_false_merge_reduction = 0.02，minimum_hard_negative_reduction = 0.05，requires_bootstrap_ci = true，claim_allowed_after_protocol = false；该协议预注册 IAD-Risk Transformer 相对强 baseline 的效果量与 95% bootstrap CI 门槛，缺少 GPT judge 前不得声称主轨道先进性
primary_track_superiority_evaluator 已接入主轨道实际优势判定器；当前 primary_track = open_v3_scholarly_balanced_gold_source_heldout，evaluation_status = blocked_missing_primary_metrics，passed_comparison_count = 0，blocked_comparison_count = 2，failed_comparison_count = 0，claim_allowed_by_evaluator = false；该判定器已切换到 source-heldout 输入口径，但当前协议要求的主轨道指标仍未完整匹配，不能写主轨道模型优势、SOTA 或二区/B 类先进性
no_annotation_protocol 已接入无人工标注阶段协议；当前 protocol_item_count = 5，blocked_annotation_count = 0，blocked_remote_count = 1，claim_lockdown_count = 1，high_reviewer_risk_count = 2，human_annotation_required_now = false，no_annotation_stage_allowed = true，q2_b_ready_under_no_annotation_strategy = false；该协议把“当前可不依赖人工标注继续推进”和“不得声称已有人工 gold / 强模型闭环 / SOTA / 二区或 B 类完成”写成可验收边界
q2b_acceptance_rubric 已接入 Q2/B 接收判定 rubric；当前 gate_count = 9，ready_gate_count = 1，blocked_gate_count = 8，highest_priority_blocker = remote_reproducibility_acceptance，q2b_acceptance_ready = false；该 rubric 明确只有 no_annotation_strategy_acceptance ready，远程复现、强模型矩阵、模型优势、创新深度、创新可证伪闭环、相关工作新颖性边界、主张锁定和最终接收判定仍 blocked
q2b_experiment_optimizer 已接入审稿驱动实验优化器；当前 experiment_count = 7，blocked_external_input_count = 1，blocked_remote_execution_count = 6，ready_for_local_review_count = 0，highest_priority_experiment = exp_remote_reproducibility_acceptance，primary_track = open_v3_scholarly_balanced_gold_source_heldout，primary_track_required_secret_count = 1，deferred_global_secret_count = 0，primary_track_can_start_without_deferred_secrets = false，q2b_experiment_plan_ready = false；该优化器把 Q2/B blocked gate、reviewer_iteration_audit、remote_input_request、remote_execution_slice 和 advanced_model_evidence_track_summary 合并为下一轮实验动作；当前优先项是在远程安全配置 OPENAI_API_KEY 后运行 Ditto-style EM 与 GPT judge 主轨道任务，并在回传后重建 remote_output_validation、remote_result_acceptance 与证据包
novelty_falsification_matrix 已接入创新可证伪矩阵；当前 contribution_count = 5，ready_contribution_count = 4，conditional_contribution_count = 1，blocked_contribution_count = 0，highest_priority_blocker = 空，q2b_novelty_defensible = false；该矩阵把 identity/agenda 风险分离、强模型优势、encoder/provenance 有效性、source-held-out 泛化和无人工标注边界分别映射到审稿人零假设、最近似已有工作家族、控制实验和论文表述边界；当前剩余缺口收敛为 strong_model_superiority_control 的条件性证据，仍不能声称完整创新闭环
prior_art_novelty_audit 已接入相关工作新颖性审计；当前 prior_art_family_count = 5，ready_prior_art_family_count = 3，conditional_prior_art_family_count = 1，blocked_prior_art_family_count = 1，unresolved_high_risk_family_count = 1，duplicate_work_found = false，highest_priority_blocker = llm_entity_matching，q2b_prior_art_position_defensible = false；该审计把 SPECTER/SciNCL/SPECTER2、Ditto/RoBERTa/DistilBERT、LLM entity matching、OpenAlex/OpenCitations 和 IAD 问题定义分别转成必须比较项与论文主张边界；当前不能写“没有相似工作”或“没有更先进工作”
paper_claim_audit 当前支持 2 条写作主张，禁止 3 条过度主张：SOTA/强模型优越、二区/B 类完成、人工 gold 已有
research_depth_audit 当前判定 problem_innovation = defensible，statistical_rigor = defensible，model_depth = defensible，advanced_baseline = not_ready，data_validity = conditional
submission_gate_audit 已接入投稿 go/no-go 审计；当前 submission_decision = blocked，blocked_gate_count = 7，conditional_gate_count = 1；source_bias_gate、model_depth_gate 与 training_input_gate 已 ready，但 remote_result_acceptance_gate、remote_connection_gate、advanced baseline、远程输出、LLM judge、模型特征复核和 Q2/B 主张仍阻塞；blocking_reasons 包含 remote_result_acceptance、remote_claim_gate_blocked、remote_result_missing_outputs、remote_secret_configuration、llm_pair_judge_api_model、model_feature_leakage 与 state_of_the_art_superiority
manuscript_evidence_matrix 已接入稿件写作边界；当前仅 identity_agenda_risk_modeling 可作为 main claim，SOTA/二区完成/人工 gold 已有等主张均不得写入论文结论
reviewer_response_matrix 已接入审稿回应边界；当前 response_count = 12，ready_to_answer_count = 4，limited_answer_count = 4，do_not_answer_as_claim_count = 4，must_not_claim_count = 6；duplicate_work 已接入 prior_art_novelty_audit 的高风险相邻工作清单，scientific representation、PLM entity matching 和 LLM entity matching 未完全闭环前不能写成“没有相似工作”；SPECTER2 actual_model 已完成，但 baseline_strength、executed_strong_baselines 和 venue_readiness 仍只能写作局限或待完成实验
manuscript_draft_skeleton 已接入章节级安全写作骨架；当前 abstract/conclusion = restricted，experiments = todo，method/introduction/related_work/limitations = ready
journal_upgrade_plan 已接入二区/B 类升级优化计划；该产物仍是旧门禁拆解视图，尚未按 open_v3 scholarly source-heldout SPECTER2 结果重建；当前实际外部高风险缺口应聚焦 LLM API、Ditto-style EM、provenance-blind Transformer 重训和远程验收链刷新，人工标注继续作为 deferred enhancement
advanced_model_evidence 已接入高级模型证据矩阵；`outputs/advanced_model_evidence_fixture/` 已切换到 open_v3 scholarly source-heldout 主口径，当前 evidence_count = 8，ready_actual_model_count = 7，ready_model_count = 7，missing_required_count = 1。已就绪系统为 `iad_risk_transformer_scincl_open_v3_scholarly_balanced_gold_source_heldout`、`iad_risk_transformer_specter2_open_v3_scholarly_balanced_gold_source_heldout`、`scincl_cosine_open_v3_scholarly_balanced_gold_source_heldout`、`specter2_adapter_cosine_open_v3_scholarly_balanced_gold_source_heldout`、`roberta_pair_open_v3_scholarly_balanced_gold_source_heldout`、`deberta_pair_open_v3_scholarly_balanced_gold_source_heldout`、`ditto_style_em_open_v3_scholarly_balanced_gold_source_heldout`；缺失系统为 GPT/LLM judge。该矩阵只能支撑 limited advancedness，不能写强模型矩阵完整。
SPECTER2 adapter 与 SPECTER2 IAD-Risk Transformer 已完成远程 CUDA actual_model：SPECTER2 adapter cosine test same_work_f1 = 0.821429，风险预算下无可行 selected 阈值；SPECTER2 IAD-Risk Transformer test same_work_f1 = 0.973118，selected_row_count = 9，max_selected_safe_merge_recall = 0.983696。该结果可写成 encoder stability 证据，但不能写成主方法全面优越。
q2b_action_board 已接入二区/B 类行动板；当前 action_count = 22，high_risk_action_count = 14，blocked_action_count = 14，remote_root_task_count = 2，remote_handoff_template_count = 3，advanced_track_gap_count = 2，unmapped_advanced_track_gap_count = 0，external_input_count = 1，q2_b_ready = false；该行动板已把远程交接模板、远程环境、远程结果接收、2 个真实未验收 GPT 根任务、高级模型评估轨道缺口和投稿门禁复核合并为审稿优先级队列；Ditto-style EM 已从缺口转为 ready_actual_model，当前主轨道阻塞是 GPT judge 的 OPENAI_API_KEY 与 GPT 输出未回传
q2b_completion_audit 已接入最终目标完成度审计；当前 criterion_count = 12，ready_count = 4，conditional_count = 0，blocked_count = 8，overall_completion_status = blocked，q2_b_goal_ready = false；该审计把 submission gate、行动板、审稿回应、远程连接、远程结果接收、创新深度压力测试、高级模型证据、split readiness、训练输入、source-heldout coverage 和 split evaluation 汇总为“是否真的能声称二区/B类完成”的最终证据门；COCI source-heldout 数据覆盖与 limited split evaluation 已 ready，但远程输出验收、LLM judge、强模型矩阵、provenance-blind、SOTA 优势和创新深度证据仍阻断；GPT/LLM judge、provenance-blind 和远程验收重建未闭环前，不得写成强模型证据或 Q2/B 证据闭环
q2b_external_blocker_audit 已接入外部阻塞合同审计；当前 blocker_count = 6，external_secret_count = 1，advanced_missing_count = 2，claim_lock_count = 1，missing_output_count = 10，highest_priority_blocker = external_secret:OPENAI_API_KEY，q2b_blocked_by_external_inputs = true。该审计不保存任何密钥值，只给出安全配置动作、缺失 GPT/LLM judge 输出和论文主张锁；远程预检确认 workspace = present，OPENAI_API_KEY = missing，默认 shell 中 conda = missing。
iad_source_heldout_gap_plan 已被 OpenAlex topic T10009 + OpenCitations COCI 子集闭合：`data/raw/opencitations/coci_T10009.csv` 包含 13,252 条有效 DOI-to-DOI 引用边，`outputs/openalex_opencitations_source_registry/T10009/` 生成 2,500 对 `agenda_non_identity` silver hard negative，且 `require_opencitations=true`。该结果只能写成 COCI second-source silver 覆盖，不等同人工 gold 或完整 SOTA 证据。
iad_bench_source_acquisition_audit 已加固 OpenCitations 输入验收；当前 overall_acquisition_status = ready，ready_to_convert_count = 5，missing_raw_file_count = 0，invalid_raw_file_count = 0。后续 COCI 候选仍必须满足 valid_citation_edge_count > 0 才能进入 ready_to_convert。
OpenAlex-only gap patch 已完成第一步公开数据获取与临时 hard-negative 构建：OpenAlex topic T10009 Works fetched_record_count = 5,000；OpenAlex-only weak-label 输出 document_count = 1,817，pair_count = 2,500，agenda_non_identity_pair_count = 2,500，citation_edge_count = 0；合并后临时 IAD-Bench `outputs/iad_bench_open_v3_openalex_only_gap_patch/` 为 documents = 19,306，pairs = 43,082，silver_pair_count = 2,500，agenda_non_identity_pair_count = 2,500
iad_source_heldout_coverage_audit 已修正为必须同时校验 `evaluation_split_strategy = source_held_out` 与 train/test `label_source` 不相交；OpenAlex-only gap patch 与 multi-topic topic-heldout split 不能被误写成 source-heldout，普通 random/topic split coverage 会被标记为 blocked_not_source_heldout_split，单来源伪 source-heldout 会被标记为 blocked_source_overlap；当前 COCI source patch 覆盖 same_work、unrelated 和 agenda_non_identity 三类 relation，ready_relation_count = 3，blocked_relation_count = 0
OpenAlex+COCI source patch 已完成：`outputs/openalex_opencitations_source_registry/T10009/` 为 document_count = 240、pair_count = 2,500、citation_edge_count = 13,252、require_opencitations = true；合并后的 `outputs/iad_bench_open_v3_coci_source_patch/` 为 documents = 19,546、pairs = 45,582、agenda_non_identity_pair_count = 5,000。`outputs/iad_bench_open_v3_coci_source_patch_source_heldout/` 的 assignment 覆盖 train_pair_count = 31,207、test_pair_count = 14,375。
COCI source-heldout lightweight IAD-Risk 已完成：test eval_pair_count = 14,375，agenda_non_identity_f1 = 0.948917，same_work_f1 = 0.086066，false_merge_rate = 0.000154。该结果只能写成 limited source-heldout 风险控制证据，不能写成主方法整体优越。
OpenAlex-only gap patch 的审稿审计结果：public_data_validity_audit 中 silver_topic_concentration = high_risk；open_v3_plan_audit 中 document_scale、silver_pair_scale、silver_topic_diversity 仍 blocked；open_v3_split_readiness overall_split_readiness = blocked；open_v3_heldout_split_plan assignment_count = 0；source_bias_diagnostic overall_source_bias_status = high_risk，max_eval_accuracy = 0.845538；provenance_balance_plan overall_provenance_balance_status = blocked。结论是：该 patch 可证明 hard negative 数据链路可跑通，但不能支撑 Q2/B 的 source-held-out、topic-held-out 或先进性主张
OpenAlex multi-topic silver patch 已完成第二步公开 hard-negative 扩展：OpenAlex 2024 article Works fetched_record_count = 3,000；weak-label 输出 document_count = 2,103，pair_count = 6,820，agenda_non_identity_pair_count = 6,820，topic_count = 344，top_silver_topic_ratio = 0.043988；合并后 `outputs/iad_bench_open_v3_multitopic_silver_patch/` 为 documents = 19,592，pairs = 47,402，silver_pair_count = 6,820，gold_pair_count = 40,582
OpenAlex multi-topic silver patch 的审稿审计结果：public_data_validity_audit 中 silver_topic_concentration = defensible；open_v3_plan_audit 中 silver_topic_diversity = defensible，但 document_scale 和 silver_pair_scale 仍 blocked；open_v3_heldout_split_plan 中 topic_held_out_split = ready，heldout_topic_count = 69，assignment_count = 6,820；source-held-out split 仍 blocked；source_bias_diagnostic overall_source_bias_status = high_risk，max_eval_accuracy = 0.859614；provenance_balance_plan overall_provenance_balance_status = blocked
topic-heldout scored lightweight IAD-Risk 已完成：test eval_pair_count = 5,580，agenda_non_identity_f1 = 0.929355，false_merge_rate = 0.004677，same_work_f1 = 0.337756。该结果只能写成 OpenAlex silver hard-negative 风险控制证据，不能写成 full same_work 模型优越或 Q2/B 完成证据
q2b_upgrade_roadmap 已接入阶段化升级路线图；当前 phase_count = 6，ready_phase_count = 0，blocked_phase_count = 5，conditional_phase_count = 0，deferred_phase_count = 1，highest_priority_blocker = p0_remote_connection_and_secret，human_annotation_required_now = false，q2_b_ready = false；连接字段已齐备，但 OPENAI_API_KEY、GPT 原始远程输出、provenance-blind 重训、source-heldout hard negative 和论文主张锁定仍未闭环
reviewer_iteration_audit 已接入审稿人迭代审核；当前 review_item_count = 7，critical_count = 3，major_revision_required_count = 7，minor_revision_required_count = 0，defensible_count = 0，highest_risk_iteration_id = r0_remote_reproducibility，q2_b_ready_from_reviewer_view = false；该审核从审稿人角度批判远程可复现性、强 baseline 与先进性、创新深度、模型泄漏、数据可信度、泛化和论文主张安全，并把批判转成下一轮实验优化动作
model_innovation_blueprint 已接入投稿级模型创新实验蓝图；当前 blueprint_count = 7，ready_count = 4，blocked_count = 2，conditional_count = 1，deferred_count = 0，overall_model_innovation_status = blocked。机制对比、open_v3 scholarly source-heldout 泛化、SPECTER2 encoder 稳定性和 Ditto-style EM 强 baseline 已 ready；provenance-blind 重训和 LLM API 仍不能写成已完成创新。
model_superiority_audit 已接入模型优势审计；当前 comparison_count = 1，blocked_missing_comparison_count = 1，overall_superiority_status = blocked，sota_claim_allowed = false。当前 advanced evidence 只允许写强 baseline 矩阵的 limited 进展：Ditto-style EM 已作为 actual_model baseline 闭环，但 GPT/LLM judge、provenance-blind 和主轨道优势 CI 未闭环，仍阻断最终先进性主张。
innovation_depth_stress_test 已接入创新深度压力测试；当前 stress_count = 6，ready_count = 4，blocked_count = 2，overall_innovation_depth_status = blocked，q2_b_innovation_claim_allowed = false；机制解释现在同时依赖 mechanism_triangulation_audit 达到 cross_system_mechanism_evidence 和 mechanism_triangulation_sensitivity 达到 threshold_stable_cross_system_evidence 才能保持 ready，source-heldout 泛化维度已 ready，剩余阻塞集中在 missing_strong_comparison 与 overall_innovation_depth
public_data_validity_audit 已接入公开数据可信度审计；balanced gold 当前 gold_scale = defensible，split_coverage = defensible，human_audit_absence = deferred_enhancement；完整 hard-negative 仍依赖 OpenAlex 多 topic silver 和后续人工 audit
iad_bench_stratification_audit 已接入 IAD-Bench 分层分布审计；balanced gold 当前 overall_stratification_status = defensible；full open_v3 用于规模报告，旧 open_v2 的 source_relation_confounding 不再作为主评估口径
iad_bench_source_bias_diagnostic 已接入 IAD-Bench 来源字段捷径诊断；balanced gold 当前 diagnostic_count = 3，high_risk_count = 0，overall_source_bias_status = defensible，max_eval_accuracy = 0.5；旧 open_v2 仍为 high_risk，只能作为反例说明为什么需要 balanced gold
iad_bench_provenance_balance_plan 已接入来源捷径缓解计划；balanced gold 当前 relation_count = 2，blocked_relation_count = 0，overall_provenance_balance_status = defensible，max_dominant_source_ratio = 0.798298；agenda_non_identity 仍未进入 balanced gold，需 OpenAlex 多 topic hard negative 补齐
iad_bench_source_candidate_registry 已接入公开来源候选 registry；当前 candidate_count = 5，public_gold_candidate_count = 4，silver_candidate_count = 1，ready_with_existing_adapter_count = 5，requires_download_count = 5，total_target_pair_count = 4,500；该 registry 将 same_work/unrelated 指向 DeepMatcher DBLP-Scholar 与 Amazon-Google，将 agenda_non_identity 指向 OpenAlex topic + OpenCitations COCI，当前仍是候选计划，不是已完成 source-held-out 证据
iad_bench_source_acquisition_audit 已刷新公开来源获取状态：正式 OpenAlex+COCI 候选当前 missing_raw_file_count = 0，invalid_raw_file_count = 0，overall_acquisition_status = ready；OpenAlex Works 与 COCI 子集均可进入转换。
iad_source_heldout_gap_plan 当前已从“缺口计划”转为“已闭合的 COCI source patch 证据”：agenda_non_identity 有第二公开来源、目标规模 2,500 pair 已达成、source-heldout assignment 与 coverage audit 已通过；但该证据仍是 silver，不等同人工 gold，也不能声称已消除所有 provider-level source bias。
iad_model_feature_guard 已接入 IAD 模型特征泄漏审计；当前 audit_count = 2，defensible_count = 1，high_risk_count = 1，violation_count = 2，overall_feature_guard_status = high_risk；lightweight IAD-Risk 未使用显式标签或来源字段，但已生成的 SciNCL Transformer actual-model 仍含旧特征 same_source_dataset；源码已移除该训练特征和中间增强字段，需在具备 sentence_transformers 的远程环境重训 actual-model 后重新审计
open_v3_plan_audit 已接入 Open-v3 数据目标差距审计；当前 blocked_count = 4，defensible_count = 1，deferred_enhancement_count = 1，overall_open_v3_status = blocked
open_v3_source_plan 已接入 Open-v3 数据源扩展计划；当前 needs_public_data_count = 2，already_seen_topic_count = 1，waiting_source_inputs_count = 1，deferred_enhancement_count = 1；需要补 1,585 对公开 gold、40,000 对 OpenAlex silver hard negative 和 29 个 OpenAlex topic
open_v3_split_readiness 已接入 split 泛化就绪度审计；balanced gold 当前 random_split_coverage = defensible，pair_leakage_guard = defensible，source_held_out_readiness = defensible，topic_held_out_readiness = blocked，overall_split_readiness = blocked
open_v3_heldout_split_plan 已接入 held-out split 执行计划；balanced gold 当前 source_held_out_split = ready，heldout_source_diversity = defensible，topic_held_out_split = blocked，pair_leakage_guard = defensible，assignment_count = 13,396；source-held-out 派生 pair 已生成，train_pair_count = 10,694，test_pair_count = 2,702，heldout_source_count = 2，heldout_key_count = 2；当前可以写多来源 source-held-out 复核，但不能写成跨 topic 泛化结论
mechanism_error_evidence 已接入机制性错误证据、分层摘要与阈值敏感性；SciNCL 阈值 0.9 下 1075 个 hard-negative false merge 全部被 IAD-Risk Transformer 阻断，且 hard_negative_level=high/medium、split=train/dev/test 分层 prevention_rate 均为 1.0；SciNCL 在 0.5、0.7、0.8、0.9、0.95 阈值下 prevention_rate 均为 1.0；RoBERTa 在 0.5、0.7、0.8 阈值下分别暴露 46、7、1 个 hard-negative false merge 且均被阻断，0.9 以上没有 baseline failure signal，因此只能作为补充机制案例，不能作为强统计结论
mechanism_triangulation_audit 已接入跨 baseline 机制三角验证；当前 system_count = 2，false_merge_pair_count = 1075，cross_system_failure_pair_count = 1，single_system_failure_pair_count = 1074，unresolved_pair_count = 0，triangulation_status = cross_system_mechanism_evidence，q2b_mechanism_depth_ready = true；该结果支持“跨 baseline 共同失败存在且 IAD-Risk 能阻断”，但共同失败 pair 只有 1 个，论文中不得外推为所有模型家族的普遍机制结论
mechanism_triangulation_sensitivity 已接入跨阈值三角验证敏感性；当前 setting_count = 25，ready_setting_count = 13，cross_system_setting_count = 13，max_cross_system_failure_pair_count = 46，threshold_stability_status = threshold_stable_cross_system_evidence，q2b_threshold_stability_ready = true；该结果缓解固定阈值 0.8 下共同失败 pair 过少的质疑，但 RoBERTa 0.9/0.95 阈值没有 cross-system signal，因此论文只能写阈值区间内机制稳健
mechanism_case_pack 已接入论文机制案例包；当前 case_count = 3，cross_system_case_count = 1，single_system_case_count = 2，unresolved_case_count = 0，case_pack_status = paper_ready_limited_case_pack；该产物补全了 pair_id、失败 baseline、baseline 分数、IAD-Risk 风险概率、源/目标文献题名和审稿使用边界，可用于错误分析章节，但不能替代统计显著性、source-held-out 泛化或 Q2/B 完成证据
venue_readiness 仍为 needs_evidence，不能提前声称达到二区 / B 类完成状态
```
