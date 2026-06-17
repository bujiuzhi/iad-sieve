"""检测 Python、PyTorch、CUDA 和 GPU 状态。"""

from __future__ import annotations

import logging
import platform
import subprocess
from typing import Any


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger("iad_sieve.check_cuda")


def _run_command(command: list[str]) -> str:
    """执行系统命令并返回标准输出。

    参数:
        command: 待执行的命令及参数。

    返回:
        命令标准输出；执行失败时返回错误说明。
    """
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=20)
        if completed.returncode != 0:
            return completed.stderr.strip() or "命令执行失败"
        return completed.stdout.strip()
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("执行命令失败: %s", command)
        return str(exc)


def collect_cuda_report() -> dict[str, Any]:
    """收集 CUDA 与 GPU 检测结果。

    参数:
        无。

    返回:
        包含 Python、PyTorch、CUDA 和 GPU 信息的字典。
    """
    report: dict[str, Any] = {"python_version": platform.python_version()}
    try:
        import torch  # type: ignore

        report["torch_version"] = torch.__version__
        report["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            device_index = torch.cuda.current_device()
            properties = torch.cuda.get_device_properties(device_index)
            report["gpu_name"] = properties.name
            report["gpu_memory_mb"] = int(properties.total_memory / 1024 / 1024)
            report["gpu_memory_allocated_mb"] = int(torch.cuda.memory_allocated(device_index) / 1024 / 1024)
        else:
            report["gpu_name"] = ""
            report["gpu_memory_mb"] = 0
            report["gpu_memory_allocated_mb"] = 0
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("PyTorch 不可用或 CUDA 检测失败: %s", exc)
        report["torch_version"] = "not_installed"
        report["cuda_available"] = False
        report["gpu_name"] = ""
        report["gpu_memory_mb"] = 0
        report["gpu_memory_allocated_mb"] = 0

    nvidia_smi = _run_command(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used",
            "--format=csv,noheader",
        ]
    )
    report["nvidia_smi"] = nvidia_smi
    return report


def main() -> None:
    """打印 CUDA 检测结果。

    参数:
        无。

    返回:
        无。
    """
    report = collect_cuda_report()
    print(f"Python 版本: {report['python_version']}")
    print(f"PyTorch 版本: {report['torch_version']}")
    print(f"CUDA 是否可用: {report['cuda_available']}")
    print(f"GPU 名称: {report['gpu_name']}")
    print(f"显存容量 MB: {report['gpu_memory_mb']}")
    print(f"当前显存占用 MB: {report['gpu_memory_allocated_mb']}")
    print(f"nvidia-smi: {report['nvidia_smi']}")


if __name__ == "__main__":
    main()
