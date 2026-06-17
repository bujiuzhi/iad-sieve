"""聚类评估模块。"""

from __future__ import annotations

import logging
import csv
import random
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from iad_sieve.evaluation.risk_calibrated_protocol import assign_selective_decision


LOGGER = logging.getLogger(__name__)
CLUSTER_BOOTSTRAP_METRIC_FIELDS = [
    "b3_f1",
    "pairwise_clustering_f1",
    "cluster_contamination_rate",
    "over_merge_pair_count",
    "under_merge_pair_count",
    "largest_contaminated_cluster_size",
]
CLUSTER_BOOTSTRAP_CSV_FIELDS = [
    "system",
    "metric_scope",
    "cluster_prediction_mode",
    "pair_count",
    "bootstrap_iterations",
    "confidence_level",
    "b3_f1_point",
    "b3_f1_mean",
    "b3_f1_ci_low",
    "b3_f1_ci_high",
    "pairwise_clustering_f1_point",
    "pairwise_clustering_f1_mean",
    "pairwise_clustering_f1_ci_low",
    "pairwise_clustering_f1_ci_high",
    "cluster_contamination_rate_point",
    "cluster_contamination_rate_mean",
    "cluster_contamination_rate_ci_low",
    "cluster_contamination_rate_ci_high",
    "over_merge_pair_count_point",
    "over_merge_pair_count_mean",
    "over_merge_pair_count_ci_low",
    "over_merge_pair_count_ci_high",
    "under_merge_pair_count_point",
    "under_merge_pair_count_mean",
    "under_merge_pair_count_ci_low",
    "under_merge_pair_count_ci_high",
    "largest_contaminated_cluster_size_point",
    "largest_contaminated_cluster_size_mean",
    "largest_contaminated_cluster_size_ci_low",
    "largest_contaminated_cluster_size_ci_high",
    "cluster_score_field",
    "cluster_score_threshold",
    "risk_system",
    "risk_fpr_budget",
    "risk_fdr_budget",
    "risk_identity_threshold",
    "risk_conflict_threshold",
]


def _clean(value: object) -> str:
    """清理字符串字段。

    参数:
        value: 原始值。

    返回:
        去除空白后的字符串。
    """
    return str(value or "").strip()


def _safe_divide(numerator: int | float, denominator: int | float) -> float:
    """执行安全除法。

    参数:
        numerator: 分子。
        denominator: 分母。

    返回:
        除法结果，分母为 0 时返回 0。
    """
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def _round_metric(value: float) -> float:
    """统一聚类指标精度。

    参数:
        value: 原始指标。

    返回:
        保留 6 位小数的指标。
    """
    return round(float(value), 6)


def _as_int(value: object, default: int = 0) -> int:
    """安全解析整数字段。

    参数:
        value: 原始值。
        default: 解析失败时的默认值。

    返回:
        整数值。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        LOGGER.warning("聚类评估整数字段无法解析: %r", value)
        return default


def _as_float(value: object, default: float = 0.0) -> float:
    """安全解析浮点字段。

    参数:
        value: 原始值。
        default: 解析失败时的默认值。

    返回:
        浮点值。
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        LOGGER.warning("聚类评估浮点字段无法解析: %r", value)
        return default


