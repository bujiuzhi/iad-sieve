"""测试 LLM pair judge 强 baseline 分数生成器。"""

from __future__ import annotations

import json
from argparse import Namespace

from iad_sieve.cli import build_parser, command_run_llm_judge_baseline
from iad_sieve.evaluation import llm_judge_baseline_runner
from iad_sieve.evaluation.llm_judge_baseline_runner import run_llm_judge_baseline
from iad_sieve.evaluation.llm_judge_baseline_runner import _normalize_judgment
from iad_sieve.evaluation.llm_judge_baseline_runner import _extract_json_object
from iad_sieve.utils.io_utils import read_records


def _document(document_id: str, title: str, abstract: str) -> dict:
    """构造测试文献。

    参数:
        document_id: 文献 ID。
        title: 标题。
        abstract: 摘要。

    返回:
        文献记录。
    """
    return {
        "document_id": document_id,
        "title": title,
        "title_normalized": title.lower(),
        "abstract": abstract,
        "abstract_normalized": abstract.lower(),
    }


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


def test_run_llm_judge_baseline_scores_pairs_and_marks_fallback_mode() -> None:
    """验证 LLM judge baseline 输出 pair 分数并标记 fallback 执行模式。"""
    documents = [
        _document("d1", "Neural Retrieval", "Dense retrieval for scientific papers"),
        _document("d2", "Neural Retrieval", "Dense retrieval for scientific papers"),
        _document("d3", "Graph Clustering", "Community detection on citation graphs"),
    ]
    pairs = [
        {"source_document_id": "d1", "target_document_id": "d2"},
        {"source_document_id": "d1", "target_document_id": "d3"},
    ]

    rows, summary = run_llm_judge_baseline(
        documents=documents,
        pairs=pairs,
        system_name="llm_fallback_judge",
        model_name="gpt-5.5",
        score_field="same_work_probability",
        api_backend="fallback",
    )

    assert len(rows) == 2
    assert rows[0]["baseline_family"] == "llm_judge"
    assert rows[0]["execution_mode"] == "fallback"
    assert rows[0]["same_work_probability"] > rows[1]["same_work_probability"]
    assert summary["baseline_family"] == "llm_judge"
    assert summary["execution_mode"] == "fallback"
    assert summary["pair_count"] == 2


def test_run_llm_judge_baseline_marks_openai_api_as_api_model(monkeypatch) -> None:
    """验证 OpenAI API 成功时标记为 api_model。"""
    documents = [
        _document("d1", "Neural Retrieval", "Dense retrieval for scientific papers"),
        _document("d2", "Neural Retrieval", "Dense retrieval for scientific papers"),
    ]
    pairs = [{"source_document_id": "d1", "target_document_id": "d2"}]

    def _fake_judge_pair_with_openai(left_document, right_document, model_name, api_key, timeout_seconds):
        """模拟 OpenAI API 返回结构化判定。"""
        assert model_name == "gpt-5.5"
        assert api_key == "test-key"
        assert timeout_seconds == 10
        return {
            "same_work_probability": 0.82,
            "same_agenda_probability": 0.91,
            "decision": "same_work",
            "rationale": "titles and abstracts match",
        }

    monkeypatch.setattr(llm_judge_baseline_runner, "_judge_pair_with_openai", _fake_judge_pair_with_openai)

    rows, summary = run_llm_judge_baseline(
        documents=documents,
        pairs=pairs,
        system_name="gpt_pair_judge",
        model_name="gpt-5.5",
        api_backend="openai",
        api_key="test-key",
        timeout_seconds=10,
    )

    assert rows[0]["execution_mode"] == "api_model"
    assert rows[0]["same_work_probability"] == 0.82
    assert rows[0]["same_agenda_probability"] == 0.91
    assert summary["execution_mode"] == "api_model"
    assert summary["requested_model_name"] == "gpt-5.5"


