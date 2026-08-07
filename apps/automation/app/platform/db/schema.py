"""Schema lifecycle helpers shared by the Alembic baseline migration and the test harness.

Keeping the extension + ENUM type creation in one place guarantees the migration-built
database and the create_all-built test database are byte-for-byte the same shape.
"""

from __future__ import annotations

from sqlalchemy import Connection, text
from sqlalchemy.dialects.postgresql import ENUM

# import models for side effect: register tables on Base.metadata
from app.platform.db import models  # noqa: F401
from app.platform.db.base import Base
from app.platform.db.enums import PG_ENUMS


def ensure_extensions(conn: Connection) -> None:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def create_enum_types(conn: Connection) -> None:
    for name, enum_cls in PG_ENUMS.items():
        ENUM(*[e.value for e in enum_cls], name=name, create_type=True).create(
            conn, checkfirst=True
        )


def drop_enum_types(conn: Connection) -> None:
    for name in PG_ENUMS:
        conn.execute(text(f'DROP TYPE IF EXISTS "{name}" CASCADE'))


def create_all(conn: Connection) -> None:
    ensure_extensions(conn)
    create_enum_types(conn)
    Base.metadata.create_all(bind=conn)


def drop_all(conn: Connection) -> None:
    Base.metadata.drop_all(bind=conn)
    drop_enum_types(conn)
