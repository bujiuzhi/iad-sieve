# GPT Pro 深度研究简报：IAD-Risk 当前方法与结果

## 状态说明

本文件是 2026-06-16 课题再重构前的输入简报，用于记录旧 `IAD-Risk Transformer` 方法、结果和审稿风险。最新主线已调整为：

```text
Risk-Calibrated Scientific Entity Matching under Agenda-Level Confounders
```

最新项目级审计与执行入口见：

```text
docs/risk-calibrated-topic-restructure.md
```

因此，本文件中的 `IAD-Risk Transformer` 主方法、强模型优势、Q2/B readiness 或 hard-negative 泛化相关表述均不得直接作为最新论文主张。

## 1. 问题拆解

当前课题研究的是科研文献去重 / 实体匹配中的误合并风险。

传统语义相似度或 pair classifier 容易把“同一研究议题”的论文误判为“同一篇文献”。例如两篇论文都研究 retrieval-augmented generation，标题、摘要、引用都相近，但它们不是同一篇 work，不能被合并。

本课题希望从“是否相似”转向“是否可以安全合并”：

```text
same_work：同一篇文献，可以合并
same_agenda：同一研究议题，但不一定能合并
agenda_non_identity：同议题但非同一文献，是关键 hard negative
unrelated：无明显身份或议题关系
```

核心目标不是做通用向量检索，而是降低 scholarly entity resolution 中的 false merge risk。

## 2. 当前方法

当前主方法名称：

```text
IAD-Risk Transformer
```

当前实现属于 frozen encoder + 多头风险判定模型，不是端到端微调大模型。

模型输入：

```text
文献 A：title / abstract / venue / year / author 等元数据
文献 B：title / abstract / venue / year / author 等元数据
pair-level provenance / split / relation label
```

当前编码器：

```text
malteos/scincl
embedding_dim：768
backend：sentence-transformers
pooling：cls
```

训练目标：

```text
same_work head：学习身份相同
same_agenda head：学习议题相同
agenda_non_identity head：学习同议题但非同一文献
merge_prediction：综合身份分数与风险阻断结果，决定是否合并
```

本轮关键工程改造：

```text
1. CLI 支持多个 --documents 输入；
2. CLI 新增 --extra-train-relations；
3. extra_train_relations 只参与训练，不进入评估输出；
4. source-heldout gold test 保持独立；
5. 修复 model_superiority_audit 误把失败比较汇总为 supported_limited 的问题。
```

本轮优化原因：

```text
旧 source-heldout 训练集中没有 agenda_non_identity 正例，
导致旧 IAD-Risk Transformer 只能以 identity_only 模式预测，
不能真正学习 false merge risk。
```

本轮优化策略：

```text
在 balanced gold source-heldout 测试不变的前提下，
额外引入 gold + OpenAlex silver 训练关系，
使 agenda_non_identity head 可以训练，
再进行 false_merge_rate 约束下的阈值校准。
```

## 3. 当前数据

### 3.1 Balanced gold source-heldout 测试集

```text
document_count：13,404
pair_count：13,396
same_work：6,698
unrelated：6,698
gold_pair_count：13,396
label_source_count：3
source-heldout train_pair_count：10,694
source-heldout test_pair_count：2,702
test positive：1,351
test negative：1,351
```

该测试集适合评估 same_work / unrelated 下的 source-heldout 身份判定，但当前 hard_negative_pair_count 为 0，因此不能证明 agenda_non_identity hard-negative 泛化能力。

### 3.2 Gold + silver 训练混合集

```text
input_relation_count：23,396
selected_pair_count：20,094
same_work：6,698
unrelated：6,698
agenda_non_identity：6,698
gold：13,396
silver：6,698
training_blend_ready：true
```

解释：

```text
gold 支撑 same_work / unrelated；
OpenAlex silver 支撑 agenda_non_identity；
该训练集可用于阶段性模型训练，不能替代人工 gold hard-negative。
```

## 4. 当前实验结果

### 4.1 旧 source-heldout IAD-Risk Transformer

```text
system：iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout
prediction_mode：identity_only
full_risk_trained：false
test F1：0.370283
test precision：0.910145
test recall：0.232420
test false_merge_rate：0.022946
```

解释：

```text
旧模型非常保守，误合并率低，但召回过低；
因为缺少 agenda_non_identity 训练信号，不能证明 IAD-Risk 的风险分解有效。
```

### 4.2 本轮优化后的 IAD-Risk Transformer

```text
system：iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout_extra_train_calibrated_fmr10
prediction_mode：full_iad_risk
full_risk_trained：true
train_pair_count：26,768
test_pair_count：2,702
test F1：0.604915
test precision：0.836601
test recall：0.473723
test false_merge_rate：0.092524
bootstrap F1 mean：0.604824
bootstrap F1 95% CI：0.579993 - 0.629519
bootstrap false_merge_rate mean：0.092561
bootstrap false_merge_rate 95% CI：0.077800 - 0.108619
```

解释：

```text
相比旧模型，召回和 F1 明显提升；
agenda_non_identity head 已训练；
但 same_work F1 仍不足，且 false_merge_rate 相比旧模型升高。
```

### 4.3 强基线对比

