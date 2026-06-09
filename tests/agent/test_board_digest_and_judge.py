"""Phase 3: board digest serializer + judge_goal board_state plumbing."""

from hermes_cli.mission import format_board_digest
from hermes_cli.goals import judge_goal


def test_digest_lane_counts_and_completion():
    d = format_board_digest({"done": 3, "running": 1, "todo": 2})
    assert "todo=2" in d and "running=1" in d and "done=3" in d
    assert "completion: 3/6 tasks done" in d


def test_digest_empty_board():
    d = format_board_digest({})
    assert "lanes: empty" in d
    assert "completion: 0/0 tasks done" in d


def test_digest_blocked_leaves_first():
    leaves = [
        {"id": "t2", "title": "build", "status": "running"},
        {"id": "t1", "title": "deploy", "status": "blocked"},
    ]
    d = format_board_digest({"running": 1, "blocked": 1}, leaves)
    # blocked task must appear before the running one
    assert d.index("t1") < d.index("t2")


def test_digest_truncates_under_max_chars():
    leaves = [{"id": f"t{i}", "title": "x" * 50, "status": "todo"} for i in range(200)]
    d = format_board_digest({"todo": 200}, leaves, max_chars=400)
    assert len(d) <= 460  # bounded (+ the truncation marker line)
    assert "truncated" in d


# --- judge_goal board_state plumbing: exercised via the no-LLM short-circuits ---
def test_judge_goal_accepts_board_state_empty_goal_skips():
    verdict, _reason, parse_failed = judge_goal("", "some response", board_state="lanes: done=1")
    assert verdict == "skipped"
    assert parse_failed is False


def test_judge_goal_accepts_board_state_empty_response_continues():
    verdict, _reason, parse_failed = judge_goal("ship X", "", board_state="lanes: done=1")
    assert verdict == "continue"
    assert parse_failed is False
