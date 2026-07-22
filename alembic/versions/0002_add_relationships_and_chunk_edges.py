"""add relationships and chunk_edges tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add relationships and chunk_edges tables."""
    
    # relationships table (v2 core - user↔agent relationship evolution)
    op.create_table(
        "relationships",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("stage", sa.Integer(), default=1),  # 1-5: stranger → friend → partner
        sa.Column("affinity", sa.Float(), default=0.0),  # -1.0 to 1.0
        sa.Column("trust", sa.Float(), default=0.0),  # 0.0 to 1.0
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), default=dict),
        sa.Column("last_interaction_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "agent_id", name="uq_relationship_user_agent"),
    )
    op.create_index("idx_relationships_user", "relationships", ["user_id"])
    op.create_index("idx_relationships_agent", "relationships", ["agent_id"])
    op.create_index("idx_relationships_stage", "relationships", ["stage"])
    
    # chunk_edges table (entity co-occurrence within chunks)
    op.create_table(
        "chunk_edges",
        sa.Column("chunk_id", sa.BigInteger(), sa.ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id_1", sa.BigInteger(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id_2", sa.BigInteger(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("edge_type", sa.String(), nullable=False),  # co-occur, related, etc.
        sa.Column("weight", sa.Float(), default=1.0),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), default=dict),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.PrimaryKeyConstraint("chunk_id", "entity_id_1", "entity_id_2"),
    )
    op.create_index("idx_chunk_edges_entity1", "chunk_edges", ["entity_id_1"])
    op.create_index("idx_chunk_edges_entity2", "chunk_edges", ["entity_id_2"])
    
    # skills table (v1 feature - agent skills)
    op.create_table(
        "skills",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("level", sa.Integer(), default=1),  # 1-10
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), default=dict),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "name", name="uq_skill_agent_name"),
    )
    op.create_index("idx_skills_agent", "skills", ["agent_id"])
    
    # task_summaries table (v1 feature - task completion summaries)
    op.create_table(
        "task_summaries",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), default="completed"),  # completed, failed, cancelled
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), default=dict),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "task_id", name="uq_task_agent_task"),
    )
    op.create_index("idx_task_summaries_agent", "task_summaries", ["agent_id"])
    op.create_index("idx_task_summaries_status", "task_summaries", ["status"])


def downgrade() -> None:
    """Drop added tables."""
    op.drop_table("task_summaries")
    op.drop_table("skills")
    op.drop_table("chunk_edges")
    op.drop_table("relationships")
