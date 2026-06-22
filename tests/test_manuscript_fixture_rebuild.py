"""测试投稿包 fixture 复现核验脚本。"""

from __future__ import annotations

import importlib.util
import subprocess
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


def test_check_cli_discovery_rejects_missing_public_source_command(monkeypatch) -> None:
    """验证 CLI discovery 会拒绝缺失的公开数据处理命令。"""

    module = _load_fixture_rebuild_module()

    def fake_run(*args, **kwargs):
        """Return CLI help output without fetch-openalex-works.

        参数:
            args: Positional subprocess arguments.
            kwargs: Keyword subprocess arguments.

        返回:
            subprocess.CompletedProcess: Simulated successful CLI help output.
        """
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=(
                "prepare-deepmatcher\n"
                "prepare-scirepeval-proximity\n"
                "prepare-openalex-weak-labels\n"
                "build-iad-bench\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    errors = module.check_cli_discovery(sys.executable, {})

    assert any("fetch-openalex-works" in error for error in errors)


def test_check_cli_discovery_reports_failed_help_command(monkeypatch) -> None:
    """验证 CLI help 命令失败时 discovery 返回明确错误。"""

    module = _load_fixture_rebuild_module()

    def fake_run(*args, **kwargs):
        """Raise a subprocess error for the simulated CLI help command.

        参数:
            args: Positional subprocess arguments.
            kwargs: Keyword subprocess arguments.

        返回:
            无。

        异常:
            subprocess.CalledProcessError: Always raised to simulate CLI failure.
        """
        raise subprocess.CalledProcessError(returncode=2, cmd=["python", "-m", "iad_sieve.cli", "--help"], stderr="boom")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    errors = module.check_cli_discovery(sys.executable, {})

    assert errors == ["CLI discovery command failed: python -m iad_sieve.cli --help"]
