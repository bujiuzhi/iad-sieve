"""LLM pair judge 强 baseline 分数生成模块。"""

from __future__ import annotations

import json
import logging
import math
import urllib.error
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from iad_sieve.utils.io_utils import write_records


LOGGER = logging.getLogger(__name__)
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
VALID_LLM_DECISIONS = {"same_work", "same_agenda_not_same_work", "different", "uncertain"}


def _pair_key(source_document_id: object, target_document_id: object) -> tuple[str, str]:
    """构造无向 pair key。

    参数:
        source_document_id: 源文献 ID。
        target_document_id: 目标文献 ID。

    返回:
        排序后的二元组。
    """
    return tuple(sorted((str(source_document_id or ""), str(target_document_id or ""))))


def _normalize_text(value: object) -> str:
    """归一化文本字段。

    参数:
        value: 任意文本、列表或缺失值。

    返回:
        小写、压缩空白后的字符串。
    """
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return " ".join(str(value).lower().split())


def _document_brief(record: dict) -> str:
    """构造 LLM judge 的文献摘要输入。

    参数:
        record: 文献记录。

    返回:
        包含 title、authors、venue、year、abstract 的文本。
    """
    fields = [
        ("title", record.get("title") or record.get("title_normalized")),
        ("authors", record.get("authors") or record.get("authors_normalized")),
        ("venue", record.get("venue") or record.get("venue_normalized")),
        ("year", record.get("year")),
        ("abstract", record.get("abstract") or record.get("abstract_normalized")),
    ]
    return "\n".join(f"{name}: {value}" for name, value in fields if value)


def _similarity(left_text: str, right_text: str) -> float:
    """计算 fallback 文本相似度。

    参数:
        left_text: 左侧文本。
        right_text: 右侧文本。

    返回:
        0 到 1 的相似度。
    """
    if not left_text or not right_text:
        return 0.0
    if left_text == right_text:
        return 1.0
    return SequenceMatcher(None, left_text, right_text).ratio()


def _fallback_judgment(left_document: dict, right_document: dict) -> dict:
    """生成本地 fallback 判定。

    参数:
        left_document: 左侧文献。
        right_document: 右侧文献。

    返回:
        包含 same_work_probability、same_agenda_probability、decision、rationale 的字典。
    """
    left_title = _normalize_text(left_document.get("title_normalized") or left_document.get("title"))
    right_title = _normalize_text(right_document.get("title_normalized") or right_document.get("title"))
    left_abstract = _normalize_text(left_document.get("abstract_normalized") or left_document.get("abstract"))
    right_abstract = _normalize_text(right_document.get("abstract_normalized") or right_document.get("abstract"))
    title_score = _similarity(left_title, right_title)
    abstract_score = _similarity(left_abstract, right_abstract)
    same_work_probability = max(0.0, min(1.0, 0.7 * title_score + 0.3 * abstract_score))
    same_agenda_probability = max(same_work_probability, min(1.0, 0.5 * title_score + 0.5 * abstract_score))
    if same_work_probability >= 0.8:
        decision = "same_work"
    elif same_agenda_probability >= 0.5:
        decision = "same_agenda_not_same_work"
    else:
        decision = "different"
    return {
        "same_work_probability": round(same_work_probability, 6),
        "same_agenda_probability": round(same_agenda_probability, 6),
        "decision": decision,
        "rationale": "fallback lexical judgment; not a real LLM call",
    }


def _judgment_schema() -> dict:
    """返回 OpenAI structured outputs JSON Schema。

    参数:
        无。

    返回:
        JSON Schema 字典。
    """
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "same_work_probability": {"type": "number", "minimum": 0, "maximum": 1},
            "same_agenda_probability": {"type": "number", "minimum": 0, "maximum": 1},
            "decision": {
                "type": "string",
                "enum": ["same_work", "same_agenda_not_same_work", "different", "uncertain"],
            },
            "rationale": {"type": "string"},
        },
        "required": ["same_work_probability", "same_agenda_probability", "decision", "rationale"],
    }


def _extract_response_text(response_payload: dict) -> str:
    """从 Responses API 返回值中提取文本。

    参数:
        response_payload: OpenAI Responses API JSON 响应。

    返回:
        模型输出文本。
    """
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    for item in response_payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                return content["text"]
    raise RuntimeError("OpenAI response 中缺少 output_text")


