"""检查 iad-sieve 仓库是否适合公开发布。"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


LOGGER = logging.getLogger("iad_sieve.public_release_check")

DEFAULT_EXCLUDED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    ".ipynb_checkpoints",
    "build",
    "data",
    "dist",
    "htmlcov",
    "models",
    "outputs",
    "venv",
    ".venv",
}

DEFAULT_EXCLUDED_PATH_PARTS = {
    ("docs", "_local_archive"),
}

DEFAULT_INCLUDED_SUFFIXES = {
    ".cfg",
    ".csv",
    ".ini",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

DOCUMENTATION_SUFFIXES = {
    ".md",
    ".rst",
    ".tex",
    ".txt",
}

DOCUMENTATION_PATH_PARTS = {
    "data",
    "docs",
    "manuscript",
    "outputs",
}

LOCAL_ONLY_PATHS = (
    "data",
    "outputs",
    "models",
    "docs/_local_archive",
    "remote_connection_profile.local.json",
    "outputs/remote_connection_profile.local.json",
)

REQUIRED_GITIGNORE_PATTERNS = (
    "texput.*",
    "*.zip",
    "/manuscript/build/submission_package/",
    "/manuscript/build/dke_preflight_package/",
)

ALLOWED_DOCS_FILES = {
    "docs/README.md",
    "docs/method-design.md",
    "docs/iad-bench-contract.md",
    "docs/data-processing-pipeline.md",
    "docs/annotation-requirements.md",
    "docs/data-and-artifact-release.md",
}

DOCS_INDEX_REQUIRED_MARKERS = (
    "| 方法设计 | `method-design.md` | 查看 IAD-Risk 方法设计、关系语义和风险门控 |",
)

DOCS_INDEX_FORBIDDEN_MARKERS = (
    "查看 IAD-Sieve 的核心流程和模块",
)

ROOT_README_REPRODUCTION_REQUIRED_MARKERS = (
    "L0 code check",
    "L1 fixture rebuild",
    "L2 public-source rebuild",
    "L3 result audit",
    "L0/L1 只能证明公开仓库代码路径和小型样本处理契约可运行",
    "L2/L3 才能支持 Open-v2 数值表的结果级审计",
    "不存在单独的 L4 Git 仓库复现等级",
)

ROOT_README_REPRODUCTION_FORBIDDEN_MARKERS = (
    "| L2 | 小样本开发实验 |",
    "| L3 | 论文主实验 |",
    "| L4 | 第三方复验 |",
)


@dataclass(frozen=True)
class RiskPattern:
    """公开发布风险正则。

    参数:
        name: 风险名称。
        regex: 用于匹配风险文本的正则表达式。
        message: 面向用户的风险说明。

    返回:
        不返回值。
    """

    name: str
    regex: re.Pattern[str]
    message: str


@dataclass(frozen=True)
class Finding:
    """公开发布检查发现项。

    参数:
        path: 发现项所在路径。
        line_number: 行号；文件级发现使用 0。
        category: 风险类型。
        message: 风险说明。
        snippet: 命中的文本片段。

    返回:
        不返回值。
    """

    path: Path
    line_number: int
    category: str
    message: str
    snippet: str


HIGH_RISK_PATTERNS: tuple[RiskPattern, ...] = (
    RiskPattern(
        name="private_key",
        regex=re.compile(r"^\s*-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----\s*$"),
        message="疑似真实私钥块起始行",
    ),
    RiskPattern(
        name="openai_secret_key",
        regex=re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        message="疑似 OpenAI 或兼容服务密钥",
    ),
    RiskPattern(
        name="local_user_path",
        regex=re.compile(r"/Users/[A-Za-z0-9._-]+\b"),
        message="包含本机用户绝对路径",
    ),
    RiskPattern(
        name="remote_user_home",
        regex=re.compile(r"/home/[A-Za-z0-9._-]+\b"),
        message="包含远程用户目录",
    ),
    RiskPattern(
        name="icloud_key_path",
        regex=re.compile(r"(?:Mobile\s+Documents.+(?:key|ssh|密钥)|\u5355\u53614090)"),
        message="包含本机云盘密钥路径线索",
    ),
    RiskPattern(
        name="inline_secret_assignment",
        regex=re.compile(
            r"(?i)\b(?:password|passwd|token|api[_-]?key|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_./:+\-]{16,}"
        ),
        message="疑似明文凭据赋值",
    ),
)

DOCUMENT_TRACE_PATTERNS: tuple[RiskPattern, ...] = (
    RiskPattern(
        name="document_ai_trace_tool",
        regex=re.compile(r"(?i)\b(?:codex|chatgpt|claude|openai|gpt|llm)\b"),
        message="公开文档包含 AI 工具或辅助生成痕迹",
    ),
    RiskPattern(
        name="document_ai_trace_process",
        regex=re.compile(r"(?i)(?:AI\s*辅助|AI\s*生成|AI-assisted|AI-generated|generated\s+by\s+AI)"),
        message="公开文档包含 AI 生成或辅助说明",
    ),
    RiskPattern(
        name="document_work_record",
        regex=re.compile(r"(?:已修改|修改记录|工作记录|工作总结|本次修改|本轮修改|处理记录|变更记录)"),
        message="公开文档包含过程性修改或工作记录",
    ),
    RiskPattern(
        name="document_editorial_marker",
        regex=re.compile(r"(?i)\b(?:TODO|FIXME)\b|(?:待补|占位)"),
        message="公开文档包含未清理的编辑标记",
    ),
    RiskPattern(
        name="document_placeholder_email",
        regex=re.compile(
            r"\b(?:your[_-]?email|your\.name|user|name)@example\.(?:com|org|net)\b",
            re.IGNORECASE,
        ),
        message="公开文档包含示例邮箱；应改为环境变量或作者确认的联系邮箱",
    ),
)


def configure_logging(verbose: bool) -> None:
    """配置日志输出。

    参数:
        verbose: 是否输出调试级日志。

    返回:
        无。
    """

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")


def build_argument_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    参数:
        无。

    返回:
        argparse.ArgumentParser 实例。
    """

    parser = argparse.ArgumentParser(description="检查 iad-sieve 公开发布风险。")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="项目根目录，默认自动推断。",
    )
    parser.add_argument(
        "--max-size-mb",
        type=float,
        default=10.0,
        help="公开范围内单文件体积上限，单位 MB。",
    )
    parser.add_argument("--verbose", action="store_true", help="输出调试日志。")
    return parser


