"""日志配置模块。"""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str = "INFO") -> logging.Logger:
    """配置项目日志。

    参数:
        level: 日志级别名称。

    返回:
        项目根 logger。
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        stream=sys.stderr,
    )
    return logging.getLogger("iad_sieve")
