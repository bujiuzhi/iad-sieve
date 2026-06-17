"""测试 IAD-Bench-Open-v3 held-out split 计划。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_open_v3_heldout_split_plan
from iad_sieve.evaluation.open_v3_heldout_split_plan import (
    build_open_v3_heldout_split_plan_rows,
    build_open_v3_heldout_split_plan_rows_from_paths,
    write_open_v3_heldout_split_plan_outputs,
)
from iad_sieve.utils.io_utils import read_records


def _write_jsonl(path, records: list[dict]) -> None:
    """写入 JSONL 测试文件。

    参数:
        path: 输出路径。
        records: 记录列表。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def _pair(pair_id: str, relation: str, source: str, topic: str = "") -> dict:
    """构造测试 pair。

    参数:
        pair_id: pair ID。
        relation: relation_label。
        source: label_source。
        topic: topic ID。

    返回:
        pair 记录。
    """
    return {
        "pair_id": pair_id,
        "source_document_id": f"{pair_id}:a",
        "target_document_id": f"{pair_id}:b",
        "relation_label": relation,
        "label_source": source,
        "label_strength": "silver" if source == "openalex" else "gold",
        "label_provenance": {"primary_topic": topic} if topic else {},
        "split": "train",
    }


def test_build_open_v3_heldout_split_plan_rows_generates_assignments_when_ready() -> None:
    """验证来源和 topic 条件满足时生成 held-out split assignment。"""
    pairs = [
        _pair("p1", "same_work", "deepmatcher"),
        _pair("p2", "same_work", "dirty_dblp"),
        _pair("p3", "unrelated", "deepmatcher"),
        _pair("p4", "unrelated", "dirty_dblp"),
        _pair("p5", "agenda_non_identity", "openalex", "T1"),
        _pair("p6", "agenda_non_identity", "scirepeval", "T2"),
        _pair("p7", "agenda_non_identity", "openalex", "T3"),
    ]

    plan_rows, assignment_rows = build_open_v3_heldout_split_plan_rows(
        pairs=pairs,
        min_sources_per_relation=2,
        min_topics_for_topic_holdout=3,
        topic_test_ratio=0.34,
    )
    by_id = {row["plan_id"]: row for row in plan_rows}
    heldout_values = by_id["source_held_out_split"]["heldout_sources"].values()
    unique_heldout_sources = {source for sources in heldout_values for source in sources}

    assert by_id["source_held_out_split"]["status"] == "ready"
    assert by_id["source_held_out_split"]["heldout_source_count"] == len(unique_heldout_sources)
    assert by_id["topic_held_out_split"]["status"] == "ready"
    assert by_id["pair_leakage_guard"]["status"] == "defensible"
    assert any(row["split_strategy"] == "source_held_out" and row["split"] == "test" for row in assignment_rows)
    assert any(row["split_strategy"] == "topic_held_out" and row["split"] == "test" for row in assignment_rows)


def test_build_open_v3_heldout_split_plan_rows_blocks_when_current_v2_like_data_is_insufficient() -> None:
    """验证单来源和单 topic 数据会阻塞 held-out split 计划。"""
    pairs = [
        _pair("g1", "same_work", "deepmatcher"),
        _pair("g2", "unrelated", "deepmatcher"),
        _pair("s1", "agenda_non_identity", "openalex", "T10009"),
    ]

    plan_rows, assignment_rows = build_open_v3_heldout_split_plan_rows(
        pairs=pairs,
        min_sources_per_relation=2,
        min_topics_for_topic_holdout=30,
    )
    by_id = {row["plan_id"]: row for row in plan_rows}

    assert by_id["source_held_out_split"]["status"] == "blocked"
    assert by_id["topic_held_out_split"]["status"] == "blocked"
    assert assignment_rows == []


def test_build_open_v3_heldout_split_plan_rows_marks_single_unique_heldout_source_limited() -> None:
    """验证单一 held-out 来源只能支撑有限跨来源复核。"""
    pairs = [
        _pair("p1", "same_work", "deepmatcher_amazon_google"),
        _pair("p2", "same_work", "deepmatcher_dblp_scholar"),
        _pair("p3", "unrelated", "deepmatcher_amazon_google"),
        _pair("p4", "unrelated", "deepmatcher_dblp_scholar"),
    ]

    plan_rows, _ = build_open_v3_heldout_split_plan_rows(
        pairs=pairs,
        min_sources_per_relation=2,
        min_topics_for_topic_holdout=3,
    )
    by_id = {row["plan_id"]: row for row in plan_rows}

    assert by_id["source_held_out_split"]["status"] == "ready"
    assert by_id["heldout_source_diversity"]["status"] == "conditional"
    assert by_id["heldout_source_diversity"]["reviewer_risk_level"] == "medium"
    assert by_id["heldout_source_diversity"]["heldout_source_count"] == 1


