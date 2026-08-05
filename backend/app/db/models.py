"""SQLAlchemy 2.0 models — `documents`, `conversations`, `answers`, `agent_steps`.

Postgres holds *what the user did*. Azure AI Search holds *what the AI retrieves*
and is owned by the agent service; nothing here duplicates chunk content.

Enums are stored as VARCHAR with a CHECK constraint (`native_enum=False`) rather
than Postgres ENUM types — adding a value later is a no-op instead of a migration
that has to `ALTER TYPE` outside a transaction.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, JSONType, TimestampTZ, utcnow

DOCUMENT_STATUSES = ("pending", "indexing", "indexed", "failed")
CONFIDENCE_LEVELS = ("high", "moderate", "low", "insufficient")
PRIORITY_CLASSES = ("W1", "W2", "W3", "W4", "informational")

DocumentStatus = Enum(
    *DOCUMENT_STATUSES, name="document_status", native_enum=False, create_constraint=True
)
ConfidenceLevel = Enum(
    *CONFIDENCE_LEVELS, name="confidence_level", native_enum=False, create_constraint=True
)
PriorityClassType = Enum(
    *PRIORITY_CLASSES, name="priority_class", native_enum=False, create_constraint=True
)

# The pre-indexed corpus. Fixed so the seeded row, the citation join, and the
# immutability check all agree without a lookup by file name.
CORPUS_DOCUMENT_ID = uuid.UUID("00000000-0000-4000-8000-000000000010")
# What the agent stamps on every corpus chunk (agent/app/ingestion/parse.py).
# Not a UUID, so it is mapped onto CORPUS_DOCUMENT_ID when citations are joined.
CORPUS_DOCUMENT_SLUG = "pandora-corpus"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    record_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(DocumentStatus, nullable=False, default="pending")
    is_preloaded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
    """One row per answered question. The audit trail behind every citation.

    The full nested report lives in `situation_report` as JSON, but the fields
    §1.5 filters on are also lifted into their own columns: a register screen
    should not have to scan JSON to answer "show me the W3s with conflicts".
    """

    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    # A flattened text rendering of the report, kept for conversation
    # coreference on the next turn — not what the frontend renders.
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    # Citations as returned to the frontend, document_name already joined in.
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, nullable=False, default=list
    )
    situation_report: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, default=dict
    )
    insufficient_evidence: Mapped[dict[str, Any] | None] = mapped_column(
        JSONType, nullable=True
    )

    # --- lifted for §1.5 filtering ---
    priority_class: Mapped[str] = mapped_column(
        PriorityClassType, nullable=False, default="informational"
    )
    assembly_mode: Mapped[str] = mapped_column(String(64), nullable=False, default="sitrep")
    confidence: Mapped[str] = mapped_column(ConfidenceLevel, nullable=False)
    affected_region_ids: Mapped[list[str]] = mapped_column(
        JSONType, nullable=False, default=list
    )
    had_conflict: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    was_partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_sufficient_evidence: Mapped[bool] = mapped_column(nullable=False, default=True)

    llm_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, nullable=False, default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="answers")
    steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="answer", cascade="all, delete-orphan", order_by="AgentStep.sequence_number"
    )

    __table_args__ = (
        Index("ix_answers_user_id_created_at", "user_id", "created_at"),
        Index("ix_answers_user_id_priority_class", "user_id", "priority_class"),
    )


class AgentStep(Base):
    """One orchestration trace event, persisted as it streamed.

    Kept so `/api/v1/situation-reports/{id}` can replay a run at full speed
    instead of standing in silence when the live network stalls.
    """

    __tablename__ = "agent_steps"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    answer_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("answers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, nullable=False, default=utcnow)

    answer: Mapped[Answer] = relationship(back_populates="steps")

    __table_args__ = (
        Index("ix_agent_steps_answer_id_sequence", "answer_id", "sequence_number"),
    )
