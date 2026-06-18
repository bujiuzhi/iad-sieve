"""测试 LaTeX 构建日志警告校验脚本。"""

from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "manuscript" / "scripts" / "check_latex_warnings.py"


def _load_latex_warning_module():
    """加载 LaTeX warning 校验脚本模块。

    参数:
        无。

    返回:
        module: 已加载的 Python 模块。
    """
    spec = importlib.util.spec_from_file_location("check_latex_warnings", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_log_text_accepts_minor_layout_warnings() -> None:
    """验证轻微 overfull 和 underfull warning 不阻断构建。"""

    module = _load_latex_warning_module()
    log_text = "\n".join(
        [
            r"warning: main.bbl:19: Underfull \hbox (badness 1721) in paragraph at lines 15--19",
            r"warning: iad-risk.tex:38: Overfull \hbox (2.608pt too wide) has occurred while \output is active",
        ]
    )

    errors = module.check_log_text(log_text, "build.log", max_overfull_pt=5.0)

    assert errors == []


def test_check_log_text_rejects_severe_overfull_hbox() -> None:
    """验证严重 overfull hbox 会被视为版面门禁错误。"""

    module = _load_latex_warning_module()
    log_text = r"warning: manuscript.tex:152: Overfull \hbox (83.51814pt too wide) in paragraph"

    errors = module.check_log_text(log_text, "build.log", max_overfull_pt=5.0)

    assert any("severe overfull hbox" in error for error in errors)
    assert any("83.518" in error for error in errors)


def test_check_log_text_rejects_unresolved_reference_and_citation() -> None:
    """验证未解析引用和参考文献会被拒绝。"""

    module = _load_latex_warning_module()
    log_text = "\n".join(
        [
            "LaTeX Warning: Reference `tab:missing' on page 2 undefined on input line 10.",
            "LaTeX Warning: Citation `missing2026' on page 3 undefined on input line 20.",
            "LaTeX Warning: There were undefined references.",
        ]
    )

    errors = module.check_log_text(log_text, "build.log", max_overfull_pt=5.0)

    assert any("unresolved reference" in error for error in errors)
    assert any("unresolved citation" in error for error in errors)
    assert any("unresolved references" in error for error in errors)


def test_check_log_files_rejects_missing_log(tmp_path: Path) -> None:
    """验证缺失构建日志会被拒绝。"""

    module = _load_latex_warning_module()
    missing_log = tmp_path / "missing.log"

    errors = module.check_log_files([missing_log], max_overfull_pt=5.0)

    assert any("missing LaTeX build log" in error for error in errors)
