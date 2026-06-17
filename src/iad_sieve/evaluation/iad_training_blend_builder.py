"""IAD-Risk gold/silver 训练混合输入构建模块。"""

from __future__ import annotations

import csv
import logging
import random
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from iad_sieve.evaluation.iad_risk_model import AGENDA_FEATURE_FIELDS, IDENTITY_FEATURE_FIELDS, RISK_FEATURE_FIELDS
from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
DEFAULT_RELATION_LABELS = ["same_work", "unrelated", "agenda_non_identity"]
TRAINING_RELATION_FIELDS = [
    "pair_id",
    "source_pair_id",
    "original_pair_id",
    "source_document_id",
    "target_document_id",
    "relation_label",
    "label_strength",
    "label_source",
    "split",
    "original_split",
    "training_evidence_scope",
    "training_label_boundary",
    "expected_label",
    "expected_agenda_label",
    "identity_score",
    "duplicate_score",
    "agenda_score",
    "topic_score",
    "agenda_non_identity_score",
    "false_merge_risk",
]
SUMMARY_FIELDS = [
    "evidence_layer",
    "system",
    "metric_target",
    "input_path_count",
    "input_relation_count",
    "feature_complete_count",
    "skipped_missing_feature_count",
    "selected_pair_count",
    "target_per_relation",
    "relation_label_counts",
    "label_strength_counts",
    "label_source_counts",
    "missing_relation_labels",
    "training_blend_ready",
    "train_ratio",
    "dev_ratio",
    "seed",
    "model_claim_boundary",
]


def _clean(value: object) -> str:
    """清理字符串字段。

    参数:
        value: 原始字段值。

    返回:
        去除多余空白后的字符串。
    """
    return " ".join(str(value or "").split())


def _safe_int(value: object, default: int = 0) -> int:
    """安全解析整数。

    参数:
        value: 原始值。
        default: 解析失败时返回的默认值。

    返回:
        整数值。
    """
    try:
        return int(value if value is not None else default)
    except (TypeError, ValueError):
        LOGGER.warning("IAD 训练混合输入整数字段无法解析: %s", value)
        return default


def _parse_relation_labels(relation_labels: Iterable[str] | str | None) -> list[str]:
    """解析需要纳入训练混合输入的关系标签。

    参数:
        relation_labels: 关系标签列表或逗号分隔字符串。

    返回:
        去重后的关系标签列表。
    """
    raw_labels = DEFAULT_RELATION_LABELS if relation_labels is None else relation_labels
    if isinstance(raw_labels, str):
        candidates = raw_labels.split(",")
    else:
        candidates = list(raw_labels)
    labels: list[str] = []
    seen: set[str] = set()
    for label in candidates:
        cleaned_label = _clean(label)
        if cleaned_label and cleaned_label not in seen:
            labels.append(cleaned_label)
            seen.add(cleaned_label)
    if len(labels) < 2:
        raise ValueError("relation_labels 至少需要两个关系标签")
    return labels


def _infer_relation_label(relation: dict) -> str:
    """推断 IAD 关系标签。

    参数:
        relation: 关系记录。

    返回:
        same_work、agenda_non_identity、unrelated 或显式 relation_label。
    """
    explicit_label = _clean(relation.get("relation_label"))
    if explicit_label:
        return explicit_label
    expected_label = _safe_int(relation.get("expected_label"))
    expected_agenda_label = _safe_int(relation.get("expected_agenda_label"))
    if expected_label == 1:
        return "same_work"
    if expected_agenda_label == 1:
        return "agenda_non_identity"
    return "unrelated"


def _infer_label_strength(relation: dict) -> str:
    """推断标签强度。

    参数:
        relation: 关系记录。

    返回:
        gold、silver、proxy 或空字符串。
    """
    explicit_strength = _clean(relation.get("label_strength"))
    if explicit_strength:
        return explicit_strength
    label_type = _clean(relation.get("label_type")).lower()
    if "gold" in label_type or "deepmatcher" in label_type:
        return "gold"
    if "proxy" in label_type or "scirepeval" in label_type or "scidocs" in label_type:
        return "proxy"
    if "silver" in label_type or "weak" in label_type or "openalex" in label_type or "opencitations" in label_type:
        return "silver"
    return ""


