"""add skills and task_summaries tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add skills and task_summaries tables."""
    
    # skills table (v3.0 - skill system for agents)
    op.create_table(
        "skills",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), default=dict),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_skills_name"),
    )
    op.create_index("idx_skills_category", "skills", ["category"])
    op.create_index("idx_skills_enabled", "skills", ["enabled"])
    
    # task_summaries table (v3.0 - task execution summaries)
    op.create_table(
        "task_summaries",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("status", sa.String(), default="pending"),  # pending, running, completed, failed
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), default=dict),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_task_summaries_task_id"),
    )
    op.create_index("idx_task_summaries_agent", "task_summaries", ["agent_id"])
    op.create_index("idx_task_summaries_status", "task_summaries", ["status"])
    op.create_index("idx_task_summaries_created", "task_summaries", ["created_at"])


def downgrade() -> None:
    """Drop skills and task_summaries tables."""
    op.drop_table("task_summaries")
    op.drop_table("skills")
