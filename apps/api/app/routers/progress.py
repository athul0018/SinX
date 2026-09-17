from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, get_auth, require_site
from app.drive import upload_plan_photo
from app.models import (
    Classification,
    DailyPlan,
    DailyProgress,
    ErectionFrontStatus,
    ErectionStatus,
    MasterEquipment,
    NonPoJob,
    PlanStatus,
    ProgressPhoto,
    Site,
)
from app.routers.plans import _route_target, pack_meta
from app.schemas import IdleOut, ProgressOut

router = APIRouter(prefix="/sites/{site_id}/progress", tags=["progress"])

IDLE_PLAN_CODE = "IDLE"
IDLE_STATUS = "Idle"

HOURS_RE = re.compile(r"^\[(\d+(?:\.\d+)?)h\]\s*")

PLAN_STATUS_MAP = {
    "hold": PlanStatus.HOLD.value,
    "progress": PlanStatus.IN_PROGRESSING.value,
    "progressing": PlanStatus.IN_PROGRESSING.value,
    "in progressing": PlanStatus.IN_PROGRESSING.value,
    "completed": PlanStatus.COMPLETED.value,
    PlanStatus.HOLD.value.lower(): PlanStatus.HOLD.value,
    PlanStatus.IN_PROGRESSING.value.lower(): PlanStatus.IN_PROGRESSING.value,
    PlanStatus.COMPLETED.value.lower(): PlanStatus.COMPLETED.value,
}


def unpack_hours(remarks: str) -> tuple[Decimal, str]:
    meta = unpack_payload(remarks)
    return meta["hours"], meta["remarks"]


