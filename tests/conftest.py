from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "agent-therapist"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
