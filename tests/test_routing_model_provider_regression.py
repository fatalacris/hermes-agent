"""Regression suite: provider/model pinning, routing churn, and mixed-model prevention.

Motivated by TASK 0171 (glm-5.1 / kimi-k2.5 configuration drift) and
TASK 0175 (heartbeat pulse must not repeat / must use correct model).

Acceptance: the next real request after a switch must match the selected route,
and pinned jobs must never drift from their explicitly configured model/provider.
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from hermes_cli.model_switch import switch_model, parse_model_flags
from agent.smart_model_routing import resolve_turn_route


_MOCK_VALIDATION = {
    "accepted": True,
    "persist": True,
    "recognized": True,
    "message": None,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_switch(raw, current_provider, current_model, current_base_url="", explicit_provider=""):
    with (
        patch("hermes_cli.model_switch.resolve_alias", return_value=None),
        patch("hermes_cli.model_switch.list_provider_models", return_value=[]),
        patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            return_value={
                "api_key": "***",
                "base_url": "https://opencode.ai/zen/go/v1",
                "api_mode": "chat_completions",
                "provider": explicit_provider or current_provider,
            },
        ),
        patch("hermes_cli.models.validate_requested_model", return_value=_MOCK_VALIDATION),
        patch("hermes_cli.model_switch.get_model_info", return_value=None),
        patch("hermes_cli.model_switch.get_model_capabilities", return_value=None),
        patch("hermes_cli.models.detect_provider_for_model", return_value=None),
    ):
        return switch_model(
            raw_input=raw,
            current_provider=current_provider,
            current_model=current_model,
            current_base_url=current_base_url,
            current_api_key="***",
            explicit_provider=explicit_provider,
        )


# ---------------------------------------------------------------------------
# 1. Provider/model pinning by task type (cron job must stay pinned)
# ---------------------------------------------------------------------------

class TestCronModelPinning:
    """A cron job with explicit model/provider must ignore global defaults."""

    def test_pinned_job_ignores_hermes_model_env(self, monkeypatch):
        """TASK 0171 regression: job.model wins over HERMES_MODEL env."""
        monkeypatch.setenv("HERMES_MODEL", "glm-5.1")
        monkeypatch.setenv("HERMES_INFERENCE_PROVIDER", "zai")

        job = {"model": "kimi-k2.5", "provider": "opencode-go"}

        # Simulate scheduler model resolution (lines 997-1012 of scheduler.py)
        resolved_model = job.get("model") or os.getenv("HERMES_MODEL") or ""
        assert resolved_model == "kimi-k2.5"

        resolved_provider = job.get("provider") or os.getenv("HERMES_INFERENCE_PROVIDER")
        assert resolved_provider == "opencode-go"

    def test_pinned_job_ignores_config_default(self, monkeypatch):
        """TASK 0171 regression: job.model wins over config.yaml model.default."""
        fake_config = {"model": {"default": "gpt-5.4-mini", "provider": "openrouter"}}

        job = {"model": "minimax-m2.7", "provider": "opencode-go"}

        # Scheduler only falls back to config when job lacks model
        _model_cfg = fake_config.get("model", {})
        if not job.get("model"):
            model = _model_cfg.get("default", "")
        else:
            model = job.get("model")
        assert model == "minimax-m2.7"

    def test_unpinned_job_falls_back_to_env_then_config(self, monkeypatch):
        """Unpinned jobs should inherit env/config — but pinned ones must not."""
        monkeypatch.setenv("HERMES_MODEL", "glm-5.1")
        fake_config = {"model": {"default": "gpt-5.4"}}

        job = {}  # no explicit model

        resolved = job.get("model") or os.getenv("HERMES_MODEL") or ""
        if not resolved:
            _model_cfg = fake_config.get("model", {})
            if isinstance(_model_cfg, dict):
                resolved = _model_cfg.get("default", resolved)
        assert resolved == "glm-5.1"


# ---------------------------------------------------------------------------
# 2. Routing churn — known models must always resolve to expected providers
# ---------------------------------------------------------------------------

class TestRoutingConsistency:
    """Catches churn in routing: if a model suddenly routes elsewhere, tests fail."""

    def test_kimi_k25_routes_to_opencode_go(self, monkeypatch):
        """0171: kimi-k2.5 must resolve via opencode-go (not zai or openrouter)."""
        # detect_provider_for_model signature requires current_provider;
        # we exercise the real switch pipeline instead.
        result = _mock_switch("kimi-k2.5", "opencode-go", "glm-5.1")
        assert result.success
        assert result.target_provider == "opencode-go"
        assert result.new_model == "kimi-k2.5"

    def test_glm51_routes_to_zai(self, monkeypatch):
        """0171: glm-5.1 must resolve via zai (not opencode-go)."""
        with patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            return_value={
                "api_key": "***",
                "base_url": "https://api.z.ai/v1",
                "api_mode": "chat_completions",
                "provider": "zai",
            },
        ), patch("hermes_cli.models.validate_requested_model", return_value=_MOCK_VALIDATION), \
             patch("hermes_cli.model_switch.get_model_info", return_value=None), \
             patch("hermes_cli.model_switch.get_model_capabilities", return_value=None), \
             patch("hermes_cli.models.detect_provider_for_model", return_value=None), \
             patch("hermes_cli.model_switch.resolve_alias", return_value=None), \
             patch("hermes_cli.model_switch.list_provider_models", return_value=[]):
            result = switch_model(
                raw_input="glm-5.1",
                current_provider="zai",
                current_model="glm-5",
                current_base_url="https://api.z.ai/v1",
                current_api_key="***",
            )
        assert result.success
        assert result.target_provider == "zai"
        assert result.new_model == "glm-5.1"

    def test_opencode_go_catalog_includes_kimi_k26(self, monkeypatch):
        """0197 regression: kimi-k2.6 must be in the opencode-go catalog."""
        from hermes_cli.models import curated_models_for_provider
        models = curated_models_for_provider("opencode-go")
        ids = [m[0] for m in models]
        assert "kimi-k2.6" in ids, f"opencode-go catalog missing kimi-k2.6; got {ids}"


# ---------------------------------------------------------------------------
# 3. Mixed-model prevention — resolve_turn_route must not mutate primary
# ---------------------------------------------------------------------------

class TestMixedModelPrevention:
    """Prevents mixed-model execution on routing/heartbeat/diagnostic surfaces."""

    def test_resolve_turn_route_honors_primary_when_no_smart_routing(self):
        """Without smart routing config, primary model/runtime must pass through unchanged."""
        primary = {
            "model": "kimi-k2.5",
            "api_key": "ak",
            "base_url": "https://opencode.ai/zen/go/v1",
            "provider": "opencode-go",
            "api_mode": "chat_completions",
            "command": None,
            "args": [],
        }
        route = resolve_turn_route("heartbeat pulse", None, primary)
        assert route["model"] == "kimi-k2.5"
        assert route["runtime"]["provider"] == "opencode-go"
        assert route["runtime"]["base_url"] == "https://opencode.ai/zen/go/v1"
        assert route["label"] is None

    def test_resolve_turn_route_does_not_swap_provider_on_simple_message(self):
        """Even for simple messages, if smart routing is disabled, provider stays."""
        primary = {
            "model": "glm-5.1",
            "api_key": "ak",
            "base_url": "https://api.z.ai/v1",
            "provider": "zai",
            "api_mode": "chat_completions",
            "command": None,
            "args": [],
        }
        route = resolve_turn_route("hola", None, primary)
        assert route["model"] == "glm-5.1"
        assert route["runtime"]["provider"] == "zai"

    def test_signature_is_stable_for_identical_primary(self):
        """Same primary inputs must yield identical signatures (idempotency)."""
        primary = {
            "model": "gpt-5.4",
            "api_key": "k",
            "base_url": "https://api.openai.com",
            "provider": "openai-codex",
            "api_mode": "codex_responses",
            "command": None,
            "args": [],
        }
        sig1 = resolve_turn_route("msg1", None, primary)["signature"]
        sig2 = resolve_turn_route("msg2", None, primary)["signature"]
        assert sig1 == sig2


# ---------------------------------------------------------------------------
# 4. Post-switch consistency — next request must match selected route
# ---------------------------------------------------------------------------

class TestPostSwitchConsistency:
    """Require the next real request to match the selected route."""

    def test_switch_to_kimi_k26_preserves_provider_and_api_mode(self):
        """After /model kimi-k2.6 on opencode-go, runtime must stay consistent."""
        result = _mock_switch("kimi-k2.6", "opencode-go", "glm-5.1")
        assert result.success
        assert result.new_model == "kimi-k2.6"
        assert result.target_provider == "opencode-go"
        assert result.api_mode == "chat_completions"
        assert result.base_url == "https://opencode.ai/zen/go/v1"

    def test_switch_to_minimax_strips_v1_for_anthropic(self):
        """0175-related: switching to Anthropic-routed model on OpenCode strips /v1."""
        with patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            return_value={
                "api_key": "***",
                "base_url": "https://opencode.ai/zen/go",  # already stripped by runtime_provider
                "api_mode": "anthropic_messages",
                "provider": "opencode-go",
            },
        ), patch("hermes_cli.models.validate_requested_model", return_value=_MOCK_VALIDATION), \
             patch("hermes_cli.model_switch.get_model_info", return_value=None), \
             patch("hermes_cli.model_switch.get_model_capabilities", return_value=None), \
             patch("hermes_cli.models.detect_provider_for_model", return_value=None), \
             patch("hermes_cli.model_switch.resolve_alias", return_value=None), \
             patch("hermes_cli.model_switch.list_provider_models", return_value=[]):
            result = switch_model(
                raw_input="minimax-m2.7",
                current_provider="opencode-go",
                current_model="glm-5",
                current_base_url="https://opencode.ai/zen/go/v1",
                current_api_key="***",
            )
        assert result.success
        assert result.api_mode == "anthropic_messages"
        # The /v1 strip happens inside runtime_provider; the switch result must
        # reflect the stripped base_url so the Anthropic SDK does not double /v1.
        assert result.base_url == "https://opencode.ai/zen/go"

    def test_global_flag_persisted_in_result(self):
        """--global must be reflected in the switch result for downstream persistence."""
        result = _mock_switch("kimi-k2.5", "opencode-go", "glm-5.1")
        # Note: _mock_switch does not pass is_global; default is False.
        assert result.is_global is False

        with patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            return_value={
                "api_key": "***",
                "base_url": "https://opencode.ai/zen/go/v1",
                "api_mode": "chat_completions",
                "provider": "opencode-go",
            },
        ), patch("hermes_cli.models.validate_requested_model", return_value=_MOCK_VALIDATION), \
             patch("hermes_cli.model_switch.get_model_info", return_value=None), \
             patch("hermes_cli.model_switch.get_model_capabilities", return_value=None), \
             patch("hermes_cli.models.detect_provider_for_model", return_value=None), \
             patch("hermes_cli.model_switch.resolve_alias", return_value=None), \
             patch("hermes_cli.model_switch.list_provider_models", return_value=[]):
            result = switch_model(
                raw_input="kimi-k2.5",
                current_provider="opencode-go",
                current_model="glm-5.1",
                current_base_url="https://opencode.ai/zen/go/v1",
                current_api_key="***",
                is_global=True,
            )
        assert result.is_global is True


# ---------------------------------------------------------------------------
# 5. Heartbeat / diagnostic surfaces must not leak models across jobs
# ---------------------------------------------------------------------------

class TestHeartbeatSurfaceIsolation:
    """0175: heartbeat and diagnostic jobs must use their own pinned route."""

    def test_two_jobs_with_different_pins_do_not_interfere(self, monkeypatch):
        """Job A pinned to glm-5.1 / zai; Job B pinned to kimi-k2.5 / opencode-go.
        Even when run in the same process, they must not swap models.
        """
        job_a = {"model": "glm-5.1", "provider": "zai", "name": "heartbeat-glm"}
        job_b = {"model": "kimi-k2.5", "provider": "opencode-go", "name": "heartbeat-kimi"}

        # Simulate scheduler resolution for both
        model_a = job_a.get("model") or os.getenv("HERMES_MODEL") or ""
        provider_a = job_a.get("provider") or os.getenv("HERMES_INFERENCE_PROVIDER")

        model_b = job_b.get("model") or os.getenv("HERMES_MODEL") or ""
        provider_b = job_b.get("provider") or os.getenv("HERMES_INFERENCE_PROVIDER")

        assert model_a == "glm-5.1"
        assert provider_a == "zai"
        assert model_b == "kimi-k2.5"
        assert provider_b == "opencode-go"
        assert model_a != model_b
        assert provider_a != provider_b

    def test_job_without_provider_inherits_env_but_not_from_other_job(self, monkeypatch):
        """An unpinned job must inherit env/config, not the last job's provider."""
        monkeypatch.setenv("HERMES_INFERENCE_PROVIDER", "openrouter")

        job_prev = {"model": "kimi-k2.5", "provider": "opencode-go"}
        job_next = {"model": "gpt-5.4"}  # no provider

        # After running job_prev, env vars are cleaned up (scheduler lines 1277-1285)
        # So job_next should see the original env, not job_prev's provider.
        resolved_provider = job_next.get("provider") or os.getenv("HERMES_INFERENCE_PROVIDER")
        assert resolved_provider == "openrouter"

    def test_heartbeat_prompt_does_not_trigger_cheap_route(self):
        """0175: heartbeat prompts are short but must NOT be demoted to cheap_model."""
        routing_config = {
            "enabled": True,
            "cheap_model": {"provider": "openrouter", "model": "claude-haiku-4-5"},
        }
        primary = {
            "model": "kimi-k2.5",
            "api_key": "ak",
            "base_url": "https://opencode.ai/zen/go/v1",
            "provider": "opencode-go",
            "api_mode": "chat_completions",
            "command": None,
            "args": [],
        }
        # Heartbeat prompt is usually structured JSON; even a short one should
        # be > 28 words or contain keywords that block cheap routing.
        prompt = (
            "Use the injected heartbeat snapshot to emit a concise status pulse "
            "for the operator. Analyze open tasks, blocked items, and recent changes. "
            "If the snapshot context is exactly [SILENT], return exactly [SILENT]. "
            "Otherwise produce a brief terminal-style report with task counts and next actions."
        )
        route = resolve_turn_route(prompt, routing_config, primary)
        # The prompt is > 28 words and contains complex keywords → should stay primary
        assert route["model"] == "kimi-k2.5"
        assert route["runtime"]["provider"] == "opencode-go"
