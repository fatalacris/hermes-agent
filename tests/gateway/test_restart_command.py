"""Tests for the Telegram /restart gateway command."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.run import GatewayRunner
from gateway.session import SessionSource
from hermes_cli.commands import resolve_command


def _make_event(text="/restart", chat_id="8224759576", platform=Platform.TELEGRAM):
    source = SessionSource(
        platform=platform,
        chat_id=chat_id,
        user_id="owner",
        user_name="Cristian Fatala",
    )
    return MessageEvent(text=text, source=source)


def _make_runner():
    return object.__new__(GatewayRunner)


class TestRestartCommandRegistry:
    def test_restart_command_is_registered_for_gateway_only(self):
        cmd = resolve_command("restart")
        assert cmd is not None
        assert cmd.name == "restart"
        assert cmd.gateway_only is True


class TestRestartCommandRouting:
    @pytest.mark.asyncio
    async def test_restart_bypasses_auth_for_telegram_owner(self):
        runner = _make_runner()
        event = _make_event()

        with patch.object(runner, "_is_user_authorized", side_effect=AssertionError("auth should not run")):
            runner._handle_restart_command = AsyncMock(return_value="🔄 Restarting Hermes gateway in the background…")
            result = await runner._handle_message(event)

        assert result == "🔄 Restarting Hermes gateway in the background…"
        runner._handle_restart_command.assert_awaited_once_with(event)


class TestHandleRestartCommand:
    @pytest.mark.asyncio
    async def test_rejects_non_owner(self, monkeypatch):
        runner = _make_runner()
        event = _make_event(chat_id="1234567890")
        monkeypatch.delenv("HERMES_MANAGED", raising=False)

        with patch("gateway.run._resolve_hermes_bin", return_value=["/usr/bin/hermes"]), \
             patch("gateway.run.shutil.which", return_value="/usr/bin/setsid"), \
             patch("gateway.run.subprocess.Popen") as popen:
            result = await runner._handle_restart_command(event)

        assert "restricted to the Telegram owner" in result
        popen.assert_not_called()

    @pytest.mark.asyncio
    async def test_spawns_detached_restart_for_owner(self, monkeypatch, tmp_path):
        runner = _make_runner()
        event = _make_event()
        monkeypatch.delenv("HERMES_MANAGED", raising=False)

        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()

        mock_popen = MagicMock()
        with patch("gateway.run._hermes_home", hermes_home), \
             patch("gateway.run._resolve_hermes_bin", return_value=["/usr/bin/hermes"]), \
             patch("gateway.run.shutil.which", return_value="/usr/bin/setsid"), \
             patch("gateway.run.subprocess.Popen", mock_popen):
            result = await runner._handle_restart_command(event)

        assert "Restarting Hermes gateway in the background" in result
        call_args = mock_popen.call_args[0][0]
        assert call_args[:3] == ["/usr/bin/setsid", "bash", "-c"]
        assert "hermes gateway restart" in call_args[3]
        assert "PYTHONUNBUFFERED=1" in call_args[3]
        assert mock_popen.call_args.kwargs["start_new_session"] is True

        pending_path = hermes_home / ".gateway_restart_pending.json"
        assert pending_path.exists()
        data = json.loads(pending_path.read_text())
        assert data["platform"] == "telegram"
        assert data["chat_id"] == "8224759576"
        assert data["user_id"] == "owner"
        assert data["session_key"]
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_rejects_non_telegram_platform(self, monkeypatch):
        runner = _make_runner()
        event = _make_event(platform=Platform.DISCORD)
        monkeypatch.delenv("HERMES_MANAGED", raising=False)

        result = await runner._handle_restart_command(event)

        assert "only available from Telegram" in result
