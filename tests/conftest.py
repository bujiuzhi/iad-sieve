"""pytest 路径配置文件。"""

from pathlib import Path
import sys

SOURCE_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SOURCE_PATH) not in sys.path:
    sys.path.insert(0, str(SOURCE_PATH))