def _as_list(value: object) -> list[str]:
    """把 cluster 成员字段转为字符串列表。

    参数:
        value: 原始成员字段。

    返回:
        文档 ID 列表。
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    if isinstance(value, tuple | set):
        return [_clean(item) for item in value if _clean(item)]
    text = _clean(value)
    if not text:
        return []
    return [item.strip() for item in text.replace(";", ",").split(",") if item.strip()]


def _pair_key(left_id: str, right_id: str) -> tuple[str, str]:
    """构造无向 pair 键。

    参数:
        left_id: 左侧文档 ID。
        right_id: 右侧文档 ID。

    返回:
        字典序排序后的二元组。
    """
    return tuple(sorted((left_id, right_id)))


def _cluster_membership(clusters: list[dict], memberships: list[dict] | None) -> dict[str, set[str]]:
    """构造 cluster 到成员文档的映射。

    参数:
        clusters: 聚类摘要记录。
        memberships: 可选 cluster_membership 记录。

    返回:
        cluster_id 到 document_id 集合的映射。
    """
    grouped: dict[str, set[str]] = defaultdict(set)
    if memberships:
        for row in memberships:
            cluster_id = _clean(row.get("cluster_id"))
            document_id = _clean(row.get("document_id"))
            if cluster_id and document_id:
                grouped[cluster_id].add(document_id)
        return dict(grouped)
    for index, cluster in enumerate(clusters, start=1):
        cluster_id = _clean(cluster.get("cluster_id")) or f"cluster-{index:06d}"
        members = (
            _as_list(cluster.get("member_document_ids"))
            or _as_list(cluster.get("document_ids"))
            or _as_list(cluster.get("representative_document_ids"))
        )
        grouped[cluster_id].update(members)
    return dict(grouped)


def _document_cluster_index(cluster_members: dict[str, set[str]]) -> dict[str, str]:
    """构造文档到预测 cluster 的索引。

    参数:
        cluster_members: cluster 到成员文档集合的映射。

    返回:
        document_id 到 cluster_id 的映射。
    """
    index: dict[str, str] = {}
    for cluster_id, document_ids in cluster_members.items():
        for document_id in document_ids:
            index[document_id] = cluster_id
    return index


def _relation_pairs(relations: list[dict] | None) -> tuple[set[tuple[str, str]], set[tuple[str, str]], set[str]]:
    """从带标签关系中提取正负 pair。

    参数:
        relations: expected_label 标注关系。

    返回:
        positive_pairs、negative_pairs、document_ids 三元组。
    """
    positive_pairs: set[tuple[str, str]] = set()
    negative_pairs: set[tuple[str, str]] = set()
    document_ids: set[str] = set()
    for relation in relations or []:
        source_id = _clean(relation.get("source_document_id"))
        target_id = _clean(relation.get("target_document_id"))
        if not source_id or not target_id or source_id == target_id:
            continue
        document_ids.update({source_id, target_id})
        pair = _pair_key(source_id, target_id)
        if _as_int(relation.get("expected_label")) == 1:
            positive_pairs.add(pair)
        elif "expected_label" in relation:
            negative_pairs.add(pair)
    return positive_pairs, negative_pairs, document_ids


def _is_positive_prediction(value: object) -> bool:
    """判断关系预测字段是否表示自动合并。

    参数:
        value: 预测字段值。

    返回:
        表示正向合并返回 True。
    """
    text = _clean(value).lower()
    if text in {"1", "true", "yes", "safe_merge", "merge", "merged", "positive"}:
        return True
    if text in {"", "0", "false", "no", "reject", "manual_review", "negative"}:
        return False
    try:
        return float(text) > 0.0
    except ValueError:
        LOGGER.warning("聚类预测字段无法解析为合并决策: %r", value)
        return False


def _cluster_members_from_predicted_pairs(document_ids: set[str], predicted_pairs: list[tuple[str, str]]) -> dict[str, set[str]]:
    """从预测合并边诱导 cluster。

    参数:
        document_ids: 参与评估的文档 ID。
        predicted_pairs: 预测为自动合并的 pair。

    返回:
        cluster_id 到 document_id 集合的映射。
    """
    if not document_ids:
        return {}
    parent = {document_id: document_id for document_id in document_ids}

    def find(document_id: str) -> str:
        """查找预测 cluster 并查集根节点。

        参数:
            document_id: 文档 ID。

        返回:
            根节点文档 ID。
        """
        if parent[document_id] != document_id:
            parent[document_id] = find(parent[document_id])
        return parent[document_id]

    def union(left_id: str, right_id: str) -> None:
        """合并两个预测为 same-cluster 的文档。

        参数:
            left_id: 左侧文档 ID。
            right_id: 右侧文档 ID。

        返回:
            无。
        """
        left_root = find(left_id)
        right_root = find(right_id)
        if left_root != right_root:
            parent[right_root] = left_root

    for left_id, right_id in predicted_pairs:
        union(left_id, right_id)
    grouped: dict[str, set[str]] = defaultdict(set)
    for document_id in sorted(parent):
        grouped[find(document_id)].add(document_id)
    return {f"pred-cluster-{index:06d}": members for index, (_, members) in enumerate(sorted(grouped.items()), start=1)}


def _relation_document_ids_and_predicted_pairs(
    relations: list[dict] | None,
    predicate,
) -> tuple[set[str], list[tuple[str, str]]]:
    """按谓词从关系记录提取预测合并边。

    参数:
        relations: 带 source/target 文档 ID 的关系记录。
        predicate: 接收 relation 并返回是否自动合并的函数。

    返回:
        document_ids 与 predicted_pairs 二元组。
    """
    document_ids: set[str] = set()
    predicted_pairs: list[tuple[str, str]] = []
    for relation in relations or []:
        source_id = _clean(relation.get("source_document_id"))
        target_id = _clean(relation.get("target_document_id"))
        if not source_id or not target_id or source_id == target_id:
            continue
        document_ids.update({source_id, target_id})
        if predicate(relation):
            predicted_pairs.append((source_id, target_id))
    return document_ids, predicted_pairs


def _predicted_cluster_members_from_relations(relations: list[dict] | None, prediction_field: str | None) -> dict[str, set[str]]:
    """从关系预测字段诱导预测 cluster。

    参数:
        relations: 带 source/target 文档 ID 的关系记录。
        prediction_field: 表示自动合并的预测字段。

    返回:
        cluster_id 到 document_id 集合的映射。
    """
    if not relations or not prediction_field:
        return {}
    document_ids, predicted_pairs = _relation_document_ids_and_predicted_pairs(
        relations,
        lambda relation: _is_positive_prediction(relation.get(prediction_field)),
    )
    return _cluster_members_from_predicted_pairs(document_ids, predicted_pairs)


def _predicted_cluster_members_from_score_threshold(
    relations: list[dict] | None,
    score_field: str | None,
    score_threshold: float | None,
) -> dict[str, set[str]]:
    """从关系分数字段和阈值诱导 baseline cluster。

    参数:
        relations: 带 source/target 文档 ID 的关系记录。
        score_field: 分数字段名。
        score_threshold: 自动合并阈值。

    返回:
        cluster_id 到 document_id 集合的映射。
    """
    if not relations or not score_field or score_threshold is None:
        return {}
    document_ids, predicted_pairs = _relation_document_ids_and_predicted_pairs(
        relations,
        lambda relation: _as_float(relation.get(score_field), default=float("-inf")) >= float(score_threshold),
    )
    return _cluster_members_from_predicted_pairs(document_ids, predicted_pairs)


def _is_selected_risk_row(row: dict) -> bool:
    """判断 risk protocol 行是否为 selected operating point。

    参数:
        row: risk_calibrated_protocol 记录。

    返回:
        is_selected 为真返回 True。
    """
    return _clean(row.get("is_selected")).lower() in {"1", "true", "yes"}


def _selected_risk_protocol_row(
    risk_protocol_rows: list[dict] | None,
    risk_system: str | None = None,
    fpr_budget: float | None = None,
    fdr_budget: float | None = None,
) -> dict | None:
    """选择一个 risk protocol selected operating point。

    参数:
        risk_protocol_rows: risk_calibrated_protocol 记录。
        risk_system: 可选系统名称。
        fpr_budget: 可选 FPR 预算。
        fdr_budget: 可选 FDR 预算。

    返回:
        selected 行；无可行行时返回 None。
    """
    rows = [row for row in risk_protocol_rows or [] if _is_selected_risk_row(row)]
    if risk_system:
        rows = [row for row in rows if _clean(row.get("system")) == risk_system]
    if fpr_budget is not None:
        rows = [row for row in rows if _as_float(row.get("fpr_budget")) == float(fpr_budget)]
    if fdr_budget is not None:
        rows = [row for row in rows if _as_float(row.get("fdr_budget")) == float(fdr_budget)]
    if not rows:
        return None
    return sorted(
        rows,
        key=lambda row: (
            _as_float(row.get("fpr_budget"), default=1.0),
            _as_float(row.get("fdr_budget"), default=1.0),
            -_as_float(row.get("safe_merge_recall"), default=0.0),
            -_as_float(row.get("safe_merge_coverage"), default=0.0),
        ),
    )[0]


def _predicted_cluster_members_from_risk_protocol(
    relations: list[dict] | None,
    selected_row: dict | None,
    identity_field: str,
    conflict_field: str,
    uncertainty_field: str,
    version_risk_field: str,
) -> dict[str, set[str]]:
    """从 risk protocol selected 阈值诱导 safe_merge cluster。

    参数:
        relations: 带 source/target 文档 ID 的关系记录。
        selected_row: risk_calibrated_protocol selected 行。
        identity_field: 身份分数字段。
        conflict_field: 冲突分数字段。
        uncertainty_field: 不确定性字段。
        version_risk_field: 版本风险字段。

    返回:
        cluster_id 到 document_id 集合的映射。
    """
    if not relations or not selected_row:
        return {}
    document_ids, predicted_pairs = _relation_document_ids_and_predicted_pairs(
        relations,
        lambda relation: assign_selective_decision(
            relation,
            identity_threshold=_as_float(selected_row.get("identity_threshold")),
            conflict_threshold=_as_float(selected_row.get("conflict_threshold")),
            uncertainty_threshold=_as_float(selected_row.get("uncertainty_threshold")),
            version_risk_threshold=_as_float(selected_row.get("version_risk_threshold")),
            identity_field=identity_field,
            conflict_field=conflict_field,
            uncertainty_field=uncertainty_field,
            version_risk_field=version_risk_field,
        )["decision"]
        == "safe_merge",
    )
    return _cluster_members_from_predicted_pairs(document_ids, predicted_pairs)


def _gold_components(document_ids: set[str], positive_pairs: set[tuple[str, str]]) -> dict[str, set[str]]:
    """按 expected_label=1 的连通分量构造 gold cluster。

    参数:
        document_ids: 参与评估的文档 ID。
        positive_pairs: 正例 same_work pair。

    返回:
        document_id 到 gold cluster 成员集合的映射。
    """
    parent = {document_id: document_id for document_id in document_ids}

    def find(document_id: str) -> str:
        """查找 gold cluster 并查集根节点。

        参数:
            document_id: 文档 ID。

        返回:
            根节点文档 ID。
        """
        if parent[document_id] != document_id:
            parent[document_id] = find(parent[document_id])
        return parent[document_id]

    def union(left_id: str, right_id: str) -> None:
        """合并两个文档所属的 gold cluster。

        参数:
            left_id: 左侧文档 ID。
            right_id: 右侧文档 ID。

        返回:
            无。
        """
        left_root = find(left_id)
        right_root = find(right_id)
        if left_root != right_root:
            parent[right_root] = left_root

    for left_id, right_id in positive_pairs:
        for document_id in (left_id, right_id):
            parent.setdefault(document_id, document_id)
        union(left_id, right_id)
    grouped: dict[str, set[str]] = defaultdict(set)
    for document_id in parent:
        grouped[find(document_id)].add(document_id)
    return {document_id: grouped[find(document_id)] for document_id in parent}


def _same_predicted_cluster(left_id: str, right_id: str, document_to_cluster: dict[str, str]) -> bool:
    """判断两个文档是否处于同一预测 cluster。

    参数:
        left_id: 左侧文档 ID。
        right_id: 右侧文档 ID。
        document_to_cluster: 文档到预测 cluster 的索引。

    返回:
        两个文档在同一预测 cluster 中返回 True。
    """
    left_cluster = document_to_cluster.get(left_id)
    right_cluster = document_to_cluster.get(right_id)
    return bool(left_cluster and right_cluster and left_cluster == right_cluster)


def _pairwise_metrics(
    positive_pairs: set[tuple[str, str]],
    negative_pairs: set[tuple[str, str]],
    document_to_cluster: dict[str, str],
) -> dict:
    """计算带标签 pair 口径的 pairwise clustering 指标。

    参数:
        positive_pairs: expected_label=1 的 pair。
        negative_pairs: expected_label=0 的 pair。
        document_to_cluster: 文档到预测 cluster 的索引。

    返回:
        pairwise precision、recall、F1 与混淆计数字典。
    """
    true_positive = sum(1 for left_id, right_id in positive_pairs if _same_predicted_cluster(left_id, right_id, document_to_cluster))
    false_negative = len(positive_pairs) - true_positive
    false_positive = sum(1 for left_id, right_id in negative_pairs if _same_predicted_cluster(left_id, right_id, document_to_cluster))
    precision = _safe_divide(true_positive, true_positive + false_positive)
    recall = _safe_divide(true_positive, true_positive + false_negative)
    f1 = _safe_divide(2 * precision * recall, precision + recall)
    return {
        "pairwise_clustering_true_positive": true_positive,
        "pairwise_clustering_false_positive": false_positive,
        "pairwise_clustering_false_negative": false_negative,
        "pairwise_clustering_precision": _round_metric(precision),
        "pairwise_clustering_recall": _round_metric(recall),
        "pairwise_clustering_f1": _round_metric(f1),
    }


def _b3_metrics(document_ids: set[str], cluster_members: dict[str, set[str]], gold_by_document: dict[str, set[str]], document_to_cluster: dict[str, str]) -> dict:
    """计算 B³ precision、recall 和 F1。

    参数:
        document_ids: 参与评估的文档 ID。
        cluster_members: 预测 cluster 到成员集合的映射。
        gold_by_document: 文档到 gold cluster 成员集合的映射。
        document_to_cluster: 文档到预测 cluster 的索引。

    返回:
        B³ 指标字典。
    """
    if not document_ids:
        return {"b3_precision": 0.0, "b3_recall": 0.0, "b3_f1": 0.0}
    precision_sum = 0.0
    recall_sum = 0.0
    for document_id in document_ids:
        predicted_members = cluster_members.get(document_to_cluster.get(document_id, ""), {document_id}) or {document_id}
        gold_members = gold_by_document.get(document_id, {document_id}) or {document_id}
        overlap_count = len(predicted_members & gold_members)
        precision_sum += _safe_divide(overlap_count, len(predicted_members))
        recall_sum += _safe_divide(overlap_count, len(gold_members))
    precision = precision_sum / len(document_ids)
    recall = recall_sum / len(document_ids)
    f1 = _safe_divide(2 * precision * recall, precision + recall)
    return {"b3_precision": _round_metric(precision), "b3_recall": _round_metric(recall), "b3_f1": _round_metric(f1)}


def _cluster_contamination_metrics(
    cluster_members: dict[str, set[str]],
    negative_pairs: set[tuple[str, str]],
    positive_pairs: set[tuple[str, str]],
    document_to_cluster: dict[str, str],
    cluster_count: int,
) -> dict:
    """计算 over-merge、under-merge 和 cluster contamination 指标。

    参数:
        cluster_members: 预测 cluster 到成员集合的映射。
        negative_pairs: expected_label=0 的 pair。
        positive_pairs: expected_label=1 的 pair。
        document_to_cluster: 文档到预测 cluster 的索引。
        cluster_count: 预测 cluster 数。

    返回:
        contamination 指标字典。
    """
    contaminated_cluster_ids: set[str] = set()
    over_merge_pair_count = 0
    for left_id, right_id in negative_pairs:
        if _same_predicted_cluster(left_id, right_id, document_to_cluster):
            over_merge_pair_count += 1
            contaminated_cluster_ids.add(document_to_cluster[left_id])
    under_merge_pair_count = sum(1 for left_id, right_id in positive_pairs if not _same_predicted_cluster(left_id, right_id, document_to_cluster))
    largest_contaminated_cluster_size = max((len(cluster_members.get(cluster_id, set())) for cluster_id in contaminated_cluster_ids), default=0)
    return {
        "cluster_contamination_rate": _round_metric(_safe_divide(len(contaminated_cluster_ids), cluster_count)),
        "over_merge_cluster_count": len(contaminated_cluster_ids),
        "over_merge_pair_count": over_merge_pair_count,
        "under_merge_pair_count": under_merge_pair_count,
        "largest_contaminated_cluster_size": largest_contaminated_cluster_size,
    }


def _percentile(values: list[float], quantile: float) -> float:
    """计算线性插值百分位数。

    参数:
        values: 数值列表。
        quantile: 分位点，范围为 0 到 1。

    返回:
        百分位数。
    """
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    bounded_quantile = min(1.0, max(0.0, quantile))
    position = bounded_quantile * (len(sorted_values) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = position - lower_index
    return float(sorted_values[lower_index] * (1.0 - fraction) + sorted_values[upper_index] * fraction)


def _summarize_values(values: list[float], confidence_level: float) -> dict[str, float]:
    """汇总 bootstrap 均值和置信区间。

    参数:
        values: bootstrap 指标值列表。
        confidence_level: 置信水平。

    返回:
        mean、ci_low、ci_high 字典。
    """
    if not values:
        return {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    alpha = 1.0 - confidence_level
    return {
        "mean": _round_metric(sum(values) / len(values)),
        "ci_low": _round_metric(_percentile(values, alpha / 2.0)),
        "ci_high": _round_metric(_percentile(values, 1.0 - alpha / 2.0)),
    }


def evaluate_clustering(
    clusters: list[dict],
    relations: list[dict] | None = None,
    memberships: list[dict] | None = None,
    prediction_field: str | None = None,
    score_field: str | None = None,
    score_threshold: float | None = None,
    risk_protocol_rows: list[dict] | None = None,
    risk_system: str | None = None,
    risk_fpr_budget: float | None = None,
    risk_fdr_budget: float | None = None,
    identity_field: str = "identity_score",
    conflict_field: str = "conflict_score",
    uncertainty_field: str = "uncertainty_score",
    version_risk_field: str = "version_risk_score",
) -> dict:
    """生成聚类评估摘要。

    参数:
        clusters: 主题簇列表。
        relations: 可选 expected_label 关系，用于 cluster-level gold 评估。
        memberships: 可选 cluster membership 记录。
        prediction_field: 无 cluster 文件时，从该关系预测字段诱导预测 cluster。
        score_field: 无 cluster 文件时，从该分数字段阈值诱导预测 cluster。
        score_threshold: score_field 自动合并阈值。
        risk_protocol_rows: 可选 risk_calibrated_protocol 记录。
        risk_system: risk protocol 中的系统名称。
        risk_fpr_budget: 可选 FPR 预算。
        risk_fdr_budget: 可选 FDR 预算。
        identity_field: risk protocol 身份分数字段。
        conflict_field: risk protocol 冲突分数字段。
        uncertainty_field: risk protocol 不确定性字段。
        version_risk_field: risk protocol 版本风险字段。

    返回:
        指标字典。
    """
    try:
        sizes = [int(cluster.get("cluster_size", 0) or 0) for cluster in clusters]
        cluster_members = _cluster_membership(clusters, memberships)
        selected_risk_row = None
        prediction_metadata: dict[str, object] = {}
        if not cluster_members:
            if risk_protocol_rows is not None:
                selected_risk_row = _selected_risk_protocol_row(risk_protocol_rows, risk_system, risk_fpr_budget, risk_fdr_budget)
                cluster_members = _predicted_cluster_members_from_risk_protocol(
                    relations,
                    selected_row=selected_risk_row,
                    identity_field=identity_field,
                    conflict_field=conflict_field,
                    uncertainty_field=uncertainty_field,
                    version_risk_field=version_risk_field,
                )
                prediction_metadata = {
                    "cluster_prediction_mode": "risk_calibrated_protocol",
                    "cluster_prediction_status": "ready" if selected_risk_row else "blocked_no_selected_risk_protocol",
                }
                if selected_risk_row:
                    prediction_metadata.update(
                        {
                            "risk_system": _clean(selected_risk_row.get("system")),
                            "risk_fpr_budget": _round_metric(_as_float(selected_risk_row.get("fpr_budget"))),
                            "risk_fdr_budget": _round_metric(_as_float(selected_risk_row.get("fdr_budget"))),
                            "risk_identity_threshold": _round_metric(_as_float(selected_risk_row.get("identity_threshold"))),
                            "risk_conflict_threshold": _round_metric(_as_float(selected_risk_row.get("conflict_threshold"))),
                            "risk_uncertainty_threshold": _round_metric(_as_float(selected_risk_row.get("uncertainty_threshold"))),
                            "risk_version_risk_threshold": _round_metric(_as_float(selected_risk_row.get("version_risk_threshold"))),
                        }
                    )
            elif score_field and score_threshold is not None:
                cluster_members = _predicted_cluster_members_from_score_threshold(relations, score_field, score_threshold)
                prediction_metadata = {
                    "cluster_prediction_mode": "score_threshold",
                    "cluster_score_field": score_field,
                    "cluster_score_threshold": _round_metric(float(score_threshold)),
                }
            else:
                cluster_members = _predicted_cluster_members_from_relations(relations, prediction_field)
                if prediction_field:
                    prediction_metadata = {"cluster_prediction_mode": "prediction_field", "cluster_prediction_field": prediction_field}
        if cluster_members:
            sizes = [len(document_ids) for document_ids in cluster_members.values()]
        cluster_count = len(clusters) if clusters else len(cluster_members)
        metrics = {
            "cluster_count": cluster_count,
            "mean_cluster_size": _round_metric(sum(sizes) / len(sizes)) if sizes else 0.0,
            "max_cluster_size": max(sizes) if sizes else 0,
        }
        metrics.update(prediction_metadata)
        positive_pairs, negative_pairs, relation_document_ids = _relation_pairs(relations)
        document_to_cluster = _document_cluster_index(cluster_members)
        document_ids = set(document_to_cluster) | relation_document_ids
        if not relations:
            return metrics
        gold_by_document = _gold_components(document_ids, positive_pairs)
        metrics.update(
            {
                "gold_relation_pair_count": len(positive_pairs) + len(negative_pairs),
                "gold_positive_pair_count": len(positive_pairs),
                "gold_negative_pair_count": len(negative_pairs),
            }
        )
        metrics.update(_pairwise_metrics(positive_pairs, negative_pairs, document_to_cluster))
        metrics.update(_b3_metrics(document_ids, cluster_members, gold_by_document, document_to_cluster))
        metrics.update(_cluster_contamination_metrics(cluster_members, negative_pairs, positive_pairs, document_to_cluster, cluster_count))
        return metrics
    except Exception:
        LOGGER.exception("聚类评估失败")
        raise


def run_cluster_contamination_bootstrap(
    relations: list[dict],
    system_name: str,
    iterations: int = 1000,
    seed: int = 42,
    confidence_level: float = 0.95,
    prediction_field: str | None = None,
    score_field: str | None = None,
    score_threshold: float | None = None,
    risk_protocol_rows: list[dict] | None = None,
    risk_system: str | None = None,
    risk_fpr_budget: float | None = None,
    risk_fdr_budget: float | None = None,
    identity_field: str = "identity_score",
    conflict_field: str = "conflict_score",
    uncertainty_field: str = "uncertainty_score",
    version_risk_field: str = "version_risk_score",
) -> list[dict]:
    """运行 cluster contamination bootstrap 置信区间。

    参数:
        relations: 带标签关系记录。
        system_name: 系统名称。
        iterations: bootstrap 抽样次数。
        seed: 随机种子。
        confidence_level: 置信水平。
        prediction_field: 二值预测字段。
        score_field: baseline 分数字段。
        score_threshold: baseline 自动合并阈值。
        risk_protocol_rows: risk_calibrated_protocol 记录。
        risk_system: risk protocol 系统名称。
        risk_fpr_budget: 可选 FPR 预算。
        risk_fdr_budget: 可选 FDR 预算。
        identity_field: risk protocol 身份分数字段。
        conflict_field: risk protocol 冲突分数字段。
        uncertainty_field: risk protocol 不确定性字段。
        version_risk_field: risk protocol 版本风险字段。

    返回:
        单行 cluster contamination bootstrap 摘要。
    """
    try:
        if iterations < 1:
            raise ValueError("iterations 必须大于等于 1")
        if not 0.0 < confidence_level < 1.0:
            raise ValueError("confidence_level 必须在 0 到 1 之间")
        sample_count = len(relations)
        rng = random.Random(seed)
        metric_samples: dict[str, list[float]] = {field: [] for field in CLUSTER_BOOTSTRAP_METRIC_FIELDS}
        base_metrics = evaluate_clustering(
            [],
            relations=relations,
            prediction_field=prediction_field,
            score_field=score_field,
            score_threshold=score_threshold,
            risk_protocol_rows=risk_protocol_rows,
            risk_system=risk_system,
            risk_fpr_budget=risk_fpr_budget,
            risk_fdr_budget=risk_fdr_budget,
            identity_field=identity_field,
            conflict_field=conflict_field,
            uncertainty_field=uncertainty_field,
            version_risk_field=version_risk_field,
        )
        for _ in range(iterations):
            sampled_relations = [relations[rng.randrange(sample_count)] for _ in range(sample_count)] if sample_count else []
            sampled_metrics = evaluate_clustering(
                [],
                relations=sampled_relations,
                prediction_field=prediction_field,
                score_field=score_field,
                score_threshold=score_threshold,
                risk_protocol_rows=risk_protocol_rows,
                risk_system=risk_system,
                risk_fpr_budget=risk_fpr_budget,
                risk_fdr_budget=risk_fdr_budget,
                identity_field=identity_field,
                conflict_field=conflict_field,
                uncertainty_field=uncertainty_field,
                version_risk_field=version_risk_field,
            )
            for field in CLUSTER_BOOTSTRAP_METRIC_FIELDS:
                metric_samples[field].append(_as_float(sampled_metrics.get(field), default=0.0))
        row: dict[str, object] = {
            "system": system_name,
            "metric_scope": "cluster_contamination",
            "cluster_prediction_mode": base_metrics.get("cluster_prediction_mode", ""),
            "pair_count": sample_count,
            "bootstrap_iterations": iterations,
            "confidence_level": confidence_level,
            "cluster_score_field": score_field or "",
            "cluster_score_threshold": "" if score_threshold is None else _round_metric(score_threshold),
            "risk_system": base_metrics.get("risk_system", risk_system or ""),
            "risk_fpr_budget": base_metrics.get("risk_fpr_budget", "" if risk_fpr_budget is None else _round_metric(risk_fpr_budget)),
            "risk_fdr_budget": base_metrics.get("risk_fdr_budget", "" if risk_fdr_budget is None else _round_metric(risk_fdr_budget)),
            "risk_identity_threshold": base_metrics.get("risk_identity_threshold", ""),
            "risk_conflict_threshold": base_metrics.get("risk_conflict_threshold", ""),
        }
        for field in CLUSTER_BOOTSTRAP_METRIC_FIELDS:
            row[f"{field}_point"] = base_metrics.get(field, 0.0)
            summary = _summarize_values(metric_samples[field], confidence_level)
            row[f"{field}_mean"] = summary["mean"]
            row[f"{field}_ci_low"] = summary["ci_low"]
            row[f"{field}_ci_high"] = summary["ci_high"]
        return [row]
    except Exception:
        LOGGER.exception("cluster contamination bootstrap 失败")
        raise


def write_cluster_bootstrap_csv(rows: list[dict], output_path: str | Path) -> None:
    """写出 cluster contamination bootstrap CSV。

    参数:
        rows: bootstrap 摘要记录。
        output_path: 输出 CSV 路径。

    返回:
        无。
    """
    fields = list(CLUSTER_BOOTSTRAP_CSV_FIELDS)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    path = Path(output_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in fields})
    except OSError:
        LOGGER.exception("写出 cluster contamination bootstrap CSV 失败: %s", output_path)
        raise
