from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, accessible_site_ids, get_auth, require_owner, require_site
from app.models import Site, SiteUser, User
from app.schemas import SiteCreate, SiteOut, SiteUpdate

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("", response_model=list[SiteOut])
def list_sites(db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)) -> list[Site]:
    ids = accessible_site_ids(db, auth)
    if not ids:
        return []
    return db.query(Site).filter(Site.id.in_(ids)).order_by(Site.created_at, Site.name).all()


@router.get("/transfer-targets", response_model=list[SiteOut])
def transfer_targets(db: Session = Depends(get_db), auth: AuthContext = Depends(get_auth)) -> list[Site]:
    return (
        db.query(Site)
        .filter(Site.company_id == auth.company.id, Site.status == "active")
        .order_by(Site.name)
        .all()
    )


@router.post("", response_model=SiteOut)
def create_site(
    body: SiteCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_owner),
) -> Site:
    exists = (
        db.query(Site)
        .filter(Site.company_id == auth.company.id, Site.code == body.code.strip().upper())
        .first()
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Site code already exists")
    site = Site(
        company_id=auth.company.id,
        name=body.name.strip(),
        code=body.code.strip().upper(),
        status="active",
    )
    db.add(site)
    db.flush()
    return site


@router.patch("/{site_id}", response_model=SiteOut)
def update_site(
    body: SiteUpdate,
    db: Session = Depends(get_db),
    _owner: AuthContext = Depends(require_owner),
    site: Site = Depends(require_site),
) -> Site:
    if body.name:
        site.name = body.name.strip()
    if body.status:
        if body.status not in {"active", "inactive"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Status must be active or inactive")
        site.status = body.status
    return site


@router.get("/{site_id}", response_model=SiteOut)
def get_site(site: Site = Depends(require_site)) -> Site:
    return site


@router.post("/{site_id}/users/{user_id}")
def assign_user(
    user_id: UUID,
    role: str = "AUTHORIZED",
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_owner),
    site: Site = Depends(require_site),
) -> dict:
    if role not in {"OWNER", "AUTHORIZED"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid role")
    user = db.get(User, user_id)
    if not user or user.company_id != auth.company.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    existing = (
        db.query(SiteUser).filter(SiteUser.site_id == site.id, SiteUser.user_id == user_id).first()
    )
    if existing:
        existing.role = role
    else:
        db.add(SiteUser(site_id=site.id, user_id=user_id, role=role))
    return {"ok": True}
