"""assessment_v1: corridas de comprobación y respuestas guardadas (MVP-01 CS-07).
Migración expand: dos tablas nuevas y la FK de `attempts.assessment_run_id` (la columna ya
existía y el código anterior nunca la llena).

Revision ID: assessment_v1
Revises: practice_v1
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "assessment_v1"
down_revision = "practice_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("form_item_id", sa.Uuid(), nullable=False),
        sa.Column("form_revision_id", sa.Uuid(), nullable=False),
        sa.Column("form_kind", sa.String(length=12), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("item_order", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('in_progress', 'submitted')", name="ck_assessment_runs_status"
        ),
        sa.CheckConstraint(
            "form_kind IN ('initial', 'checkpoint', 'final')", name="ck_assessment_runs_form_kind"
        ),
        sa.ForeignKeyConstraint(["form_item_id"], ["content_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["form_revision_id"], ["content_revisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "form_item_id", "run_number", name="uq_assessment_runs_user_form_number"
        ),
    )
    op.create_index(
        "uq_assessment_runs_in_progress",
        "assessment_runs",
        ["user_id", "form_item_id"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress'"),
    )
    op.create_index(
        "uq_assessment_runs_one_diagnostic",
        "assessment_runs",
        ["user_id", "form_item_id"],
        unique=True,
        postgresql_where=sa.text("form_kind = 'initial' AND reset_at IS NULL"),
    )
    op.create_table(
        "assessment_answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audio_failed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["assessment_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "activity_id", name="uq_assessment_answers_run_activity"),
    )
    op.create_foreign_key(
        "fk_attempts_assessment_run",
        "attempts",
        "assessment_runs",
        ["assessment_run_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_attempts_assessment_run", "attempts", type_="foreignkey")
    op.drop_table("assessment_answers")
    op.drop_index("uq_assessment_runs_one_diagnostic", table_name="assessment_runs")
    op.drop_index("uq_assessment_runs_in_progress", table_name="assessment_runs")
    op.drop_table("assessment_runs")
