"""高级模型证据矩阵模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
COUNTED_EXECUTION_MODES = {"actual_model", "api_model"}
PREFERRED_FIELDS = [
    "evidence_id",
    "system",
    "evidence_type",
    "evidence_status",
    "execution_mode",
    "model_backend",
    "evaluation_track",
    "threshold",
    "same_work_f1",
    "false_merge_rate",
    "hard_negative_false_merge_rate_mean",
    "advancedness_claim_allowed",
    "reviewer_risk",
    "missing_reason",
    "next_action",
]


def _ready_evidence_status(execution_mode: str) -> str:
    """根据执行模式返回可计入投稿证据的状态。

    参数:
        execution_mode: 执行模式。

    返回:
        ready_actual_model、ready_api_model 或 not_counted_fallback。
    """
    if execution_mode == "actual_model":
        return "ready_actual_model"
    if execution_mode == "api_model":
        return "ready_api_model"
    return "not_counted_fallback"


def _is_counted_execution_mode(execution_mode: str) -> bool:
    """判断执行模式是否可计入强模型证据。

    参数:
        execution_mode: 执行模式。

    返回:
        actual_model 或 api_model 返回 True。
    """
    return execution_mode in COUNTED_EXECUTION_MODES


def _float_or_empty(value: object) -> float | str:
    """把数值字段转为 float，空值保持为空字符串。

    参数:
        value: 原始字段值。

    返回:
        float 或空字符串。
    """
    if value in {None, ""}:
        return ""
    try:
        return float(value)
    except (TypeError, ValueError):
        LOGGER.warning("数值字段无法解析: %s", value)
        return ""


def _best_metric_rows(metric_rows: list[dict]) -> dict[str, dict]:
    """按 system 选择 F1 最高的 metric summary。

    参数:
        metric_rows: baseline metric summary 记录。

    返回:
        system 到最佳 metric 记录的映射。
    """
    best: dict[str, dict] = {}
    for row in metric_rows:
        system = str(row.get("system", ""))
        if not system:
            continue
        current_f1 = float(row.get("f1", 0.0) or 0.0)
        previous_f1 = float(best.get(system, {}).get("f1", -1.0) or -1.0)
        if system not in best or current_f1 > previous_f1:
            best[system] = row
    return best


def _execution_by_system(execution_rows: list[dict]) -> dict[str, dict]:
    """按 system 建立执行摘要索引。

    参数:
        execution_rows: execution summary 记录。

    返回:
        system 到执行摘要的映射。
    """
    return {str(row.get("system", "")): row for row in execution_rows if row.get("system")}


def _bootstrap_hard_negative_by_system(bootstrap_rows: list[dict]) -> dict[str, float]:
    """提取每个 system 的 hard-negative false merge rate。

    参数:
        bootstrap_rows: bootstrap CSV 记录。

    返回:
        system 到 hard-negative false merge rate mean 的映射。
    """
    values: dict[str, float] = {}
    for row in bootstrap_rows:
        if row.get("metric_scope") != "hard_negative_pairs":
            continue
        system = str(row.get("system", ""))
        if not system:
            continue
        value = _float_or_empty(row.get("hard_negative_false_merge_rate_mean"))
        if isinstance(value, float):
            values[system] = value
    return values


def _remote_missing(remote_summary_rows: list[dict]) -> bool:
    """判断是否仍缺远程输出。

    参数:
        remote_summary_rows: remote output validation summary 记录。

    返回:
        存在缺失输出返回 True。
    """
    for row in remote_summary_rows:
        if row.get("all_outputs_valid") is True or str(row.get("all_outputs_valid", "")).lower() == "true":
            return False
        try:
            return int(row.get("missing_output_count", 0)) > 0
        except (TypeError, ValueError):
            return True
    return True


def _canonical_transformer_system(row: dict) -> str:
    """规范化 IAD-Risk Transformer system 名称。

    参数:
        row: transformer summary 记录。

    返回:
        system 名称。
    """
    system = str(row.get("system", "iad_risk_transformer"))
    if system == "iad_risk_transformer":
        return "iad_risk_transformer_open_v2"
    return system


def _evaluation_track(system: str) -> str:
    """根据 system 名称推断评估轨道。

    参数:
        system: 模型或 baseline 的 system 名称。

    返回:
        评估轨道名称，用于防止跨数据集混合比较。
    """
    if "open_v3_scholarly_balanced_gold_source_heldout" in system:
        return "open_v3_scholarly_balanced_gold_source_heldout"
    if "open_v3_scholarly_balanced_gold" in system:
        return "open_v3_scholarly_balanced_gold"
    if "open_v3_balanced_gold_source_heldout" in system:
        return "open_v3_balanced_gold_source_heldout"
    if "open_v3_balanced_gold" in system:
        return "open_v3_balanced_gold"
    if "open_v3_multitopic_silver_patch_topic_heldout" in system:
        return "open_v3_multitopic_silver_patch_topic_heldout"
    if "open_v3_multitopic_silver_patch" in system:
        return "open_v3_multitopic_silver_patch"
    if "open_v3_gold_silver" in system:
        return "open_v3_gold_silver"
    if "open_v3" in system:
        return "open_v3"
    if "open_v2" in system:
        return "open_v2"
    if "openalex_v1" in system:
        return "openalex_v1"
    return "unscoped"


def _is_ready_model(row: dict) -> bool:
    """判断证据行是否为可计入模型。

    参数:
        row: 高级模型证据记录。

    返回:
        actual_model 或 api_model 证据返回 True。
    """
    return row.get("evidence_status") in {"ready_actual_model", "ready_api_model"}


def _is_plm_entity_matching_system(system: str) -> bool:
    """判断 system 是否属于 PLM entity matching baseline。

    参数:
        system: system 名称。

    返回:
        RoBERTa、DistilBERT、DeBERTa、Ditto 或 DeepMatcher baseline 返回 True。
    """
    normalized = system.lower()
    markers = ("roberta", "distilbert", "deberta", "ditto", "deepmatcher")
    return any(marker in normalized for marker in markers)


def _is_llm_entity_matching_system(system: str) -> bool:
    """判断 system 是否属于 LLM/API entity matching baseline。

    参数:
        system: system 名称。

    返回:
        GPT、LLM、AnyMatch 或 ComEM baseline 返回 True。
    """
    normalized = system.lower()
    markers = ("gpt", "llm", "anymatch", "comem")
    return any(marker in normalized for marker in markers)


def _transformer_summary_priority(row: dict) -> tuple[str, int]:
    """返回 Transformer summary 去重前的 split 优先级。

    参数:
        row: Transformer summary 记录。

    返回:
        system 与 split 优先级；source-heldout 轨道优先 test，其余轨道优先 all。
    """
    system = _canonical_transformer_system(row)
    eval_split = str(row.get("eval_split", "") or "")
    if "source_heldout" in system:
        split_priority = {"test": 0, "all": 1, "": 2}.get(eval_split, 3)
    else:
        split_priority = {"all": 0, "": 1, "test": 2}.get(eval_split, 3)
    return system, split_priority


def _evidence_row(
    evidence_id: str,
    system: str,
    evidence_type: str,
    evidence_status: str,
    execution_mode: str,
    model_backend: str,
    evaluation_track: str,
    threshold: object,
    same_work_f1: object,
    false_merge_rate: object,
    hard_negative_false_merge_rate_mean: object,
    advancedness_claim_allowed: str,
    reviewer_risk: str,
    missing_reason: str,
    next_action: str,
) -> dict:
    """构造高级模型证据记录。

    参数:
        evidence_id: 证据 ID。
        system: 系统名称。
        evidence_type: 证据类型。
        evidence_status: 证据状态。
        execution_mode: 执行模式。
        model_backend: 模型后端。
        evaluation_track: 评估轨道。
        threshold: 评估阈值。
        same_work_f1: same_work F1。
        false_merge_rate: 误合并率。
        hard_negative_false_merge_rate_mean: hard negative 误合并率均值。
        advancedness_claim_allowed: yes、limited 或 no。
        reviewer_risk: high、medium 或 low。
        missing_reason: 缺失原因。
        next_action: 下一步动作。

    返回:
        高级模型证据记录。
    """
    return {
        "evidence_id": evidence_id,
        "system": system,
        "evidence_type": evidence_type,
        "evidence_status": evidence_status,
        "execution_mode": execution_mode,
        "model_backend": model_backend,
        "evaluation_track": evaluation_track,
        "threshold": _float_or_empty(threshold),
        "same_work_f1": _float_or_empty(same_work_f1),
        "false_merge_rate": _float_or_empty(false_merge_rate),
        "hard_negative_false_merge_rate_mean": _float_or_empty(hard_negative_false_merge_rate_mean),
        "advancedness_claim_allowed": advancedness_claim_allowed,
        "reviewer_risk": reviewer_risk,
        "missing_reason": missing_reason,
        "next_action": next_action,
    }


def build_advanced_model_evidence_rows(
    baseline_metric_rows: list[dict],
    execution_summary_rows: list[dict],
    transformer_summary_rows: list[dict],
    bootstrap_rows: list[dict],
    remote_summary_rows: list[dict],
    required_systems: list[str] | None = None,
) -> list[dict]:
    """构建高级模型证据矩阵。

    参数:
        baseline_metric_rows: baseline metric summary 记录。
        execution_summary_rows: baseline execution summary 记录。
        transformer_summary_rows: IAD-Risk Transformer summary 记录。
        bootstrap_rows: bootstrap CSV 记录。
        remote_summary_rows: 远程输出验收 summary 记录。
        required_systems: 投稿前必须补齐的强模型 system。

    返回:
        高级模型证据记录列表。
    """
    try:
        remote_has_missing = _remote_missing(remote_summary_rows)
        hard_negative_by_system = _bootstrap_hard_negative_by_system(bootstrap_rows)
        execution_by_system = _execution_by_system(execution_summary_rows)
        best_metrics = _best_metric_rows(baseline_metric_rows)
        present_systems: set[str] = set()
        rows: list[dict] = []

        for row in sorted(transformer_summary_rows, key=_transformer_summary_priority):
            if row.get("eval_split") not in {"test", "all", None, ""}:
                continue
            system = _canonical_transformer_system(row)
            if system in present_systems:
                continue
            execution_mode = str(row.get("execution_mode", ""))
            evidence_status = _ready_evidence_status(execution_mode)
            present_systems.add(system)
            rows.append(
                _evidence_row(
                    evidence_id=f"transformer:{system}",
                    system=system,
                    evidence_type="main_method_transformer",
                    evidence_status=evidence_status,
                    execution_mode=execution_mode,
                    model_backend=str(row.get("model_backend", "")),
                    evaluation_track=_evaluation_track(system),
                    threshold="",
                    same_work_f1=row.get("same_work_f1", row.get("f1", "")),
                    false_merge_rate=row.get("false_merge_rate", ""),
                    hard_negative_false_merge_rate_mean=hard_negative_by_system.get(system, ""),
                    advancedness_claim_allowed="limited" if _is_counted_execution_mode(execution_mode) else "no",
                    reviewer_risk="medium" if _is_counted_execution_mode(execution_mode) else "high",
                    missing_reason="" if _is_counted_execution_mode(execution_mode) else "execution_mode is not actual_model or api_model",
                    next_action="补齐 SPECTER2 encoder 稳定性后再提升先进性主张。",
                )
            )

        for system, row in sorted(best_metrics.items()):
            execution_row = execution_by_system.get(system, {})
            execution_mode = str(execution_row.get("execution_mode", row.get("execution_mode", "")))
            evidence_status = _ready_evidence_status(execution_mode)
            present_systems.add(system)
            rows.append(
                _evidence_row(
                    evidence_id=f"baseline:{system}",
                    system=system,
                    evidence_type=str(row.get("baseline_family", "strong_baseline")),
                    evidence_status=evidence_status,
                    execution_mode=execution_mode,
                    model_backend=str(execution_row.get("model_backend", "")),
                    evaluation_track=_evaluation_track(system),
                    threshold=row.get("threshold", ""),
                    same_work_f1=row.get("f1", ""),
                    false_merge_rate=row.get("false_merge_rate", ""),
                    hard_negative_false_merge_rate_mean=hard_negative_by_system.get(system, ""),
                    advancedness_claim_allowed="limited" if _is_counted_execution_mode(execution_mode) else "no",
                    reviewer_risk="medium" if _is_counted_execution_mode(execution_mode) else "high",
                    missing_reason="" if _is_counted_execution_mode(execution_mode) else "fallback result cannot support reviewer-facing advancedness",
                    next_action=(
                        "保留为强 baseline 对照，并报告 hard-negative 误合并。"
                        if _is_counted_execution_mode(execution_mode)
                        else "替换为 api_model 或 actual_model 结果。"
                    ),
                )
            )

        for system in required_systems or []:
            if system in present_systems:
                continue
            rows.append(
                _evidence_row(
                    evidence_id=f"required:{system}",
                    system=system,
                    evidence_type="required_strong_baseline",
                    evidence_status="missing_required",
                    execution_mode="",
                    model_backend="",
                    evaluation_track=_evaluation_track(system),
                    threshold="",
                    same_work_f1="",
                    false_merge_rate="",
                    hard_negative_false_merge_rate_mean="",
                    advancedness_claim_allowed="no",
                    reviewer_risk="high",
                    missing_reason="remote output missing" if remote_has_missing else "required system not provided",
                    next_action="运行对应 actual_model 并重建 advanced model evidence matrix。",
                )
            )

        rows.sort(key=lambda item: (item["evidence_status"] == "missing_required", item["system"]))
        LOGGER.info("高级模型证据矩阵完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建高级模型证据矩阵失败")
        raise


def _read_csv_records(path: str | Path) -> list[dict]:
    """读取 CSV 记录。

    参数:
        path: CSV 文件路径。

    返回:
        字典记录列表。
    """
    try:
        with Path(path).open("r", encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))
    except OSError:
        LOGGER.exception("读取 CSV 文件失败: %s", path)
        raise


def _input_exists(path: str | Path) -> bool:
    """判断高级模型证据输入文件是否存在。

    参数:
        path: 输入文件路径。

    返回:
        文件存在返回 True。
    """
    if Path(path).exists():
        return True
    LOGGER.warning("高级模型证据输入缺失，跳过: %s", path)
    return False


def build_advanced_model_evidence_rows_from_paths(
    baseline_metric_summary_paths: list[str | Path],
    execution_summary_paths: list[str | Path],
    transformer_summary_paths: list[str | Path],
    bootstrap_summary_paths: list[str | Path],
    remote_output_summary_paths: list[str | Path],
    required_systems: list[str] | None = None,
) -> list[dict]:
    """从文件构建高级模型证据矩阵。

    参数:
        baseline_metric_summary_paths: baseline metric summary JSONL 文件。
        execution_summary_paths: execution summary JSONL 文件。
        transformer_summary_paths: IAD-Risk Transformer summary JSONL 文件。
        bootstrap_summary_paths: bootstrap CSV 文件。
        remote_output_summary_paths: 远程输出验收 summary JSONL 文件。
        required_systems: 必需强模型系统列表。

    返回:
        高级模型证据记录列表。
    """
    metric_rows: list[dict] = []
    execution_rows: list[dict] = []
    transformer_rows: list[dict] = []
    bootstrap_rows: list[dict] = []
    remote_rows: list[dict] = []
    try:
        for path in baseline_metric_summary_paths:
            if not _input_exists(path):
                continue
            metric_rows.extend(read_records(path))
        for path in execution_summary_paths:
            if not _input_exists(path):
                continue
            execution_rows.extend(read_records(path))
        for path in transformer_summary_paths:
            if not _input_exists(path):
                continue
            transformer_rows.extend(read_records(path))
        for path in bootstrap_summary_paths:
            if not _input_exists(path):
                continue
            bootstrap_rows.extend(_read_csv_records(path))
        for path in remote_output_summary_paths:
            if not _input_exists(path):
                continue
            remote_rows.extend(read_records(path))
    except Exception:
        LOGGER.exception("读取高级模型证据矩阵输入失败")
        raise
    return build_advanced_model_evidence_rows(metric_rows, execution_rows, transformer_rows, bootstrap_rows, remote_rows, required_systems)


def _serialize_cell(value: object) -> object:
    """序列化 CSV/Markdown 单元格。

    参数:
        value: 原始值。

    返回:
        可写入单元格的值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_rows_csv(path: Path, rows: list[dict], preferred_fields: list[str] | None = None) -> None:
    """写出通用 CSV。

    参数:
        path: 输出路径。
        rows: 字典记录。
        preferred_fields: 优先字段顺序。

    返回:
        无。
    """
    fields: list[str] = []
    for field in preferred_fields or []:
        if field not in fields:
            fields.append(field)
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _serialize_cell(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出高级模型证据矩阵 CSV 失败: %s", path)
        raise


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 高级模型证据矩阵。

    参数:
        path: 输出路径。
        rows: 证据矩阵记录。

    返回:
        无。
    """
    _write_rows_csv(path, rows, PREFERRED_FIELDS)


def _track_priority(track: str) -> tuple[int, str]:
    """返回评估轨道优先级。

    参数:
        track: evaluation_track 名称。

    返回:
        排序用优先级元组。
    """
    priorities = {
        "open_v3_scholarly_balanced_gold": 0,
        "open_v3_scholarly_balanced_gold_source_heldout": 1,
        "open_v3_multitopic_silver_patch_topic_heldout": 2,
        "open_v3_multitopic_silver_patch": 3,
        "open_v3_balanced_gold": 4,
        "open_v3_balanced_gold_source_heldout": 5,
        "open_v3_gold_silver": 6,
        "open_v2": 7,
        "openalex_v1": 8,
        "unscoped": 99,
    }
    return priorities.get(track, 50), track


def _build_track_summary(rows: list[dict]) -> list[dict]:
    """构建 evaluation_track 级强模型证据汇总。

    参数:
        rows: 高级模型证据记录。

    返回:
        evaluation_track 汇总记录。
    """
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        track = str(row.get("evaluation_track") or "unscoped")
        grouped.setdefault(track, []).append(row)
    track_rows: list[dict] = []
    for track, track_items in grouped.items():
        ready_actual_count = sum(1 for row in track_items if row.get("evidence_status") == "ready_actual_model")
        ready_api_count = sum(1 for row in track_items if row.get("evidence_status") == "ready_api_model")
        ready_model_count = ready_actual_count + ready_api_count
        missing_required_count = sum(1 for row in track_items if row.get("evidence_status") == "missing_required")
        fallback_count = sum(1 for row in track_items if row.get("evidence_status") == "not_counted_fallback")
        track_rows.append(
            {
                "evaluation_track": track,
                "track_status": "blocked" if missing_required_count else "ready",
                "evidence_count": len(track_items),
                "ready_actual_model_count": ready_actual_count,
                "ready_api_model_count": ready_api_count,
                "ready_model_count": ready_model_count,
                "not_counted_fallback_count": fallback_count,
                "missing_required_count": missing_required_count,
                "ready_systems": sorted(
                    row.get("system", "") for row in track_items if row.get("evidence_status") in {"ready_actual_model", "ready_api_model"}
                ),
                "missing_required_systems": sorted(row.get("system", "") for row in track_items if row.get("evidence_status") == "missing_required"),
            }
        )
    track_rows.sort(key=lambda row: _track_priority(str(row.get("evaluation_track", ""))))
    return track_rows


def _build_summary(rows: list[dict], track_rows: list[dict]) -> dict:
    """构建高级模型证据矩阵汇总。

    参数:
        rows: 证据矩阵记录。
        track_rows: evaluation_track 汇总记录。

    返回:
        汇总记录。
    """
    blocked_tracks = [row for row in track_rows if row.get("track_status") == "blocked"]
    ready_tracks = [row for row in track_rows if row.get("track_status") == "ready"]
    highest_missing_track = blocked_tracks[0].get("evaluation_track", "") if blocked_tracks else ""
    return {
        "evidence_count": len(rows),
        "ready_actual_model_count": sum(1 for row in rows if row.get("evidence_status") == "ready_actual_model"),
        "ready_api_model_count": sum(1 for row in rows if row.get("evidence_status") == "ready_api_model"),
        "ready_model_count": sum(1 for row in rows if _is_ready_model(row)),
        "ready_plm_model_count": sum(1 for row in rows if _is_ready_model(row) and _is_plm_entity_matching_system(str(row.get("system", "")))),
        "ready_llm_model_count": sum(1 for row in rows if _is_ready_model(row) and _is_llm_entity_matching_system(str(row.get("system", "")))),
        "not_counted_fallback_count": sum(1 for row in rows if row.get("evidence_status") == "not_counted_fallback"),
        "missing_required_count": sum(1 for row in rows if row.get("evidence_status") == "missing_required"),
        "missing_plm_required_count": sum(
            1
            for row in rows
            if row.get("evidence_status") == "missing_required" and _is_plm_entity_matching_system(str(row.get("system", "")))
        ),
        "missing_llm_required_count": sum(
            1
            for row in rows
            if row.get("evidence_status") == "missing_required" and _is_llm_entity_matching_system(str(row.get("system", "")))
        ),
        "advancedness_claim_yes_count": sum(1 for row in rows if row.get("advancedness_claim_allowed") == "yes"),
        "advancedness_claim_limited_count": sum(1 for row in rows if row.get("advancedness_claim_allowed") == "limited"),
        "evaluation_track_count": len(track_rows),
        "ready_evaluation_track_count": len(ready_tracks),
        "blocked_evaluation_track_count": len(blocked_tracks),
        "highest_priority_missing_track": highest_missing_track,
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 高级模型证据矩阵。

    参数:
        path: 输出路径。
        rows: 证据矩阵记录。
        summary: 汇总记录。

    返回:
        无。
    """
    track_fields = [
        "evaluation_track",
        "track_status",
        "evidence_count",
        "ready_model_count",
        "missing_required_count",
    ]
    fields = [
        "system",
        "evaluation_track",
        "evidence_status",
        "execution_mode",
        "same_work_f1",
        "hard_negative_false_merge_rate_mean",
        "advancedness_claim_allowed",
        "reviewer_risk",
    ]
    lines = [
        "# Advanced Model Evidence Matrix",
        "",
        "## 使用边界",
        "",
        "该矩阵只确认模型证据是否能支撑审稿写作；fallback 和 missing_required 不得写成强模型完成结果。",
        "",
        "## 汇总",
        "",
        f"- evidence_count: {summary['evidence_count']}",
        f"- ready_actual_model_count: {summary['ready_actual_model_count']}",
        f"- ready_api_model_count: {summary['ready_api_model_count']}",
        f"- ready_model_count: {summary['ready_model_count']}",
        f"- not_counted_fallback_count: {summary['not_counted_fallback_count']}",
        f"- missing_required_count: {summary['missing_required_count']}",
        f"- advancedness_claim_limited_count: {summary['advancedness_claim_limited_count']}",
        f"- evaluation_track_count: {summary['evaluation_track_count']}",
        f"- blocked_evaluation_track_count: {summary['blocked_evaluation_track_count']}",
        f"- highest_priority_missing_track: {summary['highest_priority_missing_track']}",
        "",
        "## 评估轨道汇总",
        "",
        "| " + " | ".join(track_fields) + " |",
        "| " + " | ".join(["---"] * len(track_fields)) + " |",
    ]
    for row in summary["track_rows"]:
        values = [str(_serialize_cell(row.get(field, ""))).replace("\n", " ").replace("|", "/") for field in track_fields]
        lines.append("| " + " | ".join(values) + " |")
    lines.extend(
        [
        "",
        "## 模型证据",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
        ]
    )
    for row in rows:
        values = [str(_serialize_cell(row.get(field, ""))).replace("\n", " ").replace("|", "/") for field in fields]
        lines.append("| " + " | ".join(values) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出高级模型证据矩阵 Markdown 失败: %s", path)
        raise


def write_advanced_model_evidence_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出高级模型证据矩阵产物。

    参数:
        rows: 证据矩阵记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    track_rows = _build_track_summary(rows)
    summary = _build_summary(rows, track_rows)
    markdown_summary = dict(summary)
    markdown_summary["track_rows"] = track_rows
    try:
        write_records(rows, directory / "advanced_model_evidence.jsonl")
        write_records([summary], directory / "advanced_model_evidence_summary.jsonl")
        write_records(track_rows, directory / "advanced_model_evidence_track_summary.jsonl")
        _write_csv(directory / "advanced_model_evidence.csv", rows)
        _write_rows_csv(
            directory / "advanced_model_evidence_track_summary.csv",
            track_rows,
            [
                "evaluation_track",
                "track_status",
                "evidence_count",
                "ready_model_count",
                "missing_required_count",
                "missing_required_systems",
            ],
        )
        _write_markdown(directory / "advanced_model_evidence.md", rows, markdown_summary)
    except Exception:
        LOGGER.exception("写出高级模型证据矩阵失败: %s", output_dir)
        raise
