# 稿件材料清单

## 文件清单

| 路径 | 用途 |
| --- | --- |
| `main.tex` | 主稿 LaTeX 源文件 |
| `supplementary_material.tex` | 补充材料 LaTeX 源文件 |
| `references.bib` | 参考文献条目 |
| `cover_letter.md` | 投稿信 |
| `highlights.md` | 亮点说明 |
| `keywords.md` | 关键词 |
| `target_journal_shortlist.md` | 目标期刊候选与模板前置要求 |
| `artifact_release_manifest.template.json` | 结果 artifact release 元数据模板 |
| `submission_system_checklist.md` | 正式投稿系统上传前核对清单 |
| `reviewer_readiness_audit.md` | 审稿准备度与拒稿风险审计 |
| `submission_metadata.yml` | 投稿系统元数据字段 |
| `scripts/validate_manuscript.py` | 稿件材料校验 |
| `scripts/verify_fixture_rebuild.py` | 无网络 fixture 重建校验 |
| `scripts/build_submission_package.py` | 投稿包构建脚本 |
| `scripts/validate_submission_package.py` | 投稿包完整性校验 |
| `scripts/validate_artifact_release.py` | 外部结果 artifact release 校验 |
| `scripts/build_elsevier_draft.py` | Elsevier/DKE 预转换稿生成脚本 |
| `scripts/check_latex_warnings.py` | LaTeX 构建日志与严重版面警告校验 |
| `scripts/build_latex_pdf.sh` | 正式 PDF 构建脚本 |
| `build/iad-risk-manuscript-latex.pdf` | 主稿 PDF |
| `build/iad-risk-manuscript-elsevier.tex` | DKE/Elsevier 匿名预转换 LaTeX 源 |
| `build/iad-risk-manuscript-elsevier.pdf` | DKE/Elsevier 匿名预转换 PDF |
| `build/iad-risk-supplementary-material.pdf` | 补充材料 PDF |

## 构建命令

```bash
python manuscript/scripts/validate_manuscript.py
python manuscript/scripts/verify_fixture_rebuild.py
python manuscript/scripts/build_submission_package.py
python manuscript/scripts/validate_submission_package.py
python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release
./manuscript/scripts/build_latex_pdf.sh
python manuscript/scripts/check_latex_warnings.py
python manuscript/scripts/build_elsevier_draft.py
python manuscript/scripts/build_submission_package.py --dke-preflight
python manuscript/scripts/validate_submission_package.py --dke-preflight
```

## 投稿边界

该材料包当前不绑定具体期刊模板。正式上传前，应按目标期刊要求调整 `main.tex` 文档类并补充作者元数据。

`target_journal_shortlist.md` 用于记录候选期刊和模板前置要求，不作为正式投稿附件。目标期刊和分区/分类应在最终上传前由作者按所在单位认可的数据源重新确认。

`build/iad-risk-manuscript-elsevier.tex` 和 `build/iad-risk-manuscript-elsevier.pdf` 是 Data & Knowledge Engineering 路线的匿名 `elsarticle` 预转换预览，用于模板适配检查和源文件上传准备；正式上传前仍需作者确认目标期刊、作者元数据、artifact release 和实时投稿系统字段。

`build/dke_preflight_package/` 和 `build/iad-risk-dke-preflight-package.zip` 是 DKE/Elsevier 匿名预投稿包的生成产物，不纳入 Git 跟踪；它们用于检查投稿文件组合，不替代最终上传门禁。

`artifact_release_manifest.template.json` 用于准备正式 artifact release，不作为当前匿名预投稿包的替代物。正式上传前应生成真实 artifact manifest、checksum 和公开链接，并用 `scripts/validate_artifact_release.py` 校验 release 目录。

`submission_system_checklist.md` 用于正式上传前逐项核对文件、元数据、PDF 和 artifact release，不作为当前匿名预投稿包的替代物。

`reviewer_readiness_audit.md` 用于记录投稿前审稿准备度、主要拒稿风险和最终上传门槛，不作为当前匿名预投稿包的替代物。

## 正式上传检查项

`submission_metadata.yml` 中的 `final_upload_checklist` 记录正式上传前必须完成的项目。当前预投稿包保持匿名预投稿状态；正式上传前应至少完成目标期刊选择、期刊模板套用、作者信息、通讯作者信息、模板后 PDF 重建、投稿系统文件核对和 artifact release 链接。
