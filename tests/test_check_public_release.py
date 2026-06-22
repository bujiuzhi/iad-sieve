"""测试公开发布检查脚本。"""

from __future__ import annotations

from pathlib import Path

from scripts.check_public_release import (
    DOCUMENT_TRACE_PATTERNS,
    check_data_pipeline_reproduction_boundary,
    check_docs_index_consistency,
    check_document_directory_scope,
    check_required_gitignore_patterns,
    check_required_documentation,
    check_root_readme_reproduction_levels,
    check_tracked_release_scope,
    run_public_release_check,
    scan_document_traces,
)


def _write_text(path: Path, text: str) -> None:
    """写入测试文本文件。

    参数:
        path: 输出文件路径。
        text: 文件内容。

    返回:
        无。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_required_documentation(project_root: Path) -> None:
    """创建公开发布检查所需的基础说明文档。

    参数:
        project_root: 项目根目录。

    返回:
        无。
    """

    for relative_path in (
        "README.md",
        "data/README.md",
        "docs/README.md",
        "outputs/README.md",
        "manuscript/README.md",
        "manuscript/MANIFEST.md",
    ):
        _write_text(project_root / relative_path, "# Public Documentation\n")
    _write_text(project_root / ".gitignore", "texput.*\n")


def test_scan_document_traces_flags_work_record_text(tmp_path: Path) -> None:
    """验证公开文档中的过程性修改记录会被识别。"""

    _write_text(tmp_path / "docs" / "notes.md", "本次修改：整理 README。\n")

    findings = scan_document_traces(tmp_path, DOCUMENT_TRACE_PATTERNS)

    assert len(findings) == 1
    assert findings[0].category == "document_work_record"


def test_scan_document_traces_flags_auxiliary_model_terms(tmp_path: Path) -> None:
    """验证公开文档中的辅助模型痕迹会被识别。"""

    _write_text(tmp_path / "docs" / "notes.md", "LLM pair judge is used for review.\n")

    findings = scan_document_traces(tmp_path, DOCUMENT_TRACE_PATTERNS)

    assert len(findings) == 1
    assert findings[0].category == "document_ai_trace_tool"


def test_scan_document_traces_flags_placeholder_email(tmp_path: Path) -> None:
    """验证公开文档中的示例邮箱会被识别。"""

    _write_text(tmp_path / "docs" / "data-processing-pipeline.md", "--mailto your_email@example.com\n")

    findings = scan_document_traces(tmp_path, DOCUMENT_TRACE_PATTERNS)

    assert len(findings) == 1
    assert findings[0].category == "document_placeholder_email"


def test_scan_document_traces_ignores_code_model_names(tmp_path: Path) -> None:
    """验证代码中的合法 GPT/OpenAI baseline 名称不会按文档痕迹误报。"""

    _write_text(tmp_path / "src" / "runner.py", 'system_name = "gpt_pair_judge_open_v2"\n')
    _write_text(tmp_path / "docs" / "README.md", "# Method\nThe benchmark uses external baselines.\n")

    findings = scan_document_traces(tmp_path, DOCUMENT_TRACE_PATTERNS)

    assert findings == []


def test_check_required_documentation_flags_missing_file(tmp_path: Path) -> None:
    """验证缺少必要公开说明文档会被识别。"""

    _write_required_documentation(tmp_path)
    (tmp_path / "manuscript" / "MANIFEST.md").unlink()

    findings = check_required_documentation(tmp_path)

    assert len(findings) == 1
    assert findings[0].category == "missing_required_document"
    assert findings[0].snippet == "manuscript/MANIFEST.md"


def test_check_document_directory_scope_flags_unlisted_docs_file(tmp_path: Path) -> None:
    """验证 docs 目录中不在课题文档清单内的文件会被拦截。"""

    _write_text(tmp_path / "docs" / "README.md", "# 文档索引\n")
    _write_text(tmp_path / "docs" / "method-design.md", "# 方法设计\n")
    _write_text(tmp_path / "docs" / "codex-work-record.md", "# Work Record\n")

    findings = check_document_directory_scope(tmp_path)

    assert len(findings) == 1
    assert findings[0].category == "unexpected_documentation_file"
    assert findings[0].snippet == "docs/codex-work-record.md"


def test_check_docs_index_consistency_accepts_iad_risk_method_line(tmp_path: Path) -> None:
    """验证 docs 索引必须使用当前 IAD-Risk 方法主线描述。"""

    _write_text(
        tmp_path / "docs" / "README.md",
        "| 方法设计 | `method-design.md` | 查看 IAD-Risk 方法设计、关系语义和风险门控 |\n",
    )

    findings = check_docs_index_consistency(tmp_path)

    assert findings == []


def test_check_docs_index_consistency_rejects_stale_iad_sieve_method_line(tmp_path: Path) -> None:
    """验证 docs 索引中的旧方法描述会被拦截。"""

    _write_text(
        tmp_path / "docs" / "README.md",
        "| 方法设计 | `method-design.md` | 查看 IAD-Sieve 的核心流程和模块 |\n",
    )

    findings = check_docs_index_consistency(tmp_path)

    assert len(findings) == 2
    assert {finding.category for finding in findings} == {
        "docs_index_missing_marker",
        "docs_index_stale_marker",
    }


def test_check_root_readme_reproduction_levels_accepts_current_levels(tmp_path: Path) -> None:
    """验证根 README 使用当前 L0/L1/L2/L3 复现等级时可通过检查。"""

    _write_text(
        tmp_path / "README.md",
        "\n".join(
            [
                "| L0 code check | 安装、CLI、测试和公开发布扫描 | 无大数据 | 检查公开仓库是否可运行 |",
                "| L1 fixture rebuild | 小型 fixture 重建 | `tests/fixtures/` | 验证数据适配器、schema 和评测协议 |",
                "| L2 public-source rebuild | 从独立获取的公开原始文件重建派生 eval source 和 IAD-Bench 包 | 本地 `data/raw/` 中的公开来源文件、`source_input_manifest` 和 `processing_run_log` | 审计公开输入、处理命令、输出摘要和 checksum 的 chain of custody |",
                "| L3 result audit | 审计已发布的表格、预测、阈值日志、配置、运行日志、manifest 和 checksum | 外部 artifact release | 复核论文主结果、阈值、分母和逐行预测边界 |",
                "L0/L1 只能证明公开仓库代码路径和小型样本处理契约可运行；L2/L3 才能支持 Open-v2 数值表的结果级审计。不存在单独的 L4 Git 仓库复现等级。",
                "结果级复核依赖公开数据来源记录、下载脚本、manifest、checksum 和单独发布的 artifact。",
                "议题级混杂会形成科学实体匹配中的 false merge 风险。",
                "Open-v2/Open-v3 是带有公开构造流程、复现分级和 artifact 审计边界的衍生压力评测框架；主数值复核仍依赖 L2/L3 产物。",
            ]
        ),
    )

    findings = check_root_readme_reproduction_levels(tmp_path)

    assert findings == []


def test_check_root_readme_reproduction_levels_rejects_obsolete_levels(tmp_path: Path) -> None:
    """验证根 README 中的旧版 L2/L3/L4 复现等级会被拦截。"""

    _write_text(
        tmp_path / "README.md",
        "\n".join(
            [
                "| L2 | 小样本开发实验 | 公开来源小样本 | 验证端到端流程 |",
                "| L3 | 论文主实验 | 完整数据与外部 baseline | 生成论文表格和证据包 |",
                "| L4 | 第三方复验 | 固定 artifact release | 独立读者复现 |",
                "完整复现依赖公开数据来源、下载脚本、manifest、checksum 和单独发布的 artifact。",
                "议题级混杂会显著增加科学实体匹配中的 false merge 风险。",
                "Open-v2/Open-v3 是可复验的衍生压力评测框架。",
            ]
        ),
    )

    findings = check_root_readme_reproduction_levels(tmp_path)

    assert any(finding.snippet == "| L2 | 小样本开发实验 |" for finding in findings)
    assert any(finding.snippet == "| L3 | 论文主实验 |" for finding in findings)
    assert any(finding.snippet == "| L4 | 第三方复验 |" for finding in findings)
    assert any(finding.snippet == "完整复现依赖公开数据来源" for finding in findings)
    assert any(finding.snippet == "议题级混杂会显著增加科学实体匹配中的 false merge 风险" for finding in findings)
    assert any(finding.snippet == "Open-v2/Open-v3 是可复验的衍生压力评测框架" for finding in findings)
    assert any(finding.category == "root_readme_reproduction_missing_marker" for finding in findings)


def test_check_data_pipeline_reproduction_boundary_accepts_reviewer_boundary(tmp_path: Path) -> None:
    """验证数据处理文档明确区分 Git-only 与 artifact 复验边界。"""

    _write_text(
        tmp_path / "docs" / "data-processing-pipeline.md",
        "\n".join(
            [
                "## 审稿复现判定",
                "Git-only 审稿只能确认 L0 code check 和 L1 fixture rebuild，不能据此复核 Open-v2/Open-v3 主表数值。",
                "Open-v2/Open-v3 主数值复核必须进入 L2 public-source rebuild 或 L3 result audit。",
                "`configs/source_input_manifest.json`、`logs/processing_run_log.jsonl` 和 `checksums.sha256` 必须随外部 artifact release 一起发布。",
                "未经外部 artifact release 固定的 `outputs/` 结果不能作为论文主表复验依据。",
            ]
        ),
    )

    findings = check_data_pipeline_reproduction_boundary(tmp_path)

    assert findings == []


def test_check_data_pipeline_reproduction_boundary_rejects_git_only_result_claim(tmp_path: Path) -> None:
    """验证数据处理文档缺少 artifact 复验边界时会被拦截。"""

    _write_text(
        tmp_path / "docs" / "data-processing-pipeline.md",
        "## 复现边界\nGit 仓库提供数据处理代码。\n",
    )

    findings = check_data_pipeline_reproduction_boundary(tmp_path)

    assert any(finding.category == "data_pipeline_reproduction_boundary_missing_marker" for finding in findings)
    assert any("L2 public-source rebuild" in finding.snippet for finding in findings)
    assert any("checksums.sha256" in finding.snippet for finding in findings)


def test_check_required_gitignore_patterns_requires_texput_outputs(tmp_path: Path) -> None:
    """验证临时 Tectonic stdin 输出和投稿包产物必须在 .gitignore 中排除。"""

    _write_text(tmp_path / ".gitignore", "*.log\n")

    findings = check_required_gitignore_patterns(tmp_path)

    assert {finding.category for finding in findings} == {"missing_gitignore_rule"}
    assert {finding.snippet for finding in findings} == {
        "texput.*",
        "*.zip",
        "/manuscript/build/submission_package/",
        "/manuscript/build/dke_preflight_package/",
    }


def test_check_required_gitignore_patterns_accepts_submission_package_rules(tmp_path: Path) -> None:
    """验证投稿包 zip 和本地构建目录已被排除时可通过检查。"""

    _write_text(
        tmp_path / ".gitignore",
        "\n".join(
            [
                "texput.*",
                "*.zip",
                "/manuscript/build/submission_package/",
                "/manuscript/build/dke_preflight_package/",
            ]
        ),
    )

    findings = check_required_gitignore_patterns(tmp_path)

    assert findings == []


def test_check_tracked_release_scope_accepts_boundary_readmes_and_pdf_previews(tmp_path: Path) -> None:
    """验证允许跟踪数据/输出说明文件和稿件预览产物。"""

    tracked_files = [
        "README.md",
        "data/README.md",
        "outputs/README.md",
        "manuscript/build/iad-risk-manuscript-latex.pdf",
        "manuscript/build/iad-risk-manuscript-elsevier.tex",
        "manuscript/build/iad-risk-manuscript-elsevier.pdf",
        "manuscript/build/iad-risk-supplementary-material.pdf",
    ]

    findings = check_tracked_release_scope(tmp_path, tracked_files=tracked_files)

    assert findings == []


def test_check_tracked_release_scope_rejects_data_outputs_and_package_artifacts(tmp_path: Path) -> None:
    """验证 Git 已跟踪的大数据、输出、模型和投稿包产物会被拦截。"""

    tracked_files = [
        "data/raw/openalex.jsonl",
        "outputs/main_run/results.csv",
        "models/checkpoint.bin",
        "manuscript/build/submission_package/submission_manifest.json",
        "manuscript/build/iad-risk-submission-package.zip",
        "release.zip",
    ]

    findings = check_tracked_release_scope(tmp_path, tracked_files=tracked_files)

    assert {finding.category for finding in findings} == {
        "tracked_data_file",
        "tracked_output_file",
        "tracked_model_file",
        "tracked_submission_build_artifact",
        "tracked_zip_artifact",
    }
    assert any(finding.snippet == "data/raw/openalex.jsonl" for finding in findings)
    assert any(finding.snippet == "outputs/main_run/results.csv" for finding in findings)
    assert any(finding.snippet == "models/checkpoint.bin" for finding in findings)
    assert any(finding.snippet == "manuscript/build/submission_package/submission_manifest.json" for finding in findings)
    assert any(finding.snippet == "manuscript/build/iad-risk-submission-package.zip" for finding in findings)
    assert any(finding.snippet == "release.zip" for finding in findings)


def test_run_public_release_check_fails_on_document_trace(tmp_path: Path) -> None:
    """验证公开发布检查会拦截文档中的工作记录。"""

    _write_required_documentation(tmp_path)
    _write_text(tmp_path / "docs" / "audit.md", "工作记录：删除无关文件。\n")

    exit_code = run_public_release_check(project_root=tmp_path, max_size_mb=10.0)

    assert exit_code == 1
