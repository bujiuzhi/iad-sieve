# 重构优化课题方案

## 问题拆解

2026-06-16 课题主线已再次收缩：最新方向是 **Risk-Calibrated Scientific Entity Matching under Agenda-Level Confounders**。本文件中关于 `IAD-Risk` 的方案保留为历史执行基础；当前论文主方法不再命名为 `IAD-Risk Transformer`，而是风险约束安全合并框架。最新项目级审计见：

```text
docs/risk-calibrated-topic-restructure.md
```

当前课题不应继续表述为“改进去重规则”或“IAD-Sieve++”。更稳妥的重构方式是把研究对象拆成两个互补问题：

```text
身份判定：两条记录是不是同一篇 scholarly work
风险控制：同议题但非同一篇文献时，如何避免误合并
```

前者需要公开 gold 数据支撑，后者需要 hard negative 数据支撑。人工标注暂缓后，课题应优先使用公开 gold 与公开 silver 构造可复现实验链路，把人工 gold 作为后续增强。

## 关键结论

建议课题核心重构为：

```text
IAD-Risk：面向科研文献身份-议题解耦的误合并风险学习框架
IAD-Bench-Open：公开数据驱动的 provenance-aware 评估基准
IAD-Bench-Open-v3-Balanced-Gold：公开 gold 的来源内正负平衡评估子集
```

不建议首次发布使用 `++` 命名。`IAD-Risk` 比 `IAD-Sieve++` 更适合论文，因为它强调研究问题和模型目标，而不是工程迭代版本。

## 架构方案

### A 轨：公开 gold 身份判定

目标：

```text
证明 same_work / unrelated 的身份判定能力
排除 label_source shortcut
支持 source-held-out 泛化评估
```

当前已完成：

```text
full open_v3：
  documents = 17,489
  pairs = 40,582
  gold_pair_count = 40,582
  same_work_pair_count = 6,745
  unrelated_pair_count = 33,837
  label_source_count = 3

balanced gold：
  documents = 13,404
  pairs = 13,396
  same_work_pair_count = 6,698
  unrelated_pair_count = 6,698
  label_source_count = 3

scholarly-only balanced gold：
  documents = 10,797
  pairs = 11,062
  same_work_pair_count = 5,531
  unrelated_pair_count = 5,531
  label_source_count = 2
  include_label_sources = deepmatcher_dblp_scholar, deepmatcher_py_entitymatching_dblp_acm
```

balanced gold 的审计结果：

```text
overall_source_bias_status = defensible
max_source_shortcut_accuracy = 0.5
overall_provenance_balance_status = defensible
overall_stratification_status = defensible
source_held_out_split = ready
heldout_source_diversity = defensible
pair_leakage_guard = defensible
```

审稿价值：

```text
scholarly-only balanced gold 可作为科研文献身份判定主评估；
原 balanced gold 可回应“baseline 是否只学到数据来源”的质疑；
可以回应“正负样本是否严重不平衡”的质疑；
强模型结果表必须把 scholarly-only 主评估和 cross-domain balanced 防御评估分开报告。
```

当前 scholarly-only 审计边界：

```text
overall_source_bias_status = defensible
overall_provenance_balance_status = high_risk
max_dominant_source_ratio = 0.966733
source-held-out same_work / unrelated = limited_source_heldout_coverage
agenda_non_identity source-held-out = blocked_missing_relation
source_heldout_full_iad_data_ready = false
```

COCI source patch 已补齐后续 limited source-heldout 证据：

```text
openalex_opencitations_source_registry/T10009 pair_count = 2,500
coci_T10009 valid DOI-to-DOI citation edges = 13,252
iad_bench_open_v3_coci_source_patch pairs = 45,582
source_heldout_full_iad_data_ready = true
iad_risk_split_evaluation_status = source_heldout_full_iad_limited_ready
test agenda_non_identity_f1 = 0.948917
test same_work_f1 = 0.086066
test false_merge_rate = 0.000154
```

