# ADR 0001 — Route by cost-then-capability, not by provider

- **Status:** Accepted
- **Context:** Hard-coding a model per call site couples the product to one
  provider's uptime, pricing, and capabilities. Changing models means changing
  code in many places.
- **Decision:** Treat models as a *prioritized pool*. Sort tiers cheapest-first;
  serve each request from the first tier that (a) is healthy and (b) advertises
  the required capability tag. Provider identity is irrelevant to the caller.
- **Consequences:**
  - ➕ Trivial requests are served by the cheapest capable tier automatically.
  - ➕ Adding/removing a model is a config change (a new tier entry), not code.
  - ➕ The caller depends on a *capability*, never on a specific vendor.
  - ➖ Cost-first can pick a "good enough" smaller model; mitigated by forcing
    escalation via a stricter capability tag (e.g. `reasoning`).
- **Alternatives considered:** static primary+secondary failover (too rigid,
  no cost awareness); a learned router on every request (higher quality, but
  adds latency/complexity — kept as a pluggable upgrade, not the default).
