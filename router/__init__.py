# Copyright © 2026 SurgeXi Business Intelligence, a Teamsmith Enterprises LLC company. All Rights Reserved.
"""llm-inference-router — a health-aware, cost-optimized tiered LLM routing pattern.

Reference implementation. Generic by design: wire in your own tiers via config.yaml.
"""

__all__ = ["Tier", "Router", "CircuitBreaker"]
