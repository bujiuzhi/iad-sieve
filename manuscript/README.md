# 期刊投稿材料

## 目录用途

本目录保存期刊稿件源码、参考文献、构建脚本和编译后的 PDF。该目录与项目技术文档、数据目录和实验输出目录分离。

## 目录边界

`manuscript/` 是唯一纳入 Git 跟踪的稿件产物目录。期刊写作、匿名预投稿检查、DKE/Elsevier 预转换、投稿包构建脚本、投稿系统元数据和外部 artifact release 模板均在本目录维护。

仓库根目录的 `docs/` 保存项目技术文档，不保存期刊上传材料；`data/` 保存本地数据边界，不作为投稿产物；`outputs/` 保存本地实验输出、PDF 构建缓存或离线 Tectonic bundle，不作为投稿产物。生成的投稿检查包仅位于 `manuscript/build/`，其中 `manuscript/build/submission_package/`、`manuscript/build/dke_preflight_package/` 和对应 zip 文件是本地构建产物，不纳入 Git 跟踪。

本目录只保留与本课题投稿直接相关的材料，不保存内部过程材料、编辑日志或与课题无关的文档。

## 产物分层与追踪边界

| 产物层 | 位置 | Git 状态 | 用途 | 不替代内容 |
| --- | --- | --- | --- | --- |
| 期刊源文件 | `manuscript/main.tex`、`manuscript/supplementary_material.tex`、`manuscript/references.bib`、投稿文本、元数据和脚本 | Git 跟踪 | 形成可审计的稿件源码和投稿准备材料 | 不替代目标期刊最终模板套用、作者确认和 live submission-system 核对 |
| 跟踪 PDF 预览 | `manuscript/build/iad-risk-manuscript-latex.pdf`、`manuscript/build/iad-risk-manuscript-elsevier.tex`、`manuscript/build/iad-risk-manuscript-elsevier.pdf`、`manuscript/build/iad-risk-supplementary-material.pdf` | Git 跟踪 | 证明当前源码可生成可读主稿、补充材料和 DKE/Elsevier 匿名预转换预览 | 不替代最终上传包、目标期刊作者版源文件或投稿系统预览 |
| 本地提交包 | `manuscript/build/submission_package/`、`manuscript/build/dke_preflight_package/`、`manuscript/build/iad-risk-submission-package.zip`、`manuscript/build/iad-risk-dke-preflight-package.zip` | 忽略且不提交 | 本地检查投稿文件组合、manifest 和 checksum | 不替代 Git 跟踪源文件或外部 artifact release |
| 外部结果 artifact | 仓库外 release 目录或公开 DOI/URL | 仓库外发布 | 承载 L2/L3 数值复验所需的派生表格、预测、日志、manifest 和 checksum | 不重新分发原始第三方数据，除非原始来源条款明确允许 |
| 本地数据与运行输出 | `data/`、`outputs/` | 忽略且不提交 | 存放本地输入、实验输出、PDF 构建缓存或离线 Tectonic bundle | 不作为期刊上传材料或公开源码包内容 |

## 文件清单

```text
manuscript/
  main.tex
  supplementary_material.tex
  references.bib
  cover_letter.md
  highlights.md
  keywords.md
  target_journal_shortlist.md
  artifact_release_manifest.template.json
  artifact_release_README.template.md
  final_upload_information_request.md
  submission_system_checklist.md
  reviewer_readiness_audit.md
  submission_metadata.yml
  MANIFEST.md
  scripts/
    validate_manuscript.py
    submission_metadata_checks.py
    verify_fixture_rebuild.py
    build_submission_package.py
    validate_submission_package.py
    validate_artifact_release.py
    build_artifact_release_skeleton.py
    populate_artifact_release.py
    finalize_artifact_release.py
    build_elsevier_draft.py
    check_latex_warnings.py
    check_pdf_rendering.py
    diagnose_latex_environment.py
    build_latex_pdf.sh
  build/
    iad-risk-manuscript-latex.pdf
    iad-risk-manuscript-elsevier.tex
    iad-risk-manuscript-elsevier.pdf
    iad-risk-supplementary-material.pdf
```

