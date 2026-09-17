from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, get_auth, require_site
from app.models import (
    Attendance,
    Employee,
    EmployeeStatus,
    EveningType,
    MorningStatus,
    Site,
)
from app.schemas import AttendanceRowOut, EveningIn, MorningIn

router = APIRouter(prefix="/sites/{site_id}/attendance", tags=["attendance"])


def _today(auth: AuthContext):
    return datetime.now(auth.tz()).date()


def _rows_for_date(db: Session, site_id, work_date, active_only: bool = False) -> list[AttendanceRowOut]:
    q = db.query(Employee).filter(Employee.site_id == site_id)
    if active_only:
        q = q.filter(Employee.status == EmployeeStatus.ACTIVE.value)
    employees = q.order_by(Employee.employee_code).all()
    existing = {
        row.employee_id: row
        for row in db.query(Attendance).filter(
            Attendance.site_id == site_id,
            Attendance.work_date == work_date,
        )
    }
    out: list[AttendanceRowOut] = []
    for emp in employees:
        rec = existing.get(emp.id)
        out.append(
            AttendanceRowOut(
                employee_id=emp.id,
                employee_code=emp.employee_code,
                name=emp.name,
                designation=emp.designation,
                morning_status=rec.morning_status if rec else None,
                morning_at=rec.morning_at if rec else None,
                evening_type=rec.evening_type if rec else None,
                evening_at=rec.evening_at if rec else None,
                ot_hours=rec.ot_hours if rec else Decimal("0"),
            )
        )
    return out


@router.get("", response_model=list[AttendanceRowOut])
def get_attendance(
    work_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    site: Site = Depends(require_site),
) -> list[AttendanceRowOut]:
    day = work_date or _today(auth)
    return _rows_for_date(db, site.id, day, active_only=True)


@router.post("/morning", response_model=list[AttendanceRowOut])
def save_morning(
    body: MorningIn,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    site: Site = Depends(require_site),
) -> list[AttendanceRowOut]:
    day = _today(auth)
    now = datetime.now(auth.tz())
    allowed = {MorningStatus.PRESENT.value, MorningStatus.ABSENT.value}
    for answer in body.answers:
        if answer.status not in allowed:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Morning status must be Present or Absent")
        employee = db.get(Employee, answer.employee_id)
        if (
            not employee
            or employee.site_id != site.id
            or employee.status != EmployeeStatus.ACTIVE.value
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
        rec = (
            db.query(Attendance)
            .filter(
                Attendance.site_id == site.id,
                Attendance.employee_id == employee.id,
                Attendance.work_date == day,
            )
            .first()
        )
        if rec:
            rec.morning_status = answer.status
            rec.morning_at = now
            rec.marked_by_morning_id = auth.user.id
            if answer.status != MorningStatus.PRESENT.value:
                rec.evening_type = None
                rec.evening_at = None
                rec.ot_hours = Decimal("0")
                rec.marked_by_evening_id = None
        else:
            db.add(
                Attendance(
                    site_id=site.id,
                    employee_id=employee.id,
                    work_date=day,
                    morning_status=answer.status,
                    morning_at=now,
                    marked_by_morning_id=auth.user.id,
                    ot_hours=Decimal("0"),
                )
            )
    db.flush()
    return _rows_for_date(db, site.id, day, active_only=True)


@router.post("/evening", response_model=list[AttendanceRowOut])
def save_evening(
    body: EveningIn,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    site: Site = Depends(require_site),
) -> list[AttendanceRowOut]:
    day = _today(auth)
    now = datetime.now(auth.tz())
    allowed = {EveningType.FULL_DAY.value, EveningType.HALF_DAY.value}
    for answer in body.answers:
        if answer.evening_type not in allowed:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Evening must be full_day or half_day")
        if answer.ot_hours < 0 or answer.ot_hours > 24:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "OT hours must be between 0 and 24")
        employee = db.get(Employee, answer.employee_id)
        if (
            not employee
            or employee.site_id != site.id
            or employee.status != EmployeeStatus.ACTIVE.value
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
        rec = (
            db.query(Attendance)
            .filter(
                Attendance.site_id == site.id,
                Attendance.employee_id == employee.id,
                Attendance.work_date == day,
            )
            .first()
        )
        if not rec or rec.morning_status != MorningStatus.PRESENT.value:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Evening confirmation is only for employees marked Present in the morning",
            )
        rec.evening_type = answer.evening_type
        rec.evening_at = now
        rec.ot_hours = answer.ot_hours
        rec.marked_by_evening_id = auth.user.id
    db.flush()
    return _rows_for_date(db, site.id, day, active_only=True)
