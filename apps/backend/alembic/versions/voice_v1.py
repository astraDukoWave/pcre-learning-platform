"""voice_v1: sesiones de voz y aviso de procesamiento de voz (MVP-02 CS-05).
Migración expand: una tabla nueva, una columna nullable en `users` y la FK de
`ai_runs.voice_session_id` (la columna ya existía y el código anterior nunca la llena).

Revision ID: voice_v1
Revises: usage_v1
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "voice_v1"
down_revision = "usage_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("voice_notice_accepted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "voice_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_item_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_revision_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("max_seconds", sa.Integer(), nullable=False),
        sa.Column("save_transcript", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(length=20), nullable=True),
        sa.Column("learner_speech_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "aids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("transcript", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("feedback", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ai_run_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "status IN ('reserved', 'active', 'ended', 'failed', 'expired')",
            name="ck_voice_sessions_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scenario_item_id"], ["content_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["scenario_revision_id"], ["content_revisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["ai_run_id"], ["ai_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_voice_sessions_user", "voice_sessions", ["user_id", "created_at"])
    # Una sesión viva (`reserved` o `active`) por alumno (REQ-05).
    op.create_index(
        "ux_voice_sessions_user_live",
        "voice_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('reserved', 'active')"),
    )
    op.create_foreign_key(
        "fk_ai_runs_voice_session",
        "ai_runs",
        "voice_sessions",
        ["voice_session_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_ai_runs_voice_session", "ai_runs", type_="foreignkey")
    op.drop_index("ux_voice_sessions_user_live", table_name="voice_sessions")
    op.drop_index("ix_voice_sessions_user", table_name="voice_sessions")
    op.drop_table("voice_sessions")
    op.drop_column("users", "voice_notice_accepted_at")
