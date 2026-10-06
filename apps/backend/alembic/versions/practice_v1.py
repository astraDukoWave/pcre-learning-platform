"""practice_v1: inscripciones, progreso con revisión fijada, ayudas servidas, intentos,
idempotencia y repasos (MVP-01 CS-05). Migración expand: solo tablas nuevas y la FK de
`content_reports.attempt_id`.

Revision ID: practice_v1
Revises: content_v1
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "practice_v1"
down_revision = "content_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "enrollments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_version_at_enroll", sa.Integer(), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["path_id"], ["learning_paths.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "path_id", name="uq_enrollments_user_path"),
    )
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status_code", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "operation", "key", name="uq_idempotency_user_operation_key"
        ),
    )
    op.create_table(
        "review_schedule",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("objective_code", sa.String(length=16), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_outcome", sa.String(length=16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "objective_code", name="uq_review_schedule_user_objective"),
    )
    op.create_index(
        "ix_review_schedule_user_due", "review_schedule", ["user_id", "due_at"], unique=False
    )
    op.create_table(
        "lesson_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("pinned_revision_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["pinned_revision_id"], ["content_revisions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "item_id", name="uq_lesson_progress_user_item"),
    )
    op.create_table(
        "attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=12), nullable=False),
        sa.Column("assessment_run_id", sa.Uuid(), nullable=True),
        sa.Column("revision_of", sa.Uuid(), nullable=True),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "aids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("evaluation_status", sa.String(length=16), nullable=False),
        sa.Column("evaluation_source", sa.String(length=8), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_first", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("repeated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("local_day", sa.Date(), nullable=False),
        sa.CheckConstraint(
            "evaluation_status IN ('evaluated', 'pending', 'not_evaluable', 'failed')",
            name="ck_attempts_evaluation_status",
        ),
        sa.CheckConstraint("mode IN ('practice', 'review', 'assessment')", name="ck_attempts_mode"),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revision_id"], ["content_revisions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revision_of"], ["attempts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_attempts_user_activity", "attempts", ["user_id", "activity_id"], unique=False
    )
    op.create_index(
        "ix_attempts_user_submitted", "attempts", ["user_id", "submitted_at"], unique=False
    )
    op.create_table(
        "served_aids",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("index", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("served_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('hint', 'support_es', 'transcript', 'example', 'audio_play')",
            name="ck_served_aids_kind",
        ),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_served_aids_user_activity", "served_aids", ["user_id", "activity_id"], unique=False
    )
    op.create_foreign_key(
        "fk_content_reports_attempt",
        "content_reports",
        "attempts",
        ["attempt_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_content_reports_attempt", "content_reports", type_="foreignkey")
    op.drop_index("ix_served_aids_user_activity", table_name="served_aids")
    op.drop_table("served_aids")
    op.drop_index("ix_attempts_user_submitted", table_name="attempts")
    op.drop_index("ix_attempts_user_activity", table_name="attempts")
    op.drop_table("attempts")
    op.drop_table("lesson_progress")
    op.drop_index("ix_review_schedule_user_due", table_name="review_schedule")
    op.drop_table("review_schedule")
    op.drop_table("idempotency_records")
    op.drop_table("enrollments")
