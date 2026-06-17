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
| `submission_metadata.yml` | 投稿系统元数据字段 |
| `scripts/validate_manuscript.py` | 稿件材料校验 |
| `scripts/verify_fixture_rebuild.py` | 无网络 fixture 重建校验 |
| `scripts/build_submission_package.py` | 投稿包构建脚本 |
| `scripts/validate_submission_package.py` | 投稿包完整性校验 |
| `scripts/build_latex_pdf.sh` | 正式 PDF 构建脚本 |
| `build/iad-risk-manuscript-latex.pdf` | 主稿 PDF |
| `build/iad-risk-supplementary-material.pdf` | 补充材料 PDF |

## 构建命令

```bash
python manuscript/scripts/validate_manuscript.py
python manuscript/scripts/verify_fixture_rebuild.py
python manuscript/scripts/build_submission_package.py
python manuscript/scripts/validate_submission_package.py
cd manuscript && ./scripts/build_latex_pdf.sh
```

## 投稿边界

该材料包当前不绑定具体期刊模板。正式上传前，应按目标期刊要求调整 `main.tex` 文档类并补充作者元数据。
