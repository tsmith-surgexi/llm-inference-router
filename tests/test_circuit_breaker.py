# Copyright © 2026 SurgeXi Business Intelligence, a Teamsmith Enterprises LLC company. All Rights Reserved.
"""Unit tests for the per-tier circuit breaker.

These prove the breaker's state machine in isolation, without any router or
backend: it opens after N consecutive failures, short-circuits while open, and
half-opens (self-heals) once the cooldown window has elapsed.
"""
from __future__ import annotations

from router.serve import CircuitBreaker


def test_starts_closed():
    cb = CircuitBreaker(failure_threshold=3)
    assert cb.is_open() is False


def test_stays_closed_below_threshold():
    cb = CircuitBreaker(failure_threshold=3)
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open() is False


def test_opens_at_threshold():
    cb = CircuitBreaker(failure_threshold=3)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open() is True


def test_success_resets_the_failure_count():
    cb = CircuitBreaker(failure_threshold=3)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()  # counter back to zero
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open() is False  # only 2 since reset, not 4


def test_half_opens_after_cooldown(monkeypatch):
    # cooldown of 5s; drive the clock with a controllable monotonic()
    now = {"t": 1000.0}
    monkeypatch.setattr("router.serve.time.monotonic", lambda: now["t"])

    cb = CircuitBreaker(failure_threshold=2, cooldown_s=5.0)
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open() is True  # opened at t=1000

    now["t"] = 1004.9  # still inside the cooldown window
    assert cb.is_open() is True

    now["t"] = 1005.0  # cooldown elapsed -> half-open, tier gets another chance
    assert cb.is_open() is False
    # half-open also cleared the failure history
    cb.record_failure()
    assert cb.is_open() is False
