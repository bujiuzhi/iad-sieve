"""Hard-negative stress set 分层构造模块。"""

from __future__ import annotations

import csv
import logging
from collections import Counter
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "stress_pair_id",
    "pair_id",
    "source_document_id",
    "target_document_id",
    "stress_level",
    "stress_type",
    "usable_as_primary_negative",
    "stress_rationale",
    "expected_label",
    "expected_agenda_label",
    "title_similarity",
    "embedding_similarity",
    "author_overlap",
    "shared_reference_count",
    "identifier_conflict",
    "version_risk_score",
    "label_type",
    "label_reason",
    "relation_label",
    "label_source",
    "label_strength",
]
TITLE_TEMPLATE_PATTERNS = [
    "a survey of ",
    "survey of ",
    "a review of ",
    "review of ",
    "benchmarking ",
    "benchmark for ",
    "dataset for ",
    "deep learning for ",
    "machine learning for ",
]
VERSION_RISK_KEYWORDS = [
    "preprint",
    "published version",
    "journal version",
    "conference version",
    "extended version",
    "short paper",
    "full paper",
    "erratum",
    "corrigendum",
    "version-risk",
    "version_risk",
]


def _clean(value: object) -> str:
    """清理字符串字段。

    参数:
        value: 原始字段值。

    返回:
        去除首尾空白后的字符串。
    """
    if value is None:
        return ""
    return str(value).strip()


def _lower_text(*values: object) -> str:
    """合并字段并转为小写文本。

    参数:
        *values: 待合并字段。

    返回:
        小写文本。
    """
    return " ".join(_clean(value).lower() for value in values if _clean(value))


def _as_float(record: dict, field: str, default: float = 0.0) -> float:
    """安全读取浮点字段。

    参数:
        record: 输入记录。
        field: 字段名。
        default: 字段缺失或非法时使用的默认值。

    返回:
        浮点值。
    """
    try:
        return float(record.get(field, default) or default)
    except (TypeError, ValueError):
        LOGGER.warning("hard-negative 字段无法转为浮点数: field=%s value=%r", field, record.get(field))
        return default


def _first_float(record: dict, fields: list[str], default: float = 0.0) -> float:
    """读取多个字段中的第一个有效浮点数。

    参数:
        record: 输入记录。
        fields: 候选字段名。
        default: 默认值。

    返回:
        浮点值。
    """
    for field in fields:
        if record.get(field) not in {None, ""}:
            return _as_float(record, field, default)
    return default


