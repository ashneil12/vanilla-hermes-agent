"""Approval-gate coverage for the API-server dashboard chat routes."""

import json
import time
from unittest.mock import patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from gateway.config import PlatformConfig
from gateway.platforms.api_server import APIServerAdapter, cors_middleware


class _FakeSessionDb:
    def get_session(self, session_id):
        return {"session_id": session_id, "title": "Approval Test"}

    def ensure_session(self, session_id, source="web"):
        return None

    def get_messages_as_conversation(self, session_id):
        return []


class _FakeAgent:
    def run_conversation(self, user_content, conversation_history=None, persist_user_message=True):
        from tools.approval import _gateway_notify_cbs

        callback = _gateway_notify_cbs.get("sess-approval")
        if callback:
            callback(
                {
                    "approval_id": "approval-1",
                    "command": "python3 <<'EOF'\nprint('hi')\nEOF",
                    "description": "script execution via heredoc",
                    "pattern_key": "script execution via heredoc",
                    "pattern_keys": ["script execution via heredoc"],
                }
            )

        # Give the stream loop a chance to drain the approval frame before the
        # fake run completes, matching a real blocked approval wait.
        time.sleep(0.05)
        return {
            "final_response": "Done",
            "completed": True,
            "messages": [],
            "api_calls": 1,
        }


def _make_adapter(api_key: str = "") -> APIServerAdapter:
    extra = {}
    if api_key:
        extra["key"] = api_key
    return APIServerAdapter(PlatformConfig(enabled=True, extra=extra))


def _create_app(adapter: APIServerAdapter) -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app["api_server_adapter"] = adapter
    app.router.add_post("/api/sessions/{session_id}/chat/stream", adapter._handle_session_chat_stream)
    app.router.add_post("/api/approval/respond", adapter._handle_approval_respond)
    return app


@pytest.mark.asyncio
async def test_session_chat_stream_emits_approval_event(adapter=None):
    adapter = _make_adapter()
    app = _create_app(adapter)

    with (
        patch.object(adapter, "_get_session_db", return_value=_FakeSessionDb()),
        patch.object(adapter, "_create_agent", return_value=_FakeAgent()),
    ):
        async with TestClient(TestServer(app)) as cli:
            response = await cli.post(
                "/api/sessions/sess-approval/chat/stream",
                json={"message": "write the script"},
            )

            assert response.status == 200
            body = await response.text()

    assert "event: approval" in body
    assert '"approval_id": "approval-1"' in body
    assert "script execution via heredoc" in body


@pytest.mark.asyncio
async def test_approval_respond_validates_and_resolves_one_request():
    adapter = _make_adapter(api_key="sk-secret")
    app = _create_app(adapter)

    with patch("tools.approval.resolve_gateway_approval", return_value=1) as resolve:
        async with TestClient(TestServer(app)) as cli:
            response = await cli.post(
                "/api/approval/respond",
                headers={"Authorization": "Bearer sk-secret"},
                json={
                    "session_id": "sess-approval",
                    "choice": "once",
                    "approval_id": "approval-1",
                },
            )

            assert response.status == 200
            payload = await response.json()

    assert payload == {"ok": True, "choice": "once", "resolved": 1}
    resolve.assert_called_once_with("sess-approval", "once", resolve_all=False)


@pytest.mark.asyncio
async def test_approval_respond_rejects_bad_choice():
    adapter = _make_adapter()
    app = _create_app(adapter)

    async with TestClient(TestServer(app)) as cli:
        response = await cli.post(
            "/api/approval/respond",
            json={"session_id": "sess-approval", "choice": "definitely"},
        )

        assert response.status == 400
        payload = await response.json()

    assert "Invalid choice" in json.dumps(payload)
