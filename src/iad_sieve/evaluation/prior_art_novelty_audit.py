"""相关工作新颖性审计模块。"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from iad_sieve.utils.io_utils import ensure_directory, read_records, write_records


LOGGER = logging.getLogger(__name__)
PREFERRED_FIELDS = [
    "prior_art_family_id",
    "prior_art_family",
    "priority",
    "status",
    "overlap_risk_level",
    "duplicate_work_found",
    "stronger_work_risk",
    "must_compare_against",
    "external_sources",
    "current_evidence",
    "reviewer_attack",
    "required_action",
    "surviving_position",
    "paper_claim_boundary",
    "snapshot_date",
]


def _clean(value: object) -> str:
    """清理字符串。

    参数:
        value: 原始值。

    返回:
        去除首尾空白后的字符串。
    """
    return str(value or "").strip()


def _int_value(value: object) -> int:
    """解析整数。

    参数:
        value: 原始值。

    返回:
        解析失败时返回 0。
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        LOGGER.warning("相关工作新颖性审计整数字段无法解析: %s", value)
        return 0


def _index_by_field(rows: list[dict], field_name: str) -> dict[str, dict]:
    """按字段建立索引。

    参数:
        rows: 输入记录。
        field_name: 字段名。

    返回:
        字段值到记录的映射。
    """
    return {_clean(row.get(field_name)): row for row in rows if _clean(row.get(field_name))}


def _status(index: dict[str, dict], key: str) -> str:
    """读取索引中的状态。

    参数:
        index: ID 到记录的映射。
        key: 目标 ID。

    返回:
        状态；缺失时返回 missing。
    """
    return _clean(index.get(key, {}).get("status")) or "missing"


def _row(
    prior_art_family_id: str,
    prior_art_family: str,
    priority: int,
    status: str,
    overlap_risk_level: str,
    duplicate_work_found: bool,
    stronger_work_risk: str,
    must_compare_against: list[str],
    external_sources: list[str],
    current_evidence: str,
    reviewer_attack: str,
    required_action: str,
    surviving_position: str,
    paper_claim_boundary: str,
    snapshot_date: str,
) -> dict:
    """构建相关工作新颖性审计记录。

    参数:
        prior_art_family_id: 相关工作家族 ID。
        prior_art_family: 相关工作家族名称。
        priority: 优先级。
        status: ready、conditional 或 blocked。
        overlap_risk_level: 重叠风险等级。
        duplicate_work_found: 当前核查范围内是否发现直接重复工作。
        stronger_work_risk: 是否存在更强相邻工作风险。
        must_compare_against: 必须比较的模型或工作。
        external_sources: 外部来源 URL。
        current_evidence: 当前证据。
        reviewer_attack: 审稿人攻击点。
        required_action: 下一步动作。
        surviving_position: 可保留定位。
        paper_claim_boundary: 论文表述边界。
        snapshot_date: 检索快照日期。

    返回:
        审计记录。
    """
    return {
        "prior_art_family_id": prior_art_family_id,
        "prior_art_family": prior_art_family,
        "priority": priority,
        "status": status,
        "overlap_risk_level": overlap_risk_level,
        "duplicate_work_found": duplicate_work_found,
        "stronger_work_risk": stronger_work_risk,
        "must_compare_against": list(dict.fromkeys(must_compare_against)),
        "external_sources": list(dict.fromkeys(external_sources)),
        "current_evidence": current_evidence,
        "reviewer_attack": reviewer_attack,
        "required_action": required_action,
        "surviving_position": surviving_position,
        "paper_claim_boundary": paper_claim_boundary,
        "snapshot_date": snapshot_date,
    }


def _scientific_representation_status(risk_status: str, encoder_status: str) -> str:
    """合成科学文献表示相关工作的审计状态。

    参数:
        risk_status: 风险分解贡献状态。
        encoder_status: encoder 与 provenance 有效性状态。

    返回:
        审计状态。
    """
    if risk_status == "ready" and encoder_status == "ready":
        return "ready"
    if risk_status == "ready" and encoder_status == "conditional":
        return "conditional"
    return "blocked"


def _plm_entity_matching_status(strong_status: str, missing_plm_required_count: int, ready_plm_model_count: int) -> str:
    """合成 PLM 实体匹配相关工作的审计状态。

    参数:
        strong_status: 强模型优势控制状态。
        missing_plm_required_count: advanced_model_evidence 中缺失的 PLM 强模型数量。
        ready_plm_model_count: advanced_model_evidence 中已 ready 的 PLM 强模型数量。

    返回:
        审计状态。
    """
    if missing_plm_required_count > 0 or ready_plm_model_count == 0:
        return "blocked"
    if strong_status in {"ready", "conditional"}:
        return "ready"
    return "blocked"


