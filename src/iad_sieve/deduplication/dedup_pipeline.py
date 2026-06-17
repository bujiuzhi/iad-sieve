"""受约束重复合并流水线。"""

from __future__ import annotations

import logging

from iad_sieve.deduplication.canonical_selector import select_canonical_document
from iad_sieve.deduplication.cannot_link_graph import build_cannot_link_graph
from iad_sieve.deduplication.constrained_union_find import ConstrainedUnionFind
from iad_sieve.deduplication.group_consistency import calculate_group_consistency


LOGGER = logging.getLogger(__name__)


def merge_duplicates(
    documents: list[dict],
    relations: list[dict],
    false_merge_risk_threshold: float = 0.50,
) -> tuple[list[dict], list[dict]]:
    """合并重复组并生成规范文献。

    参数:
        documents: 标准化文献列表。
        relations: pair_relations 记录列表。
        false_merge_risk_threshold: 自动合并允许的最高误合并风险。

    返回:
        duplicate_groups 与 canonical_documents 二元组。
    """
    document_lookup = {document["document_id"]: document for document in documents}
    cannot_link_graph = build_cannot_link_graph(relations)
    union_find = ConstrainedUnionFind(list(document_lookup), cannot_link_graph)
    relation_conflicts: dict[frozenset[str], float] = {}
    relation_risks: dict[frozenset[str], float] = {}
    for relation in relations:
        source_id = relation["source_document_id"]
        target_id = relation["target_document_id"]
        relation_key = frozenset((source_id, target_id))
        relation_conflicts[relation_key] = float(relation.get("conflict_score", 0.0) or 0.0)
        relation_risks[relation_key] = float(relation.get("false_merge_risk", 0.0) or 0.0)
        relation_type = relation.get("relation_type")
        if relation_type == "exact_duplicate":
            union_find.try_union(source_id, target_id, 1.0)
        elif relation_type == "high_confidence_duplicate":
            false_merge_risk = float(relation.get("false_merge_risk", 0.0) or 0.0)
            if false_merge_risk <= false_merge_risk_threshold:
                union_find.try_union(source_id, target_id, float(relation.get("identity_score", relation.get("duplicate_score", 0.0)) or 0.0))
    duplicate_groups: list[dict] = []
    canonical_documents: list[dict] = []
    for index, members in enumerate(sorted(union_find.groups(), key=lambda group: sorted(group)[0]), start=1):
        member_documents = [document_lookup[document_id] for document_id in sorted(members)]
        max_conflict = 0.0
        max_false_merge_risk = 0.0
        for left_index, left_document in enumerate(member_documents):
            for right_document in member_documents[left_index + 1 :]:
                relation_key = frozenset((left_document["document_id"], right_document["document_id"]))
                max_conflict = max(max_conflict, relation_conflicts.get(relation_key, 0.0))
                max_false_merge_risk = max(max_false_merge_risk, relation_risks.get(relation_key, 0.0))
        group_consistency = calculate_group_consistency(member_documents, max_conflict_score=max_conflict)
        canonical = select_canonical_document(member_documents)
        group_id = f"dup-{index:06d}"
        canonical_record = {
            **canonical,
            "canonical_document_id": canonical["document_id"],
            "source_document_ids": sorted(members),
            "duplicate_group_id": group_id,
            "canonical_vector_id": canonical["document_id"],
        }
        duplicate_groups.append(
            {
                "duplicate_group_id": group_id,
                "canonical_document_id": canonical["document_id"],
                "member_document_ids": sorted(members),
                "group_size": len(members),
                "group_consistency": group_consistency,
                "max_conflict_score": max_conflict,
                "max_false_merge_risk": max_false_merge_risk,
                "merge_reason": "identity_agenda_risk_constrained_union",
                "confidence": group_consistency,
            }
        )
        canonical_documents.append(canonical_record)
    return duplicate_groups, canonical_documents