def test_run_llm_judge_baseline_marks_transformers_backend_as_actual_model(monkeypatch) -> None:
    """验证本地 Transformers LLM 成功时标记为 actual_model。"""
    documents = [
        _document("d1", "Neural Retrieval", "Dense retrieval for scientific papers"),
        _document("d2", "Neural Retrieval", "Dense retrieval for scientific papers"),
    ]
    pairs = [{"source_document_id": "d1", "target_document_id": "d2"}]

    def _fake_judge_pairs_with_transformers(pair_payloads, model_name, max_new_tokens, batch_size):
        """模拟本地 Transformers LLM 返回结构化判定。"""
        assert len(pair_payloads) == 1
        assert model_name == "Qwen/Qwen2.5-0.5B-Instruct"
        assert max_new_tokens == 32
        assert batch_size == 2
        return [
            {
                "same_work_probability": 0.74,
                "same_agenda_probability": 0.88,
                "decision": "same_work",
                "rationale": "local model judged matching metadata",
            }
        ]

    monkeypatch.setattr(llm_judge_baseline_runner, "_judge_pairs_with_transformers", _fake_judge_pairs_with_transformers)

    rows, summary = run_llm_judge_baseline(
        documents=documents,
        pairs=pairs,
        system_name="local_llm_pair_judge",
        model_name="Qwen/Qwen2.5-0.5B-Instruct",
        api_backend="transformers",
        max_new_tokens=32,
        batch_size=2,
    )

    assert rows[0]["execution_mode"] == "actual_model"
    assert rows[0]["api_backend"] == "transformers"
    assert rows[0]["same_work_probability"] == 0.74
    assert summary["execution_mode"] == "actual_model"
    assert summary["model_backend"] == "transformers"
    assert summary["batch_size"] == 2


def test_normalize_judgment_coerces_invalid_decision_to_valid_label() -> None:
    """验证本地 LLM 输出非法 decision 时按概率回退为合法标签。"""
    judgment = _normalize_judgment(
        {
            "same_work_probability": 0.81,
            "same_agenda_probability": 0.7,
            "decision": "same_work|same_agenda_not_same_work|different|uncertain",
            "rationale": "invalid enum copied from prompt",
        }
    )

    assert judgment["decision"] == "same_work"
    assert judgment["same_work_probability"] == 0.81


def test_extract_json_object_prefers_complete_object_when_model_outputs_multiple_json_blocks() -> None:
    """验证模型输出多个 JSON 对象时优先选择字段完整的对象。"""
    parsed = _extract_json_object(
        '{"decision": "different", "rationale": "partial"}\n'
        '{"same_work_probability": 0.2, "same_agenda_probability": 0.9, '
        '"decision": "same_agenda_not_same_work", "rationale": "complete"}'
    )

    assert parsed["same_work_probability"] == 0.2
    assert parsed["decision"] == "same_agenda_not_same_work"


def test_run_llm_judge_baseline_cli_writes_scores(tmp_path) -> None:
    """验证 CLI 写出 LLM judge baseline 分数。"""
    documents_path = tmp_path / "documents.jsonl"
    pairs_path = tmp_path / "pairs.jsonl"
    output_path = tmp_path / "scores.jsonl"
    summary_path = tmp_path / "summary.jsonl"
    _write_jsonl(
        documents_path,
        [
            _document("d1", "Neural Retrieval", "Dense retrieval for scientific papers"),
            _document("d2", "Neural Retrieval", "Dense retrieval for scientific papers"),
        ],
    )
    _write_jsonl(pairs_path, [{"source_document_id": "d1", "target_document_id": "d2"}])

    command_run_llm_judge_baseline(
        Namespace(
            documents=str(documents_path),
            pairs=str(pairs_path),
            output=str(output_path),
            summary_output=str(summary_path),
            system_name="llm_fallback_judge",
            model_name="gpt-5.5",
            score_field="same_work_probability",
            api_backend="fallback",
            api_key_env="OPENAI_API_KEY",
            timeout_seconds=10,
            max_new_tokens=80,
            batch_size=4,
            limit=None,
        )
    )

    rows = read_records(output_path)
    summary_rows = read_records(summary_path)

    assert rows[0]["same_work_probability"] == 1.0
    assert summary_rows[0]["execution_mode"] == "fallback"


def test_cli_includes_run_llm_judge_baseline_command() -> None:
    """验证 CLI 暴露 run-llm-judge-baseline 命令。"""
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-llm-judge-baseline",
            "--documents",
            "outputs/iad_bench_fixture/iad_bench_documents.jsonl",
            "--pairs",
            "outputs/iad_bench_fixture/iad_bench_pairs.jsonl",
            "--output",
            "outputs/strong_baseline_fixture/gpt_pair_scores.jsonl",
            "--summary-output",
            "outputs/strong_baseline_fixture/gpt_pair_execution_summary.jsonl",
            "--system-name",
            "gpt_pair_judge",
            "--model-name",
            "gpt-5.5",
            "--api-backend",
            "transformers",
            "--batch-size",
            "8",
        ]
    )

    assert args.command == "run-llm-judge-baseline"
    assert args.system_name == "gpt_pair_judge"
    assert args.api_backend == "transformers"
    assert args.batch_size == 8
