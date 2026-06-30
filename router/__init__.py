"""llm-inference-router — a health-aware, cost-optimized tiered LLM routing pattern.

Reference implementation. Generic by design: wire in your own tiers via config.yaml.
"""

__all__ = ["Tier", "Router", "CircuitBreaker"]
