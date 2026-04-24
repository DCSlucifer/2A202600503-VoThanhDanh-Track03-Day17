# Deep dive — s04_fact_profile

**Title**: Factual recall - profile allergy correction
**Category**: factual

> Required rubric case: old allergy fact is corrected, and the latest fact wins without keeping a contradictory active profile value.

## Aggregates

| Metric | With-mem | No-mem | Δ |
|---|---|---|---|
| response_relevance | 1.000 | 0.667 | +0.333 |
| context_utilization | 0.077 | 0.000 | +0.077 |
| token_efficiency | 11.530 | 9.166 | +2.364 |
| memory_hit_rate | 0.333 | 0.000 | +0.333 |
| user_satisfaction_proxy | 1.000 | 0.800 | +0.200 |

## Turn-by-turn (with-mem)

**Session 0 / Turn 0** — user: _Tôi dị ứng sữa bò._
> Got it - noting that fact for later.
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=1.00 · hit=0.00

**Session 1 / Turn 0** — user: _À nhầm, tôi dị ứng đậu nành chứ không phải sữa bò._
> Got it - noting that fact for later.
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=1.00 · hit=0.00

**Session 1 / Turn 1** — user: _Tôi dị ứng gì?_
> You are allergic to đậu nành.
- recall: prefs=0 facts=1 episodes=0 semantic=1 · relevance=1.00 · hit=1.00

## Turn-by-turn (no-mem)

**Session 0 / Turn 0** — user: _Tôi dị ứng sữa bò._
> Got it - noting that fact for later.
- relevance=1.00

**Session 1 / Turn 0** — user: _À nhầm, tôi dị ứng đậu nành chứ không phải sữa bò._
> Got it - noting that fact for later.
- relevance=1.00

**Session 1 / Turn 1** — user: _Tôi dị ứng gì?_
> Here's a generic response to: Tôi dị ứng gì?
- relevance=0.00
