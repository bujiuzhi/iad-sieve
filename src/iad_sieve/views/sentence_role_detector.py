"""摘要句子角色检测模块。"""

from __future__ import annotations

import logging
import re


LOGGER = logging.getLogger(__name__)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
ROLE_KEYWORDS = {
    "problem": ["address", "investigate", "study", "task", "challenge", "problem", "aim", "objective"],
    "method": ["propose", "introduce", "develop", "present", "framework", "model", "algorithm", "approach"],
    "object": ["dataset", "benchmark", "corpus", "graph", "network", "image", "document", "papers"],
    "result": ["outperform", "improve", "improved", "achieve", "results show", "experiments demonstrate", "show"],
    "background": ["recent", "widely", "important", "has attracted", "increasingly"],
}


def split_sentences(text: str | None) -> list[str]:
    """切分英文摘要句子。

    参数:
        text: 输入摘要。

    返回:
        句子列表。
    """
    if not text:
        return []
    return [sentence.strip() for sentence in SENTENCE_SPLIT_PATTERN.split(text) if sentence.strip()]


def detect_sentence_roles(sentence: str) -> set[str]:
    """检测单句角色。

    参数:
        sentence: 摘要句子。

    返回:
        角色集合。
    """
    lowered = sentence.lower()
    roles: set[str] = set()
    for role, keywords in ROLE_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            roles.add(role)
    return roles
