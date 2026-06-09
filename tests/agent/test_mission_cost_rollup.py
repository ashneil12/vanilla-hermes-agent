"""Phase 0b-0d: fleet-scale cost rollup + board cost cap (Operator OS mission mode)."""

import sqlite3

from hermes_cli.kanban_db import (
    board_spend,
    board_cost_exceeded,
    _add_column_if_missing,
)


def _runs_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE task_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "task_id TEXT, cost_usd REAL, tokens_total INTEGER)"
    )
    return conn


def test_board_spend_sums_and_ignores_nulls():
    conn = _runs_conn()
    conn.executemany(
        "INSERT INTO task_runs (task_id, cost_usd, tokens_total) VALUES (?,?,?)",
        [("t1", 0.50, 1000), ("t2", 1.25, 2500), ("t3", None, None)],
    )
    usd, tokens = board_spend(conn)
    assert abs(usd - 1.75) < 1e-9
    assert tokens == 3500


def test_board_spend_empty_is_zero():
    assert board_spend(_runs_conn()) == (0.0, 0)


def test_board_cost_exceeded_usd():
    conn = _runs_conn()
    conn.execute("INSERT INTO task_runs (task_id, cost_usd, tokens_total) VALUES ('t', 2.0, 100)")
    assert board_cost_exceeded(conn, usd_ceiling=2.0) is True
    assert board_cost_exceeded(conn, usd_ceiling=3.0) is False


def test_board_cost_token_primary_when_usd_included():
    # Owned/subscription route: $ stays 0.0 but tokens accumulate. Token ceiling
    # must still halt the fleet even though the dollar ceiling never trips.
    conn = _runs_conn()
    conn.execute("INSERT INTO task_runs (task_id, cost_usd, tokens_total) VALUES ('t', 0.0, 5000)")
    assert board_cost_exceeded(conn, usd_ceiling=2.0, token_ceiling=5000) is True
    assert board_cost_exceeded(conn, usd_ceiling=2.0) is False


def test_board_cost_disabled_never_exceeds():
    conn = _runs_conn()
    conn.execute("INSERT INTO task_runs (task_id, cost_usd, tokens_total) VALUES ('t', 999.0, 1000000000)")
    assert board_cost_exceeded(conn) is False


def test_cost_columns_add_idempotently():
    # Exercises exactly the two migration lines added to _migrate_add_optional_columns.
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE task_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT)")
    assert _add_column_if_missing(conn, "task_runs", "cost_usd", "cost_usd REAL") is True
    assert _add_column_if_missing(conn, "task_runs", "tokens_total", "tokens_total INTEGER") is True
    # Idempotent: a second run finds the column present and does not raise.
    assert _add_column_if_missing(conn, "task_runs", "cost_usd", "cost_usd REAL") is False
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(task_runs)")}
    assert "cost_usd" in cols and "tokens_total" in cols
