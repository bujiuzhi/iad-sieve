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
| `artifact_release_README.template.md` | 外部结果 artifact release README 模板 |
| `final_upload_information_request.md` | 正式上传前作者信息、声明和 artifact 链接收集表 |
| `submission_system_checklist.md` | 正式投稿系统上传前核对清单 |
| `reviewer_readiness_audit.md` | 审稿准备度与拒稿风险审计 |
| `submission_metadata.yml` | 投稿系统元数据字段 |
| `scripts/validate_manuscript.py` | 稿件材料校验 |
| `scripts/submission_metadata_checks.py` | 正式上传元数据结构校验 |
| `scripts/verify_fixture_rebuild.py` | 无网络 fixture 重建校验 |
| `scripts/build_submission_package.py` | 投稿包构建脚本 |
| `scripts/validate_submission_package.py` | 投稿包完整性校验 |
| `scripts/validate_artifact_release.py` | 外部结果 artifact release 校验 |
| `scripts/build_artifact_release_skeleton.py` | 外部结果 artifact release 骨架生成 |
| `scripts/populate_artifact_release.py` | 从实验输出填充外部结果 artifact release |
| `scripts/finalize_artifact_release.py` | 外部结果 artifact release manifest 与 checksum 定稿 |
| `scripts/build_elsevier_draft.py` | Elsevier/DKE 预转换稿生成脚本 |
| `scripts/check_latex_warnings.py` | LaTeX 构建日志与严重版面警告校验 |
| `scripts/check_pdf_rendering.py` | PDF 抽样渲染与空白页/黑页校验 |
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
python manuscript/scripts/build_artifact_release_skeleton.py --output-dir /path/to/release --repository-commit <commit>
python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts --preflight-only
python manuscript/scripts/populate_artifact_release.py --artifact-dir /path/to/release --source-dir /path/to/source-artifacts
python manuscript/scripts/finalize_artifact_release.py --artifact-dir /path/to/release
python manuscript/scripts/validate_artifact_release.py --artifact-dir /path/to/release
./manuscript/scripts/build_latex_pdf.sh
python manuscript/scripts/check_latex_warnings.py
python manuscript/scripts/check_pdf_rendering.py
python manuscript/scripts/build_elsevier_draft.py
python manuscript/scripts/build_submission_package.py --dke-preflight
python manuscript/scripts/validate_submission_package.py --dke-preflight
```

## 投稿边界

该材料包当前不绑定具体期刊模板。正式上传前，应按目标期刊要求调整 `main.tex` 文档类并补充作者元数据。

`target_journal_shortlist.md` 用于记录候选期刊和模板前置要求，不作为正式投稿附件。目标期刊和分区/分类应在最终上传前由作者按所在单位认可的数据源重新确认。

`build/iad-risk-manuscript-elsevier.tex` 和 `build/iad-risk-manuscript-elsevier.pdf` 是 Data & Knowledge Engineering 路线的匿名 `elsarticle` 预转换预览，用于模板适配检查和源文件上传准备；正式上传前仍需作者确认目标期刊、作者元数据、artifact release 和实时投稿系统字段。

`build/dke_preflight_package/` 和 `build/iad-risk-dke-preflight-package.zip` 是 DKE/Elsevier 匿名预投稿包的生成产物，不纳入 Git 跟踪；它们用于检查投稿文件组合，不替代最终上传门禁。

`artifact_release_manifest.template.json` 和 `artifact_release_README.template.md` 用于准备正式 artifact release，不作为当前匿名预投稿包的替代物。`scripts/build_artifact_release_skeleton.py` 只生成外部 release 骨架；真实结果应从不纳入 Git 的 source artifact 目录先通过 `scripts/populate_artifact_release.py --preflight-only` 做只读完整性检查，再通过 `scripts/populate_artifact_release.py` 填充。填入真实结果 artifact 后，应使用 `scripts/finalize_artifact_release.py` 刷新 manifest 和 checksum。正式上传前应创建真实公开链接，并用 `scripts/validate_artifact_release.py` 校验 release 目录。最终上传还要求 artifact `manifest.json` 的 `publication.artifact_release_url`、`publication.artifact_release_doi` 和 `publication.public_access_status` 与 `submission_metadata.yml`、投稿信和 live submission-system data statement 保持一致；repository URL、artifact release URL 和 `publication.artifact_release_url` 均不得使用 `example.org`、`localhost`、`.test` 或 `.invalid` 等示例或本地域名。

Artifact release 的 `repository.commit` 必须是 7 到 40 位十六进制 Git 提交号。`scripts/build_artifact_release_skeleton.py` 和 `scripts/validate_artifact_release.py` 都会拒绝默认模板值或非 Git SHA 文本，避免外部结果包无法追溯到明确代码版本。

`open_v2_main_results` 是主结果表对应的外部结果 artifact。正式 artifact release 中的 CSV 必须包含 per-row denominator counts、per-row threshold source、scope label used in the main table、automatic merge count、block count、defer count、automatic merge coverage、defer rate 和 capacity-normalized review load，确保主结果表不是仅由文件名和 checksum 支撑，而是可按行追溯 denominator、阈值来源、评价范围、选择性决策覆盖率和人工复核负担边界。

`iad_risk_predictions`、`representation_baseline_scores`、`supervised_baseline_predictions` 和 `threshold_selection_logs` 是外部结果 artifact 的行级预测与阈值证据。预测与分数 JSONL 必须记录 `pair_id`、`source_document_id`、`target_document_id`、expected labels、label strength、hard-negative level、split identifiers、`score_field` 或概率字段、`threshold_value`、threshold source 和 `merge_prediction`。阈值日志必须记录 system、threshold_name、`threshold_value`、selection_split、selection_metric、selection_rule、applied_scope 和 `score_field`，用于证明阈值来自固定验证流程而不是测试后选择。

`final_upload_information_request.md` 用于收集正式上传前的 Target journal ranking/category confirmation、Author list、author biographies and photographs、Corresponding author、Funding statement、Author contribution statement、Permissions statement、Generative AI declaration、Artifact release URL or DOI、artifact manifest publication 字段和 Live submission-system fields。DKE/Elsevier 路线的作者 biography/photo 外部材料必须同步到 `submission_metadata.yml` 的 `author_identity_materials`，包括 `biography_files`、`photograph_files` 和 `author_identity_materials_verified`。该文件不作为正式投稿附件；作者确认这些外部输入后，再同步更新 `submission_metadata.yml`、投稿信和目标期刊系统字段。

`submission_system_checklist.md` 用于正式上传前逐项核对文件、元数据、PDF 和 artifact release，不作为当前匿名预投稿包的替代物。

`reviewer_readiness_audit.md` 用于记录投稿前审稿准备度、主要拒稿风险和最终上传门槛，不作为当前匿名预投稿包的替代物。

`scripts/validate_submission_package.py` 会在投稿包目录层面校验 PDF 新鲜度：主稿 PDF 必须晚于 `main.tex` 和 `references.bib`，补充材料 PDF 必须晚于 `supplementary_material.tex`，DKE/Elsevier 预转换 PDF 必须晚于 `iad-risk-manuscript-elsevier.tex`、`keywords.md` 和 `references.bib`。该门禁用于避免源文件或参考文献更新后误打包旧 PDF。

`submission_manifest.json` 会记录 `source_control` 字段，包括 `repository_commit`、`repository_branch`、`worktree_dirty` 和 `tracked_state`。正式上传校验会在 source-control 信息可用时要求 manifest 提交号与 `submission_metadata.yml` 中的 `repository_commit` 一致，要求 `repository_branch` 为 `main` 并与 `submission_metadata.yml` 一致，并要求 `worktree_dirty: false`。

为避免 tracked source 文件包含自引用 Git 提交号，`scripts/build_submission_package.py --final-upload` 会从 `git remote origin`、`git rev-parse HEAD` 和当前分支读取仓库信息，并写入生成包内的 `submission_metadata.yml` 副本。源文件中的 `repository_reference` 可在最终上传前保持空值；正式上传包副本必须与 `submission_manifest.json` 的 `source_control.repository_commit` 和 `source_control.repository_branch` 一致，且分支必须为 `main`。

## 正式上传检查项

`submission_metadata.yml` 中的 `final_upload_checklist` 记录正式上传前必须完成的项目。当前预投稿包保持匿名预投稿状态，源文件中的 `statements.originality`、`statements.author_approval` 和 `statements.competing_interests` 保持空值，正式上传前再由作者确认后填入。`main.tex` 的 Competing Interests 段只记录预投稿边界，不作为最终作者声明；最终利益冲突状态需要与 `submission_metadata.yml` 和 live submission system 保持一致。正式上传前应至少完成目标期刊选择、`selected_author_guide_source`、真实 `selected_author_guide_source_url`、`selected_author_guide_rechecked_date`、`selected_template_requirements_confirmed`、`ranking_confirmation_completed`、`ranking_confirmation_source`、真实 `ranking_confirmation_source_url`、`ranking_confirmation_checked_date`、`selected_target_author_confirmed`、期刊模板套用、作者信息、`author_identity_materials` 中的作者 biography/photo 外部材料清单与核验状态、通讯作者信息、经费声明文本、作者贡献声明、第三方材料许可声明、生成式 AI 使用声明、模板后 PDF 重建、投稿系统文件核对、`live_submission_system_verified`、`final_upload_package_verified_against_system` 和 artifact release 链接。`scripts/submission_metadata_checks.py` 对最终上传元数据执行结构检查，包括作者指南/模板要求确认字段、目标排名/类别确认字段、DKE 作者身份材料清单、live submission-system 终检字段、作者邮箱、ORCID、经费声明文本、作者贡献声明、permissions statement、generative AI declaration、repository URL、`repository_branch: "main"` 和 artifact release URL/DOI 的基本结构，并拒绝示例或本地域名。`scripts/validate_submission_package.py --final-upload --artifact-dir /path/to/release` 进一步要求提交包元数据与外部 artifact manifest publication 字段指向 same public artifact URL or DOI，要求 source_control 分支为 `main`，并拒绝示例或本地 `publication.artifact_release_url`。
