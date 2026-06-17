"""测试 OpenAlex API ingestion。"""

from __future__ import annotations

from iad_sieve.cli import build_parser
from iad_sieve.evaluation.openalex_api_ingestion import fetch_openalex_works, write_openalex_ingestion_outputs
from iad_sieve.utils.io_utils import read_records


def test_fetch_openalex_works_uses_cursor_pagination() -> None:
    """验证 OpenAlex API 拉取器支持 cursor 翻页。"""
    calls: list[str] = []

    def fake_get(url: str, timeout: int) -> dict:
        """模拟 OpenAlex HTTP 响应。"""
        calls.append(url)
        if "cursor=%2A" in url:
            return {
                "meta": {"next_cursor": "page2"},
                "results": [{"id": "https://openalex.org/W1"}, {"id": "https://openalex.org/W2"}],
            }
        return {
            "meta": {"next_cursor": None},
            "results": [{"id": "https://openalex.org/W3"}],
        }

    records, summary = fetch_openalex_works(
        filter_expression="from_publication_date:2020-01-01,type:article",
        select_fields="id,doi,display_name",
        per_page=2,
        max_records=3,
        seed=42,
        http_get=fake_get,
    )

    assert [record["id"] for record in records] == ["https://openalex.org/W1", "https://openalex.org/W2", "https://openalex.org/W3"]
    assert len(calls) == 2
    assert summary["source"] == "openalex_api"
    assert summary["fetched_record_count"] == 3
    assert summary["cursor_page_count"] == 2
    assert summary["status"] == "completed"


def test_fetch_openalex_works_caps_page_size_and_hides_api_key() -> None:
    """验证 OpenAlex API 页大小按当前限制封顶且 summary 不泄露 key。"""
    calls: list[str] = []

    def fake_get(url: str, timeout: int) -> dict:
        """模拟单页 OpenAlex HTTP 响应。"""
        calls.append(url)
        return {
            "meta": {"next_cursor": None},
            "results": [{"id": "https://openalex.org/W1"}],
        }

    _, summary = fetch_openalex_works(
        per_page=200,
        max_records=150,
        api_key="dummy",
        http_get=fake_get,
    )

    assert "per-page=100" in calls[0]
    assert "api_key=dummy" in calls[0]
    assert summary["per_page"] == 100
    assert summary["api_key_used"] is True
    assert "dummy" not in str(summary)


def test_fetch_openalex_works_omits_seed_without_sampling() -> None:
    """验证未开启 sample 时不向 OpenAlex 传 seed。"""
    calls: list[str] = []

    def fake_get(url: str, timeout: int) -> dict:
        """模拟单页 OpenAlex HTTP 响应。"""
        calls.append(url)
        return {
            "meta": {"next_cursor": None},
            "results": [{"id": "https://openalex.org/W1"}],
        }

    fetch_openalex_works(
        per_page=10,
        max_records=10,
        seed=42,
        sample_size=None,
        http_get=fake_get,
    )

    assert "seed=42" not in calls[0]


def test_fetch_openalex_works_keeps_seed_with_sampling() -> None:
    """验证开启 sample 时保留 seed 参数。"""
    calls: list[str] = []

    def fake_get(url: str, timeout: int) -> dict:
        """模拟单页 OpenAlex HTTP 响应。"""
        calls.append(url)
        return {
            "meta": {"next_cursor": None},
            "results": [{"id": "https://openalex.org/W1"}],
        }

    fetch_openalex_works(
        per_page=10,
        max_records=10,
        seed=42,
        sample_size=10,
        http_get=fake_get,
    )

    assert "sample=10" in calls[0]
    assert "seed=42" in calls[0]


def test_write_openalex_ingestion_outputs_writes_jsonl_and_summary(tmp_path) -> None:
    """验证 OpenAlex ingestion 输出 Works JSONL 和 summary。"""
    output_path = tmp_path / "works.jsonl"
    summary_path = tmp_path / "ingestion_summary.jsonl"

    write_openalex_ingestion_outputs(
        records=[{"id": "https://openalex.org/W1"}],
        summary={"source": "openalex_api", "fetched_record_count": 1, "status": "completed"},
        output_path=output_path,
        summary_output_path=summary_path,
    )

    records = read_records(output_path)
    summary_rows = read_records(summary_path)
    assert records[0]["id"] == "https://openalex.org/W1"
    assert summary_rows[0]["source"] == "openalex_api"
    assert summary_rows[0]["fetched_record_count"] == 1


def test_cli_includes_fetch_openalex_works_command() -> None:
    """验证 CLI 暴露 fetch-openalex-works 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "fetch-openalex-works",
            "--output",
            "data/raw/openalex/works_api_sample.jsonl",
            "--summary-output",
            "outputs/openalex_api_ingestion/ingestion_summary.jsonl",
            "--filter",
            "from_publication_date:2020-01-01,type:article",
            "--select",
            "id,doi,display_name",
            "--per-page",
            "200",
            "--max-records",
            "1000",
            "--seed",
            "42",
            "--api-key",
            "dummy",
        ]
    )

    assert args.command == "fetch-openalex-works"
    assert args.per_page == 200
    assert args.max_records == 1000
    assert args.api_key == "dummy"
