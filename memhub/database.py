"""Database models and initialization for Memory Hub."""

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, ForeignKey, Index, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import ARRAY
from datetime import datetime
from pgvector.sqlalchemy import Vector
from memhub.config import settings

Base = declarative_base()


class User(Base):
    """User accounts."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    # Relationships
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_username", "username"),
        Index("idx_email", "email"),
    )


class APIKey(Base):
    """API Keys for long-term authentication (e.g., MCP clients)."""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256 hash
    key_prefix = Column(String(8), nullable=False)  # First 8 chars for identification
    name = Column(String(100), nullable=False)  # Description/name for the key
    expires_at = Column(DateTime, nullable=True)  # NULL = never expires
    last_used_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="api_keys")

    __table_args__ = (
        Index("idx_key_hash", "key_hash"),
        Index("idx_user_active", "user_id", "is_active"),
    )


class Conversation(Base):
    """Stores conversation messages with vector embeddings."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    platform = Column(String(50))  # 'claude', 'chatgpt', etc.
    embedding = Column(Vector(settings.embedding_dimensions))
    extra_metadata = Column(Text)  # JSON string for additional metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    entities = relationship("Entity", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_session", "user_id", "session_id"),
        Index("idx_created_at", "created_at"),
    )


class Entity(Base):
    """Stores entities extracted from conversations for knowledge graph."""

    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    entity_type = Column(String(100), nullable=False)  # 'person', 'topic', 'concept', etc.
    entity_name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    embedding = Column(Vector(settings.embedding_dimensions))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="entities")

    __table_args__ = (
        Index("idx_entity_name", "entity_name"),
        Index("idx_entity_type", "entity_type"),
    )


class Relationship(Base):
    """Stores relationships between entities for knowledge graph."""

    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    target_entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    relationship_type = Column(String(100), nullable=False)  # 'related_to', 'discusses', etc.
    weight = Column(Float, default=1.0)  # Relationship strength
    extra_metadata = Column(Text)  # JSON string for additional metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_source_target", "source_entity_id", "target_entity_id"),
        Index("idx_relationship_type", "relationship_type"),
    )


class Summary(Base):
    """Stores conversation summaries."""

    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    session_id = Column(String(255), index=True)
    summary_text = Column(Text, nullable=False)
    summary_type = Column(String(50))  # 'session', 'daily', 'topic', etc.
    embedding = Column(Vector(settings.embedding_dimensions))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_user_summary", "user_id", "summary_type"),
    )


# Database engine and session
engine = create_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,  # Verify connections before using them to prevent stale connection errors
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database and create tables."""
    # Create pgvector extension if not exists
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
