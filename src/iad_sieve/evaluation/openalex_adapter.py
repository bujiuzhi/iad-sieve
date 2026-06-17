"""OpenAlex/OpenCitations 弱监督评估集适配模块。"""

from __future__ import annotations

import csv
import json
import logging
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Iterable

from iad_sieve.utils.io_utils import read_jsonl


LOGGER = logging.getLogger(__name__)


def _clean_text(value: object) -> str:
    """清理文本字段。

    参数:
        value: 原始字段值。

    返回:
        去除多余空白后的字符串。
    """
    return " ".join(str(value or "").split())


def _first_non_empty(record: dict, fields: list[str]) -> object:
    """读取第一个非空字段。

    参数:
        record: 输入记录。
        fields: 候选字段名。

    返回:
        字段值；全部缺失时返回空字符串。
    """
    for field in fields:
        value = record.get(field)
        if value is not None and value != "":
            return value
    return ""


def _short_openalex_id(value: object) -> str:
    """提取 OpenAlex 短 ID。

    参数:
        value: OpenAlex URL、短 ID 或其他标识符。

    返回:
        短 ID 字符串。
    """
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    return cleaned.rstrip("/").split("/")[-1]


def _normalize_doi(value: object) -> str:
    """标准化 DOI。

    参数:
        value: DOI URL、doi: 前缀或裸 DOI。

    返回:
        小写裸 DOI；缺失时返回空字符串。
    """
    cleaned = _clean_text(value).lower()
    for prefix in ["https://doi.org/", "http://doi.org/", "doi:"]:
        if cleaned.startswith(prefix):
            return cleaned[len(prefix) :]
    return cleaned


def _parse_year(value: object) -> int | None:
    """解析年份。

    参数:
        value: 原始年份值。

    返回:
        四位年份；无法解析时返回 None。
    """
    match = re.search(r"(19|20)\d{2}", str(value or ""))
    if not match:
        return None
    return int(match.group(0))


