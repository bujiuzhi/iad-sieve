"""IAD-Bench 数据契约构建模块。"""

from __future__ import annotations

import csv
import logging
import random
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
DOCUMENT_FIELDS = [
    "document_id",
    "title",
    "abstract",
    "authors",
    "year",
    "venue",
    "doi",
    "arxiv_id",
    "openalex_work_id",
    "topics",
    "references",
    "source_dataset",
]
PAIR_FIELDS = [
    "pair_id",
    "source_document_id",
    "target_document_id",
    "relation_label",
    "expected_label",
    "expected_agenda_label",
    "label_source",
    "label_strength",
    "label_provenance",
    "split",
    "hard_negative_level",
]


def _clean_text(value: object) -> str:
    """清理文本字段。

    参数:
        value: 原始字段值。

    返回:
        去除多余空白后的字符串。
    """
    return " ".join(str(value or "").split())


def _normalize_identifier(value: object) -> str:
    """标准化标识符。

    参数:
        value: 原始标识符。

    返回:
        小写标识符字符串。
    """
    return _clean_text(value).lower().rstrip("/")


def _normalize_doi(value: object) -> str:
    """标准化 DOI。

    参数:
        value: 原始 DOI。

    返回:
        小写裸 DOI。
    """
    doi = _normalize_identifier(value)
    for prefix in ["https://doi.org/", "http://doi.org/", "doi:"]:
        if doi.startswith(prefix):
            return doi[len(prefix) :]
    return doi


def _normalize_list(value: object) -> list:
    """标准化列表字段。

    参数:
        value: 原始字段值。

    返回:
        列表形式的字段值。
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    cleaned = _clean_text(value)
    return [cleaned] if cleaned else []


def _extract_openalex_work_id(document: dict) -> str:
    """提取 OpenAlex Work ID。

    参数:
        document: 文献记录。

    返回:
        OpenAlex Work ID，缺失时返回空字符串。
    """
    metadata = document.get("metadata_json") if isinstance(document.get("metadata_json"), dict) else {}
    direct_value = _clean_text(document.get("openalex_work_id") or metadata.get("openalex_id"))
    if direct_value:
        return direct_value.rstrip("/").split("/")[-1]
    document_id = _clean_text(document.get("document_id"))
    if document_id.startswith("openalex:"):
        return document_id.rsplit(":", maxsplit=1)[-1]
    return ""


def _normalize_document(document: dict) -> dict:
    """将评估文献转为 IAD-Bench 文档契约。

    参数:
        document: eval_documents 记录。

    返回:
        IAD-Bench 文档记录。
    """
    metadata = document.get("metadata_json") if isinstance(document.get("metadata_json"), dict) else {}
    normalized = {
        "document_id": _clean_text(document.get("document_id")),
        "title": _clean_text(document.get("title")),
        "abstract": _clean_text(document.get("abstract")),
        "authors": _normalize_list(document.get("authors")),
        "year": document.get("year", document.get("publication_year")),
        "venue": _clean_text(document.get("venue", document.get("journal_ref"))),
        "doi": _normalize_doi(document.get("doi")),
        "arxiv_id": _clean_text(document.get("arxiv_id")),
        "openalex_work_id": _extract_openalex_work_id(document),
        "topics": _normalize_list(document.get("topics", document.get("categories"))),
        "references": _normalize_list(document.get("references", metadata.get("referenced_work_ids"))),
        "source_dataset": _clean_text(document.get("source_dataset")),
    }
    normalized["source_record"] = document
    return normalized


def _pair_key(source_document_id: str, target_document_id: str) -> tuple[str, str]:
    """构造无向 pair key。

    参数:
        source_document_id: 左侧文献 ID。
        target_document_id: 右侧文献 ID。

    返回:
        排序后的二元组。
    """
    return tuple(sorted((_clean_text(source_document_id), _clean_text(target_document_id))))


def _safe_label_source_suffix(value: object) -> str:
    """构造安全的 label_source 后缀。

    参数:
        value: 原始来源名称。

    返回:
        仅包含小写字母、数字和下划线的来源后缀。
    """
    cleaned_value = _clean_text(value).lower()
    safe_value = re.sub(r"[^a-z0-9]+", "_", cleaned_value).strip("_")
    return safe_value or "unknown"


def _infer_deepmatcher_dataset_name(pair: dict) -> str:
    """从 DeepMatcher pair 中解析公开数据集名称。

    参数:
        pair: 原始 eval_pair 记录。

    返回:
        DeepMatcher 子数据集安全名称，缺失时返回空字符串。
    """
    for field_name in ["source_document_id", "target_document_id"]:
        document_id = _clean_text(pair.get(field_name))
        if not document_id.startswith("deepmatcher:"):
            continue
        parts = document_id.split(":")
        if len(parts) >= 3:
            return _safe_label_source_suffix(parts[1])
    return ""


def _infer_label_source(pair: dict) -> str:
    """推断标签来源。

    参数:
        pair: 原始 eval_pair 记录。

    返回:
        标签来源名称。
    """
    label_type = str(pair.get("label_type", "")).lower()
    candidate_sources = {str(source).lower() for source in pair.get("candidate_sources", [])}
    if "deepmatcher" in label_type or "deepmatcher_gold" in candidate_sources:
        dataset_name = _infer_deepmatcher_dataset_name(pair)
        return f"deepmatcher_{dataset_name}" if dataset_name else "deepmatcher"
    if "scirepeval" in label_type or "scirepeval_proximity" in candidate_sources:
        return "scirepeval"
    if "opencitations" in " ".join(candidate_sources):
        return "openalex_opencitations"
    if "openalex" in label_type or any("openalex" in source for source in candidate_sources):
        return "openalex"
    if "synthetic" in label_type or any("synthetic" in source for source in candidate_sources):
        return "synthetic"
    if "llm" in label_type or any("gpt" in source or "llm" in source for source in candidate_sources):
        return "llm"
    return "unknown"


def _infer_label_strength(label_source: str, pair: dict) -> str:
    """推断标签强度。

    参数:
        label_source: 标签来源。
        pair: 原始 eval_pair 记录。

    返回:
        label_strength。
    """
    label_type = str(pair.get("label_type", "")).lower()
    if label_source.startswith("deepmatcher") and "gold" in label_type:
        return "gold"
    if label_source == "scirepeval":
        return "proxy"
    if label_source in {"openalex", "openalex_opencitations"}:
        return "silver"
    if label_source == "llm":
        return "llm_silver"
    if label_source == "synthetic":
        return "distant"
    return "silver"


def _as_int(value: object, default: int = 0) -> int:
    """安全转换整数。

    参数:
        value: 原始值。
        default: 转换失败时的默认值。

    返回:
        整数值。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _infer_relation_label(pair: dict) -> str:
    """推断 IAD-Bench 关系标签。

    参数:
        pair: 原始 eval_pair 记录。

    返回:
        relation_label。
    """
    expected_label = _as_int(pair.get("expected_label"), default=0)
    expected_agenda_label = _as_int(pair.get("expected_agenda_label"), default=0)
    if expected_label == 1:
        return "same_work"
    if expected_agenda_label == 1:
        return "agenda_non_identity"
    if "uncertain" in str(pair.get("label_type", "")).lower():
        return "uncertain"
    return "unrelated"