该 patch 解决的是 `agenda_non_identity` 第二公开来源与 source-heldout 覆盖缺口；它仍是 silver 证据，不能写成人工 gold、主方法整体优越或 SOTA。

### B 轨：IAD hard negative 风险控制

目标：

```text
证明同议题非同身份 pair 不会被误合并
证明双空间/风险头优于单空间语义相似度
```

当前已有基础：

```text
OpenAlex/OpenCitations agenda_non_identity silver hard negative
SciNCL / RoBERTa / DistilBERT / Transformer baseline 链路
IAD-Risk lightweight 与 Transformer 训练入口
mechanism_error_evidence 机制解释产物
```

当前限制：

```text
balanced gold 不包含 agenda_non_identity；
OpenAlex hard negative 仍是 silver，不是人工 gold；
multi-topic silver patch 已让 topic-held-out 可执行；
source-held-out hard-negative 覆盖、强模型与远程复现仍 blocked；
不能把 silver topic-held-out 写成整体模型优越或人工 gold 结论。
```

下一步增强：

```text
补齐 30 个以上 OpenAlex topic；
每个 topic 采集 1,000-2,000 works；
构造 50,000+ agenda_non_identity silver hard negative；
保留 topic-held-out split；
人工标注协调完成后抽样 500-1,000 pair 做 human audit。
```

## 原理方案

IAD-Risk 的核心不是单纯提高 F1，而是分离两个空间：

```text
identity_space：判断是否同一篇文献
agenda_space：判断是否同一研究议题
false_merge_risk：当 agenda 相近但 identity 不充分时阻止合并
```

生活类比：

```text
两个人都在同一个医院看同一种病，不代表他们是同一个人。
两篇论文都研究 BERT 检索，不代表它们是同一篇论文。
```

模型优化方向：

```text
输入：文献 pair 的标题、作者、年份、venue、identifier、topic、reference、embedding
输出：p_same_work、p_same_agenda、p_agenda_non_identity、p_false_merge_risk
训练：gold 身份标签 + silver hard negative + provenance-blind 特征约束
评估：full open_v3、balanced gold、source-held-out、OpenAlex hard negative、topic-held-out
```

## 工程方案

已新增和建议保留的核心产物：

```text
src/iad_sieve/evaluation/iad_bench_balanced_subset.py
outputs/iad_bench_open_v3/
outputs/iad_bench_open_v3_balanced_gold/
outputs/iad_bench_source_bias_diagnostic_open_v3_balanced_gold/
outputs/iad_bench_provenance_balance_plan_open_v3_balanced_gold/
outputs/open_v3_heldout_split_plan_balanced_gold/
```

新增命令：

```bash
python -m iad_sieve.cli build-iad-bench-balanced-subset \
  --documents outputs/iad_bench_open_v3/iad_bench_documents.jsonl \
  --pairs outputs/iad_bench_open_v3/iad_bench_pairs.jsonl \
  --output-dir outputs/iad_bench_open_v3_balanced_gold \
  --relation-labels same_work,unrelated \
  --seed 7
```

建议实验顺序：

```text
1. 在 balanced gold 上跑 SciNCL / SPECTER2 / RoBERTa / DistilBERT / LLM pair judge。
2. 在 balanced gold 上训练 provenance-blind IAD-Risk identity head。
3. 使用 source-held-out assignment 做跨公开来源测试。
4. 在 OpenAlex hard negative 上测试 false_merge_risk。
5. 扩展 OpenAlex 多 topic 后再做 topic-held-out。
6. 最后接入人工 audit，不作为当前阻塞项。
```

当前工程落地状态：

