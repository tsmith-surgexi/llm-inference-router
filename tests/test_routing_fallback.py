# Copyright © 2026 SurgeXi Business Intelligence, a Teamsmith Enterprises LLC company. All Rights Reserved.
"""Behavioural tests for tiered routing + fallback.

No network and no models: every tier is a StubTier whose health and generate
behaviour is scripted. These prove the headline claim of the project — when a
tier is unhealthy or failing, the router skips it and falls through to the next
capable tier; and after the failure threshold a tier's breaker opens and
short-circuits it entirely.
"""
from __future__ import annotations

import pytest

from router.serve import Router, Tier


class StubTier(Tier):
    """A Tier with scripted health/generate and call counters, no I/O."""

    def __init__(self, *args, healthy: bool = True, raises: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self._healthy = healthy
        self._raises = raises
        self.health_calls = 0
        self.generate_calls = 0

    def health_check(self) -> bool:
        self.health_calls += 1
        return self._healthy

    def generate(self, prompt: str) -> str:
        self.generate_calls += 1
        if self._raises:
            raise RuntimeError(f"{self.name} backend exploded")
        return f"[{self.name}] {prompt}"


def make_router(tiers, **breaker_cfg):
    # Router sorts by cost and applies breaker config to every tier.
    return Router(tiers, breaker_cfg or None)


def test_healthy_cheapest_tier_is_preferred():
    cheap = StubTier("cheap", "e", cost_per_1k=0.0, capabilities=["chat"])
    pricey = StubTier("pricey", "e", cost_per_1k=5.0, capabilities=["chat"])
    router = make_router([pricey, cheap])  # deliberately out of cost order

    result = router.route("hi")

    assert result == "[cheap] hi"
    assert cheap.generate_calls == 1
    assert pricey.generate_calls == 0  # never touched — cheap one served it


def test_unhealthy_tier_is_skipped_and_next_tier_serves():
    down = StubTier("down", "e", cost_per_1k=0.0, capabilities=["chat"], healthy=False)
    up = StubTier("up", "e", cost_per_1k=1.0, capabilities=["chat"], healthy=True)
    router = make_router([down, up])

    result = router.route("hello")

    assert result == "[up] hello"          # (a) served by the fallback tier
    assert down.generate_calls == 0        # unhealthy tier never generated
    assert up.generate_calls == 1


def test_erroring_tier_falls_through_to_next():
    boom = StubTier("boom", "e", cost_per_1k=0.0, capabilities=["chat"], raises=True)
    safe = StubTier("safe", "e", cost_per_1k=1.0, capabilities=["chat"])
    router = make_router([boom, safe])

    result = router.route("q")

    assert result == "[safe] q"
    assert boom.generate_calls == 1        # it tried, then raised
    assert safe.generate_calls == 1        # fallback picked it up


def test_capability_filtering_routes_to_the_capable_tier():
    chat_only = StubTier("chat-only", "e", cost_per_1k=0.0, capabilities=["chat"])
    reasoner = StubTier("reasoner", "e", cost_per_1k=9.0, capabilities=["chat", "reasoning"])
    router = make_router([chat_only, reasoner])

    # classify() returns "reasoning" for prompts > 200 chars
    result = router.route("x" * 250)

    assert result.startswith("[reasoner]")
    assert chat_only.generate_calls == 0   # lacks the capability, skipped


def test_breaker_opens_after_threshold_and_short_circuits():
    boom = StubTier("boom", "e", cost_per_1k=0.0, capabilities=["chat"], raises=True)
    safe = StubTier("safe", "e", cost_per_1k=1.0, capabilities=["chat"])
    router = make_router([boom, safe], failure_threshold=3, cooldown_s=999)

    # Drive the failing tier past its threshold. Each route falls back to safe.
    for _ in range(3):
        assert router.route("go") == "[safe] go"

    assert boom.breaker.is_open() is True
    calls_before = boom.generate_calls  # should be exactly 3

    # (b) breaker is open now: further requests short-circuit boom entirely —
    # it is neither health-checked nor generated against.
    boom.health_calls = 0
    assert router.route("again") == "[safe] go".replace("go", "again")
    assert boom.generate_calls == calls_before  # no new attempt
    assert boom.health_calls == 0               # skipped before the health probe


def test_raises_when_no_capable_healthy_tier_exists():
    down = StubTier("down", "e", cost_per_1k=0.0, capabilities=["chat"], healthy=False)
    router = make_router([down])

    with pytest.raises(RuntimeError, match="no healthy tier"):
        router.route("anything")


def test_breaker_reopens_path_after_cooldown(monkeypatch):
    now = {"t": 500.0}
    monkeypatch.setattr("router.serve.time.monotonic", lambda: now["t"])

    boom = StubTier("boom", "e", cost_per_1k=0.0, capabilities=["chat"], raises=True)
    safe = StubTier("safe", "e", cost_per_1k=1.0, capabilities=["chat"])
    router = make_router([boom, safe], failure_threshold=2, cooldown_s=30)

    router.route("a")
    router.route("b")
    assert boom.breaker.is_open() is True

    # Backend recovers; after cooldown the breaker half-opens and re-admits boom.
    boom._raises = False
    now["t"] = 531.0
    assert router.route("c") == "[boom] c"   # cheapest tier is back in service
