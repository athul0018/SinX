from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class UserRole(str, enum.Enum):
    OWNER = "OWNER"
    AUTHORIZED = "AUTHORIZED"


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class MorningStatus(str, enum.Enum):
    PRESENT = "Present"
    ABSENT = "Absent"


class EveningType(str, enum.Enum):
    FULL_DAY = "full_day"
    HALF_DAY = "half_day"


class PlanStatus(str, enum.Enum):
    NOT_STARTED = "Not started"
    IN_PROGRESSING = "In progressing"
    COMPLETED = "Completed"
    HOLD = "Hold"
    PLANNED = "Planned"


class Classification(str, enum.Enum):
    UNDER_PO = "Under PO"
    NOT_UNDER_PO = "Not Under PO"


class Clarification(str, enum.Enum):
    PO_AMENDMENT = "PO Amendment Required"
    LABOUR_SUPPLY = "Labour Supply"


class ErectionStatus(str, enum.Enum):
    ERECTION_COMPLETED = "Erection Completed"
    NOT_AVAILABLE = "Not Available"
    PARTIALLY_AVAILABLE = "Partially Available"
    PROGRESSING = "Progressing"


class ErectionFrontStatus(str, enum.Enum):
    FOUNDATION_NOT_HANDED_OVER = "Foundation not handed over"
    STRUCTURAL_STEEL_NOT_COMPLETED = "Structural steel not completed"
    ACCESS_NOT_AVAILABLE = "Access not available"
    CIVIL_WORK_IN_PROGRESS = "Civil work in progress"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sites: Mapped[list[Site]] = relationship(back_populates="company")
    users: Mapped[list[User]] = relationship(back_populates="company")


class Site(Base):
    __tablename__ = "sites"
    __table_args__ = (UniqueConstraint("company_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="active")
    sheets_export_spreadsheet_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company] = relationship(back_populates="sites")
    site_users: Mapped[list[SiteUser]] = relationship(back_populates="site")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    global_role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company] = relationship(back_populates="users")
    site_users: Mapped[list[SiteUser]] = relationship(back_populates="user")


class SiteUser(Base):
    __tablename__ = "site_users"
    __table_args__ = (UniqueConstraint("site_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))

    site: Mapped[Site] = relationship(back_populates="site_users")
    user: Mapped[User] = relationship(back_populates="site_users")


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("site_id", "employee_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    employee_code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    designation: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default=EmployeeStatus.ACTIVE.value)
    joining_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("site_id", "employee_id", "work_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    morning_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    morning_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evening_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    evening_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ot_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    marked_by_morning_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    marked_by_evening_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class MasterEquipment(Base):
    __tablename__ = "master_equipment"
    __table_args__ = (UniqueConstraint("site_id", "po_ref", "equipment_tag"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    po_ref: Mapped[str] = mapped_column(String(100), default="")
    equipment_tag: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(String(500), default="")
    unit: Mapped[str] = mapped_column(String(40), default="")
    po_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    completed_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(80), default="")
    erection_front_status: Mapped[str] = mapped_column(String(80), default="")
    remarks: Mapped[str] = mapped_column(Text, default="")
    photo_ref: Mapped[str] = mapped_column(String(500), default="")


class NonPoJob(Base):
    __tablename__ = "non_po_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("daily_plans.id"), nullable=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    clarification: Mapped[str] = mapped_column(String(40))
    job_description: Mapped[str] = mapped_column(Text)
    allocated_workers: Mapped[str] = mapped_column(Text, default="")
    remarks: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(80), default="")
    photo_ref: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyPlan(Base):
    __tablename__ = "daily_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    plan_code: Mapped[str] = mapped_column(String(40), index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    po_ref: Mapped[str] = mapped_column(String(100), default="N/A")
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("master_equipment.id"), nullable=True)
    equipment_tag: Mapped[str] = mapped_column(String(100), default="")
    equipment_description: Mapped[str] = mapped_column(String(500), default="")
    classification: Mapped[str] = mapped_column(String(40))
    clarification: Mapped[str | None] = mapped_column(String(40), nullable=True)
    job_description: Mapped[str] = mapped_column(Text)
    allocated_workers: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=PlanStatus.PLANNED.value)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    planned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyProgress(Base):
    __tablename__ = "daily_progress"
    __table_args__ = (UniqueConstraint("plan_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sites.id"), index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("daily_plans.id"))
    status: Mapped[str] = mapped_column(String(80), default="")
    erection_front_status: Mapped[str] = mapped_column(String(80), default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    remarks: Mapped[str] = mapped_column(Text, default="")
    photo_ref: Mapped[str] = mapped_column(String(500), default="")
    reported_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    route_target: Mapped[str | None] = mapped_column(String(40), nullable=True)


class ProgressPhoto(Base):
    __tablename__ = "progress_photos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    progress_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("daily_progress.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(100), default="image/jpeg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
