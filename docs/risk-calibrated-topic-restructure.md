# Risk-Calibrated Scientific Entity Matching 课题重构审计

## 问题拆解

当前项目不能继续把 `IAD-Risk Transformer` 作为“新 Transformer 架构”或 SOTA 主方法来叙事。更稳妥的研究对象是科研文献实体匹配中的安全合并：

```text
两条记录可能语义相近、研究同一议题，但不是同一篇 scholarly work。
系统目标不是判断“像不像”，而是在显式 false-merge 风险预算下判断“是否可以安全合并”。
```

重构后的任务是风险约束选择性实体匹配，输出：

```text
safe_merge
reject
manual_review
```

## 关键结论

项目主线应从：

```text
IAD-Risk Transformer：降低 false_merge_rate 的 frozen encoder + 多头分类器
```

重构为：

```text
Risk-Calibrated Scientific Entity Matching under Agenda-Level Confounders：
面向同议题非同文干扰的风险约束安全合并框架
```

`IAD-Risk` 保留为 `agenda-aware conflict/risk module`，不再作为论文主方法名称。论文核心结论必须围绕：

```text
Recall_or_Coverage(method, risk <= α) > Recall_or_Coverage(baseline, risk <= α)
```

## 架构

五阶段框架：

```text
Stage 1：Candidate Generation
Stage 2：Identity Cross-Encoder
Stage 3：Agenda-Conflict Decomposition
Stage 4：Risk Calibration and Selective Decision
Stage 5：Cluster-Safe Merging and Evaluation
```

模块边界：

| 阶段 | 责任 | 当前状态 | 下一步 |
|---|---|---|---|
| Candidate Generation | 高召回候选，不负责最终合并 | 已有 lexical/dense/identifier candidate 入口 | 报告 candidate recall，避免让风险模型背召回不足 |
| Identity Cross-Encoder | same_work 精判 | 当前主要是 frozen SciNCL 表示 + 浅层头 | P1 引入 RoBERTa/DeBERTa cross-encoder 主方法分支 |
| Agenda-Conflict | 议题相似、冲突证据、版本边界分解 | 已有 `same_agenda` / `agenda_non_identity` head | 重命名为 conflict/veto signal，增加 version-risk |
| Risk Calibration | 风险预算下三态决策 | 已新增 `run-risk-calibrated-protocol` | 与所有强基线统一比较 FPR/FDR 预算 |
| Cluster-Safe Evaluation | pair edge 到 entity cluster 的污染审计 | 已接入 source-heldout cluster contamination、pair bootstrap CI 和 hard-negative stress cluster 审计 | P2 继续补齐更多强 baseline 的 stress cluster 对照 |

## 原理

旧二分类目标：

```text
same_work / not_same_work
```

新三态决策：

```text
safe_merge 当且仅当：
  identity_score >= τ_identity
  AND conflict_score <= τ_conflict
  AND uncertainty_score <= τ_uncertainty
  AND version_risk_score <= τ_version
```

否则：

```text
high_identity + high_conflict -> manual_review
high_version_risk -> manual_review
high_uncertainty -> manual_review
low_identity -> reject
```

必须同时报告：

| 指标 | 定义 | 作用 |
|---|---|---|
| negative false merge rate / FPR | `FP / N_negative` | 非同文 pair 被误合并比例 |
| merge contamination / FDR | `FP / (TP + FP)` | 自动合并结果中的错误比例 |
| safe-merge precision | `TP / (TP + FP)` | 自动合并可信度 |
| safe-merge recall | `TP / N_positive` | same_work 安全覆盖率 |
| review rate | `manual_review / all_pairs` | 人工复核压力 |
| hard-negative false merge rate | hard-negative 中被 safe_merge 的比例 | 同议题非同文压力测试 |
| cluster contamination rate | 含错误边 cluster 占比 | 实体解析最终伤害 |

## 工程

本轮已落地 P0 小步重构：

```text
src/iad_sieve/evaluation/risk_calibrated_protocol.py
tests/test_risk_calibrated_protocol.py
python -m iad_sieve.cli run-risk-calibrated-protocol --help
```

