# ADR 0002 — Circuit breaker over blind retry

- **Status:** Accepted
- **Context:** When a backend slows down or errors, retrying the same backend
  amplifies load and latency across every in-flight request — the classic
  retry storm that turns a partial outage into a total one.
- **Decision:** Each tier owns a circuit breaker. After `failure_threshold`
  consecutive failures the breaker *opens* and the tier is removed from the pool
  for a `cooldown_s` window. After cooldown it *half-opens*: the next request
  tests it, and success re-arms it while failure re-opens it.
- **Consequences:**
  - ➕ A sick backend is isolated quickly instead of dragging the whole pool.
  - ➕ Recovery is automatic and self-limiting (half-open probe, not a flood).
  - ➖ A tier can be skipped briefly after it has actually recovered (cooldown
    slack). Acceptable: availability beats squeezing out the last few requests
    from a flapping backend.
- **Alternatives considered:** unbounded retries with backoff (still hammers a
  failing backend); health-cache with TTL only (slower to react to sudden
  failure than a failure-counted breaker).