def _same_doi(left_document: dict | None, right_document: dict | None) -> bool:
    """判断两篇文献 DOI 是否相同。

    参数:
        left_document: 左侧文献。
        right_document: 右侧文献。

    返回:
        DOI 同且非空返回 True。
    """
    left_doi = _normalize_doi((left_document or {}).get("doi"))
    right_doi = _normalize_doi((right_document or {}).get("doi"))
    return bool(left_doi and right_doi and left_doi == right_doi)


def _same_arxiv_id(left_document: dict | None, right_document: dict | None) -> bool:
    """判断两篇文献 arXiv ID 是否相同。

    参数:
        left_document: 左侧文献。
        right_document: 右侧文献。

    返回:
        arXiv ID 同且非空返回 True。
    """
    left_id = _normalize_identifier((left_document or {}).get("arxiv_id"))
    right_id = _normalize_identifier((right_document or {}).get("arxiv_id"))
    return bool(left_id and right_id and left_id == right_id)


def _same_openalex_work_id(left_document: dict | None, right_document: dict | None) -> bool:
    """判断两篇文献 OpenAlex Work ID 是否相同。

    参数:
        left_document: 左侧文献。
        right_document: 右侧文献。

    返回:
        OpenAlex Work ID 同且非空返回 True。
    """
    left_id = _normalize_identifier((left_document or {}).get("openalex_work_id"))
    right_id = _normalize_identifier((right_document or {}).get("openalex_work_id"))
    return bool(left_id and right_id and left_id == right_id)


def _infer_hard_negative_level(pair: dict, label_source: str, relation_label: str) -> str:
    """推断 hard negative 强度。

    参数:
        pair: 原始 eval_pair 记录。
        label_source: 标签来源。
        relation_label: IAD-Bench 关系标签。

    返回:
        hard_negative_level。
    """
    if relation_label != "agenda_non_identity":
        return "none"
    shared_reference_count = _as_int(pair.get("shared_reference_count"), default=0)
    if label_source == "openalex_opencitations" or shared_reference_count >= 2:
        return "high"
    if label_source in {"scirepeval", "openalex"}:
        return "medium"
    return "low"


