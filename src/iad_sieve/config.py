"""项目配置对象。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelineConfig:
    """流水线配置。

    参数:
        run_id: 本次运行标识。
        output_dir: 输出目录。
        seed: 随机种子。
        embedding_model: embedding 模型名称。

    返回:
        不返回值，作为不可变配置对象使用。
    """

    run_id: str
    output_dir: Path
    seed: int = 42
    embedding_model: str = "hashing-fallback"