def _infer_label_source(relation: dict, label_strength: str) -> str:
    """推断标签来源。

    参数:
        relation: 关系记录。
        label_strength: 已推断的标签强度。

    返回:
        标签来源名称。
    """
    explicit_source = _clean(relation.get("label_source"))
    if explicit_source:
        return explicit_source
    label_type = _clean(relation.get("label_type")).lower()
    candidate_sources = " ".join(_clean(source).lower() for source in relation.get("candidate_sources", []))
    if "deepmatcher" in label_type:
        return "deepmatcher"
    if "scirepeval" in label_type or "scidocs" in label_type:
        return "scirepeval"
    if "opencitations" in label_type or "opencitations" in candidate_sources:
        return "openalex_opencitations"
    if "openalex" in label_type or "openalex" in candidate_sources:
        return "openalex"
    return label_strength or "unknown"


def _has_group_feature(relation: dict, feature_fields: list[str]) -> bool:
    """判断记录是否至少含有一个指定特征组字段。

    参数:
        relation: 关系记录。
        feature_fields: 特征字段列表。

    返回:
        至少有一个字段存在时返回 True。
    """
    return any(field in relation for field in feature_fields)


def _feature_complete(relation: dict) -> bool:
    """判断记录是否具备 IAD-Risk 三个空间的训练特征。

    参数:
        relation: 关系记录。

    返回:
        三个特征组均有字段时返回 True。
    """
    return (
        _has_group_feature(relation, IDENTITY_FEATURE_FIELDS)
        and _has_group_feature(relation, AGENDA_FEATURE_FIELDS)
        and _has_group_feature(relation, RISK_FEATURE_FIELDS)
    )


def _normalize_relation(relation: dict, evidence_scope: str) -> dict:
    """标准化训练候选关系。

    参数:
        relation: 原始关系记录。
        evidence_scope: 训练证据范围。

    返回:
        补全标签、来源和声明边界后的关系记录。
    """
    normalized = dict(relation)
    original_pair_id = _clean(relation.get("pair_id")) or _clean(relation.get("source_pair_id"))
    relation_label = _infer_relation_label(relation)
    label_strength = _infer_label_strength(relation)
    label_source = _infer_label_source(relation, label_strength)
    if relation_label == "same_work":
        normalized["expected_label"] = 1
        normalized["expected_agenda_label"] = _safe_int(normalized.get("expected_agenda_label"), 1) or 1
    elif relation_label == "agenda_non_identity":
        normalized["expected_label"] = 0
        normalized["expected_agenda_label"] = 1
    elif relation_label == "unrelated":
        normalized["expected_label"] = 0
        normalized["expected_agenda_label"] = 0
    normalized["original_pair_id"] = original_pair_id
    normalized["original_split"] = _clean(relation.get("split"))
    normalized["relation_label"] = relation_label
    normalized["label_strength"] = label_strength
    normalized["label_source"] = label_source
    normalized["training_evidence_scope"] = evidence_scope
    normalized["evaluation_split_strategy"] = "stratified_gold_silver_blend"
    normalized["training_label_boundary"] = (
        "same_work/unrelated 可来自公开 gold；agenda_non_identity 可来自 OpenAlex/OpenCitations/Scirepeval silver 或 proxy，不能写作人工 gold。"
    )
    return normalized


def _sample_group(candidates: list[dict], sample_count: int, rng: random.Random) -> list[dict]:
    """确定性抽样候选关系。

    参数:
        candidates: 候选关系。
        sample_count: 抽样数量。
        rng: 随机数生成器。

    返回:
        抽样后的关系列表。
    """
    ordered = sorted(candidates, key=lambda row: (_clean(row.get("label_source")), _clean(row.get("original_pair_id")), _clean(row.get("source_document_id"))))
    if sample_count >= len(ordered):
        return ordered
    return sorted(rng.sample(ordered, sample_count), key=lambda row: (_clean(row.get("label_source")), _clean(row.get("original_pair_id"))))


def _assign_splits(rows: list[dict], seed: int, train_ratio: float, dev_ratio: float) -> None:
    """按 relation_label 分层写入 train/dev/test split。

    参数:
        rows: 训练关系，会被原地写入 split。
        seed: 随机种子。
        train_ratio: train 比例。
        dev_ratio: dev 比例。

    返回:
        无。
    """
    if train_ratio < 0 or dev_ratio < 0 or train_ratio + dev_ratio > 1:
        raise ValueError("train_ratio 和 dev_ratio 必须非负，且二者之和不能超过 1")
    grouped_indices: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped_indices[_clean(row.get("relation_label"))].append(index)
    rng = random.Random(seed)
    for relation_label in sorted(grouped_indices):
        indices = grouped_indices[relation_label]
        rng.shuffle(indices)
        train_count = int(len(indices) * train_ratio)
        dev_count = int(len(indices) * dev_ratio)
        train_indices = set(indices[:train_count])
        dev_indices = set(indices[train_count : train_count + dev_count])
        for index in indices:
            if index in train_indices:
                rows[index]["split"] = "train"
            elif index in dev_indices:
                rows[index]["split"] = "dev"
            else:
                rows[index]["split"] = "test"


