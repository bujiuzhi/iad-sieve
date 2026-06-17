"""主题簇标签模块。"""

from __future__ import annotations

import logging


LOGGER = logging.getLogger(__name__)


def label_cluster(cluster: dict) -> str:
    """生成主题簇标签。

    参数:
        cluster: 主题簇记录。

    返回:
        簇标签。
    """
    keywords = cluster.get("keywords") or []
    return " / ".join(keywords[:3]) if keywords else "unknown"
