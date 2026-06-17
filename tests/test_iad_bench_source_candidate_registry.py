"""测试 IAD-Bench 公开来源候选 registry。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_build_iad_bench_source_candidate_registry
from iad_sieve.evaluation.iad_bench_source_candidate_registry import (
    build_iad_bench_source_candidate_registry_rows,
    build_iad_bench_source_candidate_registry_rows_from_paths,
    write_iad_bench_source_candidate_registry_outputs,
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


def _balance_row(relation_label: str, source_family: str, minimum_balance_pair_count: int = 0) -> dict:
    """构造 provenance balance 测试记录。

    参数:
        relation_label: relation 标签。
        source_family: 推荐来源家族。
        minimum_balance_pair_count: 降低主来源占比需要补充的 pair 数。

    返回:
        provenance balance 记录。
    """
    return {
        "relation_label": relation_label,
        "audit_status": "blocked",
        "current_source_count": 1,
        "missing_source_count": 1,
        "dominant_source": "openalex" if relation_label == "agenda_non_identity" else "deepmatcher",
        "minimum_balance_pair_count": minimum_balance_pair_count,
        "target_pairs_per_new_source": 500,
        "recommended_source_family": source_family,
    }


def test_build_iad_bench_source_candidate_registry_rows_maps_blocked_relations_to_adapters() -> None:
    """验证 blocked relation 会被转换为可执行公开来源候选。"""
    rows = build_iad_bench_source_candidate_registry_rows(
        provenance_balance_rows=[
            _balance_row("same_work", "public_entity_matching_gold"),
            _balance_row("agenda_non_identity", "multi_topic_openalex_hard_negative", minimum_balance_pair_count=2500),
        ],
        public_gold_source_ids=["deepmatcher_dblp_scholar"],
        openalex_topic_seed_ids=["T200001"],
    )

    by_candidate = {row["candidate_id"]: row for row in rows}

    same_work = by_candidate["same_work_deepmatcher_dblp_scholar"]
    assert same_work["existing_adapter"] == "prepare-deepmatcher"
    assert same_work["adapter_format"] == "deepmatcher_like_csv"
    assert same_work["target_pair_count"] == 500
    assert "prepare-deepmatcher" in same_work["command_template"]
    assert "DBLP-Scholar" in same_work["source_name"]

    agenda = by_candidate["agenda_non_identity_opencitations_coci_T200001"]
    assert agenda["existing_adapter"] == "prepare-openalex-weak-labels"
    assert agenda["adapter_format"] == "openalex_works_plus_opencitations_coci_csv"
    assert agenda["target_pair_count"] == 2500
    assert "--citations data/raw/opencitations/coci_T200001.csv" in agenda["weak_label_command"]
    assert "openalex_opencitations" in agenda["planned_label_source"]


def test_build_iad_bench_source_candidate_registry_rows_from_paths_reads_plan(tmp_path) -> None:
    """验证 registry 可从 provenance balance plan 文件读取输入。"""
    plan_path = tmp_path / "balance.jsonl"
    _write_jsonl(plan_path, [_balance_row("unrelated", "public_entity_matching_gold")])

    rows = build_iad_bench_source_candidate_registry_rows_from_paths(
        provenance_balance_plan_path=plan_path,
        public_gold_source_ids=["deepmatcher_dblp_scholar"],
    )

    assert rows[0]["relation_label"] == "unrelated"
    assert rows[0]["candidate_id"] == "unrelated_deepmatcher_dblp_scholar"


def test_write_iad_bench_source_candidate_registry_outputs_writes_files(tmp_path) -> None:
    """验证 registry 写出 JSONL、CSV、Markdown 和 summary。"""
    output_dir = tmp_path / "registry"
    rows = build_iad_bench_source_candidate_registry_rows(
        provenance_balance_rows=[_balance_row("same_work", "public_entity_matching_gold")],
        public_gold_source_ids=["deepmatcher_dblp_scholar"],
    )

    write_iad_bench_source_candidate_registry_outputs(rows, output_dir)

    assert read_records(output_dir / "iad_bench_source_candidate_registry.jsonl")[0]["candidate_id"] == "same_work_deepmatcher_dblp_scholar"
    assert (output_dir / "iad_bench_source_candidate_registry.csv").exists()
    assert "# IAD-Bench Source Candidate Registry" in (output_dir / "iad_bench_source_candidate_registry.md").read_text(encoding="utf-8")
    summary = read_records(output_dir / "iad_bench_source_candidate_registry_summary.jsonl")[0]
    assert summary["candidate_count"] == 1
    assert summary["ready_with_existing_adapter_count"] == 1
    assert summary["overall_registry_status"] == "planned"


def test_build_iad_bench_source_candidate_registry_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 写出公开来源候选 registry。"""
    plan_path = tmp_path / "balance.jsonl"
    output_dir = tmp_path / "registry"
    _write_jsonl(plan_path, [_balance_row("same_work", "public_entity_matching_gold")])

    command_build_iad_bench_source_candidate_registry(
        Namespace(
            provenance_balance_plan=str(plan_path),
            output_dir=str(output_dir),
            public_gold_source_ids=["deepmatcher_dblp_scholar"],
            openalex_topic_seed_ids=["T200001"],
        )
    )

    assert (output_dir / "iad_bench_source_candidate_registry.jsonl").exists()
    assert (output_dir / "iad_bench_source_candidate_registry_summary.jsonl").exists()


def test_cli_includes_build_iad_bench_source_candidate_registry_command() -> None:
    """验证 CLI 暴露 build-iad-bench-source-candidate-registry 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "build-iad-bench-source-candidate-registry",
            "--provenance-balance-plan",
            "outputs/iad_bench_provenance_balance_plan_fixture/iad_bench_provenance_balance_plan.jsonl",
            "--output-dir",
            "outputs/iad_bench_source_candidate_registry_fixture",
            "--public-gold-source-ids",
            "deepmatcher_dblp_scholar",
            "--openalex-topic-seed-ids",
            "T200001",
        ]
    )

    assert args.command == "build-iad-bench-source-candidate-registry"
    assert args.public_gold_source_ids == ["deepmatcher_dblp_scholar"]
    assert args.openalex_topic_seed_ids == ["T200001"]
