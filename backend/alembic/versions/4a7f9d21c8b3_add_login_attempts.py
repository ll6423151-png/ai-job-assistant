"""add password login attempt tracking

Revision ID: 4a7f9d21c8b3
Revises: 00dd80cb63b9
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "4a7f9d21c8b3"
down_revision: str | None = "00dd80cb63b9"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_login_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("identifier_hash", sa.String(length=64), nullable=False),
        sa.Column("ip_address", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_auth_login_attempts_created_at"), "auth_login_attempts", ["created_at"], unique=False)
    op.create_index(op.f("ix_auth_login_attempts_identifier_hash"), "auth_login_attempts", ["identifier_hash"], unique=False)
    op.create_index(op.f("ix_auth_login_attempts_ip_address"), "auth_login_attempts", ["ip_address"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_login_attempts_ip_address"), table_name="auth_login_attempts")
    op.drop_index(op.f("ix_auth_login_attempts_identifier_hash"), table_name="auth_login_attempts")
    op.drop_index(op.f("ix_auth_login_attempts_created_at"), table_name="auth_login_attempts")
    op.drop_table("auth_login_attempts")
