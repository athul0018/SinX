"""master list columns and non-PO jobs

Revision ID: 002_master
Revises: 001_initial
Create Date: 2026-09-15
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "002_master"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("master_equipment", sa.Column("unit", sa.String(length=40), server_default="", nullable=False))
    op.add_column("master_equipment", sa.Column("po_quantity", sa.Numeric(12, 2), server_default="0", nullable=False))
    op.add_column(
        "master_equipment",
        sa.Column("completed_quantity", sa.Numeric(12, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "master_equipment",
        sa.Column("remaining_quantity", sa.Numeric(12, 2), server_default="0", nullable=False),
    )
    op.add_column("master_equipment", sa.Column("status", sa.String(length=80), server_default="", nullable=False))
    op.add_column(
        "master_equipment",
        sa.Column("erection_front_status", sa.String(length=80), server_default="", nullable=False),
    )
    op.add_column("master_equipment", sa.Column("remarks", sa.Text(), server_default="", nullable=False))
    op.add_column("master_equipment", sa.Column("photo_ref", sa.String(length=500), server_default="", nullable=False))
    op.create_unique_constraint(
        "uq_master_equipment_site_po_tag",
        "master_equipment",
        ["site_id", "po_ref", "equipment_tag"],
    )

    op.add_column(
        "daily_progress",
        sa.Column("erection_front_status", sa.String(length=80), server_default="", nullable=False),
    )
    op.add_column("daily_progress", sa.Column("photo_ref", sa.String(length=500), server_default="", nullable=False))
    op.alter_column("daily_progress", "status", existing_type=sa.String(length=40), type_=sa.String(length=80))

    op.create_table(
        "non_po_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("clarification", sa.String(length=40), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=False),
        sa.Column("allocated_workers", sa.Text(), server_default="", nullable=False),
        sa.Column("remarks", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=80), server_default="", nullable=False),
        sa.Column("photo_ref", sa.String(length=500), server_default="", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["daily_plans.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_non_po_jobs_site_id", "non_po_jobs", ["site_id"])
    op.create_index("ix_non_po_jobs_work_date", "non_po_jobs", ["work_date"])


def downgrade() -> None:
    op.drop_index("ix_non_po_jobs_work_date", table_name="non_po_jobs")
    op.drop_index("ix_non_po_jobs_site_id", table_name="non_po_jobs")
    op.drop_table("non_po_jobs")
    op.drop_column("daily_progress", "photo_ref")
    op.drop_column("daily_progress", "erection_front_status")
    op.drop_constraint("uq_master_equipment_site_po_tag", "master_equipment", type_="unique")
    op.drop_column("master_equipment", "photo_ref")
    op.drop_column("master_equipment", "remarks")
    op.drop_column("master_equipment", "erection_front_status")
    op.drop_column("master_equipment", "status")
    op.drop_column("master_equipment", "remaining_quantity")
    op.drop_column("master_equipment", "completed_quantity")
    op.drop_column("master_equipment", "po_quantity")
    op.drop_column("master_equipment", "unit")
