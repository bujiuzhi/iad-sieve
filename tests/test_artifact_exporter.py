"""论文产物导出测试。"""

from __future__ import annotations

from pathlib import Path

from iad_sieve.evaluation.artifact_exporter import export_paper_artifacts
from iad_sieve.utils.io_utils import write_records


def test_export_paper_artifacts_writes_tables_and_figures(tmp_path: Path) -> None:
    """验证导出器生成表格和 PNG 图。

    参数:
        tmp_path: pytest 临时目录。

    返回:
        无。
    """
    input_dir = tmp_path / "run"
    output_dir = tmp_path / "paper"
    write_records(
        [
            {
                "source_document_id": "arxiv:a",
                "target_document_id": "arxiv:b",
                "relation_type": "same_topic_non_duplicate",
                "topic_score": 0.9,
                "duplicate_score": 0.4,
                "full_similarity": 0.91,
            }
        ],
        input_dir / "pair_relations.jsonl",
    )
    write_records([{"cluster_id": "cluster-1", "cluster_size": 3}], input_dir / "clusters.jsonl")
    write_records([{"role": "representative", "duplicate_group_id": "dup-1"}], input_dir / "recommendations.jsonl")
    (input_dir / "reports").mkdir(parents=True)
    (input_dir / "reports" / "bootstrap_confidence.csv").write_text(
        "system,f1_mean,f1_ci_low,f1_ci_high\nours,0.9,0.8,1.0\n",
        encoding="utf-8",
    )
    (input_dir / "reports" / "error_analysis").mkdir(parents=True)
    (input_dir / "reports" / "error_analysis" / "error_analysis_summary.csv").write_text(
        "system,false_positive,false_negative\nours,1,2\n",
        encoding="utf-8",
    )
    (input_dir / "reports" / "manual_annotation").mkdir(parents=True)
    (input_dir / "reports" / "manual_annotation" / "manual_annotation_summary.csv").write_text(
        "sample_count,labeled_count\n10,8\n",
        encoding="utf-8",
    )

    export_paper_artifacts(input_dir, output_dir)

    assert (output_dir / "tables" / "run_summary.csv").exists()
    assert (output_dir / "tables" / "baseline_comparison.csv").exists()
    assert (output_dir / "tables" / "ablation_summary.csv").exists()
    assert (output_dir / "tables" / "bootstrap_confidence.csv").exists()
    assert (output_dir / "tables" / "error_analysis_summary.csv").exists()
    assert (output_dir / "tables" / "manual_annotation_summary.csv").exists()
    assert (output_dir / "figures" / "relation_type_distribution.png").read_bytes().startswith(b"\x89PNG")
    assert (output_dir / "figures" / "cluster_size_distribution.png").read_bytes().startswith(b"\x89PNG")
    assert (output_dir / "figures" / "baseline_f1.png").read_bytes().startswith(b"\x89PNG")