def test_build_open_v3_heldout_split_plan_rows_prefers_multi_source_holdouts_when_train_source_remains() -> None:
    """验证来源充足时优先选择多个 held-out 来源且每类 relation 保留训练来源。"""
    pairs = [
        _pair("sw1", "same_work", "deepmatcher_py_entitymatching_dblp_acm"),
        _pair("sw2", "same_work", "deepmatcher_amazon_google"),
        _pair("sw3", "same_work", "deepmatcher_amazon_google"),
        _pair("sw4", "same_work", "deepmatcher_dblp_scholar"),
        _pair("sw5", "same_work", "deepmatcher_dblp_scholar"),
        _pair("sw6", "same_work", "deepmatcher_dblp_scholar"),
        _pair("ur1", "unrelated", "deepmatcher_py_entitymatching_dblp_acm"),
        _pair("ur2", "unrelated", "deepmatcher_amazon_google"),
        _pair("ur3", "unrelated", "deepmatcher_amazon_google"),
        _pair("ur4", "unrelated", "deepmatcher_dblp_scholar"),
        _pair("ur5", "unrelated", "deepmatcher_dblp_scholar"),
        _pair("ur6", "unrelated", "deepmatcher_dblp_scholar"),
    ]

    plan_rows, assignment_rows = build_open_v3_heldout_split_plan_rows(
        pairs=pairs,
        min_sources_per_relation=2,
        min_topics_for_topic_holdout=3,
    )
    by_id = {row["plan_id"]: row for row in plan_rows}
    source_assignments = [row for row in assignment_rows if row["split_strategy"] == "source_held_out"]
    train_relations = {row["relation_label"] for row in source_assignments if row["split"] == "train"}
    test_sources = {row["label_source"] for row in source_assignments if row["split"] == "test"}
    train_heldout_keys = {row["heldout_key"] for row in source_assignments if row["split"] == "train"}

    assert by_id["source_held_out_split"]["status"] == "ready"
    assert by_id["heldout_source_diversity"]["status"] == "defensible"
    assert by_id["heldout_source_diversity"]["heldout_source_count"] == 2
    assert train_relations == {"same_work", "unrelated"}
    assert test_sources == {"deepmatcher_amazon_google", "deepmatcher_py_entitymatching_dblp_acm"}
    assert train_heldout_keys == {""}


def test_build_open_v3_heldout_split_plan_rows_from_paths_reads_pairs(tmp_path) -> None:
    """验证 held-out split 计划可从 pair 文件读取输入。"""
    pairs_path = tmp_path / "pairs.jsonl"
    _write_jsonl(pairs_path, [_pair("p1", "same_work", "deepmatcher")])

    plan_rows, _ = build_open_v3_heldout_split_plan_rows_from_paths(pairs_path=pairs_path)

    assert any(row["plan_id"] == "source_held_out_split" for row in plan_rows)


def test_write_open_v3_heldout_split_plan_outputs_writes_outputs(tmp_path) -> None:
    """验证 held-out split 计划写出计划、assignment、CSV、Markdown 和 summary。"""
    plan_rows = [
        {
            "plan_id": "source_held_out_split",
            "status": "blocked",
            "reviewer_risk_level": "high",
            "reviewer_value": "source-held-out 不足。",
            "next_optimization": "补充来源。",
        }
    ]
    assignment_rows = [{"pair_id": "p1", "split_strategy": "source_held_out", "split": "test"}]
    output_dir = tmp_path / "heldout_split_plan"

    write_open_v3_heldout_split_plan_outputs(plan_rows, assignment_rows, output_dir)

    assert read_records(output_dir / "open_v3_heldout_split_plan.jsonl")[0]["plan_id"] == "source_held_out_split"
    assert read_records(output_dir / "open_v3_heldout_split_assignments.jsonl")[0]["pair_id"] == "p1"
    assert (output_dir / "open_v3_heldout_split_plan.csv").exists()
    assert "# IAD-Bench-Open-v3 Held-out Split Plan" in (output_dir / "open_v3_heldout_split_plan.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "open_v3_heldout_split_plan_summary.jsonl")[0]
    assert summary["plan_count"] == 1
    assert summary["assignment_count"] == 1


def test_write_open_v3_heldout_split_plan_outputs_keeps_assignment_csv_header_when_empty(tmp_path) -> None:
    """验证 assignment 为空时 CSV 仍保留字段表头。"""
    plan_rows = [
        {
            "plan_id": "topic_held_out_split",
            "status": "blocked",
            "reviewer_risk_level": "high",
            "reviewer_value": "topic 不足。",
            "next_optimization": "补充 topic。",
        }
    ]
    output_dir = tmp_path / "heldout_split_plan"

    write_open_v3_heldout_split_plan_outputs(plan_rows, [], output_dir)

    assignment_csv = (output_dir / "open_v3_heldout_split_assignments.csv").read_text(encoding="utf-8")
    assert assignment_csv.startswith("assignment_id,split_strategy,pair_id")


def test_build_open_v3_heldout_split_plan_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出 held-out split 计划。"""
    pairs_path = tmp_path / "pairs.jsonl"
    output_dir = tmp_path / "heldout_split_plan"
    _write_jsonl(pairs_path, [_pair("p1", "same_work", "deepmatcher")])

    command_build_open_v3_heldout_split_plan(
        Namespace(
            pairs=str(pairs_path),
            output_dir=str(output_dir),
            min_sources_per_relation=2,
            min_topics_for_topic_holdout=30,
            topic_test_ratio=0.2,
        )
    )

    assert (output_dir / "open_v3_heldout_split_plan.jsonl").exists()
    assert (output_dir / "open_v3_heldout_split_plan_summary.jsonl").exists()


def test_cli_includes_build_open_v3_heldout_split_plan_command() -> None:
    """验证 CLI 暴露 build-open-v3-heldout-split-plan 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-open-v3-heldout-split-plan",
            "--pairs",
            "outputs/iad_bench_open_v2/iad_bench_pairs.jsonl",
            "--output-dir",
            "outputs/open_v3_heldout_split_plan_fixture",
        ]
    )

    assert args.command == "build-open-v3-heldout-split-plan"
    assert args.min_sources_per_relation == 2
    assert args.min_topics_for_topic_holdout == 30
