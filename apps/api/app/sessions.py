from __future__ import annotations

from time import time
from uuid import uuid4

_revoked: dict[str, float] = {}


def new_jti() -> str:
    return uuid4().hex


def revoke_jti(jti: str, ttl_seconds: int) -> None:
    _revoked[jti] = time() + ttl_seconds


def is_revoked(jti: str | None) -> bool:
    if not jti:
        return False
    expires = _revoked.get(jti)
    if expires is None:
        return False
    if time() > expires:
        _revoked.pop(jti, None)
        return False
    return True
