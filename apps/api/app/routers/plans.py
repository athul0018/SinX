from __future__ import annotations

import json
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, get_auth, require_owner, require_site
from app.pagination import list_limit, list_offset
from app.models import (
    Classification,
    Clarification,
    DailyPlan,
    MasterEquipment,
    NonPoJob,
    PlanStatus,
    Site,
)
from app.schemas import EquipmentIn, EquipmentOut, PlanIn, PlanOut

router = APIRouter(prefix="/sites/{site_id}", tags=["plans"])

PLAN_STATUSES = {
    PlanStatus.NOT_STARTED.value,
    PlanStatus.IN_PROGRESSING.value,
    PlanStatus.COMPLETED.value,
    PlanStatus.HOLD.value,
}


def _route_target(classification: str, clarification: str | None) -> str | None:
    if classification == Classification.UNDER_PO.value:
        return "po_works"
    if clarification == Clarification.LABOUR_SUPPLY.value:
        return "labour_supply"
    if clarification == Clarification.PO_AMENDMENT.value:
        return "po_amendment"
    return None


def pack_meta(requirement: str, ready: bool, comment: str) -> str:
    return json.dumps({"requirement": requirement, "ready": ready, "comment": comment})


def unpack_meta(raw: str) -> dict:
    try:
        data = json.loads(raw or "")
        if isinstance(data, dict) and "ready" in data:
            return {
                "requirement": str(data.get("requirement") or ""),
                "ready": bool(data.get("ready")),
                "comment": str(data.get("comment") or ""),
            }
    except (json.JSONDecodeError, TypeError):
        pass
    return {"requirement": raw or "", "ready": False, "comment": ""}


def normalize_status(value: str) -> str:
    if value == PlanStatus.PLANNED.value:
        return PlanStatus.NOT_STARTED.value
    if value in PLAN_STATUSES:
        return value
    return PlanStatus.NOT_STARTED.value


def to_plan_out(plan: DailyPlan) -> PlanOut:
    meta = unpack_meta(plan.allocated_workers)
    item = PlanOut.model_validate(plan)
    item.status = normalize_status(plan.status)
    item.requirement = meta["requirement"]
    item.ready = meta["ready"]
    item.comment = meta["comment"]
    return item


def apply_activity(db: Session, site: Site, body: PlanIn) -> tuple[UUID | None, str, str, str, str]:
    po_ref = (body.po_ref or "N/A").strip() or "N/A"
    tag = body.equipment_tag.strip()
    desc = body.equipment_description.strip()
    equipment_id = None
    job = body.job_description.strip()
    if body.classification == Classification.UNDER_PO.value:
        if not body.equipment_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Select an activity from the master list")
        equipment = db.get(MasterEquipment, body.equipment_id)
        if not equipment or equipment.site_id != site.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipment not found")
        equipment_id = equipment.id
        po_ref = equipment.po_ref
        tag = equipment.equipment_tag
        desc = equipment.description
        job = desc or tag
    else:
        if not job:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enter the activity name")
        tag = ""
        desc = ""
    return equipment_id, po_ref, tag, desc, job


@router.get("/equipment", response_model=list[EquipmentOut])
def search_equipment(
    q: str = Query(default=""),
    db: Session = Depends(get_db),
    site: Site = Depends(require_site),
) -> list[MasterEquipment]:
    query = db.query(MasterEquipment).filter(MasterEquipment.site_id == site.id)
    text = q.strip().lower()
    rows = query.order_by(MasterEquipment.po_ref, MasterEquipment.equipment_tag).limit(400).all()
    if not text:
        return rows[:200]
    matched = [
        row
        for row in rows
        if text in " ".join([row.po_ref, row.equipment_tag, row.description]).lower()
    ]
    return matched[:50]


@router.post("/equipment", response_model=EquipmentOut)
def add_equipment(
    body: EquipmentIn,
    db: Session = Depends(get_db),
    site: Site = Depends(require_site),
    _owner: AuthContext = Depends(require_owner),
) -> MasterEquipment:
    row = MasterEquipment(
        site_id=site.id,
        po_ref=body.po_ref.strip(),
        equipment_tag=body.equipment_tag.strip(),
        description=body.description.strip(),
    )
    db.add(row)
    db.flush()
    return row


@router.get("/plans", response_model=list[PlanOut])
def list_plans(
    work_date: date | None = Query(default=None),
    open_only: bool = Query(default=False, alias="open"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    site: Site = Depends(require_site),
    limit: int = Depends(list_limit),
    offset: int = Depends(list_offset),
) -> list[PlanOut]:
    query = db.query(DailyPlan).filter(DailyPlan.site_id == site.id, DailyPlan.plan_code != "IDLE")
    if open_only:
        query = query.filter(DailyPlan.status != PlanStatus.COMPLETED.value)
    else:
        day = work_date or datetime.now(auth.tz()).date()
        query = query.filter(DailyPlan.work_date == day)
    plans = query.order_by(DailyPlan.planned_at).offset(offset).limit(limit).all()
    return [to_plan_out(plan) for plan in plans]


@router.post("/plans", response_model=PlanOut)
def create_plan(
    body: PlanIn,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    site: Site = Depends(require_site),
) -> PlanOut:
    if body.classification not in {Classification.UNDER_PO.value, Classification.NOT_UNDER_PO.value}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid category")
    equipment_id, po_ref, tag, desc, job = apply_activity(db, site, body)
    plan_status = normalize_status(body.status)
    requirement = (body.requirement or body.allocated_workers or "").strip()
    day = datetime.now(auth.tz()).date()
    count = (
        db.query(DailyPlan)
        .filter(DailyPlan.site_id == site.id, DailyPlan.work_date == day, DailyPlan.plan_code != "IDLE")
        .count()
    )
    plan = DailyPlan(
        site_id=site.id,
        plan_code=f"PLAN-{day:%Y%m%d}-{count + 1:03d}",
        work_date=day,
        po_ref=po_ref,
        equipment_id=equipment_id,
        equipment_tag=tag,
        equipment_description=desc,
        classification=body.classification,
        clarification=None,
        job_description=job,
        allocated_workers=pack_meta(requirement, body.ready, body.comment.strip()),
        status=plan_status,
        created_by=auth.user.id,
        planned_at=datetime.now(auth.tz()),
    )
    db.add(plan)
    db.flush()
    if body.classification == Classification.NOT_UNDER_PO.value:
        db.add(
            NonPoJob(
                site_id=site.id,
                plan_id=plan.id,
                work_date=day,
                clarification="",
                job_description=job,
                allocated_workers=requirement,
                created_by=auth.user.id,
            )
        )
    return to_plan_out(plan)


@router.patch("/plans/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: UUID,
    body: PlanIn,
    db: Session = Depends(get_db),
    site: Site = Depends(require_site),
) -> PlanOut:
    plan = db.get(DailyPlan, plan_id)
    if not plan or plan.site_id != site.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")
    if body.classification not in {Classification.UNDER_PO.value, Classification.NOT_UNDER_PO.value}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid category")
    equipment_id, po_ref, tag, desc, job = apply_activity(db, site, body)
    requirement = (body.requirement or body.allocated_workers or "").strip()
    plan.classification = body.classification
    plan.equipment_id = equipment_id
    plan.po_ref = po_ref
    plan.equipment_tag = tag
    plan.equipment_description = desc
    plan.job_description = job
    plan.status = normalize_status(body.status)
    plan.allocated_workers = pack_meta(requirement, body.ready, body.comment.strip())
    plan.clarification = None
    return to_plan_out(plan)
