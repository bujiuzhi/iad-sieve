# 远程开发配置

## 问题拆解

远程服务器用于 GPU 实验和大样本批处理。仓库不得保存服务器 IP、SSH key、Kaggle token 或任何凭据。

## 结论

远程目录使用 `~/work/code/python/iad-sieve`。首次部署需要同步源码、文档、测试、脚本和执行阶段依赖的 `outputs/` 计划产物；不得同步远程连接 profile、本地凭据、缓存或最终课题包。

## 需要提供的连接信息

仓库内未保存可用远程连接方式。执行 open_v3 scholarly 主轨道强模型前，需要通过安全渠道临时提供以下连接字段；这些信息不得提交到仓库或写入课题包：

```text
remote_host
remote_port
remote_user
ssh_key_path
remote_workspace
conda_env
```

`outputs/primary_remote_readiness_fixture/primary_remote_readiness.md` 已把主轨道阻塞收敛为上述 6 个连接字段；open_v3 scholarly 主轨道不需要 `OPENAI_API_KEY`。`OPENAI_API_KEY` 只用于后续 open_v2 LLM pair judge baseline，不用于生成 gold label；论文中必须写为 `api_model baseline`，不能写成人工标注来源。

如果后续要运行 open_v2 LLM 轨道，只需要确认远程环境已安全配置 `OPENAI_API_KEY` 变量名，不要把密钥值写入聊天、profile、仓库或课题包。

## 交接模板

生成远程连接准备包后，会同时输出三个 shell 模板和一份人工交接手册：

```text
outputs/remote_connection_pack_fixture/remote_preflight.template.sh
outputs/remote_connection_pack_fixture/remote_sync_and_run.template.sh
outputs/remote_connection_pack_fixture/remote_pull_outputs.template.sh
outputs/remote_connection_pack_fixture/remote_execution_runbook.md
outputs/remote_slice_run_pack_fixture/run_remote_slice_open_v3_scholarly_balanced_gold.template.sh
outputs/primary_remote_handoff_fixture/primary_remote_handoff.md
outputs/primary_track_claim_gate_fixture/primary_track_claim_gate.md
outputs/primary_track_superiority_protocol_fixture/primary_track_superiority_protocol.md
outputs/primary_track_superiority_evaluator_fixture/primary_track_superiority_evaluator.md
```

连接信息到位后，先用本地命令生成 profile；该文件只保存在本地，不进入课题包，不同步到远程：

```bash
python -m iad_sieve.cli build-remote-connection-profile \
  --remote-host "<remote_host>" \
  --remote-port "<remote_port>" \
  --remote-user "<remote_user>" \
  --ssh-key-path "<ssh_key_path>" \
  --remote-workspace "<remote_workspace>" \
  --conda-env "<conda_env>" \
  --remote-conda-path "<remote_conda_path>" \
  --configured-secret OPENAI_API_KEY \
  --output-path outputs/remote_connection_profile.local.json
```

`--remote-conda-path` 用于远程默认 PATH 找不到 `conda` 但已有显式 conda 可执行文件路径的情况；为空时模板回退到 `conda`。`--configured-secret OPENAI_API_KEY` 只表示远程环境已安全配置该变量名，不要传入 `OPENAI_API_KEY` 的值。若暂不运行 LLM pair judge，可先不写 `--configured-secret`。

