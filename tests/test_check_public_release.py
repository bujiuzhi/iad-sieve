"""测试公开发布检查脚本。"""

from __future__ import annotations

from pathlib import Path

from scripts.check_public_release import (
    DOCUMENT_TRACE_PATTERNS,
    check_docs_index_consistency,
    check_document_directory_scope,
    check_required_gitignore_patterns,
    check_required_documentation,
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


def test_check_required_gitignore_patterns_requires_texput_outputs(tmp_path: Path) -> None:
    """验证临时 Tectonic stdin 输出必须在 .gitignore 中排除。"""

    _write_text(tmp_path / ".gitignore", "*.log\n")

    findings = check_required_gitignore_patterns(tmp_path)

    assert len(findings) == 1
    assert findings[0].category == "missing_gitignore_rule"
    assert findings[0].snippet == "texput.*"


def test_run_public_release_check_fails_on_document_trace(tmp_path: Path) -> None:
    """验证公开发布检查会拦截文档中的工作记录。"""

    _write_required_documentation(tmp_path)
    _write_text(tmp_path / "docs" / "audit.md", "工作记录：删除无关文件。\n")

    exit_code = run_public_release_check(project_root=tmp_path, max_size_mb=10.0)

    assert exit_code == 1
