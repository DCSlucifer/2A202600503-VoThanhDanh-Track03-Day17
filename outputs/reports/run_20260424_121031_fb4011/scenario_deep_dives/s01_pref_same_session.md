# Deep dive — s01_pref_same_session

**Title**: Preference capture + same-session use
**Category**: preference

> Covers the minimal write→read loop within a single session.

## Aggregates

| Metric | With-mem | No-mem | Δ |
|---|---|---|---|
| response_relevance | 1.000 | 0.750 | +0.250 |
| context_utilization | 0.116 | 0.000 | +0.116 |
| token_efficiency | 12.037 | 11.111 | +0.926 |
| memory_hit_rate | 0.500 | 0.000 | +0.500 |
| user_satisfaction_proxy | 1.000 | 0.850 | +0.150 |

## Turn-by-turn (with-mem)

**Session 0 / Turn 0** — user: _Tôi thích Python._
> Got it — noting that preference for later.
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=1.00 · hit=0.00

**Session 0 / Turn 1** — user: _Which language should I use for a short web-scraper script?_
> Going with Python since you've told me you prefer it. Here's a short Python sketch: ```python def solve(x):     return x  # replace with your logic ```
- recall: prefs=1 facts=0 episodes=0 semantic=1 · relevance=1.00 · hit=1.00

## Turn-by-turn (no-mem)

**Session 0 / Turn 0** — user: _Tôi thích Python._
> Got it — noting that preference for later.
- relevance=1.00

**Session 0 / Turn 1** — user: _Which language should I use for a short web-scraper script?_
> I don't have a saved preference yet — could you tell me which language you'd like to use?
- relevance=0.50
