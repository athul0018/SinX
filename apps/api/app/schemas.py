from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class SiteOut(BaseModel):
    id: UUID
    name: str
    code: str
    status: str

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    global_role: str
    is_active: bool
    sites: list[SiteOut]


class TokenOut(BaseModel):
    token: str
    user: UserOut


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=50)


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = None


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    global_role: str
    site_ids: list[UUID] = []


class EmployeeIn(BaseModel):
    employee_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    designation: str = Field(min_length=1, max_length=200)
    joining_date: date

    @field_validator("joining_date")
    @classmethod
    def not_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Joining date cannot be in the future")
        return value


class EmployeeOut(BaseModel):
    id: UUID
    employee_code: str
    name: str
    designation: str
    status: str
    joining_date: date

    model_config = {"from_attributes": True}


class AttendanceRowOut(BaseModel):
    employee_id: UUID
    employee_code: str
    name: str
    designation: str
    morning_status: str | None
    morning_at: datetime | None
    evening_type: str | None
    evening_at: datetime | None
    ot_hours: Decimal


class MorningAnswer(BaseModel):
    employee_id: UUID
    status: str


class MorningIn(BaseModel):
    answers: list[MorningAnswer]


class EveningAnswer(BaseModel):
    employee_id: UUID
    evening_type: str
    ot_hours: Decimal = Field(default=Decimal("0"), ge=0, le=24)


class EveningIn(BaseModel):
    answers: list[EveningAnswer]


class EquipmentOut(BaseModel):
    id: UUID
    po_ref: str
    equipment_tag: str
    description: str
    unit: str = ""
    po_quantity: Decimal = Decimal("0")
    completed_quantity: Decimal = Decimal("0")
    remaining_quantity: Decimal = Decimal("0")
    status: str = ""
    erection_front_status: str = ""
    remarks: str = ""
    photo_ref: str = ""

    model_config = {"from_attributes": True}


class EquipmentIn(BaseModel):
    po_ref: str = ""
    equipment_tag: str = ""
    description: str = ""
    unit: str = ""
    po_quantity: Decimal = Decimal("0")
    completed_quantity: Decimal = Decimal("0")
    remaining_quantity: Decimal = Decimal("0")
    status: str = ""
    erection_front_status: str = ""
    remarks: str = ""
    photo_ref: str = ""


class EmployeeTransferIn(BaseModel):
    to_site_id: UUID


class PlanIn(BaseModel):
    classification: str
    clarification: str | None = None
    equipment_id: UUID | None = None
    equipment_tag: str = ""
    equipment_description: str = ""
    po_ref: str = "N/A"
    job_description: str = ""
    allocated_workers: str = ""
    requirement: str = ""
    ready: bool = False
    comment: str = ""
    status: str = "Not started"


class PlanOut(BaseModel):
    id: UUID
    plan_code: str
    work_date: date
    po_ref: str
    equipment_id: UUID | None = None
    equipment_tag: str
    equipment_description: str
    classification: str
    clarification: str | None
    job_description: str
    allocated_workers: str
    requirement: str = ""
    ready: bool = False
    comment: str = ""
    status: str
    created_by: UUID

    model_config = {"from_attributes": True}


class ProgressIn(BaseModel):
    plan_id: UUID
    status: str = ""
    erection_front_status: str = ""
    quantity: Decimal = Decimal("0")
    remarks: str = ""


class IssueComment(BaseModel):
    text: str
    at: str = ""


class DailyLog(BaseModel):
    date: str = ""
    manpower: str = "0"
    quantity: str = "0"
    unit: str = ""
    update: str = ""
    status: str = ""
    remarks: str = ""
    reason: str = ""


class ProgressOut(BaseModel):
    id: UUID
    plan_id: UUID
    status: str
    erection_front_status: str = ""
    quantity: Decimal
    hours: Decimal = Decimal("0")
    unit: str = ""
    update: str = ""
    has_issue: bool = False
    issue_description: str = ""
    remarks: str
    photo_ref: str = ""
    reported_by: UUID
    activity: str = ""
    observed_at: str = ""
    rectify_status: str = ""
    rectify_status_at: str = ""
    comments: list[IssueComment] = []
    manpower: str = "0"
    plan_status: str = ""
    daily: list[DailyLog] = []
    kind: str = "work"
    reason: str = ""

    model_config = {"from_attributes": True}


class IdleOut(BaseModel):
    manpower: str = "0"
    reason: str = ""
    remarks: str = ""


class IssueOut(BaseModel):
    id: UUID
    plan_id: UUID
    activity: str = ""
    issue_description: str = ""
    observed_at: str = ""
    rectify_status: str = "Raised"
    rectify_status_at: str = ""
    comments: list[IssueComment] = []


class IssueUpdateIn(BaseModel):
    observed_at: str | None = None
    rectify_status: str | None = None
    comment: str | None = None
