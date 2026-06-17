"""OpenAlex API 数据采集模块。"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from iad_sieve.utils.io_utils import write_records


LOGGER = logging.getLogger(__name__)
OPENALEX_WORKS_ENDPOINT = "https://api.openalex.org/works"
HttpGet = Callable[[str, int], dict]


def _build_openalex_url(
    endpoint: str,
    cursor: str,
    filter_expression: str | None = None,
    select_fields: str | None = None,
    per_page: int = 200,
    sample_size: int | None = None,
    seed: int | None = None,
    mailto: str | None = None,
    api_key: str | None = None,
) -> str:
    """构造 OpenAlex Works API URL。

    参数:
        endpoint: API endpoint。
        cursor: OpenAlex cursor 值。
        filter_expression: OpenAlex filter 表达式。
        select_fields: 逗号分隔字段。
        per_page: 每页记录数。
        sample_size: 可选 API sample 参数。
        seed: 可选 sample seed。
        mailto: 可选 polite pool 邮箱。
        api_key: 可选 OpenAlex API key。

    返回:
        完整 URL。
    """
    params: dict[str, str | int] = {
        "per-page": per_page,
        "cursor": cursor,
    }
    if filter_expression:
        params["filter"] = filter_expression
    if select_fields:
        params["select"] = select_fields
    if sample_size is not None:
        params["sample"] = sample_size
    if sample_size is not None and seed is not None:
        params["seed"] = seed
    if mailto:
        params["mailto"] = mailto
    if api_key:
        params["api_key"] = api_key
    return f"{endpoint}?{urlencode(params)}"


def _default_http_get(url: str, timeout: int) -> dict:
    """读取 OpenAlex API JSON 响应。

    参数:
        url: 请求 URL。
        timeout: 超时时间，单位秒。

    返回:
        JSON 响应字典。
    """
    request = Request(url, headers={"User-Agent": "iad-sieve-openalex-ingestion/1.0"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = response.read().decode("utf-8")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError("OpenAlex API 响应不是 JSON object")
    return parsed


def _bounded_per_page(per_page: int) -> int:
    """限制 OpenAlex per-page 范围。

    参数:
        per_page: 用户输入页大小。

    返回:
        1 到 200 之间的页大小。
    """
    if per_page < 1:
        raise ValueError("per_page 必须大于等于 1")
    return min(per_page, 100)


def fetch_openalex_works(
    filter_expression: str | None = None,
    select_fields: str | None = None,
    per_page: int = 200,
    max_records: int = 1000,
    seed: int | None = None,
    sample_size: int | None = None,
    mailto: str | None = None,
    api_key: str | None = None,
    endpoint: str = OPENALEX_WORKS_ENDPOINT,
    timeout: int = 30,
    http_get: HttpGet | None = None,
) -> tuple[list[dict], dict]:
    """从 OpenAlex Works API 拉取记录。

    参数:
        filter_expression: OpenAlex filter 表达式。
        select_fields: 逗号分隔字段。
        per_page: 每页记录数，OpenAlex 最大为 200。
        max_records: 最多拉取记录数。
        seed: 可选随机种子。
        sample_size: 可选 API sample 参数。
        mailto: 可选 polite pool 邮箱。
        api_key: 可选 OpenAlex API key。
        endpoint: API endpoint。
        timeout: HTTP 超时时间。
        http_get: 可注入 HTTP getter，便于测试。

    返回:
        Works 记录和 ingestion summary。
    """
    if max_records < 1:
        raise ValueError("max_records 必须大于等于 1")
    resolved_per_page = _bounded_per_page(per_page)
    getter = http_get or _default_http_get
    cursor = "*"
    records: list[dict] = []
    page_count = 0
    status = "completed"
    while len(records) < max_records:
        url = _build_openalex_url(
            endpoint=endpoint,
            cursor=cursor,
            filter_expression=filter_expression,
            select_fields=select_fields,
            per_page=min(resolved_per_page, max_records - len(records)),
            sample_size=sample_size,
            seed=seed,
            mailto=mailto,
            api_key=api_key,
        )
        payload = getter(url, timeout)
        page_count += 1
        raw_results = payload.get("results", [])
        if not isinstance(raw_results, list):
            raise ValueError("OpenAlex API 响应 results 不是列表")
        page_records = [dict(record) for record in raw_results if isinstance(record, dict)]
        records.extend(page_records[: max_records - len(records)])
        next_cursor = payload.get("meta", {}).get("next_cursor") if isinstance(payload.get("meta"), dict) else None
        if not page_records:
            status = "empty_page"
            break
        if not next_cursor or next_cursor == cursor:
            break
        cursor = str(next_cursor)
    summary = {
        "source": "openalex_api",
        "endpoint": endpoint,
        "filter": filter_expression or "",
        "select": select_fields or "",
        "per_page": resolved_per_page,
        "requested_max_records": max_records,
        "fetched_record_count": len(records),
        "cursor_page_count": page_count,
        "sample_size": sample_size or "",
        "sample_seed": seed if sample_size is not None and seed is not None else "",
        "mailto_used": bool(mailto),
        "api_key_used": bool(api_key),
        "status": status,
        "fetched_at_utc": datetime.now(UTC).isoformat(),
    }
    LOGGER.info("OpenAlex API 拉取完成: records=%s pages=%s status=%s", len(records), page_count, status)
    return records, summary


def write_openalex_ingestion_outputs(
    records: list[dict],
    summary: dict,
    output_path: str | Path,
    summary_output_path: str | Path,
) -> None:
    """写出 OpenAlex API 采集产物。

    参数:
        records: OpenAlex Work 记录。
        summary: ingestion summary。
        output_path: Works JSONL 输出路径。
        summary_output_path: summary JSONL 输出路径。

    返回:
        无。
    """
    write_records(records, output_path)
    write_records([summary], summary_output_path)