def _llm_entity_matching_status(ready_llm_model_count: int, missing_required_count: int) -> str:
    """合成 LLM 实体匹配相关工作的审计状态。

    参数:
        ready_llm_model_count: 已 ready 的 LLM judge 模型数量。
        missing_required_count: advanced_model_evidence 缺失强模型数量。

    返回:
        审计状态。
    """
    if ready_llm_model_count > 0 and missing_required_count == 0:
        return "ready"
    return "blocked"


def _open_bibliographic_status(no_annotation_status: str) -> str:
    """合成开放书目图谱相关工作的审计状态。

    参数:
        no_annotation_status: 无人工标注主张边界状态。

    返回:
        审计状态。
    """
    if no_annotation_status == "ready":
        return "conditional"
    return "blocked"


def _iad_formulation_status(risk_status: str, no_annotation_status: str) -> str:
    """合成 IAD 问题定义相关工作的审计状态。

    参数:
        risk_status: 风险分解贡献状态。
        no_annotation_status: 无人工标注主张边界状态。

    返回:
        审计状态。
    """
    if risk_status == "ready" and no_annotation_status == "ready":
        return "ready"
    if risk_status in {"ready", "conditional"}:
        return "conditional"
    return "blocked"


def _ready_sensitive_text(status: str, ready_text: str, pending_text: str) -> str:
    """按状态选择 ready 或待完成文本。

    参数:
        status: 当前相关工作审计状态。
        ready_text: ready 状态下使用的文本。
        pending_text: 非 ready 状态下使用的文本。

    返回:
        与审计状态一致的文本。
    """
    return ready_text if status == "ready" else pending_text