def _reassign_pair_ids(rows: list[dict]) -> None:
    """写入稳定训练 pair ID。

    参数:
        rows: 训练关系，会被原地更新 pair_id。

    返回:
        无。
    """
    rows.sort(key=lambda row: (_clean(row.get("relation_label")), _clean(row.get("label_source")), _clean(row.get("original_pair_id"))))
    for index, row in enumerate(rows, start=1):
        row["source_pair_id"] = _clean(row.get("source_pair_id")) or _clean(row.get("original_pair_id"))
        row["pair_id"] = f"iadtrain_{index:06d}"


def _build_summary(
    *,
    input_path_count: int,
    input_relation_count: int,
    feature_complete_count: int,
    skipped_missing_feature_count: int,
    selected_rows: list[dict],
    relation_labels: list[str],
    target_per_relation: int,
    seed: int,
    train_ratio: float,
    dev_ratio: float,
    evidence_scope: str,
) -> dict:
    """构建训练混合输入摘要。

    参数:
        input_path_count: 输入文件数量。
        input_relation_count: 输入关系数量。
        feature_complete_count: 特征完整候选数量。
        skipped_missing_feature_count: 缺少特征而跳过的数量。
        selected_rows: 最终训练关系。
        relation_labels: 目标关系标签。
        target_per_relation: 每类抽样数量。
        seed: 随机种子。
        train_ratio: train 比例。
        dev_ratio: dev 比例。
        evidence_scope: 训练证据范围。

    返回:
        摘要记录。
    """
    relation_counts = Counter(_clean(row.get("relation_label")) for row in selected_rows)
    label_strength_counts = Counter(_clean(row.get("label_strength")) for row in selected_rows)
    label_source_counts = Counter(_clean(row.get("label_source")) for row in selected_rows)
    missing_relation_labels = [label for label in relation_labels if relation_counts.get(label, 0) <= 0]
    ready = not missing_relation_labels and target_per_relation > 0 and bool(selected_rows)
    return {
        "evidence_layer": "iad_risk_training_blend",
        "system": "iad_risk_gold_silver_training_blend",
        "metric_target": "iad_risk_training_input_construction",
        "input_path_count": input_path_count,
        "input_relation_count": input_relation_count,
        "feature_complete_count": feature_complete_count,
        "skipped_missing_feature_count": skipped_missing_feature_count,
        "selected_pair_count": len(selected_rows),
        "target_per_relation": target_per_relation,
        "relation_label_counts": dict(sorted(relation_counts.items())),
        "label_strength_counts": dict(sorted(label_strength_counts.items())),
        "label_source_counts": dict(sorted(label_source_counts.items())),
        "missing_relation_labels": missing_relation_labels,
        "training_blend_ready": ready,
        "train_ratio": train_ratio,
        "dev_ratio": dev_ratio,
        "seed": seed,
        "training_evidence_scope": evidence_scope,
        "model_claim_boundary": "该输入可支持 gold+silver IAD-Risk 训练实验；不能替代人工 gold，也不能单独支撑强泛化结论。",
    }


