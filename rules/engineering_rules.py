import json
from pathlib import Path

ROOT = Path(__file__).parent
LEVELS = {"不考虑": 0, "较低": 1, "一般": 2, "较高": 4, "很高": 5}
HARDNESS_LEVELS = {"软": 1, "较软": 2, "中": 3, "硬": 4, "很硬": 5}

def load(path=None):
    return json.loads(Path(path or ROOT / "weights.json").read_text(encoding="utf-8"))