SciNCL cosine source-heldout：

```text
threshold 0.9：
F1：0.714436
precision：0.679813
recall：0.752776
false_merge_rate：0.354552
```

RoBERTa pair classifier source-heldout：

```text
threshold 0.5：
F1：0.663194
precision：0.624591
recall：0.706884
false_merge_rate：0.424870
```

当前模型优势审计：

```text
vs RoBERTa：
same_work_f1_delta：-0.276210
false_merge_rate_reduction：0.332346
status：not_supported

vs SciNCL：
same_work_f1_delta：-0.327452
false_merge_rate_reduction：0.262028
status：not_supported

overall_superiority_status：not_supported
sota_claim_allowed：false
```

解释：

```text
IAD-Risk 明显降低 false_merge_rate；
但 F1 没有超过强基线；
按当前审稿标准，不能声称模型全面优于 SciNCL 或 RoBERTa。
```

## 5. 当前审稿门控结论

```text
q2b_acceptance_ready：false
blocked_gate_count：8 / 9
claim_gate_status：blocked
primary_track_superiority_evaluator：failed_protocol_threshold
overall_innovation_depth_status：blocked
q2_b_innovation_claim_allowed：false
```

主要阻塞：

```text
1. 强基线优势不成立；
2. hard-negative test set 为空，无法证明 agenda_non_identity 泛化；
3. SPECTER2 / provenance-blind / LLM judge 轨道未补齐；
4. 当前方法仍像“frozen encoder + 校准分类器”，模型结构创新不足；
5. 无人工 gold hard-negative，只能作为 no-annotation 阶段证据。
```

当前不需要立即人工标注：

```text
human_annotation_required_now：false
no_annotation_stage_allowed：true
q2_b_ready_under_no_annotation_strategy：false
```

含义：

```text
可以继续做无人工标注阶段的公开数据与方法优化；
但不能声称已经达到二区 / B 类期刊证据要求。
```

## 6. 当前可成立的论文主张

可以谨慎表述：

```text
IAD-Risk 将 scholarly entity resolution 中的合并判定拆成 identity 与 agenda/risk 两层，
在 source-heldout balanced gold 上能够降低 false_merge_rate，
并显示 extra gold/silver risk training 对召回和 F1 有明显提升。
```

不能表述：

```text
不能说达到 SOTA；
不能说优于 SciNCL / RoBERTa；
不能说已满足二区 / B 类投稿；
不能说 agenda_non_identity hard-negative 泛化已经被充分验证；
不能把 OpenAlex silver 写成人工 gold。
```

## 7. 希望 GPT Pro 重点分析的问题

请从审稿人和方法重构角度回答以下问题：

```text
1. 当前 IAD-Risk 是否应继续作为主方法，还是应重构为“风险校准层 + 强模型 reranker”的框架？
2. 如何在不新增人工标注的阶段构造更强 hard-negative test set？
3. 如何设计模型结构，使创新不只是 frozen encoder + 阈值校准？
4. 是否应引入 cross-encoder、contrastive learning、multi-task loss、uncertainty calibration 或 conformal prediction？
5. 如何同时提高 same_work F1 并保持 false_merge_rate 优势？
6. 哪些实验是二区 / B 类审稿最可能要求的最低闭环？
7. 当前最合理的论文主张边界是什么？
8. 如果完全推翻现有方法，最有潜力的新课题核心应该是什么？
```

## 8. 建议的重构方向

优先方向：

```text
Risk-Calibrated Scientific Entity Matching
```

可考虑的模型框架：

```text
Stage 1：Bi-encoder / SciNCL / SPECTER2 召回候选；
Stage 2：Cross-encoder pair classifier 识别 same_work；
Stage 3：Agenda-aware hard-negative detector 识别同议题非同文；
Stage 4：Conformal / uncertainty calibration 输出“可安全合并 / 需人工复核 / 禁止合并”三态决策；
Stage 5：provenance-blind 和 source-heldout 评估防止来源捷径。
```

关键评估指标：

```text
same_work F1
false_merge_rate
hard_negative_false_merge_rate
source-heldout F1
topic-heldout F1
calibration error
abstention / review rate
```

最关键的下一步实验：

```text
1. 构造包含 agenda_non_identity 的 source-heldout / topic-heldout test；
2. 运行 SPECTER2 与 SciNCL 双 encoder 对比；
3. 加入 RoBERTa / DeBERTa / SciBERT cross-encoder；
4. 做 provenance-blind 训练，验证是否依赖数据来源捷径；
5. 做 threshold-free 或 calibrated decision analysis，避免只靠单点阈值。
```

## 9. 当前文件入口

核心摘要：

```text
docs/current-work-summary.md
docs/gpt-pro-research-brief.md
```

最终包：

```text
outputs/topic_package_final/
```

关键模型结果：

```text
outputs/iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout_extra_train_calibrated_fmr10/
```

强基线：

```text
outputs/strong_baseline_open_v3_balanced_gold_source_heldout/
```

审稿门控：

```text
outputs/model_superiority_audit_fixture/
outputs/q2b_acceptance_rubric_fixture/
outputs/innovation_depth_stress_test_fixture/
outputs/reviewer_threat_model_fixture/
```
