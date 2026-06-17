"""标题和摘要标准化模块。"""

from __future__ import annotations

import hashlib
import html
import logging
import re
import unicodedata


LOGGER = logging.getLogger(__name__)
MATH_PATTERN = re.compile(r"\$[^$]*\$|\\\([^)]*\\\)|\\\[[^\]]*\\\]")
LATEX_COMMAND_PATTERN = re.compile(r"\\[a-zA-Z]+\{([^{}]*)\}")
GENERIC_LATEX_COMMAND_PATTERN = re.compile(r"\\[a-zA-Z]+")
SPACE_PATTERN = re.compile(r"\s+")
NON_FINGERPRINT_PATTERN = re.compile(r"[^a-z0-9]+")
GREEK_MAP = {
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "δ": "delta",
    "λ": "lambda",
    "μ": "mu",
}


def _clean_latex(text: str) -> str:
    """清洗轻量 LaTeX 标记。

    参数:
        text: 输入文本。

    返回:
        清洗后的文本。
    """
    text = MATH_PATTERN.sub(" <math> ", text)
    text = LATEX_COMMAND_PATTERN.sub(r"\1", text)
    return GENERIC_LATEX_COMMAND_PATTERN.sub(" ", text)


def normalize_title(title: str | None) -> str:
    """标准化标题。

    参数:
        title: 原始标题。

    返回:
        标准化标题。
    """
    if not title:
        return ""
    try:
        normalized = unicodedata.normalize("NFKC", html.unescape(title)).replace("\\n", " ")
        normalized = _clean_latex(normalized)
        for greek, replacement in GREEK_MAP.items():
            normalized = normalized.replace(greek, replacement)
        normalized = normalized.replace("–", "-").replace("—", "-").replace("--", "-")
        normalized = SPACE_PATTERN.sub(" ", normalized).strip().lower()
        return normalized
    except Exception:
        LOGGER.exception("标题标准化失败")
        raise


def normalize_abstract(abstract: str | None) -> str:
    """标准化摘要。

    参数:
        abstract: 原始摘要。

    返回:
        标准化摘要。
    """
    if not abstract:
        return ""
    try:
        normalized = unicodedata.normalize("NFKC", html.unescape(abstract)).replace("\\n", " ")
        normalized = re.sub(r"^\s*abstract\s*:\s*", "", normalized, flags=re.IGNORECASE)
        normalized = _clean_latex(normalized)
        normalized = SPACE_PATTERN.sub(" ", normalized).strip().lower()
        return normalized
    except Exception:
        LOGGER.exception("摘要标准化失败")
        raise


def build_title_fingerprint(title: str | None) -> str:
    """生成标题指纹。

    参数:
        title: 原始或标准化标题。

    返回:
        仅包含小写字母、数字和下划线的标题指纹。
    """
    normalized = normalize_title(title)
    fingerprint = NON_FINGERPRINT_PATTERN.sub("_", normalized).strip("_")
    return re.sub(r"_+", "_", fingerprint)


def build_content_hash(title: str | None, abstract: str | None) -> str:
    """生成标题摘要内容哈希。

    参数:
        title: 标题。
        abstract: 摘要。

    返回:
        SHA1 哈希前 16 位。
    """
    payload = f"{normalize_title(title)}\n{normalize_abstract(abstract)}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:16]