def _bool_value(value: object) -> bool:
    """解析布尔字段。

    参数:
        value: 原始字段值。

    返回:
        布尔值。
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) > 0.0
    return _clean(value).lower() in {"true", "1", "yes", "y", "ready"}


def _provenance(record: dict) -> dict:
    """读取嵌套 label_provenance。

    参数:
        record: 关系记录。

    返回:
        provenance 字典；缺失或类型不符时返回空字典。
    """
    value = record.get("label_provenance")
    return value if isinstance(value, dict) else {}


def _provenance_marker_text(record: dict) -> str:
    """构造 provenance 相关标记文本。

    参数:
        record: 关系记录。

    返回:
        小写标记文本。
    """
    provenance = _provenance(record)
    candidate_sources = provenance.get("candidate_sources", [])
    if isinstance(candidate_sources, list):
        candidate_source_text = " ".join(_clean(item) for item in candidate_sources)
    else:
        candidate_source_text = _clean(candidate_sources)
    return _lower_text(
        record.get("relation_label"),
        record.get("label_type"),
        record.get("relation_type"),
        provenance.get("label_type"),
        provenance.get("label_reason"),
        candidate_source_text,
    )


def _different_non_empty(left: object, right: object) -> bool:
    """判断两个非空标识符是否不同。

    参数:
        left: 左侧标识符。
        right: 右侧标识符。

    返回:
        两者均非空且不同返回 True。
    """
    left_text = _clean(left).lower()
    right_text = _clean(right).lower()
    return bool(left_text and right_text and left_text != right_text)


def _identifier_conflict(record: dict) -> bool:
    """判断 pair 是否存在稳定标识符冲突。

    参数:
        record: 关系记录。

    返回:
        存在 DOI/arXiv/OpenAlex/PMID/ACL 等冲突返回 True。
    """
    conflict_fields = [
        "different_identifier",
        "identifier_conflict",
        "different_doi",
        "different_arxiv_id",
        "different_openalex_work_id",
        "different_pmid",
        "different_pmcid",
        "different_acl_id",
    ]
    if any(_bool_value(record.get(field)) for field in conflict_fields):
        return True
    provenance = _provenance(record)
    provenance_marker = _provenance_marker_text(record)
    if (
        ("agenda_non_identity" in provenance_marker or "openalex" in provenance_marker or "opencitations" in provenance_marker)
        and provenance.get("same_doi") is False
        and provenance.get("same_openalex_work_id") is False
    ):
        return True
    same_fields = ["same_doi", "same_arxiv_id", "same_openalex_work_id", "same_pmid", "same_pmcid", "same_acl_id"]
    if any(_bool_value(record.get(field)) for field in same_fields):
        return False
    identifier_pairs = [
        ("doi", "target_doi"),
        ("source_doi", "target_doi"),
        ("arxiv_id", "target_arxiv_id"),
        ("source_arxiv_id", "target_arxiv_id"),
        ("openalex_work_id", "target_openalex_work_id"),
        ("source_openalex_work_id", "target_openalex_work_id"),
        ("pmid", "target_pmid"),
        ("source_pmid", "target_pmid"),
        ("acl_id", "target_acl_id"),
        ("source_acl_id", "target_acl_id"),
    ]
    return any(_different_non_empty(record.get(left), record.get(right)) for left, right in identifier_pairs)


def _is_negative_candidate(record: dict) -> bool:
    """判断记录是否可进入 hard-negative stress 构造候选。

    参数:
        record: 关系记录。

    返回:
        属于负例或同议题非同文候选返回 True。
    """
    if int(record.get("expected_label", 0) or 0) == 1:
        return False
    marker_text = _provenance_marker_text(record)
    if "agenda_non_identity" in marker_text or "non_identity" in marker_text or "hard_negative" in marker_text or "same_topic" in marker_text:
        return True
    if int(record.get("expected_agenda_label", 0) or 0) == 1:
        return True
    title_similarity = _first_float(record, ["title_similarity", "raw_title_similarity"])
    embedding_similarity = _first_float(record, ["embedding_similarity", "transformer_cosine", "full_similarity", "cosine_similarity", "score"])
    return title_similarity >= 0.80 and embedding_similarity >= 0.75 and _identifier_conflict(record)


def _shared_reference_count(record: dict) -> int:
    """读取共享引用数量，兼容顶层与 label_provenance。

    参数:
        record: 关系记录。

    返回:
        共享引用数量。
    """
    top_level_count = int(_first_float(record, ["shared_reference_count", "common_reference_count"], default=0.0))
    if top_level_count:
        return top_level_count
    provenance = _provenance(record)
    try:
        return int(provenance.get("shared_reference_count", 0) or 0)
    except (TypeError, ValueError):
        LOGGER.warning("shared_reference_count 无法转为整数: value=%r", provenance.get("shared_reference_count"))
        return 0


def _has_version_risk(record: dict, author_overlap: float, title_similarity: float) -> bool:
    """判断 pair 是否应进入版本边界复核层。

    参数:
        record: 关系记录。
        author_overlap: 作者重叠分。
        title_similarity: 标题相似度。

    返回:
        存在版本边界风险返回 True。
    """
    if _first_float(record, ["version_risk_score", "version_boundary_score"], default=0.0) >= 0.50:
        return True
    if any(_bool_value(record.get(field)) for field in ["version_risk", "version_boundary", "version_risk_ambiguous"]):
        return True
    provenance = _provenance(record)
    marker_text = _lower_text(
        record.get("label_reason"),
        record.get("label_type"),
        record.get("relation_type"),
        record.get("title"),
        record.get("target_title"),
        provenance.get("label_reason"),
        provenance.get("label_type"),
    )
    if any(keyword in marker_text for keyword in VERSION_RISK_KEYWORDS):
        return True
    return author_overlap >= 0.85 and title_similarity >= 0.90 and _identifier_conflict(record) and _as_float(record, "claim_difference_score") < 0.20


def _has_title_template(record: dict) -> bool:
    """判断标题是否属于模板陷阱。

    参数:
        record: 关系记录。

    返回:
        标题命中模板模式返回 True。
    """
    title_text = _lower_text(record.get("title"), record.get("source_title"), record.get("target_title"))
    return any(pattern in title_text for pattern in TITLE_TEMPLATE_PATTERNS)


def _has_high_similarity(title_similarity: float, embedding_similarity: float, min_title_similarity: float, min_embedding_similarity: float) -> bool:
    """判断是否满足同议题压力测试相似度门槛。

    参数:
        title_similarity: 标题相似度。
        embedding_similarity: 表示相似度。
        min_title_similarity: 最低标题相似度。
        min_embedding_similarity: 最低表示相似度。

    返回:
        满足相似度门槛返回 True。
    """
    return title_similarity >= min_title_similarity and embedding_similarity >= min_embedding_similarity


def _classify_stress_type(
    record: dict,
    title_similarity: float,
    embedding_similarity: float,
    author_overlap: float,
    shared_reference_count: int,
    min_title_similarity: float,
    min_embedding_similarity: float,
    min_shared_references: int,
) -> tuple[str, str, bool, list[str]]:
    """分类 hard-negative stress 层级与类型。

    参数:
        record: 关系记录。
        title_similarity: 标题相似度。
        embedding_similarity: 表示相似度。
        author_overlap: 作者重叠分。
        shared_reference_count: 共享引用数。
        min_title_similarity: 最低标题相似度。
        min_embedding_similarity: 最低表示相似度。
        min_shared_references: citation-neighbor 最低共享引用数。

    返回:
        stress_level、stress_type、是否可作为主负例、理由列表。
    """
    identifier_conflict = _identifier_conflict(record)
    high_similarity = _has_high_similarity(title_similarity, embedding_similarity, min_title_similarity, min_embedding_similarity)
    if _has_version_risk(record, author_overlap, title_similarity):
        return "version_risk_ambiguous", "version_risk_ambiguous", False, ["version_boundary_or_publication_family_risk"]
    if not high_similarity or not identifier_conflict:
        return "weak_pseudo_negative", "weak_pseudo_negative", False, ["insufficient_similarity_or_conflict_evidence"]

    if _bool_value(record.get("source_cites_target")) or _bool_value(record.get("target_cites_source")) or _bool_value(record.get("one_cites_the_other")):
        return "high_confidence_non_identity", "one_cites_the_other", True, ["direct_citation_relation_implies_agenda_related_non_identity"]
    if shared_reference_count >= min_shared_references or _bool_value(record.get("citation_neighbor")):
        return "high_confidence_non_identity", "citation_neighbor", True, ["citation_neighborhood_similarity_with_identifier_conflict"]
    if author_overlap >= 0.65 and (_as_float(record, "claim_difference_score") >= 0.50 or _bool_value(record.get("venue_conflict"))):
        return "high_confidence_non_identity", "author_overlap_trap", True, ["same_author_series_with_distinct_claim_or_venue"]
    if _has_title_template(record):
        return "high_confidence_non_identity", "title_template_trap", True, ["generic_title_template_with_identifier_conflict"]
    if (
        (_bool_value(record.get("same_venue")) or _as_float(record, "venue_similarity") >= 0.90)
        and (_bool_value(record.get("same_year")) or _as_float(record, "year_match") >= 1.0)
        and (_bool_value(record.get("same_topic")) or _as_float(record, "topic_overlap") >= 0.50 or int(record.get("expected_agenda_label", 0) or 0) == 1)
    ):
        return "high_confidence_non_identity", "same_venue_year_topic", True, ["same_venue_year_topic_with_identifier_conflict"]
    return "high_confidence_non_identity", "similar_title_identifier_conflict", True, ["similar_title_or_embedding_with_identifier_and_metadata_conflict"]


def build_hard_negative_stress_set(
    relations: list[dict],
    min_title_similarity: float = 0.80,
    min_embedding_similarity: float = 0.75,
    min_shared_references: int = 2,
) -> list[dict]:
    """构建 agenda-level hard-negative stress set 分层记录。

    参数:
        relations: 已评分关系或 IAD-Bench pair 记录。
        min_title_similarity: 高置信压力测试的最低标题相似度。
        min_embedding_similarity: 高置信压力测试的最低表示相似度。
        min_shared_references: citation-neighbor 类型的最低共享引用数。

    返回:
        stress set 记录列表。
    """
    try:
        rows: list[dict] = []
        for index, relation in enumerate(relations, start=1):
            if not _is_negative_candidate(relation):
                continue
            title_similarity = _first_float(relation, ["title_similarity", "raw_title_similarity"])
            embedding_similarity = _first_float(
                relation,
                ["embedding_similarity", "transformer_cosine", "full_similarity", "cosine_similarity", "score"],
            )
            author_overlap = _first_float(relation, ["author_overlap", "author_jaccard"])
            shared_reference_count = _shared_reference_count(relation)
            stress_level, stress_type, usable_as_primary_negative, rationale = _classify_stress_type(
                relation,
                title_similarity=title_similarity,
                embedding_similarity=embedding_similarity,
                author_overlap=author_overlap,
                shared_reference_count=shared_reference_count,
                min_title_similarity=min_title_similarity,
                min_embedding_similarity=min_embedding_similarity,
                min_shared_references=min_shared_references,
            )
            pair_id = _clean(relation.get("pair_id")) or f"stress_pair_{index:06d}"
            rows.append(
                {
                    "stress_pair_id": f"stress_pair_{len(rows) + 1:06d}",
                    "pair_id": pair_id,
                    "source_document_id": relation.get("source_document_id", ""),
                    "target_document_id": relation.get("target_document_id", ""),
                    "stress_level": stress_level,
                    "stress_type": stress_type,
                    "usable_as_primary_negative": usable_as_primary_negative,
                    "stress_rationale": "; ".join(rationale),
                    "expected_label": int(relation.get("expected_label", 0) or 0),
                    "expected_agenda_label": int(relation.get("expected_agenda_label", 0) or 0),
                    "title_similarity": round(title_similarity, 6),
                    "embedding_similarity": round(embedding_similarity, 6),
                    "author_overlap": round(author_overlap, 6),
                    "shared_reference_count": shared_reference_count,
                    "identifier_conflict": _identifier_conflict(relation),
                    "version_risk_score": round(_first_float(relation, ["version_risk_score", "version_boundary_score"]), 6),
                    "label_type": relation.get("label_type", ""),
                    "label_reason": relation.get("label_reason", ""),
                    "relation_label": relation.get("relation_label", ""),
                    "label_source": relation.get("label_source", ""),
                    "label_strength": relation.get("label_strength", ""),
                }
            )
        LOGGER.info("hard-negative stress set 构建完成: input=%s output=%s", len(relations), len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建 hard-negative stress set 失败")
        raise


def build_hard_negative_stress_set_from_paths(
    relation_paths: list[str | Path],
    limit: int | None = None,
    min_title_similarity: float = 0.80,
    min_embedding_similarity: float = 0.75,
    min_shared_references: int = 2,
) -> list[dict]:
    """从一个或多个文件读取关系并构建 stress set。

    参数:
        relation_paths: 输入 JSONL 或 Parquet 文件列表。
        limit: 最多读取记录数，跨文件累计。
        min_title_similarity: 高置信压力测试的最低标题相似度。
        min_embedding_similarity: 高置信压力测试的最低表示相似度。
        min_shared_references: citation-neighbor 类型的最低共享引用数。

    返回:
        stress set 记录列表。
    """
    relations: list[dict] = []
    try:
        for relation_path in relation_paths:
            remaining_limit = None if limit is None else max(0, limit - len(relations))
            if remaining_limit == 0:
                break
            relations.extend(read_records(relation_path, limit=remaining_limit))
        return build_hard_negative_stress_set(
            relations,
            min_title_similarity=min_title_similarity,
            min_embedding_similarity=min_embedding_similarity,
            min_shared_references=min_shared_references,
        )
    except Exception:
        LOGGER.exception("从文件构建 hard-negative stress set 失败: paths=%s", relation_paths)
        raise


def _serialize_csv_value(value: object) -> object:
    """序列化 CSV 单元格。

    参数:
        value: 原始值。

    返回:
        CSV 可写值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 明细。

    参数:
        path: 输出 CSV 路径。
        rows: stress set 记录。

    返回:
        无。
    """
    fields = list(PREFERRED_FIELDS)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_csv_value(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出 hard-negative stress CSV 失败: %s", path)
        raise


def _summary(rows: list[dict]) -> dict:
    """构建 stress set 摘要。

    参数:
        rows: stress set 记录。

    返回:
        摘要记录。
    """
    level_counts = Counter(str(row.get("stress_level", "")) for row in rows)
    type_counts = Counter(str(row.get("stress_type", "")) for row in rows)
    return {
        "stress_pair_count": len(rows),
        "high_confidence_non_identity_count": level_counts.get("high_confidence_non_identity", 0),
        "version_risk_ambiguous_count": level_counts.get("version_risk_ambiguous", 0),
        "weak_pseudo_negative_count": level_counts.get("weak_pseudo_negative", 0),
        "primary_negative_count": sum(1 for row in rows if row.get("usable_as_primary_negative") is True),
        "stress_type_count": len(type_counts),
        "stress_types": sorted(type_counts),
        "stress_set_status": "ready" if rows else "empty",
        "claim_boundary": "该集合是 pseudo-gold stress test，不等同人工 gold benchmark。",
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出 Markdown 路径。
        rows: stress set 记录。
        summary: 摘要记录。

    返回:
        无。
    """
    type_counts = Counter(str(row.get("stress_type", "")) for row in rows)
    lines = [
        "# Hard-Negative Stress Set",
        "",
        "## 摘要",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## 类型分布", ""])
    for stress_type, count in sorted(type_counts.items()):
        lines.append(f"- {stress_type}: {count}")
    lines.extend(
        [
            "",
            "## 主张边界",
            "",
            "该集合用于 agenda-level non-identity 压力测试，不等同人工 gold。version_risk_ambiguous 只用于 manual_review 机制评估，不作为普通负例。",
        ]
    )
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 hard-negative stress Markdown 失败: %s", path)
        raise


def write_hard_negative_stress_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 hard-negative stress set 产物。

    参数:
        rows: stress set 记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(rows, directory / "hard_negative_stress_pairs.jsonl")
        _write_csv(directory / "hard_negative_stress_pairs.csv", rows)
        summary = _summary(rows)
        write_records([summary], directory / "hard_negative_stress_summary.jsonl")
        _write_markdown(directory / "hard_negative_stress_report.md", rows, summary)
    except Exception:
        LOGGER.exception("写出 hard-negative stress set 产物失败: %s", output_dir)
        raise
