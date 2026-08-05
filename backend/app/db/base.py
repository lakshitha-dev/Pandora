"""Declarative base and the column types shared across models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import JSON, TypeDecorator

# Predictable constraint names so Alembic autogenerate produces stable migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class GUID(TypeDecorator):
    """UUID that is native on Postgres and a 36-char string elsewhere (tests on SQLite)."""

    impl = PG_UUID
    cache_ok = True

    def load_dialect_impl(self, dialect):  # noqa: ANN001, ANN201
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        from sqlalchemy import String

        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):  # noqa: ANN001, ANN201
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):  # noqa: ANN001, ANN201
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


# JSONB on Postgres, plain JSON on anything else.
JSONType = JSON().with_variant(JSONB(), "postgresql")

# All timestamps are timezone-aware, stored as timestamptz, serialized as ISO 8601 UTC.
TimestampTZ = DateTime(timezone=True)


def utcnow() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)
