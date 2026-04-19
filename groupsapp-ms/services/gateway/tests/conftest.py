import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent  # services/gateway/
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "generated"))
