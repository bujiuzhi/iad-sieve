"""IAD-Bench-Open-v3 数据源扩展计划模块。"""

from __future__ import annotations

import csv
import logging
import math
import re
from collections import Counter
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "plan_id",
    "source_type",
    "status",
    "priority",
    "topic_id",
    "current_document_count",
    "target_document_count",
    "missing_document_count",
    "current_pair_count",
    "target_pair_count",
    "missing_pair_count",
    "current_topic_count",
    "target_topic_count",
    "missing_topic_count",
    "target_pairs_per_topic",
    "target_records_per_topic",
    "fetch_command",
    "weak_label_command",
    "command_template",
    "reviewer_value",
    "paper_claim_boundary",
]


def _label_strength(row: dict) -> str:
    """读取标签强度。

    参数:
        row: pair 记录。

    返回:
        小写标签强度。
    """
    return str(row.get("label_strength", "") or "").strip().lower()


def _label_source(row: dict) -> str:
    """读取标签来源。

    参数:
        row: pair 记录。

    返回:
        小写标签来源。
    """
    return str(row.get("label_source", "") or "").strip().lower()


def _topic_id(row: dict) -> str:
    """读取 pair 的 OpenAlex topic ID。

    参数:
        row: pair 记录。

    返回:
        topic ID；缺失时返回 unknown。
    """
    for field_name in ["topic_id", "primary_topic", "openalex_topic_id"]:
        value = row.get(field_name)
        if value:
            return str(value).strip()
    provenance = row.get("label_provenance")
    if isinstance(provenance, dict):
        for field_name in ["primary_topic", "topic_id", "openalex_topic_id"]:
            value = provenance.get(field_name)
            if value:
                return str(value).replace("openalex:", "").strip()
    return "unknown"


def _safe_plan_suffix(value: str) -> str:
    """生成安全 plan_id 后缀。

    参数:
        value: 原始 topic ID。

    返回:
        只包含字母、数字和下划线的后缀。
    """
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    return cleaned.strip("_") or "unknown"


def _normalize_topic_seed_ids(topic_seed_ids: list[str] | tuple[str, ...] | None) -> list[str]:
    """规范化外部提供的 topic seed 列表。

    参数:
        topic_seed_ids: topic ID 列表。

    返回:
        去重后的 topic ID 列表。
    """
    normalized: list[str] = []
    for topic_id in topic_seed_ids or []:
        cleaned = str(topic_id).strip()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return normalized


def _openalex_fetch_command(topic_id: str, target_records_per_topic: int) -> str:
    """构造单 topic OpenAlex Works 拉取命令。

    参数:
        topic_id: OpenAlex topic ID。
        target_records_per_topic: 每个 topic 目标 Works 数。

    返回:
        可执行命令字符串。
    """
    safe_topic = _safe_plan_suffix(topic_id)
    return (
        "python -m iad_sieve.cli fetch-openalex-works "
        f"--output data/raw/openalex/open_v3_{safe_topic}_works.jsonl "
        f"--summary-output outputs/openalex_api_ingestion_open_v3/{safe_topic}/ingestion_summary.jsonl "
        f'--filter "primary_topic.id:{topic_id},publication_year:2024,type:article" '
        '--select "id,doi,display_name,publication_year,authorships,primary_topic,topics,referenced_works,abstract_inverted_index" '
        "--per-page 100 "
        f"--max-records {target_records_per_topic}"
    )


def _openalex_weak_label_command(topic_id: str, target_pairs_per_topic: int) -> str:
    """构造单 topic OpenAlex weak-label 转换命令。

    参数:
        topic_id: OpenAlex topic ID。
        target_pairs_per_topic: 每个 topic 目标 hard negative pair 数。

    返回:
        可执行命令字符串。
    """
    safe_topic = _safe_plan_suffix(topic_id)
    return (
        "python -m iad_sieve.cli prepare-openalex-weak-labels "
        f"--works data/raw/openalex/open_v3_{safe_topic}_works.jsonl "
        f"--dataset-name open_v3_{safe_topic} "
        f"--output-dir outputs/openalex_api_open_v3/{safe_topic} "
        "--min-shared-references 1 "
        f"--max-pairs-per-topic {target_pairs_per_topic} "
        f"--max-pairs {target_pairs_per_topic}"
    )


