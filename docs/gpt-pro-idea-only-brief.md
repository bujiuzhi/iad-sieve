# 给 GPT Pro 的课题思路分析简报

## 使用边界

请只从研究思路、课题重构、创新性、审稿风险和实验设计角度分析，不需要给出具体代码实现、文件修改方案或工程任务拆解。

后续代码实现、实验脚本、工程重构和产物生成会回到 Codex 完成。

## 当前课题一句话概括

当前课题研究科研文献实体匹配中的误合并风险：两篇论文可能研究同一议题、语义非常相近，但不是同一篇文献，不能被错误合并。

核心问题不是“它们像不像”，而是“它们是否可以安全合并”。

## 当前方法

当前主方法名：

```text
IAD-Risk Transformer
```

当前方法把文献 pair 拆成三类风险信号：

```text
same_work：是否同一篇文献
same_agenda：是否同一研究议题
agenda_non_identity：是否同议题但非同一文献
```

当前实现方式：

```text
encoder：malteos/scincl
模式：frozen encoder + 多头风险分类/校准
目标：在尽量保留 same_work 识别能力的同时降低 false_merge_rate
```

本轮已做的关键优化：

```text
1. 训练时引入额外 gold + OpenAlex silver 关系；
2. 额外训练关系只参与训练，不混入 source-heldout gold 测试；
3. 让 agenda_non_identity head 真正可训练；
4. 做 false_merge_rate 约束下的阈值校准；
5. 修复模型优势审计逻辑，避免失败比较被误报为 supported。
```

## 当前数据

主要测试集：

```text
balanced gold source-heldout
document_count：13,404
pair_count：13,396
same_work：6,698
unrelated：6,698
test_pair_count：2,702
test positive：1,351
test negative：1,351
```

额外训练混合集：

```text
gold + silver training blend
selected_pair_count：20,094
same_work：6,698
unrelated：6,698
agenda_non_identity：6,698
gold：13,396
silver：6,698
```

重要限制：

```text
当前 source-heldout 测试集中 hard_negative_pair_count = 0
因此它不能证明 agenda_non_identity hard-negative 泛化能力
OpenAlex silver 不能等同于人工 gold
```

## 当前结果

旧模型：

```text
prediction_mode：identity_only
full_risk_trained：false
test F1：0.370283
precision：0.910145
recall：0.232420
false_merge_rate：0.022946
```

本轮优化后模型：

```text
prediction_mode：full_iad_risk
full_risk_trained：true
test F1：0.604915
precision：0.836601
recall：0.473723
false_merge_rate：0.092524
bootstrap F1 95% CI：0.579993 - 0.629519
bootstrap false_merge_rate 95% CI：0.077800 - 0.108619
```

强基线：

```text
SciNCL cosine source-heldout best F1：0.714436
SciNCL false_merge_rate：0.354552

RoBERTa pair classifier source-heldout F1：0.663194
RoBERTa false_merge_rate：0.424870
```

模型优势审计：

```text
vs RoBERTa：same_work_f1_delta = -0.276210，false_merge_rate_reduction = 0.332346，status = not_supported
vs SciNCL：same_work_f1_delta = -0.327452，false_merge_rate_reduction = 0.262028，status = not_supported
overall_superiority_status：not_supported
sota_claim_allowed：false
```

## 当前审稿结论

当前结果说明：

```text
1. 引入 agenda_non_identity 训练信号后，F1 和召回明显提升；
2. IAD-Risk 能降低 false_merge_rate；
3. 但 same_work F1 仍未超过 SciNCL / RoBERTa 强基线；
4. 当前不能声称 SOTA；
5. 当前不能声称达到二区或 B 类期刊要求。
```

Q2/B 门控：

```text
q2b_acceptance_ready：false
blocked_gate_count：8 / 9
claim_gate_status：blocked
primary_track_superiority_evaluator：failed_protocol_threshold
overall_innovation_depth_status：blocked
q2_b_innovation_claim_allowed：false
```

## 希望 GPT Pro 分析的问题

请重点回答以下问题，只给研究思路和论证，不给代码实现：

```text
1. 当前 IAD-Risk 是否值得继续作为主方法？
2. 是否应该改成“强模型实体匹配 + 风险校准层”的框架？
3. 如何在不人工标注的前提下构造更强 hard-negative test set？
4. 如何让创新点从 frozen encoder + 阈值校准升级为真正的方法创新？
5. 是否应引入 cross-encoder、contrastive learning、multi-task loss、uncertainty calibration、conformal prediction？
6. 如何同时提高 same_work F1 并保留 false_merge_rate 优势？
7. 如果目标是二区 / B 类，最低需要补齐哪些实验闭环？
8. 如果完全推翻现有方向，最有潜力的新课题核心是什么？
9. 当前论文主张应该如何收缩，避免被审稿人认为夸大？
10. 哪些相关工作最可能被审稿人拿来质疑创新性？
```

## 希望输出格式

请按以下结构输出：

```text
1. 对当前课题价值的判断
2. 对当前方法创新性的批判
3. 最推荐的重构方向
4. 可保留的已有工作
5. 应放弃或弱化的部分
6. 无人工标注阶段可做的实验设计
7. 达到二区 / B 类前必须补齐的证据
8. 建议的新题目名称
9. 建议的论文主张边界
10. 给 Codex 后续执行的高层任务清单
```

注意：第 10 点只需要高层任务，不需要具体代码路径、函数、命令或实现细节。

## 当前建议倾向

当前更合理的方向可能不是继续强调 `IAD-Risk Transformer` 本身，而是重构为：

```text
Risk-Calibrated Scientific Entity Matching
```

潜在框架：

```text
Stage 1：SciNCL / SPECTER2 bi-encoder 召回候选
Stage 2：cross-encoder 判定 same_work
Stage 3：agenda-aware hard-negative detector 识别同议题非同文
Stage 4：uncertainty / conformal calibration 输出安全合并、拒绝合并、需人工复核三态决策
Stage 5：source-heldout、topic-heldout、provenance-blind 评估防止数据来源捷径
```

请判断这个方向是否比当前方法更有论文价值。
