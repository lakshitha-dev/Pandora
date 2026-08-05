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
CONFIDENCE_LEVELS = ("high", "moderate", "low", "insufficient")
ROLE_LENSES = ("guardian", "researcher", "citizen")

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
RoleLensType = Enum(*ROLE_LENSES, name="role_lens", native_enum=False, create_constraint=True)


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
    """One answered question and the Situation Report it produced.

    The report is stored as the §1.1 JSON the frontend received, verbatim — it is
    the audit trail, so it must not drift as the schema evolves. The scalar
    columns beside it are denormalised copies that let `/api/v1/situation-reports`
    filter and sort (§1.5) without opening the JSON on every row.
    """

    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    # The lens the question was asked under. Display-only — the report is the
    # same under every lens; the frontend re-renders it client-side.
    role_lens: Mapped[str] = mapped_column(RoleLensType, nullable=False, default="guardian")
    situation_report: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, default=dict
    )
    # Citations as returned to the frontend, document_name already joined in.
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, nullable=False, default=list
    )
    # The §1.4 object. Non-null only when has_sufficient_evidence is false.
    insufficient_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    # The §1.2 trace in sequence_number order, as the browser saw it. Empty for
    # a non-streamed answer. Replay is demo insurance: if the live network
    # stalls, we replay a cached trace at full speed instead of standing in
    # silence (§1.5).
    agent_steps: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, nullable=False, default=list
    )

    confidence: Mapped[str] = mapped_column(ConfidenceLevel, nullable=False)
    groundedness: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    priority_class: Mapped[str] = mapped_column(String(20), nullable=False, default="informational")
    assembly_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="sitrep")
    affected_region_ids: Mapped[list[str]] = mapped_column(
        JSONType, nullable=False, default=list
    )
    citation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    had_conflict: Mapped[bool] = mapped_column(nullable=False, default=False)
    was_partial: Mapped[bool] = mapped_column(nullable=False, default=False)
    has_sufficient_evidence: Mapped[bool] = mapped_column(nullable=False, default=True)
    llm_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TimestampTZ, nullable=False, default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="answers")

    __table_args__ = (
        # §1.5 lists a user's past reports newest-first, optionally by priority.
        Index("ix_answers_user_id_created_at", "user_id", "created_at"),
    )


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