def _build_label_provenance(pair: dict, label_source: str, left_document: dict | None, right_document: dict | None, source_dir: Path) -> dict:
    """构造标签 provenance。

    参数:
        pair: 原始 eval_pair 记录。
        label_source: 标签来源。
        left_document: 左侧文献。
        right_document: 右侧文献。
        source_dir: 来源评估目录。

    返回:
        provenance 字典。
    """
    provenance = {
        "label_type": _clean_text(pair.get("label_type")),
        "label_reason": _clean_text(pair.get("label_reason")),
        "candidate_sources": _normalize_list(pair.get("candidate_sources")),
        "source_dir": str(source_dir),
        "source_pair_id": _clean_text(pair.get("source_pair_id")),
        "raw_similarity": pair.get("raw_similarity", ""),
        "same_doi": _same_doi(left_document, right_document),
        "same_arxiv_id": _same_arxiv_id(left_document, right_document),
        "same_openalex_work_id": _same_openalex_work_id(left_document, right_document),
        "shared_reference_count": _as_int(pair.get("shared_reference_count"), default=0),
        "shared_references": _normalize_list(pair.get("shared_references")),
        "primary_topic": _clean_text(pair.get("primary_topic")),
        "relevance_score": pair.get("relevance_score", ""),
        "llm_used": label_source == "llm",
    }
    return provenance


def _assign_splits(pairs: list[dict], seed: int, train_ratio: float, dev_ratio: float) -> None:
    """为 pair 分配 train/dev/test split。

    参数:
        pairs: IAD-Bench pair 记录，会被原地写入 split。
        seed: 随机种子。
        train_ratio: 训练集比例。
        dev_ratio: 开发集比例。

    返回:
        无。
    """
    if train_ratio < 0 or dev_ratio < 0 or train_ratio + dev_ratio > 1:
        raise ValueError("train_ratio 和 dev_ratio 必须非负，且二者之和不能超过 1")
    shuffled_indices = list(range(len(pairs)))
    random.Random(seed).shuffle(shuffled_indices)
    train_count = int(len(pairs) * train_ratio)
    dev_count = int(len(pairs) * dev_ratio)
    train_indices = set(shuffled_indices[:train_count])
    dev_indices = set(shuffled_indices[train_count : train_count + dev_count])
    for index, pair in enumerate(pairs):
        if index in train_indices:
            pair["split"] = "train"
        elif index in dev_indices:
            pair["split"] = "dev"
        else:
            pair["split"] = "test"


def _load_source_dir(source_dir: str | Path) -> tuple[list[dict], list[dict], list[dict]]:
    """读取一个评估目录。

    参数:
        source_dir: 包含 eval_documents、eval_pairs 和 dataset_summary 的目录。

    返回:
        文献、pair 和 summary 列表。
    """
    resolved_source_dir = Path(source_dir)
    try:
        documents = read_records(resolved_source_dir / "eval_documents.jsonl")
        pairs = read_records(resolved_source_dir / "eval_pairs.jsonl")
        summary_path = resolved_source_dir / "dataset_summary.jsonl"
        summaries = read_records(summary_path) if summary_path.exists() else []
    except Exception:
        LOGGER.exception("读取 IAD-Bench 来源目录失败: %s", source_dir)
        raise
    return documents, pairs, summaries


