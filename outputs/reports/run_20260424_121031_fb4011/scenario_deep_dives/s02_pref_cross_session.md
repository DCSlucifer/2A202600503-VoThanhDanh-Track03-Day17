# Deep dive — s02_pref_cross_session

**Title**: Preference cross-session recall (demo #1 and #2)
**Category**: preference

> Proves cross-session recall — the second session has no buffer overlap.

## Aggregates

| Metric | With-mem | No-mem | Δ |
|---|---|---|---|
| response_relevance | 0.667 | 0.500 | +0.167 |
| context_utilization | 0.140 | 0.000 | +0.140 |
| token_efficiency | 7.398 | 7.739 | -0.341 |
| memory_hit_rate | 0.333 | 0.000 | +0.333 |
| user_satisfaction_proxy | 0.800 | 0.700 | +0.100 |

## Turn-by-turn (with-mem)

**Session 0 / Turn 0** — user: _Tôi thích Python, không thích Java._
> Got it — noting that preference for later.
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=1.00 · hit=0.00

**Session 1 / Turn 0** — user: _Which language should I use for a simple script?_
> Going with Python since you've told me you prefer it. Here's a short Python sketch: ```python def solve(x):     return x  # replace with your logic ``` I'll avoid Java because you've mentioned you don't like it.
- recall: prefs=2 facts=0 episodes=0 semantic=2 · relevance=1.00 · hit=1.00

**Session 1 / Turn 1** — user: _Can you write the hello-world version for me?_
> Here's a generic response to: Can you write the hello-world version for me?
- recall: prefs=0 facts=0 episodes=0 semantic=0 · relevance=0.00 · hit=0.00

## Turn-by-turn (no-mem)

**Session 0 / Turn 0** — user: _Tôi thích Python, không thích Java._
> Got it — noting that preference for later.
- relevance=1.00

**Session 1 / Turn 0** — user: _Which language should I use for a simple script?_
> I don't have a saved preference yet — could you tell me which language you'd like to use?
- relevance=0.50

**Session 1 / Turn 1** — user: _Can you write the hello-world version for me?_
> Here's a generic response to: Can you write the hello-world version for me?
- relevance=0.00
