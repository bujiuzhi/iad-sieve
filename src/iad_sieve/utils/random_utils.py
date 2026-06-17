"""随机数工具。"""

from __future__ import annotations

import logging
import random


LOGGER = logging.getLogger(__name__)


def set_random_seed(seed: int) -> None:
    """设置 Python 和可选 numpy 随机种子。

    参数:
        seed: 随机种子。

    返回:
        无。
    """
    random.seed(seed)
    try:
        import numpy as np  # type: ignore

        np.random.seed(seed)
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("numpy 不可用，跳过 numpy seed: %s", exc)
