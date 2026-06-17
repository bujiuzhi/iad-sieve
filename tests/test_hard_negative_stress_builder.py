"""测试 hard-negative stress set 构造器。"""

from __future__ import annotations

import csv
import json

from iad_sieve.cli import build_parser, command_build_hard_negative_stress_set
from iad_sieve.evaluation.hard_negative_stress_builder import (
    build_hard_negative_stress_set,
    write_hard_negative_stress_outputs,
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


def test_build_hard_negative_stress_set_separates_confident_negative_and_version_risk() -> None:
    """验证构造器区分高置信非同文和版本边界样本。"""
    rows = build_hard_negative_stress_set(
        [
            {
                "pair_id": "p1",
                "source_document_id": "a",
                "target_document_id": "b",
                "expected_label": 0,
                "expected_agenda_label": 1,
                "title_similarity": 0.94,
                "transformer_cosine": 0.88,
                "different_identifier": 1,
                "author_overlap": 0.10,
                "venue_conflict": 1,
                "year_conflict": 1,
                "claim_difference_score": 0.80,
            },
            {
                "pair_id": "p2",
                "source_document_id": "c",
                "target_document_id": "d",
                "expected_label": 0,
                "expected_agenda_label": 1,
                "title_similarity": 0.91,
                "transformer_cosine": 0.86,
                "different_identifier": 1,
                "author_overlap": 0.92,
                "version_risk_score": 0.95,
                "label_reason": "preprint_to_journal_version_candidate",
            },
        ]
    )

    by_pair = {row["pair_id"]: row for row in rows}

    assert by_pair["p1"]["stress_level"] == "high_confidence_non_identity"
    assert by_pair["p1"]["stress_type"] == "similar_title_identifier_conflict"
    assert by_pair["p1"]["usable_as_primary_negative"] is True
    assert by_pair["p2"]["stress_level"] == "version_risk_ambiguous"
    assert by_pair["p2"]["stress_type"] == "version_risk_ambiguous"
    assert by_pair["p2"]["usable_as_primary_negative"] is False


def test_build_hard_negative_stress_set_labels_citation_author_and_template_traps() -> None:
    """验证 citation、作者重叠和标题模板陷阱被分类。"""
    rows = build_hard_negative_stress_set(
        [
            {
                "pair_id": "citation",
                "expected_label": 0,
                "expected_agenda_label": 1,
                "title_similarity": 0.82,
                "embedding_similarity": 0.83,
                "different_identifier": 1,
                "shared_reference_count": 7,
                "author_overlap": 0.20,
            },
            {
                "pair_id": "one_cites",
                "expected_label": 0,
                "title_similarity": 0.85,
                "embedding_similarity": 0.84,
                "different_identifier": 1,
                "source_cites_target": True,
                "author_overlap": 0.10,
            },
            {
                "pair_id": "author",
                "expected_label": 0,
                "title_similarity": 0.88,
                "embedding_similarity": 0.82,
                "different_identifier": 1,
                "author_overlap": 0.76,
                "claim_difference_score": 0.70,
                "venue_conflict": 1,
            },
            {
                "pair_id": "template",
                "expected_label": 0,
                "title_similarity": 0.86,
                "embedding_similarity": 0.81,
                "different_identifier": 1,
                "author_overlap": 0.15,
                "title": "A Survey of Neural Retrieval",
                "target_title": "A Survey of Neural Ranking",
            },
        ]
    )
    by_pair = {row["pair_id"]: row for row in rows}

    assert by_pair["citation"]["stress_type"] == "citation_neighbor"
    assert by_pair["one_cites"]["stress_type"] == "one_cites_the_other"
    assert by_pair["author"]["stress_type"] == "author_overlap_trap"
    assert by_pair["template"]["stress_type"] == "title_template_trap"
    assert all(row["stress_level"] == "high_confidence_non_identity" for row in rows)


def test_build_hard_negative_stress_set_keeps_weak_pseudo_negative_separate() -> None:
    """验证证据不足的同议题负例只进入弱伪负例层。"""
    rows = build_hard_negative_stress_set(
        [
            {
                "pair_id": "weak",
                "expected_label": 0,
                "expected_agenda_label": 1,
                "title_similarity": 0.55,
                "embedding_similarity": 0.58,
                "different_identifier": 1,
                "shared_reference_count": 1,
            }
        ]
    )

    assert rows[0]["stress_level"] == "weak_pseudo_negative"
    assert rows[0]["usable_as_primary_negative"] is False
    assert "insufficient_similarity_or_conflict_evidence" in rows[0]["stress_rationale"]


def test_build_hard_negative_stress_set_excludes_plain_unrelated_gold_negatives() -> None:
    """验证普通 unrelated gold negative 不进入 agenda-level stress set。"""
    rows = build_hard_negative_stress_set(
        [
            {
                "pair_id": "plain_unrelated",
                "expected_label": 0,
                "expected_agenda_label": 0,
                "relation_label": "unrelated",
                "title_similarity": 1.0,
                "full_similarity": 1.0,
                "author_overlap": 0.0,
                "label_strength": "gold",
            }
        ]
    )

    assert rows == []


def test_build_hard_negative_stress_set_uses_nested_label_provenance_conflict() -> None:
    """验证 OpenAlex/IAD-Bench 嵌套 provenance 可提供标识符冲突和共享引用证据。"""
    rows = build_hard_negative_stress_set(
        [
            {
                "pair_id": "openalex",
                "expected_label": 0,
                "expected_agenda_label": 1,
                "relation_label": "agenda_non_identity",
                "label_type": "openalex_agenda_non_identity_weak",
                "title_similarity": 0.87,
                "full_similarity": 0.91,
                "author_overlap": 0.10,
                "label_provenance": {
                    "same_doi": False,
                    "same_openalex_work_id": False,
                    "shared_reference_count": 5,
                    "candidate_sources": ["openalex_topic", "opencitations_shared_citation"],
                },
            }
        ]
    )

    assert rows[0]["identifier_conflict"] is True
    assert rows[0]["shared_reference_count"] == 5
    assert rows[0]["stress_level"] == "high_confidence_non_identity"
    assert rows[0]["stress_type"] == "citation_neighbor"


def test_write_hard_negative_stress_outputs_writes_reports(tmp_path) -> None:
    """验证 hard-negative stress set 写出 JSONL、CSV、summary 和 Markdown。"""
    rows = build_hard_negative_stress_set(
        [
            {
                "pair_id": "p1",
                "expected_label": 0,
                "title_similarity": 0.94,
                "embedding_similarity": 0.88,
                "different_identifier": 1,
                "author_overlap": 0.10,
                "venue_conflict": 1,
            }
        ]
    )
    output_dir = tmp_path / "hard_negative_stress"

    write_hard_negative_stress_outputs(rows, output_dir)

    assert read_records(output_dir / "hard_negative_stress_pairs.jsonl")[0]["stress_level"] == "high_confidence_non_identity"
    assert read_records(output_dir / "hard_negative_stress_summary.jsonl")[0]["high_confidence_non_identity_count"] == 1
    with (output_dir / "hard_negative_stress_pairs.csv").open("r", encoding="utf-8", newline="") as file:
        csv_rows = list(csv.DictReader(file))
    assert csv_rows[0]["stress_type"] == "similar_title_identifier_conflict"
    assert "# Hard-Negative Stress Set" in (output_dir / "hard_negative_stress_report.md").read_text(encoding="utf-8")


def test_build_hard_negative_stress_set_cli_writes_outputs(tmp_path) -> None:
    """验证 CLI 构造 hard-negative stress set。"""
    relations_path = tmp_path / "relations.jsonl"
    output_dir = tmp_path / "hard_negative_stress"
    _write_jsonl(
        relations_path,
        [
            {
                "pair_id": "p1",
                "expected_label": 0,
                "title_similarity": 0.94,
                "embedding_similarity": 0.88,
                "different_identifier": 1,
                "author_overlap": 0.10,
                "venue_conflict": 1,
            }
        ],
    )

    command_build_hard_negative_stress_set(
        type(
            "Args",
            (),
            {
                "relations": [str(relations_path)],
                "output_dir": str(output_dir),
                "limit": None,
                "min_title_similarity": 0.80,
                "min_embedding_similarity": 0.75,
                "min_shared_references": 2,
            },
        )()
    )

    assert (output_dir / "hard_negative_stress_summary.jsonl").exists()
    parser = build_parser()
    args = parser.parse_args(
        [
            "build-hard-negative-stress-set",
            "--relations",
            str(relations_path),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert args.command == "build-hard-negative-stress-set"
