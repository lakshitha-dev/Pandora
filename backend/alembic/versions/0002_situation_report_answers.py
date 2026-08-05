"""answers hold a Situation Report, not a text answer (API_CONTRACT §1.1)

The gateway was built against a plain `answer` string. Pandora's contract returns
a six-section Situation Report, so `answers.answer` becomes `answers.situation_report`
(the §1.1 JSON, verbatim) with the filterable fields §1.5 needs beside it.

Data is dropped, not migrated: the old rows hold SME-assistant answers that no
longer parse as a report, and there is no production data at this point.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_LENS = sa.Enum(
    "guardian", "researcher", "citizen",
    name="role_lens", native_enum=False, create_constraint=True,
)
OLD_CONFIDENCE_LEVEL = sa.Enum(
    "high", "medium", "low", "insufficient",
    name="confidence_level", native_enum=False, create_constraint=True,
)
NEW_CONFIDENCE_LEVEL = sa.Enum(
    "high", "moderate", "low", "insufficient",
    name="confidence_level", native_enum=False, create_constraint=True,
)

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    # Existing rows cannot produce a report; clear before adding NOT NULL columns.
    op.execute(sa.text("DELETE FROM answers"))

    op.drop_column("answers", "answer")

    op.add_column(
        "answers",
        sa.Column("role_lens", ROLE_LENS, nullable=False, server_default="guardian"),
    )
    op.add_column(
        "answers",
        sa.Column("situation_report", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column("answers", sa.Column("insufficient_evidence", JSONB, nullable=True))
    op.add_column(
        "answers",
        sa.Column("agent_steps", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "answers", sa.Column("groundedness", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "answers",
        sa.Column(
            "priority_class", sa.String(length=20), nullable=False, server_default="informational"
        ),
    )
    op.add_column(
        "answers",
        sa.Column("assembly_mode", sa.String(length=32), nullable=False, server_default="sitrep"),
    )
    op.add_column(
        "answers",
        sa.Column(
            "affected_region_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
    )
    op.add_column(
        "answers", sa.Column("citation_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "answers", sa.Column("had_conflict", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "answers", sa.Column("was_partial", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "answers", sa.Column("llm_call_count", sa.Integer(), nullable=False, server_default="0")
    )

    # "medium" → "moderate": §1.1 names the middle confidence level differently.
    op.drop_constraint("ck_answers_confidence_level", "answers", type_="check")
    NEW_CONFIDENCE_LEVEL.create(op.get_bind(), checkfirst=True)
    op.create_check_constraint(
        "confidence_level",
        "answers",
        sa.column("confidence").in_(["high", "moderate", "low", "insufficient"]),
    )

    op.create_index("ix_answers_user_id_created_at", "answers", ["user_id", "created_at"])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM answers"))
    op.drop_index("ix_answers_user_id_created_at", table_name="answers")

    op.drop_constraint("ck_answers_confidence_level", "answers", type_="check")
    OLD_CONFIDENCE_LEVEL.create(op.get_bind(), checkfirst=True)
    op.create_check_constraint(
        "confidence_level",
        "answers",
        sa.column("confidence").in_(["high", "medium", "low", "insufficient"]),
    )

    for column in (
        "agent_steps",
        "llm_call_count",
        "was_partial",
        "had_conflict",
        "citation_count",
        "affected_region_ids",
        "assembly_mode",
        "priority_class",
        "groundedness",
        "insufficient_evidence",
        "situation_report",
        "role_lens",
    ):
        op.drop_column("answers", column)

    op.add_column(
        "answers", sa.Column("answer", sa.Text(), nullable=False, server_default="")
    )