新增协议输出：

```text
risk_calibrated_protocol.jsonl
risk_calibrated_protocol.csv
risk_calibrated_protocol_summary.jsonl
risk_calibrated_protocol.md
```

推荐对当前 IAD-Risk Transformer 预测运行：

```bash
python -m iad_sieve.cli run-risk-calibrated-protocol \
  --relations outputs/iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout_extra_train_calibrated_fmr10/iad_risk_transformer_predictions.jsonl \
  --output-dir outputs/risk_calibrated_protocol_open_v3_source_heldout \
  --eval-split test \
  --system-name iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout_extra_train_calibrated_fmr10 \
  --identity-field p_same_work \
  --conflict-field p_false_merge_risk \
  --identity-thresholds 0.70,0.80,0.85,0.90,0.92,0.95 \
  --conflict-thresholds 0.10,0.30,0.50 \
  --fpr-budgets 0.01,0.03,0.05,0.10 \
  --fdr-budgets 0.01,0.03,0.05,0.10
```

## 项目级审计清单

需要优先修改或重审：

| 区域 | 文件/模块 | 重构要求 |
|---|---|---|
| 顶层叙事 | `README.md` | 主线改为 Risk-Calibrated Scientific Entity Matching |
| 研究计划 | `docs/restructured-topic-plan.md` | 从 IAD-Risk 主方法改为 safe-merge 风险框架 |
| 当前总结 | `docs/current-work-summary.md` | 收缩 SOTA、Q2/B、Transformer 架构表述 |
| GPT 简报 | `docs/gpt-pro-research-brief.md` | 保留为历史输入，不作为最新主线 |
| Claim gate | `src/iad_sieve/evaluation/primary_track_claim_gate.py` | 禁止新 Transformer、SOTA、Q2/B ready、silver=gold |
| 评价协议 | `src/iad_sieve/evaluation/risk_calibrated_protocol.py` | 新增 FPR/FDR 风险预算协议 |
| 模型优势 | `src/iad_sieve/evaluation/model_superiority_audit.py` | 已接入 constrained-risk operating-point 审计，best F1 降级为辅助指标 |
| 数据构造 | `src/iad_sieve/evaluation/openalex_adapter.py` 等 | hard-negative stress set 分层，不写作人工 gold |
| 聚类评估 | `src/iad_sieve/evaluation/clustering_evaluator.py` | 已增加 B³、pairwise clustering F1、cluster contamination、over/under-merge |

## 术语替换表

| 旧术语 | 新术语 | 处理方式 |
|---|---|---|
| IAD-Risk Transformer 主方法 | Risk-Calibrated Scientific Entity Matching 框架 | 论文主线替换 |
| 新 Transformer 架构 | frozen encoder + agenda-aware risk module | 禁止作为创新主张 |
| agenda_non_identity head | agenda-aware conflict signal | 从普通 head 改为 veto/conflict 信号 |
| false_merge_rate 阈值校准 | selective risk calibration | 与 FDR、review rate 一起报告 |
| best F1 对比 | Recall/Coverage @ FPR/FDR budget | 主实验替换 |
| OpenAlex silver hard negative | high-confidence pseudo-gold stress test candidate | 不等同人工 gold |
| duplicate prediction | safe_merge decision | 强调自动合并风险 |
| source-heldout passed | source-heldout identity evidence only | 不外推 hard-negative 泛化 |

## Hard-Negative Stress Test 设计

无人工标注阶段的名称：

```text
agenda-level non-identity stress set
```

或：

```text
high-confidence pseudo-gold hard-negative stress test
```

必须分三层：

| 层级 | 名称 | 用途 |
|---|---|---|
| Level 1 | high-confidence non-identity | 主 hard-negative stress test |
| Level 2 | version-risk ambiguous | manual_review 评估，不作为普通负例 |
| Level 3 | weak pseudo-negative | 训练或辅助分析，不进入主测试表 |

覆盖类型：

```text
A. 相似标题 + 稳定标识符冲突
B. Citation-neighbor hard negatives
C. Same venue / same year / same topic 近邻
D. One-cites-the-other hard negatives
E. Author-overlap trap
F. Title-template trap
G. Version-risk ambiguous set
```

