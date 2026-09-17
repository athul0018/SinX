from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, get_auth, require_site
from app.models import AuditLog, Employee, EmployeeStatus, Site
from app.schemas import EmployeeIn, EmployeeOut, EmployeeTransferIn

router = APIRouter(prefix="/sites/{site_id}/employees", tags=["employees"])


@router.get("", response_model=list[EmployeeOut])
def list_employees(
    db: Session = Depends(get_db),
    site: Site = Depends(require_site),
) -> list[Employee]:
    return (
        db.query(Employee)
        .filter(Employee.site_id == site.id)
        .order_by(Employee.employee_code)
        .all()
    )


@router.post("", response_model=EmployeeOut)
def add_employee(
    body: EmployeeIn,
    db: Session = Depends(get_db),
    site: Site = Depends(require_site),
) -> Employee:
    code = body.employee_code.strip()
    exists = (
        db.query(Employee)
        .filter(Employee.site_id == site.id, Employee.employee_code == code)
        .first()
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Employee ID already exists.")
    employee = Employee(
        site_id=site.id,
        employee_code=code,
        name=body.name.strip(),
        designation=body.designation.strip(),
        status=EmployeeStatus.ACTIVE.value,
        joining_date=body.joining_date,
    )
    db.add(employee)
    db.flush()
    return employee


@router.patch("/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: UUID,
    body: EmployeeIn,
    db: Session = Depends(get_db),
    site: Site = Depends(require_site),
) -> Employee:
    employee = db.get(Employee, employee_id)
    if not employee or employee.site_id != site.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee ID not found.")
    new_code = body.employee_code.strip()
    clash = (
        db.query(Employee)
        .filter(
            Employee.site_id == site.id,
            Employee.employee_code == new_code,
            Employee.id != employee.id,
        )
        .first()
    )
    if clash:
        raise HTTPException(status.HTTP_409_CONFLICT, "Employee ID already exists.")
    employee.employee_code = new_code
    employee.name = body.name.strip()
    employee.designation = body.designation.strip()
    employee.joining_date = body.joining_date
    return employee


@router.post("/{employee_id}/deactivate", response_model=EmployeeOut)
def deactivate_employee(
    employee_id: UUID,
    db: Session = Depends(get_db),
    site: Site = Depends(require_site),
) -> Employee:
    employee = db.get(Employee, employee_id)
    if not employee or employee.site_id != site.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee ID not found.")
    employee.status = EmployeeStatus.INACTIVE.value
    return employee


@router.post("/{employee_id}/transfer", response_model=EmployeeOut)
def transfer_employee(
    employee_id: UUID,
    body: EmployeeTransferIn,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth),
    site: Site = Depends(require_site),
) -> Employee:
    employee = db.get(Employee, employee_id)
    if not employee or employee.site_id != site.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee ID not found.")
    dest = db.get(Site, body.to_site_id)
    if not dest or dest.company_id != auth.company.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Destination site not found")
    if dest.id == site.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Employee is already on this site")
    clash = (
        db.query(Employee)
        .filter(Employee.site_id == dest.id, Employee.employee_code == employee.employee_code)
        .first()
    )
    if clash and clash.status == EmployeeStatus.ACTIVE.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "That employee ID already exists on the destination site")
    if clash:
        clash.name = employee.name
        clash.designation = employee.designation
        clash.joining_date = employee.joining_date
        clash.status = EmployeeStatus.ACTIVE.value
        employee.status = EmployeeStatus.INACTIVE.value
        moved = clash
    else:
        employee.site_id = dest.id
        moved = employee
    db.add(
        AuditLog(
            company_id=auth.company.id,
            site_id=site.id,
            user_id=auth.user.id,
            action="employee_transfer",
            entity="employee",
            entity_id=str(employee.id),
            payload={"from_site_id": str(site.id), "to_site_id": str(dest.id)},
        )
    )
    db.flush()
    return moved
