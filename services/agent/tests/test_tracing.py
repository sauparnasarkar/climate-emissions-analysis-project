"""Unit tests for tracing.py -- no network, no graph construction needed."""

import logging

from agent.tracing import TraceIdFilter, new_trace_id, trace_id_var


def test_new_trace_id_is_unique():
    assert new_trace_id() != new_trace_id()


def test_trace_id_filter_defaults_to_dash():
    record = logging.LogRecord("agent.graph", logging.INFO, __file__, 1, "msg", None, None)
    assert TraceIdFilter().filter(record) is True
    assert record.trace_id == "-"


def test_trace_id_filter_reads_current_contextvar_value():
    token = trace_id_var.set("abc123")
    try:
        record = logging.LogRecord("agent.graph", logging.INFO, __file__, 1, "msg", None, None)
        TraceIdFilter().filter(record)
        assert record.trace_id == "abc123"
    finally:
        trace_id_var.reset(token)