def _call_openai_responses_api(payload: dict, api_key: str, timeout_seconds: int) -> dict:
    """调用 OpenAI Responses API。

    参数:
        payload: 请求 JSON。
        api_key: OpenAI API key。
        timeout_seconds: 请求超时时间。

    返回:
        响应 JSON。
    """
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI Responses API 请求失败: {exc}") from exc


def _coerce_probability(value: Any) -> float:
    """将模型输出转成 0 到 1 概率。

    参数:
        value: 模型输出值。

    返回:
        0 到 1 的浮点数。
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(number) or math.isinf(number):
        return 0.0
    return max(0.0, min(1.0, number))


def _judge_pair_with_openai(
    left_document: dict,
    right_document: dict,
    model_name: str,
    api_key: str,
    timeout_seconds: int,
) -> dict:
    """使用 OpenAI API 判断一个文献 pair。

    参数:
        left_document: 左侧文献。
        right_document: 右侧文献。
        model_name: OpenAI 模型名。
        api_key: OpenAI API key。
        timeout_seconds: 请求超时时间。

    返回:
        结构化判定字典。
    """
    payload = {
        "model": model_name,
        "input": [
            {
                "role": "developer",
                "content": (
                    "You judge whether two scientific paper records are the same work. "
                    "Return calibrated probabilities. same_work means the same paper/version; "
                    "same_agenda_not_same_work means related topic but different work."
                ),
            },
            {
                "role": "user",
                "content": f"Record A:\n{_document_brief(left_document)}\n\nRecord B:\n{_document_brief(right_document)}",
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "iad_pair_judgment",
                "strict": True,
                "schema": _judgment_schema(),
            }
        },
    }
    response_payload = _call_openai_responses_api(payload, api_key=api_key, timeout_seconds=timeout_seconds)
    raw_text = _extract_response_text(response_payload)
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenAI structured output 不是合法 JSON: {raw_text[:200]}") from exc
    return {
        "same_work_probability": round(_coerce_probability(parsed.get("same_work_probability")), 6),
        "same_agenda_probability": round(_coerce_probability(parsed.get("same_agenda_probability")), 6),
        "decision": str(parsed.get("decision") or "uncertain"),
        "rationale": str(parsed.get("rationale") or ""),
    }


def _local_judge_prompt(left_document: dict, right_document: dict) -> str:
    """构造本地 Transformers LLM 的 pair judge prompt。

    参数:
        left_document: 左侧文献。
        right_document: 右侧文献。

    返回:
        要求输出 JSON 的 prompt。
    """
    return (
        "Return exactly one JSON object. Do not use markdown. Do not explain before the JSON.\n"
        "Required keys: same_work_probability, same_agenda_probability, decision, rationale.\n"
        "The decision value must be exactly one of: same_work, same_agenda_not_same_work, different, uncertain.\n"
        "Task: judge whether two scientific paper records describe the same work.\n"
        "same_work means the same paper/version. same_agenda_not_same_work means related topic but different paper.\n\n"
        f"Record A:\n{_document_brief(left_document)}\n\n"
        f"Record B:\n{_document_brief(right_document)}\n\n"
        "JSON object only:"
    )


def _extract_json_object(raw_text: str) -> dict:
    """从模型文本中提取 JSON 对象。

    参数:
        raw_text: 模型输出文本。

    返回:
        解析后的 JSON 对象。
    """
    text = raw_text.strip()
    if "{" not in text:
        raise RuntimeError(f"本地 LLM 输出缺少 JSON 对象: {text[:200]}")
    decoder = json.JSONDecoder()
    candidates: list[dict] = []
    for start_index, character in enumerate(text):
        if character != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[start_index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            candidates.append(parsed)
    if not candidates:
        raise RuntimeError(f"本地 LLM 输出 JSON 无法解析: {text[:200]}")
    required_keys = {"same_work_probability", "same_agenda_probability", "decision", "rationale"}
    for candidate in candidates:
        if required_keys.issubset(candidate):
            return candidate
    return candidates[0]


def _normalize_judgment(parsed: dict) -> dict:
    """规范化 pair judge 结构化判定。

    参数:
        parsed: 模型输出 JSON 对象。

    返回:
        含概率、决策和理由的判定字典。
    """
    same_work_probability = round(_coerce_probability(parsed.get("same_work_probability")), 6)
    same_agenda_probability = round(_coerce_probability(parsed.get("same_agenda_probability")), 6)
    decision = str(parsed.get("decision") or "uncertain")
    if decision not in VALID_LLM_DECISIONS:
        if same_work_probability >= 0.8:
            decision = "same_work"
        elif same_agenda_probability >= 0.5:
            decision = "same_agenda_not_same_work"
        else:
            decision = "different"
    return {
        "same_work_probability": same_work_probability,
        "same_agenda_probability": same_agenda_probability,
        "decision": decision,
        "rationale": str(parsed.get("rationale") or ""),
    }


def _judge_pairs_with_transformers(
    pair_payloads: list[tuple[dict, dict, str, str]],
    model_name: str,
    max_new_tokens: int,
    batch_size: int = 4,
) -> list[dict]:
    """使用本地 Transformers 模型批量判断文献 pair。

    参数:
        pair_payloads: 文献 pair 输入列表。
        model_name: Hugging Face 模型名或本地模型目录。
        max_new_tokens: 每个 pair 最大生成 token 数。
        batch_size: Transformers pipeline 批处理大小。

    返回:
        结构化判定列表。
    """
    try:
        import torch
        from transformers import pipeline
    except ImportError as exc:
        raise RuntimeError("transformers 或 torch 未安装，无法运行本地 LLM judge") from exc

    device = 0 if torch.cuda.is_available() else -1
    try:
        generator = pipeline(
            "text-generation",
            model=model_name,
            device=device,
            torch_dtype="auto",
            trust_remote_code=True,
        )
    except Exception as exc:
        raise RuntimeError(f"加载本地 Transformers LLM 失败: {model_name}") from exc
    tokenizer = getattr(generator, "tokenizer", None)
    if tokenizer is not None:
        try:
            tokenizer.padding_side = "left"
            if getattr(tokenizer, "pad_token_id", None) is None and getattr(tokenizer, "eos_token", None) is not None:
                tokenizer.pad_token = tokenizer.eos_token
        except Exception:
            LOGGER.warning("设置本地 Transformers LLM tokenizer 左填充失败，继续执行。")

    judgments: list[dict] = []
    safe_batch_size = max(1, int(batch_size or 1))
    for start_index in range(0, len(pair_payloads), safe_batch_size):
        batch_payloads = pair_payloads[start_index : start_index + safe_batch_size]
        prompts = [_local_judge_prompt(left_document, right_document) for left_document, right_document, _, _ in batch_payloads]
        try:
            outputs = generator(
                prompts,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                return_full_text=False,
                batch_size=safe_batch_size,
            )
        except Exception as exc:
            raise RuntimeError("本地 Transformers LLM 生成失败") from exc
        for output in outputs:
            if isinstance(output, list):
                item = output[0] if output else {}
            else:
                item = output
            raw_text = str(item.get("generated_text", "") if isinstance(item, dict) else "")
            judgments.append(_normalize_judgment(_extract_json_object(raw_text)))
    return judgments


def run_llm_judge_baseline(
    documents: list[dict],
    pairs: list[dict],
    system_name: str,
    model_name: str,
    score_field: str = "same_work_probability",
    api_backend: str = "auto",
    api_key: str | None = None,
    timeout_seconds: int = 30,
    max_new_tokens: int = 80,
    batch_size: int = 4,
) -> tuple[list[dict], dict]:
    """运行 LLM pair judge baseline。

    参数:
        documents: IAD-Bench 或 eval_documents 文献记录。
        pairs: IAD-Bench 或 eval_pairs 文献对记录。
        system_name: baseline 名称，如 gpt_pair_judge。
        model_name: LLM 模型名，如 gpt-5.5。
        score_field: 输出 same_work 分数字段名。
        api_backend: `auto`、`openai`、`transformers` 或 `fallback`。
        api_key: 可选 OpenAI API key。
        timeout_seconds: 单次 API 请求超时时间。
        max_new_tokens: 本地 Transformers LLM 每个 pair 最大生成 token 数。
        batch_size: 本地 Transformers LLM pipeline 批处理大小。

    返回:
        baseline 分数记录列表和执行摘要。
    """
    document_lookup = {str(record.get("document_id", "")): record for record in documents}
    pair_payloads: list[tuple[dict, dict, str, str]] = []
    missing_pair_count = 0
    seen_pairs: set[tuple[str, str]] = set()
    for pair in pairs:
        source_document_id = str(pair.get("source_document_id", ""))
        target_document_id = str(pair.get("target_document_id", ""))
        key = _pair_key(source_document_id, target_document_id)
        if key in seen_pairs:
            LOGGER.warning("LLM judge baseline 跳过重复 pair: %s", key)
            continue
        seen_pairs.add(key)
        left_document = document_lookup.get(source_document_id)
        right_document = document_lookup.get(target_document_id)
        if left_document is None or right_document is None:
            missing_pair_count += 1
            LOGGER.warning("LLM judge baseline pair 引用缺失文献: %s", pair)
            continue
        pair_payloads.append((left_document, right_document, source_document_id, target_document_id))

    execution_mode = "fallback"
    fallback_reason = ""
    use_openai = api_backend in {"auto", "openai"} and bool(api_key)
    judgments: list[dict] = []
    if api_backend == "transformers":
        judgments = _judge_pairs_with_transformers(pair_payloads, model_name=model_name, max_new_tokens=max_new_tokens, batch_size=batch_size)
        execution_mode = "actual_model"
    elif use_openai:
        try:
            judgments = [
                _judge_pair_with_openai(
                    left_document,
                    right_document,
                    model_name=model_name,
                    api_key=str(api_key),
                    timeout_seconds=timeout_seconds,
                )
                for left_document, right_document, _, _ in pair_payloads
            ]
            execution_mode = "api_model"
        except RuntimeError as exc:
            LOGGER.warning("LLM judge baseline 回退 fallback: %s", exc)
            fallback_reason = str(exc)
            judgments = [_fallback_judgment(left_document, right_document) for left_document, right_document, _, _ in pair_payloads]
    else:
        if api_backend in {"auto", "openai"}:
            fallback_reason = "missing_api_key"
        judgments = [_fallback_judgment(left_document, right_document) for left_document, right_document, _, _ in pair_payloads]

    rows: list[dict] = []
    for (left_document, right_document, source_document_id, target_document_id), judgment in zip(pair_payloads, judgments, strict=True):
        same_work_probability = round(_coerce_probability(judgment.get("same_work_probability")), 6)
        row = {
            "source_document_id": source_document_id,
            "target_document_id": target_document_id,
            "system": system_name,
            "baseline_family": "llm_judge",
            "execution_mode": execution_mode,
            "model_name": model_name,
            "api_backend": api_backend,
            "model_backend": "transformers" if execution_mode == "actual_model" and api_backend == "transformers" else api_backend,
            "same_work_probability": same_work_probability,
            "same_agenda_probability": round(_coerce_probability(judgment.get("same_agenda_probability")), 6),
            "decision": str(judgment.get("decision") or "uncertain"),
            "rationale": str(judgment.get("rationale") or ""),
        }
        if score_field != "same_work_probability":
            row[score_field] = same_work_probability
        rows.append(row)

    summary = {
        "system": system_name,
        "baseline_family": "llm_judge",
        "execution_mode": execution_mode,
        "requested_model_name": model_name,
        "resolved_model_name": model_name,
        "api_backend": api_backend,
        "model_backend": "transformers" if execution_mode == "actual_model" and api_backend == "transformers" else api_backend,
        "score_field": score_field,
        "document_count": len(documents),
        "pair_count": len(rows),
        "missing_pair_count": missing_pair_count,
        "max_new_tokens": max_new_tokens if api_backend == "transformers" else "",
        "batch_size": max(1, int(batch_size or 1)) if api_backend == "transformers" else "",
    }
    if fallback_reason:
        summary["fallback_reason"] = fallback_reason
    LOGGER.info(
        "LLM judge baseline 完成: system=%s execution_mode=%s pairs=%s missing=%s",
        system_name,
        execution_mode,
        len(rows),
        missing_pair_count,
    )
    return rows, summary


def write_llm_judge_scores(rows: list[dict], summary: dict, output_path: str | Path, summary_path: str | Path) -> None:
    """写出 LLM judge baseline 分数和执行摘要。

    参数:
        rows: baseline 分数记录。
        summary: baseline 执行摘要。
        output_path: 分数 JSONL 输出路径。
        summary_path: 摘要 JSONL 输出路径。

    返回:
        无。
    """
    write_records(rows, output_path)
    write_records([summary], summary_path)