def build_prior_art_novelty_rows(
    novelty_rows: list[dict],
    advanced_model_summary: dict,
    snapshot_date: str,
) -> list[dict]:
    """构建相关工作新颖性审计记录。

    参数:
        novelty_rows: novelty_falsification_matrix 记录。
        advanced_model_summary: advanced_model_evidence_summary 记录。
        snapshot_date: 外部相关工作检索快照日期。

    返回:
        相关工作新颖性审计记录。
    """
    try:
        novelty_by_id = _index_by_field(novelty_rows, "contribution_id")
        risk_status = _status(novelty_by_id, "risk_decomposition_vs_single_space")
        strong_status = _status(novelty_by_id, "strong_model_superiority_control")
        encoder_status = _status(novelty_by_id, "encoder_and_provenance_validity")
        no_annotation_status = _status(novelty_by_id, "no_annotation_claim_boundary")
        missing_required_count = _int_value(advanced_model_summary.get("missing_required_count"))
        missing_plm_required_count = _int_value(advanced_model_summary.get("missing_plm_required_count", missing_required_count))
        missing_llm_required_count = _int_value(advanced_model_summary.get("missing_llm_required_count", missing_required_count))
        ready_plm_model_count = _int_value(advanced_model_summary.get("ready_plm_model_count"))
        ready_api_model_count = _int_value(advanced_model_summary.get("ready_api_model_count"))
        ready_llm_model_count = _int_value(advanced_model_summary.get("ready_llm_model_count", ready_api_model_count))

        scientific_status = _scientific_representation_status(risk_status, encoder_status)
        plm_status = _plm_entity_matching_status(strong_status, missing_plm_required_count, ready_plm_model_count)
        llm_status = _llm_entity_matching_status(ready_llm_model_count, missing_llm_required_count)
        open_graph_status = _open_bibliographic_status(no_annotation_status)
        iad_formulation_status = _iad_formulation_status(risk_status, no_annotation_status)

        rows = [
            _row(
                prior_art_family_id="scientific_document_representation",
                prior_art_family="SPECTER、SciNCL、SciRepEval/SPECTER2 等科学文献表示模型",
                priority=0,
                status=scientific_status,
                overlap_risk_level="high",
                duplicate_work_found=False,
                stronger_work_risk="high",
                must_compare_against=[
                    "SciNCL",
                    "SPECTER2",
                    "SPECTER2 proximity adapter",
                    "single-space cosine false-merge baseline",
                    "Topic Is Not Agenda embedding audit",
                ],
                external_sources=[
                    "https://arxiv.org/abs/2004.07180",
                    "https://arxiv.org/abs/2202.06671",
                    "https://arxiv.org/abs/2211.13308",
                    "https://arxiv.org/abs/2605.07158",
                    "https://huggingface.co/allenai/specter2_base",
                    "https://huggingface.co/malteos/scincl",
                ],
                current_evidence=f"risk_status={risk_status}; encoder_status={encoder_status}",
                reviewer_attack="已有科学文献 embedding 与 agenda audit 已能分析相似论文，IAD-Risk 可能只是换了阈值或特征组合。",
                required_action=_ready_sensitive_text(
                    scientific_status,
                    "在论文中保留 SPECTER2、SciNCL 与 Topic-Is-Not-Agenda 类失败边界同口径比较，并明确 IAD-Risk 的风险控制定位。",
                    "在 hard-negative false merge rate 上补齐 SPECTER2、SciNCL 与 Topic-Is-Not-Agenda 类失败边界同口径比较，并通过 encoder/provenance 控制。",
                ),
                surviving_position="可主张 IAD-Risk 研究的是相似议题下的误合并风险，而不是通用文献相似度学习。",
                paper_claim_boundary=_ready_sensitive_text(
                    scientific_status,
                    "可写成相似议题误合并风险控制补充；仍不能写成全面优于 SPECTER2/SciNCL 或通用 SOTA。",
                    "未通过前不能写成优于 SPECTER2/SciNCL，只能写成相邻工作的风险控制补充。",
                ),
                snapshot_date=snapshot_date,
            ),
            _row(
                prior_art_family_id="plm_entity_matching",
                prior_art_family="Ditto、RoBERTa、DistilBERT、DeepMatcher 风格的 PLM pair classifier",
                priority=1,
                status=plm_status,
                overlap_risk_level="high",
                duplicate_work_found=False,
                stronger_work_risk="high",
                must_compare_against=["Ditto-style pair classifier", "RoBERTa pair classifier", "DistilBERT MRPC classifier"],
                external_sources=[
                    "https://arxiv.org/abs/2004.00584",
                    "https://github.com/megagonlabs/ditto",
                    "https://arxiv.org/abs/2106.08455",
                ],
                current_evidence=(
                    f"strong_status={strong_status}; "
                    f"missing_plm_required_count={missing_plm_required_count}; "
                    f"ready_plm_model_count={ready_plm_model_count}"
                ),
                reviewer_attack="通用实体匹配模型已经覆盖 pair classification，IAD-Risk 的 baseline 可能偏弱。",
                required_action=_ready_sensitive_text(
                    plm_status,
                    "保留 PLM pair classifier、阈值搜索和 bootstrap 效应量，论文中限定为风险预算下的受控比较。",
                    "补齐 PLM pair classifier、阈值搜索和 bootstrap 效应量；未完成前不得写强模型优势。",
                ),
                surviving_position="可主张 IAD-Risk 把身份匹配与议题 hard negative 风险拆开，而不是替代通用 EM。",
                paper_claim_boundary=_ready_sensitive_text(
                    plm_status,
                    "可写成已覆盖 PLM entity matching 相关工作边界；仍不能写全面优于所有 EM 或 SOTA。",
                    "未通过前不能写成全面优于实体匹配模型，也不能写 SOTA。",
                ),
                snapshot_date=snapshot_date,
            ),
            _row(
                prior_art_family_id="llm_entity_matching",
                prior_art_family="GPT-4/LLM entity matching、AnyMatch 与结构化推理 EM",
                priority=2,
                status=llm_status,
                overlap_risk_level="high",
                duplicate_work_found=False,
                stronger_work_risk="high",
                must_compare_against=[
                    "LLM pair judge",
                    "few-shot LLM EM",
                    "AnyMatch or equivalent efficient zero-shot EM",
                    "ComEM interaction-aware LLM EM",
                    "fine-tuned LLM entity matching",
                ],
                external_sources=[
                    "https://arxiv.org/abs/2310.11244",
                    "https://arxiv.org/abs/2405.16884",
                    "https://arxiv.org/abs/2409.04073",
                    "https://arxiv.org/abs/2409.08185",
                ],
                current_evidence=(
                    f"ready_api_model_count={ready_api_model_count}; "
                    f"ready_llm_model_count={ready_llm_model_count}; "
                    f"missing_llm_required_count={missing_llm_required_count}"
                ),
                reviewer_attack="LLM zero-shot/few-shot EM 可能在无需训练的情况下达到同等或更强效果。",
                required_action="补齐 LLM pair judge 对比，报告成本、吞吐、解释一致性和 hard-negative false merge。",
                surviving_position="可主张 IAD-Risk 提供可复现、可校准的风险模型；LLM 可作为强外部 judge。",
                paper_claim_boundary="未通过前不能写成比 LLM 更先进，只能写 LLM 对比仍在执行门槛内。",
                snapshot_date=snapshot_date,
            ),
            _row(
                prior_art_family_id="open_bibliographic_graph",
                prior_art_family="OpenAlex、OpenCitations、Crossref 等开放书目知识图谱与元数据质量研究",
                priority=3,
                status=open_graph_status,
                overlap_risk_level="medium",
                duplicate_work_found=False,
                stronger_work_risk="medium",
                must_compare_against=[
                    "OpenAlex work id policy",
                    "OpenAlex metadata quality limitation",
                    "DBLPLink / DBLPLink 2.0 scholarly KG entity linking",
                    "silver hard-negative provenance audit",
                ],
                external_sources=[
                    "https://arxiv.org/abs/2205.01833",
                    "https://arxiv.org/abs/2309.07545",
                    "https://arxiv.org/abs/2507.22811",
                    "https://developers.openalex.org/",
                    "https://arxiv.org/abs/2512.16434",
                ],
                current_evidence=f"no_annotation_status={no_annotation_status}",
                reviewer_attack="OpenAlex hard negative 可能只是元数据噪声，不能等价于人工 gold。",
                required_action="继续把 OpenAlex/OpenCitations 标为 silver，并保留 public_data_validity_audit 与 no_annotation_protocol 边界。",
                surviving_position="可主张公开图谱适合构造可复现压力测试，但不替代人工 gold。",
                paper_claim_boundary="不能把 silver/proxy 写成人工 gold；人工 audit 仍作为后续增强。",
                snapshot_date=snapshot_date,
            ),
            _row(
                prior_art_family_id="iad_problem_formulation",
                prior_art_family="同议题但非同一文献的误合并风险问题定义",
                priority=4,
                status=iad_formulation_status,
                overlap_risk_level="medium",
                duplicate_work_found=False,
                stronger_work_risk="medium",
                must_compare_against=["same_work", "same_agenda", "agenda_non_identity", "false_merge_risk"],
                external_sources=[
                    "https://arxiv.org/abs/2004.00584",
                    "https://arxiv.org/abs/2211.13308",
                    "https://arxiv.org/abs/2205.01833",
                ],
                current_evidence=f"risk_status={risk_status}; no_annotation_status={no_annotation_status}",
                reviewer_attack="问题定义可能只是把已有 EM 和文献表示任务重新命名。",
                required_action="在论文贡献中明确 IAD-Risk 是相邻任务交叉处的风险建模，并用 hard-negative 证据约束。",
                surviving_position="当前可保留的创新定位是身份-议题解耦的误合并风险学习框架。",
                paper_claim_boundary="不能写成没有相似工作；只能写成已知相关工作未直接覆盖该风险证据链。",
                snapshot_date=snapshot_date,
            ),
        ]
        LOGGER.info("相关工作新颖性审计生成完成: rows=%s", len(rows))
        return rows
    except Exception:
        LOGGER.exception("构建相关工作新颖性审计失败")
        raise


