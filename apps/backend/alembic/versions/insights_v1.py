"""insights_v1: feedback del producto, eventos de producto y errores del servidor
(MVP-01 CS-09). Migración expand: solo tablas nuevas.

Revision ID: insights_v1
Revises: assessment_v1
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "insights_v1"
down_revision = "assessment_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("context_type", sa.String(length=16), nullable=False),
        sa.Column("context_id", sa.Uuid(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("page", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "context_type IN ('lesson', 'general', 'voice', 'ai_observation')",
            name="ck_user_feedback_context",
        ),
        sa.CheckConstraint(
            "rating IS NULL OR (rating BETWEEN 0 AND 5)", name="ck_user_feedback_rating"
        ),
        sa.CheckConstraint("char_length(message) <= 1000", name="ck_user_feedback_message"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_feedback_created", "user_feedback", ["created_at"])
    op.create_table(
        "product_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column(
            "props",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_events_name_occurred", "product_events", ["name", "occurred_at"])
    op.create_table(
        "error_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("route", sa.String(length=200), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=False),
        sa.Column("exception_type", sa.String(length=120), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_error_events_occurred", "error_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_error_events_occurred", table_name="error_events")
    op.drop_table("error_events")
    op.drop_index("ix_product_events_name_occurred", table_name="product_events")
    op.drop_table("product_events")
    op.drop_index("ix_user_feedback_created", table_name="user_feedback")
    op.drop_table("user_feedback")
