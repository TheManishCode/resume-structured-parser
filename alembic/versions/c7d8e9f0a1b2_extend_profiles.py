"""extend user profiles and add analysis history

Revision ID: c7d8e9f0a1b2
Revises: 05d951f03b90
Create Date: 2026-06-30

"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "05d951f03b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Candidate profile fields ──────────────────────────────────────────────
    op.add_column("candidates", sa.Column("name",             sa.String(255), nullable=True))
    op.add_column("candidates", sa.Column("phone",            sa.String(32),  nullable=True))
    op.add_column("candidates", sa.Column("location",         sa.String(255), nullable=True))
    op.add_column("candidates", sa.Column("target_roles",     postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("candidates", sa.Column("experience_level", sa.String(32),  nullable=True))
    op.add_column("candidates", sa.Column("job_type_pref",    postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("candidates", sa.Column("skills",           postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("candidates", sa.Column("visibility",       sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("candidates", sa.Column("onboarding_done",  sa.Boolean(), nullable=False, server_default="false"))

    # ── Recruiter profile fields ──────────────────────────────────────────────
    op.add_column("recruiters", sa.Column("name",             sa.String(255), nullable=True))
    op.add_column("recruiters", sa.Column("company_website",  sa.String(512), nullable=True))
    op.add_column("recruiters", sa.Column("hiring_role",      sa.String(128), nullable=True))
    op.add_column("recruiters", sa.Column("hiring_domains",   postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("recruiters", sa.Column("company_size",     sa.String(32),  nullable=True))
    op.add_column("recruiters", sa.Column("onboarding_done",  sa.Boolean(), nullable=False, server_default="false"))

    # ── Analysis history table ────────────────────────────────────────────────
    op.create_table(
        "analysis_history",
        sa.Column("id",                  postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("candidate_id",        postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("job_title",           sa.String(255), nullable=True),
        sa.Column("company",             sa.String(255), nullable=True),
        sa.Column("job_url",             sa.String(1024), nullable=True),
        sa.Column("overall_score",       sa.Integer(), nullable=True),
        sa.Column("ats_score",           sa.Integer(), nullable=True),
        sa.Column("keyword_match_score", sa.Integer(), nullable=True),
        sa.Column("skills_match_score",  sa.Integer(), nullable=True),
        sa.Column("experience_score",    sa.Integer(), nullable=True),
        sa.Column("format_score",        sa.Integer(), nullable=True),
        sa.Column("matched_keywords",    postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("missing_keywords",    postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("improvements",        postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("summary",             sa.Text(), nullable=True),
        sa.Column("analyzed_at",         sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_history_candidate_id", "analysis_history", ["candidate_id"])


def downgrade() -> None:
    op.drop_index("ix_analysis_history_candidate_id", table_name="analysis_history")
    op.drop_table("analysis_history")

    for col in ["onboarding_done", "company_size", "hiring_domains", "hiring_role",
                "company_website", "name"]:
        op.drop_column("recruiters", col)

    for col in ["onboarding_done", "visibility", "skills", "job_type_pref",
                "experience_level", "target_roles", "location", "phone", "name"]:
        op.drop_column("candidates", col)