def normalize_relative_path(path: Path, project_root: Path) -> str:
    """转换为 POSIX 风格相对路径。

    参数:
        path: 待转换路径。
        project_root: 项目根目录。

    返回:
        POSIX 风格相对路径。
    """

    return path.relative_to(project_root).as_posix()


def is_excluded_directory(path: Path) -> bool:
    """判断目录是否应排除扫描。

    参数:
        path: 候选目录路径。

    返回:
        需要排除时返回 True，否则返回 False。
    """

    return path.name in DEFAULT_EXCLUDED_DIRECTORIES


def has_excluded_path_parts(path: Path, project_root: Path) -> bool:
    """判断路径是否位于本地归档等排除区域。

    参数:
        path: 候选路径。
        project_root: 项目根目录。

    返回:
        需要排除时返回 True，否则返回 False。
    """

    relative_parts = normalize_relative_path(path, project_root).split("/")
    for excluded_parts in DEFAULT_EXCLUDED_PATH_PARTS:
        if tuple(relative_parts[: len(excluded_parts)]) == excluded_parts:
            return True
    return False


def should_scan_file(path: Path, project_root: Path) -> bool:
    """判断文件是否属于公开扫描范围。

    参数:
        path: 候选文件路径。
        project_root: 项目根目录。

    返回:
        需要扫描时返回 True，否则返回 False。
    """

    if has_excluded_path_parts(path, project_root):
        return False
    return path.suffix in DEFAULT_INCLUDED_SUFFIXES


def iter_candidate_files(project_root: Path) -> Iterable[Path]:
    """遍历公开范围内的候选文件。

    参数:
        project_root: 项目根目录。

    返回:
        候选文件路径迭代器。
    """

    for current_root_text, dirnames, filenames in os.walk(project_root):
        current_root = Path(current_root_text)
        dirnames[:] = [dirname for dirname in dirnames if not is_excluded_directory(current_root / dirname)]
        for filename in filenames:
            path = current_root / filename
            if should_scan_file(path, project_root):
                yield path