def _input_exists(path: str | Path) -> bool:
    """判断输入文件是否存在。

    参数:
        path: 输入路径。

    返回:
        文件存在返回 True。
    """
    if Path(path).exists():
        return True
    LOGGER.warning("相关工作新颖性审计输入缺失，跳过: %s", path)
    return False


def _read_many(paths: list[str | Path]) -> list[dict]:
    """读取多个 JSONL 文件。

    参数:
        paths: JSONL 路径列表。

    返回:
        合并后的记录。
    """
    rows: list[dict] = []
    for path in paths:
        if _input_exists(path):
            rows.extend(read_records(path))
    return rows


def _first(path: str | Path | None) -> dict:
    """读取 JSONL 首条记录。

    参数:
        path: JSONL 文件路径。

    返回:
        首条记录；路径为空或缺失时返回空字典。
    """
    if not path or not _input_exists(path):
        return {}
    rows = read_records(path)
    return rows[0] if rows else {}


def build_prior_art_novelty_rows_from_paths(
    novelty_matrix_paths: list[str | Path],
    advanced_model_summary_path: str | Path | None,
    snapshot_date: str,
) -> list[dict]:
    """从文件构建相关工作新颖性审计记录。

    参数:
        novelty_matrix_paths: novelty_falsification_matrix JSONL 文件。
        advanced_model_summary_path: advanced_model_evidence_summary JSONL 文件。
        snapshot_date: 外部相关工作检索快照日期。

    返回:
        相关工作新颖性审计记录。
    """
    return build_prior_art_novelty_rows(
        novelty_rows=_read_many(novelty_matrix_paths),
        advanced_model_summary=_first(advanced_model_summary_path),
        snapshot_date=snapshot_date,
    )