禁止规则：

```text
不同 DOI -> not_same_work
```

原因是 preprint、conference version、journal extension、erratum 可能存在不同 identifier，但仍属于版本关系或同一作品族。

当前已新增构造入口：

```bash
python -m iad_sieve.cli build-hard-negative-stress-set \
  --relations outputs/iad_bench_open_v3_multitopic_silver_patch/scored_relations.jsonl \
  --output-dir outputs/hard_negative_stress_open_v3_multitopic_silver_patch \
  --min-title-similarity 0.80 \
  --min-embedding-similarity 0.75 \
  --min-shared-references 2
```

当前 Open-v3 multi-topic silver patch 输出：

```text
stress_pair_count = 6,820
high_confidence_non_identity_count = 6,802
version_risk_ambiguous_count = 18
weak_pseudo_negative_count = 0
stress_types = citation_neighbor, similar_title_identifier_conflict, version_risk_ambiguous
```

主张边界：

```text
该集合是 agenda-level pseudo-gold stress test，不等同人工 gold benchmark；
version_risk_ambiguous 仅用于 manual_review 机制评估，不作为普通负例；
当前真实数据暂未覆盖 author-overlap trap、title-template trap、one-cites-the-other 等全部类型，后续仍需补齐。
```

已新增 hard-negative stress cluster contamination 审计：

```text
src/iad_sieve/evaluation/stress_cluster_contamination.py
tests/test_stress_cluster_contamination.py
```

当前真实产物：

```text
outputs/stress_cluster_contamination_iad_risk_open_v3_multitopic_silver_patch/stress_cluster_contamination.md
outputs/stress_cluster_contamination_iad_risk_identifier_veto_open_v3_multitopic_silver_patch/stress_cluster_contamination.md
outputs/stress_cluster_contamination_iad_sieve_duplicate_score_open_v3_multitopic_silver_patch/stress_cluster_contamination.md
```

当前 stress cluster 审计结果：

```text
IAD-Risk lightweight：
  evaluated_stress_pair_count = 6,802
  prediction_coverage_rate = 1.0
  cluster_contamination_rate = 0.006747
  over_merge_pair_count = 18
  largest_contaminated_cluster_size = 3

IAD-Risk + identifier_conflict veto：
  evaluated_stress_pair_count = 6,802
  vetoed_merge_count = 17
  cluster_contamination_rate = 0.0
  over_merge_pair_count = 0
  largest_contaminated_cluster_size = 0

IAD-Sieve duplicate_score >= 0.92：
  evaluated_stress_pair_count = 6,802
  prediction_coverage_rate = 1.0
  cluster_contamination_rate = 0.0
  over_merge_pair_count = 0
  largest_contaminated_cluster_size = 0
```

审稿结论：

```text
可写：hard-negative stress cluster contamination 审计已补齐；原始 lightweight IAD-Risk 暴露 18 个传递 over-merge pair，但显式 identifier_conflict veto 可将 17 条直接自动合并转入 manual_review/veto，并把 stress cluster contamination 降为 0。
不可写：IAD-Risk 模型本体已通过 hard-negative stress 泛化；原因是归零依赖显式冲突 veto，而不是 p_same_work / p_false_merge_risk 自身稳定识别全部 stress 样本。
下一步：补齐 SciNCL/SPECTER2/RoBERTa/DeBERTa/Ditto/LLM 的同一 stress cluster 对照。
```

`identifier_conflict` veto 已纳入正式 selective decision protocol：

```text
src/iad_sieve/evaluation/risk_calibrated_protocol.py
tests/test_risk_calibrated_protocol.py
python -m iad_sieve.cli run-risk-calibrated-protocol --veto-fields identifier_conflict
```

当前 stress-only formal protocol 产物：

```text
outputs/stress_risk_protocol_input_iad_risk_open_v3_multitopic_silver_patch/iad_risk_stress_predictions.jsonl
outputs/risk_protocol_stress_iad_risk_raw_open_v3_multitopic_silver_patch/risk_calibrated_protocol.jsonl
outputs/risk_protocol_stress_iad_risk_identifier_veto_open_v3_multitopic_silver_patch/risk_calibrated_protocol.jsonl
```

