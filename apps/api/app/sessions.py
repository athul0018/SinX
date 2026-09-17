from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import RevokedSession


def revoke_jti(db: Session, jti: str, ttl_seconds: int) -> None:
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    db.merge(RevokedSession(jti=jti, expires_at=expires_at))
    _purge_expired(db)


def is_revoked(db: Session, jti: str | None) -> bool:
    if not jti:
        return False
    row = db.get(RevokedSession, jti)
    if not row:
        return False
    if row.expires_at <= datetime.now(UTC):
        db.delete(row)
        return False
    return True


def _purge_expired(db: Session) -> None:
    db.query(RevokedSession).filter(RevokedSession.expires_at <= datetime.now(UTC)).delete(
        synchronize_session=False
    )
