"""Cursor pagination: `?limit=20`, then `?limit=20&cursor=<next_cursor>` for the next page.

A cursor marks the last item of the previous page (newest first), so pages stay
correct while new items are added.
"""

import base64
import json
from datetime import datetime

from sqlalchemy import Select, and_, or_
from sqlalchemy.orm import Session

from api.errors import APIError

MAX_LIMIT = 100


def _encode(value, row_id) -> str:
    raw = {"v": value.isoformat() if isinstance(value, datetime) else value,
           "dt": isinstance(value, datetime), "id": row_id}
    return base64.urlsafe_b64encode(json.dumps(raw).encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple:
    try:
        raw = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        value = datetime.fromisoformat(raw["v"]) if raw["dt"] else raw["v"]
        return value, raw["id"]
    except Exception as exc:
        raise APIError(400, "invalid_cursor", "The cursor is not valid; start again without it.") from exc


def paginate(db: Session, query: Select, sort_column, id_column, limit: int, cursor: str | None) -> tuple[list, str | None]:
    """One page of `query`, newest first by `sort_column` (ties broken by `id_column`)."""
    if cursor:
        value, last_id = _decode(cursor)
        query = query.where(or_(sort_column < value, and_(sort_column == value, id_column < last_id)))
    rows = list(db.scalars(query.order_by(sort_column.desc(), id_column.desc()).limit(limit + 1)))
    if len(rows) <= limit:
        return rows, None
    last = rows[limit - 1]
    return rows[:limit], _encode(getattr(last, sort_column.key), getattr(last, id_column.key))