def _normalize_pairs(raw_pairs_by_dir: list[tuple[Path, list[dict]]], documents_by_id: dict[str, dict]) -> tuple[list[dict], int]:
    """标准化 pair 记录。

    参数:
        raw_pairs_by_dir: 来源目录与原始 pair 列表。
        documents_by_id: 已标准化文献映射。

    返回:
        IAD-Bench pair 列表和跳过的重复 pair 数。
    """
    normalized_pairs: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()
    duplicate_pair_count = 0
    for source_dir, raw_pairs in raw_pairs_by_dir:
        for raw_pair in raw_pairs:
            source_document_id = _clean_text(raw_pair.get("source_document_id"))
            target_document_id = _clean_text(raw_pair.get("target_document_id"))
            if not source_document_id or not target_document_id:
                LOGGER.warning("IAD-Bench pair 缺少 source/target，跳过: %s", raw_pair)
                continue
            canonical_key = _pair_key(source_document_id, target_document_id)
            if canonical_key in seen_keys:
                duplicate_pair_count += 1
                LOGGER.warning("IAD-Bench 检测到重复无向 pair，保留首次记录: %s", canonical_key)
                continue
            seen_keys.add(canonical_key)
            left_document = documents_by_id.get(source_document_id)
            right_document = documents_by_id.get(target_document_id)
            label_source = _infer_label_source(raw_pair)
            relation_label = _infer_relation_label(raw_pair)
            normalized_pair = {
                "source_document_id": source_document_id,
                "target_document_id": target_document_id,
                "relation_label": relation_label,
                "expected_label": 1 if relation_label == "same_work" else 0,
                "expected_agenda_label": 1 if relation_label in {"same_work", "same_agenda", "agenda_non_identity"} else 0,
                "label_source": label_source,
                "label_strength": _infer_label_strength(label_source, raw_pair),
                "label_provenance": _build_label_provenance(raw_pair, label_source, left_document, right_document, source_dir),
                "hard_negative_level": _infer_hard_negative_level(raw_pair, label_source, relation_label),
                "source_pair_id": _clean_text(raw_pair.get("source_pair_id")),
            }
            normalized_pairs.append(normalized_pair)
    normalized_pairs.sort(key=lambda pair: _pair_key(pair["source_document_id"], pair["target_document_id"]))
    for index, pair in enumerate(normalized_pairs, start=1):
        pair["pair_id"] = f"iadbench_{index:06d}"
    return normalized_pairs, duplicate_pair_count