def _serialize_cell(value: object) -> object:
    """序列化单元格。

    参数:
        value: 原始值。

    返回:
        CSV/Markdown 可写入值。
    """
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    """写出 CSV 文件。

    参数:
        path: 输出路径。
        rows: 审计记录。

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
            for row in rows:
                writer.writerow({field: _serialize_cell(row.get(field, "")) for field in fields})
    except OSError:
        LOGGER.exception("写出相关工作新颖性审计 CSV 失败: %s", path)
        raise


def _build_summary(rows: list[dict]) -> dict:
    """构建相关工作新颖性审计摘要。

    参数:
        rows: 审计记录。

    返回:
        摘要记录。
    """
    ready_rows = [row for row in rows if row.get("status") == "ready"]
    conditional_rows = [row for row in rows if row.get("status") == "conditional"]
    blocked_rows = [row for row in rows if row.get("status") == "blocked"]
    unresolved_high_risk_rows = [
        row for row in rows if row.get("overlap_risk_level") == "high" and row.get("status") != "ready"
    ]
    duplicate_work_found = any(bool(row.get("duplicate_work_found")) for row in rows)
    highest_blocker_pool = blocked_rows or unresolved_high_risk_rows
    highest_blocker = sorted(highest_blocker_pool, key=lambda row: int(row.get("priority", 99)))[0] if highest_blocker_pool else {}
    return {
        "prior_art_family_count": len(rows),
        "ready_prior_art_family_count": len(ready_rows),
        "conditional_prior_art_family_count": len(conditional_rows),
        "blocked_prior_art_family_count": len(blocked_rows),
        "high_overlap_family_count": sum(1 for row in rows if row.get("overlap_risk_level") == "high"),
        "unresolved_high_risk_family_count": len(unresolved_high_risk_rows),
        "duplicate_work_found": duplicate_work_found,
        "highest_priority_blocker": highest_blocker.get("prior_art_family_id", ""),
        "highest_priority_action": highest_blocker.get("required_action", ""),
        "q2b_prior_art_position_defensible": not duplicate_work_found and not unresolved_high_risk_rows,
    }


def _write_markdown(path: Path, rows: list[dict], summary: dict) -> None:
    """写出 Markdown 报告。

    参数:
        path: 输出路径。
        rows: 审计记录。
        summary: 摘要记录。

    返回:
        无。
    """
    fields = [
        "prior_art_family_id",
        "status",
        "overlap_risk_level",
        "must_compare_against",
        "reviewer_attack",
        "paper_claim_boundary",
    ]
    lines = [
        "# Prior Art Novelty Audit",
        "",
        "## 使用边界",
        "",
        "该审计把外部相关工作转成可执行的新颖性门槛；它只能说明当前检索快照下未发现直接重复工作，不能写成全网不存在相似工作。",
        "",
        "## 汇总",
        "",
        f"- prior_art_family_count: {summary['prior_art_family_count']}",
        f"- blocked_prior_art_family_count: {summary['blocked_prior_art_family_count']}",
        f"- unresolved_high_risk_family_count: {summary['unresolved_high_risk_family_count']}",
        f"- duplicate_work_found: {str(summary['duplicate_work_found']).lower()}",
        f"- highest_priority_blocker: {summary['highest_priority_blocker']}",
        f"- q2b_prior_art_position_defensible: {str(summary['q2b_prior_art_position_defensible']).lower()}",
        "",
        "## 明细",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    for row in rows:
        values = [str(_serialize_cell(row.get(field, ""))).replace("\n", " ").replace("|", "/") for field in fields]
        lines.append("| " + " | ".join(values) + " |")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        LOGGER.exception("写出相关工作新颖性审计 Markdown 失败: %s", path)
        raise


def write_prior_art_novelty_outputs(rows: list[dict], output_dir: str | Path) -> None:
    """写出相关工作新颖性审计产物。

    参数:
        rows: 审计记录。
        output_dir: 输出目录。

    返回:
        无。
    """
    directory = ensure_directory(output_dir)
    summary = _build_summary(rows)
    try:
        write_records(rows, directory / "prior_art_novelty_audit.jsonl")
        write_records([summary], directory / "prior_art_novelty_audit_summary.jsonl")
        _write_csv(directory / "prior_art_novelty_audit.csv", rows)
        _write_markdown(directory / "prior_art_novelty_audit.md", rows, summary)
    except Exception:
        LOGGER.exception("写出相关工作新颖性审计失败: %s", output_dir)
        raise