`remote_preflight.template.sh` 只验证 SSH、conda、CUDA、`sentence_transformers`、`torch`、`transformers`、`adapters` 和可选 API 环境，不启动实验。`remote_sync_and_run.template.sh` 用本地环境变量或 `remote_connection.env` 占位文件读取连接字段，先创建远程目录，再通过 `rsync` 同步项目，随后通过 `REMOTE_CONDA_PATH` / `REMOTE_CONDA_COMMAND` 在远程 conda 环境中检查 CUDA、Python 模块和可选 API 环境，通过后再依次执行 `run_stage_*.sh`。`remote_pull_outputs.template.sh` 将远程 `outputs/` 拉回本地，运行 `validate-remote-outputs`、`build-remote-result-acceptance`，并触发 `run_stage_03.sh` 重建审稿证据包与 Q2/B 判定材料。三个模板均不保存远程地址、私钥路径或 API 密钥值。
优先执行 `outputs/remote_slice_run_pack_fixture/run_remote_slice_open_v3_scholarly_balanced_gold_source_heldout.template.sh`。该脚本当前只运行 GPT judge source-heldout 主轨道任务，运行前必须确认远程环境已安全配置 `OPENAI_API_KEY`。全量 `remote_sync_and_run.template.sh` 适合所有远程字段和 API 配置都齐全后的完整复跑。
`outputs/primary_remote_handoff_fixture/primary_remote_handoff.md` 是主轨道最小交接入口，集中列出主轨道脚本、1 个 GPT judge 任务、回传派生产物和 27 步回传验收命令。远程结果拉回后，优先运行 `outputs/primary_remote_handoff_fixture/run_primary_post_run_validation.sh`，该脚本会继续生成 GPT judge metric summary、bootstrap、advanced_model_evidence、model_superiority_audit、Q2/B 接收门禁、主轨道优势判定器和下一轮实验优化器。
`outputs/primary_track_claim_gate_fixture/primary_track_claim_gate.md` 是主轨道论文主张门禁。远程结果回传并重建前，该文件会保持 blocked，禁止把主轨道强模型、SOTA、跨来源泛化或二区/B 类完成写成论文结论。
`outputs/primary_track_superiority_protocol_fixture/primary_track_superiority_protocol.md` 是主轨道优势判定协议。远程结果回传后，需要按该协议同时检查 same_work F1、不良合并率、hard-negative 不良合并率和 bootstrap 95% CI，不能只凭均值提升写模型先进性。
`outputs/primary_track_superiority_evaluator_fixture/primary_track_superiority_evaluator.md` 是主轨道实际优势判定器。它会读取协议、主轨道 metric summary 和 bootstrap CSV，只有两组比较均 passed 时才允许写主轨道模型优势；当前缺少远程指标，因此保持 `blocked_missing_primary_metrics`。
`remote_connection.env` 只允许作为本地 shell 输入文件使用，`remote_sync_and_run.template.sh` 会在 `rsync` 时排除 `remote_connection.env`、`remote_connection.env.*` 和 `outputs/remote_connection_profile.local.json`，避免把连接字段或本机私钥路径同步到远程项目目录。
`remote_execution_runbook.md` 用于人工审核与交接，展开 4 个远程阶段、任务 ID、命令模板、必需输出和密钥配置要求；其中只保留变量名，不保存真实服务器地址、私钥路径或 API 密钥值。
`remote_connection_profile.template.json` 中 `configured_secrets` 默认保持空列表；只有远程 shell、凭据管理系统或调度器已经安全配置对应变量后，才能把变量名加入该列表。不得把 `OPENAI_API_KEY` 的值写入 profile。

## 检查命令

```bash
python3 --version
python3 scripts/check_cuda.py
python3 -m iad_sieve.cli --help
```

## 数据放置

```text
data/raw/arxiv-metadata-oai-snapshot.json
```

## 实验命令

```bash
conda activate iad-sieve
python -m iad_sieve.cli --help
python scripts/check_cuda.py
PYTHON_BIN=python scripts/run_dev_experiment.sh 1000
PYTHON_BIN=python scripts/run_dev_experiment.sh 10000
```

## 优先远程任务

```text
1. run_scincl_baseline_open_v3_scholarly_balanced_gold
2. run_roberta_pair_baseline_open_v3_scholarly_balanced_gold
3. run_scincl_provenance_blind_iad_risk_transformer_open_v3_scholarly_balanced_gold
4. pull outputs and run primary_remote_handoff post-run validation
5. run_scincl_baseline_open_v3_scholarly_balanced_gold_source_heldout
6. run_roberta_pair_baseline_open_v3_scholarly_balanced_gold_source_heldout
7. run_scincl_iad_risk_transformer_open_v3_scholarly_balanced_gold_source_heldout
8. run_specter2_adapter_baseline_open_v2
9. run_specter2_adapter_iad_risk_transformer_open_v2
10. run_scincl_provenance_blind_iad_risk_transformer_open_v2
11. run_llm_pair_judge_api_model_open_v2
12. rebuild_evidence_package_after_strong_baselines
```
