"""Contract tests for the GHCR image publish workflow."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docker-publish.yml"


def test_workflow_can_publish_non_floating_manual_canary_tag() -> None:
    text = WORKFLOW.read_text()

    assert "publish_tag:" in text
    assert "Validate manual publish tag" in text
    assert "Push manual image tag" in text
    assert 'docker tag "${image}:test"' in text
    assert 'docker push "${image}:${{ steps.manual_tag.outputs.tag }}"' in text


def test_manual_publish_tag_cannot_move_production_floating_tags() -> None:
    text = WORKFLOW.read_text()

    assert "latest|stable" in text
    assert "Refusing to publish floating production tag" in text
    assert "Move :latest and :stable to this SHA" in text, (
        "Production floating tags should still move only through the guarded "
        "main-branch ancestor check."
    )


def test_smoke_test_image_carries_revision_label_for_registry_audits() -> None:
    text = WORKFLOW.read_text()

    assert "org.opencontainers.image.revision=${{ github.sha }}" in text
