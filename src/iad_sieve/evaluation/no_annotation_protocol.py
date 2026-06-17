"""无人工标注阶段协议生成模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "protocol_id",
    "protocol_dimension",
    "status",
    "reviewer_risk_level",
    "current_evidence",
    "allowed_claim",
    "forbidden_claim",
    "required_action",
    "acceptance_evidence",
    "human_annotation_required_now",
    "remote_required",
    "source_ids",
]
BLOCKED_STATUSES = {"blocked", "high_risk", "major_revision_required"}
READY_STATUSES = {"ready", "defensible", "evidence_ready"}


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _bool_value(value: object) -> bool:
    """解析布尔值。

    参数:
        value: 原始字段值。

    返回:
        布尔值。
    """
    if isinstance(value, bool):
        return value
    return _clean(value).lower() in {"1", "true", "yes", "y"}


def _list_value(value: object) -> list[str]:
    """解析列表或分号分隔字段。

    参数:
        value: 原始字段值。

    返回:
        字符串列表。
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    return [item.strip() for item in str(value).split(";") if item.strip()]


def _unique(values: list[str]) -> list[str]:
    """按出现顺序去重。

    参数:
        values: 字符串列表。

    返回:
        去重后的字符串列表。
    """
    return list(dict.fromkeys(value for value in values if value))


def _row_by_id(rows: list[dict], field_name: str, field_value: str) -> dict:
    """按字段值读取首条记录。

    参数:
        rows: 输入记录。
        field_name: 字段名。
        field_value: 字段值。

    返回:
        匹配记录；不存在时返回空字典。
    """
    for row in rows:
        if _clean(row.get(field_name)) == field_value:
            return row
    return {}


def _status_counts(rows: list[dict], status_field: str) -> dict[str, int]:
    """统计状态字段。

    参数:
        rows: 输入记录。
        status_field: 状态字段名。

    返回:
        状态到数量的映射。
    """
    counts: dict[str, int] = {}
    for row in rows:
        status = _clean(row.get(status_field))
        if not status:
            continue
        counts[status] = counts.get(status, 0) + 1
    return counts


def _public_data_protocol(public_data_rows: list[dict]) -> dict:
    """构建公开数据证据协议项。

    参数:
        public_data_rows: public_data_validity_audit 记录。

    返回:
        协议记录。
    """
    counts = _status_counts(public_data_rows, "audit_status")
    human_row = _row_by_id(public_data_rows, "dimension_id", "human_audit_absence")
    high_risk_count = counts.get("high_risk", 0)
    conditional_count = counts.get("conditional", 0)
    if high_risk_count:
        status = "conditional"
        risk = "high"
    elif conditional_count:
        status = "conditional"
        risk = "medium"
    else:
        status = "defensible"
        risk = "low"
    evidence = (
        f"public_data_dimensions={len(public_data_rows)}; "
        f"high_risk={high_risk_count}; conditional={conditional_count}; "
        f"human_audit_status={_clean(human_row.get('audit_status')) or 'unknown'}"
    )
    return {
        "protocol_id": "public_data_label_contract",
        "protocol_dimension": "公开 gold/proxy/silver 证据边界",
        "status": status,
        "reviewer_risk_level": risk,
        "current_evidence": evidence,
        "allowed_claim": "可写公开 gold 支撑 same_work，公开 silver 支撑 hard-negative 压力测试，且二者分层报告。",
        "forbidden_claim": "不得把 OpenAlex silver、LLM 输出或公开 proxy 写成人工 gold。",
        "required_action": "继续保留 label_strength、label_source 和 split 分层指标；若存在 high_risk 数据维度，先补公开数据或限制论文主张。",
        "acceptance_evidence": "public_data_validity_audit 中 gold_scale、relation_label_balance、evidence_tier_separation、split_coverage 和 human_audit_absence 均有明确边界。",
        "human_annotation_required_now": False,
        "remote_required": False,
        "source_ids": [_clean(row.get("dimension_id")) for row in public_data_rows],
    }


