"""测试 LaTeX 环境诊断脚本。"""

from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "manuscript" / "scripts" / "diagnose_latex_environment.py"


def _load_latex_diagnostic_module():
    """加载 LaTeX 环境诊断脚本模块。

    参数:
        无。

    返回:
        module: 已加载的 Python 模块。
    """
    spec = importlib.util.spec_from_file_location("diagnose_latex_environment", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_analyze_log_text_accepts_clean_tectonic_log() -> None:
    """验证正常 Tectonic 日志不会被误判为运行时崩溃。"""

    module = _load_latex_diagnostic_module()
    log_text = "\n".join(
        [
            "note: Running TeX ...",
            "note: Running xdvipdfmx ...",
            "note: Writing `main.pdf` (123 KiB)",
        ]
    )

    errors = module.analyze_log_text(log_text, "main.log")

    assert errors == []


def test_analyze_log_text_rejects_tectonic_runtime_panic() -> None:
    """验证 Tectonic/Rust panic 日志会被识别为构建环境问题。"""

    module = _load_latex_diagnostic_module()
    log_text = "\n".join(
        [
            "thread 'reqwest-internal-sync-runtime' panicked at system-configuration/src/dynamic_store.rs:154:1:",
            "Attempted to create a NULL object.",
            "thread 'main' panicked at reqwest/src/blocking/client.rs:1397:5:",
            "event loop thread panicked",
        ]
    )

    errors = module.analyze_log_text(log_text, "main.log")

    assert any("Tectonic/Rust runtime panic" in error for error in errors)
    assert any("Attempted to create a NULL object" in error for error in errors)
    assert any("event loop thread panicked" in error for error in errors)


def test_check_bundle_directory_accepts_existing_directory(tmp_path: Path) -> None:
    """验证本地 Tectonic bundle 目录存在时不会报错。"""

    module = _load_latex_diagnostic_module()

    warnings, errors = module.check_bundle_directory(str(tmp_path))

    assert errors == []
    assert any("TECTONIC_BUNDLE_DIR points to a local directory" in warning for warning in warnings)


def test_check_bundle_directory_rejects_missing_directory(tmp_path: Path) -> None:
    """验证 Tectonic bundle 路径不存在时会给出明确错误。"""

    module = _load_latex_diagnostic_module()
    missing_path = tmp_path / "missing-bundle"

    warnings, errors = module.check_bundle_directory(str(missing_path))

    assert warnings == []
    assert any("TECTONIC_BUNDLE_DIR does not point to a directory" in error for error in errors)


def test_check_engine_availability_rejects_missing_engines() -> None:
    """验证没有可用 LaTeX 引擎时会给出明确错误。"""

    module = _load_latex_diagnostic_module()

    warnings, errors = module.check_engine_availability(["definitely_missing_latex_engine"])

    assert any("definitely_missing_latex_engine: missing" in warning for warning in warnings)
    assert any("no supported LaTeX engine found" in error for error in errors)
