from __future__ import annotations

from calendar import monthrange
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_owner, require_site
from app.excel_reports import attendance_workbook, progress_workbook
from app.models import Attendance, DailyPlan, DailyProgress, Employee, MasterEquipment, NonPoJob, Site, User
from app.routers.progress import unpack_hours

router = APIRouter(prefix="/sites/{site_id}/reports", tags=["reports"])


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _file(content: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/attendance")
def download_attendance(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    site: Site = Depends(require_site),
    _owner=Depends(require_owner),
):
    start, end = _month_bounds(year, month)
    attendance = (
        db.query(Attendance)
        .filter(
            Attendance.site_id == site.id,
            Attendance.work_date >= start,
            Attendance.work_date <= end,
        )
        .all()
    )
    employee_ids = {row.employee_id for row in attendance}
    employees = (
        db.query(Employee)
        .filter(Employee.site_id == site.id)
        .order_by(Employee.employee_code)
        .all()
    )
    extra = []
    if employee_ids:
        extra = (
            db.query(Employee)
            .filter(Employee.id.in_(employee_ids), Employee.site_id != site.id)
            .all()
        )
    by_id: dict[UUID, Employee] = {emp.id: emp for emp in employees}
    for emp in extra:
        by_id[emp.id] = emp
    ordered = sorted(by_id.values(), key=lambda emp: emp.employee_code)
    payload = [
        {
            "id": str(emp.id),
            "employee_code": emp.employee_code,
            "name": emp.name,
            "designation": emp.designation,
        }
        for emp in ordered
    ]
    marks: dict[tuple[str, int], dict] = {}
    for row in attendance:
        mark, ot = _attendance_mark(row)
        marks[(str(row.employee_id), row.work_date.day)] = {"mark": mark, "ot": ot}
    content = attendance_workbook(site.name, year, month, payload, marks)
    return _file(content, f"{site.code}-attendance-{year}-{month:02d}.xlsx")


def _attendance_mark(row: Attendance) -> tuple[str, float]:
    ot = float(row.ot_hours or 0)
    if row.evening_type == "full_day":
        return "F", ot
    if row.evening_type == "half_day":
        return "H", ot
    if row.morning_status == "Absent":
        return "A", 0.0
    if row.morning_status == "Present":
        return "", ot
    return "", 0.0


@router.get("/progress")
def download_progress(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    site: Site = Depends(require_site),
    _owner=Depends(require_owner),
):
    start, end = _month_bounds(year, month)
    plans = (
        db.query(DailyPlan)
        .filter(DailyPlan.site_id == site.id, DailyPlan.work_date >= start, DailyPlan.work_date <= end, DailyPlan.plan_code != "IDLE")
        .all()
    )
    plan_map = {plan.id: plan for plan in plans}
    progress = (
        db.query(DailyProgress)
        .filter(DailyProgress.site_id == site.id, DailyProgress.plan_id.in_(plan_map.keys()) if plan_map else False)
        .all()
        if plan_map
        else []
    )
    users = {user.id: user.name for user in db.query(User).filter(User.company_id == site.company_id)}
    progress_rows = []
    for row in sorted(progress, key=lambda item: item.reported_at or start):
        plan = plan_map.get(row.plan_id)
        if not plan:
            continue
        hours, remarks = unpack_hours(row.remarks or "")
        progress_rows.append(
            [
                plan.work_date.isoformat(),
                plan.plan_code,
                plan.classification,
                plan.po_ref,
                plan.equipment_tag,
                plan.job_description,
                row.status,
                row.erection_front_status,
                float(row.quantity or 0),
                float(hours),
                remarks,
                row.photo_ref,
                users.get(row.reported_by, ""),
            ]
        )
    master = (
        db.query(MasterEquipment)
        .filter(MasterEquipment.site_id == site.id)
        .order_by(MasterEquipment.po_ref, MasterEquipment.equipment_tag)
        .all()
    )
    master_rows = [
        [
            row.po_ref,
            row.equipment_tag,
            row.description,
            row.unit,
            float(row.po_quantity or 0),
            float(row.completed_quantity or 0),
            float(row.remaining_quantity or 0),
            row.status,
            row.erection_front_status,
            row.remarks,
            row.photo_ref,
        ]
        for row in master
    ]
    non_po = (
        db.query(NonPoJob)
        .filter(NonPoJob.site_id == site.id, NonPoJob.work_date >= start, NonPoJob.work_date <= end)
        .order_by(NonPoJob.work_date)
        .all()
    )
    non_po_rows = [
        [
            row.work_date.isoformat(),
            row.clarification,
            row.job_description,
            row.allocated_workers,
            row.status,
            row.remarks,
            row.photo_ref,
        ]
        for row in non_po
    ]
    content = progress_workbook(site.name, year, month, progress_rows, master_rows, non_po_rows)
    return _file(content, f"{site.code}-progress-{year}-{month:02d}.xlsx")