def _human_boundary_protocol(public_data_rows: list[dict], roadmap_rows: list[dict]) -> dict:
    """构建人工标注后置协议项。

    参数:
        public_data_rows: public_data_validity_audit 记录。
        roadmap_rows: q2b_upgrade_roadmap 记录。

    返回:
        协议记录。
    """
    human_required = any(_bool_value(row.get("human_annotation_required_now")) for row in roadmap_rows)
    human_row = _row_by_id(public_data_rows, "dimension_id", "human_audit_absence")
    human_status = _clean(human_row.get("audit_status")) or "unknown"
    status = "blocked_annotation_required" if human_required else "deferred_enhancement"
    risk = "high" if human_required else "medium"
    return {
        "protocol_id": "human_gold_deferred_boundary",
        "protocol_dimension": "人工 gold 后置边界",
        "status": status,
        "reviewer_risk_level": risk,
        "current_evidence": f"human_annotation_required_now={human_required}; human_audit_status={human_status}",
        "allowed_claim": "当前阶段可说明人工 gold 是后续增强，不作为本阶段启动条件。",
        "forbidden_claim": "不得声称已有人工 gold、大规模人工标注或人工一致性结果。",
        "required_action": "标注协调完成后再按 annotation-requirements 抽样 500-1,000 pair 做双标与仲裁。",
        "acceptance_evidence": "Q2/B 路线图中 human_annotation_required_now=false，且人工 gold 阶段为 deferred。",
        "human_annotation_required_now": human_required,
        "remote_required": False,
        "source_ids": ["human_audit_absence", "p5_optional_human_gold_enhancement"],
    }


def _remote_protocol(remote_input_rows: list[dict]) -> dict:
    """构建远程强模型依赖协议项。

    参数:
        remote_input_rows: remote_input_request 记录。

    返回:
        协议记录。
    """
    waiting_rows = [row for row in remote_input_rows if _clean(row.get("status")) in {"waiting_for_user", "waiting_for_secure_configuration"}]
    requested_fields = [_clean(row.get("field_name")) for row in waiting_rows if _clean(row.get("field_name"))]
    status = "blocked_remote_required" if waiting_rows else "ready"
    risk = "high" if waiting_rows else "low"
    return {
        "protocol_id": "remote_strong_model_dependency",
        "protocol_dimension": "强模型与 API baseline 远程依赖",
        "status": status,
        "reviewer_risk_level": risk,
        "current_evidence": f"waiting_remote_inputs={len(waiting_rows)}; requested_fields={','.join(requested_fields)}",
        "allowed_claim": "远程输出未验收前，只能写强模型实验计划、执行脚本和验收标准。",
        "forbidden_claim": "不得声称 SPECTER2、LLM judge、source-held-out 强模型或 Q2/B 证据闭环已完成。",
        "required_action": "补齐远程连接字段和安全密钥配置后执行 stage 脚本，回传 outputs 并重建验收审计。",
        "acceptance_evidence": "remote_input_request 全部为 provided 或 securely_configured，remote_result_acceptance 全部门禁 accepted。",
        "human_annotation_required_now": False,
        "remote_required": True,
        "source_ids": [_clean(row.get("request_id")) for row in remote_input_rows],
    }


def _claim_protocol(roadmap_rows: list[dict], reviewer_rows: list[dict]) -> dict:
    """构建论文主张锁定协议项。

    参数:
        roadmap_rows: q2b_upgrade_roadmap 记录。
        reviewer_rows: reviewer_iteration_audit 记录。

    返回:
        协议记录。
    """
    roadmap_blocked = [row for row in roadmap_rows if _clean(row.get("status")) in BLOCKED_STATUSES or _clean(row.get("status")).startswith("blocked")]
    critical_reviews = [row for row in reviewer_rows if _clean(row.get("severity")) == "critical"]
    q2b_ready = bool(roadmap_rows) and not roadmap_blocked and not critical_reviews
    status = "ready" if q2b_ready else "claim_lockdown_required"
    risk = "low" if q2b_ready else "high"
    boundaries = _unique([_clean(row.get("paper_claim_boundary")) for row in roadmap_rows + reviewer_rows])
    return {
        "protocol_id": "q2b_claim_lockdown",
        "protocol_dimension": "二区/B 类主张安全边界",
        "status": status,
        "reviewer_risk_level": risk,
        "current_evidence": f"blocked_roadmap_phase_count={len(roadmap_blocked)}; critical_review_count={len(critical_reviews)}",
        "allowed_claim": "可写当前方法设计、公开数据证据链、机制性错误分析和仍需补齐的强模型实验。",
        "forbidden_claim": "不得声称已经达到二区/B 类、SOTA、全面优于强模型或完成投稿级闭环。",
        "required_action": "关闭 remote、strong baseline、innovation depth、source-held-out 和 claim gate 后重建全部审稿审计。",
        "acceptance_evidence": "q2b_upgrade_roadmap 全部 ready，reviewer_iteration_audit 无 critical/major revision required。",
        "human_annotation_required_now": False,
        "remote_required": False,
        "source_ids": _unique([_clean(row.get("phase_id")) for row in roadmap_rows] + [_clean(row.get("iteration_id")) for row in reviewer_rows]),
        "paper_claim_boundary": "；".join(boundaries[:4]),
    }


