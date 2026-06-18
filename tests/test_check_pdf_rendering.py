"""测试 PDF 渲染质量校验脚本。"""

from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "manuscript" / "scripts" / "check_pdf_rendering.py"


def _load_pdf_rendering_module():
    """加载 PDF 渲染校验脚本模块。

    参数:
        无。

    返回:
        module: 已加载的 Python 模块。
    """
    spec = importlib.util.spec_from_file_location("check_pdf_rendering", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_pdf_page_count_reads_pdfinfo_pages() -> None:
    """验证 pdfinfo 页数字段可被解析。"""

    module = _load_pdf_rendering_module()
    pdfinfo_text = "Title: IAD-Risk\nPages:           19\nEncrypted: no\n"

    page_count = module.parse_pdf_page_count(pdfinfo_text)

    assert page_count == 19


def test_sample_pages_uses_first_middle_and_last_without_duplicates() -> None:
    """验证抽样页包含首页、中页、末页且不重复。"""

    module = _load_pdf_rendering_module()

    assert module.sample_pages(1) == [1]
    assert module.sample_pages(2) == [1, 2]
    assert module.sample_pages(19) == [1, 10, 19]


def test_load_ppm_pixels_accepts_ascii_ppm(tmp_path: Path) -> None:
    """验证 P3 PPM 图片可被解析为 RGB 像素。"""

    module = _load_pdf_rendering_module()
    ppm_path = tmp_path / "sample.ppm"
    ppm_path.write_text("P3\n# comment\n2 1\n255\n255 255 255 0 0 0\n", encoding="ascii")

    width, height, pixels = module.load_ppm_pixels(ppm_path)

    assert width == 2
    assert height == 1
    assert pixels == [(255, 255, 255), (0, 0, 0)]


def test_analyze_pixels_accepts_text_like_page() -> None:
    """验证含少量文字像素的页面可通过非空白检测。"""

    module = _load_pdf_rendering_module()
    pixels = [(255, 255, 255)] * 990 + [(0, 0, 0)] * 10

    errors = module.analyze_pixels(50, 20, pixels, min_non_white_ratio=0.002, max_dark_ratio=0.90)

    assert errors == []


def test_analyze_pixels_rejects_blank_page() -> None:
    """验证全白页面会被判定为空白渲染。"""

    module = _load_pdf_rendering_module()
    pixels = [(255, 255, 255)] * 1000

    errors = module.analyze_pixels(50, 20, pixels, min_non_white_ratio=0.002, max_dark_ratio=0.90)

    assert any("appears blank" in error for error in errors)


def test_analyze_pixels_rejects_dark_page() -> None:
    """验证近全黑页面会被判定为失败渲染。"""

    module = _load_pdf_rendering_module()
    pixels = [(0, 0, 0)] * 950 + [(255, 255, 255)] * 50

    errors = module.analyze_pixels(50, 20, pixels, min_non_white_ratio=0.002, max_dark_ratio=0.90)

    assert any("appears dark/failed" in error for error in errors)
