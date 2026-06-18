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

`target_journal_shortlist.md` 记录候选期刊、适配风险和模板前置要求。该文件用于投稿前决策，不作为最终期刊系统上传附件；正式上传前仍需由作者确认目标期刊和最新分区/分类信息。

`build/iad-risk-manuscript-elsevier.tex` 和 `build/iad-risk-manuscript-elsevier.pdf` 是 Data & Knowledge Engineering 路线的匿名 `elsarticle` 预转换预览，由 `scripts/build_elsevier_draft.py` 从 `main.tex` 和 `keywords.md` 生成。该组文件用于模板适配检查和源文件上传准备，不等同于最终投稿文件；正式上传前仍需作者信息、artifact release 和投稿系统核对。

`build/dke_preflight_package/` 和 `build/iad-risk-dke-preflight-package.zip` 由 `build_submission_package.py --dke-preflight` 生成，包含模板无关材料和 DKE/Elsevier 预转换源/PDF。该包用于投稿前检查，不表示最终上传门禁已通过。

`artifact_release_manifest.template.json` 记录结果 artifact release 应包含的表格、预测、日志、校验命令和 claim boundary。`artifact_release_README.template.md` 是外部 artifact release 的 README 模板，说明目录结构、校验命令、数据边界和条件 claim artifact。`scripts/build_artifact_release_skeleton.py` 可从模板生成外部 release 骨架，但不会生成真实结果文件；真实结果应先由实验流程写入不纳入 Git 的 source artifact 目录，再由 `scripts/populate_artifact_release.py` 拷贝到 release 骨架。补齐真实 artifact 后，应使用 `scripts/finalize_artifact_release.py` 刷新 manifest 和 SHA256，再用 `scripts/validate_artifact_release.py` 校验 release 目录。正式上传前还应在 `submission_metadata.yml` 中填写 artifact 链接。

`submission_system_checklist.md` 记录最终上传到期刊系统前需要核对的文件、元数据、PDF 和 artifact release 项。该文件用于最终上传前检查，不作为当前预投稿包附件。

`reviewer_readiness_audit.md` 记录投稿前的审稿准备度、主要拒稿风险、证据边界和最终上传门槛。该文件用于质量控制，不作为最终投稿附件。

`submission_metadata.yml` 中的 `final_upload_checklist` 是正式上传门禁。只有目标期刊、期刊模板、作者元数据、通讯作者元数据、模板后 PDF 重建、投稿系统文件核对和 artifact release 信息均完成后，才应使用 `--final-upload` 生成或校验最终投稿包。`scripts/submission_metadata_checks.py` 会同时检查作者邮箱、ORCID 和 artifact release URL/DOI 的基本结构。
