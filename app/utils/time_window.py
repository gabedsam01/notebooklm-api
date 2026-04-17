from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def compute_daily_window(date_reference: date, timezone_name: str) -> tuple[datetime, datetime]:
    """Return previous day 21:00:00 to current day 20:59:59 for timezone."""

    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"timezone invalido: {timezone_name}") from exc

    window_start = datetime.combine(
        date_reference - timedelta(days=1),
        time(hour=21, minute=0, second=0),
        tzinfo=timezone,
    )
    window_end = datetime.combine(
        date_reference,
        time(hour=20, minute=59, second=59),
        tzinfo=timezone,
    )
    return window_start, window_end


def filter_messages_by_window(
    messages: list[Any],
    start: datetime,
    end: datetime,
) -> list[Any]:
    """Filter messages whose timestamps are inside [start, end]."""

    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start e end precisam ter timezone")

    filtered: list[Any] = []
    for message in messages:
        timestamp = _extract_timestamp(message)
        if timestamp.tzinfo is None:
            raise ValueError("todas as mensagens precisam de timestamp com timezone")

        localized = timestamp.astimezone(start.tzinfo)
        if start <= localized <= end:
            filtered.append(message)

    return filtered


def _extract_timestamp(message: Any) -> datetime:
    if isinstance(message, dict):
        timestamp = message.get("timestamp")
    else:
        timestamp = getattr(message, "timestamp", None)

    if not isinstance(timestamp, datetime):
        raise ValueError("mensagem sem timestamp valido")
    return timestamp
