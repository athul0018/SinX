"""auth security tables and must_change_password

Revision ID: 003_auth_security
Revises: 002_master
Create Date: 2026-09-17

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_auth_security"
down_revision = "002_master"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "revoked_sessions",
        sa.Column("jti", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_sessions_expires_at", "revoked_sessions", ["expires_at"])
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bucket_key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_login_attempts_bucket_created", "login_attempts", ["bucket_key", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_login_attempts_bucket_created", table_name="login_attempts")
    op.drop_table("login_attempts")
    op.drop_index("ix_revoked_sessions_expires_at", table_name="revoked_sessions")
    op.drop_table("revoked_sessions")
    op.drop_column("users", "must_change_password")
