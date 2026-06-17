"""SciRepEval/SciDocs proximity 数据适配模块。"""

from __future__ import annotations

import csv
import json
import logging
import re
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
    if isinstance(value, list):
        return " ".join(_clean_text(item) for item in value if _clean_text(item))
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


def _parse_authors(value: object) -> list[str]:
    """解析作者字段。

    参数:
        value: 原始作者字段。

    返回:
        作者字符串列表。
    """
    if isinstance(value, list):
        authors: list[str] = []
        for item in value:
            if isinstance(item, dict):
                name = _clean_text(_first_non_empty(item, ["name", "author", "full_name"]))
                if name:
                    authors.append(name)
            else:
                name = _clean_text(item)
                if name:
                    authors.append(name)
        return authors
    cleaned = _clean_text(value)
    if not cleaned:
        return []
    if ";" in cleaned:
        return [_clean_text(author) for author in cleaned.split(";") if _clean_text(author)]
    if "|" in cleaned:
        return [_clean_text(author) for author in cleaned.split("|") if _clean_text(author)]
    if " and " in cleaned.lower():
        return [_clean_text(author) for author in re.split(r"\s+and\s+", cleaned, flags=re.IGNORECASE) if _clean_text(author)]
    return [cleaned]


def _read_tabular_records(path: str | Path) -> list[dict]:
    """读取 JSONL、JSON 或 CSV 记录。

    参数:
        path: 输入文件路径。

    返回:
        记录列表。
    """
    input_path = Path(path)
    try:
        if input_path.suffix == ".jsonl":
            return list(read_jsonl(input_path))
        if input_path.suffix == ".json":
            payload = json.loads(input_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return [dict(record) for record in payload]
            if isinstance(payload, dict):
                for field in ["data", "records", "examples", "rows"]:
                    value = payload.get(field)
                    if isinstance(value, list):
                        return [dict(record) for record in value]
                return [payload]
        with input_path.open("r", encoding="utf-8", newline="") as file:
            return [dict(row) for row in csv.DictReader(file)]
    except Exception:
        LOGGER.exception("读取 SciRepEval/SciDocs 文件失败: %s", path)
        raise
    raise ValueError(f"不支持的 SciRepEval/SciDocs 文件格式: {path}")


def _document_id(dataset_name: str, raw_id: object) -> str:
    """构造内部文献 ID。

    参数:
        dataset_name: 数据集名称。
        raw_id: 原始论文 ID。

    返回:
        项目内部 document_id。
    """
    safe_dataset = _clean_text(dataset_name).replace(" ", "_")
    safe_id = _clean_text(raw_id)
    return f"scirepeval:{safe_dataset}:{safe_id}"


def read_scirepeval_metadata(path: str | Path, dataset_name: str) -> list[dict]:
    """读取 SciRepEval/SciDocs metadata 并转换为标准文献记录。

    参数:
        path: metadata JSONL/JSON/CSV 文件。
        dataset_name: 数据集名称。

    返回:
        标准化文献记录列表。
    """
    documents: list[dict] = []
    for row in _read_tabular_records(path):
        raw_id = _first_non_empty(row, ["paper_id", "corpus_id", "doc_id", "document_id", "id", "pid"])
        if not raw_id:
            LOGGER.warning("SciRepEval metadata 缺少论文 ID，跳过: %s", row)
            continue
        title = _clean_text(_first_non_empty(row, ["title", "paper_title", "name"]))
        abstract = _clean_text(_first_non_empty(row, ["abstract", "paper_abstract", "text"]))
        authors = _parse_authors(_first_non_empty(row, ["authors", "author", "author_names"]))
        venue = _clean_text(_first_non_empty(row, ["venue", "journal", "journal_ref", "source"]))
        year = _parse_year(_first_non_empty(row, ["year", "publication_year", "pub_year"]))
        document_id = _document_id(dataset_name, raw_id)
        documents.append(
            {
                "document_id": document_id,
                "source_dataset": dataset_name,
                "source_record_id": _clean_text(raw_id),
                "title": title,
                "title_normalized": title.lower(),
                "abstract": abstract,
                "abstract_normalized": abstract.lower(),
                "authors": authors,
                "categories": ["scirepeval_proximity"],
                "primary_category": "scirepeval_proximity",
                "publication_year": year,
                "doi": _clean_text(_first_non_empty(row, ["doi", "DOI"])),
                "arxiv_id": _clean_text(_first_non_empty(row, ["arxiv_id", "arxiv"])),
                "journal_ref": venue,
                "version_count": 1,
                "withdrawn_flag": False,
                "metadata_json": {"scirepeval_row": row},
            }
        )
    LOGGER.info("SciRepEval metadata 读取完成: path=%s records=%s", path, len(documents))
    return documents


def _score_from_record(row: dict) -> float:
    """从 pair 记录读取相关性分数。

    参数:
        row: pair 记录。

    返回:
        相关性分数，缺失时相关 pair 默认 1。
    """
    raw_value = _first_non_empty(row, ["score", "relevance", "label", "gold", "weight"])
    if raw_value == "":
        return 1.0
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        normalized = _clean_text(raw_value).lower()
        return 1.0 if normalized in {"true", "yes", "y", "relevant", "positive"} else 0.0


def _pair_ids_from_record(row: dict) -> tuple[object, object] | None:
    """从 pair 记录解析左右论文 ID。

    参数:
        row: pair 记录。

    返回:
        原始左右 ID；缺失时返回 None。
    """
    left_id = _first_non_empty(row, ["query_id", "source_id", "source_paper_id", "anchor_id", "paper_id", "pid1", "from_id"])
    right_id = _first_non_empty(row, ["candidate_id", "target_id", "target_paper_id", "positive_id", "cited_paper_id", "pid2", "to_id"])
    if left_id and right_id:
        return left_id, right_id
    return None


def read_scirepeval_proximity_pairs(
    path: str | Path,
    dataset_name: str,
    min_relevance_score: float = 1.0,
) -> list[dict]:
    """读取 SciRepEval/SciDocs proximity pair 并转换为 agenda_non_identity 评估 pair。

    参数:
        path: proximity pair JSONL/JSON/CSV 文件。
        dataset_name: 数据集名称。
        min_relevance_score: 视为 same_agenda proxy 的最低分。

    返回:
        评估 pair 记录列表。
    """
    pairs: list[dict] = []
    for row in _read_tabular_records(path):
        pair_ids = _pair_ids_from_record(row)
        if pair_ids is None:
            LOGGER.warning("SciRepEval proximity pair 缺少左右 ID，跳过: %s", row)
            continue
        left_id, right_id = pair_ids
        relevance_score = _score_from_record(row)
        is_agenda_proxy = relevance_score >= min_relevance_score
        pairs.append(
            {
                "source_document_id": _document_id(dataset_name, left_id),
                "target_document_id": _document_id(dataset_name, right_id),
                "candidate_sources": ["scirepeval_proximity"],
                "raw_similarity": relevance_score,
                "expected_label": 0,
                "expected_agenda_label": 1 if is_agenda_proxy else 0,
                "label_type": "scirepeval_agenda_non_identity_proxy" if is_agenda_proxy else "scirepeval_nonrelevant_proxy",
                "label_reason": "proximity_relevance_proxy",
                "relevance_score": relevance_score,
                "source_pair_id": _clean_text(_first_non_empty(row, ["id", "pair_id"])),
            }
        )
    LOGGER.info("SciRepEval proximity pair 读取完成: path=%s pairs=%s", path, len(pairs))
    return pairs


def _filter_needed_documents(documents: Iterable[dict], pairs: Iterable[dict]) -> tuple[list[dict], list[str]]:
    """筛选评估 pair 需要的文献。

    参数:
        documents: 标准化文献记录。
        pairs: 评估 pair 记录。

    返回:
        文献列表与缺失 ID 列表。
    """
    document_lookup = {document["document_id"]: document for document in documents}
    needed_ids = {pair["source_document_id"] for pair in pairs} | {pair["target_document_id"] for pair in pairs}
    missing_ids = sorted(document_id for document_id in needed_ids if document_id not in document_lookup)
    return [document_lookup[document_id] for document_id in sorted(needed_ids) if document_id in document_lookup], missing_ids


def prepare_scirepeval_proximity_evaluation_set(
    metadata_path: str | Path,
    pairs_path: str | Path,
    dataset_name: str,
    min_relevance_score: float = 1.0,
) -> tuple[list[dict], list[dict], dict]:
    """构造 SciRepEval/SciDocs same_agenda proxy 评估集。

    参数:
        metadata_path: SciRepEval metadata 文件。
        pairs_path: SciRepEval proximity pair 文件。
        dataset_name: 数据集名称。
        min_relevance_score: 视为 same_agenda proxy 的最低分。

    返回:
        评估文献、评估 pair 和摘要字典。
    """
    all_documents = read_scirepeval_metadata(metadata_path, dataset_name)
    pairs = read_scirepeval_proximity_pairs(pairs_path, dataset_name, min_relevance_score=min_relevance_score)
    documents, missing_ids = _filter_needed_documents(all_documents, pairs)
    agenda_positive_count = sum(1 for pair in pairs if pair.get("expected_agenda_label") == 1)
    summary = {
        "dataset_name": dataset_name,
        "metadata_document_count": len(all_documents),
        "document_count": len(documents),
        "pair_count": len(pairs),
        "agenda_positive_pair_count": agenda_positive_count,
        "duplicate_positive_pair_count": 0,
        "missing_document_count": len(missing_ids),
        "label_type": "same_agenda_proxy_as_non_duplicate",
        "min_relevance_score": min_relevance_score,
    }
    return documents, pairs, summary
