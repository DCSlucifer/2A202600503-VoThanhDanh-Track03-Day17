# Deep dive — s03_pref_contradiction

**Title**: Preference contradiction / update (conflict resolver)
**Category**: preference

> After the user flips, newer preference must win — older entry moves to history.

## Aggregates

| Metric | With-mem | No-mem | Δ |
|---|---|---|---|
| response_relevance | 1.000 | 0.667 | +0.333 |
| context_utilization | 0.101 | 0.000 | +0.101 |
| token_efficiency | 13.650 | 11.303 | +2.347 |
| memory_hit_rate | 0.333 | 0.000 | +0.333 |
| user_satisfaction_proxy | 1.000 | 0.800 | +0.200 |

## Turn-by-turn (with-mem)

**Session 0 / Turn 0** — user: _Tôi thích Python._
> Got it — noting that preference for later.
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=1.00 · hit=0.00

**Session 1 / Turn 0** — user: _Actually I prefer Rust now._
> Got it — noting that preference for later.
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=1.00 · hit=0.00

**Session 1 / Turn 1** — user: _Which language should I use for a CLI tool?_
> Going with Rust since you've told me you prefer it.
- recall: prefs=1 facts=0 episodes=0 semantic=2 · relevance=1.00 · hit=1.00

## Turn-by-turn (no-mem)

**Session 0 / Turn 0** — user: _Tôi thích Python._
> Got it — noting that preference for later.
- relevance=1.00

**Session 1 / Turn 0** — user: _Actually I prefer Rust now._
> Got it — noting that preference for later.
- relevance=1.00

**Session 1 / Turn 1** — user: _Which language should I use for a CLI tool?_
> I don't have a saved preference yet — could you tell me which language you'd like to use?
- relevance=0.00
