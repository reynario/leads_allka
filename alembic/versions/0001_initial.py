"""initial schema: leads.leads + leads.lead_analysis

Revision ID: 0001
Revises:
Create Date: 2026-05-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS leads")

    op.create_table(
        "leads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("redrive_id", sa.Text(), nullable=False),
        sa.Column("company_name", sa.Text()),
        sa.Column("website", sa.Text()),
        sa.Column("instagram", sa.Text()),
        sa.Column("phone", sa.Text()),
        sa.Column("city", sa.Text()),
        sa.Column("segment", sa.Text()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("bitrix_id", sa.BigInteger()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("redrive_id", name="uq_leads_redrive_id"),
        schema="leads",
    )
    op.create_index(
        "ix_leads_status_created_at",
        "leads",
        ["status", "created_at"],
        schema="leads",
    )

    op.create_table(
        "lead_analysis",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("site_active", sa.Boolean()),
        sa.Column("has_whatsapp", sa.Boolean()),
        sa.Column("has_form", sa.Boolean()),
        sa.Column("has_meta_pixel", sa.Boolean()),
        sa.Column("has_google_tag", sa.Boolean()),
        sa.Column("has_gtm", sa.Boolean()),
        sa.Column("instagram_active", sa.Boolean()),
        sa.Column("last_post_date", sa.DateTime(timezone=True)),
        sa.Column("posting_frequency", sa.Text()),
        sa.Column("best_post_url", sa.Text()),
        sa.Column("best_post_likes", sa.Integer()),
        sa.Column("best_post_comments", sa.Integer()),
        sa.Column("has_meta_ads", sa.Boolean()),
        sa.Column("has_google_ads", sa.Boolean()),
        sa.Column("meta_ads_print", sa.Text()),
        sa.Column("google_ads_print", sa.Text()),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("ai_pains", sa.Text()),
        sa.Column("ai_opportunity", sa.Text()),
        sa.Column("ai_message", sa.Text()),
        sa.Column("score", sa.Integer()),
        sa.Column("raw_payload", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.leads.id"], ondelete="CASCADE", name="fk_lead_analysis_lead_id"
        ),
        sa.UniqueConstraint("lead_id", name="uq_lead_analysis_lead_id"),
        schema="leads",
    )


def downgrade() -> None:
    op.drop_table("lead_analysis", schema="leads")
    op.drop_index("ix_leads_status_created_at", table_name="leads", schema="leads")
    op.drop_table("leads", schema="leads")
    op.execute("DROP SCHEMA IF EXISTS leads")