def _read_tabular_records(path: str | Path, limit: int | None = None) -> list[dict]:
    """读取 JSONL、JSON 或 CSV 记录。

    参数:
        path: 输入文件路径。
        limit: 最多读取记录数。

    返回:
        记录列表。
    """
    input_path = Path(path)
    try:
        if input_path.suffix == ".jsonl":
            return list(read_jsonl(input_path, limit=limit))
        if input_path.suffix == ".json":
            payload = json.loads(input_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                records = [dict(record) for record in payload]
            elif isinstance(payload, dict):
                records = [dict(record) for record in payload.get("results", payload.get("data", [payload]))]
            else:
                records = []
            return records[:limit] if limit is not None else records
        with input_path.open("r", encoding="utf-8", newline="") as file:
            records = [dict(row) for row in csv.DictReader(file)]
        return records[:limit] if limit is not None else records
    except Exception:
        LOGGER.exception("读取 OpenAlex/OpenCitations 文件失败: %s", path)
        raise


def _restore_abstract_from_inverted_index(value: object) -> str:
    """从 OpenAlex abstract_inverted_index 还原摘要文本。

    参数:
        value: OpenAlex abstract_inverted_index 字段。

    返回:
        按词位排序后的摘要文本。
    """
    if not isinstance(value, dict):
        return _clean_text(value)
    positioned_terms: list[tuple[int, str]] = []
    for term, positions in value.items():
        if not isinstance(positions, list):
            continue
        for position in positions:
            try:
                positioned_terms.append((int(position), str(term)))
            except (TypeError, ValueError):
                LOGGER.warning("OpenAlex abstract_inverted_index 位置非法: term=%s position=%r", term, position)
    return " ".join(term for _, term in sorted(positioned_terms))


def _parse_authors(authorships: object) -> list[str]:
    """解析 OpenAlex authorships 字段。

    参数:
        authorships: OpenAlex authorships 列表。

    返回:
        作者名列表。
    """
    if not isinstance(authorships, list):
        return []
    authors: list[str] = []
    for authorship in authorships:
        if not isinstance(authorship, dict):
            continue
        author = authorship.get("author")
        name = ""
        if isinstance(author, dict):
            name = _clean_text(_first_non_empty(author, ["display_name", "name", "id"]))
        if not name:
            name = _clean_text(_first_non_empty(authorship, ["raw_author_name", "author_name"]))
        if name:
            authors.append(name)
    return authors


def _topic_id(topic: object) -> str:
    """读取 topic 短 ID。

    参数:
        topic: OpenAlex topic 字段。

    返回:
        topic 短 ID。
    """
    if isinstance(topic, dict):
        return _short_openalex_id(topic.get("id", ""))
    return _short_openalex_id(topic)


def _topic_categories(work: dict) -> tuple[str, list[str]]:
    """生成文献 topic 分类字段。

    参数:
        work: OpenAlex Work 记录。

    返回:
        primary_category 和 categories 列表。
    """
    topic_ids: list[str] = []
    primary_topic_id = _topic_id(work.get("primary_topic"))
    if primary_topic_id:
        topic_ids.append(primary_topic_id)
    topics = work.get("topics")
    if isinstance(topics, list):
        for topic in topics:
            topic_id = _topic_id(topic)
            if topic_id and topic_id not in topic_ids:
                topic_ids.append(topic_id)
    categories = [f"openalex:{topic_id}" for topic_id in topic_ids] or ["openalex:unknown"]
    return categories[0], categories


def _reference_ids(work: dict) -> set[str]:
    """读取 OpenAlex 引用目标集合。

    参数:
        work: OpenAlex Work 记录。

    返回:
        引用目标 ID 集合。
    """
    references = work.get("referenced_works")
    if not isinstance(references, list):
        return set()
    return {_short_openalex_id(reference) for reference in references if _short_openalex_id(reference)}


def _document_id(dataset_name: str, openalex_id: str) -> str:
    """构造 OpenAlex 内部文献 ID。

    参数:
        dataset_name: 数据集名称。
        openalex_id: OpenAlex Work 短 ID。

    返回:
        项目内部 document_id。
    """
    safe_dataset = _clean_text(dataset_name).replace(" ", "_")
    return f"openalex:{safe_dataset}:{openalex_id}"


def read_openalex_works(path: str | Path, dataset_name: str, limit: int | None = None) -> list[dict]:
    """读取 OpenAlex Works 并转换为标准文献记录。

    参数:
        path: OpenAlex Works JSONL/JSON/CSV 文件。
        dataset_name: 数据集名称。
        limit: 最多读取记录数。

    返回:
        标准化文献记录列表。
    """
    documents: list[dict] = []
    for work in _read_tabular_records(path, limit=limit):
        raw_openalex_id = _short_openalex_id(_first_non_empty(work, ["id", "openalex_id", "work_id"]))
        if not raw_openalex_id:
            LOGGER.warning("OpenAlex work 缺少 id，跳过: %s", work)
            continue
        title = _clean_text(_first_non_empty(work, ["display_name", "title", "name"]))
        abstract = _restore_abstract_from_inverted_index(_first_non_empty(work, ["abstract_inverted_index", "abstract", "text"]))
        primary_category, categories = _topic_categories(work)
        documents.append(
            {
                "document_id": _document_id(dataset_name, raw_openalex_id),
                "source_dataset": dataset_name,
                "source_record_id": raw_openalex_id,
                "title": title,
                "title_normalized": title.lower(),
                "abstract": abstract,
                "abstract_normalized": abstract.lower(),
                "authors": _parse_authors(work.get("authorships")),
                "categories": categories,
                "primary_category": primary_category,
                "publication_year": _parse_year(_first_non_empty(work, ["publication_year", "year", "publication_date"])),
                "doi": _normalize_doi(_first_non_empty(work, ["doi", "DOI"])),
                "arxiv_id": "",
                "journal_ref": "",
                "version_count": 1,
                "withdrawn_flag": False,
                "metadata_json": {
                    "openalex_id": raw_openalex_id,
                    "openalex_row": work,
                    "referenced_work_ids": sorted(_reference_ids(work)),
                },
            }
        )
    LOGGER.info("OpenAlex Works 读取完成: path=%s records=%s", path, len(documents))
    return documents


def _citation_edges_by_doi(path: str | Path) -> tuple[dict[str, set[str]], int]:
    """读取 OpenCitations COCI 风格 DOI-to-DOI 引用边。

    参数:
        path: CSV 文件路径，支持 citing/cited 或 citing_doi/cited_doi 字段。

    返回:
        citing DOI 到 cited DOI 集合的映射，以及有效边数量。
    """
    edges: dict[str, set[str]] = defaultdict(set)
    edge_count = 0
    for row in _read_tabular_records(path):
        citing_doi = _normalize_doi(_first_non_empty(row, ["citing", "citing_doi", "source_doi", "from_doi"]))
        cited_doi = _normalize_doi(_first_non_empty(row, ["cited", "cited_doi", "target_doi", "to_doi"]))
        if not citing_doi or not cited_doi:
            LOGGER.warning("OpenCitations 引用边缺少 DOI，跳过: %s", row)
            continue
        edges[citing_doi].add(f"doi:{cited_doi}")
        edge_count += 1
    return edges, edge_count


def _augment_references_with_citations(documents: list[dict], citations_path: str | Path | None) -> int:
    """用 OpenCitations 引用边补充文献引用集合。

    参数:
        documents: 标准化文献记录。
        citations_path: 可选 OpenCitations CSV 路径。

    返回:
        有效引用边数量。
    """
    if citations_path is None:
        return 0
    edges_by_doi, edge_count = _citation_edges_by_doi(citations_path)
    for document in documents:
        doi = _normalize_doi(document.get("doi"))
        if not doi or doi not in edges_by_doi:
            continue
        metadata = dict(document.get("metadata_json", {}))
        references = set(metadata.get("referenced_work_ids", []))
        references.update(edges_by_doi[doi])
        metadata["referenced_work_ids"] = sorted(references)
        document["metadata_json"] = metadata
    return edge_count


def _shared_references(left_document: dict, right_document: dict) -> set[str]:
    """计算两篇文献共享引用集合。

    参数:
        left_document: 左侧文献记录。
        right_document: 右侧文献记录。

    返回:
        共享引用 ID 集合。
    """
    left_refs = set(left_document.get("metadata_json", {}).get("referenced_work_ids", []))
    right_refs = set(right_document.get("metadata_json", {}).get("referenced_work_ids", []))
    return left_refs & right_refs


def _is_identity_conflict(left_document: dict, right_document: dict) -> bool:
    """判断两篇文献是否可作为非同身份弱标签。

    参数:
        left_document: 左侧文献记录。
        right_document: 右侧文献记录。

    返回:
        True 表示可认为不是同一身份；False 表示应跳过。
    """
    if left_document["document_id"] == right_document["document_id"]:
        return False
    left_doi = _normalize_doi(left_document.get("doi"))
    right_doi = _normalize_doi(right_document.get("doi"))
    if left_doi and right_doi and left_doi == right_doi:
        return False
    return True


def _source_labels(shared_references: set[str]) -> list[str]:
    """生成候选来源标签。

    参数:
        shared_references: 共享引用集合。

    返回:
        candidate_sources 列表。
    """
    if any(reference.startswith("doi:") for reference in shared_references):
        return ["openalex_topic", "opencitations_shared_citation"]
    return ["openalex_topic", "openalex_shared_references"]


def build_openalex_agenda_non_identity_pairs(
    documents: list[dict],
    min_shared_references: int = 1,
    max_pairs_per_topic: int = 200,
    max_pairs: int | None = None,
    require_opencitations: bool = False,
) -> list[dict]:
    """构造 OpenAlex agenda_non_identity 弱监督 pair。

    参数:
        documents: 标准化 OpenAlex 文献记录。
        min_shared_references: 最少共享引用数。
        max_pairs_per_topic: 每个 primary topic 最多输出 pair 数。
        max_pairs: 全局最多输出 pair 数。
        require_opencitations: 是否要求共享引用中至少包含一个 DOI 引用边。

    返回:
        评估 pair 记录列表。
    """
    documents_by_topic: dict[str, list[dict]] = defaultdict(list)
    for document in documents:
        documents_by_topic[str(document.get("primary_category", "openalex:unknown"))].append(document)
    pairs: list[dict] = []
    for topic, topic_documents in sorted(documents_by_topic.items()):
        topic_pair_count = 0
        for left_document, right_document in combinations(sorted(topic_documents, key=lambda record: record["document_id"]), 2):
            if max_pairs is not None and len(pairs) >= max_pairs:
                return pairs
            if topic_pair_count >= max_pairs_per_topic:
                break
            if not _is_identity_conflict(left_document, right_document):
                continue
            shared_references = _shared_references(left_document, right_document)
            if len(shared_references) < min_shared_references:
                continue
            if require_opencitations and not any(reference.startswith("doi:") for reference in shared_references):
                continue
            raw_similarity = min(1.0, len(shared_references) / max(1, min_shared_references))
            pairs.append(
                {
                    "source_document_id": left_document["document_id"],
                    "target_document_id": right_document["document_id"],
                    "candidate_sources": _source_labels(shared_references),
                    "raw_similarity": raw_similarity,
                    "expected_label": 0,
                    "expected_agenda_label": 1,
                    "label_type": "openalex_agenda_non_identity_weak",
                    "label_reason": "same_openalex_topic_shared_references_different_doi",
                    "primary_topic": topic,
                    "shared_reference_count": len(shared_references),
                    "shared_references": sorted(shared_references),
                }
            )
            topic_pair_count += 1
    LOGGER.info("OpenAlex agenda_non_identity weak pair 构造完成: pairs=%s", len(pairs))
    return pairs


def _filter_needed_documents(documents: Iterable[dict], pairs: Iterable[dict]) -> list[dict]:
    """筛选评估 pair 需要的文献。

    参数:
        documents: 标准化文献记录。
        pairs: 评估 pair 记录。

    返回:
        文献列表。
    """
    document_lookup = {document["document_id"]: document for document in documents}
    needed_ids = {pair["source_document_id"] for pair in pairs} | {pair["target_document_id"] for pair in pairs}
    return [document_lookup[document_id] for document_id in sorted(needed_ids) if document_id in document_lookup]


def prepare_openalex_weak_label_evaluation_set(
    works_path: str | Path,
    dataset_name: str,
    citations_path: str | Path | None = None,
    min_shared_references: int = 1,
    max_pairs_per_topic: int = 200,
    max_pairs: int | None = None,
    limit: int | None = None,
    require_opencitations: bool = False,
) -> tuple[list[dict], list[dict], dict]:
    """构造 OpenAlex/OpenCitations agenda_non_identity 弱监督评估集。

    参数:
        works_path: OpenAlex Works JSONL/JSON/CSV 文件。
        dataset_name: 数据集名称。
        citations_path: 可选 OpenCitations COCI 风格 CSV 文件。
        min_shared_references: 最少共享引用数。
        max_pairs_per_topic: 每个 primary topic 最多输出 pair 数。
        max_pairs: 全局最多输出 pair 数。
        limit: 最多读取 Work 记录数。
        require_opencitations: 是否只保留共享 DOI 引用边支持的 pair。

    返回:
        评估文献、评估 pair 和摘要字典。
    """
    all_documents = read_openalex_works(works_path, dataset_name, limit=limit)
    citation_edge_count = _augment_references_with_citations(all_documents, citations_path)
    pairs = build_openalex_agenda_non_identity_pairs(
        all_documents,
        min_shared_references=min_shared_references,
        max_pairs_per_topic=max_pairs_per_topic,
        max_pairs=max_pairs,
        require_opencitations=require_opencitations,
    )
    documents = _filter_needed_documents(all_documents, pairs)
    summary = {
        "dataset_name": dataset_name,
        "source_work_count": len(all_documents),
        "document_count": len(documents),
        "pair_count": len(pairs),
        "agenda_non_identity_pair_count": len(pairs),
        "duplicate_positive_pair_count": 0,
        "citation_edge_count": citation_edge_count,
        "label_type": "same_agenda_weak_as_non_duplicate",
        "min_shared_references": min_shared_references,
        "max_pairs_per_topic": max_pairs_per_topic,
        "max_pairs": max_pairs,
        "require_opencitations": require_opencitations,
    }
    return documents, pairs, summary