def is_documentation_file(path: Path, project_root: Path) -> bool:
    """判断文件是否属于公开文档痕迹扫描范围。

    参数:
        path: 候选文件路径。
        project_root: 项目根目录。

    返回:
        属于公开文档时返回 True，否则返回 False。
    """

    if has_excluded_path_parts(path, project_root):
        return False
    if path.suffix not in DOCUMENTATION_SUFFIXES:
        return False
    relative_parts = normalize_relative_path(path, project_root).split("/")
    if len(relative_parts) == 1:
        return path.name.upper() in {"README.MD", "LICENSE", "NOTICE"}
    return relative_parts[0] in DOCUMENTATION_PATH_PARTS


def iter_documentation_files(project_root: Path) -> Iterable[Path]:
    """遍历公开文档文件。

    参数:
        project_root: 项目根目录。

    返回:
        公开文档文件路径迭代器。
    """

    for current_root_text, dirnames, filenames in os.walk(project_root):
        current_root = Path(current_root_text)
        dirnames[:] = [dirname for dirname in dirnames if not is_excluded_directory(current_root / dirname)]
        for filename in filenames:
            path = current_root / filename
            if is_documentation_file(path, project_root):
                yield path


def safe_read_lines(path: Path) -> list[str]:
    """安全读取文本文件。

    参数:
        path: 文件路径。

    返回:
        文件行列表；无法读取时返回空列表并记录日志。
    """

    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        LOGGER.warning("跳过非 UTF-8 文件: %s", path)
    except OSError as exc:
        LOGGER.exception("读取文件失败: %s", path)
        LOGGER.debug("读取异常: %s", exc)
    return []


def scan_patterns_in_files(files: Iterable[Path], patterns: Sequence[RiskPattern]) -> list[Finding]:
    """扫描指定文件中的风险模式。

    参数:
        files: 待扫描文件路径。
        patterns: 风险正则列表。

    返回:
        风险发现项列表。
    """

    findings: list[Finding] = []
    for path in files:
        for line_number, line in enumerate(safe_read_lines(path), start=1):
            for pattern in patterns:
                match = pattern.regex.search(line)
                if match is None:
                    continue
                findings.append(
                    Finding(
                        path=path,
                        line_number=line_number,
                        category=pattern.name,
                        message=pattern.message,
                        snippet=match.group(0),
                    )
                )
    return findings


def scan_sensitive_patterns(project_root: Path, patterns: Sequence[RiskPattern]) -> list[Finding]:
    """扫描敏感信息和本机路径。

    参数:
        project_root: 项目根目录。
        patterns: 风险正则列表。

    返回:
        风险发现项列表。
    """

    return scan_patterns_in_files(iter_candidate_files(project_root), patterns)


def scan_document_traces(project_root: Path, patterns: Sequence[RiskPattern]) -> list[Finding]:
    """扫描公开文档中的 AI 痕迹和过程性记录。

    参数:
        project_root: 项目根目录。
        patterns: 文档痕迹正则列表。

    返回:
        风险发现项列表。
    """

    return scan_patterns_in_files(iter_documentation_files(project_root), patterns)


def check_required_documentation(project_root: Path) -> list[Finding]:
    """检查公开文档目录是否保留必要说明文件。

    参数:
        project_root: 项目根目录。

    返回:
        缺失文档发现项列表。
    """

    required_paths = (
        "README.md",
        "data/README.md",
        "docs/README.md",
        "outputs/README.md",
        "manuscript/README.md",
        "manuscript/MANIFEST.md",
    )
    findings: list[Finding] = []
    for relative_path in required_paths:
        path = project_root / relative_path
        if path.exists():
            continue
        findings.append(
            Finding(
                path=path,
                line_number=0,
                category="missing_required_document",
                message="缺少公开仓库必要说明文档",
                snippet=relative_path,
            )
        )
    return findings


