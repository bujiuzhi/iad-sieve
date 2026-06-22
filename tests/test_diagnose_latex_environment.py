"""测试 LaTeX 环境诊断脚本。"""

from __future__ import annotations

import importlib.util
import subprocess
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


def test_analyze_log_text_reports_missing_tex_resource() -> None:
    """验证缺失 TeX 资源会被识别为 bundle 完整性问题。"""

    module = _load_latex_diagnostic_module()
    log_text = "\n".join(
        [
            "note: Running TeX ...",
            "error: article.cls:113: ! LaTeX Error: File `size11.clo' not found.",
            "error: halted on potentially-recoverable error as specified",
        ]
    )

    errors = module.analyze_log_text(log_text, "smoke.log")

    assert any("missing TeX resource: size11.clo" in error for error in errors)
    assert any("Tectonic bundle completeness" in error for error in errors)


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


def test_check_tectonic_smoke_test_rejects_runtime_panic(monkeypatch) -> None:
    """验证最小 Tectonic 烟测能识别版本可用但运行即崩溃的环境。"""

    module = _load_latex_diagnostic_module()
    panic_output = "\n".join(
        [
            "thread 'reqwest-internal-sync-runtime' panicked at system-configuration/src/dynamic_store.rs:154:1:",
            "Attempted to create a NULL object.",
            "thread 'main' panicked at reqwest/src/blocking/client.rs:1397:5:",
            "event loop thread panicked",
        ]
    )

    def fake_run(command, check, capture_output, text, timeout):
        """Return a synthetic Tectonic runtime panic."""
        return subprocess.CompletedProcess(command, 101, stdout="", stderr=panic_output)

    monkeypatch.setattr(module.shutil, "which", lambda command_name: "/usr/bin/tectonic")
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    warnings, errors = module.check_tectonic_smoke_test("")

    assert warnings == []
    assert any("article 11pt smoke test contains a Tectonic/Rust runtime panic" in error for error in errors)
    assert any("Attempted to create a NULL object" in error for error in errors)
    assert any("event loop thread panicked" in error for error in errors)


def test_check_tectonic_smoke_test_reports_non_panic_output_excerpt(monkeypatch) -> None:
    """验证非 panic 烟测失败会保留可定位的输出摘录。"""

    module = _load_latex_diagnostic_module()
    missing_resource_output = "\n".join(
        [
            "note: using only cached resource files",
            "note: Running TeX ...",
            "error: article.cls:113: ! LaTeX Error: File `size11.clo' not found.",
            "error: halted on potentially-recoverable error as specified",
        ]
    )

    def fake_run(command, check, capture_output, text, timeout):
        """Return a synthetic missing-resource Tectonic failure."""
        return subprocess.CompletedProcess(command, 1, stdout="", stderr=missing_resource_output)

    monkeypatch.setattr(module.shutil, "which", lambda command_name: "/usr/bin/tectonic")
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    warnings, errors = module.check_tectonic_smoke_test("/tmp/partial-bundle")

    assert warnings == []
    assert any("missing TeX resource: size11.clo" in error for error in errors)
    assert any("article 11pt smoke test failed with exit code 1" in error for error in errors)
    assert any("Tectonic smoke test output excerpt (article 11pt smoke test)" in error for error in errors)
    assert any("size11.clo" in error for error in errors)


def test_check_tectonic_smoke_test_uses_project_relevant_documents(monkeypatch) -> None:
    """验证烟测覆盖主稿 article 11pt 和 Elsevier 12pt 构建路径。"""

    module = _load_latex_diagnostic_module()
    compiled_sources: list[str] = []

    def fake_run(command, check, capture_output, text, timeout):
        """Record the smoke-test source document and return success."""
        source_path = Path(command[-1])
        compiled_sources.append(source_path.read_text(encoding="utf-8"))
        return subprocess.CompletedProcess(command, 0, stdout="note: Writing `smoke.pdf`", stderr="")

    monkeypatch.setattr(module.shutil, "which", lambda command_name: "/usr/bin/tectonic")
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    warnings, errors = module.check_tectonic_smoke_test("/tmp/project-bundle")

    assert errors == []
    assert any("\\documentclass[11pt]{article}" in source for source in compiled_sources)
    assert any("\\documentclass[preprint,12pt]{elsarticle}" in source for source in compiled_sources)
    assert any("article 11pt smoke test completed" in warning for warning in warnings)
    assert any("elsarticle 12pt smoke test completed" in warning for warning in warnings)


