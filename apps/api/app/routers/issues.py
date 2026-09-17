from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, get_auth, require_site
from app.models import DailyPlan, DailyProgress, Site
from app.routers.progress import pack_payload, unpack_payload
from app.schemas import IssueOut, IssueUpdateIn

router = APIRouter(prefix="/sites/{site_id}/issues", tags=["issues"])


def to_issue(row: DailyProgress, plan: DailyPlan | None) -> IssueOut | None:
    meta = unpack_payload(row.remarks)
    if not meta["has_issue"]:
        return None
    if plan and plan.plan_code == "IDLE":
        return None
    if meta["rectify_status"] == "Closed":
        return None
    activity = ""
    if plan:
        activity = plan.equipment_tag or plan.job_description or plan.plan_code
    observed = meta["observed_at"]
    if not observed and row.reported_at:
        observed = row.reported_at.date().isoformat()
    status_at = meta["rectify_status_at"] or observed
    return IssueOut(
        id=row.id,
        plan_id=row.plan_id,
        activity=activity,
        issue_description=meta["issue_description"],
        observed_at=observed,
        rectify_status=meta["rectify_status"] or "Raised",
        rectify_status_at=status_at,
        comments=meta["comments"],
    )


@router.get("", response_model=list[IssueOut])
def list_issues(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    site: Site = Depends(require_site),
) -> list[IssueOut]:
    rows = (
        db.query(DailyProgress)
        .filter(DailyProgress.site_id == site.id)
        .order_by(DailyProgress.reported_at.desc())
        .limit(500)
        .all()
    )
    plans = {row.id: row for row in db.query(DailyPlan).filter(DailyPlan.site_id == site.id).all()}
    items: list[IssueOut] = []
    for row in rows:
        item = to_issue(row, plans.get(row.plan_id))
        if item:
            items.append(item)
    return items


@router.patch("/{progress_id}", response_model=IssueOut)
def update_issue(
    progress_id: UUID,
    body: IssueUpdateIn,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    site: Site = Depends(require_site),
) -> IssueOut:
    row = db.get(DailyProgress, progress_id)
    if not row or row.site_id != site.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Issue not found")
    meta = unpack_payload(row.remarks)
    if not meta["has_issue"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No issue on this progress record")

    today = datetime.now(auth.tz()).date().isoformat()
    observed_at = meta["observed_at"] or today
    if body.observed_at is not None:
        value = body.observed_at.strip()
        if value:
            observed_at = value

    rectify_status = meta["rectify_status"] or "Raised"
    rectify_status_at = meta["rectify_status_at"] or observed_at
    if body.rectify_status is not None:
        key = body.rectify_status.strip().lower()
        if key in {"rised", "raised"}:
            next_status = "Raised"
        elif key == "closed":
            next_status = "Closed"
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Status must be Raised or Closed")
        if next_status != rectify_status:
            rectify_status = next_status
            rectify_status_at = today

    comments = list(meta["comments"] or [])
    if body.comment is not None and body.comment.strip():
        comments.append({"text": body.comment.strip(), "at": today})

    row.remarks = pack_payload(
        meta["hours"],
        meta["unit"],
        True,
        meta["issue_description"],
        meta["remarks"],
        meta["update"],
        observed_at=observed_at,
        rectify_status=rectify_status,
        rectify_status_at=rectify_status_at,
        comments=comments,
        manpower=meta.get("manpower") or "0",
        daily=meta.get("daily") or [],
        idle_reason=meta.get("idle_reason") or "",
    )
    db.flush()
    plan = db.get(DailyPlan, row.plan_id)
    activity = ""
    if plan:
        activity = plan.equipment_tag or plan.job_description or plan.plan_code
    return IssueOut(
        id=row.id,
        plan_id=row.plan_id,
        activity=activity,
        issue_description=meta["issue_description"],
        observed_at=observed_at,
        rectify_status=rectify_status,
        rectify_status_at=rectify_status_at,
        comments=comments,
    )
