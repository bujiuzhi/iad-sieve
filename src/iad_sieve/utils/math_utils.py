"""数学辅助函数。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    """将数值限制在指定区间。

    参数:
        value: 输入数值。
        lower: 下界。
        upper: 上界。

    返回:
        限制后的数值。
    """
    return max(lower, min(upper, value))


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """安全除法。

    参数:
        numerator: 分子。
        denominator: 分母。
        default: 分母为 0 时的返回值。

    返回:
        除法结果或默认值。
    """
    if denominator == 0:
        return default
    return numerator / denominator


def minmax_normalize(values: dict[str, float]) -> dict[str, float]:
    """对字典值做 min-max 归一化。

    参数:
        values: 键到数值的映射。

    返回:
        归一化后的映射。
    """
    if not values:
        return {}
    minimum = min(values.values())
    maximum = max(values.values())
    if maximum == minimum:
        return {key: 0.0 for key in values}
    return {key: (value - minimum) / (maximum - minimum) for key, value in values.items()}
