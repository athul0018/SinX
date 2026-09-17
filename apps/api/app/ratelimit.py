from __future__ import annotations

from collections import defaultdict
from time import time

from fastapi import HTTPException, Request, status

_WINDOW = 15 * 60
_MAX = 8
_hits: dict[str, list[float]] = defaultdict(list)


def check_login_rate(request: Request, email: str) -> None:
    ip = request.client.host if request.client else "unknown"
    key = f"{ip}:{email.lower().strip()}"
    now = time()
    recent = [t for t in _hits[key] if now - t < _WINDOW]
    if len(recent) >= _MAX:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts. Try again later.")
    recent.append(now)
    _hits[key] = recent
