# Copyright © 2026 SurgeXi Business Intelligence, a Teamsmith Enterprises LLC company. All Rights Reserved.
"""Minimal, runnable reference for tiered LLM routing.

Loads a tier config, classifies a request, and picks the cheapest *healthy*
tier that has the required capability. Tiers that fail health checks trip a
circuit breaker and are skipped until cooldown expires.

This is a PATTERN, not a product: the health check and the "generate" call are
deliberately stubbed so the file runs with no external services. Wire in your
own backends where the TODOs are marked.

    python -m router.serve            # runs the built-in demo
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    cooldown_s: float = 120.0
    _failures: int = 0
    _opened_at: float | None = None

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self.cooldown_s:
            # cooldown elapsed: half-open, give the tier another chance
            self._opened_at = None
            self._failures = 0
            return False
        return True


@dataclass
class Tier:
    name: str
    endpoint: str
    cost_per_1k: float
    capabilities: list[str]
    timeout_s: float = 30.0
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def health_check(self) -> bool:
        """Fast liveness probe.

        TODO: replace with a real GET {endpoint}/models (or equivalent) with
        self.timeout_s. Returning True here keeps the reference self-contained.
        """
        return True

    def generate(self, prompt: str) -> str:
        """TODO: call the real backend. Stubbed for the reference."""
        return f"[{self.name}] would answer: {prompt!r}"


class Router:
    def __init__(self, tiers: list[Tier], breaker_cfg: dict | None = None):
        # cheapest first; capability + health filtering happens at route time
        self.tiers = sorted(tiers, key=lambda t: t.cost_per_1k)
        bc = breaker_cfg or {}
        for t in self.tiers:
            t.breaker.failure_threshold = bc.get("failure_threshold", 3)
            t.breaker.cooldown_s = bc.get("cooldown_s", 120)

    @staticmethod
    def classify(prompt: str) -> str:
        """Toy classifier: map a request to the capability it needs.

        TODO: swap for a real complexity/sensitivity classifier.
        """
        return "reasoning" if len(prompt) > 200 else "chat"

    def route(self, prompt: str) -> str:
        capability = self.classify(prompt)
        for tier in self.tiers:
            if not tier.supports(capability):
                continue
            if tier.breaker.is_open():
                continue
            if not tier.health_check():
                tier.breaker.record_failure()
                continue
            try:
                result = tier.generate(prompt)
                tier.breaker.record_success()
                return result
            except Exception:  # noqa: BLE001 — reference: any backend error escalates
                tier.breaker.record_failure()
                continue
        raise RuntimeError(f"no healthy tier serves capability={capability!r}")


def _expand_env(value):
    return os.path.expandvars(value) if isinstance(value, str) else value


def load_config(path: str | os.PathLike) -> tuple[list[Tier], dict]:
    data = yaml.safe_load(Path(path).read_text())
    tiers = [
        Tier(
            name=t["name"],
            endpoint=_expand_env(t["endpoint"]),
            cost_per_1k=float(t["cost_per_1k"]),
            capabilities=list(t["capabilities"]),
            timeout_s=float(t.get("timeout_s", 30)),
        )
        for t in data["tiers"]
    ]
    breaker_cfg = data.get("routing", {}).get("circuit_breaker", {})
    return tiers, breaker_cfg


def main() -> None:
    here = Path(__file__).resolve().parent.parent
    cfg = here / "config.yaml"
    if not cfg.exists():
        cfg = here / "config.example.yaml"
    tiers, breaker_cfg = load_config(cfg)
    router = Router(tiers, breaker_cfg)

    print(f"Loaded {len(tiers)} tiers from {cfg.name}: "
          f"{', '.join(t.name for t in router.tiers)}\n")
    for prompt in ["What's the weather pattern?", "Explain " + "x" * 220]:
        print(router.route(prompt))


if __name__ == "__main__":
    main()
