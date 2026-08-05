"""SQLAlchemy 2.0 models — `documents`, `conversations`, `answers`, `agent_actions`.

Postgres holds *what the user did*. Azure AI Search holds *what the AI retrieves*
and is owned by the agent service; nothing here duplicates chunk content.

Enums are stored as VARCHAR with a CHECK constraint (`native_enum=False`) rather
than Postgres ENUM types — adding a value later is a no-op instead of a migration
that has to `ALTER TYPE` outside a transaction.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, JSONType, TimestampTZ, utcnow

DOCUMENT_STATUSES = ("pending", "indexing", "indexed", "failed")
ACTION_TYPES = ("flag_invoice", "draft_email", "create_task")
ACTION_STATUSES = ("proposed", "approved", "rejected", "completed")
CONFIDENCE_LEVELS = ("high", "medium", "low", "insufficient")

DocumentStatus = Enum(
    *DOCUMENT_STATUSES, name="document_status", native_enum=False, create_constraint=True
)
ActionType = Enum(*ACTION_TYPES, name="action_type", native_enum=False, create_constraint=True)
ActionStatus = Enum(
    *ACTION_STATUSES, name="action_status", native_enum=False, create_constraint=True
)
ConfidenceLevel = Enum(
    *CONFIDENCE_LEVELS, name="confidence_level", native_enum=False, create_constraint=True
)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(DocumentStatus, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(TimestampTZ, nullable=False, default=utcnow)
    indexed_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=True)

    __table_args__ = (Index("ix_documents_user_id_status", "user_id", "status"),)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, nullable=False, default=utcnow)

    answers: Mapped[list["Answer"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Answer(Base):
    """One row per answered question. The audit trail behind every citation."""

    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    # Citations as returned to the frontend, document_name already joined in.
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, nullable=False, default=list
    )
    confidence: Mapped[str] = mapped_column(ConfidenceLevel, nullable=False)
    has_sufficient_evidence: Mapped[bool] = mapped_column(nullable=False, default=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, nullable=False, default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="answers")


class AgentAction(Base):
    """A proposed action. Nothing here executes without an explicit approval."""

    __tablename__ = "agent_actions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    type: Mapped[str] = mapped_column(ActionType, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(ActionStatus, nullable=False, default="proposed")
    source_answer_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("answers.id", ondelete="SET NULL"), nullable=True
    )
    # Snapshot of the citations that justified the action, frozen at creation:
    # the evidence must survive the source document being deleted.
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, nullable=False, default=list
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, nullable=False, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(TimestampTZ, nullable=True)

    __table_args__ = (
        Index("ix_agent_actions_user_id_status", "user_id", "status"),
        Index("ix_agent_actions_user_id_type", "user_id", "type"),
    )
