"""Initial migration - create all tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables."""

    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # chunks table
    op.create_table(
        "chunks",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), default="private"),
        sa.Column("role", sa.String()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), default=dict),
        sa.Column("tsvector", postgresql.TSVECTOR()),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_chunks_agent_scope", "chunks", ["agent_id", "scope"])
    op.create_index("idx_chunks_created_at", "chunks", ["created_at"])
    op.create_index("idx_chunks_tsvector", "chunks", ["tsvector"], postgresql_using="gin")

    # chunk_vectors table
    op.create_table(
        "chunk_vectors",
        sa.Column("chunk_id", sa.BigInteger(), sa.ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("chunk_id"),
    )

    # entities table
    op.create_table(
        "entities",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String()),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), default=dict),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_entities_name", "entities", ["name"])
    op.create_index("idx_entities_agent", "entities", ["agent_id"])

    # entity_edges table
    op.create_table(
        "entity_edges",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("from_entity_id", sa.BigInteger(), sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("to_entity_id", sa.BigInteger(), sa.ForeignKey("entities.id"), nullable=False),
        sa.Column("relation_type", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), default=1.0),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_edges_from_to", "entity_edges", ["from_entity_id", "to_entity_id"])
    op.create_index("idx_edges_agent", "entity_edges", ["agent_id"])

    # agent_state table
    op.create_table(
        "agent_state",
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("pack_id", sa.String(), nullable=False),
        sa.Column("stage", sa.Integer(), default=1),
        sa.Column("affinity", sa.Float(), default=0),
        sa.Column("mood", sa.Float(), default=50),
        sa.Column("energy", sa.Float(), default=50),
        sa.Column("last_interaction", sa.DateTime()),
        sa.Column("last_heartbeat", sa.DateTime()),
        sa.Column("pending_heartbeat", sa.Boolean(), default=False),
        sa.Column("state", postgresql.JSONB(astext_type=sa.Text()), default=dict),
        sa.Column("version", sa.Integer(), default=1, nullable=False),
        sa.Column("updated_at", sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("agent_id"),
    )
    op.create_index("idx_state_pack", "agent_state", ["pack_id"])
    op.create_index("idx_state_pending", "agent_state", ["pending_heartbeat"], postgresql_where="pending_heartbeat = true")

    # events table
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("related_chunk_id", sa.BigInteger(), sa.ForeignKey("chunks.id")),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_events_agent_time", "events", ["agent_id", sa.desc("created_at")])
    op.create_index("idx_events_type", "events", ["event_type"])
    op.create_index("idx_events_payload", "events", ["payload"], postgresql_using="gin", postgresql_ops={"payload": "jsonb_path_ops"})

    # event_vectors table
    op.create_table(
        "event_vectors",
        sa.Column("event_id", sa.BigInteger(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )

    # promises table
    op.create_table(
        "promises",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), default="open"),
        sa.Column("due_at", sa.DateTime()),
        sa.Column("fulfilled_at", sa.DateTime()),
        sa.Column("event_id", sa.BigInteger(), sa.ForeignKey("events.id")),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_promises_agent_status", "promises", ["agent_id", "status"])

    # user_profile table
    op.create_table(
        "user_profile",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String()),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), default=dict),
        sa.Column("updated_by", sa.String()),
        sa.Column("updated_at", sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # packs table
    op.create_table(
        "packs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("install_path", sa.String()),
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column("installed_at", sa.DateTime(), default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # tool_logs table
    op.create_table(
        "tool_logs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("duration_ms", sa.Float()),
        sa.Column("success", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tool_logs_agent", "tool_logs", ["agent_id"])
    op.create_index("idx_tool_logs_created_at", "tool_logs", ["created_at"])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("tool_logs")
    op.drop_table("packs")
    op.drop_table("user_profile")
    op.drop_table("promises")
    op.drop_table("event_vectors")
    op.drop_table("events")
    op.drop_table("agent_state")
    op.drop_table("entity_edges")
    op.drop_table("entities")
    op.drop_table("chunk_vectors")
    op.drop_table("chunks")
    op.execute("DROP EXTENSION IF EXISTS vector")
