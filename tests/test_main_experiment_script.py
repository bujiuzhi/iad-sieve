"""验证 100k 分片主实验脚本的结构契约。"""

from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_100k_sharded_experiment.sh"
MAIN_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_main_experiment.sh"


def test_100k_sharded_script_exists_and_has_valid_shell_syntax() -> None:
    """验证 100k 分片实验脚本存在且 Bash 语法有效。"""
    assert SCRIPT_PATH.exists()

    result = subprocess.run(["bash", "-n", str(SCRIPT_PATH)], check=False, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


def test_100k_sharded_script_uses_incremental_sharded_flow() -> None:
    """验证 100k 主实验脚本采用可恢复的分片评分流程。"""
    script_content = SCRIPT_PATH.read_text(encoding="utf-8")

    expected_commands = [
        "prepare-sample",
        "preprocess",
        "build-views",
        "embed",
        "generate-candidates",
        "score-relations",
        "merge-duplicates",
        "build-topic-graph",
        "cluster",
        "rank",
        "recommend",
        "evaluate",
        "run-bootstrap",
        "export-error-analysis",
        "score-manual-annotations",
        "export-paper-artifacts",
        "analyze-candidate-cap",
    ]
    for command_name in expected_commands:
        assert command_name in script_content

    assert "--shard-count" in script_content
    assert "--shard-index" in script_content
    assert "pair_relations_shard_" in script_content
    assert "run-pipeline" not in script_content


def test_main_experiment_entrypoint_delegates_to_100k_sharded_script() -> None:
    """验证主实验入口委托给 100k 分片主实验脚本。"""
    script_content = MAIN_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "run_100k_sharded_experiment.sh" in script_content
    assert "run_dev_experiment.sh" not in script_content
