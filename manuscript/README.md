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
  submission_metadata.yml
  MANIFEST.md
  scripts/
    validate_manuscript.py
    verify_fixture_rebuild.py
    build_submission_package.py
    validate_submission_package.py
    build_latex_pdf.sh
  build/
    iad-risk-manuscript-latex.pdf
    iad-risk-supplementary-material.pdf
```

## 构建命令

正式 LaTeX 构建：

```bash
cd manuscript
tectonic main.tex
mv main.pdf build/iad-risk-manuscript-latex.pdf
tectonic supplementary_material.tex
mv supplementary_material.pdf build/iad-risk-supplementary-material.pdf
```

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

## 投稿边界

稿件当前使用模板无关的 LaTeX 源文件。正式投稿前，应按目标期刊要求替换 `main.tex` 的文档类并设置作者信息。现有证据支持保守主张：IAD-Risk 在 gold/proxy/silver 分层评估下建模身份-议题混杂并降低误合并风险，不应主张全领域方法优越性或已完成完整人工金标。

`target_journal_shortlist.md` 记录候选期刊、适配风险和模板前置要求。该文件用于投稿前决策，不作为最终期刊系统上传附件；正式上传前仍需由作者确认目标期刊和最新分区/分类信息。

`submission_metadata.yml` 中的 `final_upload_checklist` 是正式上传门禁。只有目标期刊、期刊模板、作者元数据、通讯作者元数据、模板后 PDF 重建、投稿系统文件核对和 artifact release 信息均完成后，才应使用 `--final-upload` 生成或校验最终投稿包。