正式协议结果：

```text
raw stress protocol：
  pair_count = 6,802
  safe_merge_count = 17
  hard_negative_false_merge_count = 17
  hard_negative_false_merge_rate = 0.002499
  merge_contamination_fdr = 1.0

identifier_conflict veto protocol：
  pair_count = 6,802
  safe_merge_count = 0
  vetoed_merge_count = 17
  hard_negative_false_merge_count = 0
  hard_negative_false_merge_rate = 0.0
  review_rate = 0.005293
```

强 baseline actual-model stress 对照：

```text
SciNCL actual_model malteos/scincl, threshold = 0.90：
  execution_mode = actual_model
  pair_count = 6,802
  missing_pair_count = 0
  direct_safe_merge_count = 2,668
  hard_negative_false_merge_rate = 0.392238
  cluster_contamination_rate = 0.304791
  over_merge_pair_count = 3,960
  largest_contaminated_cluster_size = 64

RoBERTa MRPC actual_model textattack/roberta-base-MRPC, threshold = 0.50：
  execution_mode = actual_model
  pair_count = 6,802
  missing_pair_count = 0
  direct_safe_merge_count = 38
  hard_negative_false_merge_rate = 0.005587
  cluster_contamination_rate = 0.011187
  over_merge_pair_count = 46
  largest_contaminated_cluster_size = 5
```

强 baseline stress 结论：

```text
可写：在同一 stress set 上，SciNCL 单空间科学语义相似会产生大规模直接 false merge，并通过传递闭包放大为 cluster contamination；RoBERTa MRPC pair classifier 风险较低但仍非零。IAD-Risk + identifier_conflict veto 在该 stress-only 协议下直接 hard_negative_false_merge_count = 0，cluster_contamination_rate = 0。
不可写：IAD 模型本体已全面优于所有强 baseline，或 hard-negative 泛化已完成。当前归零依赖显式 veto；SPECTER2、DeBERTa、Ditto-style EM 和 LLM judge 仍需补齐同一 stress protocol 与 cluster 对照。
```

## Constrained-Risk Baseline Comparison

已新增 source-heldout 约束风险比较：

```text
src/iad_sieve/evaluation/model_superiority_audit.py
tests/test_constrained_risk_superiority_audit.py
```

实际产物：

```text
outputs/risk_protocol_iad_risk_open_v3_balanced_gold_source_heldout/
outputs/risk_protocol_scincl_open_v3_balanced_gold_source_heldout/
outputs/risk_protocol_roberta_open_v3_balanced_gold_source_heldout/
outputs/advanced_model_evidence_constrained_risk_open_v3_source_heldout/
outputs/model_superiority_constrained_risk_open_v3_source_heldout/
outputs/risk_protocol_iad_risk_open_v3_scholarly_balanced_gold_source_heldout/
outputs/risk_protocol_scincl_open_v3_scholarly_balanced_gold_source_heldout/
outputs/risk_protocol_roberta_open_v3_scholarly_balanced_gold_source_heldout/
outputs/advanced_model_evidence_open_v3_scholarly_source_heldout/
outputs/model_innovation_blueprint_open_v3_scholarly_source_heldout/
outputs/model_superiority_open_v3_scholarly_source_heldout/
```

balanced source-heldout 历史结果：

```text
IAD-Risk risk module：selected_row_count = 3
selected operating point：FPR <= 0.03, FDR <= 0.10, safe_merge_recall = 0.246484, safe_merge_coverage = 0.136936
SciNCL baseline：selected_row_count = 0
RoBERTa pair historical baseline：selected_row_count = 0
model_superiority_audit constrained_risk_advantage_count = 2
model_superiority_audit overall_superiority_status = limited
```

open_v3 scholarly source-heldout 当前主轨道结果：

