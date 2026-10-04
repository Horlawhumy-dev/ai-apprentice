"""Time helpers.

The database stores naive UTC datetimes (``DateTime`` columns with a
``datetime.utcnow`` default), so writes stay naive-UTC. Epoch milliseconds are
computed separately and must be true Unix time: calling ``.timestamp()`` on a
*naive* ``utcnow()`` makes Python reinterpret the UTC wall-clock as local time,
which silently shifts every value by the local UTC offset.
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC, matching the ``DateTime`` columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def epoch_ms() -> int:
    """True Unix epoch milliseconds, independent of the local timezone."""
    return int(datetime.now(timezone.utc).timestamp() * 1000)