def _write_provenance_summary(path: Path, pairs: Iterable[dict]) -> list[dict]:
    """写出 label provenance 分层汇总。

    参数:
        path: 输出 CSV 路径。
        pairs: IAD-Bench pair 记录。

    返回:
        汇总行列表。
    """
    grouped_counts: Counter[tuple[str, str, str, str]] = Counter()
    for pair in pairs:
        grouped_counts[(pair["label_source"], pair["label_strength"], pair["relation_label"], pair["split"])] += 1
    rows = [
        {
            "label_source": label_source,
            "label_strength": label_strength,
            "relation_label": relation_label,
            "split": split,
            "pair_count": count,
        }
        for (label_source, label_strength, relation_label, split), count in sorted(grouped_counts.items())
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["label_source", "label_strength", "relation_label", "split", "pair_count"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def _summary_from_pairs(pairs: list[dict], documents: list[dict], duplicate_pair_count: int, source_dirs: list[str | Path]) -> dict:
    """构造 IAD-Bench 摘要。

    参数:
        pairs: IAD-Bench pair 记录。
        documents: IAD-Bench 文献记录。
        duplicate_pair_count: 被跳过的重复 pair 数。
        source_dirs: 来源目录列表。

    返回:
        摘要记录。
    """
    strength_counts = Counter(pair["label_strength"] for pair in pairs)
    relation_counts = Counter(pair["relation_label"] for pair in pairs)
    hard_negative_count = sum(1 for pair in pairs if pair["hard_negative_level"] != "none")
    return {
        "evidence_layer": "iad_bench_provenance",
        "system": "iad_bench",
        "metric_target": "label_provenance",
        "document_count": len(documents),
        "pair_count": len(pairs),
        "gold_pair_count": strength_counts.get("gold", 0),
        "distant_pair_count": strength_counts.get("distant", 0),
        "proxy_pair_count": strength_counts.get("proxy", 0),
        "silver_pair_count": strength_counts.get("silver", 0),
        "llm_silver_pair_count": strength_counts.get("llm_silver", 0),
        "human_audit_pair_count": strength_counts.get("human_audit", 0),
        "same_work_pair_count": relation_counts.get("same_work", 0),
        "agenda_non_identity_pair_count": relation_counts.get("agenda_non_identity", 0),
        "unrelated_pair_count": relation_counts.get("unrelated", 0),
        "hard_negative_pair_count": hard_negative_count,
        "duplicate_pair_skipped_count": duplicate_pair_count,
        "source_dir_count": len(source_dirs),
    }


def _write_dataset_card(path: Path, summary: dict, source_dirs: list[str | Path], provenance_rows: list[dict]) -> None:
    """写出 IAD-Bench 数据卡。

    参数:
        path: 数据卡路径。
        summary: IAD-Bench 摘要。
        source_dirs: 来源目录列表。
        provenance_rows: provenance 汇总行。

    返回:
        无。
    """
    lines = [
        "# IAD-Bench Dataset Card",
        "",
        "## 数据边界",
        "",
        "IAD-Bench 统一公开 gold、proxy 与 silver pair 的字段契约，不把 OpenAlex、SciRepEval 或 LLM 标签写作 gold。",
        "",
        "## 来源目录",
        "",
    ]
    lines.extend(f"- `{source_dir}`" for source_dir in source_dirs)
    lines.extend(
        [
            "",
            "## 规模摘要",
            "",
            f"- document_count: {summary['document_count']}",
            f"- pair_count: {summary['pair_count']}",
            f"- gold_pair_count: {summary['gold_pair_count']}",
            f"- proxy_pair_count: {summary['proxy_pair_count']}",
            f"- silver_pair_count: {summary['silver_pair_count']}",
            f"- hard_negative_pair_count: {summary['hard_negative_pair_count']}",
            "",
            "## Provenance 分层",
            "",
            "| label_source | label_strength | relation_label | split | pair_count |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in provenance_rows:
        lines.append(
            f"| {row['label_source']} | {row['label_strength']} | {row['relation_label']} | {row['split']} | {row['pair_count']} |"
        )
    lines.extend(
        [
            "",
            "## 禁止事项",
            "",
            "- 禁止把 `proxy`、`silver`、`llm_silver` 混写成 gold。",
            "- 禁止把不同 `label_strength` 的结果汇总成无来源说明的主指标。",
            "- 禁止用 GPT 生成标签作为唯一测试集。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_iad_bench(
    source_dirs: list[str | Path],
    output_dir: str | Path,
    seed: int = 42,
    train_ratio: float = 0.8,
    dev_ratio: float = 0.1,
) -> dict:
    """构建 IAD-Bench 数据契约产物。

    参数:
        source_dirs: 一个或多个评估目录，需包含 eval_documents.jsonl 和 eval_pairs.jsonl。
        output_dir: IAD-Bench 输出目录。
        seed: split 随机种子。
        train_ratio: train split 比例。
        dev_ratio: dev split 比例。

    返回:
        IAD-Bench 摘要记录。
    """
    if not source_dirs:
        raise ValueError("source_dirs 不能为空")
    resolved_output_dir = ensure_directory(output_dir)
    documents_by_id: dict[str, dict] = {}
    raw_pairs_by_dir: list[tuple[Path, list[dict]]] = []
    source_summaries: list[dict] = []
    for source_dir in source_dirs:
        resolved_source_dir = Path(source_dir)
        raw_documents, raw_pairs, summaries = _load_source_dir(resolved_source_dir)
        raw_pairs_by_dir.append((resolved_source_dir, raw_pairs))
        source_summaries.extend(summaries)
        for raw_document in raw_documents:
            normalized_document = _normalize_document(raw_document)
            document_id = normalized_document["document_id"]
            if not document_id:
                LOGGER.warning("IAD-Bench 文献缺少 document_id，跳过: %s", raw_document)
                continue
            documents_by_id.setdefault(document_id, normalized_document)
    normalized_documents = [documents_by_id[document_id] for document_id in sorted(documents_by_id)]
    normalized_pairs, duplicate_pair_count = _normalize_pairs(raw_pairs_by_dir, documents_by_id)
    _assign_splits(normalized_pairs, seed=seed, train_ratio=train_ratio, dev_ratio=dev_ratio)
    split_rows = [
        {
            "pair_id": pair["pair_id"],
            "source_document_id": pair["source_document_id"],
            "target_document_id": pair["target_document_id"],
            "split": pair["split"],
            "label_source": pair["label_source"],
            "label_strength": pair["label_strength"],
        }
        for pair in normalized_pairs
    ]
    provenance_rows = _write_provenance_summary(resolved_output_dir / "label_provenance_summary.csv", normalized_pairs)
    summary = _summary_from_pairs(normalized_pairs, normalized_documents, duplicate_pair_count, source_dirs)
    summary["source_summaries"] = source_summaries
    write_records([{field: document.get(field) for field in DOCUMENT_FIELDS} for document in normalized_documents], resolved_output_dir / "iad_bench_documents.jsonl")
    write_records([{**{field: pair.get(field) for field in PAIR_FIELDS}, "source_pair_id": pair.get("source_pair_id", "")} for pair in normalized_pairs], resolved_output_dir / "iad_bench_pairs.jsonl")
    write_records(split_rows, resolved_output_dir / "iad_bench_splits.jsonl")
    write_records([summary], resolved_output_dir / "iad_bench_summary.jsonl")
    _write_dataset_card(resolved_output_dir / "dataset_card.md", summary, source_dirs, provenance_rows)
    LOGGER.info(
        "IAD-Bench 构建完成: output_dir=%s documents=%s pairs=%s",
        resolved_output_dir,
        len(normalized_documents),
        len(normalized_pairs),
    )
    return summary
