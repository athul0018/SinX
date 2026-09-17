from __future__ import annotations

from fastapi import Query

DEFAULT_LIST_LIMIT = 200
MAX_LIST_LIMIT = 500


def list_limit(limit: int = Query(DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT)) -> int:
    return limit


def list_offset(offset: int = Query(0, ge=0)) -> int:
    return offset