def _future_human_audit_protocol(roadmap_rows: list[dict]) -> dict:
    """构建后续人工 audit 协议项。

    参数:
        roadmap_rows: q2b_upgrade_roadmap 记录。

    返回:
        协议记录。
    """
    phase = _row_by_id(roadmap_rows, "phase_id", "p5_optional_human_gold_enhancement")
    return {
        "protocol_id": "future_human_audit_enhancement",
        "protocol_dimension": "后续人工 gold 增强",
        "status": "deferred_enhancement",
        "reviewer_risk_level": "medium",
        "current_evidence": _clean(phase.get("current_blockers")) or "annotation_coordination_deferred",
        "allowed_claim": "可把人工 gold 写作后续增强和独立 audit 计划。",
        "forbidden_claim": "不得把该计划写成已经完成的数据集或实验结果。",
        "required_action": _clean(phase.get("required_actions")) or "协调后执行 500-1,000 pair 双标、仲裁和一致性统计。",
        "acceptance_evidence": _clean(phase.get("acceptance_evidence")) or "Cohen's Kappa >= 0.70，双标一致率 >= 80%，仲裁完成率 100%。",
        "human_annotation_required_now": False,
        "remote_required": False,
        "source_ids": ["p5_optional_human_gold_enhancement"],
    }


def build_no_annotation_protocol_rows(
    public_data_rows: list[dict],
    q2b_roadmap_rows: list[dict],
    reviewer_iteration_rows: list[dict] | None = None,
    remote_input_request_rows: list[dict] | None = None,
) -> list[dict]:
    """构建无人工标注阶段协议记录。

    参数:
        public_data_rows: 一个或多个 public_data_validity_audit 记录。
        q2b_roadmap_rows: q2b_upgrade_roadmap 记录。
        reviewer_iteration_rows: reviewer_iteration_audit 记录。
        remote_input_request_rows: remote_input_request 记录。

    返回:
        协议记录列表。
    """
    try:
        reviewer_rows = reviewer_iteration_rows or []
        remote_rows = remote_input_request_rows or []
        rows = [
            _public_data_protocol(public_data_rows),
            _human_boundary_protocol(public_data_rows, q2b_roadmap_rows),
            _remote_protocol(remote_rows),
            _claim_protocol(q2b_roadmap_rows, reviewer_rows),
            _future_human_audit_protocol(q2b_roadmap_rows),
        ]
        LOGGER.info("无人工标注阶段协议生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建无人工标注阶段协议失败")
        raise


def _read_many(paths: list[str | Path] | None) -> list[dict]:
    """读取多个 JSONL 输入。

    参数:
        paths: 文件路径列表。

    返回:
        合并后的记录列表。
    """
    rows: list[dict] = []
    for path in paths or []:
        try:
            rows.extend(read_records(path))
        except Exception:
            LOGGER.exception("读取无人工标注协议输入失败: %s", path)
            raise
    return rows


