"""Lightweight smart routing helper for turn-level model selection.

This module keeps the routing contract small and deterministic:
- If smart routing is disabled or absent, the primary route passes through unchanged.
- If a cheap route is configured and the prompt looks simple enough, route to it.
- Otherwise preserve the primary route.

The helper is intentionally conservative so pinned jobs and heartbeat-style
messages do not drift across provider/model boundaries.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


_SIMPLE_BLOCKLIST = (
    "heartbeat",
    "status pulse",
    "analyze open tasks",
    "blocked items",
    "recent changes",
    "diagnostic",
    "report",
)


def _build_signature(model: str, runtime: Mapping[str, Any]) -> tuple:
    return (
        model,
        runtime.get("provider"),
        runtime.get("base_url"),
        runtime.get("api_mode"),
        runtime.get("command"),
        tuple(runtime.get("args") or ()),
    )


def _copy_runtime(primary: Mapping[str, Any]) -> dict[str, Any]:
    runtime = dict(primary)
    runtime.pop("model", None)
    runtime.pop("label", None)
    runtime.pop("signature", None)
    runtime.pop("request_overrides", None)
    return runtime


def _should_use_cheap_route(prompt: str, routing_config: Mapping[str, Any] | None) -> bool:
    if not routing_config or not routing_config.get("enabled"):
        return False

    cheap_model = routing_config.get("cheap_model")
    if not isinstance(cheap_model, Mapping):
        return False

    text = (prompt or "").strip().lower()
    if not text:
        return False

    word_count = len(text.split())
    if word_count > 28:
        return False

    if any(term in text for term in _SIMPLE_BLOCKLIST):
        return False

    return True


def resolve_turn_route(prompt: str, routing_config: Mapping[str, Any] | None, primary: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve the effective turn route for a single prompt.

    Args:
        prompt: The user message for the turn.
        routing_config: Optional smart-routing config dict.
        primary: The session's pinned model/runtime route.

    Returns:
        A dict with at least:
        - model
        - runtime
        - signature
        - label
        - request_overrides
    """
    primary_model = primary.get("model", "") if isinstance(primary, Mapping) else ""
    primary_runtime = _copy_runtime(primary if isinstance(primary, Mapping) else {})

    route = {
        "model": primary_model,
        "runtime": primary_runtime,
        "signature": _build_signature(primary_model, primary_runtime),
        "label": None,
        "request_overrides": None,
    }

    if not _should_use_cheap_route(prompt, routing_config):
        return route

    cheap_model = routing_config.get("cheap_model")  # type: ignore[union-attr]
    if not isinstance(cheap_model, Mapping):
        return route

    chosen_model = str(cheap_model.get("model") or primary_model)
    chosen_runtime = deepcopy(primary_runtime)

    provider = cheap_model.get("provider")
    if provider:
        chosen_runtime["provider"] = provider

    for key in ("base_url", "api_mode", "command", "args", "api_key", "credential_pool"):
        if key in cheap_model and cheap_model[key] is not None:
            chosen_runtime[key] = cheap_model[key]

    route["model"] = chosen_model
    route["runtime"] = chosen_runtime
    route["signature"] = _build_signature(chosen_model, chosen_runtime)
    route["label"] = str(routing_config.get("label") or "cheap_model")
    route["request_overrides"] = routing_config.get("request_overrides") if isinstance(routing_config, Mapping) else None
    return route
