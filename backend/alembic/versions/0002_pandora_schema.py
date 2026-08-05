"""retarget to Pandora — situation reports, agent_steps, preloaded corpus

Drops the invoice-era `agent_actions` table, widens `documents` and `answers`
for the Situation Report contract, adds the orchestration trace table, and seeds
the preloaded corpus row.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-05
"""

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed so the seeded row, the citation join, and the immutability check agree.
CORPUS_DOCUMENT_ID = uuid.UUID("00000000-0000-4000-8000-000000000010")
# The corpus belongs to no user — it is visible to everyone, and queries for it
# match on `is_preloaded` rather than ownership.
NIL_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def upgrade() -> None:
    # --- the invoice-era table goes (its indexes drop with it) ---
    op.drop_table("agent_actions")

    # --- documents ---
    op.add_column("documents", sa.Column("record_count", sa.Integer(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "is_preloaded", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )

    # --- answers ---
    op.add_column(
        "answers",
        sa.Column("situation_report", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "answers", sa.Column("insufficient_evidence", postgresql.JSONB(), nullable=True)
    )
    op.add_column("answers", sa.Column("assembly_mode", sa.String(length=64),
                                       nullable=False, server_default="sitrep"))
    op.add_column(
        "answers",
        sa.Column("affected_region_ids", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column("answers", sa.Column("had_conflict", sa.Boolean(), nullable=False,
                                       server_default=sa.false()))
    op.add_column("answers", sa.Column("was_partial", sa.Boolean(), nullable=False,
                                       server_default=sa.false()))
    op.add_column("answers", sa.Column("llm_call_count", sa.Integer(), nullable=False,
                                       server_default="0"))
    op.add_column("answers", sa.Column("priority_class", sa.String(length=32),
                                       nullable=False, server_default="informational"))

    # Constraint DDL is written out longhand rather than via
    # op.create_check_constraint: 0001 built these inline through sa.Enum, which
    # bypassed the metadata naming convention, so the existing constraint is
    # literally `confidence_level` and not `ck_answers_confidence_level`. Going
    # through the helper here would silently create a differently-named one.
    op.execute(
        "ALTER TABLE answers ADD CONSTRAINT priority_class "
        "CHECK (priority_class IN ('W1', 'W2', 'W3', 'W4', 'informational'))"
    )

    # The contract says `moderate`, not `medium`. Existing rows are migrated
    # before the CHECK is recreated, or the new constraint would reject them.
    op.execute("ALTER TABLE answers DROP CONSTRAINT confidence_level")
    op.execute("UPDATE answers SET confidence = 'moderate' WHERE confidence = 'medium'")
    op.execute(
        "ALTER TABLE answers ADD CONSTRAINT confidence_level "
        "CHECK (confidence IN ('high', 'moderate', 'low', 'insufficient'))"
    )

    op.create_index(
        "ix_answers_user_id_created_at", "answers", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_answers_user_id_priority_class", "answers", ["user_id", "priority_class"]
    )

    # --- the orchestration trace ---
    op.create_table(
        "agent_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=64), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["answer_id"], ["answers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_steps_answer_id", "agent_steps", ["answer_id"])
    op.create_index(
        "ix_agent_steps_answer_id_sequence", "agent_steps", ["answer_id", "sequence_number"]
    )

    # --- the preloaded corpus ---
    # Without this row, citations resolve to "(document unavailable)" and the
    # knowledge base screen looks empty even though the index is fully seeded.
    documents = sa.table(
        "documents",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("user_id", postgresql.UUID(as_uuid=True)),
        sa.column("file_name", sa.String),
        sa.column("content_type", sa.String),
        sa.column("size_bytes", sa.Integer),
        sa.column("page_count", sa.Integer),
        sa.column("chunk_count", sa.Integer),
        sa.column("record_count", sa.Integer),
        sa.column("status", sa.String),
        sa.column("is_preloaded", sa.Boolean),
        sa.column("uploaded_at", sa.DateTime(timezone=True)),
        sa.column("indexed_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        documents,
        [
            {
                "id": CORPUS_DOCUMENT_ID,
                "user_id": NIL_USER_ID,
                "file_name": "Pandora_RAG_Knowledge_2026.pdf",
                "content_type": "application/pdf",
                "size_bytes": 501366,
                "page_count": 56,
                # Counts are refreshed from the agent's /health at read time —
                # these are the seed-run values and only a fallback.
                "chunk_count": 195,
                "record_count": 149,
                "status": "indexed",
                "is_preloaded": True,
                "uploaded_at": now,
                "indexed_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM documents WHERE id = '{CORPUS_DOCUMENT_ID}'")

    op.drop_table("agent_steps")

    op.drop_index("ix_answers_user_id_priority_class", table_name="answers")
    op.drop_index("ix_answers_user_id_created_at", table_name="answers")

    op.execute("ALTER TABLE answers DROP CONSTRAINT confidence_level")
    op.execute("UPDATE answers SET confidence = 'medium' WHERE confidence = 'moderate'")
    op.execute(
        "ALTER TABLE answers ADD CONSTRAINT confidence_level "
        "CHECK (confidence IN ('high', 'medium', 'low', 'insufficient'))"
    )

    op.execute("ALTER TABLE answers DROP CONSTRAINT priority_class")
    for column in (
        "priority_class",
        "llm_call_count",
        "was_partial",
        "had_conflict",
        "affected_region_ids",
        "assembly_mode",
        "insufficient_evidence",
        "situation_report",
    ):
        op.drop_column("answers", column)

    op.drop_column("documents", "is_preloaded")
    op.drop_column("documents", "record_count")

    op.create_table(
        "agent_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_answer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("citations", postgresql.JSONB(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source_answer_id"], ["answers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_actions_user_id_status", "agent_actions", ["user_id", "status"])
    op.create_index("ix_agent_actions_user_id_type", "agent_actions", ["user_id", "type"])
