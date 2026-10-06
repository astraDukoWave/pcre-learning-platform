"""usage_v1: presupuestos por periodo y ejecuciones de IA y voz (MVP-02 CS-01).
Migración expand: solo tablas nuevas.

Revision ID: usage_v1
Revises: insights_v1
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "usage_v1"
down_revision = "insights_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budget_periods",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=8), nullable=False),
        sa.Column("scope_key", sa.String(length=40), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("limit_microusd", sa.BigInteger(), nullable=False),
        sa.Column("reserved_microusd", sa.BigInteger(), nullable=False),
        sa.Column("spent_microusd", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("scope IN ('global', 'user')", name="ck_budget_periods_scope"),
        sa.CheckConstraint(
            "(scope = 'global' AND user_id IS NULL) OR (scope = 'user' AND user_id IS NOT NULL)",
            name="ck_budget_periods_user",
        ),
        sa.CheckConstraint(
            "limit_microusd >= 0 AND reserved_microusd >= 0 AND spent_microusd >= 0",
            name="ck_budget_periods_amounts",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "scope_key", "period", name="uq_budget_periods_scope_period"),
    )
    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=True),
        sa.Column("rubric_version", sa.String(length=40), nullable=True),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.Column("voice_session_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("reserved_microusd", sa.BigInteger(), nullable=False),
        sa.Column("observed_units", sa.Integer(), nullable=True),
        sa.Column("cost_microusd", sa.BigInteger(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('writing_feedback', 'speaking_feedback', 'transcription', "
            "'voice_session')",
            name="ck_ai_runs_purpose",
        ),
        sa.CheckConstraint(
            "status IN ('reserved', 'running', 'succeeded', 'failed', 'unknown', 'released')",
            name="ck_ai_runs_status",
        ),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "purpose", "idempotency_key", name="uq_ai_runs_idempotency"
        ),
    )
    op.create_index("ix_ai_runs_attempt", "ai_runs", ["attempt_id"])
    op.create_index("ix_ai_runs_period_user", "ai_runs", ["period", "user_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_runs_period_user", table_name="ai_runs")
    op.drop_index("ix_ai_runs_attempt", table_name="ai_runs")
    op.drop_table("ai_runs")
    op.drop_table("budget_periods")
