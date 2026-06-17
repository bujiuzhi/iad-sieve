"""IAD-Bench 公开来源候选 registry 模块。"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
DEFAULT_PUBLIC_GOLD_SOURCE_IDS = ["deepmatcher_dblp_scholar"]
DEFAULT_OPENALEX_TOPIC_SEED_IDS = ["T10009"]
READY_ADAPTERS = {"prepare-deepmatcher", "prepare-openalex-weak-labels"}
PUBLIC_GOLD_SOURCE_CATALOG: dict[str, dict[str, str]] = {
    "deepmatcher_dblp_scholar": {
        "source_name": "DeepMatcher DBLP-Scholar",
        "source_domain": "citation",
        "dataset_name": "DBLP-Scholar",
        "source_url": "https://github.com/anhaidgroup/deepmatcher/blob/master/Datasets.md",
        "evidence_url": "https://github.com/anhaidgroup/deepmatcher",
        "download_note": "Use the preprocessed DBLP-Scholar download from DeepMatcher Datasets.md.",
    },
    "deepmatcher_amazon_google": {
        "source_name": "DeepMatcher Amazon-Google",
        "source_domain": "software_product",
        "dataset_name": "Amazon-Google",
        "source_url": "https://github.com/anhaidgroup/deepmatcher/blob/master/Datasets.md",
        "evidence_url": "https://github.com/anhaidgroup/deepmatcher",
        "download_note": "Use the preprocessed Amazon-Google download from DeepMatcher Datasets.md.",
    },
    "deepmatcher_walmart_amazon": {
        "source_name": "DeepMatcher Walmart-Amazon",
        "source_domain": "electronics_product",
        "dataset_name": "Walmart-Amazon",
        "source_url": "https://github.com/anhaidgroup/deepmatcher/blob/master/Datasets.md",
        "evidence_url": "https://github.com/anhaidgroup/deepmatcher",
        "download_note": "Use the preprocessed Walmart-Amazon download from DeepMatcher Datasets.md.",
    },
    "deepmatcher_abt_buy": {
        "source_name": "DeepMatcher Abt-Buy",
        "source_domain": "product_text",
        "dataset_name": "Abt-Buy",
        "source_url": "https://github.com/anhaidgroup/deepmatcher/blob/master/Datasets.md",
        "evidence_url": "https://github.com/anhaidgroup/deepmatcher",
        "download_note": "Use the preprocessed Abt-Buy download from DeepMatcher Datasets.md.",
    },
    "ditto_wdc_products": {
        "source_name": "WDC Products",
        "source_domain": "product_matching",
        "dataset_name": "WDC Products",
        "source_url": "https://arxiv.org/abs/2301.09521",
        "evidence_url": "https://github.com/megagonlabs/ditto",
        "download_note": "Requires a WDC-to-IAD converter before it can enter build-iad-bench.",
    },
}
PREFERRED_FIELDS = [
    "candidate_id",
    "relation_label",
    "candidate_status",
    "source_family",
    "source_id",
    "source_name",
    "source_domain",
    "planned_label_strength",
    "planned_label_source",
    "adapter_format",
    "existing_adapter",
    "target_pair_count",
    "minimum_balance_pair_count",
    "target_pairs_per_new_source",
    "current_dominant_source",
    "current_source_count",
    "missing_source_count",
    "source_url",
    "evidence_url",
    "download_note",
    "command_template",
    "fetch_command",
    "weak_label_command",
    "reviewer_value",
    "paper_claim_boundary",
]


def _clean(value: object) -> str:
    """清理字符串字段。

    参数:
        value: 原始值。

    返回:
        去除空白后的字符串。
    """
    return str(value or "").strip()


def _safe_suffix(value: str) -> str:
    """生成安全路径后缀。

    参数:
        value: 原始字符串。

    返回:
        只包含字母、数字和下划线的后缀。
    """
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    return cleaned.strip("_") or "source"


def _as_int(value: object, default: int = 0) -> int:
    """安全解析整数。

    参数:
        value: 原始值。
        default: 解析失败时返回的默认值。

    返回:
        整数值。
    """
    try:
        if value in {None, ""}:
            return default
        return int(float(str(value)))
    except (TypeError, ValueError):
        LOGGER.warning("整数解析失败，使用默认值: value=%s default=%s", value, default)
        return default


def _normalize_ids(values: list[str] | tuple[str, ...] | None, default_values: list[str]) -> list[str]:
    """规范化 ID 列表。

    参数:
        values: 用户输入 ID。
        default_values: 空输入时使用的默认 ID。

    返回:
        去重后的 ID 列表。
    """
    normalized: list[str] = []
    for value in values or default_values:
        cleaned = _clean(value)
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return normalized


def _target_pair_count(row: dict) -> int:
    """计算候选来源目标 pair 数。

    参数:
        row: provenance balance 记录。

    返回:
        目标 pair 数。
    """
    minimum_balance_pair_count = _as_int(row.get("minimum_balance_pair_count"), 0)
    target_pairs_per_new_source = _as_int(row.get("target_pairs_per_new_source"), 500)
    return max(minimum_balance_pair_count, target_pairs_per_new_source)


def _catalog_entry(source_id: str) -> dict[str, str]:
    """读取公开 gold 候选来源元数据。

    参数:
        source_id: 来源 ID。

    返回:
        来源元数据。
    """
    if source_id in PUBLIC_GOLD_SOURCE_CATALOG:
        return dict(PUBLIC_GOLD_SOURCE_CATALOG[source_id])
    safe_source_id = _safe_suffix(source_id)
    return {
        "source_name": source_id,
        "source_domain": "public_entity_matching",
        "dataset_name": source_id,
        "source_url": "",
        "evidence_url": "",
        "download_note": f"Place tableA.csv, tableB.csv and split CSV files under data/raw/deepmatcher/{safe_source_id}/.",
    }


def _deepmatcher_command(source_id: str, dataset_name: str) -> str:
    """构造 DeepMatcher 适配命令模板。

    参数:
        source_id: 来源 ID。
        dataset_name: DeepMatcher dataset name。

    返回:
        prepare-deepmatcher 命令模板。
    """
    safe_source_id = _safe_suffix(source_id)
    return (
        "python -m iad_sieve.cli prepare-deepmatcher "
        f"--table-a data/raw/deepmatcher/{safe_source_id}/tableA.csv "
        f"--table-b data/raw/deepmatcher/{safe_source_id}/tableB.csv "
        f"--pairs data/raw/deepmatcher/{safe_source_id}/{{split}}.csv "
        f'--dataset-name "{dataset_name}" '
        f"--output-dir outputs/deepmatcher_open_v3/{safe_source_id}/{{split}}"
    )


def _public_gold_candidate(row: dict, source_id: str) -> dict:
    """构造公开 entity matching gold 候选记录。

    参数:
        row: provenance balance 记录。
        source_id: 公开 gold 来源 ID。

    返回:
        registry 候选记录。
    """
    relation_label = _clean(row.get("relation_label")) or "unknown"
    metadata = _catalog_entry(source_id)
    existing_adapter = "prepare-deepmatcher" if source_id.startswith("deepmatcher_") else "needs_converter"
    adapter_format = "deepmatcher_like_csv" if existing_adapter == "prepare-deepmatcher" else "external_entity_matching_pairwise"
    return {
        "candidate_id": f"{_safe_suffix(relation_label)}_{_safe_suffix(source_id)}",
        "relation_label": relation_label,
        "candidate_status": "requires_download" if existing_adapter == "prepare-deepmatcher" else "requires_converter",
        "source_family": "public_entity_matching_gold",
        "source_id": source_id,
        "source_name": metadata["source_name"],
        "source_domain": metadata["source_domain"],
        "planned_label_strength": "gold",
        "planned_label_source": f"public_gold_{_safe_suffix(source_id)}",
        "adapter_format": adapter_format,
        "existing_adapter": existing_adapter,
        "target_pair_count": _target_pair_count(row),
        "minimum_balance_pair_count": _as_int(row.get("minimum_balance_pair_count"), 0),
        "target_pairs_per_new_source": _as_int(row.get("target_pairs_per_new_source"), 500),
        "current_dominant_source": _clean(row.get("dominant_source")),
        "current_source_count": _as_int(row.get("current_source_count"), 0),
        "missing_source_count": _as_int(row.get("missing_source_count"), 0),
        "source_url": metadata["source_url"],
        "evidence_url": metadata["evidence_url"],
        "download_note": metadata["download_note"],
        "command_template": _deepmatcher_command(source_id, metadata["dataset_name"]) if existing_adapter == "prepare-deepmatcher" else "",
        "reviewer_value": "补充同类 relation 的第二公开来源，降低 relation 与 label_source 绑定导致的 provenance shortcut。",
        "paper_claim_boundary": "下载并转换前只能作为候选来源，不能写成已完成 source balance。",
    }


def _openalex_fetch_command(topic_id: str, target_pair_count: int) -> str:
    """构造 OpenAlex Works 拉取命令。

    参数:
        topic_id: OpenAlex topic ID。
        target_pair_count: 目标 pair 数。

    返回:
        fetch-openalex-works 命令。
    """
    safe_topic = _safe_suffix(topic_id)
    target_records = max(1000, min(target_pair_count * 2, 10000))
    return (
        "python -m iad_sieve.cli fetch-openalex-works "
        f"--output data/raw/openalex/source_registry_{safe_topic}_works.jsonl "
        f"--summary-output outputs/openalex_api_ingestion_source_registry/{safe_topic}/ingestion_summary.jsonl "
        f'--filter "primary_topic.id:{topic_id},publication_year:2024,type:article" '
        '--select "id,doi,display_name,publication_year,authorships,primary_topic,topics,referenced_works,abstract_inverted_index" '
        f"--per-page 100 --max-records {target_records}"
    )


def _opencitations_weak_label_command(topic_id: str, target_pair_count: int) -> str:
    """构造 OpenAlex/OpenCitations weak-label 转换命令。

    参数:
        topic_id: OpenAlex topic ID。
        target_pair_count: 目标 pair 数。

    返回:
        prepare-openalex-weak-labels 命令。
    """
    safe_topic = _safe_suffix(topic_id)
    return (
        "python -m iad_sieve.cli prepare-openalex-weak-labels "
        f"--works data/raw/openalex/source_registry_{safe_topic}_works.jsonl "
        f"--citations data/raw/opencitations/coci_{safe_topic}.csv "
        f"--dataset-name openalex_opencitations_{safe_topic} "
        f"--output-dir outputs/openalex_opencitations_source_registry/{safe_topic} "
        "--min-shared-references 1 "
        f"--max-pairs-per-topic {target_pair_count} "
        f"--max-pairs {target_pair_count}"
    )


def _agenda_candidate(row: dict, topic_id: str) -> dict:
    """构造 agenda_non_identity 公开 silver 候选记录。

    参数:
        row: provenance balance 记录。
        topic_id: OpenAlex topic ID。

    返回:
        registry 候选记录。
    """
    relation_label = _clean(row.get("relation_label")) or "agenda_non_identity"
    safe_topic = _safe_suffix(topic_id)
    target_pair_count = _target_pair_count(row)
    return {
        "candidate_id": f"{_safe_suffix(relation_label)}_opencitations_coci_{safe_topic}",
        "relation_label": relation_label,
        "candidate_status": "requires_openalex_and_citations_download",
        "source_family": "opencitations_augmented_openalex_hard_negative",
        "source_id": f"opencitations_coci_{safe_topic}",
        "source_name": f"OpenAlex topic {topic_id} with OpenCitations COCI",
        "source_domain": "scholarly_citation_graph",
        "planned_label_strength": "silver",
        "planned_label_source": "openalex_opencitations",
        "adapter_format": "openalex_works_plus_opencitations_coci_csv",
        "existing_adapter": "prepare-openalex-weak-labels",
        "target_pair_count": target_pair_count,
        "minimum_balance_pair_count": _as_int(row.get("minimum_balance_pair_count"), 0),
        "target_pairs_per_new_source": _as_int(row.get("target_pairs_per_new_source"), 500),
        "current_dominant_source": _clean(row.get("dominant_source")),
        "current_source_count": _as_int(row.get("current_source_count"), 0),
        "missing_source_count": _as_int(row.get("missing_source_count"), 0),
        "source_url": "https://opencitations.net/index/coci",
        "evidence_url": "https://arxiv.org/abs/1904.06052",
        "download_note": "Download or export COCI DOI-to-DOI citation edges for the selected topic works before weak-label conversion.",
        "fetch_command": _openalex_fetch_command(topic_id, target_pair_count),
        "weak_label_command": _opencitations_weak_label_command(topic_id, target_pair_count),
        "reviewer_value": "用 OpenCitations 共享引用补强 OpenAlex topic hard negative，减少纯 OpenAlex 单来源解释风险。",
        "paper_claim_boundary": "该来源仍是 silver hard negative，不是人工 gold；完成前不能写成已排除 provider-level source bias。",
    }


def _needs_registry_candidate(row: dict) -> bool:
    """判断 provenance balance 记录是否需要候选来源。

    参数:
        row: provenance balance 记录。

    返回:
        需要候选来源返回 True。
    """
    status = _clean(row.get("audit_status")).lower()
    return status in {"blocked", "high_risk"} or _as_int(row.get("missing_source_count"), 0) > 0 or _as_int(row.get("minimum_balance_pair_count"), 0) > 0


def build_iad_bench_source_candidate_registry_rows(
    provenance_balance_rows: list[dict],
    public_gold_source_ids: list[str] | tuple[str, ...] | None = None,
    openalex_topic_seed_ids: list[str] | tuple[str, ...] | None = None,
) -> list[dict]:
    """构建 IAD-Bench 公开来源候选 registry。

    参数:
        provenance_balance_rows: provenance balance plan 记录。
        public_gold_source_ids: 公开 entity matching gold 来源 ID。
        openalex_topic_seed_ids: OpenAlex topic seed ID。

    返回:
        来源候选 registry 记录。
    """
    try:
        public_sources = _normalize_ids(public_gold_source_ids, DEFAULT_PUBLIC_GOLD_SOURCE_IDS)
        topic_ids = _normalize_ids(openalex_topic_seed_ids, DEFAULT_OPENALEX_TOPIC_SEED_IDS)
        rows: list[dict] = []
        for balance_row in provenance_balance_rows:
            if not _needs_registry_candidate(balance_row):
                continue
            relation_label = _clean(balance_row.get("relation_label")).lower()
            source_family = _clean(balance_row.get("recommended_source_family")).lower()
            if relation_label in {"same_work", "unrelated"} or source_family == "public_entity_matching_gold":
                rows.extend(_public_gold_candidate(balance_row, source_id) for source_id in public_sources)
            elif relation_label == "agenda_non_identity" or "openalex" in source_family:
                rows.extend(_agenda_candidate(balance_row, topic_id) for topic_id in topic_ids)
        rows.sort(key=lambda row: (row["relation_label"], row["candidate_id"]))
        LOGGER.info("IAD-Bench 公开来源候选 registry 完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建 IAD-Bench 公开来源候选 registry 失败")
        raise


def build_iad_bench_source_candidate_registry_rows_from_paths(
    provenance_balance_plan_path: str | Path,
    public_gold_source_ids: list[str] | tuple[str, ...] | None = None,
    openalex_topic_seed_ids: list[str] | tuple[str, ...] | None = None,
) -> list[dict]:
    """从 provenance balance plan 文件构建公开来源候选 registry。

    参数:
        provenance_balance_plan_path: provenance balance plan JSONL 路径。
        public_gold_source_ids: 公开 entity matching gold 来源 ID。
        openalex_topic_seed_ids: OpenAlex topic seed ID。

    返回:
        来源候选 registry 记录。
    """
    try:
        return build_iad_bench_source_candidate_registry_rows(
            provenance_balance_rows=read_records(provenance_balance_plan_path),
            public_gold_source_ids=public_gold_source_ids,
            openalex_topic_seed_ids=openalex_topic_seed_ids,
        )
    except Exception:
        LOGGER.exception("读取 IAD-Bench 公开来源候选 registry 输入失败: %s", provenance_balance_plan_path)
        raise


def _serialize_cell(value: object) -> object:
    """序列化 CSV / Markdown 单元格。

    参数:
        value: 原始值。

    返回:
        可写入单元格的值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出公开来源候选 registry CSV。

    参数:
        path: 输出路径。
        rows: registry 记录。

    返回:
        无。
    """
    fields = [field for field in PREFERRED_FIELDS if any(field in row for row in rows)]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_cell(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出 IAD-Bench 公开来源候选 registry CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建公开来源候选 registry 汇总。

    参数:
        rows: registry 记录。

    返回:
        summary 记录。
    """
    return {
        "candidate_count": len(rows),
        "public_gold_candidate_count": sum(1 for row in rows if row.get("planned_label_strength") == "gold"),
        "silver_candidate_count": sum(1 for row in rows if row.get("planned_label_strength") == "silver"),
        "ready_with_existing_adapter_count": sum(1 for row in rows if row.get("existing_adapter") in READY_ADAPTERS),
        "requires_download_count": sum(1 for row in rows if "download" in _clean(row.get("candidate_status"))),
        "requires_converter_count": sum(1 for row in rows if row.get("candidate_status") == "requires_converter"),
        "total_target_pair_count": sum(_as_int(row.get("target_pair_count"), 0) for row in rows),
        "overall_registry_status": "planned" if rows else "empty",
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出公开来源候选 registry Markdown。

    参数:
        path: 输出路径。
        rows: registry 记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = [
        "candidate_id",
        "relation_label",
        "candidate_status",
        "source_name",
        "planned_label_strength",
        "existing_adapter",
        "target_pair_count",
        "paper_claim_boundary",
    ]
    lines = [
        "# IAD-Bench Source Candidate Registry",
        "",
        "## 使用边界",
        "",
        "该 registry 只把 provenance balance blocker 转成可执行公开来源候选；它不是新增实验结果，也不能替代真实数据下载、转换和 source-held-out 评估。",
        "",
        "## 汇总",
        "",
        f"- candidate_count: {summary['candidate_count']}",
        f"- public_gold_candidate_count: {summary['public_gold_candidate_count']}",
        f"- silver_candidate_count: {summary['silver_candidate_count']}",
        f"- ready_with_existing_adapter_count: {summary['ready_with_existing_adapter_count']}",
        f"- requires_download_count: {summary['requires_download_count']}",
        f"- requires_converter_count: {summary['requires_converter_count']}",
        f"- total_target_pair_count: {summary['total_target_pair_count']}",
        f"- overall_registry_status: {summary['overall_registry_status']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        values = [str(_serialize_cell(row.get(field, ""))).replace("\n", " ").replace("|", "/") for field in fields]
        lines.append("| " + " | ".join(values) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 IAD-Bench 公开来源候选 registry Markdown 失败: %s", path)
        raise


def write_iad_bench_source_candidate_registry_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出公开来源候选 registry 产物。

    参数:
        rows: registry 记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "iad_bench_source_candidate_registry.jsonl")
        write_records([summary], directory / "iad_bench_source_candidate_registry_summary.jsonl")
        _write_csv(directory / "iad_bench_source_candidate_registry.csv", rows)
        _write_markdown(directory / "iad_bench_source_candidate_registry.md", rows, summary)
    except Exception:
        LOGGER.exception("写出 IAD-Bench 公开来源候选 registry 失败: %s", output_dir)
        raise