def build_iad_training_blend(
    relations: list[dict],
    relation_labels: Iterable[str] | str | None = None,
    max_per_relation: int | None = None,
    seed: int = 42,
    train_ratio: float = 0.8,
    dev_ratio: float = 0.1,
    evidence_scope: str = "gold_silver_training_blend",
    input_path_count: int = 0,
) -> tuple[list[dict], dict]:
    """构建 IAD-Risk gold/silver 训练混合输入。

    参数:
        relations: 已评分关系记录。
        relation_labels: 需要纳入的关系标签。
        max_per_relation: 每类关系最多保留数量；为空时按最小类全量配平。
        seed: 抽样与 split 随机种子。
        train_ratio: train split 比例。
        dev_ratio: dev split 比例。
        evidence_scope: 训练证据范围。
        input_path_count: 输入文件数量。

    返回:
        训练关系与摘要记录。
    """
    try:
        labels = _parse_relation_labels(relation_labels)
        rng = random.Random(seed)
        normalized_rows = [_normalize_relation(relation, evidence_scope) for relation in relations]
        feature_complete_rows = [row for row in normalized_rows if _feature_complete(row)]
        grouped_rows: dict[str, list[dict]] = defaultdict(list)
        for row in feature_complete_rows:
            relation_label = _clean(row.get("relation_label"))
            if relation_label in labels:
                grouped_rows[relation_label].append(row)
        available_counts = [len(grouped_rows.get(label, [])) for label in labels]
        target_per_relation = min(available_counts) if available_counts and all(count > 0 for count in available_counts) else 0
        if max_per_relation is not None:
            target_per_relation = min(target_per_relation, max(0, int(max_per_relation)))
        selected_rows: list[dict] = []
        if target_per_relation > 0:
            for label in labels:
                selected_rows.extend(_sample_group(grouped_rows[label], target_per_relation, rng))
        _reassign_pair_ids(selected_rows)
        _assign_splits(selected_rows, seed=seed, train_ratio=train_ratio, dev_ratio=dev_ratio)
        summary = _build_summary(
            input_path_count=input_path_count,
            input_relation_count=len(relations),
            feature_complete_count=len(feature_complete_rows),
            skipped_missing_feature_count=max(0, len(relations) - len(feature_complete_rows)),
            selected_rows=selected_rows,
            relation_labels=labels,
            target_per_relation=target_per_relation,
            seed=seed,
            train_ratio=train_ratio,
            dev_ratio=dev_ratio,
            evidence_scope=evidence_scope,
        )
        LOGGER.info("IAD-Risk 训练混合输入构建完成: rows=%s target_per_relation=%s", len(selected_rows), target_per_relation)
        return selected_rows, summary
    except Exception:
        LOGGER.exception("构建 IAD-Risk 训练混合输入失败")
        raise


def build_iad_training_blend_from_paths(
    relation_paths: list[str | Path],
    relation_labels: Iterable[str] | str | None = None,
    max_per_relation: int | None = None,
    seed: int = 42,
    train_ratio: float = 0.8,
    dev_ratio: float = 0.1,
) -> tuple[list[dict], dict]:
    """从多个关系文件构建 IAD-Risk 训练混合输入。

    参数:
        relation_paths: 一个或多个已评分关系 JSONL/Parquet 文件。
        relation_labels: 需要纳入的关系标签。
        max_per_relation: 每类关系最多保留数量。
        seed: 抽样与 split 随机种子。
        train_ratio: train split 比例。
        dev_ratio: dev split 比例。

    返回:
        训练关系与摘要记录。
    """
    try:
        relations: list[dict] = []
        for relation_path in relation_paths:
            relations.extend(read_records(relation_path))
        training_rows, summary = build_iad_training_blend(
            relations=relations,
            relation_labels=relation_labels,
            max_per_relation=max_per_relation,
            seed=seed,
            train_ratio=train_ratio,
            dev_ratio=dev_ratio,
            input_path_count=len(relation_paths),
        )
        return training_rows, summary
    except Exception:
        LOGGER.exception("读取 IAD-Risk 训练混合输入失败: paths=%s", relation_paths)
        raise


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出训练混合输入 CSV。

    参数:
        path: 输出 CSV 路径。
        rows: 训练关系。

    返回:
        无。
    """
    fields = [field for field in TRAINING_RELATION_FIELDS if any(field in row for row in rows)]
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
        LOGGER.exception("写出 IAD-Risk 训练混合输入 CSV 失败: %s", path)
        raise


def _write_markdown(path: Path, summary: dict) -> None:
    """写出训练混合输入 Markdown 报告。

    参数:
        path: 输出 Markdown 路径。
        summary: 摘要记录。

    返回:
        无。
    """
    lines = [
        "# IAD-Risk Training Blend",
        "",
        "## 使用边界",
        "",
        "该文件构建 gold/silver 混合训练输入：same_work/unrelated 可来自公开 gold，agenda_non_identity 可来自公开弱监督或 proxy。它用于缓解暂未人工标注时的训练 head 缺失问题，但不能写作人工 gold。",
        "",
        "## 汇总",
        "",
    ]
    for field in SUMMARY_FIELDS:
        if field in summary:
            lines.append(f"- {field}: {summary[field]}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出 IAD-Risk 训练混合输入 Markdown 失败: %s", path)
        raise


def write_iad_training_blend_outputs(training_rows: list[dict], summary: dict, output_dir: str | Path) -> None:
    """写出 IAD-Risk 训练混合输入产物。

    参数:
        training_rows: 训练关系。
        summary: 摘要记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    try:
        write_records(training_rows, directory / "iad_training_relations.jsonl")
        write_records([summary], directory / "iad_training_blend_summary.jsonl")
        _write_csv(directory / "iad_training_blend.csv", training_rows)
        _write_markdown(directory / "iad_training_blend.md", summary)
    except Exception:
        LOGGER.exception("写出 IAD-Risk 训练混合输入失败: %s", output_dir)
        raise
