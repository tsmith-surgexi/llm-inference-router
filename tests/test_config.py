# Copyright © 2026 SurgeXi Business Intelligence, a Teamsmith Enterprises LLC company. All Rights Reserved.
"""Config loading: the shipped example parses and env placeholders expand."""
from __future__ import annotations

from pathlib import Path

from router.serve import Router, load_config

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_example_config_parses_into_tiers():
    tiers, breaker_cfg = load_config(REPO_ROOT / "config.example.yaml")

    names = {t.name for t in tiers}
    assert names == {"local-primary", "specialized", "cloud-fallback"}
    assert breaker_cfg == {"failure_threshold": 3, "cooldown_s": 120}


def test_endpoint_env_vars_are_expanded(monkeypatch, tmp_path):
    monkeypatch.setenv("SPECIALIZED_ENDPOINT", "http://specialized.internal/v1")
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "tiers:\n"
        "  - name: specialized\n"
        "    endpoint: ${SPECIALIZED_ENDPOINT}\n"
        "    cost_per_1k: 0.0\n"
        "    capabilities: [chat]\n"
    )

    tiers, _ = load_config(cfg)

    assert tiers[0].endpoint == "http://specialized.internal/v1"


def test_router_applies_breaker_config_to_every_tier():
    tiers, breaker_cfg = load_config(REPO_ROOT / "config.example.yaml")
    router = Router(tiers, breaker_cfg)

    for tier in router.tiers:
        assert tier.breaker.failure_threshold == 3
        assert tier.breaker.cooldown_s == 120
