from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from jwt import InvalidTokenError
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db import get_db
from app.deps import AuthContext, accessible_site_ids, get_auth
from app.models import Company, Site, User
from app.ratelimit import check_login_rate
from app.schemas import ChangePasswordIn, LoginIn, SiteOut, TokenOut, UserOut
from app.security import create_token, decode_token, hash_password, verify_password
from app.sessions import revoke_jti

router = APIRouter(prefix="/auth", tags=["auth"])


def user_payload(db: Session, user: User, company: Company) -> UserOut:
    ids = accessible_site_ids(db, AuthContext(user, company))
    sites = (
        db.query(Site).filter(Site.id.in_(ids)).order_by(Site.created_at, Site.name).all() if ids else []
    )
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        global_role=user.global_role,
        is_active=user.is_active,
        must_change_password=bool(user.must_change_password),
        sites=[SiteOut.model_validate(s) for s in sites],
    )


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax" if not settings.cookie_secure else "none",
        max_age=settings.jwt_expire_hours * 3600,
        path="/",
    )


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    check_login_rate(db, request, str(body.email))
    user = (
        db.query(User)
        .options(joinedload(User.company))
        .filter(User.email == str(body.email).lower().strip())
        .first()
    )
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if settings.enforce_secure_defaults and verify_password(
        settings.initial_owner_password, user.password_hash
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Default password is disabled in production. Set a new INITIAL_OWNER_PASSWORD and update the owner account.",
        )
    token = create_token(str(user.id), user.global_role, str(user.company_id))
    set_session_cookie(response, token)
    return TokenOut(token=token, user=user_payload(db, user, user.company))


@router.post("/change-password", response_model=UserOut)
def change_password(
    body: ChangePasswordIn,
    response: Response,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
) -> UserOut:
    if not verify_password(body.current_password, auth.user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if verify_password(body.new_password, auth.user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose a different password")
    auth.user.password_hash = hash_password(body.new_password)
    auth.user.must_change_password = False
    token = create_token(str(auth.user.id), auth.user.global_role, str(auth.company.id))
    set_session_cookie(response, token)
    db.flush()
    return user_payload(db, auth.user, auth.company)


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    gsb_session: str | None = Cookie(default=None, alias=settings.cookie_name),
) -> dict:
    raw = None
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1].strip()
    elif gsb_session:
        raw = gsb_session
    if raw:
        try:
            payload = decode_token(raw)
            jti = payload.get("jti")
            if jti:
                revoke_jti(db, str(jti), settings.jwt_expire_hours * 3600)
        except (InvalidTokenError, ValueError, KeyError):
            pass
    response.delete_cookie(settings.cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)) -> UserOut:
    return user_payload(db, auth.user, auth.company)