def build_open_v3_source_plan_rows(
    pairs: list[dict],
    documents: list[dict],
    min_documents: int = 20_000,
    min_gold_pairs: int = 2_000,
    min_silver_pairs: int = 50_000,
    min_topics: int = 30,
    target_records_per_topic: int = 2_000,
    topic_seed_ids: list[str] | tuple[str, ...] | None = None,
) -> list[dict]:
    """构建 IAD-Bench-Open-v3 数据源扩展计划。

    参数:
        pairs: IAD-Bench pair 记录。
        documents: IAD-Bench document 记录。
        min_documents: Open-v3 目标最少文档数。
        min_gold_pairs: Open-v3 目标最少公开 gold pair 数。
        min_silver_pairs: Open-v3 目标最少 silver hard negative pair 数。
        min_topics: Open-v3 目标最少 OpenAlex topic 数。
        target_records_per_topic: 每个 OpenAlex topic 的目标 Works 数。
        topic_seed_ids: 可选 OpenAlex topic seed 列表。

    返回:
        数据源扩展计划记录列表。
    """
    try:
        strength_counts = Counter(_label_strength(row) for row in pairs)
        silver_pairs = [row for row in pairs if _label_strength(row) == "silver" and (_label_source(row) in {"", "openalex"})]
        topic_ids = sorted({_topic_id(row) for row in silver_pairs if _topic_id(row) != "unknown"})
        seed_topic_ids = _normalize_topic_seed_ids(topic_seed_ids)
        all_planned_topics = []
        for topic_id in [*topic_ids, *seed_topic_ids]:
            if topic_id not in all_planned_topics:
                all_planned_topics.append(topic_id)
        document_count = len(documents)
        gold_pair_count = strength_counts.get("gold", 0)
        silver_pair_count = len(silver_pairs)
        current_topic_count = len(topic_ids)
        missing_document_count = max(0, min_documents - document_count)
        missing_gold_pair_count = max(0, min_gold_pairs - gold_pair_count)
        missing_silver_pair_count = max(0, min_silver_pairs - silver_pair_count)
        missing_topic_count = max(0, min_topics - current_topic_count)
        target_pairs_per_topic = max(1, math.ceil(min_silver_pairs / min_topics)) if min_topics else min_silver_pairs
        rows: list[dict] = [
            {
                "plan_id": "expand_public_gold",
                "source_type": "public_gold",
                "status": "needs_public_data" if missing_gold_pair_count else "defensible",
                "priority": 1,
                "current_document_count": document_count,
                "target_document_count": min_documents,
                "missing_document_count": missing_document_count,
                "current_pair_count": gold_pair_count,
                "target_pair_count": min_gold_pairs,
                "missing_pair_count": missing_gold_pair_count,
                "command_template": (
                    "python -m iad_sieve.cli prepare-deepmatcher "
                    "--table-a data/raw/deepmatcher/{dataset_name}/tableA.csv "
                    "--table-b data/raw/deepmatcher/{dataset_name}/tableB.csv "
                    "--pairs data/raw/deepmatcher/{dataset_name}/{split}.csv "
                    "--dataset-name {dataset_name} "
                    "--output-dir outputs/deepmatcher_open_v3/{dataset_name}/{split}"
                ),
                "reviewer_value": "补齐公开 same_work gold，降低 small-gold pilot 质疑。",
                "paper_claim_boundary": "公开 gold 扩展完成前，只能写 v2 阶段性 same_work 结果。",
            },
            {
                "plan_id": "expand_openalex_topics",
                "source_type": "openalex_topic_hard_negative",
                "status": "needs_public_data" if missing_silver_pair_count or missing_topic_count else "defensible",
                "priority": 2,
                "current_document_count": document_count,
                "target_document_count": min_documents,
                "missing_document_count": missing_document_count,
                "current_pair_count": silver_pair_count,
                "target_pair_count": min_silver_pairs,
                "missing_pair_count": missing_silver_pair_count,
                "current_topic_count": current_topic_count,
                "target_topic_count": min_topics,
                "missing_topic_count": missing_topic_count,
                "target_pairs_per_topic": target_pairs_per_topic,
                "target_records_per_topic": target_records_per_topic,
                "command_template": (
                    "python -m iad_sieve.cli fetch-openalex-works "
                    "--output data/raw/openalex/open_v3_{topic_id}_works.jsonl "
                    "--summary-output outputs/openalex_api_ingestion_open_v3/{topic_id}/ingestion_summary.jsonl "
                    '--filter "primary_topic.id:{topic_id},publication_year:2024,type:article" '
                    '--select "id,doi,display_name,publication_year,authorships,primary_topic,topics,referenced_works,abstract_inverted_index" '
                    f"--per-page 100 --max-records {target_records_per_topic}"
                ),
                "weak_label_command": (
                    "python -m iad_sieve.cli prepare-openalex-weak-labels "
                    "--works data/raw/openalex/open_v3_{topic_id}_works.jsonl "
                    "--dataset-name open_v3_{topic_id} "
                    "--output-dir outputs/openalex_api_open_v3/{topic_id} "
                    "--min-shared-references 1 "
                    f"--max-pairs-per-topic {target_pairs_per_topic} --max-pairs {target_pairs_per_topic}"
                ),
                "reviewer_value": "把 hard negative 从单 topic 压力测试扩展为跨 topic 稳定性证据。",
                "paper_claim_boundary": "跨 topic 完成前，不能写 hard-negative 结论已跨领域稳定。",
            },
        ]
        for index, topic_id in enumerate(all_planned_topics, start=1):
            rows.append(
                {
                    "plan_id": f"fetch_openalex_topic_{_safe_plan_suffix(topic_id)}",
                    "source_type": "openalex_topic_hard_negative",
                    "status": "already_seen" if topic_id in topic_ids else "planned",
                    "priority": 10 + index,
                    "topic_id": topic_id,
                    "target_pairs_per_topic": target_pairs_per_topic,
                    "target_records_per_topic": target_records_per_topic,
                    "fetch_command": _openalex_fetch_command(topic_id, target_records_per_topic),
                    "weak_label_command": _openalex_weak_label_command(topic_id, target_pairs_per_topic),
                    "reviewer_value": "生成单 topic hard negative 候选，服务 Open-v3 跨 topic 扩展。",
                    "paper_claim_boundary": "该 topic 转换后仍是 silver hard negative，不是人工 gold。",
                }
            )
        rows.extend(
            [
                {
                    "plan_id": "rebuild_iad_bench_open_v3",
                    "source_type": "benchmark_rebuild",
                    "status": "waiting_source_inputs",
                    "priority": 90,
                    "command_template": (
                        "python -m iad_sieve.cli build-iad-bench "
                        "--source-dirs outputs/deepmatcher_open_v3/{public_gold_dirs} outputs/openalex_api_open_v3/{topic_eval_dirs} "
                        "--output-dir outputs/iad_bench_open_v3 "
                        "--train-ratio 0.8 --dev-ratio 0.1 --seed 42"
                    ),
                    "reviewer_value": "统一公开 gold 与多 topic silver，生成可复核 Open-v3 benchmark。",
                    "paper_claim_boundary": "重建完成并通过 audit 前，不得声称 Open-v3 已完成。",
                },
                {
                    "plan_id": "human_audit_deferred",
                    "source_type": "human_audit",
                    "status": "deferred_enhancement",
                    "priority": 99,
                    "current_pair_count": strength_counts.get("human_audit", 0),
                    "target_pair_count": "500-1000",
                    "missing_pair_count": 0,
                    "reviewer_value": "人工 gold 保留为后续增强，避免阻塞当前公开数据路线。",
                    "paper_claim_boundary": "未完成标注前，不能写已有人工 gold 或 human validation。",
                },
            ]
        )
        rows.sort(key=lambda row: int(row["priority"]))
        LOGGER.info("Open-v3 数据源扩展计划完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建 Open-v3 数据源扩展计划失败")
        raise


