"""Top-level pytest configuration — 注入 src 路径 + 共享 fixtures。"""

import sys
from pathlib import Path

# 自动把 src/ 加进 sys.path，避免用户需要 export PYTHONPATH
_src = Path(__file__).parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
