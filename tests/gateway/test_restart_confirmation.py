"""Tests for the gateway restart confirmation marker flow."""

import json
import threading
from unittest.mock import AsyncMock, patch

import pytest

from gateway.config import Platform
from gateway.run import GatewayRunner


def _make_runner():
    return object.__new__(GatewayRunner)


class TestRestartConfirmation:
    @pytest.mark.asyncio
    async def test_sends_confirmation_and_clears_marker(self, tmp_path):
        runner = _make_runner()
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()

        marker_path = hermes_home / ".gateway_restart_pending.json"
        marker_path.write_text(json.dumps({
            "platform": "telegram",
            "chat_id": "8224759576",
            "user_id": "owner",
            "session_key": "telegram:8224759576",
            "timestamp": "2026-04-12T23:26:00",
        }))

        mock_adapter = AsyncMock()
        mock_adapter.send = AsyncMock()
        runner.adapters = {Platform.TELEGRAM: mock_adapter}

        with patch("gateway.run._hermes_home", hermes_home):
            result = await runner._send_restart_confirmation()

        assert result is True
        mock_adapter.send.assert_called_once_with("8224759576", "✅ Hermes gateway restarted.")
        assert not marker_path.exists()

    @pytest.mark.asyncio
    async def test_defers_when_telegram_adapter_is_missing(self, tmp_path):
        runner = _make_runner()
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()

        marker_path = hermes_home / ".gateway_restart_pending.json"
        marker_path.write_text(json.dumps({
            "platform": "telegram",
            "chat_id": "8224759576",
            "user_id": "owner",
        }))

        runner.adapters = {}

        with patch("gateway.run._hermes_home", hermes_home):
            result = await runner._send_restart_confirmation()

        assert result is False
        assert marker_path.exists()

    @pytest.mark.asyncio
    async def test_discards_corrupt_marker(self, tmp_path):
        runner = _make_runner()
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()

        marker_path = hermes_home / ".gateway_restart_pending.json"
        marker_path.write_text("{not-json")
        runner.adapters = {Platform.TELEGRAM: AsyncMock()}

        with patch("gateway.run._hermes_home", hermes_home):
            result = await runner._send_restart_confirmation()

        assert result is True
        assert not marker_path.exists()

    def test_cron_ticker_schedules_restart_confirmation(self, tmp_path):
        runner = _make_runner()
        hermes_home = tmp_path / "hermes"
        hermes_home.mkdir()
        (hermes_home / ".gateway_restart_pending.json").write_text(json.dumps({
            "platform": "telegram",
            "chat_id": "8224759576",
            "user_id": "owner",
        }))

        stop_event = threading.Event()

        def fake_tick(*args, **kwargs):
            stop_event.set()

        runner._send_restart_confirmation = AsyncMock()
        with patch("gateway.run._hermes_home", hermes_home), \
             patch("cron.scheduler.tick", side_effect=fake_tick), \
             patch("gateway.run.asyncio.run_coroutine_threadsafe") as submit:
            from gateway.run import _start_cron_ticker
            _start_cron_ticker(stop_event, adapters={}, loop=object(), runner=runner, interval=0)

        assert submit.called