```text
IAD-Risk Transformer actual_model：selected_row_count = 9, max_selected_safe_merge_recall = 0.983696
IAD-Risk Transformer SPECTER2 actual_model：selected_row_count = 9, max_selected_safe_merge_recall = 0.983696
SciNCL actual_model：selected_row_count = 0
RoBERTa MRPC actual_model：selected_row_count = 9, max_selected_safe_merge_recall = 0.711957
DeBERTa NLI cross-encoder actual_model：selected_row_count = 0, protocol_status = blocked_no_feasible_threshold
SPECTER2 adapter cosine actual_model：selected_row_count = 0, protocol_status = blocked_no_feasible_threshold
model_superiority_audit constrained_risk_advantage_count = 4
model_superiority_audit blocked_missing_comparison_count = 2
model_superiority_audit overall_superiority_status = blocked
```

主张边界：

```text
可写：在 open_v3 scholarly source-heldout test 的同一 FPR/FDR 预算内，IAD-Risk 相对 RoBERTa 取得更高 safe-merge recall/coverage；SciNCL、DeBERTa 和 SPECTER2 adapter cosine 无可行 selected 阈值，而 IAD-Risk 有可行 operating point；SPECTER2 IAD-Risk 与 SciNCL IAD-Risk 在风险协议上等价，可作为 encoder stability 证据。
不可写：IAD-Risk 已全面优于 SciNCL / RoBERTa，或已达到 SOTA、Q2/B ready。
原因：DeBERTa 和 SPECTER2 adapter source-heldout actual-model 已闭环但风险预算表现不足；Ditto-style EM、LLM judge 和 provenance-blind 仍未闭环；bootstrap constrained-risk CI、更多 baseline stress 对照和特征泄漏复核仍未完成。
```

## Cluster-Level Contamination Evaluation

已新增 cluster-safe 评估口径：

```text
src/iad_sieve/evaluation/clustering_evaluator.py
tests/test_cluster_contamination.py
```

评价命令：

```bash
python -m iad_sieve.cli evaluate \
  --relations outputs/iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout_extra_train_calibrated_fmr10/iad_risk_transformer_predictions.jsonl \
  --risk-protocol outputs/risk_protocol_iad_risk_open_v3_balanced_gold_source_heldout/risk_calibrated_protocol.jsonl \
  --risk-system iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout_extra_train_calibrated_fmr10 \
  --risk-fpr-budget 0.03 \
  --risk-fdr-budget 0.10 \
  --identity-field p_same_work \
  --conflict-field p_false_merge_risk \
  --eval-split test \
  --output-dir outputs/cluster_contamination_iad_risk_selected_open_v3_balanced_gold_source_heldout_test
```

当前 source-heldout test 对照结果：

```text
IAD risk-selected：
  B3 F1 = 0.811327
  pairwise clustering precision = 0.900000
  pairwise clustering recall = 0.246484
  pairwise clustering F1 = 0.386984
  cluster_contamination_rate = 0.011958
  over_merge_pair_count = 37
  largest_contaminated_cluster_size = 4

SciNCL best-F1 threshold 0.90：
  B3 F1 = 0.844415
  pairwise clustering F1 = 0.692308
  cluster_contamination_rate = 0.094168
  over_merge_pair_count = 570
  largest_contaminated_cluster_size = 125

RoBERTa best-F1 threshold 0.50：
  B3 F1 = 0.828914
  pairwise clustering F1 = 0.645096
  cluster_contamination_rate = 0.069926
  over_merge_pair_count = 659
  largest_contaminated_cluster_size = 262
```

Cluster-level bootstrap CI 输出：

```text
outputs/cluster_bootstrap_open_v3_balanced_gold_source_heldout/iad_risk_selected_cluster_bootstrap.csv
outputs/cluster_bootstrap_open_v3_balanced_gold_source_heldout/scincl_bestf1_cluster_bootstrap.csv
outputs/cluster_bootstrap_open_v3_balanced_gold_source_heldout/roberta_bestf1_cluster_bootstrap.csv
```

300 次 pair bootstrap、95% CI：