def check_document_directory_scope(project_root: Path) -> list[Finding]:
    """检查 docs 目录是否只包含课题相关公开文档。

    参数:
        project_root: 项目根目录。

    返回:
        清单外文档发现项列表。
    """

    docs_dir = project_root / "docs"
    if not docs_dir.exists():
        return []

    findings: list[Finding] = []
    for current_root_text, dirnames, filenames in os.walk(docs_dir):
        current_root = Path(current_root_text)
        dirnames[:] = [dirname for dirname in dirnames if not is_excluded_directory(current_root / dirname)]
        if has_excluded_path_parts(current_root, project_root):
            continue
        for filename in filenames:
            path = current_root / filename
            if has_excluded_path_parts(path, project_root):
                continue
            relative_path = normalize_relative_path(path, project_root)
            if relative_path in ALLOWED_DOCS_FILES:
                continue
            findings.append(
                Finding(
                    path=path,
                    line_number=0,
                    category="unexpected_documentation_file",
                    message="docs 目录只能保留本课题公开技术文档清单内的文件",
                    snippet=relative_path,
                )
            )
    return findings


def check_docs_index_consistency(project_root: Path) -> list[Finding]:
    """检查 docs 索引是否与当前论文方法主线一致。

    参数:
        project_root: 项目根目录。

    返回:
        docs 索引内容不一致时返回发现项列表。
    """

    docs_index_path = project_root / "docs" / "README.md"
    if not docs_index_path.exists():
        return []

    index_text = "\n".join(safe_read_lines(docs_index_path))
    findings: list[Finding] = []
    for marker in DOCS_INDEX_REQUIRED_MARKERS:
        if marker in index_text:
            continue
        findings.append(
            Finding(
                path=docs_index_path,
                line_number=0,
                category="docs_index_missing_marker",
                message="docs 索引缺少当前 IAD-Risk 方法主线说明",
                snippet=marker,
            )
        )
    for marker in DOCS_INDEX_FORBIDDEN_MARKERS:
        if marker not in index_text:
            continue
        findings.append(
            Finding(
                path=docs_index_path,
                line_number=0,
                category="docs_index_stale_marker",
                message="docs 索引包含过期方法描述",
                snippet=marker,
            )
        )
    return findings


def check_root_readme_reproduction_levels(project_root: Path) -> list[Finding]:
    """检查根 README 是否使用当前论文一致的复现等级。

    参数:
        project_root: 项目根目录。

    返回:
        根 README 复现等级不一致时返回发现项列表。
    """

    readme_path = project_root / "README.md"
    if not readme_path.exists():
        return []

    readme_text = "\n".join(safe_read_lines(readme_path))
    findings: list[Finding] = []
    for marker in ROOT_README_REPRODUCTION_REQUIRED_MARKERS:
        if marker in readme_text:
            continue
        findings.append(
            Finding(
                path=readme_path,
                line_number=0,
                category="root_readme_reproduction_missing_marker",
                message="根 README 缺少当前复现等级边界说明",
                snippet=marker,
            )
        )
    for marker in ROOT_README_REPRODUCTION_FORBIDDEN_MARKERS:
        if marker not in readme_text:
            continue
        findings.append(
            Finding(
                path=readme_path,
                line_number=0,
                category="root_readme_reproduction_stale_marker",
                message="根 README 包含旧版复现等级表述",
                snippet=marker,
            )
        )
    return findings


def check_required_gitignore_patterns(project_root: Path) -> list[Finding]:
    """检查临时构建产物是否被 .gitignore 明确排除。

    参数:
        project_root: 项目根目录。

    返回:
        缺失 ignore 规则发现项列表。
    """

    gitignore_path = project_root / ".gitignore"
    gitignore_text = "\n".join(safe_read_lines(gitignore_path)) if gitignore_path.exists() else ""
    findings: list[Finding] = []
    for pattern in REQUIRED_GITIGNORE_PATTERNS:
        if pattern in gitignore_text:
            continue
        findings.append(
            Finding(
                path=gitignore_path,
                line_number=0,
                category="missing_gitignore_rule",
                message="缺少临时构建产物忽略规则",
                snippet=pattern,
            )
        )
    return findings


