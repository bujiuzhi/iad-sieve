# 期刊投稿材料

## 目录用途

本目录保存期刊稿件源码、参考文献、构建脚本和编译后的 PDF。该目录与项目技术文档、数据目录和实验输出目录分离。

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

构建脚本会同步生成主稿 PDF、补充材料 PDF、DKE/Elsevier 预转换 PDF，并在 `build/logs/` 下写入本地构建日志。`scripts/check_latex_warnings.py` 会拒绝严重 overfull hbox、未定义引用、未定义参考文献和致命 TeX 错误；`scripts/check_pdf_rendering.py` 会抽样渲染 PDF 页面，拒绝空白页、黑页和渲染失败。

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
python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts
python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release
python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release
```

Elsevier/DKE 预转换稿构建：

```bash
python manuscript/scripts/build_elsevier_draft.py
```

DKE/Elsevier 匿名预投稿包构建：

```bash
python manuscript/scripts/build_submission_package.py --dke-preflight
python manuscript/scripts/validate_submission_package.py --dke-preflight
```

## 投稿边界

稿件当前使用模板无关的 LaTeX 源文件。正式投稿前，应按目标期刊要求替换 `main.tex` 的文档类并设置作者信息。现有证据支持保守主张：IAD-Risk 在 gold/proxy/silver 分层评估下建模身份-议题混杂并降低误合并风险，不应主张全领域方法优越性或已完成完整人工金标。

`target_journal_shortlist.md` 记录候选期刊、适配风险和模板前置要求。该文件用于投稿前决策，不作为最终期刊系统上传附件；正式上传前仍需由作者确认目标期刊和最新分区/分类信息。若选择 DKE/Elsevier 路线，还需在最终上传前准备作者 biography 和 passport-type photograph 等作者身份材料。

`build/iad-risk-manuscript-elsevier.tex` 和 `build/iad-risk-manuscript-elsevier.pdf` 是 Data & Knowledge Engineering 路线的匿名 `elsarticle` 预转换预览，由 `scripts/build_elsevier_draft.py` 从 `main.tex` 和 `keywords.md` 生成。该组文件用于模板适配检查和源文件上传准备，不等同于最终投稿文件；正式上传前仍需作者信息、artifact release 和投稿系统核对。

`build/dke_preflight_package/` 和 `build/iad-risk-dke-preflight-package.zip` 由 `build_submission_package.py --dke-preflight` 生成，包含模板无关材料和 DKE/Elsevier 预转换源/PDF。该包用于投稿前检查，不表示最终上传门禁已通过。

`artifact_release_manifest.template.json` 记录结果 artifact release 应包含的表格、预测、日志、校验命令和 claim boundary。`artifact_release_README.template.md` 是外部 artifact release 的 README 模板，说明目录结构、校验命令、数据边界和条件 claim artifact。`scripts/build_artifact_release_skeleton.py` 可从模板生成外部 release 骨架，但不会生成真实结果文件；真实结果应先由实验流程写入不纳入 Git 的 source artifact 目录，再由 `scripts/populate_artifact_release.py` 拷贝到 release 骨架。补齐真实 artifact 后，应使用 `scripts/finalize_artifact_release.py` 刷新 manifest 和 SHA256，再用 `scripts/validate_artifact_release.py` 校验 release 目录。正式上传前还应在 `submission_metadata.yml` 中填写 artifact 链接。

`open_v2_main_results` 是主结果表对应的外部 artifact。其 CSV 需要包含 per-row denominator counts、per-row threshold source、scope label used in the main table、automatic merge count、block count、defer count、automatic merge coverage 和 defer rate；否则只能说明文件存在，不能支持主结果表逐行审计。

`iad_risk_predictions`、`representation_baseline_scores`、`supervised_baseline_predictions` 和 `threshold_selection_logs` 是主结果表的行级复核入口。预测与分数 JSONL 至少需要包含 `pair_id`、`source_document_id`、`target_document_id`、expected labels、label strength、hard-negative level、split identifiers、`score_field` 或概率字段、`threshold_value`、threshold source 和 `merge_prediction`；阈值日志至少需要包含 system、threshold_name、`threshold_value`、selection_split、selection_metric、selection_rule、applied_scope 和 `score_field`。缺少这些字段时，外部 artifact 只能证明文件存在，不能支持 L3 result audit。

`final_upload_information_request.md` 汇总正式上传前必须由作者确认或提供的外部输入，包括 Author list、author biographies and photographs、Corresponding author、Funding statement、Author contribution statement、Permissions statement、Generative AI declaration、Artifact release URL or DOI 和 Live submission-system fields。该文件不作为期刊上传附件；它用于防止在稿件、投稿信或 `submission_metadata.yml` 中填入未确认信息。

`submission_system_checklist.md` 记录最终上传到期刊系统前需要核对的文件、元数据、PDF 和 artifact release 项。该文件用于最终上传前检查，不作为当前预投稿包附件。

`reviewer_readiness_audit.md` 记录投稿前的审稿准备度、主要拒稿风险、证据边界和最终上传门槛。该文件用于质量控制，不作为最终投稿附件。

`submission_metadata.yml` 中的 `final_upload_checklist` 是正式上传门禁。只有目标期刊、期刊模板、作者元数据、作者 biography/photo 材料、通讯作者元数据、经费声明文本、作者贡献声明、第三方材料许可声明、生成式 AI 使用声明、模板后 PDF 重建、投稿系统文件核对和 artifact release 信息均完成后，才应使用 `--final-upload` 生成或校验最终投稿包。`scripts/submission_metadata_checks.py` 会同时检查作者邮箱、ORCID、经费声明文本、作者贡献声明、permissions statement、generative AI declaration 和 artifact release URL/DOI 的基本结构。
