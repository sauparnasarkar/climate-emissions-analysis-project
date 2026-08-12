"""Response trimming & scope_note (SPEC.md §3.2).

Trigger is "no explicit countries given," not "multi-country" -- every caller of `trim()`
applies it only on the broad/default-scope path, never when the agent passed a specific
country list (trimming there would silently drop something asked for). Absence of a
scope_note on a response is itself informative ("this is everything") -- `trim()` returns
None rather than an empty-but-present note when nothing was actually trimmed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

MAX_ROWS = 10


def trim(
    rows: list[dict[str, Any]],
    *,
    scope_label: str,
    sort_key_label: str,
    sort_key: Callable[[dict[str, Any]], Any] | None = None,
    reverse: bool = True,
) -> tuple[list[dict[str, Any]], str | None]:
    """Cap `rows` at MAX_ROWS and build the accompanying scope_note.

    `sort_key=None` means `rows` is already sorted the way the caller wants (e.g. the
    wrapped API pre-sorted it) -- `trim()` only slices in that case, it never re-sorts.
    Returns (trimmed_rows, scope_note); scope_note is None when `rows` was already at or
    under MAX_ROWS, since no trimming happened.
    """
    total = len(rows)
    if total <= MAX_ROWS:
        return rows, None
    ordered = sorted(rows, key=sort_key, reverse=reverse) if sort_key is not None else rows
    trimmed = ordered[:MAX_ROWS]
    note = f"Showing {len(trimmed)} of {total} countries ({scope_label}), sorted by {sort_key_label}"
    return trimmed, note
