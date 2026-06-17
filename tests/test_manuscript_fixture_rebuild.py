"""测试投稿包 fixture 复现核验脚本。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from iad_sieve.utils.io_utils import read_records


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "manuscript" / "scripts" / "verify_fixture_rebuild.py"


def _load_fixture_rebuild_module():
    """加载投稿包 fixture 复现脚本模块。

    参数:
        无。

    返回:
        module: 已加载的 Python 模块。
    """
    spec = importlib.util.spec_from_file_location("verify_fixture_rebuild", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_verify_fixture_rebuild_runs_no_network_pipeline(tmp_path) -> None:
    """验证投稿包脚本可重建无网络 fixture IAD-Bench 输出。"""

    module = _load_fixture_rebuild_module()
    output_root = tmp_path / "fixture_rebuild"

    errors = module.run_fixture_rebuild(sys.executable, output_root)

    assert errors == []
    pairs = read_records(output_root / "iad_bench" / "iad_bench_pairs.jsonl")
    summary = read_records(output_root / "iad_bench" / "iad_bench_summary.jsonl")[0]
    assert pairs
    assert summary["evidence_layer"] == "iad_bench_provenance"
