"""Connection to the app database (DATABASE_URL; SQLite by default, PostgreSQL later).

Tables are created on first use. `session()` opens a unit of work:

    with session() as db:
        db.add(...)
        db.commit()
"""

from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from database.models import Base
from utils.config import get_settings

_SQLITE_PREFIX = "sqlite:///"


def _sqlite_pragmas(connection, _record) -> None:
    cursor = connection.cursor()
    # WAL lets the API read while the worker writes; foreign keys make deletes cascade
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if url.startswith(_SQLITE_PREFIX):
        Path(url.removeprefix(_SQLITE_PREFIX)).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
        event.listen(engine, "connect", _sqlite_pragmas)
    else:
        engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine


def session() -> Session:
    # expire_on_commit=False: objects stay readable after commit (e.g. to return them)
    return Session(get_engine(), expire_on_commit=False)