def _comments(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        out.append({"text": text, "at": str(item.get("at") or "")})
    return out


def unpack_payload(raw: str) -> dict:
    text = raw or ""
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "remarks" in data:
            status = str(data.get("rectify_status") or data.get("issue_status") or "").strip()
            if status.lower() == "closed":
                status = "Closed"
            elif status.lower() in {"raised", "rised", "open"} or (data.get("issue") or data.get("has_issue")):
                status = "Raised" if (data.get("issue") or data.get("has_issue")) else status
            return {
                "hours": Decimal(str(data.get("hours") or 0)),
                "unit": str(data.get("unit") or ""),
                "has_issue": bool(data.get("issue") or data.get("has_issue")),
                "issue_description": str(data.get("issue_desc") or data.get("issue_description") or ""),
                "remarks": str(data.get("remarks") or ""),
                "update": str(data.get("update") or ""),
                "observed_at": str(data.get("observed_at") or ""),
                "rectify_status": status if status in {"Raised", "Closed"} else ("Raised" if (data.get("issue") or data.get("has_issue")) else ""),
                "rectify_status_at": str(data.get("rectify_status_at") or data.get("status_at") or ""),
                "comments": _comments(data.get("comments")),
                "manpower": str(data.get("manpower") or "0"),
                "idle_reason": str(data.get("idle_reason") or data.get("reason") or ""),
                "daily": data.get("daily") if isinstance(data.get("daily"), list) else [],
            }
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    match = HOURS_RE.match(text)
    hours = Decimal(match.group(1)) if match else Decimal("0")
    remarks = HOURS_RE.sub("", text, count=1) if match else text
    return {
        "hours": hours,
        "unit": "",
        "has_issue": False,
        "issue_description": "",
        "remarks": remarks,
        "update": "",
        "observed_at": "",
        "rectify_status": "",
        "rectify_status_at": "",
        "comments": [],
        "manpower": "0",
        "idle_reason": "",
        "daily": [],
    }


def pack_payload(
    hours: Decimal,
    unit: str,
    has_issue: bool,
    issue_description: str,
    remarks: str,
    update: str,
    *,
    observed_at: str = "",
    rectify_status: str = "",
    rectify_status_at: str = "",
    comments: list[dict] | None = None,
    manpower: str = "0",
    daily: list[dict] | None = None,
    idle_reason: str = "",
) -> str:
    return json.dumps(
        {
            "hours": str(hours),
            "unit": unit.strip(),
            "issue": has_issue,
            "issue_desc": issue_description.strip(),
            "remarks": remarks.strip(),
            "update": update.strip(),
            "observed_at": observed_at.strip(),
            "rectify_status": rectify_status.strip(),
            "rectify_status_at": rectify_status_at.strip(),
            "comments": comments or [],
            "manpower": str(manpower).strip() or "0",
            "idle_reason": idle_reason.strip(),
            "daily": daily or [],
        }
    )


def is_idle_plan(plan: DailyPlan | None) -> bool:
    return bool(plan and plan.plan_code == IDLE_PLAN_CODE)


def ensure_idle_plan(db: Session, site: Site, auth: AuthContext) -> DailyPlan:
    plan = (
        db.query(DailyPlan)
        .filter(DailyPlan.site_id == site.id, DailyPlan.plan_code == IDLE_PLAN_CODE)
        .first()
    )
    if plan:
        return plan
    day = datetime.now(auth.tz()).date()
    plan = DailyPlan(
        site_id=site.id,
        plan_code=IDLE_PLAN_CODE,
        work_date=day,
        po_ref="N/A",
        classification=Classification.NOT_UNDER_PO.value,
        job_description="Idle workers",
        allocated_workers=pack_meta("", False, ""),
        status=IDLE_STATUS,
        created_by=auth.user.id,
        planned_at=datetime.now(auth.tz()),
    )
    db.add(plan)
    db.flush()
    return plan


def progress_out(row: DailyProgress, plan: DailyPlan | None = None) -> ProgressOut:
    meta = unpack_payload(row.remarks)
    idle = is_idle_plan(plan)
    activity = "Idle workers" if idle else ""
    if plan and not idle:
        activity = plan.equipment_tag or plan.job_description or plan.plan_code
    return ProgressOut(
        id=row.id,
        plan_id=row.plan_id,
        status=row.status,
        erection_front_status=row.erection_front_status or "",
        quantity=row.quantity,
        hours=meta["hours"],
        unit=meta["unit"],
        has_issue=meta["has_issue"],
        issue_description=meta["issue_description"],
        update=meta["update"],
        remarks=meta["remarks"] or meta["update"],
        photo_ref=row.photo_ref or "",
        reported_by=row.reported_by,
        activity=activity,
        observed_at=meta["observed_at"],
        rectify_status=meta["rectify_status"],
        rectify_status_at=meta["rectify_status_at"],
        comments=meta["comments"],
        manpower=meta.get("manpower") or "0",
        plan_status=IDLE_STATUS if idle else (plan.status if plan else ""),
        daily=meta.get("daily") or [],
        kind="idle" if idle else "work",
        reason=meta.get("idle_reason") or "",
    )


def resolve_plan_status(value: str) -> str:
    key = value.strip().lower()
    mapped = PLAN_STATUS_MAP.get(key)
    if not mapped:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Status must be hold, progress, or completed")
    return mapped


@router.get("", response_model=list[ProgressOut])
def list_progress(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    site: Site = Depends(require_site),
) -> list[ProgressOut]:
    rows = (
        db.query(DailyProgress)
        .filter(DailyProgress.site_id == site.id)
        .order_by(DailyProgress.reported_at.desc())
        .limit(500)
        .all()
    )
    plans = {row.id: row for row in db.query(DailyPlan).filter(DailyPlan.site_id == site.id).all()}
    return [progress_out(row, plans.get(row.plan_id)) for row in rows if not is_idle_plan(plans.get(row.plan_id))]


@router.get("/today", response_model=list[ProgressOut])
def list_today_progress(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    site: Site = Depends(require_site),
) -> list[ProgressOut]:
    today = datetime.now(auth.tz()).date().isoformat()
    rows = (
        db.query(DailyProgress)
        .filter(DailyProgress.site_id == site.id)
        .order_by(DailyProgress.reported_at.desc())
        .limit(500)
        .all()
    )
    plans = {row.id: row for row in db.query(DailyPlan).filter(DailyPlan.site_id == site.id).all()}
    out: list[ProgressOut] = []
    for row in rows:
        plan = plans.get(row.plan_id)
        if plan and plan.status == PlanStatus.COMPLETED.value:
            continue
        meta = unpack_payload(row.remarks)
        today_row = next((item for item in (meta.get("daily") or []) if isinstance(item, dict) and item.get("date") == today), None)
        reported = row.reported_at.date().isoformat() if row.reported_at else ""
        if is_idle_plan(plan):
            if not today_row:
                continue
        elif not today_row and reported != today:
            continue
        item = progress_out(row, plan)
        if today_row:
            item.manpower = str(today_row.get("manpower") or item.manpower)
            item.quantity = Decimal(str(today_row.get("quantity") or item.quantity or 0))
            item.unit = str(today_row.get("unit") or item.unit)
            item.update = str(today_row.get("update") or item.update)
            item.remarks = str(today_row.get("remarks") or item.remarks)
            item.plan_status = str(today_row.get("status") or item.plan_status)
            item.reason = str(today_row.get("reason") or item.reason)
        out.append(item)
    return out


@router.get("/idle", response_model=IdleOut)
def get_idle_workers(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    site: Site = Depends(require_site),
) -> IdleOut:
    today = datetime.now(auth.tz()).date().isoformat()
    plan = (
        db.query(DailyPlan)
        .filter(DailyPlan.site_id == site.id, DailyPlan.plan_code == IDLE_PLAN_CODE)
        .first()
    )
    if not plan:
        return IdleOut()
    row = db.query(DailyProgress).filter(DailyProgress.plan_id == plan.id).first()
    if not row:
        return IdleOut()
    meta = unpack_payload(row.remarks)
    today_row = next((item for item in (meta.get("daily") or []) if isinstance(item, dict) and item.get("date") == today), None)
    if not today_row:
        return IdleOut()
    return IdleOut(
        manpower=str(today_row.get("manpower") or "0"),
        reason=str(today_row.get("reason") or ""),
        remarks=str(today_row.get("remarks") or ""),
    )


@router.post("/idle", response_model=ProgressOut)
def save_idle_workers(
    manpower: str = Form(...),
    reason: str = Form(...),
    remarks: str = Form(""),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    site: Site = Depends(require_site),
) -> ProgressOut:
    try:
        manpower_n = Decimal(str(manpower or 0))
    except Exception:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Manpower must be a number")
    if manpower_n <= 0:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Enter idle manpower")
    reason_text = reason.strip()
    if not reason_text:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Enter the idle reason")
    plan = ensure_idle_plan(db, site, auth)
    existing = db.query(DailyProgress).filter(DailyProgress.plan_id == plan.id).first()
    previous = unpack_payload(existing.remarks) if existing else unpack_payload("")
    today = datetime.now(auth.tz()).date().isoformat()
    daily = [item for item in (previous.get("daily") or []) if isinstance(item, dict) and item.get("date") != today]
    daily.append(
        {
            "date": today,
            "manpower": str(manpower_n),
            "quantity": "0",
            "unit": "",
            "update": reason_text,
            "status": IDLE_STATUS,
            "remarks": remarks.strip(),
            "reason": reason_text,
        }
    )
    stored = pack_payload(
        Decimal("0"),
        "",
        False,
        "",
        remarks,
        reason_text,
        manpower=str(manpower_n),
        daily=daily,
        idle_reason=reason_text,
    )
    if existing:
        existing.quantity = Decimal("0")
        existing.remarks = stored
        existing.status = IDLE_STATUS
        existing.reported_by = auth.user.id
        existing.reported_at = datetime.now(auth.tz())
        progress = existing
    else:
        progress = DailyProgress(
            site_id=site.id,
            plan_id=plan.id,
            status=IDLE_STATUS,
            erection_front_status="",
            quantity=Decimal("0"),
            remarks=stored,
            photo_ref="",
            reported_by=auth.user.id,
            reported_at=datetime.now(auth.tz()),
        )
        db.add(progress)
    plan.status = IDLE_STATUS
    db.flush()
    return progress_out(progress, plan)


@router.post("", response_model=ProgressOut)
def save_progress(
    plan_id: UUID = Form(...),
    status: str = Form("progress"),
    erection_front_status: str = Form(""),
    quantity: Decimal = Form(Decimal("0")),
    unit: str = Form(""),
    update: str = Form(""),
    has_issue: str = Form("no"),
    issue_description: str = Form(""),
    hours: Decimal = Form(Decimal("0")),
    remarks: str = Form(""),
    manpower: str = Form("0"),
    photos: list[UploadFile] | None = File(default=None),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    site: Site = Depends(require_site),
) -> ProgressOut:
    if quantity < 0:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Quantity cannot be negative")
    if hours < 0 or hours > 24:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Hours must be between 0 and 24")
    try:
        manpower_n = Decimal(str(manpower or 0))
    except Exception:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Manpower must be a number")
    if manpower_n < 0:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Manpower cannot be negative")
    plan = db.get(DailyPlan, plan_id)
    if not plan or plan.site_id != site.id:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Plan not found")
    if is_idle_plan(plan):
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Use idle workers to record idle manpower")

    issue = str(has_issue).strip().lower() in {"yes", "true", "1"}
    if issue and not issue_description.strip():
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Describe the issue")

    plan_status = resolve_plan_status(status)
    erection = (
        ErectionStatus.ERECTION_COMPLETED.value
        if plan_status == PlanStatus.COMPLETED.value
        else ErectionStatus.PROGRESSING.value
    )
    if plan_status == PlanStatus.HOLD.value:
        erection = ErectionStatus.NOT_AVAILABLE.value
    front = erection_front_status.strip() or ErectionFrontStatus.CIVIL_WORK_IN_PROGRESS.value

    is_po = plan.classification == Classification.UNDER_PO.value
    photo_links: list[str] = []
    uploads = [item for item in (photos or []) if item and item.filename]
    if len(uploads) > 2:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Maximum 2 photos")
    for index, upload in enumerate(uploads, start=1):
        data = upload.file.read()
        filename = f"{plan.plan_code}_{index}.jpg"
        try:
            photo_links.append(upload_plan_photo(data, filename, upload.content_type or "image/jpeg"))
        except Exception:
            raise HTTPException(
                http_status.HTTP_503_SERVICE_UNAVAILABLE,
                "Photo upload is unavailable. Submit without photos or configure Drive.",
            ) from None

    latest_photo = photo_links[-1] if photo_links else ""
    existing = db.query(DailyProgress).filter(DailyProgress.plan_id == plan.id).first()
    previous_qty = existing.quantity if existing else Decimal("0")
    previous = unpack_payload(existing.remarks) if existing else unpack_payload("")
    today = datetime.now(auth.tz()).date().isoformat()
    observed_at = previous.get("observed_at") or ""
    rectify_status = previous.get("rectify_status") or ""
    rectify_status_at = previous.get("rectify_status_at") or ""
    comments = previous.get("comments") or []
    daily = [item for item in (previous.get("daily") or []) if isinstance(item, dict)]
    day_entry = {
        "date": today,
        "manpower": str(manpower_n),
        "quantity": str(quantity),
        "unit": unit.strip(),
        "update": update.strip(),
        "status": plan_status,
        "remarks": remarks.strip(),
    }
    daily = [item for item in daily if item.get("date") != today]
    daily.append(day_entry)
    if issue:
        if not observed_at:
            observed_at = today
        if rectify_status != "Closed":
            if rectify_status != "Raised":
                rectify_status_at = today
            rectify_status = "Raised"
        if issue_description.strip() and not previous.get("issue_description"):
            # keep description; comments stay as-is
            pass
    stored_remarks = pack_payload(
        Decimal(hours),
        unit,
        issue,
        issue_description or previous.get("issue_description") or "",
        remarks,
        update,
        observed_at=observed_at if issue else previous.get("observed_at") or "",
        rectify_status=rectify_status if issue else previous.get("rectify_status") or "",
        rectify_status_at=rectify_status_at if issue else previous.get("rectify_status_at") or "",
        comments=comments,
        manpower=str(manpower_n),
        daily=daily,
        idle_reason=previous.get("idle_reason") or "",
    )

    if existing:
        existing.status = erection
        existing.erection_front_status = front
        existing.quantity = Decimal(quantity)
        existing.remarks = stored_remarks
        if latest_photo:
            existing.photo_ref = latest_photo
        existing.reported_by = auth.user.id
        existing.reported_at = datetime.now(auth.tz())
        progress = existing
    else:
        progress = DailyProgress(
            site_id=site.id,
            plan_id=plan.id,
            status=erection,
            erection_front_status=front,
            quantity=Decimal(quantity),
            remarks=stored_remarks,
            photo_ref=latest_photo,
            reported_by=auth.user.id,
            reported_at=datetime.now(auth.tz()),
            route_target=_route_target(plan.classification, plan.clarification),
        )
        db.add(progress)

    plan.status = plan_status
    db.flush()
    for link in photo_links:
        db.add(ProgressPhoto(progress_id=progress.id, storage_key=link, content_type="image/jpeg"))

    if is_po and plan.equipment_id:
        equipment = db.get(MasterEquipment, plan.equipment_id)
        if equipment and equipment.site_id == site.id:
            equipment.status = plan_status
            equipment.erection_front_status = front
            current = equipment.completed_quantity or Decimal("0")
            equipment.completed_quantity = current - (previous_qty or Decimal("0")) + Decimal(quantity)
            if equipment.completed_quantity < 0:
                equipment.completed_quantity = Decimal("0")
            remaining = (equipment.po_quantity or Decimal("0")) - equipment.completed_quantity
            equipment.remaining_quantity = remaining if remaining > 0 else Decimal("0")
            if remarks.strip():
                equipment.remarks = remarks.strip()
            if latest_photo:
                equipment.photo_ref = latest_photo
    else:
        non_po = db.query(NonPoJob).filter(NonPoJob.plan_id == plan.id).first()
        if non_po:
            non_po.status = plan_status
            non_po.remarks = remarks.strip() or issue_description.strip()
            if latest_photo:
                non_po.photo_ref = latest_photo

    return progress_out(progress, plan)
