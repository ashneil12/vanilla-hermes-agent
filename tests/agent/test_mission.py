"""Phase 2: Mission object, registry, deterministic tick, no-progress, heartbeat."""

from hermes_cli.mission import (
    Mission,
    board_fingerprint,
    is_no_progress,
    decide_tick,
    save_mission,
    load_mission,
    list_active_mission_ids,
    pause_mission,
    mark_done,
    write_supervisor_heartbeat,
    supervisor_heartbeat_stale,
    STATUS_RUNNING,
    STATUS_DONE,
)


class FakeStore:
    def __init__(self):
        self.d = {}

    def get(self, key):
        return self.d.get(key)

    def set(self, key, value):
        self.d[key] = value


def _mission(**kw):
    base = dict(id="m1", goal_session_id="s1", root_task_id="t_root", max_turns=20)
    base.update(kw)
    return Mission(**base)


def test_mission_json_roundtrip_and_forward_compat():
    m = _mission(token_ceiling=1000, fp_history=["a", "b"])
    m2 = Mission.from_json(m.to_json())
    assert m2.id == "m1" and m2.token_ceiling == 1000 and m2.fp_history == ["a", "b"]
    # Unknown future keys must not break loading.
    import json
    raw = json.loads(m.to_json())
    raw["some_future_field"] = 123
    m3 = Mission.from_json(json.dumps(raw))
    assert m3.id == "m1"


def test_board_fingerprint_stable_and_sensitive():
    a = board_fingerprint({"done": 2, "running": 1})
    b = board_fingerprint({"running": 1, "done": 2})  # key order irrelevant
    c = board_fingerprint({"done": 3, "running": 0})
    assert a == b
    assert a != c


def test_is_no_progress():
    assert is_no_progress(["x", "x"]) is False  # < repeat(3)
    assert is_no_progress(["x", "x", "x"]) is True
    assert is_no_progress(["x", "y", "x"]) is False
    assert is_no_progress(["a", "x", "x", "x"]) is True


def test_decide_tick_budget_halt_token_primary():
    m = _mission(board_token_ceiling=5000, board_usd_ceiling=None)
    d = decide_tick(m, board_usd_spent=0.0, board_tokens_spent=5000,
                    active_agents=1, new_fingerprint="f1")
    assert d.action == "halt" and d.halt_reason == "BUDGET_CEILING"


def test_decide_tick_turn_budget_halt():
    m = _mission(max_turns=3, turns_used=3)
    d = decide_tick(m, board_usd_spent=0.0, board_tokens_spent=0,
                    active_agents=0, new_fingerprint="f1")
    assert d.action == "halt" and d.halt_reason == "TURN_BUDGET_EXHAUSTED"


def test_decide_tick_no_progress_halt():
    m = _mission()
    for _ in range(2):
        decide_tick(m, board_usd_spent=0, board_tokens_spent=0, active_agents=1, new_fingerprint="same")
    d = decide_tick(m, board_usd_spent=0, board_tokens_spent=0, active_agents=1, new_fingerprint="same")
    assert d.action == "halt" and d.halt_reason == "NO_PROGRESS"


def test_decide_tick_normal_spawn_and_throttle():
    m = _mission(global_agent_ceiling=4)
    d = decide_tick(m, board_usd_spent=0, board_tokens_spent=0, active_agents=1, new_fingerprint="f1")
    assert d.action == "spawn" and d.throttle is False
    d2 = decide_tick(m, board_usd_spent=0, board_tokens_spent=0, active_agents=4, new_fingerprint="f2")
    assert d2.action == "spawn" and d2.throttle is True


def test_registry_save_load_index():
    store = FakeStore()
    m = _mission()
    save_mission(m, store=store)
    assert list_active_mission_ids(store=store) == ["m1"]
    loaded = load_mission("m1", store=store)
    assert loaded is not None and loaded.root_task_id == "t_root"
    # done removes from the active index but the row is retained for audit.
    mark_done(m, store=store)
    assert list_active_mission_ids(store=store) == []
    assert load_mission("m1", store=store).status == STATUS_DONE


def test_pause_records_reason_and_deindexes():
    store = FakeStore()
    m = _mission()
    save_mission(m, store=store)
    pause_mission(m, "BUDGET_CEILING", store=store)
    assert list_active_mission_ids(store=store) == []
    assert load_mission("m1", store=store).paused_reason == "BUDGET_CEILING"


def test_heartbeat_staleness():
    store = FakeStore()
    assert supervisor_heartbeat_stale(store=store, now=1000.0) is False  # never started
    write_supervisor_heartbeat(store=store, now=1000.0)
    assert supervisor_heartbeat_stale(store=store, now=1100.0, threshold_seconds=600) is False
    assert supervisor_heartbeat_stale(store=store, now=2000.0, threshold_seconds=600) is True
