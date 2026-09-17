from __future__ import annotations

import uuid
from zoneinfo import ZoneInfo

from fastapi import Cookie, Depends, Header, HTTPException, status
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Company, Site, SiteUser, User, UserRole
from app.security import decode_token
from app.sessions import is_revoked


class AuthContext:
    def __init__(self, user: User, company: Company):
        self.user = user
        self.company = company

    @property
    def is_owner(self) -> bool:
        return self.user.global_role == UserRole.OWNER.value

    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.company.timezone or "Asia/Kolkata")


def _token_from_request(
    authorization: str | None,
    cookie_token: str | None,
) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    if cookie_token:
        return cookie_token
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")


def get_auth(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    gsb_session: str | None = Cookie(default=None, alias=settings.cookie_name),
) -> AuthContext:
    token = _token_from_request(authorization, gsb_session)
    try:
        payload = decode_token(token)
    except InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session") from None

    user = db.get(User, uuid.UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive or missing")
    if is_revoked(payload.get("jti")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    company = db.get(Company, user.company_id)
    if not company:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Company missing")
    return AuthContext(user, company)


def require_owner(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    if not auth.is_owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner access required")
    return auth


def accessible_site_ids(db: Session, auth: AuthContext) -> set[uuid.UUID]:
    if auth.is_owner:
        rows = db.query(Site.id).filter(Site.company_id == auth.company.id).all()
        return {row[0] for row in rows}
    rows = (
        db.query(SiteUser.site_id)
        .join(Site, Site.id == SiteUser.site_id)
        .filter(SiteUser.user_id == auth.user.id, Site.company_id == auth.company.id)
        .all()
    )
    return {row[0] for row in rows}


def require_site(
    site_id: uuid.UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
) -> Site:
    site = db.get(Site, site_id)
    if not site or site.company_id != auth.company.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Site not found")
    if site.id not in accessible_site_ids(db, auth):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Site not found")
    return site