```text
IAD risk-selected：
  cluster_contamination_rate point = 0.011958
  cluster_contamination_rate bootstrap mean = 0.010472
  cluster_contamination_rate 95% CI = [0.007814, 0.012860]
  pairwise_clustering_f1 point = 0.386984
  pairwise_clustering_f1 95% CI = [0.366882, 0.411009]

SciNCL best-F1 threshold 0.90：
  cluster_contamination_rate point = 0.094168
  cluster_contamination_rate bootstrap mean = 0.107316
  cluster_contamination_rate 95% CI = [0.096376, 0.117412]
  pairwise_clustering_f1 point = 0.692308
  pairwise_clustering_f1 95% CI = [0.694738, 0.723662]

RoBERTa best-F1 threshold 0.50：
  cluster_contamination_rate point = 0.069926
  cluster_contamination_rate bootstrap mean = 0.086604
  cluster_contamination_rate 95% CI = [0.077011, 0.094528]
  pairwise_clustering_f1 point = 0.645096
  pairwise_clustering_f1 95% CI = [0.641031, 0.670696]
```

主张边界：

```text
可写：当前 source-heldout test 上，IAD risk-selected operating point 的传递合并污染及其 bootstrap CI 显著低于 SciNCL/RoBERTa best-F1 baseline。
不可写：IAD 整体聚类质量优于强 baseline；原因是 IAD pairwise recall、pairwise F1 和 B3 F1 低于两个 baseline。
下一步：hard-negative stress 已补齐 SciNCL/RoBERTa actual-model cluster 对照；继续补齐 SPECTER2、DeBERTa、Ditto-style EM 和 LLM judge 对照。
```

## P0/P1/P2 执行计划

### P0：主线与评价协议重构

目标：

```text
重写 README、claim gate、evaluation protocol 和研究计划，停止使用 IAD-Risk Transformer 作为主方法中心。
```

验收标准：

```text
所有文档不再把 IAD-Risk 描述为 SOTA 或新 Transformer 架构；
主目标变为 low-risk safe-merge coverage；
run-risk-calibrated-protocol 可对 proposed method 和 baseline 输出统一 FPR/FDR 预算表。
```

### P1：Hard-negative 与强基线补齐

目标：

```text
构造 agenda-level stress set，并补齐 SciNCL、SPECTER2、RoBERTa/DeBERTa、Ditto-style EM、metadata-only、S2APLER-style baseline。
```

验收标准：

```text
所有模型都能在相同 FPR/FDR 风险预算下比较；
hard-negative false merge rate 明确低于强基线，或 claim gate 阻止优势主张。
```

### P2：模型升级与 cluster-level 评估

目标：

```text
引入 candidate retrieval + identity cross-encoder + conflict/veto + uncertainty/risk calibration，并评估传递合并污染。
```

验收标准：

```text
报告 B³、pairwise clustering F1、cluster contamination rate、over-merge count、under-merge count；
identifier-masked、provenance-blind、topic-heldout、venue-heldout、year-heldout 审计均进入 claim gate。
```

## 禁止继续使用的论文主张

```text
IAD-Risk 是 SOTA。
IAD-Risk 是新的 Transformer 架构。
IAD-Risk 已优于 SciNCL / RoBERTa。
agenda_non_identity hard-negative 泛化已被当前 source-heldout gold 证明。
OpenAlex silver 等同人工 gold。
当前结果已达到二区 / B 类投稿要求。
best F1 可以单独证明模型优势。
balanced pair-level evaluation 足以代表真实 entity resolution 部署效果。
```

## 后续最低证据闭环

达到投稿级别前，至少补齐：

```text
1. high-confidence agenda-level pseudo-gold stress set；
2. 小规模人工审计 pseudo-label 噪声率；
3. SciNCL、SPECTER2、RoBERTa/DeBERTa、Ditto-style、metadata-only、S2APLER-style baseline；
4. FPR/FDR 预算下的 Pareto 比较；
5. hard-negative false merge 显著性检验；
6. cluster contamination 审计；
7. agenda/conflict/calibration/cross-encoder/hard-negative mining/silver data 消融；
8. source/topic/venue/year/provenance/identifier 鲁棒性与泄漏审计；
9. false merge / false split 类型学错误分析；
10. 每轮实验后重新生成 claim gate。
```