def build_open_v3_source_plan_rows_from_paths(
    pairs_path: str | Path,
    documents_path: str | Path,
    min_documents: int = 20_000,
    min_gold_pairs: int = 2_000,
    min_silver_pairs: int = 50_000,
    min_topics: int = 30,
    target_records_per_topic: int = 2_000,
    topic_seed_ids: list[str] | tuple[str, ...] | None = None,
) -> list[dict]:
    """从 IAD-Bench 文件构建 Open-v3 数据源扩展计划。

    参数:
        pairs_path: IAD-Bench pair JSONL。
        documents_path: IAD-Bench document JSONL。
        min_documents: Open-v3 目标最少文档数。
        min_gold_pairs: Open-v3 目标最少公开 gold pair 数。
        min_silver_pairs: Open-v3 目标最少 silver hard negative pair 数。
        min_topics: Open-v3 目标最少 OpenAlex topic 数。
        target_records_per_topic: 每个 OpenAlex topic 的目标 Works 数。
        topic_seed_ids: 可选 OpenAlex topic seed 列表。

    返回:
        数据源扩展计划记录列表。
    """
    try:
        return build_open_v3_source_plan_rows(
            pairs=read_records(pairs_path),
            documents=read_records(documents_path),
            min_documents=min_documents,
            min_gold_pairs=min_gold_pairs,
            min_silver_pairs=min_silver_pairs,
            min_topics=min_topics,
            target_records_per_topic=target_records_per_topic,
            topic_seed_ids=topic_seed_ids,
        )
    except Exception:
        LOGGER.exception("读取 Open-v3 数据源扩展计划输入失败")
        raise


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 计划记录。

    返回:
        无。
    """
    fields = [field for field in PREFERRED_FIELDS if any(field in row for row in rows)]
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    except OSError:
        LOGGER.exception("写出 Open-v3 数据源扩展计划 CSV 失败: %s", path)
        raise


def _summary(rows: list[dict]) -> dict:
    """构建 Open-v3 数据源扩展计划汇总。

    参数:
        rows: 计划记录。

    返回:
        汇总记录。
    """
    status_counts = Counter(str(row.get("status", "")) for row in rows)
    return {
        "plan_count": len(rows),
        "needs_public_data_count": status_counts.get("needs_public_data", 0),
        "planned_topic_count": status_counts.get("planned", 0),
        "already_seen_topic_count": status_counts.get("already_seen", 0),
        "deferred_enhancement_count": status_counts.get("deferred_enhancement", 0),
        "waiting_source_inputs_count": status_counts.get("waiting_source_inputs", 0),
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        rows: 计划记录。
        summary: 汇总记录。

    返回:
        无。
    """
    fields = ["plan_id", "source_type", "status", "priority", "missing_pair_count", "missing_topic_count", "reviewer_value", "paper_claim_boundary"]
    lines = [
        "# IAD-Bench-Open-v3 Source Plan",
        "",
        "## 使用边界",
        "",
        "该计划把 Open-v3 数据差距转换为公开数据采集与转换任务；OpenAlex 仍是 silver，人工 gold 后置。",
        "",
        "## 汇总",
        "",
        f"- plan_count: {summary['plan_count']}",
        f"- needs_public_data_count: {summary['needs_public_data_count']}",
        f"- planned_topic_count: {summary['planned_topic_count']}",
        f"- already_seen_topic_count: {summary['already_seen_topic_count']}",
        f"- deferred_enhancement_count: {summary['deferred_enhancement_count']}",
        f"- waiting_source_inputs_count: {summary['waiting_source_inputs_count']}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/") for field in fields) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 Open-v3 数据源扩展计划 Markdown 失败: %s", path)
        raise


def write_open_v3_source_plan_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出 Open-v3 数据源扩展计划产物。

    参数:
        rows: 计划记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _summary(rows)
    try:
        write_records(rows, directory / "open_v3_source_plan.jsonl")
        write_records([summary], directory / "open_v3_source_plan_summary.jsonl")
        _write_csv(directory / "open_v3_source_plan.csv", rows)
        _write_markdown(directory / "open_v3_source_plan.md", rows, summary)
    except Exception:
        LOGGER.exception("写出 Open-v3 数据源扩展计划失败: %s", output_dir)
        raise