```text
experiment_queue：44 个任务
experiment_preflight：44 个任务已进入本地预检
experiment_dependency：44 个任务已生成依赖关系
balanced gold 与 scholarly-only gold 新增任务：SciNCL baseline、RoBERTa pair baseline、IAD-Risk Transformer、对应 evaluate/bootstrap
source-held-out 新增任务：派生 pair 文件、SciNCL baseline、RoBERTa pair baseline、IAD-Risk Transformer、test-only evaluate
remote_output_validation：total_output_count = 172，valid_output_count = 162，missing_output_count = 10
remote_result_acceptance：task_count = 44，accepted_task_count = 38，blocked_task_count = 6，gate_count = 7，accepted_gate_count = 5，blocked_gate_count = 2，missing_output_count = 10，all_claim_gates_accepted = false；Ditto-style EM 与多数 open_v3 scholarly source-heldout 强 baseline 已接收，剩余未接收项收敛为 GPT/LLM judge 输出
remote_environment_audit：check_count = 4，ready_count = 0，missing_count = 4；该本地重建产物仅检查 Python 模块默认项，不再把 OpenAI API key 作为默认前置条件；远程真实可运行性以 remote_preflight.template.sh 和目标 conda 环境为准
remote_execution_blueprint：blueprint_item_count = 6，environment_missing_count = 4，root_task_count = 2，root_task_blocked_count = 2，missing_output_count = 4
remote_connection_pack：item_count = 15，missing_required_field_count = 0，blocked_secret_count = 0，model_artifact_count = 1，missing_model_artifact_count = 1，stage_command_count = 4，script_template_count = 3，all_remote_run_inputs_ready = false；已生成 remote_connection_profile.template.json、remote_preflight.template.sh、remote_sync_and_run.template.sh、remote_pull_outputs.template.sh、remote_execution_runbook.md；profile 仅允许保存连接字段、remote_conda_path 和 configured_secrets 变量名，拒绝明文密钥、password、token、私钥内容或 sk- 风格密钥值；remote_preflight.template.sh 与 remote_sync_and_run.template.sh 会检查 outputs/models/local_llm_judge 是否已预置
remote_input_request：request_count = 8，missing_connection_field_count = 0，blocked_secret_configuration_count = 0，deferred_secret_configuration_count = 0，missing_model_artifact_count = 1，primary_track_ready_to_execute_remote_stages = false，global_ready_to_execute_all_remote_stages = false；连接字段已齐备，当前外部输入仅剩 outputs/models/local_llm_judge 本地 Transformers LLM 权重目录
remote_execution_slice：slice_count = 4，track_slice_count = 2，blocked_slice_count = 4，ready_slice_count = 0，remote_input_blocked = true，primary_track = open_v3_scholarly_balanced_gold_source_heldout，primary_track_task_count = 1，primary_track_missing_output_count = 2，unmapped_track_slice_count = 0，q2b_remote_execution_slice_ready = false；该切片不再要求重复运行已验收的 open_v3 SciNCL/RoBERTa/SPECTER2/Ditto root task，当前主轨道阻塞是 outputs/models/local_llm_judge 未预置与 GPT/LLM judge 两个原始输出未回传
remote_slice_run_pack：slice_script_count = 3，slice_task_command_count = 3，blocked_script_count = 0，primary_track = open_v3_scholarly_balanced_gold_source_heldout，primary_track_command_count = 1，primary_track_required_secret_count = 0，q2b_remote_slice_run_pack_ready = true；已生成主轨道模板 run_remote_slice_open_v3_scholarly_balanced_gold_source_heldout.template.sh，运行前必须先预置 outputs/models/local_llm_judge
primary_remote_readiness：primary_track = open_v3_scholarly_balanced_gold_source_heldout，readiness_status = blocked_missing_model_artifact，missing_connection_field_count = 0，missing_primary_secret_count = 0，missing_model_artifact_count = 1，deferred_global_secret_count = 0，primary_remote_ready = false；主轨道连接字段已齐备，真实阻塞是 outputs/models/local_llm_judge 尚未在远程项目目录预置
primary_remote_handoff：primary_track = open_v3_scholarly_balanced_gold_source_heldout，handoff_status = waiting_for_model_artifact，connection_field_count = 0，primary_task_count = 1，missing_primary_secret_count = 0，missing_model_artifact_count = 1，post_run_validation_step_count = 27；交接包固定主轨道本地 Transformers LLM judge 执行、回传派生产物、run_primary_post_run_validation.sh 和回传验收命令，模型目录未预置前不得写入 GPT/LLM judge 结果
primary_track_claim_gate：primary_track = open_v3_scholarly_balanced_gold_source_heldout，claim_gate_status = blocked，claim_allowed = false，blocking_reason_count = 6，connection_field_count = 0，ready_model_count = 4，missing_required_system_count = 1，reviewer_risk = high；该门禁把主轨道远程交接、advanced_model_evidence_track_summary、model_superiority_audit、innovation_depth_stress_test 和 q2b_acceptance_rubric 汇总成论文主张锁，当前不得写 SOTA、强模型闭环、跨来源泛化完成或二区/B 类完成
primary_track_superiority_protocol：primary_track = open_v3_scholarly_balanced_gold，protocol_status = blocked_waiting_for_primary_models，required_system_count = 3，required_comparison_count = 2，minimum_f1_delta = 0.0，minimum_false_merge_reduction = 0.02，minimum_hard_negative_reduction = 0.05，requires_bootstrap_ci = true，claim_allowed_after_protocol = false；该协议把 IAD-Risk Transformer vs SciNCL、IAD-Risk Transformer vs RoBERTa pair 的优势判定预注册为效果量 + bootstrap 95% CI 规则，避免远程结果回传后选择性报告或只凭均值提升写先进性
primary_track_superiority_evaluator：primary_track = open_v3_scholarly_balanced_gold，evaluation_status = blocked_missing_primary_metrics，claim_allowed_by_evaluator = false，passed_comparison_count = 0，blocked_comparison_count = 2，failed_comparison_count = 0；该判定器把预注册协议落实为实际 pass/fail 证据，远程 metric summary 与 bootstrap CSV 缺失或字段不全时自动 blocked，避免把“协议已设计”误写成“模型优势已证明”
no_annotation_protocol：protocol_item_count = 5，blocked_annotation_count = 0，blocked_remote_count = 1，claim_lockdown_count = 1，high_reviewer_risk_count = 2，human_annotation_required_now = false，no_annotation_stage_allowed = true，q2_b_ready_under_no_annotation_strategy = false；该协议明确当前可以不依赖新增人工标注继续推进，但不得声称已有人工 gold、强模型闭环、SOTA 或二区/B 类完成
q2b_acceptance_rubric：gate_count = 9，ready_gate_count = 1，blocked_gate_count = 8，highest_priority_blocker = remote_reproducibility_acceptance，q2b_acceptance_ready = false；该 rubric 把远程复现、强模型矩阵、模型优势、创新深度、创新可证伪闭环、相关工作新颖性边界、无人工标注策略和主张锁定转成最终接收判定门槛，当前仅 no_annotation_strategy_acceptance ready
q2b_experiment_optimizer：experiment_count = 7，blocked_external_input_count = 1，blocked_remote_execution_count = 6，ready_for_local_review_count = 0，highest_priority_experiment = exp_remote_reproducibility_acceptance，primary_track = open_v3_scholarly_balanced_gold_source_heldout，primary_track_required_secret_count = 0，deferred_global_secret_count = 0，primary_track_can_start_without_deferred_secrets = true，q2b_experiment_plan_ready = false；该优化器把 Q2/B blocked gate、审稿人批判、远程输入请求、远程执行切片和高级模型轨道摘要合并为下一轮实验动作，当前最高优先级是预置 outputs/models/local_llm_judge、运行本地 Transformers LLM judge 主轨道并回传验收产物
novelty_falsification_matrix：contribution_count = 5，ready_contribution_count = 4，conditional_contribution_count = 1，blocked_contribution_count = 0，highest_priority_blocker = 空，q2b_novelty_defensible = false；该矩阵把每个创新点映射为审稿人零假设、最近似已有工作家族、证伪实验、必需控制和论文边界，当前未关闭项收敛为 strong_model_superiority_control 的条件性证据；在 LLM judge 与强 baseline 优势未闭环前，不能声称完整创新可证伪闭环
prior_art_novelty_audit：prior_art_family_count = 5，ready_prior_art_family_count = 3，conditional_prior_art_family_count = 1，blocked_prior_art_family_count = 1，unresolved_high_risk_family_count = 1，duplicate_work_found = false，highest_priority_blocker = llm_entity_matching，q2b_prior_art_position_defensible = false；该审计把相似工作和更先进工作风险转成可执行门槛，当前高风险未解决家族已收敛为 LLM entity matching；不得声称没有相似工作，也不得声称新颖性边界已经完全闭环
q2b_action_board：action_count = 22，high_risk_action_count = 14，blocked_action_count = 14，remote_handoff_template_count = 3，advanced_track_gap_count = 2，unmapped_advanced_track_gap_count = 0，external_input_count = 2，remote_root_task_count = 2，q2_b_ready = false；evaluation_track 级强模型阻塞动作已映射到 remote_execution_blueprint 的 root_task、missing_outputs 和 execution_stage，最高优先级缺口收敛为 GPT/LLM judge 的本地模型目录与缺失输出
q2b_upgrade_roadmap：phase_count = 6，blocked_phase_count = 4，conditional_phase_count = 0，deferred_phase_count = 1，highest_priority_blocker = p0_remote_connection_and_secret，human_annotation_required_now = false，q2_b_ready = false；该路线图把“先补远程模型工件、再跑强模型、再锁定论文主张”固化为可验收阶段
reviewer_iteration_audit：review_item_count = 7，critical_count = 3，major_revision_required_count = 7，minor_revision_required_count = 0，defensible_count = 0，highest_risk_iteration_id = r0_remote_reproducibility，q2_b_ready_from_reviewer_view = false；该审核从审稿人角度批判远程可复现性、强 baseline、创新深度、模型泄漏、数据可信度、泛化与论文主张安全，并给出下一轮优化动作
reviewer_response_matrix：response_count = 12，ready_to_answer_count = 4，limited_answer_count = 4，do_not_answer_as_claim_count = 4，must_not_claim_count = 6；duplicate_work 已接入 prior_art_novelty_audit，当前只能写“未发现直接重复工作且相邻高风险工作仍需闭环”，不能写“没有相似工作”；baseline_strength、executed_strong_baselines 和 venue_readiness 仍不能写成论文主张
q2b_completion_audit：criterion_count = 12，ready_count = 4，conditional_count = 0，blocked_count = 8，overall_completion_status = blocked，q2_b_goal_ready = false；COCI source-heldout 数据覆盖与 limited split evaluation 已 ready，但远程结果验收、GPT/LLM judge、强模型矩阵、主轨道优势和创新深度仍 blocked；remote_model_artifact、remote_result_acceptance_closure 未 ready 前不得写强模型证据闭环；innovation_depth_closure 未 ready 前不得写二区/B类创新深度已满足
q2b_external_blocker_audit：blocker_count = 6，external_secret_count = 0，external_model_artifact_count = 1，advanced_missing_count = 2，claim_lock_count = 1，missing_output_count = 10，highest_priority_blocker = external_model_artifact:outputs/models/local_llm_judge，q2b_blocked_by_external_inputs = true；该合同用于下一轮预置本地 LLM 权重、运行 GPT/LLM judge、回传输出和重建验收链
iad_source_heldout_gap_plan：OpenAlex topic T10009 + OpenCitations COCI 缺口已闭合，`data/raw/opencitations/coci_T10009.csv` 含 13,252 条有效 DOI-to-DOI 引用边，`outputs/openalex_opencitations_source_registry/T10009/` 生成 2,500 对 silver hard negative，且 `require_opencitations=true`；该证据不能写成新增 gold、完整 SOTA 泛化或 provider-level source bias 已完全排除
OpenAlex-only gap patch：已下载 OpenAlex topic T10009 Works 5,000 条，生成 OpenAlex-only silver hard negative 2,500 对；合并后的临时 IAD-Bench documents = 19,306，pairs = 43,082，agenda_non_identity_pair_count = 2,500。该 patch 只证明 OpenAlex-only 数据链路可执行，不能替代 OpenCitations COCI 或人工 gold
strict source-held-out coverage guard：iad_source_heldout_coverage_audit 已要求输入 pair 显式包含 evaluation_split_strategy = source_held_out，且同一 relation 的 train/test label_source 不相交；OpenAlex-only patch 的 random split 被标记为 blocked_not_source_heldout_split，单来源伪 source-heldout 会被标记为 blocked_source_overlap。该修正确保普通 random/topic split 或单来源切分不会被误写成 source-held-out 泛化
OpenAlex+COCI source patch：`outputs/openalex_opencitations_source_registry/T10009/` 为 document_count = 240、pair_count = 2,500、citation_edge_count = 13,252；合并后的 `outputs/iad_bench_open_v3_coci_source_patch/` 为 documents = 19,546、pairs = 45,582、agenda_non_identity_pair_count = 5,000；source-heldout assignment 覆盖 train_pair_count = 31,207、test_pair_count = 14,375
iad_source_heldout_coverage_audit_coci_source_patch：relation_count = 3，ready_relation_count = 3，blocked_relation_count = 0，source_heldout_full_iad_data_ready = true；该审计同时校验 evaluation_split_strategy 与 train/test label_source 不相交
iad_risk_split_evaluation_audit_coci_source_patch_source_heldout：overall_split_evaluation_status = source_heldout_full_iad_limited_ready，limited_source_heldout_count = 1，test agenda_non_identity_f1 = 0.948917，test same_work_f1 = 0.086066，test false_merge_rate = 0.000154；该结果只能写 limited 风险控制，不支持主方法整体优越
iad_bench_source_acquisition_audit：OpenCitations COCI 候选已新增有效 DOI-to-DOI 边验收；当前 overall_acquisition_status = ready，ready_to_convert_count = 5，missing_raw_file_count = 0，invalid_raw_file_count = 0。后续即使文件存在，valid_citation_edge_count 必须大于 0 才能进入 ready_to_convert
OpenAlex-only patch reviewer audit：public_data_validity_audit 的 silver_topic_concentration = high_risk；open_v3_plan_audit 的 document_scale、silver_pair_scale、silver_topic_diversity 仍 blocked；open_v3_heldout_split_plan assignment_count = 0；source_bias_diagnostic overall_source_bias_status = high_risk，max_eval_accuracy = 0.845538；provenance_balance_plan overall_provenance_balance_status = blocked
OpenAlex multi-topic silver patch：已下载 OpenAlex 2024 article Works 3,000 条，生成 document_count = 2,103、agenda_non_identity_pair_count = 6,820、topic_count = 344、top_silver_topic_ratio = 0.043988 的公开 silver hard negative；合并后 IAD-Bench documents = 19,592，pairs = 47,402，silver_pair_count = 6,820，gold_pair_count = 40,582。public_data_validity_audit 的 silver_topic_concentration = defensible，open_v3_plan_audit 的 silver_topic_diversity = defensible，open_v3_heldout_split_plan 的 topic_held_out_split = ready，heldout_topic_count = 69，assignment_count = 6,820；但 source_held_out_split 仍 blocked，source_bias_diagnostic overall_source_bias_status = high_risk，max_eval_accuracy = 0.859614，provenance_balance_plan overall_provenance_balance_status = blocked
topic-heldout lightweight IAD-Risk：已在 scored multi-topic patch 上执行 topic_held_out 训练/测试，test eval_pair_count = 5,580，agenda_non_identity_f1 = 0.929355，false_merge_rate = 0.004677，但 same_work_f1 = 0.337756。该结果只能写成 silver hard-negative 风险控制证据，不能写成 full IAD 模型优越证据
submission_gate_audit：source_bias_gate = ready，provenance_balance_gate = ready，remote_result_acceptance_gate = blocked，remote_connection_gate = blocked，overall_submission_gate = blocked
advanced_model_evidence：evidence_count = 23，ready_actual_model_count = 20，ready_api_model_count = 0，ready_llm_model_count = 0，ready_model_count = 20，missing_required_count = 2，evaluation_track_count = 5，blocked_evaluation_track_count = 2，highest_priority_missing_track = open_v3_scholarly_balanced_gold_source_heldout
model_innovation_blueprint：blueprint_count = 7，ready_count = 5，conditional_count = 1，blocked_count = 1，deferred_count = 0，overall_model_innovation_status = blocked；机制对比、source-heldout 泛化、SPECTER2 encoder 稳定性和 Ditto-style EM 强 baseline 已 ready；LLM actual_model 仍不能写成已完成创新
model_superiority_audit：comparison_count = 9，blocked_missing_comparison_count = 1，overall_superiority_status = blocked，sota_claim_allowed = false；阻塞项是主轨道 GPT/LLM judge 缺失，不能把 open_v2 的有限优势写成最终主轨道先进性
innovation_depth_stress_test：stress_count = 6，ready_count = 4，blocked_count = 2，overall_innovation_depth_status = blocked，q2_b_innovation_claim_allowed = false；当前机制解释已经由 mechanism_triangulation_audit 的 cross_system_mechanism_evidence 和 mechanism_triangulation_sensitivity 的 threshold_stable_cross_system_evidence 联合支撑，source-heldout 泛化维度已 ready，剩余阻塞集中在强 baseline 比较与最终整体创新深度门禁
mechanism_triangulation_audit：system_count = 2，false_merge_pair_count = 1075，cross_system_failure_pair_count = 1，single_system_failure_pair_count = 1074，unresolved_pair_count = 0，triangulation_status = cross_system_mechanism_evidence；该审计能支撑跨 baseline 共同失败存在性，但共同失败样本少，论文表述需限定为机制深度补强证据
mechanism_triangulation_sensitivity：setting_count = 25，ready_setting_count = 13，cross_system_setting_count = 13，max_cross_system_failure_pair_count = 46，threshold_stability_status = threshold_stable_cross_system_evidence；该审计说明共同失败并非只在固定阈值 0.8 出现，但高 RoBERTa 阈值缺少 cross-system signal，论文需限定阈值区间
mechanism_case_pack：case_count = 3，cross_system_case_count = 1，single_system_case_count = 2，unresolved_case_count = 0，case_pack_status = paper_ready_limited_case_pack；该产物把三角验证证据转成可写入错误分析章节的代表性案例，但不能替代统计检验或强模型闭环
topic_package_final：manifest rows = 868；已纳入 q2b_upgrade_roadmap_fixture、reviewer_iteration_audit_fixture、remote_input_request_fixture、remote_execution_slice_fixture、remote_slice_run_pack_fixture、primary_remote_readiness_fixture、primary_remote_handoff_fixture、primary_track_claim_gate_fixture、primary_track_superiority_protocol_fixture、primary_track_superiority_evaluator_fixture、no_annotation_protocol_fixture、q2b_acceptance_rubric_fixture、q2b_experiment_optimizer_fixture、q2b_external_blocker_audit_fixture、novelty_falsification_matrix_fixture、prior_art_novelty_audit_fixture、advanced_model_evidence_track_summary、iad_source_heldout_coverage_audit_open_v3_balanced_gold、iad_source_heldout_coverage_audit_open_v3_scholarly_balanced_gold、iad_source_heldout_gap_plan_open_v3_balanced_gold、scholarly-only balanced gold、OpenAlex-only gap patch、OpenAlex multi-topic silver patch 和 COCI source patch 审计产物；继续排除旧的 iad_training_input_audit_source_heldout 和历史 superpowers spec/plan 文档，避免把早期执行计划误写成当前审稿证据
```

