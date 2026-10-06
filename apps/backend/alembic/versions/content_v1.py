"""content_v1: ruta, unidades, ítems, revisiones, actividades, fuentes, hallazgos,
bitácora editorial y reportes de contenido (MVP-01 CS-04, ADR-03 y ADR-08).

Migración expand: solo tablas nuevas; las legadas no se tocan.

Revision ID: content_v1
Revises: identity_v1
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "content_v1"
down_revision = "identity_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learning_paths",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("exam_code", sa.String(length=40), nullable=False),
        sa.Column("exam_format_version", sa.String(length=20), nullable=False),
        sa.Column("level_from", sa.String(length=4), nullable=False),
        sa.Column("level_to", sa.String(length=4), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column(
            "status", sa.String(length=12), server_default=sa.text("'active'"), nullable=False
        ),
        sa.Column("catalog_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("accessed_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_table(
        "units",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["path_id"], ["learning_paths.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path_id", "position", name="uq_units_path_position"),
        sa.UniqueConstraint("path_id", "slug", name="uq_units_path_slug"),
    )
    op.create_table(
        "content_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("path_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=True),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("skill", sa.String(length=12), nullable=True),
        sa.Column("form_kind", sa.String(length=12), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("published_revision_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('lesson', 'assessment_form', 'scenario')", name="ck_content_items_kind"
        ),
        sa.ForeignKeyConstraint(["path_id"], ["learning_paths.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path_id", "slug", name="uq_content_items_path_slug"),
    )
    op.create_table(
        "content_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_path", sa.String(length=300), nullable=False),
        sa.Column("source_commit", sa.String(length=64), nullable=True),
        sa.Column(
            "status", sa.String(length=12), server_default=sa.text("'draft'"), nullable=False
        ),
        sa.Column("file_status", sa.String(length=20), nullable=False),
        sa.Column("lint_errors", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "lint_warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("audio_pending", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_hash", sa.String(length=64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdraw_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'published', 'superseded', 'withdrawn')",
            name="ck_content_revisions_status",
        ),
        sa.ForeignKeyConstraint(["item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", "content_hash", name="uq_content_revisions_item_hash"),
        sa.UniqueConstraint("item_id", "version", name="uq_content_revisions_item_version"),
    )
    # FK circular (ítem → revisión publicada): se crea cuando ya existen ambas tablas.
    op.create_foreign_key(
        "fk_content_items_published_revision",
        "content_items",
        "content_revisions",
        ["published_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("activity_key", sa.String(length=90), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(length=24), nullable=False),
        sa.Column("task_family", sa.String(length=40), nullable=False),
        sa.Column("pool", sa.String(length=12), nullable=False),
        sa.Column("objective_codes", sa.ARRAY(sa.String(length=16)), nullable=False),
        sa.Column("prompt", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("stimulus", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "hints",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("support_es", sa.Text(), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("example", sa.Text(), nullable=True),
        sa.Column("solution", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("rubric", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "pool IN ('practice', 'review', 'assessment')", name="ck_activities_pool"
        ),
        sa.ForeignKeyConstraint(["revision_id"], ["content_revisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_id", "activity_key", name="uq_activities_revision_key"),
    )
    op.create_index("ix_activities_activity_key", "activities", ["activity_key"], unique=False)
    op.create_table(
        "editorial_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("decided_by", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('approve', 'publish', 'withdraw', 'request_changes')",
            name="ck_editorial_decisions_action",
        ),
        sa.ForeignKeyConstraint(["revision_id"], ["content_revisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_editorial_decisions_revision_id"),
        "editorial_decisions",
        ["revision_id"],
        unique=False,
    )
    op.create_table(
        "review_findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("author", sa.String(length=80), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=12), server_default=sa.text("'open'"), nullable=False),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("severity IN ('material', 'minor')", name="ck_review_findings_severity"),
        sa.CheckConstraint(
            "status IN ('open', 'resolved', 'wont_fix')", name="ck_review_findings_status"
        ),
        sa.ForeignKeyConstraint(["revision_id"], ["content_revisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_review_findings_revision_id"), "review_findings", ["revision_id"], unique=False
    )
    op.create_table(
        "revision_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(["revision_id"], ["content_revisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_revision_sources_revision_id"), "revision_sources", ["revision_id"], unique=False
    )
    op.create_table(
        "content_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=True),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("message", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("page", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=12), server_default=sa.text("'open'"), nullable=False),
        sa.Column("triage_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'triaged', 'resolved', 'wont_fix')",
            name="ck_content_reports_status",
        ),
        sa.CheckConstraint("char_length(message) <= 1000", name="ck_content_reports_message"),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revision_id"], ["content_revisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_content_reports_user_id"), "content_reports", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_content_reports_user_id"), table_name="content_reports")
    op.drop_table("content_reports")
    op.drop_index(op.f("ix_revision_sources_revision_id"), table_name="revision_sources")
    op.drop_table("revision_sources")
    op.drop_index(op.f("ix_review_findings_revision_id"), table_name="review_findings")
    op.drop_table("review_findings")
    op.drop_index(op.f("ix_editorial_decisions_revision_id"), table_name="editorial_decisions")
    op.drop_table("editorial_decisions")
    op.drop_index("ix_activities_activity_key", table_name="activities")
    op.drop_table("activities")
    op.drop_constraint("fk_content_items_published_revision", "content_items", type_="foreignkey")
    op.drop_table("content_revisions")
    op.drop_table("content_items")
    op.drop_table("units")
    op.drop_table("sources")
    op.drop_table("learning_paths")
