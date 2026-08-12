from mcp_server.trimming import MAX_ROWS, trim


def _rows(n):
    return [{"country": f"C{i}", "value": i} for i in range(n)]


def test_no_trimming_when_at_or_under_cap():
    rows = _rows(MAX_ROWS)
    trimmed, note = trim(rows, scope_label="x", sort_key_label="y", sort_key=lambda r: r["value"])
    assert trimmed == rows
    assert note is None


def test_trims_and_sorts_when_over_cap():
    rows = _rows(MAX_ROWS + 5)
    trimmed, note = trim(rows, scope_label="Expanded", sort_key_label="value descending", sort_key=lambda r: r["value"])
    assert len(trimmed) == MAX_ROWS
    assert [r["value"] for r in trimmed] == list(range(MAX_ROWS + 4, 4, -1))
    assert note == f"Showing {MAX_ROWS} of {MAX_ROWS + 5} countries (Expanded), sorted by value descending"


def test_presorted_input_is_only_sliced_not_resorted():
    rows = list(reversed(_rows(MAX_ROWS + 3)))  # already "sorted" descending by construction
    trimmed, note = trim(rows, scope_label="x", sort_key_label="y")
    assert trimmed == rows[:MAX_ROWS]
    assert note is not None


def test_ascending_sort_when_reverse_false():
    rows = _rows(MAX_ROWS + 2)
    trimmed, _ = trim(rows, scope_label="x", sort_key_label="y", sort_key=lambda r: r["value"], reverse=False)
    assert [r["value"] for r in trimmed] == list(range(MAX_ROWS))
