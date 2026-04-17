from __future__ import annotations

from datetime import datetime
from typing import Any


def has_useful_text(text: str | None) -> bool:
    return bool(text and text.strip())


def build_markdown_chunks(
    group_name: str,
    window_start: datetime,
    window_end: datetime,
    messages: list[Any],
    max_chars: int,
) -> list[str]:
    """Create one or more markdown chunks from WhatsApp messages."""

    if max_chars < 200:
        raise ValueError("max_chars precisa ser maior ou igual a 200")

    formatted_entries = _format_entries(messages=messages, timezone=window_start.tzinfo)
    if not formatted_entries:
        return []

    grouped_entries: list[list[str]] = []
    current_group: list[str] = []

    for entry in formatted_entries:
        candidate = current_group + [entry]
        candidate_chunk = _render_chunk(
            group_name=group_name,
            window_start=window_start,
            window_end=window_end,
            entries=candidate,
            part_index=1,
            part_total=1,
        )
        if current_group and len(candidate_chunk) > max_chars:
            grouped_entries.append(current_group)
            current_group = [entry]
            continue
        current_group = candidate

    if current_group:
        grouped_entries.append(current_group)

    total_parts = len(grouped_entries)
    return [
        _render_chunk(
            group_name=group_name,
            window_start=window_start,
            window_end=window_end,
            entries=entries,
            part_index=part_index,
            part_total=total_parts,
        )
        for part_index, entries in enumerate(grouped_entries, start=1)
    ]


def count_messages_with_useful_text(messages: list[Any]) -> int:
    return sum(1 for message in messages if has_useful_text(_extract_field(message, "text") or ""))


def _render_chunk(
    group_name: str,
    window_start: datetime,
    window_end: datetime,
    entries: list[str],
    part_index: int,
    part_total: int,
) -> str:
    header_lines = [
        f"# Conversa do grupo: {group_name}",
        "",
        (
            "Periodo: "
            f"{window_start.strftime('%Y-%m-%d %H:%M:%S %z')} "
            f"ate {window_end.strftime('%Y-%m-%d %H:%M:%S %z')}"
        ),
    ]

    if part_total > 1:
        header_lines.extend(["", f"## Parte {part_index} de {part_total}"])

    header_lines.append("")
    body = "\n".join(entries)
    return "\n".join(header_lines) + body + "\n"


def _format_entries(messages: list[Any], timezone: Any) -> list[str]:
    sortable_entries: list[tuple[datetime, str]] = []
    for message in messages:
        text = _extract_field(message, "text")
        if not has_useful_text(text):
            continue

        timestamp = _extract_field(message, "timestamp")
        sender = _extract_field(message, "sender")
        if not isinstance(timestamp, datetime):
            raise ValueError("mensagem sem timestamp valido")
        if timestamp.tzinfo is None:
            raise ValueError("mensagem sem timezone")

        localized = timestamp.astimezone(timezone)
        safe_sender = str(sender).strip() or "Desconhecido"
        safe_text = str(text).strip()
        entry = f"[{localized.strftime('%Y-%m-%d %H:%M')}] {safe_sender}:\n{safe_text}\n"
        sortable_entries.append((localized, entry))

    sortable_entries.sort(key=lambda item: item[0])
    return [entry for _, entry in sortable_entries]


def _extract_field(message: Any, field_name: str) -> Any:
    if isinstance(message, dict):
        return message.get(field_name)
    return getattr(message, field_name, None)