## 构建命令

正式 LaTeX 构建：

```bash
cd manuscript
./scripts/build_latex_pdf.sh
```

构建脚本会先运行 `python scripts/diagnose_latex_environment.py --skip-logs`，在正式编译前检查 LaTeX/Tectonic 引擎、bundle 路径和项目相关 Tectonic compile smoke tests，包括 `article[11pt]` 和 `elsarticle[preprint,12pt]`。通过前置诊断后，脚本会同步生成主稿 PDF、补充材料 PDF、DKE/Elsevier 预转换 PDF，并在 `build/logs/` 下写入本地构建日志。`scripts/check_latex_warnings.py` 会拒绝严重 overfull hbox、未定义引用、未定义参考文献和致命 TeX 错误；`scripts/check_pdf_rendering.py` 会抽样渲染 PDF 页面，拒绝空白页、黑页和渲染失败。

离线或默认 Tectonic bundle 不可用时，可先准备一个只读本地 Tectonic bundle 目录，并通过 `TECTONIC_BUNDLE_DIR=/path/to/tectonic-bundle ./scripts/build_latex_pdf.sh` 构建。也可以从仓库根目录使用相对路径，例如 `TECTONIC_BUNDLE_DIR=outputs/tectonic_dir_bundle manuscript/scripts/build_latex_pdf.sh`；构建脚本会在进入 `manuscript/` 前将相对路径解析为绝对路径。该环境变量只改变 TeX 资源来源，不改变主稿、补充材料、Elsevier 预转换稿、LaTeX 日志和 PDF rendering 检查的构建门禁；临时 bundle 目录应放在 `outputs/` 或其他不纳入 Git 的位置。

LaTeX 环境诊断：

```bash
python manuscript/scripts/diagnose_latex_environment.py
```