source-held-out 当前边界：

```text
source_held_out_split = ready
source-held-out assignment_count = 13,396
source-held-out train_pair_count = 10,694
source-held-out test_pair_count = 2,702
heldout_source_count = 2
heldout_key_count = 2
heldout_source_diversity = defensible
```

含义：当前可做多来源 source-held-out 复核，但不能替代 topic-held-out 或 OpenAlex hard-negative 跨 topic 结论。

当前缺失的主要课题包目录均属于待远程/API 执行产物：

```text
outputs/strong_baseline_open_v3_balanced_gold
outputs/strong_baseline_open_v3_balanced_gold_source_heldout
outputs/iad_risk_transformer_scincl_provenance_blind_open_v2
outputs/iad_risk_transformer_specter2_open_v2
outputs/iad_risk_transformer_scincl_open_v3_balanced_gold
outputs/iad_risk_transformer_scincl_open_v3_balanced_gold_source_heldout
outputs/iad_bootstrap_open_v3_balanced_gold
```

## 审稿人视角风险

当前可以防住的质疑：

```text
公开 gold 规模过小：已从 415 pair 提升到 40,582 full gold pair。
正负样本严重不平衡：balanced gold 提供 6,698 / 6,698 平衡评估。
来源字段捷径：balanced gold 的来源捷径准确率为 0.5。
领域边界不清：新增 scholarly-only balanced gold，避免把 Amazon-Google 混写成科研文献主评估。
来源泛化不足：source-held-out split 已 ready，且 held-out test 覆盖 2 个公开来源；后续主要风险转为跨 topic 泛化不足。
hard negative 数据链路不可执行：OpenAlex-only patch 已完成 5,000 Works 拉取和 2,500 对 silver hard negative 生成。
single-topic hard negative 过度集中：multi-topic patch 已覆盖 344 个 OpenAlex topic，top topic ratio = 0.043988，并生成 69 个 held-out topic。
```

