"""规则式语义视图抽取模块。"""

from __future__ import annotations

import logging

from iad_sieve.preprocessing.text_normalizer import normalize_abstract, normalize_title
from iad_sieve.views.keyphrase_extractor import extract_keyphrases
from iad_sieve.views.sentence_role_detector import detect_sentence_roles, split_sentences


LOGGER = logging.getLogger(__name__)
VIEW_FIELDS = ["problem", "method", "object", "result", "background"]


def extract_semantic_view(record: dict) -> dict:
    """抽取单篇文献的多语义视图。

    参数:
        record: 标准化文献记录。

    返回:
        semantic_views 字段字典。
    """
    try:
        document_id = record.get("document_id", "")
        title_view = normalize_title(record.get("title_normalized") or record.get("title", ""))
        abstract = normalize_abstract(record.get("abstract_normalized") or record.get("abstract", ""))
        buckets = {field: [] for field in VIEW_FIELDS}
        sentences = split_sentences(abstract)
        for sentence in sentences:
            roles = detect_sentence_roles(sentence)
            for role in roles:
                buckets[role].append(sentence)
        full_text = f"{title_view} {abstract}"
        result = {
            "document_id": document_id,
            "title_view": title_view,
            "problem_view": " ".join(buckets["problem"]),
            "method_view": " ".join(buckets["method"]),
            "object_view": " ".join(buckets["object"]),
            "result_view": " ".join(buckets["result"]),
            "background_view": " ".join(buckets["background"]),
            "keyphrases": extract_keyphrases(full_text),
        }
        sentence_count = max(1, len(sentences))
        for field in ["problem", "method", "object", "result"]:
            result[f"conf_{field}"] = min(1.0, len(buckets[field]) / sentence_count)
        return result
    except Exception:
        LOGGER.exception("语义视图抽取失败: %s", record.get("document_id", ""))
        raise


def build_semantic_views(records: list[dict]) -> list[dict]:
    """批量抽取语义视图。

    参数:
        records: 标准化文献列表。

    返回:
        语义视图列表。
    """
    return [extract_semantic_view(record) for record in records]
