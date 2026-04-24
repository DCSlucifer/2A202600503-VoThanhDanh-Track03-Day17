# Deep dive — s08_precision

**Title**: Irrelevant query — precision test
**Category**: precision

> Agent must NOT leak unrelated preferences into an off-topic question.

## Aggregates

| Metric | With-mem | No-mem | Δ |
|---|---|---|---|
| response_relevance | 1.000 | 1.000 | +0.000 |
| context_utilization | 0.000 | 0.000 | +0.000 |
| token_efficiency | 16.667 | 16.667 | +0.000 |
| memory_hit_rate | 0.000 | 0.000 | +0.000 |
| user_satisfaction_proxy | 1.000 | 1.000 | +0.000 |

## Turn-by-turn (with-mem)

**Session 0 / Turn 0** — user: _Tôi thích Python._
> Got it — noting that preference for later.
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=1.00 · hit=0.00

**Session 1 / Turn 0** — user: _What's the boiling point of water?_
> Here's a generic response to: What's the boiling point of water?
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=1.00 · hit=0.00

## Turn-by-turn (no-mem)

**Session 0 / Turn 0** — user: _Tôi thích Python._
> Got it — noting that preference for later.
- relevance=1.00

**Session 1 / Turn 0** — user: _What's the boiling point of water?_
> Here's a generic response to: What's the boiling point of water?
- relevance=1.00
