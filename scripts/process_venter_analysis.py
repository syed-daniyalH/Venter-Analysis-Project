"""Thin wrapper so the pipeline can be run directly from the scripts folder."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from venter_analysis.pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())
