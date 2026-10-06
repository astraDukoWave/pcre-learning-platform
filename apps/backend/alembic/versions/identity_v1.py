"""identity_v1: amplía users; sesiones, invitaciones y tokens de reset (MVP-01 CS-03).

Migración expand: columnas nuevas con default o nulas; los emails existentes pasan a
minúsculas. Desde aquí, toda FK hacia users lleva ON DELETE CASCADE.

Revision ID: identity_v1
Revises: 816c80672425
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "identity_v1"
down_revision = "816c80672425"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute("UPDATE users SET email = lower(email) WHERE email <> lower(email)")
    op.add_column("users", sa.Column("display_name", sa.String(80), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "timezone",
            sa.String(64),
            nullable=False,
            server_default=sa.text("'America/Mexico_City'"),
        ),
    )
    op.add_column("users", sa.Column("goal_purpose", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("target_exam", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("target_exam_other", sa.String(80), nullable=True))
    op.add_column("users", sa.Column("target_score", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("target_date", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("self_reported_level", sa.String(10), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("consent_version", sa.String(40), nullable=True))
    op.add_column("users", sa.Column("consent_accepted_at", TS, nullable=True))
    op.add_column("users", sa.Column("adult_attested_at", TS, nullable=True))
    op.add_column("users", sa.Column("onboarded_at", TS, nullable=True))
    op.add_column("users", sa.Column("last_login_at", TS, nullable=True))
    op.create_check_constraint("ck_users_email_lower", "users", "email = lower(email)")

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("last_seen_at", TS, nullable=False),
        sa.Column("absolute_expires_at", TS, nullable=False),
        sa.Column("idle_expires_at", TS, nullable=False),
        sa.Column("revoked_at", TS, nullable=True),
        sa.Column("revoke_reason", sa.String(20), nullable=True),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])

    role = postgresql.ENUM("admin", "student", name="userrole", create_type=False)
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", role, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("consumed_at", TS, nullable=True),
        sa.Column(
            "consumed_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_invitations_email", "invitations", ["email"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("consumed_at", TS, nullable=True),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
    op.drop_table("invitations")
    op.drop_table("auth_sessions")
    op.drop_constraint("ck_users_email_lower", "users", type_="check")
    for column in (
        "last_login_at",
        "onboarded_at",
        "adult_attested_at",
        "consent_accepted_at",
        "consent_version",
        "is_internal",
        "self_reported_level",
        "target_date",
        "target_score",
        "target_exam_other",
        "target_exam",
        "goal_purpose",
        "timezone",
        "display_name",
    ):
        op.drop_column("users", column)