def build_no_annotation_protocol_rows_from_paths(
    public_data_validity_paths: list[str | Path],
    q2b_roadmap_path: str | Path,
    reviewer_iteration_path: str | Path | None = None,
    remote_input_request_path: str | Path | None = None,
) -> list[dict]:
    """从文件构建无人工标注阶段协议。

    参数:
        public_data_validity_paths: public_data_validity_audit JSONL 文件列表。
        q2b_roadmap_path: q2b_upgrade_roadmap JSONL 文件。
        reviewer_iteration_path: reviewer_iteration_audit JSONL 文件。
        remote_input_request_path: remote_input_request JSONL 文件。

    返回:
        协议记录列表。
    """
    return build_no_annotation_protocol_rows(
        public_data_rows=_read_many(public_data_validity_paths),
        q2b_roadmap_rows=read_records(q2b_roadmap_path),
        reviewer_iteration_rows=read_records(reviewer_iteration_path) if reviewer_iteration_path else [],
        remote_input_request_rows=read_records(remote_input_request_path) if remote_input_request_path else [],
    )


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 协议记录。

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
        LOGGER.exception("写出无人工标注阶段协议 CSV 失败: %s", path)
        raise


def _summary(rows: list[dict]) -> dict:
    """构建协议摘要。

    参数:
        rows: 协议记录。

    返回:
        摘要记录。
    """
    blocked_annotation_count = sum(1 for row in rows if _clean(row.get("status")) == "blocked_annotation_required")
    blocked_remote_count = sum(1 for row in rows if _clean(row.get("status")) == "blocked_remote_required")
    claim_lockdown_count = sum(1 for row in rows if _clean(row.get("status")) == "claim_lockdown_required")
    high_risk_count = sum(1 for row in rows if _clean(row.get("reviewer_risk_level")) == "high")
    human_required = any(_bool_value(row.get("human_annotation_required_now")) for row in rows)
    return {
        "protocol_item_count": len(rows),
        "blocked_annotation_count": blocked_annotation_count,
        "blocked_remote_count": blocked_remote_count,
        "claim_lockdown_count": claim_lockdown_count,
        "high_reviewer_risk_count": high_risk_count,
        "human_annotation_required_now": human_required,
        "no_annotation_stage_allowed": not human_required and blocked_annotation_count == 0,
        "q2_b_ready_under_no_annotation_strategy": blocked_remote_count == 0 and claim_lockdown_count == 0 and high_risk_count == 0,
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        rows: 协议记录。
        summary: 摘要记录。

    返回:
        无。
    """
    fields = ["protocol_id", "status", "reviewer_risk_level", "allowed_claim", "forbidden_claim", "required_action"]
    lines = [
        "# No Annotation Stage Protocol",
        "",
        "## 使用边界",
        "",
        "该协议用于说明当前阶段不新增人工标注时的可写证据、禁止主张和后续增强边界；它不把公开 gold、silver、proxy 或 LLM 输出写成人工 gold。",
        "",
        "## 汇总",
        "",
        f"- protocol_item_count: {summary['protocol_item_count']}",
        f"- blocked_annotation_count: {summary['blocked_annotation_count']}",
        f"- blocked_remote_count: {summary['blocked_remote_count']}",
        f"- claim_lockdown_count: {summary['claim_lockdown_count']}",
        f"- high_reviewer_risk_count: {summary['high_reviewer_risk_count']}",
        f"- human_annotation_required_now: {summary['human_annotation_required_now']}",
        f"- no_annotation_stage_allowed: {summary['no_annotation_stage_allowed']}",
        f"- q2_b_ready_under_no_annotation_strategy: {summary['q2_b_ready_under_no_annotation_strategy']}",
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
        LOGGER.exception("写出无人工标注阶段协议 Markdown 失败: %s", path)
        raise


def write_no_annotation_protocol_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出无人工标注阶段协议产物。

    参数:
        rows: 协议记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _summary(rows)
    try:
        write_records(rows, directory / "no_annotation_protocol.jsonl")
        write_records([summary], directory / "no_annotation_protocol_summary.jsonl")
        _write_csv(directory / "no_annotation_protocol.csv", rows)
        _write_markdown(directory / "no_annotation_protocol.md", rows, summary)
    except Exception:
        LOGGER.exception("写出无人工标注阶段协议失败: %s", output_dir)
        raise
