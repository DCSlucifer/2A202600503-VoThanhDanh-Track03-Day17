# Deep dive — s05_fact_technical

**Title**: Factual recall - technical stack
**Category**: factual

> Second profile fact path: the user stores a technical stack fact and recalls it in a new session.

## Aggregates

| Metric | With-mem | No-mem | Δ |
|---|---|---|---|
| response_relevance | 1.000 | 0.500 | +0.500 |
| context_utilization | 0.180 | 0.000 | +0.180 |
| token_efficiency | 13.039 | 7.936 | +5.102 |
| memory_hit_rate | 0.500 | 0.000 | +0.500 |
| user_satisfaction_proxy | 1.000 | 0.700 | +0.300 |

## Turn-by-turn (with-mem)

**Session 0 / Turn 0** — user: _I'm using Postgres 15 for this project._
> Got it - noting that fact for later.
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=1.00 · hit=0.00

**Session 1 / Turn 0** — user: _Remind me what database version I'm using?_
> You're using Postgres 15 for this project.
- recall: prefs=0 facts=1 episodes=0 semantic=1 · relevance=1.00 · hit=1.00

## Turn-by-turn (no-mem)

**Session 0 / Turn 0** — user: _I'm using Postgres 15 for this project._
> Got it - noting that fact for later.
- relevance=1.00

**Session 1 / Turn 0** — user: _Remind me what database version I'm using?_
> Here's a generic response to: Remind me what database version I'm using?
- relevance=0.00