当前仍防不住的质疑：

```text
没有人工 gold：只能写公开 gold / silver，不能写人工标注结论。
跨 topic 泛化仍是 silver 证据：topic-held-out 已可执行，但不是人工 gold，也未接入强模型闭环。
hard negative 不是 gold：OpenAlex/OpenCitations 只能作为 silver。
OpenAlex 来源偏置：multi-topic patch 仍是单一 OpenAlex provider，source bias 诊断 high risk，不能替代 COCI 或 source-held-out。
scholarly-only provenance 不平衡：DBLP-Scholar 占比 0.966733，只能作为领域主评估，不能单独防御来源分布质疑。
强模型结果未全部补齐：SPECTER2、LLM API、provenance-blind Transformer 仍需远程/API 执行。
```

## 二区或 B 类判断

不能保证一定达到二区或 B 类。按审稿标准判断，当前重构后已经具备一篇论文的可辩护骨架，但还不建议直接投稿。

投稿前最低完成条件：

```text
balanced gold 上完成强 baseline 对比；
source-held-out 上完成 IAD-Risk 与强 baseline 对比；
OpenAlex 多 topic hard negative 完成 topic-held-out；
provenance-blind Transformer 重训完成；
统计显著性和错误分析完成；
论文中明确 human audit 是 deferred enhancement。
```