`scripts/diagnose_latex_environment.py` 用于区分 TeX 源文件问题与本地构建环境问题。该脚本检查本机 LaTeX 引擎可用性、`TECTONIC_BUNDLE_DIR` 是否指向本地 Tectonic bundle、`build/logs/*.log` 中的 Tectonic/Rust runtime panic 标记，以及 `system-configuration`、`reqwest`、`Attempted to create a NULL object`、`event loop thread panicked` 等运行时失败线索。默认诊断还会运行 `article[11pt]` 和 `elsarticle[preprint,12pt]` 两个项目相关 Tectonic compile smoke tests，用于发现“版本可用但一运行即崩溃”或“bundle 缺少项目所需宏包”的环境；非 panic 类烟测失败会保留 bounded output excerpt，并识别 ``File `...' not found`` 这类 missing TeX resource，提示检查本地 Tectonic bundle 完整性。如只需检查历史日志，可加 `--skip-smoke-test`，如在构建前尚无 `build/logs/` 文件，可加 `--skip-logs`。该诊断只记录构建环境阻断项，不替代 PDF 构建、LaTeX warning 检查、PDF rendering 检查或最终投稿包新鲜度校验。

稿件校验：

```bash
python manuscript/scripts/validate_manuscript.py
```

无网络 fixture 重建校验：

```bash
python manuscript/scripts/verify_fixture_rebuild.py
```

投稿包构建：

```bash
python manuscript/scripts/build_submission_package.py
python manuscript/scripts/validate_submission_package.py
```

Artifact release 校验：

```bash
python manuscript/scripts/build_artifact_release_skeleton.py --output-dir /path/to/release --repository-commit <commit>
python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only
python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts
python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release
python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release
```

`/path/to/source-artifacts` 必须是完成 L3 实验后生成的独立只读源目录，不是 `outputs/` 根目录，也不是 PDF 构建目录。最小结构必须包含 `tables/open_v2_main_results.csv`、`predictions/iad_risk_transformer_predictions.jsonl`、`predictions/representation_baseline_scores.jsonl`、`predictions/roberta_pair_classifier_predictions.jsonl`、`logs/threshold_selection_logs.jsonl`、`reports/iad_bench_split_summary.jsonl`、`configs/source_input_manifest.json` 和 `logs/processing_run_log.jsonl`。`--preflight-only` 通过前，不应声明已有可发布的 L3 artifact release。

Elsevier/DKE 预转换稿构建：

```bash
python manuscript/scripts/build_elsevier_draft.py
```

该命令在调用 Tectonic 生成 PDF 前同样运行 `diagnose_latex_environment.py --skip-logs`。若只需要更新 Elsevier LaTeX 源文件而不生成 PDF，可使用 `python manuscript/scripts/build_elsevier_draft.py --no-pdf`。

DKE/Elsevier 匿名预投稿包构建：

```bash
python manuscript/scripts/build_submission_package.py --dke-preflight
python manuscript/scripts/validate_submission_package.py --dke-preflight
```

## 投稿边界

稿件当前使用模板无关的 LaTeX 源文件。正式投稿前，应按目标期刊要求替换 `main.tex` 的文档类并设置作者信息。现有证据支持保守主张：IAD-Risk 在 gold/proxy/silver 分层评估下建模身份-议题混杂并降低误合并风险，不应主张全领域方法优越性或已完成完整人工金标。

`target_journal_shortlist.md` 记录候选期刊、适配风险和模板前置要求。该文件用于投稿前决策，不作为最终期刊系统上传附件；正式上传前仍需由作者确认目标期刊、真实作者指南来源 URL 和最新分区/分类信息，并在 `submission_metadata.yml` 中填写 `ranking_confirmation_completed`、`ranking_confirmation_source`、真实 `ranking_confirmation_source_url`、`ranking_confirmation_checked_date` 和 `selected_target_author_confirmed`。若选择 DKE/Elsevier 路线，还需在最终上传前准备作者 biography 和 passport-type photograph 等作者身份材料；每位作者 biography 需不超过 100 词，文件需为可编辑格式且不能为 PDF，并在 `author_identity_materials` 中记录 `biography_files`、`photograph_files` 和 `author_identity_materials_verified`。

`build/iad-risk-manuscript-elsevier.tex` 和 `build/iad-risk-manuscript-elsevier.pdf` 是 Data & Knowledge Engineering 路线的匿名 `elsarticle` 预转换预览，由 `scripts/build_elsevier_draft.py` 从 `main.tex` 和 `keywords.md` 生成。该组文件用于模板适配检查和源文件上传准备，不等同于最终投稿文件；正式上传前仍需作者信息、artifact release 和投稿系统核对。

`build/dke_preflight_package/` 和 `build/iad-risk-dke-preflight-package.zip` 由 `build_submission_package.py --dke-preflight` 生成，包含模板无关材料和 DKE/Elsevier 预转换源/PDF。该包用于投稿前检查，不表示最终上传门禁已通过。

`artifact_release_manifest.template.json` 记录结果 artifact release 应包含的表格、预测、日志、校验命令、claim boundary 和 publication 绑定字段。`artifact_release_README.template.md` 是外部 artifact release 的 README 模板，说明目录结构、校验命令、数据边界和条件 claim artifact。`scripts/build_artifact_release_skeleton.py` 可从模板生成外部 release 骨架，但不会生成真实结果文件；真实结果应先由实验流程写入不纳入 Git 的 source artifact 目录，并先用 `scripts/populate_artifact_release.py --preflight-only` 只读检查必需 source artifact 文件是否齐全，再由 `scripts/populate_artifact_release.py` 拷贝到 release 骨架。补齐真实 artifact 后，应使用 `scripts/finalize_artifact_release.py` 刷新 manifest 和 SHA256，再用 `scripts/validate_artifact_release.py` 校验 release 目录。正式上传前还应在 `submission_metadata.yml` 中填写真实公开 artifact 链接，并确保 artifact `manifest.json` 的 `publication.artifact_release_url`、`publication.artifact_release_doi` 和 `publication.public_access_status` 与最终上传元数据一致；repository URL、artifact release URL 和 `publication.artifact_release_url` 均不得使用 `example.org`、`localhost`、`.test` 或 `.invalid` 等示例或本地域名。

外部 artifact release 应发布可再分发的派生表格、预测文件、日志、manifest 和 checksum，而不是原始第三方来源文件，除非原始来源条款明确允许再分发。`configs/source_input_manifest.json` 必须记录每个公开输入的 original provider、acquisition date or version、safe relative local file boundary、license boundary 和 valid SHA256 checksum。`logs/processing_run_log.jsonl` 必须记录 command line、code commit matching `manifest.json` `repository.commit`、environment summary、random seed、start/finish timestamps、input manifest reference、checksum-bound output path 和 successful `exit_status=0`。

`open_v2_main_results` 是主结果表对应的外部 artifact。其 CSV 需要包含 per-row denominator counts、per-row threshold source、scope label used in the main table、automatic merge count、block count、defer count、automatic merge coverage、defer rate 和 capacity-normalized review load；否则只能说明文件存在，不能支持主结果表逐行审计或人工复核负担判断。

`iad_risk_predictions`、`representation_baseline_scores`、`supervised_baseline_predictions` 和 `threshold_selection_logs` 是主结果表的行级复核入口。预测与分数 JSONL 至少需要包含 `pair_id`、`source_document_id`、`target_document_id`、expected labels、label strength、hard-negative level、split identifiers、`score_field` 或概率字段、`threshold_value`、threshold source 和 `merge_prediction`；阈值日志至少需要包含 system、threshold_name、`threshold_value`、selection_split、selection_metric、selection_rule、applied_scope 和 `score_field`。缺少这些字段时，外部 artifact 只能证明文件存在，不能支持 L3 result audit。

`final_upload_information_request.md` 汇总正式上传前必须由作者确认或提供的外部输入，包括 Target journal ranking/category confirmation、Author list、author biographies and photographs、Corresponding author、Funding statement、Author contribution statement、Permissions statement、Generative AI declaration、Artifact release URL or DOI 和 Live submission-system fields。该文件不作为期刊上传附件；它用于防止在稿件、投稿信或 `submission_metadata.yml` 中填入未确认信息。

`submission_system_checklist.md` 记录最终上传到期刊系统前需要核对的文件、元数据、PDF 和 artifact release 项。该文件用于最终上传前检查，不作为当前预投稿包附件。

`reviewer_readiness_audit.md` 记录投稿前的审稿准备度、主要拒稿风险、证据边界和最终上传门槛。该文件用于质量控制，不作为最终投稿附件。

`submission_metadata.yml` 中的 `final_upload_checklist` 是正式上传门禁。当前匿名评审源中的 `statements.originality`、`statements.author_approval` 和 `statements.competing_interests` 保持空值，避免在作者名单、通讯作者和 live submission-system 字段确认前写入最终作者声明。`main.tex` 的 Competing Interests 段同样只说明匿名评审文件不声明最终利益冲突结论，正式上传前必须由署名作者确认利益冲突状态，并同步更新 `submission_metadata.yml` 和期刊系统字段。只有目标期刊、所选作者指南来源与复核日期、模板要求确认、目标排名/类别确认来源和日期、期刊模板、作者元数据、`author_identity_materials` 中的作者 biography/photo 外部材料清单与核验状态、通讯作者元数据、经费声明文本、作者贡献声明、第三方材料许可声明、生成式 AI 使用声明、模板后 PDF 重建、投稿系统文件核对、live submission-system 终检和 artifact release 信息均完成后，才应使用 `--final-upload` 生成或校验最终投稿包。DKE 路线下，`scripts/submission_metadata_checks.py` 还会拒绝 PDF 或非可编辑格式的作者 biography 文件。`scripts/submission_metadata_checks.py` 会同时检查作者指南/模板要求确认字段、目标排名/类别确认字段、DKE 作者身份材料清单、`live_submission_system_verified`、`final_upload_package_verified_against_system`、作者邮箱、ORCID、经费声明文本、作者贡献声明、permissions statement、generative AI declaration、repository URL、`repository_branch: "main"` 和 artifact release URL/DOI 的基本结构，并拒绝示例或本地域名；`scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release` 还会检查提交包元数据、`source_control.repository_branch`、artifact manifest publication 字段和外部 release 目录是否绑定到 same public artifact URL or DOI，并要求分支必须为 `main`，同时拒绝示例或本地 `publication.artifact_release_url`。
