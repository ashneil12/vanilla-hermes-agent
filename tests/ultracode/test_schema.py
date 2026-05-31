"""Unit tests for ultracode.schema — pure, no runtime."""

import pytest

from agent.ultracode.schema import (
    Finding,
    StageResult,
    SubtaskSpec,
    Verdict,
    VerifyLens,
    VerifierVote,
    dedupe_findings,
)


def test_finding_requires_nonempty_claim():
    with pytest.raises(ValueError):
        Finding(claim="").validate()
    with pytest.raises(ValueError):
        Finding(claim="   ").validate()


def test_finding_roundtrip_json():
    f = Finding(
        claim="off-by-one in loop",
        evidence="index goes to len, not len-1",
        locator="foo.py:42",
        severity="high",
        verdict=Verdict.CONFIRMED,
        votes=[VerifierVote(VerifyLens.CORRECTNESS, Verdict.CONFIRMED, "checked", refuted=False)],
        survived=True,
    ).validate()
    d = f.as_dict()
    assert d["verdict"] == "confirmed"
    assert d["votes"][0]["lens"] == "correctness"
    assert d["dedup_key"].startswith("loc::foo.py:42")
    f2 = Finding.from_dict(d)
    assert f2.claim == f.claim
    assert f2.verdict == Verdict.CONFIRMED
    assert f2.votes[0].lens == VerifyLens.CORRECTNESS


def test_dedup_key_prefers_locator_then_claim_hash():
    a = Finding(claim="bug here", locator="x.py:10")
    b = Finding(claim="bug here", locator="x.py:10")
    c = Finding(claim="some unrelated claim")
    assert a.dedup_key() == b.dedup_key()
    assert a.dedup_key() != c.dedup_key()
    # no-locator findings dedup by normalized claim hash
    d = Finding(claim="Some Unrelated   Claim!!")
    assert c.dedup_key() == d.dedup_key()


def test_dedupe_findings_merges_evidence():
    fs = [
        Finding(claim="leak", locator="a.py:1", evidence="path A"),
        Finding(claim="leak", locator="a.py:1", evidence="path B"),
        Finding(claim="other", locator="b.py:2", evidence="x"),
    ]
    out = dedupe_findings(fs)
    assert len(out) == 2
    leak = next(f for f in out if f.locator == "a.py:1")
    assert "path A" in leak.evidence and "path B" in leak.evidence


def test_vote_refuted_follows_verdict():
    v = VerifierVote(VerifyLens.SECURITY, Verdict.REFUTED).validate()
    assert v.refuted is True
    v2 = VerifierVote(VerifyLens.SECURITY, Verdict.CONFIRMED, refuted=True).validate()
    assert v2.refuted is False  # normalized from verdict


def test_subtask_to_delegate_task_shape():
    s = SubtaskSpec(goal="find bugs", context="in foo.py", toolsets=["file"], role="leaf").validate()
    t = s.to_delegate_task()
    assert t == {"goal": "find bugs", "context": "in foo.py", "toolsets": ["file"]}
    # orchestrator role is carried; leaf is omitted (delegate default)
    s2 = SubtaskSpec(goal="coordinate", role="orchestrator").validate()
    assert s2.to_delegate_task()["role"] == "orchestrator"
    # invalid role coerces to leaf
    s3 = SubtaskSpec(goal="x", role="bogus").validate()
    assert s3.role == "leaf"


def test_stage_result_serializes():
    sr = StageResult(stage="find", findings=[Finding(claim="c", locator="z:1")], caps_announced=["capped at 8"])
    d = sr.as_dict()
    assert d["stage"] == "find"
    assert d["caps_announced"] == ["capped at 8"]
    assert d["findings"][0]["claim"] == "c"
