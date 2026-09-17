from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, require_owner
from app.models import Site, SiteUser, User, UserRole
from app.schemas import SiteOut, UserCreate, UserOut
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_owner),
) -> list[UserOut]:
    users = (
        db.query(User)
        .filter(User.company_id == auth.company.id)
        .order_by(User.name)
        .all()
    )
    out: list[UserOut] = []
    for user in users:
        site_rows = (
            db.query(Site)
            .join(SiteUser, SiteUser.site_id == Site.id)
            .filter(SiteUser.user_id == user.id)
            .all()
        )
        if user.global_role == UserRole.OWNER.value:
            site_rows = db.query(Site).filter(Site.company_id == auth.company.id).all()
        out.append(
            UserOut(
                id=user.id,
                name=user.name,
                email=user.email,
                global_role=user.global_role,
                is_active=user.is_active,
                sites=[SiteOut.model_validate(s) for s in site_rows],
            )
        )
    return out


@router.post("", response_model=UserOut)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_owner),
) -> UserOut:
    if body.global_role not in {UserRole.OWNER.value, UserRole.AUTHORIZED.value}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid role")
    email = str(body.email).lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already exists")
    user = User(
        company_id=auth.company.id,
        email=email,
        password_hash=hash_password(body.password),
        name=body.name.strip(),
        is_active=True,
        global_role=body.global_role,
    )
    db.add(user)
    db.flush()
    for site_id in body.site_ids:
        site = db.get(Site, site_id)
        if not site or site.company_id != auth.company.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Site not found")
        db.add(SiteUser(site_id=site.id, user_id=user.id, role=body.global_role))
    sites = db.query(Site).filter(Site.id.in_(body.site_ids)).all() if body.site_ids else []
    if body.global_role == UserRole.OWNER.value:
        sites = db.query(Site).filter(Site.company_id == auth.company.id).all()
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        global_role=user.global_role,
        is_active=user.is_active,
        sites=[SiteOut.model_validate(s) for s in sites],
    )


@router.post("/{user_id}/deactivate")
def deactivate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_owner),
) -> dict:
    user = db.get(User, user_id)
    if not user or user.company_id != auth.company.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == auth.user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot deactivate yourself")
    user.is_active = False
    return {"ok": True}


@router.post("/{user_id}/reactivate")
def reactivate_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_owner),
) -> dict:
    user = db.get(User, user_id)
    if not user or user.company_id != auth.company.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    user.is_active = True
    return {"ok": True}