def test_diagnose_latex_environment_can_skip_smoke_test(tmp_path: Path, monkeypatch) -> None:
    """验证只检查历史日志时可以显式跳过 Tectonic 烟测。"""

    module = _load_latex_diagnostic_module()
    clean_log = tmp_path / "main.log"
    clean_log.write_text("note: Writing `main.pdf`\n", encoding="utf-8")
    monkeypatch.setattr(module, "check_engine_availability", lambda: (["tectonic: mocked"], []))
    monkeypatch.setattr(
        module,
        "check_tectonic_smoke_test",
        lambda bundle_dir: (_ for _ in ()).throw(AssertionError("smoke test should be skipped")),
    )

    warnings, errors = module.diagnose_latex_environment([clean_log], "", run_smoke_test=False)

    assert any("TECTONIC_BUNDLE_DIR is not set" in warning for warning in warnings)
    assert errors == []


def test_diagnose_latex_environment_can_skip_missing_logs(tmp_path: Path, monkeypatch) -> None:
    """验证构建前诊断可以跳过尚未生成的日志文件。"""

    module = _load_latex_diagnostic_module()
    missing_log = tmp_path / "missing-main.log"
    monkeypatch.setattr(module, "check_engine_availability", lambda: (["tectonic: mocked"], []))
    monkeypatch.setattr(module, "check_tectonic_smoke_test", lambda bundle_dir: (["smoke ok"], []))

    warnings, errors = module.diagnose_latex_environment(
        [missing_log],
        "",
        run_smoke_test=True,
        run_log_checks=False,
    )

    assert any("TECTONIC_BUNDLE_DIR is not set" in warning for warning in warnings)
    assert any("smoke ok" in warning for warning in warnings)
    assert errors == []


def test_diagnose_latex_environment_reports_missing_logs_when_enabled(tmp_path: Path, monkeypatch) -> None:
    """验证未跳过日志检查时缺失构建日志仍会被报告。"""

    module = _load_latex_diagnostic_module()
    missing_log = tmp_path / "missing-main.log"
    monkeypatch.setattr(module, "check_engine_availability", lambda: (["tectonic: mocked"], []))
    monkeypatch.setattr(module, "check_tectonic_smoke_test", lambda bundle_dir: (["smoke ok"], []))

    warnings, errors = module.diagnose_latex_environment(
        [missing_log],
        "",
        run_smoke_test=True,
        run_log_checks=True,
    )

    assert any("smoke ok" in warning for warning in warnings)
    assert any("missing LaTeX build log for diagnosis" in error for error in errors)


def test_diagnose_latex_environment_reports_smoke_test_errors(tmp_path: Path, monkeypatch) -> None:
    """验证诊断入口会汇总最小 Tectonic 烟测错误。"""

    module = _load_latex_diagnostic_module()
    clean_log = tmp_path / "main.log"
    clean_log.write_text("note: Writing `main.pdf`\n", encoding="utf-8")
    monkeypatch.setattr(module, "check_engine_availability", lambda: (["tectonic: mocked"], []))
    monkeypatch.setattr(
        module,
        "check_tectonic_smoke_test",
        lambda bundle_dir: ([], ["tectonic smoke test contains a Tectonic/Rust runtime panic"]),
    )

    warnings, errors = module.diagnose_latex_environment([clean_log], "", run_smoke_test=True)

    assert any("TECTONIC_BUNDLE_DIR is not set" in warning for warning in warnings)
    assert any("Tectonic/Rust runtime panic" in error for error in errors)
