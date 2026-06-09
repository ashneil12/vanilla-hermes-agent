"""Phase 5: planning-gate lane — park/approve flips over a task DAG."""

import sqlite3

from hermes_cli.kanban_db import park_plan, approve_plan, _dag_ids, VALID_STATUSES


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, status TEXT)")
    conn.execute(
        "CREATE TABLE task_links (parent_id TEXT, child_id TEXT, "
        "PRIMARY KEY(parent_id, child_id))"
    )
    return conn


def _tree(conn):
    # root -> c1, c2 ; c1 -> g1   (a 4-node DAG)
    for tid in ("root", "c1", "c2", "g1"):
        conn.execute("INSERT INTO tasks (id, status) VALUES (?, 'todo')", (tid,))
    conn.executemany(
        "INSERT INTO task_links (parent_id, child_id) VALUES (?,?)",
        [("root", "c1"), ("root", "c2"), ("c1", "g1")],
    )


def test_plan_review_is_a_valid_status():
    assert "plan_review" in VALID_STATUSES


def test_dag_ids_walks_whole_tree():
    conn = _db()
    _tree(conn)
    assert _dag_ids(conn, "root") == {"root", "c1", "c2", "g1"}


def test_park_holds_whole_dag():
    conn = _db()
    _tree(conn)
    assert park_plan(conn, "root") == 4
    statuses = {r["id"]: r["status"] for r in conn.execute("SELECT id, status FROM tasks")}
    assert all(s == "plan_review" for s in statuses.values())


def test_park_only_flips_todo_tasks():
    conn = _db()
    _tree(conn)
    conn.execute("UPDATE tasks SET status='running' WHERE id='c2'")
    assert park_plan(conn, "root") == 3  # c2 (running) is left alone
    statuses = {r["id"]: r["status"] for r in conn.execute("SELECT id, status FROM tasks")}
    assert statuses["c2"] == "running"


def test_approve_promotes_parked_dag_back_to_todo():
    conn = _db()
    _tree(conn)
    park_plan(conn, "root")
    assert approve_plan(conn, "root") == 4
    assert all(r["status"] == "todo" for r in conn.execute("SELECT status FROM tasks"))


def test_approve_is_guarded_and_idempotent():
    conn = _db()
    _tree(conn)  # nothing parked
    assert approve_plan(conn, "root") == 0  # only flips plan_review rows
