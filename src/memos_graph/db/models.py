"""SQLAlchemy models for memos-graph."""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Float, Boolean, DateTime,
    ForeignKey, Index, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, BIGINT, TSVECTOR
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy import Computed
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class Chunk(Base):
    """Memory chunk (L1)."""
    __tablename__ = "chunks"

    id = Column(BigInteger, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    scope = Column(String, default="private")  # private | shared | public
    role = Column(String)  # user | assistant | system
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)
    tsvector = Column(TSVECTOR)  # Full-text search vector

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_chunks_agent_scope", "agent_id", "scope"),
        Index("idx_chunks_tsvector", "tsvector", postgresql_using="gin"),
    )


class ChunkVector(Base):
    """Vector embedding for chunks."""
    __tablename__ = "chunk_vectors"

    chunk_id = Column(BigInteger, ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True)
    embedding = Column(Vector(1024), nullable=False)  # BAAI/bge-m3 uses 1024 dimensions
    model = Column(String, nullable=False)

    chunk = relationship("Chunk")


class ChunkEntity(Base):
    """Association table: which entities appear in which chunks."""
    __tablename__ = "chunk_entities"

    chunk_id = Column(BigInteger, ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True)
    entity_id = Column(BigInteger, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    confidence = Column(Float, default=1.0)

    chunk = relationship("Chunk")
    entity = relationship("Entity")

    __table_args__ = (
        Index("idx_chunk_entity_chunk", "chunk_id"),
        Index("idx_chunk_entity_entity", "entity_id"),
    )


class Entity(Base):
    """Extracted entity."""
    __tablename__ = "entities"

    id = Column(BigInteger, primary_key=True)
    name = Column(String, nullable=False, index=True)
    type = Column(String)  # person | place | event | object | concept
    metadata_ = Column("metadata", JSONB, default=dict)
    agent_id = Column(String, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class EntityEdge(Base):
    """Entity relationship edge."""
    __tablename__ = "entity_edges"

    id = Column(BigInteger, primary_key=True)
    from_entity_id = Column(BigInteger, ForeignKey("entities.id"), nullable=False)
    to_entity_id = Column(BigInteger, ForeignKey("entities.id"), nullable=False)
    relation_type = Column(String, nullable=False)
    confidence = Column(Float, default=1.0)
    agent_id = Column(String, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_edges_from_to", "from_entity_id", "to_entity_id"),
    )


class AgentState(Base):
    """Agent runtime state (affinity, mood, stage, etc.)."""
    __tablename__ = "agent_state"

    agent_id = Column(String, primary_key=True)
    pack_id = Column(String, nullable=False)
    stage = Column(Integer, default=1)  # 1-5 relationship stage
    affinity = Column(Float, default=0)  # 0-100
    mood = Column(Float, default=50)  # 0-100
    energy = Column(Float, default=50)  # 0-100
    last_interaction = Column(DateTime)
    last_heartbeat = Column(DateTime)
    pending_heartbeat = Column(Boolean, default=False)
    state = Column(JSONB, default=dict)  # Custom key-value state
    version = Column(Integer, default=1, nullable=False)  # Optimistic lock

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_state_pack", "pack_id"),
        Index("idx_state_pending", "pending_heartbeat", postgresql_where="pending_heartbeat = true"),
    )


class Event(Base):
    """Structured event stream."""
    __tablename__ = "events"

    id = Column(BigInteger, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)  # message | heartbeat | mood_change | etc.
    actor = Column(String, nullable=False)  # user | agent | system
    payload = Column(JSONB, nullable=False)
    summary = Column(Text)
    related_chunk_id = Column(BigInteger, ForeignKey("chunks.id"))

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_events_agent_time", "agent_id", text("created_at DESC")),
        Index("idx_events_type", "event_type"),
    )


class EventVector(Base):
    """Vector embedding for events."""
    __tablename__ = "event_vectors"

    event_id = Column(BigInteger, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    embedding = Column(Vector(768), nullable=False)
    model = Column(String, nullable=False)


class Promise(Base):
    """Promise tracking."""
    __tablename__ = "promises"

    id = Column(BigInteger, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    user_id = Column(String)
    content = Column(Text, nullable=False)
    status = Column(String, default="open")  # open | fulfilled | broken | expired
    deadline = Column("due_at", DateTime)
    fulfilled_at = Column(DateTime)
    event_id = Column(BigInteger, ForeignKey("events.id"))

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_promises_agent_status", "agent_id", "status"),
    )


class UserProfile(Base):
    """Cross-agent user profile."""
    __tablename__ = "user_profile"

    user_id = Column(String, primary_key=True)
    display_name = Column(String)
    attributes = Column(JSONB, default=dict)
    updated_by = Column(String)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Pack(Base):
    """Registered Agent Pack."""
    __tablename__ = "packs"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    manifest = Column(JSONB, nullable=False)
    install_path = Column(String)
    enabled = Column(Boolean, default=True)

    installed_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ToolLog(Base):
    """Tool/skill invocation log."""
    __tablename__ = "tool_logs"

    id = Column(BigInteger, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    tool_name = Column(String, nullable=False)
    input_ = Column("input", JSONB)
    output_ = Column("output", JSONB)
    duration_ms = Column(Float)
    success = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