def find_large_files(project_root: Path, max_size_mb: float) -> list[Finding]:
    """查找公开范围内的大文件。

    参数:
        project_root: 项目根目录。
        max_size_mb: 单文件体积上限，单位 MB。

    返回:
        大文件发现项列表。
    """

    max_size_bytes = int(max_size_mb * 1024 * 1024)
    findings: list[Finding] = []
    for path in iter_candidate_files(project_root):
        try:
            size_bytes = path.stat().st_size
        except OSError as exc:
            LOGGER.exception("读取文件大小失败: %s", path)
            LOGGER.debug("文件大小异常: %s", exc)
            continue
        if size_bytes > max_size_bytes:
            findings.append(
                Finding(
                    path=path,
                    line_number=0,
                    category="large_file",
                    message=f"公开范围内文件超过 {max_size_mb:.1f} MB",
                    snippet=f"{size_bytes / 1024 / 1024:.2f} MB",
                )
            )
    return findings


def find_local_only_paths(project_root: Path) -> list[Path]:
    """查找存在但不应公开提交的本地路径。

    参数:
        project_root: 项目根目录。

    返回:
        已存在的本地路径列表。
    """

    existing_paths: list[Path] = []
    for relative_path in LOCAL_ONLY_PATHS:
        path = project_root / relative_path
        if path.exists():
            existing_paths.append(path)
    return existing_paths


def format_finding(finding: Finding, project_root: Path) -> str:
    """格式化单条发现项。

    参数:
        finding: 风险发现项。
        project_root: 项目根目录。

    返回:
        可读的发现项文本。
    """

    relative_path = normalize_relative_path(finding.path, project_root)
    location = relative_path if finding.line_number == 0 else f"{relative_path}:{finding.line_number}"
    return f"- [{finding.category}] {location}: {finding.message} ({finding.snippet})"


def run_public_release_check(project_root: Path, max_size_mb: float) -> int:
    """执行公开发布检查。

    参数:
        project_root: 项目根目录。
        max_size_mb: 公开范围内单文件体积上限，单位 MB。

    返回:
        发现高风险问题时返回 1，否则返回 0。
    """

    resolved_root = project_root.resolve()
    if not resolved_root.exists():
        LOGGER.error("项目根目录不存在: %s", resolved_root)
        return 1

    LOGGER.info("扫描项目: %s", resolved_root)
    sensitive_findings = scan_sensitive_patterns(resolved_root, HIGH_RISK_PATTERNS)
    document_trace_findings = scan_document_traces(resolved_root, DOCUMENT_TRACE_PATTERNS)
    missing_document_findings = check_required_documentation(resolved_root)
    unexpected_document_findings = check_document_directory_scope(resolved_root)
    docs_index_findings = check_docs_index_consistency(resolved_root)
    root_readme_reproduction_findings = check_root_readme_reproduction_levels(resolved_root)
    gitignore_findings = check_required_gitignore_patterns(resolved_root)
    large_file_findings = find_large_files(resolved_root, max_size_mb)
    high_risk_findings = (
        sensitive_findings
        + document_trace_findings
        + missing_document_findings
        + unexpected_document_findings
        + docs_index_findings
        + root_readme_reproduction_findings
        + gitignore_findings
        + large_file_findings
    )

    local_only_paths = find_local_only_paths(resolved_root)
    if local_only_paths:
        print("本地存在但不应提交的路径:")
        for path in local_only_paths:
            print(f"- {normalize_relative_path(path, resolved_root)}")
        print()

    if high_risk_findings:
        print("公开发布检查未通过:")
        for finding in high_risk_findings:
            print(format_finding(finding, resolved_root))
        return 1

    print("公开发布检查通过: 未在公开扫描范围内发现高风险敏感信息或大文件。")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """命令行入口。

    参数:
        argv: 命令行参数列表；为 None 时读取 sys.argv。

    返回:
        进程退出码。
    """

    parser = build_argument_parser()
    args = parser.parse_args(argv)
    configure_logging(verbose=args.verbose)
    try:
        return run_public_release_check(project_root=args.project_root, max_size_mb=args.max_size_mb)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("公开发布检查异常")
        LOGGER.debug("异常详情: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
