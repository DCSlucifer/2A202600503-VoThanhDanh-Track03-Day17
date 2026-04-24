# Deep dive — s07_ambiguous_multi

**Title**: Ambiguous intent — multi-memory recall
**Category**: routing

> Router should fan out to preference + episodic backends.

## Aggregates

| Metric | With-mem | No-mem | Δ |
|---|---|---|---|
| response_relevance | 0.667 | 0.667 | +0.000 |
| context_utilization | 0.000 | 0.000 | +0.000 |
| token_efficiency | 9.431 | 9.431 | +0.000 |
| memory_hit_rate | 0.000 | 0.000 | +0.000 |
| user_satisfaction_proxy | 0.800 | 0.800 | +0.000 |

## Turn-by-turn (with-mem)

**Session 0 / Turn 0** — user: _Tôi thích Python._
> Got it — noting that preference for later.
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=1.00 · hit=0.00

**Session 0 / Turn 1** — user: _Also, I was confused about decorators once._
> Here's a generic response to: Also, I was confused about decorators once.
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=1.00 · hit=0.00

**Session 1 / Turn 0** — user: _Remind me what I prefer and what tripped me up before._
> Got it — noting that preference for later.
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=0.00 · hit=0.00

## Turn-by-turn (no-mem)

**Session 0 / Turn 0** — user: _Tôi thích Python._
> Got it — noting that preference for later.
- relevance=1.00

**Session 0 / Turn 1** — user: _Also, I was confused about decorators once._
> Here's a generic response to: Also, I was confused about decorators once.
- relevance=1.00

**Session 1 / Turn 0** — user: _Remind me what I prefer and what tripped me up before._
> Got it — noting that preference for later.
- relevance=0.00
