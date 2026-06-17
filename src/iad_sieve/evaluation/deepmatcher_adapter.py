"""DeepMatcher citation matching 数据适配模块。"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path


LOGGER = logging.getLogger(__name__)


def _clean_text(value: object) -> str:
    """清理 CSV 字段文本。

    参数:
        value: 原始字段值。

    返回:
        去除多余空白后的字符串。
    """
    return " ".join(str(value or "").split())


def _first_non_empty(record: dict[str, str], fields: list[str]) -> str:
    """按字段优先级读取第一个非空值。

    参数:
        record: CSV 行记录。
        fields: 候选字段名列表。

    返回:
        第一个非空字段值，缺失时返回空字符串。
    """
    for field in fields:
        value = _clean_text(record.get(field, ""))
        if value:
            return value
    return ""


def _parse_year(raw_value: str) -> int | None:
    """解析年份字段。

    参数:
        raw_value: 原始年份字符串。

    返回:
        四位年份；无法解析时返回 None。
    """
    match = re.search(r"(19|20)\d{2}", str(raw_value or ""))
    if not match:
        return None
    return int(match.group(0))


def _parse_authors(raw_value: str) -> list[str]:
    """解析作者字段。

    参数:
        raw_value: 原始作者字符串。

    返回:
        作者列表。
    """
    cleaned = _clean_text(raw_value)
    if not cleaned:
        return []
    if ";" in cleaned:
        return [_clean_text(author) for author in cleaned.split(";") if _clean_text(author)]
    if "|" in cleaned:
        return [_clean_text(author) for author in cleaned.split("|") if _clean_text(author)]
    if " and " in cleaned.lower():
        return [_clean_text(author) for author in re.split(r"\s+and\s+", cleaned, flags=re.IGNORECASE) if _clean_text(author)]
    return [cleaned]


def _document_id(dataset_name: str, side: str, raw_id: str) -> str:
    """构造 DeepMatcher 文献 ID。

    参数:
        dataset_name: 数据集名称。
        side: 表侧标识，通常为 A 或 B。
        raw_id: 原始表内 ID。

    返回:
        项目内部 document_id。
    """
    safe_dataset = _clean_text(dataset_name).replace(" ", "_")
    safe_side = _clean_text(side).upper()
    safe_id = _clean_text(raw_id)
    return f"deepmatcher:{safe_dataset}:table{safe_side}:{safe_id}"


def _read_csv_records(path: str | Path) -> list[dict[str, str]]:
    """读取 CSV 记录。

    参数:
        path: CSV 文件路径。

    返回:
        CSV 行字典列表。
    """
    input_path = Path(path)
    try:
        with input_path.open("r", encoding="utf-8", newline="") as file:
            return [dict(row) for row in csv.DictReader(file)]
    except OSError:
        LOGGER.exception("读取 DeepMatcher CSV 失败: %s", path)
        raise


def read_deepmatcher_table(path: str | Path, dataset_name: str, side: str) -> list[dict]:
    """读取 DeepMatcher 实体表并转换为标准文献记录。

    参数:
        path: tableA.csv 或 tableB.csv 路径。
        dataset_name: 数据集名称。
        side: 表侧标识，通常为 A 或 B。

    返回:
        标准化文献记录列表。
    """
    records: list[dict] = []
    for row in _read_csv_records(path):
        raw_id = _first_non_empty(row, ["id", "paper_id", "record_id"])
        if not raw_id:
            LOGGER.warning("DeepMatcher 表记录缺少 id，跳过: %s", row)
            continue
        title = _first_non_empty(row, ["title", "paper_title", "name"])
        authors = _parse_authors(_first_non_empty(row, ["authors", "author", "authors_list"]))
        venue = _first_non_empty(row, ["venue", "journal", "booktitle", "journal_ref"])
        year = _parse_year(_first_non_empty(row, ["year", "publication_year", "date"]))
        document_id = _document_id(dataset_name, side, raw_id)
        records.append(
            {
                "document_id": document_id,
                "source_dataset": dataset_name,
                "source_table": f"table{side.upper()}",
                "source_record_id": raw_id,
                "title": title,
                "title_normalized": title.lower(),
                "abstract": "",
                "abstract_normalized": "",
                "authors": authors,
                "categories": ["citation_matching"],
                "primary_category": "citation_matching",
                "publication_year": year,
                "doi": "",
                "arxiv_id": "",
                "journal_ref": venue,
                "version_count": 1,
                "withdrawn_flag": False,
                "metadata_json": {"deepmatcher_row": row},
            }
        )
    LOGGER.info("DeepMatcher 表读取完成: path=%s records=%s", path, len(records))
    return records


def _parse_label(raw_value: str) -> int:
    """解析 DeepMatcher 标签。

    参数:
        raw_value: 原始标签字段。

    返回:
        1 表示同一文献，0 表示非同一文献。
    """
    normalized = _clean_text(raw_value).lower()
    return 1 if normalized in {"1", "true", "yes", "y", "match", "matched"} else 0


def read_deepmatcher_pairs(path: str | Path, dataset_name: str) -> list[dict]:
    """读取 DeepMatcher 标注 pair 并转换为评估 pair。

    参数:
        path: train.csv、valid.csv 或 test.csv 路径。
        dataset_name: 数据集名称。

    返回:
        评估 pair 记录列表。
    """
    pairs: list[dict] = []
    for row in _read_csv_records(path):
        left_id = _first_non_empty(row, ["ltable_id", "ltable.id", "left_id", "tableA_id", "source_id", "id1"])
        right_id = _first_non_empty(row, ["rtable_id", "rtable.id", "right_id", "tableB_id", "target_id", "id2"])
        if not left_id or not right_id:
            LOGGER.warning("DeepMatcher pair 缺少左右 ID，跳过: %s", row)
            continue
        label = _parse_label(_first_non_empty(row, ["label", "gold", "is_match", "match"]))
        pairs.append(
            {
                "source_document_id": _document_id(dataset_name, "A", left_id),
                "target_document_id": _document_id(dataset_name, "B", right_id),
                "candidate_sources": ["deepmatcher_gold"],
                "raw_similarity": 1.0 if label == 1 else 0.0,
                "expected_label": label,
                "label_type": "deepmatcher_same_work_gold",
                "label_reason": "public_gold_label",
                "source_pair_id": _first_non_empty(row, ["id", "_id", "pair_id"]),
            }
        )
    LOGGER.info("DeepMatcher pair 读取完成: path=%s pairs=%s", path, len(pairs))
    return pairs


def prepare_deepmatcher_evaluation_set(
    table_a_path: str | Path,
    table_b_path: str | Path,
    pairs_path: str | Path,
    dataset_name: str,
) -> tuple[list[dict], list[dict], dict]:
    """构造 IAD-Sieve 评估集。

    参数:
        table_a_path: DeepMatcher tableA.csv 路径。
        table_b_path: DeepMatcher tableB.csv 路径。
        pairs_path: DeepMatcher 标注 pair CSV 路径。
        dataset_name: 数据集名称。

    返回:
        评估文献、评估 pair 和摘要字典。
    """
    table_a_records = read_deepmatcher_table(table_a_path, dataset_name, "A")
    table_b_records = read_deepmatcher_table(table_b_path, dataset_name, "B")
    pairs = read_deepmatcher_pairs(pairs_path, dataset_name)
    needed_ids = {pair["source_document_id"] for pair in pairs} | {pair["target_document_id"] for pair in pairs}
    documents_by_id = {record["document_id"]: record for record in table_a_records + table_b_records}
    missing_ids = sorted(document_id for document_id in needed_ids if document_id not in documents_by_id)
    if missing_ids:
        LOGGER.warning("DeepMatcher pair 引用了缺失文献: count=%s examples=%s", len(missing_ids), missing_ids[:5])
    documents = [documents_by_id[document_id] for document_id in sorted(needed_ids) if document_id in documents_by_id]
    positive_count = sum(1 for pair in pairs if pair["expected_label"] == 1)
    negative_count = sum(1 for pair in pairs if pair["expected_label"] == 0)
    summary = {
        "dataset_name": dataset_name,
        "table_a_count": len(table_a_records),
        "table_b_count": len(table_b_records),
        "document_count": len(documents),
        "pair_count": len(pairs),
        "positive_pair_count": positive_count,
        "negative_pair_count": negative_count,
        "missing_document_count": len(missing_ids),
        "label_type": "same_work_gold",
    }
    return documents, pairs, summary
