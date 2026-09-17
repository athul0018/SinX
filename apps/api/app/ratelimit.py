from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models import LoginAttempt

_WINDOW = timedelta(minutes=15)
_MAX = 8


def check_login_rate(db: Session, request: Request, email: str) -> None:
    ip = request.client.host if request.client else "unknown"
    key = f"{ip}:{email.lower().strip()}"
    cutoff = datetime.now(UTC) - _WINDOW
    recent = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.bucket_key == key, LoginAttempt.created_at >= cutoff)
        .count()
    )
    if recent >= _MAX:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts. Try again later.")
    db.add(LoginAttempt(bucket_key=key))
    db.query(LoginAttempt).filter(LoginAttempt.created_at < cutoff - timedelta(days=1)).delete(
        synchronize_session=False
    )
