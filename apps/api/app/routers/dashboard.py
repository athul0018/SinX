from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, get_auth, require_site
from app.models import Attendance, DailyPlan, DailyProgress, Employee, EmployeeStatus, Site
from app.routers.progress import unpack_payload

router = APIRouter(prefix="/sites/{site_id}/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    site: Site = Depends(require_site),
) -> dict:
    day = datetime.now(auth.tz()).date()
    active = (
        db.query(Employee)
        .filter(Employee.site_id == site.id, Employee.status == EmployeeStatus.ACTIVE.value)
        .count()
    )
    active_ids = {
        row.id
        for row in db.query(Employee.id).filter(
            Employee.site_id == site.id, Employee.status == EmployeeStatus.ACTIVE.value
        )
    }
    rows = (
        db.query(Attendance)
        .filter(
            Attendance.site_id == site.id,
            Attendance.work_date == day,
            Attendance.employee_id.in_(active_ids) if active_ids else False,
        )
        .all()
    ) if active_ids else []
    morning_done = sum(1 for r in rows if r.morning_status)
    evening_done = sum(1 for r in rows if r.evening_type)
    present = sum(1 for r in rows if r.morning_status == "Present")
    ot_total = sum((r.ot_hours or Decimal("0")) for r in rows)
    plans = db.query(DailyPlan).filter(DailyPlan.site_id == site.id, DailyPlan.plan_code != "IDLE").all()
    completed = sum(1 for p in plans if p.status == "Completed")
    hold = sum(1 for p in plans if p.status == "Hold")
    progressing = sum(1 for p in plans if p.status == "In progressing")
    not_started = sum(1 for p in plans if p.status in {"Not started", "Planned"})
    today_plans = [p for p in plans if p.work_date == day]
    today_completed = sum(1 for p in today_plans if p.status == "Completed")
    planned = len(today_plans) - today_completed
    progress_rows = db.query(DailyProgress).filter(DailyProgress.site_id == site.id).all()
    issues_open = 0
    issues_closed = 0
    for row in progress_rows:
        meta = unpack_payload(row.remarks)
        if not meta["has_issue"]:
            continue
        if meta["rectify_status"] == "Closed":
            issues_closed += 1
        else:
            issues_open += 1
    return {
        "date": day.isoformat(),
        "site_name": site.name,
        "active_employees": active,
        "morning_marked": morning_done,
        "evening_marked": evening_done,
        "present": present,
        "ot_hours": float(ot_total),
        "absent": sum(1 for r in rows if r.morning_status == "Absent"),
        "site_code": site.code,
        "plans_open": planned,
        "plans_completed": today_completed,
        "progress_not_started": not_started,
        "progress_going": progressing,
        "progress_hold": hold,
        "progress_done": completed,
        "issues_open": issues_open,
        "issues_closed": issues_closed,
    }
