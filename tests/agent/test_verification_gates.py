"""Phase 4: verification gate parsing, head-SHA pin, mission DONE conjunction."""

import json

from hermes_cli.mission import (
    verifier_gate_from_metadata,
    head_sha_unchanged,
    mission_done,
)


def test_gate_from_dict():
    assert verifier_gate_from_metadata({"gate": "pass"}) is True
    assert verifier_gate_from_metadata({"gate": "PASS"}) is True
    assert verifier_gate_from_metadata({"gate": "fail"}) is False
    assert verifier_gate_from_metadata({"gate": "maybe"}) is None
    assert verifier_gate_from_metadata({}) is None


def test_gate_from_json_string():
    assert verifier_gate_from_metadata(json.dumps({"gate": "pass"})) is True
    assert verifier_gate_from_metadata(json.dumps({"gate": "fail"})) is False
    assert verifier_gate_from_metadata("not json") is None


def test_gate_from_none_and_non_dict():
    assert verifier_gate_from_metadata(None) is None
    assert verifier_gate_from_metadata(123) is None
    assert verifier_gate_from_metadata([1, 2]) is None


def test_head_sha_pin():
    assert head_sha_unchanged("abc123", "abc123") is True
    assert head_sha_unchanged("abc123", "def456") is False
    assert head_sha_unchanged(None, "abc123") is False  # fail closed
    assert head_sha_unchanged("abc123", None) is False
    assert head_sha_unchanged("", "") is False


def test_mission_done_conjunction():
    # all true -> done
    assert mission_done(True, [True, True], True) is True
    # no children + final gate + judge -> done (e.g. single-task mission)
    assert mission_done(True, [], True) is True
    # judge not done -> not done
    assert mission_done(False, [True], True) is False
    # a failing child gate -> not done
    assert mission_done(True, [True, False], True) is False
    # a None (un-verified) child gate is NOT a pass -> not done
    assert mission_done(True, [True, None], True) is False
    # final verifier failed -> not done
    assert mission_done(True, [True], False) is False
