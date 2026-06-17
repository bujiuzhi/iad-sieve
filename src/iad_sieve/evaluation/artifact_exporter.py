"""论文表格与图形产物导出模块。"""

from __future__ import annotations

import csv
import logging
import struct
import zlib
from collections import Counter
from pathlib import Path

from iad_sieve.evaluation.ablation_runner import run_ablation_summary
from iad_sieve.evaluation.baseline_runner import run_baseline_summary
from iad_sieve.evaluation.recommendation_evaluator import evaluate_recommendations
from iad_sieve.utils.io_utils import ensure_directory, read_records


LOGGER = logging.getLogger(__name__)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
Color = tuple[int, int, int]


def _read_if_exists(path: Path) -> list[dict]:
    """读取存在的 JSONL/Parquet 文件。

    参数:
        path: 输入文件路径。

    返回:
        记录列表；文件不存在时返回空列表。
    """
    if not path.exists():
        LOGGER.warning("导出产物时输入文件不存在: %s", path)
        return []
    return read_records(path)


def _count_lines(path: Path) -> int:
    """统计文本文件行数。

    参数:
        path: 输入文件路径。

    返回:
        行数，文件不存在时返回 0。
    """
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as file:
        for _ in file:
            count += 1
    return count


def _write_csv(path: Path, rows: list[dict], preferred_fields: list[str] | None = None) -> None:
    """写入 CSV 表。

    参数:
        path: 输出 CSV 路径。
        rows: 表格记录。
        preferred_fields: 可选优先字段顺序。

    返回:
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for field in preferred_fields or []:
        if field not in fields:
            fields.append(field)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    if not fields:
        fields = ["status"]
        rows = [{"status": "empty"}]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _copy_text_file_if_exists(source_path: Path, target_path: Path) -> bool:
    """复制已存在的文本产物。

    参数:
        source_path: 源文件路径。
        target_path: 目标文件路径。

    返回:
        是否完成复制。
    """
    if not source_path.exists():
        LOGGER.warning("可选论文产物不存在，跳过复制: %s", source_path)
        return False
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    return True


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """构造 PNG chunk。

    参数:
        chunk_type: PNG chunk 类型。
        data: chunk 数据。

    返回:
        编码后的 chunk 字节。
    """
    checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)


def _write_png(path: Path, pixels: list[list[Color]]) -> None:
    """写入 RGB PNG 文件。

    参数:
        path: 输出 PNG 路径。
        pixels: RGB 像素矩阵。

    返回:
        无。
    """
    height = len(pixels)
    width = len(pixels[0]) if height else 1
    raw_rows = []
    for row in pixels:
        raw_rows.append(b"\x00" + b"".join(bytes(pixel) for pixel in row))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as file:
        file.write(PNG_SIGNATURE)
        file.write(_png_chunk(b"IHDR", header))
        file.write(_png_chunk(b"IDAT", zlib.compress(b"".join(raw_rows), level=9)))
        file.write(_png_chunk(b"IEND", b""))


def _draw_rectangle(pixels: list[list[Color]], x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
    """在像素矩阵中绘制实心矩形。

    参数:
        pixels: RGB 像素矩阵。
        x0: 左边界。
        y0: 上边界。
        x1: 右边界。
        y1: 下边界。
        color: RGB 颜色。

    返回:
        无。
    """
    height = len(pixels)
    width = len(pixels[0]) if height else 0
    left = max(0, min(width, x0))
    right = max(0, min(width, x1))
    top = max(0, min(height, y0))
    bottom = max(0, min(height, y1))
    for y in range(top, bottom):
        row = pixels[y]
        for x in range(left, right):
            row[x] = color


def _write_bar_png(path: Path, values: list[float], width: int = 720, height: int = 360) -> None:
    """写入简单柱状 PNG 图。

    参数:
        path: 输出 PNG 路径。
        values: 柱状图数值。
        width: 图片宽度。
        height: 图片高度。

    返回:
        无。
    """
    clean_values = [max(0.0, float(value)) for value in values] or [0.0]
    if max(clean_values) == 0:
        clean_values = [1.0]
    palette: list[Color] = [(37, 99, 235), (16, 185, 129), (245, 158, 11), (239, 68, 68), (124, 58, 237), (14, 165, 233)]
    pixels: list[list[Color]] = [[(248, 250, 252) for _ in range(width)] for _ in range(height)]
    margin_left = 56
    margin_right = 32
    margin_top = 32
    margin_bottom = 48
    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom
    axis_color = (71, 85, 105)
    _draw_rectangle(pixels, margin_left, margin_top, margin_left + 2, margin_top + chart_height, axis_color)
    _draw_rectangle(pixels, margin_left, margin_top + chart_height, margin_left + chart_width, margin_top + chart_height + 2, axis_color)
    max_value = max(clean_values)
    slot_width = max(12, chart_width // max(1, len(clean_values)))
    bar_width = max(8, int(slot_width * 0.62))
    for index, value in enumerate(clean_values):
        bar_height = int(chart_height * (value / max_value))
        x0 = margin_left + index * slot_width + max(2, (slot_width - bar_width) // 2)
        y0 = margin_top + chart_height - bar_height
        _draw_rectangle(pixels, x0, y0, x0 + bar_width, margin_top + chart_height, palette[index % len(palette)])
    _write_png(path, pixels)


def _build_run_summary(input_dir: Path | None) -> list[dict]:
    """构造运行产物摘要。

    参数:
        input_dir: 实验输出目录。

    返回:
        运行产物摘要记录。
    """
    expected_files = [
        "normalized_documents.jsonl",
        "semantic_views.jsonl",
        "candidate_pairs.jsonl",
        "pair_relations.jsonl",
        "duplicate_groups.jsonl",
        "canonical_documents.jsonl",
        "topic_graph.jsonl",
        "clusters.jsonl",
        "cluster_membership.jsonl",
        "rankings.jsonl",
        "recommendations.jsonl",
    ]
    rows: list[dict] = []
    for file_name in expected_files:
        path = input_dir / file_name if input_dir else Path(file_name)
        rows.append(
            {
                "artifact": file_name.removesuffix(".jsonl"),
                "file": str(path),
                "record_count": _count_lines(path) if input_dir else 0,
                "size_bytes": path.stat().st_size if input_dir and path.exists() else 0,
                "status": "available" if input_dir and path.exists() else "missing",
            }
        )
    return rows


def _cluster_size_bins(clusters: list[dict]) -> list[int]:
    """计算聚类规模分箱计数。

    参数:
        clusters: 聚类记录。

    返回:
        分箱计数，顺序为 1、2-5、6-10、11-50、51+。
    """
    bins = [0, 0, 0, 0, 0]
    for cluster in clusters:
        size = int(cluster.get("cluster_size", 0) or 0)
        if size <= 1:
            bins[0] += 1
        elif size <= 5:
            bins[1] += 1
        elif size <= 10:
            bins[2] += 1
        elif size <= 50:
            bins[3] += 1
        else:
            bins[4] += 1
    return bins


def export_paper_artifacts(input_dir: str | Path | None, output_dir: str | Path) -> None:
    """导出论文表格和图形产物。

    参数:
        input_dir: 实验输出目录；为空时导出空模板。
        output_dir: 论文产物输出目录。

    返回:
        无。
    """
    resolved_input_dir = Path(input_dir) if input_dir else None
    resolved_output_dir = ensure_directory(output_dir)
    tables_dir = ensure_directory(resolved_output_dir / "tables")
    figures_dir = ensure_directory(resolved_output_dir / "figures")

    relations = _read_if_exists(resolved_input_dir / "pair_relations.jsonl") if resolved_input_dir else []
    clusters = _read_if_exists(resolved_input_dir / "clusters.jsonl") if resolved_input_dir else []
    rankings = _read_if_exists(resolved_input_dir / "rankings.jsonl") if resolved_input_dir else []
    recommendations = _read_if_exists(resolved_input_dir / "recommendations.jsonl") if resolved_input_dir else []

    run_summary = _build_run_summary(resolved_input_dir)
    baseline_rows = run_baseline_summary(relations)
    ablation_rows = run_ablation_summary(relations, rankings=rankings, recommendations=recommendations)
    recommendation_metrics = evaluate_recommendations(recommendations)
    role_counts = Counter(str(record.get("role", "unknown")) for record in recommendations)
    recommendation_rows = [
        {"metric": key, "value": value}
        for key, value in recommendation_metrics.items()
    ] + [{"metric": f"role_count_{role}", "value": count} for role, count in sorted(role_counts.items())]

    _write_csv(tables_dir / "run_summary.csv", run_summary, ["artifact", "file", "record_count", "size_bytes", "status"])
    _write_csv(tables_dir / "baseline_comparison.csv", baseline_rows, ["system", "description", "weak_label_count", "precision", "recall", "f1", "false_merge_rate"])
    _write_csv(tables_dir / "ablation_summary.csv", ablation_rows, ["variant", "status", "note", "weak_label_count", "precision", "recall", "f1", "false_merge_rate"])
    _write_csv(tables_dir / "recommendation_summary.csv", recommendation_rows, ["metric", "value"])
    if resolved_input_dir:
        _copy_text_file_if_exists(resolved_input_dir / "reports" / "bootstrap_confidence.csv", tables_dir / "bootstrap_confidence.csv")
        _copy_text_file_if_exists(resolved_input_dir / "reports" / "error_analysis" / "error_analysis_summary.csv", tables_dir / "error_analysis_summary.csv")
        _copy_text_file_if_exists(resolved_input_dir / "reports" / "manual_annotation" / "manual_annotation_summary.csv", tables_dir / "manual_annotation_summary.csv")

    relation_type_counts = Counter(str(relation.get("relation_type", "unknown")) for relation in relations)
    _write_bar_png(figures_dir / "relation_type_distribution.png", [float(value) for _, value in relation_type_counts.most_common(8)] or [0.0])
    _write_bar_png(figures_dir / "cluster_size_distribution.png", [float(value) for value in _cluster_size_bins(clusters)])
    _write_bar_png(figures_dir / "baseline_f1.png", [float(row.get("f1", 0.0)) for row in baseline_rows])

    figure_rows = [
        {"figure": "relation_type_distribution.png", "source_table": "pair_relations.jsonl", "description": "候选文献对关系类型分布"},
        {"figure": "cluster_size_distribution.png", "source_table": "clusters.jsonl", "description": "主题簇规模分布"},
        {"figure": "baseline_f1.png", "source_table": "baseline_comparison.csv", "description": "baseline 与 RSL-Sieve 弱监督 F1 对比"},
    ]
    _write_csv(tables_dir / "figure_index.csv", figure_rows, ["figure", "source_table", "description"])
    LOGGER.info("论文产物导出完成: %s", resolved_output_dir)
