# Deep dive — s10_cold_start

**Title**: Cold-start — empty memory should not break the agent
**Category**: robustness

> Control scenario — no memory content exists. With-mem and no-mem should both produce sane output.

## Aggregates

| Metric | With-mem | No-mem | Δ |
|---|---|---|---|
| response_relevance | 1.000 | 1.000 | +0.000 |
| context_utilization | 0.000 | 0.000 | +0.000 |
| token_efficiency | 13.460 | 13.460 | +0.000 |
| memory_hit_rate | 0.000 | 0.000 | +0.000 |
| user_satisfaction_proxy | 1.000 | 1.000 | +0.000 |

## Turn-by-turn (with-mem)

**Session 0 / Turn 0** — user: _Hello, can you help me with something?_
> Here's a generic response to: Hello, can you help me with something?
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=1.00 · hit=0.00

**Session 0 / Turn 1** — user: _Which language should I use for a tiny script?_
> I don't have a saved preference yet — could you tell me which language you'd like to use?
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=1.00 · hit=0.00

## Turn-by-turn (no-mem)

**Session 0 / Turn 0** — user: _Hello, can you help me with something?_
> Here's a generic response to: Hello, can you help me with something?
- relevance=1.00

**Session 0 / Turn 1** — user: _Which language should I use for a tiny script?_
> I don't have a saved preference yet — could you tell me which language you'd like to use?
- relevance=1.00
