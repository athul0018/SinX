from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import AuthContext, accessible_site_ids, get_auth
from app.models import Site, User
from app.schemas import LoginIn, SiteOut, TokenOut, UserOut
from app.security import create_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def user_payload(db: Session, user: User) -> UserOut:
    ids = accessible_site_ids(
        db,
        AuthContext(user, user.company),
    )
    sites = db.query(Site).filter(Site.id.in_(ids)).order_by(Site.name).all() if ids else []
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        global_role=user.global_role,
        is_active=user.is_active,
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
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token = create_token(str(user.id), user.global_role, str(user.company_id))
    set_session_cookie(response, token)
    return TokenOut(token=token, user=user_payload(db, user))


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(settings.cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)) -> UserOut:
    return user_payload(db, auth.user)
