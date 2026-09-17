"""Vercel entry shim: re-export FastAPI app from apps/api."""
from __future__ import annotations

import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent / "apps" / "api"
_api_root = str(_API_ROOT)
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)

from app.main import app  # noqa: E402
